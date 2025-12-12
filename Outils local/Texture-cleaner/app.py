"""
2D Texture Listing - Application Windows
Comparateur d'images entre fichiers source et dossier avec suppression directe
"""

import sys
import os
import re
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QScrollArea, QGridLayout, QFrame,
    QSplitter, QGroupBox, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QFont
import ctypes

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class ImageThumbnail(QFrame):
    """Widget pour afficher une miniature d'image avec bouton de suppression"""
    deleteRequested = pyqtSignal(str)
    
    def __init__(self, file_path, file_name, file_size, show_delete=False):
        super().__init__()
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.marked_for_deletion = False
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setMaximumWidth(180)
        
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # Image
        self.image_label = QLabel()
        self.image_label.setFixedSize(150, 120)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2e2e4e; border-radius: 5px;")
        
        if os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(150, 120, Qt.AspectRatioMode.KeepAspectRatio, 
                                              Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("🖼️")
                self.image_label.setStyleSheet("background-color: #f0f0f0; font-size: 40px;")
        
        layout.addWidget(self.image_label)
        
        # Nom du fichier
        name_label = QLabel(file_name)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 11px; color: #f1f1f1;")
        name_label.setMaximumWidth(150)
        layout.addWidget(name_label)
        
        # Taille du fichier
        size_label = QLabel(self.format_file_size(file_size))
        size_label.setStyleSheet("font-size: 10px; color: #aaa; font-weight: bold;")
        layout.addWidget(size_label)
        
        # Bouton de suppression
        if show_delete:
            self.delete_btn = QPushButton("🗑️ Supprimer")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 5px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
            self.delete_btn.clicked.connect(self.toggle_delete_mark)
            layout.addWidget(self.delete_btn)
        
        self.setLayout(layout)
        self.update_style()
    
    def toggle_delete_mark(self):
        self.marked_for_deletion = not self.marked_for_deletion
        if self.marked_for_deletion:
            self.delete_btn.setText("✓ Marqué")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4caf50;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 5px;
                    font-size: 11px;
                }
            """)
        else:
            self.delete_btn.setText("🗑️ Supprimer")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 5px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
        self.update_style()
        self.deleteRequested.emit(self.file_path)
    
    def update_style(self):
        if self.marked_for_deletion:
            self.setStyleSheet("QFrame { background-color: #3e3e5e; opacity: 0.5; border: 2px solid #f44336; border-radius: 8px; }")
        else:
            self.setStyleSheet("QFrame { background-color: #16213e; border: 2px solid #533483; border-radius: 8px; }")
    
    @staticmethod
    def format_file_size(bytes_size):
        if bytes_size == 0:
            return '0 B'
        k = 1024
        sizes = ['B', 'KB', 'MB', 'GB']
        i = 0
        size = bytes_size
        while size >= k and i < len(sizes) - 1:
            size /= k
            i += 1
        return f"{size:.2f} {sizes[i]}"


class TextureCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2D Texture Listing - Comparateur d'Images")
        self.setGeometry(100, 100, 1600, 900)
        
        # État de l'application
        self.source_files = []  # Liste des noms de fichiers trouvés dans les sources
        self.imported_source_files = []  # Liste des fichiers texte importés avec chemins
        self.folder_files = []  # Liste des fichiers du dossier avec chemins complets
        self.current_folder_path = ""  # Chemin du dossier actuel
        
        self.setWindowIcon(QIcon(resource_path('icone_final.ico')))
        self.init_ui()
    
    def init_ui(self):
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Header
        header_container = QWidget()
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        header_container.setLayout(header_layout)
        header_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 15px;
            }
            QLabel {
                background: transparent;
                color: white;
            }
        """)
        
        header = QLabel("🖼️ 2D Texture Listing")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 24px; font-weight: bold; margin-top: 10px;")
        header_layout.addWidget(header)
        
        subtitle = QLabel("Comparateur d'images entre fichier source et dossier")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #e0e0e0; margin-bottom: 10px;")
        header_layout.addWidget(subtitle)
        
        main_layout.addWidget(header_container)
        
        # Splitter pour les 3 colonnes
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Colonne 1: Fichiers source
        col1 = self.create_source_column()
        splitter.addWidget(col1)
        
        # Colonne 2: Dossier
        col2 = self.create_folder_column()
        splitter.addWidget(col2)
        
        # Colonne 3: Statistiques
        col3 = self.create_stats_column()
        splitter.addWidget(col3)
        
        splitter.setSizes([500, 500, 400])
        main_layout.addWidget(splitter)
        
        # Style global - Mode sombre
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
            }
            QGroupBox {
                background-color: #0f3460;
                border: 2px solid #533483;
                border-radius: 15px;
                padding: 15px;
                font-weight: bold;
                font-size: 14px;
                color: #e94560;
            }
            QGroupBox::title {
                color: #e94560;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
            }
            QPushButton {
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
            }
            QLabel {
                color: #f1f1f1;
            }
            QRadioButton {
                color: #f1f1f1;
            }
            QLineEdit {
                background-color: #1a1a2e;
                color: #f1f1f1;
                border: 1px solid #533483;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget {
                background-color: #1a1a2e;
                color: #f1f1f1;
                border: 1px solid #533483;
            }
        """)
    
    def create_source_column(self):
        group = QGroupBox("📄 Fichier Source")
        layout = QVBoxLayout()
        
        # Layout boutons
        btn_layout = QHBoxLayout()
        
        # Bouton de sélection
        select_btn = QPushButton("📁 Sélectionner des fichiers")
        select_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5a6fd8, stop:1 #6a4390);
            }
        """)
        select_btn.clicked.connect(self.select_source_files)
        btn_layout.addWidget(select_btn)
        
        # Bouton actualiser (Icone)
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.setToolTip("Recharger les fichiers sources")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00d9ff, stop:1 #00a8cc);
                color: white;
                font-size: 20px;
            }
        """)
        refresh_btn.clicked.connect(self.reload_source_files)
        btn_layout.addWidget(refresh_btn)
        
        layout.addLayout(btn_layout)
        
        # Liste des fichiers importés
        self.imported_files_list = QListWidget()
        self.imported_files_list.setMaximumHeight(150)
        self.imported_files_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a2e;
                border-radius: 8px;
                padding: 5px;
                border: 1px solid #533483;
            }
            QListWidget::item {
                background-color: #0f3460;
                border-left: 3px solid #e94560;
                border-radius: 5px;
                padding: 8px;
                margin: 3px;
                color: #f1f1f1;
            }
            QListWidget::item:hover {
                background-color: #16213e;
            }
        """)
        layout.addWidget(QLabel("📋 Fichiers importés:"))
        layout.addWidget(self.imported_files_list)
        

        
        # Recherche
        self.source_search = QLineEdit()
        self.source_search.setPlaceholderText("🔍 Rechercher...")
        self.source_search.textChanged.connect(self.refresh_source_list)
        layout.addWidget(self.source_search)
        
        # Liste des images (Créée avant les filtres pour éviter le crash)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.source_list_widget = QWidget()
        self.source_list_layout = QVBoxLayout()
        self.source_list_widget.setLayout(self.source_list_layout)
        scroll.setWidget(self.source_list_widget)
        
        # Filtres
        filter_layout = QHBoxLayout()
        self.source_filter_group = QButtonGroup()
        
        filters = [("Tous", "all"), (".jpg", ".jpg"), (".png", ".png"), 
                   (".jpeg", ".jpeg"), (".webp", ".webp")]
        for i, (label, value) in enumerate(filters):
            radio = QRadioButton(label)
            radio.setProperty("filter_value", value)
            radio.toggled.connect(self.refresh_source_list)
            self.source_filter_group.addButton(radio, i)
            filter_layout.addWidget(radio)
            if value == "all":
                radio.setChecked(True)
        
        layout.addLayout(filter_layout)
        layout.addWidget(scroll)
        
        group.setLayout(layout)
        return group
    
    def create_folder_column(self):
        group = QGroupBox("📁 Dossier d'Images")
        layout = QVBoxLayout()
        
        # Layout boutons
        btn_layout = QHBoxLayout()

        # Bouton de sélection
        select_btn = QPushButton("📂 Sélectionner un dossier")
        select_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5a6fd8, stop:1 #6a4390);
            }
        """)
        select_btn.clicked.connect(self.select_folder)
        btn_layout.addWidget(select_btn)
        
        # Bouton actualiser (Icone)
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.setToolTip("Rescanner le dossier")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00d9ff, stop:1 #00a8cc);
                color: white;
                font-size: 20px;
            }
        """)
        refresh_btn.clicked.connect(self.reload_folder_files)
        btn_layout.addWidget(refresh_btn)
        
        layout.addLayout(btn_layout)
        

        
        # Recherche
        self.folder_search = QLineEdit()
        self.folder_search.setPlaceholderText("🔍 Rechercher...")
        self.folder_search.textChanged.connect(self.refresh_folder_list)
        layout.addWidget(self.folder_search)
        
        # Liste des images (Créée avant les filtres)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.folder_list_widget = QWidget()
        self.folder_list_layout = QVBoxLayout()
        self.folder_list_widget.setLayout(self.folder_list_layout)
        scroll.setWidget(self.folder_list_widget)

        # Filtres
        filter_layout = QHBoxLayout()
        self.folder_filter_group = QButtonGroup()
        
        filters = [("Tous", "all"), ("✅ Présents", "green"), ("❌ Manquants", "red")]
        for i, (label, value) in enumerate(filters):
            radio = QRadioButton(label)
            radio.setProperty("filter_value", value)
            radio.toggled.connect(self.refresh_folder_list)
            self.folder_filter_group.addButton(radio, i)
            filter_layout.addWidget(radio)
            if value == "all":
                radio.setChecked(True)
        
        layout.addLayout(filter_layout)
        layout.addWidget(scroll)
        
        group.setLayout(layout)
        return group
    
    def create_stats_column(self):
        group = QGroupBox("📊 Statistiques")
        layout = QVBoxLayout()
        
        # Légende
        legend_group = QGroupBox("Légende")
        legend_layout = QVBoxLayout()
        legend_layout.addWidget(QLabel("🔵 Fichier source uniquement"))
        legend_layout.addWidget(QLabel("🟢 Présent dans les deux"))
        legend_layout.addWidget(QLabel("🔴 Dossier uniquement"))
        legend_group.setLayout(legend_layout)
        layout.addWidget(legend_group)
        
        # Cartes statistiques
        self.stat_source = self.create_stat_card("Images dans le fichier source", "#667eea", 
                                                  lambda: self.show_modal('source'))
        self.stat_folder = self.create_stat_card("Images dans le dossier", "#667eea",
                                                  lambda: self.show_modal('folder'))
        self.stat_match = self.create_stat_card("Correspondances", "#667eea",
                                                 lambda: self.show_modal('match'))
        self.stat_missing = self.create_stat_card("Uniquement dans le dossier", "#f44336",
                                                   lambda: self.show_modal('missing'))
        
        layout.addWidget(self.stat_source)
        layout.addWidget(self.stat_folder)
        layout.addWidget(self.stat_match)
        layout.addWidget(self.stat_missing)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
    
    def create_stat_card(self, label_text, color, click_handler):
        card = QPushButton()
        card.setMinimumHeight(120)
        card.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: white;
                border-radius: 10px;
                text-align: center;
                font-size: 16px;
                font-weight: bold;
                padding: 15px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        card.clicked.connect(click_handler)
        card.setProperty("count", 0)
        card.setProperty("fileSize", "0 B")
        card.setProperty("label", label_text)
        card.setProperty("color", color)
        self.update_stat_card(card)
        return card
    
    def update_stat_card(self, card):
        count = card.property("count")
        size = card.property("fileSize")
        label = card.property("label")
        # Format avec nombre en gros, label en petit, taille en bas
        card.setText(f"{count}\n{label}\n{size}")
        card.setStyleSheet(card.styleSheet() + f"""
            QPushButton {{
                line-height: 1.4;
            }}
        """)
    
    def select_source_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Sélectionner des fichiers source",
            "", "Fichiers texte (*.json *.js *.txt *.babylon);;Tous les fichiers (*.*)"
        )
        
        if files:
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        images = self.extract_images_from_text(content)
                        
                        self.imported_source_files.append({
                            'filePath': file_path,
                            'fileName': os.path.basename(file_path),
                            'images': images,
                            'imageCount': len(images)
                        })
                except Exception as e:
                    QMessageBox.warning(self, "Erreur", f"Erreur lors de la lecture de {file_path}:\n{str(e)}")
            
            self.update_source_files_list()
            self.update_imported_files_list()
            self.refresh_source_list()
            self.update_stats()
    
    def extract_images_from_text(self, text):
        """Extrait les noms de fichiers d'images du texte"""
        images = set()
        patterns = [
            r'"([^"]*\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|tif))"',
            r"'([^']*\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|tif))'",
            r'([a-zA-Z0-9_\-/\\.]+\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|tif))'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                image_path = match.group(1) if match.lastindex >= 1 else match.group(0)
                file_name = os.path.basename(image_path)
                if file_name:
                    images.add(file_name.lower())
        
        return list(images)
    
    def update_source_files_list(self):
        """Met à jour la liste complète des images sources (sans doublons)"""
        all_images = set()
        for source_file in self.imported_source_files:
            for img in source_file['images']:
                all_images.add(img)
        
        self.source_files = list(all_images)
    
    def update_imported_files_list(self):
        """Affiche la liste des fichiers importés"""
        self.imported_files_list.clear()
        for source_file in self.imported_source_files:
            item_text = f"{source_file['fileName']} ({source_file['imageCount']} images)"
            self.imported_files_list.addItem(item_text)
    
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        
        if folder:
            self.current_folder_path = folder
            self.scan_folder(folder)

    def reload_folder_files(self):
        """Rescanne le dossier actuel"""
        if self.current_folder_path and os.path.exists(self.current_folder_path):
            self.scan_folder(self.current_folder_path)
        else:
            QMessageBox.information(self, "Info", "Aucun dossier sélectionné ou dossier introuvable.")

    def scan_folder(self, folder_path):
        """Scanne un dossier pour trouver les images"""
        self.folder_files = []
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif']
        
        # Parcourir récursivement le dossier
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    full_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(full_path)
                        self.folder_files.append({
                            'name': file,
                            'path': full_path,
                            'size': size
                        })
                    except:
                        pass
        
        self.refresh_folder_list()
        self.update_stats()

    def reload_source_files(self):
        """Relit tous les fichiers sources importés"""
        if not self.imported_source_files:
            QMessageBox.information(self, "Info", "Aucun fichier source importé.")
            return

        updated_files = []
        for source_file in self.imported_source_files:
            file_path = source_file.get('filePath')
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        images = self.extract_images_from_text(content)
                        source_file['images'] = images
                        source_file['imageCount'] = len(images)
                        updated_files.append(source_file)
                except Exception as e:
                    print(f"Erreur relecture {file_path}: {e}")
            else:
                 # Garder l'ancien si on ne peut pas relire (ou le supprimer ?)
                 # Ici on garde pour éviter de perdre des données sans avertissement
                 updated_files.append(source_file)
        
        self.imported_source_files = updated_files
        self.update_source_files_list()
        self.update_imported_files_list()
        self.refresh_source_list()
        self.update_stats()
    
    def refresh_source_list(self):
        """Rafraîchit l'affichage de la liste source"""
        # Nettoyer la liste
        while self.source_list_layout.count():
            child = self.source_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Obtenir le filtre actif
        filter_value = "all"
        for button in self.source_filter_group.buttons():
            if button.isChecked():
                filter_value = button.property("filter_value")
                break
        
        search_text = self.source_search.text().lower()
        
        # Filtrer et afficher
        for img_name in self.source_files:
            # Filtre par extension
            if filter_value != "all" and not img_name.endswith(filter_value):
                continue
            
            # Filtre par recherche
            if search_text and search_text not in img_name:
                continue
            
            # Vérifier si dans le dossier
            is_in_folder = any(f['name'].lower() == img_name for f in self.folder_files)
            
            item = QLabel(f"{'🟢' if is_in_folder else '🔵'} {img_name}")
            item.setStyleSheet("""
                QLabel {
                    background-color: #0f3460;
                    border-radius: 6px;
                    padding: 10px;
                    margin: 2px;
                    color: #f1f1f1;
                    border: 1px solid #533483;
                }
                QLabel:hover {
                    background-color: #16213e;
                    border: 1px solid #e94560;
                }
            """)
            self.source_list_layout.addWidget(item)
        
        self.source_list_layout.addStretch()
    
    def refresh_folder_list(self):
        """Rafraîchit l'affichage de la liste dossier"""
        # Nettoyer la liste
        while self.folder_list_layout.count():
            child = self.folder_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Obtenir le filtre actif
        filter_value = "all"
        for button in self.folder_filter_group.buttons():
            if button.isChecked():
                filter_value = button.property("filter_value")
                break
        
        search_text = self.folder_search.text().lower()
        
        # Filtrer et afficher
        for file_info in self.folder_files:
            is_in_source = file_info['name'].lower() in self.source_files
            
            # Filtre par statut
            if filter_value == "green" and not is_in_source:
                continue
            if filter_value == "red" and is_in_source:
                continue
            
            # Filtre par recherche
            if search_text and search_text not in file_info['path'].lower():
                continue
            
            # Créer un bouton cliquable au lieu d'un label
            item = QPushButton(f"{'🟢' if is_in_source else '🔴'} {file_info['name']}")
            item.setStyleSheet("""
                QPushButton {
                    background-color: #0f3460;
                    border-radius: 6px;
                    padding: 10px;
                    margin: 2px;
                    color: #f1f1f1;
                    border: 1px solid #533483;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #16213e;
                    border: 1px solid #e94560;
                    cursor: pointer;
                }
            """)
            # Connecter le clic pour afficher la prévisualisation
            item.clicked.connect(lambda checked, path=file_info['path'], name=file_info['name']: self.show_image_preview(path, name))
            self.folder_list_layout.addWidget(item)
        
        self.folder_list_layout.addStretch()
    
    def update_stats(self):
        """Met à jour les statistiques"""
        matches = [f for f in self.folder_files if f['name'].lower() in self.source_files]
        only_in_folder = [f for f in self.folder_files if f['name'].lower() not in self.source_files]
        
        folder_size = sum(f['size'] for f in self.folder_files)
        match_size = sum(f['size'] for f in matches)
        missing_size = sum(f['size'] for f in only_in_folder)
        
        self.stat_source.setProperty("count", len(self.source_files))
        self.stat_source.setProperty("fileSize", "(Fichier texte)")
        self.update_stat_card(self.stat_source)
        
        self.stat_folder.setProperty("count", len(self.folder_files))
        self.stat_folder.setProperty("fileSize", ImageThumbnail.format_file_size(folder_size))
        self.update_stat_card(self.stat_folder)
        
        self.stat_match.setProperty("count", len(matches))
        self.stat_match.setProperty("fileSize", ImageThumbnail.format_file_size(match_size))
        self.update_stat_card(self.stat_match)
        
        self.stat_missing.setProperty("count", len(only_in_folder))
        self.stat_missing.setProperty("fileSize", ImageThumbnail.format_file_size(missing_size))
        self.update_stat_card(self.stat_missing)
    
    def show_modal(self, modal_type):
        """Affiche une fenêtre modale avec les miniatures"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Images")
        dialog.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout()
        
        # Titre
        if modal_type == 'source':
            title = "📄 Images dans le fichier source"
            files_to_show = [{'name': name, 'path': '', 'size': 0} for name in self.source_files]
        elif modal_type == 'folder':
            title = "📁 Toutes les images du dossier"
            files_to_show = self.folder_files
        elif modal_type == 'match':
            title = "✅ Images présentes dans les deux"
            files_to_show = [f for f in self.folder_files if f['name'].lower() in self.source_files]
        else:  # missing
            title = "❌ Images uniquement dans le dossier"
            files_to_show = [f for f in self.folder_files if f['name'].lower() not in self.source_files]
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e94560; padding: 10px; background-color: #0f3460; border-radius: 8px;")
        layout.addWidget(title_label)
        
        # Boutons d'action pour "missing"
        if modal_type == 'missing' and files_to_show:
            action_layout = QHBoxLayout()
            
            select_all_btn = QPushButton(f"✅ Tout sélectionner ({len(files_to_show)} fichiers)")
            select_all_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #533483, stop:1 #e94560);
                    color: white;
                    padding: 12px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #6a4390, stop:1 #ff5577);
                }
            """)
            
            delete_btn = QPushButton("🗑️ Supprimer les fichiers sélectionnés")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f44336, stop:1 #e91e63);
                    color: white;
                    padding: 12px;
                    font-size: 14px;
                }
            """)
            delete_btn.setEnabled(False)
            
            action_layout.addWidget(select_all_btn)
            action_layout.addWidget(delete_btn)
            layout.addLayout(action_layout)
            
            # Séparateur
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet("background-color: #533483; margin: 10px 0;")
            layout.addWidget(separator)
        
        # Statistiques
        total_size = sum(f['size'] for f in files_to_show)
        stats_label = QLabel(f"📊 {len(files_to_show)} images • {ImageThumbnail.format_file_size(total_size)}")
        stats_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #0f3460; border-radius: 8px; color: #f1f1f1;")
        layout.addWidget(stats_label)
        
        # Grille de miniatures
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        
        thumbnails = []
        row, col = 0, 0
        max_cols = 5
        
        for file_info in files_to_show:
            if modal_type == 'source':
                # Pour les sources, pas d'image réelle
                thumb = QFrame()
                thumb.setFixedSize(150, 180)
                thumb_layout = QVBoxLayout()
                
                icon_label = QLabel("🖼️")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setStyleSheet("font-size: 40px; background-color: #f0f0f0; border-radius: 5px;")
                icon_label.setFixedSize(150, 120)
                thumb_layout.addWidget(icon_label)
                
                name_label = QLabel(file_info['name'])
                name_label.setWordWrap(True)
                name_label.setStyleSheet("font-size: 11px;")
                thumb_layout.addWidget(name_label)
                
                thumb.setLayout(thumb_layout)
                grid_layout.addWidget(thumb, row, col)
            else:
                thumb = ImageThumbnail(
                    file_info['path'],
                    file_info['name'],
                    file_info['size'],
                    show_delete=(modal_type == 'missing')
                )
                thumbnails.append(thumb)
                
                if modal_type == 'missing':
                    thumb.deleteRequested.connect(lambda path, btn=delete_btn, thumbs=thumbnails: 
                                                  self.update_delete_button(btn, thumbs))
                
                grid_layout.addWidget(thumb, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        grid_widget.setLayout(grid_layout)
        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)
        
        
        # Boutons de dialogue
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.setStyleSheet("QPushButton { background-color: #533483; color: white; border-radius: 5px; padding: 5px 15px; }")
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Connecter les boutons d'action
        if modal_type == 'missing' and files_to_show:
            select_all_btn.clicked.connect(lambda: self.toggle_select_all(thumbnails, select_all_btn, delete_btn))
            delete_btn.clicked.connect(lambda: self.delete_selected_files(thumbnails, dialog))
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog { background-color: #1a1a2e; }")
        
        # Exécuter et nettoyer explicitement après
        dialog.exec()
        dialog.deleteLater()
    
    def toggle_select_all(self, thumbnails, select_btn, delete_btn):
        """Sélectionne ou désélectionne tous les fichiers"""
        all_selected = all(thumb.marked_for_deletion for thumb in thumbnails)
        
        for thumb in thumbnails:
            if all_selected and thumb.marked_for_deletion:
                thumb.toggle_delete_mark()
            elif not all_selected and not thumb.marked_for_deletion:
                thumb.toggle_delete_mark()
        
        self.update_delete_button(delete_btn, thumbnails)
        
        # Mettre à jour le texte du bouton
        if all_selected:
            select_btn.setText(f"✅ Tout sélectionner ({len(thumbnails)} fichiers)")
        else:
            select_btn.setText(f"✖️ Tout désélectionner ({len(thumbnails)} fichiers)")
    
    def update_delete_button(self, delete_btn, thumbnails):
        """Met à jour l'état du bouton de suppression"""
        selected_count = sum(1 for thumb in thumbnails if thumb.marked_for_deletion)
        
        if selected_count > 0:
            delete_btn.setEnabled(True)
            delete_btn.setText(f"🗑️ Supprimer les fichiers sélectionnés ({selected_count})")
        else:
            delete_btn.setEnabled(False)
            delete_btn.setText("🗑️ Supprimer les fichiers sélectionnés")
    
    def delete_selected_files(self, thumbnails, dialog):
        """Supprime les fichiers sélectionnés"""
        files_to_delete = [thumb.file_path for thumb in thumbnails if thumb.marked_for_deletion]
        
        if not files_to_delete:
            return
        
        # Confirmation
        reply = QMessageBox.question(
            self,
            "Confirmation de suppression",
            f"⚠️ ATTENTION ⚠️\n\n"
            f"Vous êtes sur le point de supprimer {len(files_to_delete)} fichier(s) de manière PERMANENTE.\n\n"
            f"Cette action est IRRÉVERSIBLE !\n\n"
            f"Voulez-vous vraiment continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            failed_files = []
            
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    # Retirer de la liste
                    self.folder_files = [f for f in self.folder_files if f['path'] != file_path]
                except Exception as e:
                    failed_files.append((file_path, str(e)))
            
            # Rapport
            message = f"✅ {deleted_count} fichier(s) supprimé(s) avec succès."
            if failed_files:
                message += f"\n\n❌ {len(failed_files)} échec(s):\n"
                for file_path, error in failed_files[:5]:  # Limiter à 5 erreurs
                    message += f"\n• {os.path.basename(file_path)}: {error}"
                if len(failed_files) > 5:
                    message += f"\n... et {len(failed_files) - 5} autre(s)"
            
            QMessageBox.information(self, "Résultat de la suppression", message)
            
            # Rafraîchir l'interface
            self.refresh_folder_list()
            self.update_stats()
            
            # Fermer la modal
            dialog.accept()
    
    def show_image_preview(self, image_path, image_name):
        """Affiche une popup avec l'aperçu de l'image et son chemin"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Aperçu - {image_name}")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # Titre
        title_label = QLabel(image_name)
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #e94560;
            padding: 10px;
            background-color: #0f3460;
            border-radius: 8px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Chemin complet
        path_label = QLabel(f"📂 Chemin: {image_path}")
        path_label.setStyleSheet("""
            font-size: 12px;
            color: #f1f1f1;
            padding: 8px;
            background-color: #1a1a2e;
            border-radius: 5px;
            border: 1px solid #533483;
        """)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        
        # Image
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("""
            background-color: #0f3460;
            border: 2px solid #533483;
            border-radius: 10px;
            padding: 10px;
        """)
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Redimensionner pour s'adapter à la fenêtre
                scaled_pixmap = pixmap.scaled(750, 450, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
            else:
                image_label.setText("❌ Impossible de charger l'image")
                image_label.setStyleSheet(image_label.styleSheet() + "font-size: 16px; color: #e94560;")
        else:
            image_label.setText("❌ Fichier introuvable")
            image_label.setStyleSheet(image_label.styleSheet() + "font-size: 16px; color: #e94560;")
        
        layout.addWidget(image_label)
        
        # Bouton fermer
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #533483, stop:1 #e94560);
                color: white;
                padding: 10px;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6a4390, stop:1 #ff5577);
            }
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #16213e;
            }
        """)
        dialog.exec()


def main():
    # Gestionnaire d'erreurs global
    def handle_exception(exc_type, exc_value, exc_traceback):
        import traceback
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            # Tenter d'afficher une boîte de dialogue
            from PyQt6.QtWidgets import QMessageBox
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "Erreur Fatale", f"Une erreur est survenue au démarrage:\n\n{error_msg}")
        except:
            # Fallback si PyQt plante aussi
            with open("error_log.txt", "w") as f:
                f.write(error_msg)
            print("ERREUR FATALE:", error_msg)
        sys.exit(1)

    sys.excepthook = handle_exception

    # Fix taskbar icon on Windows
    myappid = 'olivier.texturecleaner.tool.1.0' 
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Style moderne
        
        window = TextureCleaner()
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        handle_exception(type(e), e, e.__traceback__)



if __name__ == '__main__':
    main()
