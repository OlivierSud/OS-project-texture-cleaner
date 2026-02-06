"""
2D Texture Listing - Application Windows
Comparateur d'images entre fichiers source et dossier avec suppression directe
"""

import sys
import os
import re
import json
import shutil
import version
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QScrollArea, QGridLayout, QFrame,
    QSplitter, QGroupBox, QButtonGroup, QRadioButton, QTabWidget,
    QComboBox, QSpinBox, QDoubleSpinBox, QProgressBar, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QCheckBox,
    QDialog, QTextEdit, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRunnable, QThreadPool, QObject, QRegularExpression
from PyQt6.QtGui import (
    QPixmap, QIcon, QFont, QImage, QImageReader, QTextCharFormat, 
    QColor, QTextCursor, QSyntaxHighlighter, QTextDocument
)
import ctypes

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class WorkerSignals(QObject):
    """Signaux pour le worker de chargement d'image"""
    finished = pyqtSignal(QImage)
    error = pyqtSignal()

class ThumbnailLoader(QRunnable):
    """Worker pour charger les images en arrière-plan"""
    def __init__(self, file_path, width, height):
        super().__init__()
        self.file_path = file_path
        self.width = width
        self.height = height
        self.signals = WorkerSignals()

    def run(self):
        try:
            if os.path.exists(self.file_path):
                # Chargement de l'image (QImage est thread-safe, QPixmap non)
                image = QImage(self.file_path)
                if not image.isNull():
                    # Redimensionnement haute qualité
                    scaled_image = image.scaled(
                        self.width, self.height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.signals.finished.emit(scaled_image)
                else:
                    self.signals.error.emit()
            else:
                self.signals.error.emit()
        except Exception:
            self.signals.error.emit()


class ImageThumbnail(QFrame):
    """Widget pour afficher une miniature d'image avec bouton de suppression"""
    deleteRequested = pyqtSignal(str)
    
    def __init__(self, file_path, file_name, file_size, pool=None, cache=None, show_delete=False):
        super().__init__()
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.marked_for_deletion = False
        self.pool = pool
        self.cache = cache
        
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
        
        # Vérifier le cache
        if self.cache and self.file_path in self.cache:
            self.image_label.setPixmap(QPixmap.fromImage(self.cache[self.file_path]))
        elif self.pool:
            # Placeholder initial
            self.loading_label = QLabel("Chargement...")
            self.loading_label.setStyleSheet("color: #aaa; font-size: 10px;")
            self.image_label.setLayout(QVBoxLayout())
            self.image_label.layout().addWidget(self.loading_label)
            self.image_label.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.load_image_async()
        else:
             # Fallback synchrone
             self.load_image_sync()
        
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
            self.delete_btn = QPushButton("🟦 Non Marqué")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #65bdcf;
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

    def load_image_async(self):
        """Lance le chargement asynchrone"""
        loader = ThumbnailLoader(self.file_path, 150, 120)
        loader.signals.finished.connect(self.on_image_loaded)
        loader.signals.error.connect(self.on_image_error)
        self.pool.start(loader)

    def on_image_loaded(self, image):
        """Callback quand l'image est chargée"""
        # Mettre en cache
        if self.cache is not None:
            self.cache[self.file_path] = image

        # Supprimer le placeholder
        if self.image_label.layout():
             # Nettoyage brutal mais efficace pour ce cas simple
             QWidget().setLayout(self.image_label.layout())
        
        self.image_label.setPixmap(QPixmap.fromImage(image))
    
    def on_image_error(self):
        """Callback en cas d'erreur de chargement"""
        if self.image_label.layout():
             QWidget().setLayout(self.image_label.layout())
        
        self.image_label.setText("🖼️")
        self.image_label.setStyleSheet("background-color: #f0f0f0; font-size: 40px;")

    def load_image_sync(self):
        """Chargement synchrone (ancien comportement)"""
        if os.path.exists(self.file_path):
            pixmap = QPixmap(self.file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(150, 120, Qt.AspectRatioMode.KeepAspectRatio, 
                                              Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
                # Enlever le placeholder
                if self.image_label.layout():
                     QWidget().setLayout(self.image_label.layout())
            else:
                self.on_image_error()
        else:
             self.on_image_error()
    
    def toggle_delete_mark(self):
        self.marked_for_deletion = not self.marked_for_deletion
        if self.marked_for_deletion:
            self.delete_btn.setText("✅ Marqué")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #db3d21;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 5px;
                    font-size: 11px;
                }
            """)
        else:
            self.delete_btn.setText("🟦 Non Marqué")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #65bdcf;
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


class SegmentedToggle(QFrame):
    toggled = pyqtSignal(bool) # True = Left, False = Right

    def __init__(self, left_text, right_text, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 40)
        self.setStyleSheet("background-color: transparent;")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        self.btn_left = QPushButton(left_text)
        self.btn_left.setCheckable(True)
        self.btn_left.setChecked(True)
        self.btn_left.clicked.connect(self.on_left_clicked)
        self.btn_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_left.setSizePolicy(self.btn_left.sizePolicy().horizontalPolicy(), self.btn_left.sizePolicy().verticalPolicy())
        
        self.btn_right = QPushButton(right_text)
        self.btn_right.setCheckable(True)
        self.btn_right.setChecked(False)
        self.btn_right.clicked.connect(self.on_right_clicked)
        self.btn_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_right.setSizePolicy(self.btn_right.sizePolicy().horizontalPolicy(), self.btn_right.sizePolicy().verticalPolicy())
        
        layout.addWidget(self.btn_left)
        layout.addWidget(self.btn_right)
        
        self.update_style()

    def on_left_clicked(self):
        if not self.btn_left.isChecked():
            self.btn_left.setChecked(True)
        self.btn_right.setChecked(False)
        self.update_style()
        self.toggled.emit(True)

    def on_right_clicked(self):
        if not self.btn_right.isChecked():
            self.btn_right.setChecked(True)
        self.btn_left.setChecked(False)
        self.update_style()
        self.toggled.emit(False)
        
    def is_left_active(self):
        return self.btn_left.isChecked()

    def update_style(self):
        # Style inspiré de l'image (Green / Dark)
        active_style = """
            background-color: #00d9ff; 
            color: #1a1a2e; 
            font-weight: bold;
            border: 1px solid #00d9ff;
        """
        inactive_style = """
            background-color: #333333; 
            color: #888888; 
            font-weight: normal;
            border: 1px solid #555555;
        """
        
        # Left button styling
        base_left = """
            QPushButton {
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
                font-size: 14px;
                padding: 5px;
        """
        if self.btn_left.isChecked():
            self.btn_left.setStyleSheet(base_left + active_style + "}")
        else:
            self.btn_left.setStyleSheet(base_left + inactive_style + "}")
            
        # Right button styling
        base_right = """
            QPushButton {
                border-top-right-radius: 20px;
                border-bottom-right-radius: 20px;
                font-size: 14px;
                padding: 5px;
        """
        if self.btn_right.isChecked():
            dim_active_style = """
                background-color: #ff9800; 
                color: #1a1a2e; 
                font-weight: bold;
                border: 1px solid #ff9800;
            """
            self.btn_right.setStyleSheet(base_right + dim_active_style + "}")
        else:
            self.btn_right.setStyleSheet(base_right + inactive_style + "}")



class AdvancedUsageDialog(QDialog):
    def __init__(self, usage_data, image_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Usage de : {image_name}")
        self.setMinimumSize(900, 600)
        self.usage_data = usage_data
        self.image_name = image_name
        self.file_paths = list(usage_data.keys())
        self.current_match_cursors = []
        self.current_match_index = -1
        
        self.init_ui()
        
        if self.file_paths:
            self.load_file(0)
            
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # --- Toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        
        # Sélecteur de fichier
        toolbar.addWidget(QLabel("📁 Fichier :"))
        self.file_combo = QComboBox()
        for path in self.file_paths:
            self.file_combo.addItem(os.path.basename(path), path)
        self.file_combo.currentIndexChanged.connect(self.load_file)
        self.file_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a1a2e;
                color: #f1f1f1;
                border: 1px solid #533483;
                padding: 5px;
                min-width: 200px;
            }
        """)
        toolbar.addWidget(self.file_combo)
        
        toolbar.addSpacing(20)
        
        # Navigation occurrences
        self.prev_btn = QPushButton("⬆️ Précédent")
        self.prev_btn.clicked.connect(self.prev_match)
        self.next_btn = QPushButton("⬇️ Suivant")
        self.next_btn.clicked.connect(self.next_match)
        self.match_label = QLabel("Occurrence : 0 / 0")
        
        btn_style = """
            QPushButton {
                background-color: #533483;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #6a42a8; }
        """
        self.prev_btn.setStyleSheet(btn_style)
        self.next_btn.setStyleSheet(btn_style)
        self.match_label.setStyleSheet("color: #e94560; font-weight: bold;")
        
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.match_label)
        toolbar.addWidget(self.next_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # --- Text Editor ---
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1a1a2e;
                color: #f1f1f1;
                border: 1px solid #533483;
                border-radius: 5px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
                padding-left: 5px;
            }
        """)
        layout.addWidget(self.text_edit)
        
        # Close button
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(btn_style)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def load_file(self, index):
        if index < 0 or index >= len(self.file_paths):
            return
            
        file_path = self.file_paths[index]
        self.current_match_cursors = []
        self.current_match_index = -1
        
        # Charger le contenu
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remplissage
            self.text_edit.setPlainText(content)
            
            # Recherche et Highlight
            self.highlight_matches()
            
            # Aller au premier match
            if self.current_match_cursors:
                self.next_match()
            else:
                self.match_label.setText("Occurrence : 0 / 0")

        except Exception as e:
            self.text_edit.setPlainText(f"Erreur de lecture du fichier : {e}")

    def highlight_matches(self):
        """Surligne toutes les occurrences et stocke leurs positions"""
        doc = self.text_edit.document()
        cursor = QTextCursor(doc)
        
        # Reset format
        cursor.select(QTextCursor.SelectionType.Document)
        format_normal = QTextCharFormat()
        format_normal.setBackground(QColor("#1a1a2e")) # Fond normal
        cursor.setCharFormat(format_normal)
        cursor.clearSelection() # Clear selection after applying format
        
        # Find format
        format_highlight = QTextCharFormat()
        format_highlight.setBackground(QColor("#533483")) # Fond violet sombre pour tous les matches
        format_highlight.setForeground(Qt.GlobalColor.white)
        format_highlight.setFontWeight(QFont.Weight.Bold)
        
        # Setup Regex
        # Escape the search term to treat it as literal string but allow case insensitive flag
        regex = QRegularExpression(QRegularExpression.escape(self.image_name))
        regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
        
        # Search loop
        cursor = QTextCursor(doc)
        while True:
            # find() with QRegularExpression returns a cursor with selection covering the match
            cursor = doc.find(regex, cursor)
            
            if cursor.isNull():
                break
                
            cursor.mergeCharFormat(format_highlight)
            self.current_match_cursors.append(QTextCursor(cursor)) # Store copy
        
        # Update UI count
        self.match_label.setText(f"Occurrence : 0 / {len(self.current_match_cursors)}")

    def next_match(self):
        if not self.current_match_cursors:
            return
            
        self.current_match_index += 1
        if self.current_match_index >= len(self.current_match_cursors):
            self.current_match_index = 0
        
        self.focus_match(self.current_match_index)

    def prev_match(self):
        if not self.current_match_cursors:
            return
            
        self.current_match_index -= 1
        if self.current_match_index < 0:
            self.current_match_index = len(self.current_match_cursors) - 1
            
        self.focus_match(self.current_match_index)
        
    def focus_match(self, index):
        # Reset previous active if any (complex to track, so let's just re-highlight all then highlight active)
        # Optimization: keep track of last active index
        
        # For simplicity: Re-highlight all simply ensures base color, then apply active color to current.
        # But `highlight_matches` rebuilds list. We don't want that.
        # Just iterating colors is fine.
        
        format_highlight = QTextCharFormat()
        format_highlight.setBackground(QColor("#533483"))
        format_highlight.setForeground(Qt.GlobalColor.white)
        format_highlight.setFontWeight(QFont.Weight.Bold)
        
        format_active = QTextCharFormat()
        format_active.setBackground(QColor("#e94560")) 
        format_active.setForeground(Qt.GlobalColor.white)
        format_active.setFontWeight(QFont.Weight.Bold)

        # Reset all to normal highlight
        for cur in self.current_match_cursors:
             cur.setCharFormat(format_highlight)
             
        # Set active
        cursor = self.current_match_cursors[index]
        cursor.setCharFormat(format_active)

        self.text_edit.setTextCursor(cursor)
        self.text_edit.centerCursor()
        
        self.match_label.setText(f"Occurrence : {index + 1} / {len(self.current_match_cursors)}")


class TextureCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2D Texture Cleaner")
        self.setGeometry(100, 100, 1600, 900)
        
        # État de l'application
        self.source_files = []  # Liste des noms de fichiers trouvés dans les sources
        self.imported_source_files = []  # Liste des fichiers texte importés avec chemins
        self.folder_files = []  # Liste des fichiers du dossier avec chemins complets
        self.current_folder_path = ""  # Chemin du dossier actuel
        self.resize_folder_path = "" # Chemin du dossier pour l'onglet Resize
        
        # ThreadPool pour le chargement d'images
        self.thread_pool = QThreadPool()
        self.thumbnail_cache = {}  # Cache RAM pour les miniatures
        
        self.setWindowIcon(QIcon(resource_path('icone_final.ico')))
        self.init_ui()
    
    def init_ui(self):
        # Création des onglets
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Build number
        build_label = QLabel(f"Build: {version.BUILD_NUMBER}")
        build_label.setStyleSheet("color: #666; font-size: 10px; padding-right: 10px;")
        self.tabs.setCornerWidget(build_label, Qt.Corner.TopRightCorner)
        
        # --- Onglet 1: Nettoyage des fichiers ---
        self.cleaner_tab = QWidget()
        self.tabs.addTab(self.cleaner_tab, "Nettoyage des fichiers")
        
        # Layout pour l'onglet de nettoyage (ancien main_layout)
        cleaner_layout = QVBoxLayout()
        self.cleaner_tab.setLayout(cleaner_layout)
        
        # Header
        header_container = QWidget()
        header_container.setMaximumHeight(50)  # Contrainte de hauteur
        header_layout = QHBoxLayout() # Layout horizontal
        header_layout.setContentsMargins(10, 5, 10, 5) # Marges réduites
        header_layout.setSpacing(10)
        header_container.setLayout(header_layout)
        header_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px; /* Rayon réduit */
            }
            QLabel {
                background: transparent;
                color: white;
            }
        """)
        
        header = QLabel("🖼️ 2D Texture Listing")
        header.setStyleSheet("font-size: 16px; font-weight: bold;") # Police réduite
        header_layout.addWidget(header)
        
        subtitle = QLabel("- 1️⃣. Liste les image présente dans les sources texte - 2️⃣. Liste les image présente dans le dossier - 3️⃣. Supprime les images non référencées")
        subtitle.setStyleSheet("font-size: 13px; color: #e0e0e0;")
        header_layout.addWidget(subtitle)
        
        header_layout.addStretch() # Pousser le reste à gauche

        
        cleaner_layout.addWidget(header_container)
        
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
        cleaner_layout.addWidget(splitter)
        
        # --- Onglet 2: Resize ---
        self.resize_tab = QWidget()
        self.tabs.addTab(self.resize_tab, "Resize")
        
        # Layout principal vertical pour l'onglet
        resize_main_layout = QVBoxLayout()
        self.resize_tab.setLayout(resize_main_layout)
        
        # --- Zone Haute : Colonnes et Options ---
        top_area_layout = QHBoxLayout()
        resize_main_layout.addLayout(top_area_layout, 1) # prend tout l'espace dispo
        
        # --- Colonne Gauche: Tableau des textures ---
        left_col = QWidget()
        left_layout = QVBoxLayout()
        left_col.setLayout(left_layout)
        
        # Header Colonne Gauche
        left_header = QLabel("🖼️ Textures du projet")
        left_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #e94560;")
        left_layout.addWidget(left_header)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.resize_folder_btn = QPushButton("📂 Sélectionner dossier cible")
        self.resize_folder_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                padding: 8px;
            }
        """)
        self.resize_folder_btn.clicked.connect(self.select_resize_folder)
        folder_layout.addWidget(self.resize_folder_btn)
        
        refresh_resize_btn = QPushButton("🔄")
        refresh_resize_btn.setFixedSize(35, 35)
        refresh_resize_btn.setStyleSheet("background-color: #00d9ff; color: white; border-radius: 5px;")
        refresh_resize_btn.clicked.connect(self.refresh_resize_list)
        folder_layout.addWidget(refresh_resize_btn)
        
        left_layout.addLayout(folder_layout)
        
        # Tableau des fichiers (Remplace QListWidget)
        self.resize_table = QTableWidget()

        # Recherche et Filtres
        search_filter_layout = QHBoxLayout()
        
        self.resize_search = QLineEdit()
        self.resize_search.setPlaceholderText("🔍 Rechercher une texture...")
        self.resize_search.textChanged.connect(self.filter_resize_table)
        search_filter_layout.addWidget(self.resize_search, 2)
        
        self.resize_filter_group = QButtonGroup()
        filters = [("Tous", "all"), ("🟢 Associé", "prepared"), ("⚪ Invariable", "remaining")]
        for i, (label, value) in enumerate(filters):
            radio = QRadioButton(label)
            radio.setProperty("filter_value", value)
            radio.toggled.connect(self.filter_resize_table)
            self.resize_filter_group.addButton(radio, i)
            search_filter_layout.addWidget(radio)
            if value == "all":
                radio.setChecked(True)
        
        left_layout.addLayout(search_filter_layout)
        
        # Déjà initialisé plus haut
        self.resize_table.setColumnCount(3)
        self.resize_table.setHorizontalHeaderLabels(["Fichier", "Dimensions (Av. > Ap.)", "Poids (Av. > Ap.)"])
        
        # Config tableau style
        self.resize_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a2e;
                color: #f1f1f1;
                gridline-color: #533483;
                border: 1px solid #533483;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #0f3460;
                color: white;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e94560;
                color: white;
            }
        """)
        self.resize_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.resize_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.resize_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.resize_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.resize_table.verticalHeader().setVisible(False)
        self.resize_table.cellDoubleClicked.connect(self.open_image_popup_from_table) # Popup double clic
        self.resize_table.itemSelectionChanged.connect(self.reset_resize_options_ui) # Reset UI on selection change
        
        left_layout.addWidget(self.resize_table)
        
        top_area_layout.addWidget(left_col, 2) # Plus large que les options
        
        # --- Colonne Droite: Options ---
        right_col = QGroupBox("🛠️ Options")
        right_layout = QVBoxLayout()
        right_col.setLayout(right_layout)
        
        # Mode de redimensionnement (Nouveau Switch Custom)
        switch_layout = QHBoxLayout()
        switch_layout.addStretch()
        
        # Instantiation du Toggle Switch
        self.mode_switch = SegmentedToggle("🔒 Ratio Fixe", "🔓 Dimensions", self)
        
        switch_layout.addWidget(self.mode_switch)
        switch_layout.addStretch()
        
        right_layout.addLayout(switch_layout)
        right_layout.addSpacing(10)
        
        # Options Ratio
        self.ratio_options_frame = QFrame()
        ratio_layout = QVBoxLayout()
        self.ratio_options_frame.setLayout(ratio_layout)
        
        self.ratio_type_combo = QComboBox()
        self.ratio_type_combo.addItems(["Pourcentage de réduction", "Largeur fixe (Hauteur auto)", "Hauteur fixe (Largeur auto)"])
        ratio_layout.addWidget(self.ratio_type_combo)
        
        self.ratio_value_spin = QSpinBox()
        self.ratio_value_spin.setRange(1, 10000)
        self.ratio_value_spin.setValue(50) # Defaut 50%
        self.ratio_value_spin.setSuffix(" %")
        ratio_layout.addWidget(self.ratio_value_spin)
        
        right_layout.addWidget(self.ratio_options_frame)
        
        # Options Dimensions Fixes
        self.fixed_options_frame = QFrame()
        self.fixed_options_frame.setEnabled(False) # Désactivé par défaut
        self.fixed_options_frame.hide() # Caché par défaut
        fixed_layout = QVBoxLayout()
        self.fixed_options_frame.setLayout(fixed_layout)
        
        fixed_form = QHBoxLayout()
        fixed_form.addWidget(QLabel("L:"))
        self.fixed_width_spin = QSpinBox()
        self.fixed_width_spin.setRange(1, 10000)
        self.fixed_width_spin.setValue(1024)
        self.fixed_width_spin.setSuffix(" px")
        fixed_form.addWidget(self.fixed_width_spin)
        
        fixed_form.addWidget(QLabel("H:"))
        self.fixed_height_spin = QSpinBox()
        self.fixed_height_spin.setRange(1, 10000)
        self.fixed_height_spin.setValue(1024)
        self.fixed_height_spin.setSuffix(" px")
        fixed_form.addWidget(self.fixed_height_spin)
        
        fixed_layout.addLayout(fixed_form)
        right_layout.addWidget(self.fixed_options_frame)
        
        # Bouton Appliquer à la sélection
        self.apply_btn = QPushButton("Associer ces réglages à la sélection")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #533483;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #6a42a8; }
        """)
        self.apply_btn.clicked.connect(self.apply_settings_to_selection)
        right_layout.addWidget(self.apply_btn)
        
        right_layout.addStretch()
        top_area_layout.addWidget(right_col, 1) # Plus petit

        # --- Zone Basse: Stats et Actions ---
        bottom_container = QFrame()
        bottom_container.setStyleSheet("background-color: #0f3460; border-top: 2px solid #533483; border-radius: 0px 0px 8px 8px;")
        bottom_layout = QVBoxLayout()
        bottom_container.setLayout(bottom_layout)

        # Stats Globales
        self.global_stats_label = QLabel("Poids Total : 0 MB -> 0 MB | Gain : 0 MB (0%)")
        self.global_stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f1f1f1; padding: 5px;")
        bottom_layout.addWidget(self.global_stats_label)

        # Bouton d'exécution
        self.execute_btn = QPushButton("🚀 Lancer l'optimisation")
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00b09b, stop:1 #96c93d);
                color: white;
                font-weight: bold;
                padding: 15px;
                font-size: 18px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00c9b1, stop:1 #a8df44);
            }
        """)
        self.execute_btn.clicked.connect(self.execute_resize)
        bottom_layout.addWidget(self.execute_btn)

        resize_main_layout.addWidget(bottom_container)

        # Connexions UI
        self.mode_switch.toggled.connect(self.toggle_resize_ui)
        self.ratio_type_combo.currentIndexChanged.connect(self.update_ratio_ui)
        
        # Disconnect Preview from direct UI change (only explicit Apply now for individual Update)
        # But we might keep preview update on Apply ?
        # Actually logic is: UI -> Apply -> Update Stored Data -> Update Preview.
        # So UI changes shouldn't trigger global preview update if preview depends on stored data.
        # However, it might be nice to preview "what if" ? 
        # User said: "Settings reset when selection changes". "Only selected files taken charge by right column".
        # Let's remove direct connection to update_resize_preview from UI widgets.
        
        # Tab Change Listener
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- Onglet 3: Compression ---
        self.compression_tab = QWidget()
        self.tabs.addTab(self.compression_tab, "Compression")
        compression_layout = QVBoxLayout()
        self.compression_tab.setLayout(compression_layout)
        label_compression = QLabel("Fonctionnalité Compression à venir")
        label_compression.setAlignment(Qt.AlignmentFlag.AlignCenter)
        compression_layout.addWidget(label_compression)
        
        # Style global - Mode sombre
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
            }
            QTabWidget::pane {
                border: 1px solid #533483;
                background-color: #1a1a2e;
            }
            QTabBar::tab {
                background: #0f3460;
                color: #f1f1f1;
                padding: 10px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #16213e;
                border-bottom: 2px solid #e94560;
                color: #e94560;
                font-weight: bold;
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
        group = QGroupBox("📄 Source texte")
        layout = QVBoxLayout()
        
        # Layout boutons
        btn_layout = QHBoxLayout()
        
        # Bouton de sélection
        select_btn = QPushButton("📁 Dossier de textures")
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
        group = QGroupBox("📁  Dossier de textures")
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
        
        filters = [("Tous", "all"), ("✅ Utilisées", "green"), ("❌ Non utilisées", "red")]
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
        group = QGroupBox("📊 Récapitulatif")
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
            
            # Créer un bouton cliquable pour afficher l'usage
            item = QPushButton(f"{'🟢' if is_in_folder else '🔵'} {img_name}")
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
            item.clicked.connect(lambda checked, name=img_name: self.show_usage_popup(name))
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
        
        # Lancer le préchargement des miniatures
        self.preload_thumbnails()
    
    def preload_thumbnails(self):
        """Précharge les miniatures en arrière-plan"""
        for file_info in self.folder_files:
            path = file_info['path']
            if path not in self.thumbnail_cache:
                loader = ThumbnailLoader(path, 150, 120)
                # On utilise une lambda pour capturer le chemin
                loader.signals.finished.connect(lambda img, p=path: self.on_thumbnail_preloaded(p, img))
                self.thread_pool.start(loader)
    
    def on_thumbnail_preloaded(self, path, image):
        """Callback de préchargement"""
        self.thumbnail_cache[path] = image

    def find_image_usage(self, image_name):
        """Trouve les fichiers et lignes où l'image est utilisée"""
        usage_data = {}
        
        for source_file in self.imported_source_files:
            file_path = source_file.get('filePath')
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        file_matches = []
                        for i, line in enumerate(lines):
                            if image_name.lower() in line.lower():
                                file_matches.append((i + 1, line.strip()))
                        
                        if file_matches:
                            usage_data[file_path] = file_matches
                except Exception as e:
                    print(f"Erreur lecture {file_path}: {e}")
        
        return usage_data

    def show_usage_popup(self, image_name):
        """Affiche une popup avec les endroits où l'image est utilisée"""
        # Récupère juste les chemins de fichiers concernés
        # Mais AdvancedUsageDialog attend un dict.
        # find_image_usage retourne déjà un dict {file: [matches]}.
        # On va le réutiliser même si on affiche tout le fichier.
        # Les "matches" dans le dict ne seront pas forcément utilisés pour le highlight (on refait le find live),
        # mais ça permet de filtrer quels fichiers contiennent l'image.
        
        usage_data = self.find_image_usage(image_name)
        
        if not usage_data:
            QMessageBox.information(self, "Info", f"Aucune utilisation trouvée pour {image_name}")
            return

        dialog = AdvancedUsageDialog(usage_data, image_name, self)
        dialog.exec()

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
            
            self.move_btn = QPushButton("📂 Déplacer la sélection")
            self.move_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #ff9800, stop:1 #f57c00);
                    color: white;
                    padding: 12px;
                    font-size: 14px;
                }
                 QPushButton:disabled {
                    background: #555;
                    color: #aaa;
                }
            """)
            self.move_btn.setEnabled(False)

            self.delete_btn = QPushButton("🗑️ Supprimer la sélection")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f44336, stop:1 #e91e63);
                    color: white;
                    padding: 12px;
                    font-size: 14px;
                }
                 QPushButton:disabled {
                    background: #555;
                    color: #aaa;
                }
            """)
            self.delete_btn.setEnabled(False)
            
            action_layout.addWidget(select_all_btn)
            action_layout.addWidget(self.move_btn)
            action_layout.addWidget(self.delete_btn)
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
                    pool=self.thread_pool,
                    cache=self.thumbnail_cache,
                    show_delete=(modal_type == 'missing')
                )
                thumbnails.append(thumb)
                
                if modal_type == 'missing':
                    thumb.deleteRequested.connect(lambda path, thumbs=thumbnails: 
                                                  self.update_action_buttons(thumbs))
                
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
            select_all_btn.clicked.connect(lambda: self.toggle_select_all(thumbnails, select_all_btn))
            self.delete_btn.clicked.connect(lambda: self.delete_selected_files(thumbnails, dialog))
            self.move_btn.clicked.connect(lambda: self.move_selected_files(thumbnails, dialog))
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog { background-color: #1a1a2e; }")
        
        # Exécuter et nettoyer explicitement après
        dialog.exec()
        dialog.deleteLater()
    
    def toggle_select_all(self, thumbnails, select_btn):
        """Sélectionne ou désélectionne tous les fichiers"""
        all_selected = all(thumb.marked_for_deletion for thumb in thumbnails)
        
        for thumb in thumbnails:
            if all_selected and thumb.marked_for_deletion:
                thumb.toggle_delete_mark()
            elif not all_selected and not thumb.marked_for_deletion:
                thumb.toggle_delete_mark()
        
        self.update_action_buttons(thumbnails)
        
        # Mettre à jour le texte du bouton
        if all_selected:
            select_btn.setText(f"✅ Tout sélectionner ({len(thumbnails)} fichiers)")
        else:
            select_btn.setText(f"✖️ Tout désélectionner ({len(thumbnails)} fichiers)")
    
    def update_action_buttons(self, thumbnails):
        """Met à jour l'état des boutons d'action"""
        selected_count = sum(1 for thumb in thumbnails if thumb.marked_for_deletion)
        
        if selected_count > 0:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setText(f"🗑️ Supprimer la sélection ({selected_count})")
            
            self.move_btn.setEnabled(True)
            self.move_btn.setText(f"📂 Déplacer la sélection ({selected_count})")
        else:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setText("🗑️ Supprimer la sélection")
            
            self.move_btn.setEnabled(False)
            self.move_btn.setText("📂 Déplacer la sélection")

    def move_selected_files(self, thumbnails, dialog):
        """Déplace les fichiers sélectionnés vers un autre dossier"""
        files_to_move = [thumb.file_path for thumb in thumbnails if thumb.marked_for_deletion]
        
        if not files_to_move:
            return
            
        # Demander le dossier de destination
        dest_folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination")
        if not dest_folder:
            return
            
        moved_count = 0
        failed_files = []
        
        for file_path in files_to_move:
            try:
                # Calculer le nouveau chemin
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(dest_folder, file_name)
                
                # Déplacement
                shutil.move(file_path, dest_path)
                
                moved_count += 1
                # Retirer de la liste
                self.folder_files = [f for f in self.folder_files if f['path'] != file_path]
            except Exception as e:
                failed_files.append((file_path, str(e)))
                
        # Rapport
        message = f"✅ {moved_count} fichier(s) déplacé(s) avec succès."
        if failed_files:
            message += f"\n\n❌ {len(failed_files)} échec(s):\n"
            for file_path, error in failed_files[:5]:
                message += f"\n• {os.path.basename(file_path)}: {error}"
            if len(failed_files) > 5:
                message += f"\n... et {len(failed_files) - 5} autre(s)"
        
        QMessageBox.information(self, "Résultat du déplacement", message)
        
        # Rafraîchir l'interface
        self.refresh_folder_list()
        self.update_stats()
        
        # Fermer la modal car l'état a changé
        dialog.accept()
    
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

    # --- Gestion Onglet Resize ---
    
    def on_tab_changed(self, index):
        """Gestion du changement d'onglet"""
        if index == 1: # Onglet Resize
            # Si aucun dossier spécifique n'est défini pour resize, 
            # on prend celui du cleaner si disponible
            if not self.resize_folder_path and self.current_folder_path:
                self.resize_folder_path = self.current_folder_path
                self.populate_resize_list()
            elif self.resize_folder_path:
                # Si déjà un dossier, on rafraichit au cas où
                if self.resize_table.rowCount() == 0:
                    self.populate_resize_list()
            
    def select_resize_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner dossier pour redimensionnement")
        if folder:
            self.resize_folder_path = folder
            self.populate_resize_list()
            
    def refresh_resize_list(self):
        self.populate_resize_list()
            
    def populate_resize_list(self):
        """Remplit la liste des fichiers pour l'onglet Resize"""
        self.resize_table.setRowCount(0)
        
        if not self.resize_folder_path or not os.path.exists(self.resize_folder_path):
             return
             
        # Récupérer les images
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif']
        files_found = []
        
        for root, dirs, files in os.walk(self.resize_folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    full_path = os.path.join(root, file)
                    files_found.append(full_path)
        
        self.resize_table.setRowCount(len(files_found))
        
        # Afficher dans la liste avec détails
        for i, path in enumerate(files_found):
            try:
                # Lire dimensions sans charger toute l'image
                reader = QImageReader(path)
                size = reader.size()
                file_size = os.path.getsize(path)
                
                # Colonne 1: Nom
                item_name = QTableWidgetItem(os.path.basename(path))
                item_name.setData(Qt.ItemDataRole.UserRole, path)
                item_name.setData(Qt.ItemDataRole.UserRole + 1, size.width()) # Storing original width
                item_name.setData(Qt.ItemDataRole.UserRole + 2, size.height()) # Storing original height
                item_name.setData(Qt.ItemDataRole.UserRole + 3, file_size) # Storing original size
                # Pas de réglages par défaut (UserRole + 10 restera None)
                self.resize_table.setItem(i, 0, item_name)
                
                # Colonne 2: Dimensions init
                item_dim = QTableWidgetItem(f"{size.width()}x{size.height()} px")
                self.resize_table.setItem(i, 1, item_dim)
                
                # Colonne 3: Poids init
                item_size = QTableWidgetItem(ImageThumbnail.format_file_size(file_size))
                self.resize_table.setItem(i, 2, item_size)
                
            except Exception as e:
                print(f"Erreur lecture {path}: {e}")
                
        # Lancer la prévisualisation initiale
        self.update_resize_preview()
        self.filter_resize_table()

    def filter_resize_table(self):
        """Filtre les lignes du tableau selon la recherche et le statut"""
        if not hasattr(self, 'resize_table'):
            return
            
        search_text = self.resize_search.text().lower()
        
        active_filter = "all"
        for btn in self.resize_filter_group.buttons():
            if btn.isChecked():
                active_filter = btn.property("filter_value")
                break
        
        for i in range(self.resize_table.rowCount()):
            item_name = self.resize_table.item(i, 0)
            if not item_name: continue
            
            name = item_name.text().lower()
            is_associated = item_name.data(Qt.ItemDataRole.UserRole + 10) is not None
            
            # Match recherche
            match_search = not search_text or search_text in name
            
            # Match filtre
            match_filter = True
            if active_filter == "prepared":
                match_filter = is_associated
            elif active_filter == "remaining":
                match_filter = not is_associated
                
            self.resize_table.setRowHidden(i, not (match_search and match_filter))

    def open_image_popup_from_table(self, row, col):
        """Ouvre un popup avec l'image au clic"""
        # Récupère le path depuis la première colonne
        item = self.resize_table.item(row, 0)
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        
        self.show_image_preview(path, name)

    def toggle_resize_ui(self, is_ratio):
        """Active/Désactive les sections selon le mode Switch"""
        # is_ratio est passé par le signal toggled (True=Left/Ratio)
        
        self.ratio_options_frame.setEnabled(is_ratio)
        self.ratio_options_frame.setVisible(is_ratio)
        
        self.fixed_options_frame.setEnabled(not is_ratio)
        self.fixed_options_frame.setVisible(not is_ratio)
        
        # Note: Plus besoin de gérer les labels manuellement, le widget le fait
        
        self.update_resize_preview()

    def update_ratio_ui(self):
        """Met à jour l'interface des options de ratio"""
        idx = self.ratio_type_combo.currentIndex()
        if idx == 0: # Pourcentage
            self.ratio_value_spin.setSuffix(" %")
            self.ratio_value_spin.setRange(1, 100)
            self.ratio_value_spin.setValue(50)
        else: # Largeur ou Hauteur
            self.ratio_value_spin.setSuffix(" px")
            self.ratio_value_spin.setRange(1, 10000)
            self.ratio_value_spin.setValue(1024)
        self.update_resize_preview()

    def apply_settings_to_selection(self):
        """Applique les réglages de l'interface aux fichiers sélectionnés"""
        selected_items = self.resize_table.selectedItems()
        if not selected_items:
            return
            
        # Get UI Values
        is_ratio = self.mode_switch.is_left_active()
        ratio_mode = self.ratio_type_combo.currentIndex()
        val = self.ratio_value_spin.value()
        fix_w = self.fixed_width_spin.value()
        fix_h = self.fixed_height_spin.value()
        
        # Apply to unique rows of selection
        rows = set(item.row() for item in selected_items)
        for row in rows:
            item = self.resize_table.item(row, 0)
            item.setData(Qt.ItemDataRole.UserRole + 10, is_ratio)
            item.setData(Qt.ItemDataRole.UserRole + 11, ratio_mode)
            item.setData(Qt.ItemDataRole.UserRole + 12, val)
            item.setData(Qt.ItemDataRole.UserRole + 13, fix_w)
            item.setData(Qt.ItemDataRole.UserRole + 14, fix_h)
            
        # Update Preview
        self.update_resize_preview()
        self.filter_resize_table()

    def reset_resize_options_ui(self):
        """Réinitialise les réglages UI (visuel seulement) lors du changement de sélection"""
        # Note: Désactivé temporairement car cela empêche de régler les options 
        # AVANT de sélectionner les fichiers à qui les appliquer.
        pass
        # self.mode_switch.btn_left.click() # Ratio
        # self.ratio_type_combo.setCurrentIndex(0)
        # self.ratio_value_spin.setValue(50)
        # self.fixed_width_spin.setValue(1024)
        # self.fixed_height_spin.setValue(1024)

    def update_resize_preview(self):
        """Met à jour le tableau avec les prévisions basées sur les données STOCKÉES par item"""
        count = self.resize_table.rowCount()
        if count == 0:
            return

        total_orig_size = 0
        total_new_size = 0

        for i in range(count):
            item_name = self.resize_table.item(i, 0)
            item_dim = self.resize_table.item(i, 1)
            item_size = self.resize_table.item(i, 2)
            if not item_name: continue
            
            # Récupérer données image
            orig_w = item_name.data(Qt.ItemDataRole.UserRole + 1)
            orig_h = item_name.data(Qt.ItemDataRole.UserRole + 2)
            orig_file_size = item_name.data(Qt.ItemDataRole.UserRole + 3)
            
            if orig_w is None: continue 
            
            # Récupérer données REGLAGES (Item specific)
            is_ratio = item_name.data(Qt.ItemDataRole.UserRole + 10)
            
            # Si aucun réglage n'est associé (None), on affiche en blanc/normal
            if is_ratio is None:
                item_name.setForeground(Qt.GlobalColor.white)
                item_dim.setForeground(Qt.GlobalColor.white)
                item_size.setForeground(Qt.GlobalColor.white)
                item_dim.setText(f"{orig_w}x{orig_h} px")
                item_size.setText(ImageThumbnail.format_file_size(orig_file_size))
                continue

            ratio_mode = item_name.data(Qt.ItemDataRole.UserRole + 11)
            val = item_name.data(Qt.ItemDataRole.UserRole + 12)
            fix_w = item_name.data(Qt.ItemDataRole.UserRole + 13)
            fix_h = item_name.data(Qt.ItemDataRole.UserRole + 14)
            
            total_orig_size += orig_file_size
            
            new_w, new_h = 0, 0
            
            if is_ratio:
                if ratio_mode == 0: # %
                    scale = val / 100.0
                    new_w = int(orig_w * scale)
                    new_h = int(orig_h * scale)
                elif ratio_mode == 1: # Largeur fixe
                    new_w = val
                    if orig_w > 0:
                        new_h = int(orig_h * (val / orig_w))
                elif ratio_mode == 2: # Hauteur fixe
                    new_h = val
                    if orig_h > 0:
                        new_w = int(orig_w * (val / orig_h))
            else: # Dimensions libres
                new_w = fix_w
                new_h = fix_h
            
            # Estimation Poids
            orig_pixels = orig_w * orig_h
            new_pixels = new_w * new_h
            if orig_pixels > 0:
                est_file_size = orig_file_size * (new_pixels / orig_pixels)
            else:
                est_file_size = orig_file_size
            
            total_new_size += est_file_size
            
            # Mise à jour UI Tableau
            # Col 2: Dimensions
            item_dim.setText(f"{orig_w}x{orig_h} ➜ {new_w}x{new_h}")
            
            # Col 3: Poids
            orig_fmt = ImageThumbnail.format_file_size(orig_file_size)
            new_fmt = ImageThumbnail.format_file_size(est_file_size)
            item_size.setText(f"{orig_fmt} ➜ ~{new_fmt}")
            
            # Couleur dynamique
            if est_file_size < orig_file_size:
                # Réduction
                color = Qt.GlobalColor.green
            elif est_file_size > orig_file_size:
                # Augmentation
                color = Qt.GlobalColor.red
            else:
                # Identique
                color = Qt.GlobalColor.white

            item_name.setForeground(color)
            item_dim.setForeground(color)
            item_size.setForeground(color)
        
        # Mise à jour Stats Globales
        gain = total_orig_size - total_new_size
        pct_gain = (gain / total_orig_size * 100) if total_orig_size > 0 else 0
        
        self.global_stats_label.setText(
            f"Fichiers à traiter : {ImageThumbnail.format_file_size(total_orig_size)} ➜ ~{ImageThumbnail.format_file_size(total_new_size)} "
            f"| Gain : {ImageThumbnail.format_file_size(gain)} ({pct_gain:.1f}%)"
        )
        if gain > 0:
            self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4caf50; padding: 5px;")
        elif gain < 0:
            self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f44336; padding: 5px;")
        else:
             self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f1f1f1; padding: 5px;")


    def execute_resize(self):
        """Lance le processus de redimensionnement"""
        count = self.resize_table.rowCount()
        if count == 0:
            QMessageBox.warning(self, "Attention", "Aucune image à traiter.")
            return

        # Identification des fichiers à traiter (Ceux qui ont des réglages associés)
        rows_to_process = []
        for i in range(count):
            item = self.resize_table.item(i, 0)
            if item.data(Qt.ItemDataRole.UserRole + 10) is not None:
                rows_to_process.append(i)
        
        if not rows_to_process:
             QMessageBox.warning(self, "Attention", "Aucun réglage n'a été associé. Cliquez sur 'Associer ces réglages à la sélection' pour préparer les fichiers.")
             return
             
        selection_msg = f"les {len(rows_to_process)} images préparées"

        # Dialogue choix destination
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Lancer l'optimisation")
        msg_box.setText(f"Vous allez traiter {selection_msg}.\nComment voulez-vous sauvegarder ?")
        msg_box.setStyleSheet("background-color: #1a1a2e; color: white;")
        
        btn_overwrite = msg_box.addButton("Écraser les fichiers existants", QMessageBox.ButtonRole.DestructiveRole)
        btn_new_folder = msg_box.addButton("Créer dans un nouveau dossier...", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == btn_cancel:
            return
            
        target_folder = None
        overwrite = False
        
        if clicked_button == btn_overwrite:
            confirm = QMessageBox.question(self, "Confirmation ultime", "Êtes-vous SÛR de vouloir écraser les fichiers originaux ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        elif clicked_button == btn_new_folder:
            target_folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination")
            if not target_folder:
                return
        
        # Paramètres
        is_ratio = self.mode_switch.is_left_active()
        ratio_mode = self.ratio_type_combo.currentIndex()
        val = self.ratio_value_spin.value()
        fix_w = self.fixed_width_spin.value()
        fix_h = self.fixed_height_spin.value()
        
        # Barre de progression
        progress = QDialog(self)
        progress.setWindowTitle("Traitement en cours...")
        progress.setFixedSize(300, 100)
        progress_layout = QVBoxLayout()
        p_bar = QProgressBar()
        progress_layout.addWidget(QLabel("Optimisation des textures..."))
        progress_layout.addWidget(p_bar)
        progress.setLayout(progress_layout)
        progress.show()
        
        success_count = 0
        error_count = 0
            
        p_bar.setRange(0, len(rows_to_process))
        
        for i, row_idx in enumerate(rows_to_process):
            item_name = self.resize_table.item(row_idx, 0)
            path = item_name.data(Qt.ItemDataRole.UserRole)
            
            if not path or not os.path.exists(path):
                continue
                
            # Récupérer les réglages SPÉCIFIQUES à cet item
            is_ratio = item_name.data(Qt.ItemDataRole.UserRole + 10)
            ratio_mode = item_name.data(Qt.ItemDataRole.UserRole + 11)
            val = item_name.data(Qt.ItemDataRole.UserRole + 12)
            fix_w = item_name.data(Qt.ItemDataRole.UserRole + 13)
            fix_h = item_name.data(Qt.ItemDataRole.UserRole + 14)
            
            # Fallback si non défini (auto-apply current UI values if item wasn't explicitly associated)
            if is_ratio is None:
                is_ratio = self.mode_switch.is_left_active()
                ratio_mode = self.ratio_type_combo.currentIndex()
                val = self.ratio_value_spin.value()
                fix_w = self.fixed_width_spin.value()
                fix_h = self.fixed_height_spin.value()

            try:
                # Chargement
                img = QImage(path)
                if img.isNull():
                    error_count += 1
                    continue
                    
                orig_w, orig_h = img.width(), img.height()
                new_w, new_h = 0, 0
                
                # Calcul dimensions
                if is_ratio:
                    if ratio_mode == 0: # %
                        scale = val / 100.0
                        new_w = int(orig_w * scale)
                        new_h = int(orig_h * scale)
                    elif ratio_mode == 1: # Largeur fixe
                        new_w = val
                        if orig_w > 0:
                            new_h = int(orig_h * (val / orig_w))
                    elif ratio_mode == 2: # Hauteur fixe
                        new_h = val
                        if orig_h > 0:
                            new_w = int(orig_w * (val / orig_h))
                else: # Dimensions libres
                    new_w = fix_w
                    new_h = fix_h
                
                # Redimensionnement
                if new_w > 0 and new_h > 0:
                    scaled_img = img.scaled(new_w, new_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    # Sauvegarde
                    save_path = path if overwrite else os.path.join(target_folder, os.path.basename(path))
                    scaled_img.save(save_path)
                    success_count += 1
                else:
                    error_count += 1

            except Exception as e:
                print(f"Erreur resize {path}: {e}")
                error_count += 1
            
            p_bar.setValue(i + 1)
            QApplication.processEvents()
            
        progress.close()
        
        QMessageBox.information(self, "Terminé", f"Traitement terminé.\nSuccès: {success_count}\nErreurs: {error_count}")
        
        # Refresh si overwrite
        if overwrite:
            self.refresh_resize_list()


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
