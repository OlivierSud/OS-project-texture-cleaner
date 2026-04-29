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
    QDialog, QTextEdit, QPlainTextEdit, QSizePolicy, QProgressBar,
    QStyledItemDelegate, QStyle
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRunnable, QThreadPool, QObject, QRegularExpression, QTimer
from PyQt6.QtGui import (
    QPixmap, QIcon, QFont, QImage, QImageReader, QImageWriter, QTextCharFormat, 
    QColor, QTextCursor, QSyntaxHighlighter, QTextDocument, QPalette
)
import ctypes

# Configuration du style Blender
STYLE_CONFIG = {
    "bg_main": "#282828",
    "bg_panel": "#3d3d3d",
    "bg_button": "#4a4a4a",   # Plus de contraste pour les boutons
    "bg_input": "#1d1d1d",
    "accent": "#f09000",      # Orange Blender
    "accent_hover": "#ff9e15",
    "selection": "#4772b3",   # Bleu Blender (Utilisé seulement pour sélection de texte/items)
    "text_main": "#cfcfcf",
    "text_highlight": "#ffffff",
    "border": "#1d1d1d",
    "border_light": "#555555",
    "status_red": "#ff4d4d",
    "status_green": "#4deb4d",
    "status_orange": "#f09000",
    "font_family": "'Inter', 'Segoe UI', 'Roboto', 'Helvetica', sans-serif",
    "font_size": "12px",
    "font_size_small": "11px",
    "font_size_large": "14px"
}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ImageViewer(QScrollArea):
    """Widget pour afficher une image avec zoom et pan"""
    zoomChanged = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False) # On garde le contrôle total de la taille du widget
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #1a1a1a; border: none;")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setScaledContents(True)
        
        self.setWidget(self.image_label)
        
        self.zoom_factor = 1.0
        self.pixmap = None
        self.last_mouse_pos = None
        self.display_size_override = None # Taille logique forcée pour l'affichage (stretch)

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        if pixmap and not pixmap.isNull():
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.clear()
            self.image_label.setText("Pas d'image")
        self.update_viewer()

    def update_viewer(self):
        if self.pixmap and not self.pixmap.isNull():
            # On utilise la taille forcée si elle existe, sinon la taille réelle de la pixmap
            base_size = self.display_size_override if self.display_size_override else self.pixmap.size()
            size = base_size * self.zoom_factor
            self.image_label.setFixedSize(size)
            # setScaledContents(True) s'occupe d'étirer l'image dans le label
        else:
            self.image_label.setFixedSize(QSize(0, 0))

    def center_image(self):
        """Place les scrollbars au centre"""
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        h_bar.setValue((h_bar.minimum() + h_bar.maximum()) // 2)
        v_bar.setValue((v_bar.minimum() + v_bar.maximum()) // 2)

    def wheelEvent(self, event):
        if not self.pixmap or self.pixmap.isNull():
            return

        old_zoom = self.zoom_factor
        delta = event.angleDelta().y()
        
        if delta > 0:
            self.zoom_factor *= 1.1
        else:
            self.zoom_factor /= 1.1
            
        self.zoom_factor = max(0.1, min(self.zoom_factor, 10.0))
        
        if old_zoom == self.zoom_factor:
            return

        # Position de la souris dans le viewport (zone visible)
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        
        # Point dans l'image avant le zoom
        # mapFromParent ou mapFromViewport pour être sûr du point visé
        point_in_image = self.image_label.mapFrom(self.viewport(), pos)
        
        # Appliquer le zoom
        self.update_viewer()
        
        # Calcul du décalage (offset) pour que le point reste sous la souris
        ratio = self.zoom_factor / old_zoom
        new_point_in_image = point_in_image * ratio
        
        # On calcule les nouvelles valeurs de scroll
        # delta = nouveau_point_image - position_souris_viewport
        new_h = new_point_in_image.x() - pos.x()
        new_v = new_point_in_image.y() - pos.y()
        
        self.horizontalScrollBar().setValue(int(new_h))
        self.verticalScrollBar().setValue(int(new_v))
        
        self.zoomChanged.emit(self.zoom_factor)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos is not None:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()
            
            # Pan
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class SyncedImageViewer(QWidget):
    """Double visionneuse synchronisée pour comparer source et compressé"""
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Grid pour les labels et les viewers
        grid_layout = QGridLayout()
        grid_layout.setSpacing(2)
        
        label_style = "font-weight: bold; color: #f09000; background-color: #282828; padding: 4px;"
        
        self.label_left = QLabel("SOURCE (ORIGINAL)")
        self.label_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_left.setStyleSheet(label_style)
        
        self.label_right = QLabel("PREVIEW (COMPRESSED)")
        self.label_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_right.setStyleSheet(label_style)
        
        self.left_viewer = ImageViewer()
        self.right_viewer = ImageViewer()
        
        # Synchronisation du zoom et du scroll
        self.left_viewer.horizontalScrollBar().valueChanged.connect(lambda v: self.sync_h_scroll(v, source='left'))
        self.right_viewer.horizontalScrollBar().valueChanged.connect(lambda v: self.sync_h_scroll(v, source='right'))
        self.left_viewer.verticalScrollBar().valueChanged.connect(self.sync_v_scroll)
        self.right_viewer.verticalScrollBar().valueChanged.connect(self.sync_v_scroll)
        
        # Sync Zoom
        self.left_viewer.zoomChanged.connect(self.sync_zoom)
        self.right_viewer.zoomChanged.connect(self.sync_zoom)
        
        grid_layout.addWidget(self.label_left, 0, 0)
        grid_layout.addWidget(self.label_right, 0, 1)
        grid_layout.addWidget(self.left_viewer, 1, 0)
        grid_layout.addWidget(self.right_viewer, 1, 1)
        
        main_layout.addLayout(grid_layout)
        
        self.is_syncing = False

    def sync_h_scroll(self, value, source='left'):
        """Synchronise le scroll horizontal pour créer une continuité"""
        if self.is_syncing: return
        self.is_syncing = True
        
        if source == 'left':
            # Si on bouge à gauche, la droite suit avec le même offset relatif
            # Pour la continuité : si l'image de gauche finit au milieu de son viewer,
            # celle de droite doit commencer au milieu de son viewer.
            self.right_viewer.horizontalScrollBar().setValue(value)
        else:
            self.left_viewer.horizontalScrollBar().setValue(value)
            
        self.is_syncing = False

    def sync_v_scroll(self, value):
        if self.is_syncing: return
        self.is_syncing = True
        self.left_viewer.verticalScrollBar().setValue(value)
        self.right_viewer.verticalScrollBar().setValue(value)
        self.is_syncing = False

    def sync_zoom(self, zoom):
        if self.is_syncing: return
        self.is_syncing = True
        self.left_viewer.zoom_factor = zoom
        self.right_viewer.zoom_factor = zoom
        
        # On s'assure que la droite utilise toujours la taille de la gauche comme référence d'affichage
        ref_size = self.left_viewer.pixmap.size() if self.left_viewer.pixmap else None
        self.right_viewer.display_size_override = ref_size
        
        self.left_viewer.update_viewer()
        self.right_viewer.update_viewer()
        self.is_syncing = False

    def set_images(self, original_pixmap, compressed_pixmap=None, reset_view=True):
        # La source garde sa taille originale
        self.left_viewer.display_size_override = None
        self.left_viewer.set_pixmap(original_pixmap)
        
        # La preview s'adapte à la taille de la source pour permettre la comparaison à même échelle
        ref_size = original_pixmap.size() if original_pixmap else None
        self.right_viewer.display_size_override = ref_size
        
        if compressed_pixmap:
            self.right_viewer.set_pixmap(compressed_pixmap)
        else:
            self.right_viewer.set_pixmap(original_pixmap)
        
        # Force a center view after loading only if requested
        if reset_view:
            self.reset_view()

    def reset_view(self):
        """Réinitialise le zoom et centre les vues"""
        # Centrage différé pour laisser le temps au layout de se mettre à jour
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.left_viewer.center_image)
        QTimer.singleShot(50, self.right_viewer.center_image)

    # --- Fin Signaux ---

class SortableTableWidgetItem(QTableWidgetItem):
    """Item de tableau personnalisé pour trier sur une valeur numérique (ou autre clé)"""
    def __init__(self, text, sort_key):
        super().__init__(text)
        self.sort_key = sort_key

    def __lt__(self, other):
        return self.sort_key < other.sort_key

class TableColorDelegate(QStyledItemDelegate):
    """Delegate pour garder la couleur du texte même lors de la sélection"""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Si une couleur de texte (ForegroundRole) est définie, on l'utilise pour la sélection aussi
        fg = index.data(Qt.ItemDataRole.ForegroundRole)
        if fg and isinstance(fg, QColor):
            option.palette.setColor(QPalette.ColorRole.HighlightedText, fg)
        elif fg and hasattr(fg, 'color'): # Parfois c'est une QBrush
            option.palette.setColor(QPalette.ColorRole.HighlightedText, fg.color())


class WorkerSignals(QObject):
    """Signaux pour le worker de chargement d'image"""
    finished = pyqtSignal(QImage)
    error = pyqtSignal()

class CompressionSignals(QObject):
    """Signaux pour le worker de compression"""
    finished = pyqtSignal(int, int, QPixmap) # index, new_size, pixmap

class CompressionWorker(QRunnable):
    """Worker pour compresser une image en arrière-plan"""
    def __init__(self, index, path, quality, format_name, original_size):
        super().__init__()
        self.index = index
        self.path = path
        self.quality = quality
        self.format_name = format_name
        self.original_size = original_size
        self.signals = CompressionSignals()

    def run(self):
        try:
            img = QImage(self.path)
            if img.isNull():
                self.signals.finished.emit(self.index, self.original_size, QPixmap())
                return
                
            from PyQt6.QtCore import QBuffer, QIODevice
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.ReadWrite)
            
            out_format = self.format_name
            if out_format == "JPG": out_format = "JPEG"
            
            q_writer = QImageWriter(buffer, out_format.encode())
            
            if out_format == "PNG":
                q_writer.setQuality(9 if self.quality >= 100 else int(self.quality / 11))
            else:
                q_set = self.quality if self.quality <= 100 else 100
                q_writer.setQuality(q_set)
                
            if q_writer.write(img):
                new_size = buffer.size()
                # Safety check
                if self.quality <= 100 and new_size > self.original_size:
                    self.signals.finished.emit(self.index, self.original_size, QPixmap())
                else:
                    pix = QPixmap()
                    pix.loadFromData(buffer.data())
                    self.signals.finished.emit(self.index, new_size, pix)
            else:
                self.signals.finished.emit(self.index, self.original_size, QPixmap())
        except Exception:
            self.signals.finished.emit(self.index, self.original_size, QPixmap())

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
        
        # Case à cocher pour la sélection (suppression/déplacement)
        if show_delete:
            self.delete_check = QCheckBox("")
            self.delete_check.setCursor(Qt.CursorShape.PointingHandCursor)
            self.delete_check.setToolTip("Mark for deletion or move")
            self.delete_check.setStyleSheet(f"""
                QCheckBox {{
                    color: {STYLE_CONFIG['text_main']};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 4px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                }}
            """)
            self.delete_check.toggled.connect(self.toggle_delete_mark)
            layout.addWidget(self.delete_check, 0, Qt.AlignmentFlag.AlignCenter)
        
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
    
    def toggle_delete_mark(self, checked=None):
        if checked is not None:
            self.marked_for_deletion = checked
        else:
            self.marked_for_deletion = not self.marked_for_deletion
            # Si on toggle manuellement, on met à jour la checkbox
            if hasattr(self, 'delete_check'):
                self.delete_check.blockSignals(True)
                self.delete_check.setChecked(self.marked_for_deletion)
                self.delete_check.blockSignals(False)
                
        self.update_style()
        self.deleteRequested.emit(self.file_path)
    
    def update_style(self):
        if self.marked_for_deletion:
            self.setStyleSheet(f"QFrame {{ background-color: #4d2b2b; border: 1px solid {STYLE_CONFIG['accent']}; border-radius: 4px; }}")
        else:
            self.setStyleSheet(f"QFrame {{ background-color: {STYLE_CONFIG['bg_panel']}; border: 1px solid {STYLE_CONFIG['border']}; border-radius: 4px; }}")
    
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
        active_style = f"background-color: {STYLE_CONFIG['accent']}; color: black; font-weight: bold; border: 1px solid {STYLE_CONFIG['border']};"
        inactive_style = f"background-color: {STYLE_CONFIG['bg_input']}; color: {STYLE_CONFIG['text_main']}; border: 1px solid {STYLE_CONFIG['border']};"
        
        base = "QPushButton { padding: 4px; font-size: 11px;"
        
        # Left button styling
        style_left = base + "border-top-left-radius: 10px; border-bottom-left-radius: 10px;"
        if self.btn_left.isChecked():
            self.btn_left.setStyleSheet(style_left + active_style + "}")
        else:
            self.btn_left.setStyleSheet(style_left + inactive_style + "}")
            
        # Right button styling
        style_right = base + "border-top-right-radius: 10px; border-bottom-right-radius: 10px;"
        if self.btn_right.isChecked():
            self.btn_right.setStyleSheet(style_right + active_style + "}")
        else:
            self.btn_right.setStyleSheet(style_right + inactive_style + "}")



class AdvancedUsageDialog(QDialog):
    def __init__(self, usage_data, image_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Usage de : {image_name}")
        self.setMinimumSize(950, 650)
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
        toolbar.addWidget(QLabel("FILE :"))
        self.file_combo = QComboBox()
        for path in self.file_paths:
            self.file_combo.addItem(os.path.basename(path), path)
        self.file_combo.currentIndexChanged.connect(self.load_file)
        self.file_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {STYLE_CONFIG['bg_input']};
                color: {STYLE_CONFIG['text_main']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                padding: 4px;
                min-width: 200px;
            }}
        """)
        toolbar.addWidget(self.file_combo)
        
        toolbar.addSpacing(20)
        
        # Navigation occurrences
        self.prev_btn = QPushButton("PREV")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(self.prev_match)
        self.next_btn = QPushButton("NEXT")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self.next_match)
        self.match_label = QLabel("Occurrence : 0 / 0")
        
        btn_style = f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_panel']};
                color: {STYLE_CONFIG['text_highlight']};
                border: 1px solid {STYLE_CONFIG['border_light']};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {STYLE_CONFIG['accent']}; color: black; }}
        """
        self.prev_btn.setStyleSheet(btn_style)
        self.next_btn.setStyleSheet(btn_style)
        self.match_label.setStyleSheet(f"color: {STYLE_CONFIG['accent']}; font-weight: bold; font-size: 13px;")
        
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.match_label)
        toolbar.addWidget(self.next_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # --- Text Editor ---
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {STYLE_CONFIG['bg_input']};
                color: {STYLE_CONFIG['text_main']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                padding: 10px;
            }}
        """)
        layout.addWidget(self.text_edit)
        
        # Close button
        close_btn = QPushButton("Fermer")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.comp_folder_path = "" # Chemin du dossier pour l'onglet Compression
        
        self.comp_files = [] # Liste des images pour l'onglet Compression
        
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
        self.tabs.addTab(self.cleaner_tab, "Spot unused data")
        
        # Layout pour l'onglet de nettoyage (ancien main_layout)
        cleaner_layout = QVBoxLayout()
        self.cleaner_tab.setLayout(cleaner_layout)
        
        # Header
        header_container = QWidget()
        header_container.setMaximumHeight(60)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_container.setLayout(header_layout)
        header_container.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_panel']}; border-bottom: 1px solid {STYLE_CONFIG['border']};")
        
        header = QLabel("TEXTURE LISTING")
        header.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {STYLE_CONFIG['accent']}; letter-spacing: 1px;")
        header_layout.addWidget(header)
        
        subtitle = QLabel("Gestionnaire de textures professionnel")
        subtitle.setStyleSheet(f"font-size: 12px; color: {STYLE_CONFIG['text_main']};")
        header_layout.addWidget(subtitle)
        
        header_layout.addStretch()
        
        cleaner_layout.setContentsMargins(0, 0, 0, 0)
        cleaner_layout.setSpacing(0)
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
        resize_main_layout.setContentsMargins(8, 8, 8, 8)
        resize_main_layout.setSpacing(4)
        self.resize_tab.setLayout(resize_main_layout)
        
        # --- Zone Haute : Colonnes et Options ---
        top_area_layout = QHBoxLayout()
        top_area_layout.setSpacing(8)
        resize_main_layout.addLayout(top_area_layout, 1) # prend tout l'espace dispo
        
        # --- Colonne Gauche: Tableau des textures ---
        left_col = QWidget()
        left_layout = QVBoxLayout()
        left_col.setLayout(left_layout)
        
        # Header Colonne Gauche
        left_header = QLabel("PROJECT TEXTURES")
        left_header.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {STYLE_CONFIG['text_highlight']}; border-bottom: 1px solid {STYLE_CONFIG['border_light']}; padding-bottom: 2px;")
        left_layout.addWidget(left_header)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.resize_folder_btn = QPushButton("FOLDER")
        self.resize_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resize_folder_btn.clicked.connect(self.select_resize_folder)
        folder_layout.addWidget(self.resize_folder_btn)
        
        refresh_resize_btn = QPushButton("🔄")
        refresh_resize_btn.setFixedSize(34, 34)
        refresh_resize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_resize_btn.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_button']}; color: white; border: 1px solid {STYLE_CONFIG['border_light']}; font-weight: bold; padding: 0px; font-size: 16px;")
        refresh_resize_btn.clicked.connect(self.refresh_resize_list)
        folder_layout.addWidget(refresh_resize_btn)
        
        left_layout.addLayout(folder_layout)
        
        # Tableau des fichiers (Remplace QListWidget)
        self.resize_table = QTableWidget()

        # Recherche et Filtres
        search_filter_layout = QHBoxLayout()
        
        self.resize_search = QLineEdit()
        self.resize_search.setPlaceholderText("Search textures...")
        self.resize_search.textChanged.connect(self.filter_resize_table)
        search_filter_layout.addWidget(self.resize_search, 2)
        
        self.resize_filter_group = QButtonGroup()
        filters = [("All", "all"), ("🟢Prepared", "prepared"), ("​⚪Unchanged", "remaining")]
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
        self.resize_table.setColumnCount(4)
        self.resize_table.setHorizontalHeaderLabels(["File", "Dimensions", "Weight", "Gain"])
        
        # Config tableau style handled by global QSS
        self.resize_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.resize_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.resize_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.resize_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.resize_table.setColumnWidth(3, 80)
        self.resize_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.resize_table.verticalHeader().setVisible(False)
        self.resize_table.cellDoubleClicked.connect(self.open_image_popup_from_table) # Popup double clic
        self.resize_table.itemSelectionChanged.connect(self.on_resize_row_changed) # Update preview and UI on selection change
        self.resize_table.setSortingEnabled(True)
        
        left_layout.addWidget(self.resize_table)
        
        top_area_layout.addWidget(left_col, 2)
        
        # --- Colonne Droite: Options & Preview ---
        right_container = QWidget()
        right_v_layout = QVBoxLayout(right_container)
        right_v_layout.setContentsMargins(0, 0, 0, 0)
        right_v_layout.setSpacing(4)
        
        # --- Colonne Droite: Options ---
        right_col = QGroupBox("ACTION SETTINGS")
        right_layout = QVBoxLayout()
        right_col.setLayout(right_layout)
        
        # Mode de redimensionnement (Nouveau Switch Custom)
        switch_layout = QHBoxLayout()
        switch_layout.addStretch()
        
        # Instantiation du Toggle Switch
        self.mode_switch = SegmentedToggle("RATIO", "FIXED", self)
        
        switch_layout.addWidget(self.mode_switch)
        switch_layout.addStretch()
        
        right_layout.addLayout(switch_layout)
        right_layout.addSpacing(10)
        
        # Options Ratio
        self.ratio_options_frame = QFrame()
        ratio_layout = QVBoxLayout()
        self.ratio_options_frame.setLayout(ratio_layout)
        
        self.ratio_type_combo = QComboBox()
        self.ratio_type_combo.addItems(["Reduction Percentage", "Fixed Width (Auto H)", "Fixed Height (Auto W)"])
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
        self.apply_btn = QPushButton("APPLY TO SELECTION")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self.apply_settings_to_selection)
        right_layout.addWidget(self.apply_btn)
        
        right_layout.addStretch()
        right_v_layout.addWidget(right_col, 0)
        
        # Visionneuse de comparaison (Comme dans l'onglet Compression)
        self.resize_viewer = SyncedImageViewer()
        self.resize_viewer.label_right.setText("PREVIEW (RESIZED)")
        right_v_layout.addWidget(self.resize_viewer, 1)
        
        top_area_layout.addWidget(right_container, 3) # Plus de place pour la preview

        # --- Zone Basse: Stats et Actions ---
        bottom_container = QFrame()
        bottom_container.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_panel']}; border-top: 1px solid {STYLE_CONFIG['border']}; border-radius: 0px;")
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(10, 5, 10, 10)
        bottom_layout.setSpacing(5)
        bottom_container.setLayout(bottom_layout)

        # Stats Globales
        self.global_stats_label = QLabel("Weight : 0 MB -> 0 MB | Gain : 0 MB (0%)")
        self.global_stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.global_stats_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {STYLE_CONFIG['text_main']}; padding: 10px; border-bottom: 1px solid {STYLE_CONFIG['border']};")
        bottom_layout.addWidget(self.global_stats_label)

        # Bouton d'exécution
        self.execute_btn = QPushButton("RUN OPTIMIZATION")
        self.execute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.execute_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_button']};
                color: {STYLE_CONFIG['text_highlight']};
                font-weight: bold;
                padding: 15px;
                font-size: 16px;
                border-radius: 4px;
                border: 2px solid {STYLE_CONFIG['accent']};
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['border_light']};
                border: 2px solid {STYLE_CONFIG['accent_hover']};
            }}
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
        
        comp_main_layout = QVBoxLayout()
        comp_main_layout.setContentsMargins(0, 0, 0, 0)
        comp_main_layout.setSpacing(0)
        self.compression_tab.setLayout(comp_main_layout)
        
        # Splitter pour les 3 colonnes de compression
        self.comp_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Colonne 1: Liste des images
        self.comp_col1 = self.create_comp_list_column()
        self.comp_splitter.addWidget(self.comp_col1)
        
        # Colonne 2: Réglages
        self.comp_col2 = self.create_comp_settings_column()
        self.comp_splitter.addWidget(self.comp_col2)
        
        # Colonne 3: Visionneuse
        self.comp_col3 = self.create_comp_preview_column()
        self.comp_splitter.addWidget(self.comp_col3)
        
        self.comp_splitter.setSizes([450, 300, 850])
        comp_main_layout.addWidget(self.comp_splitter)
        
        # Style global - Mode Blender Pro
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {STYLE_CONFIG['bg_main']};
                font-family: {STYLE_CONFIG['font_family']};
                font-size: {STYLE_CONFIG['font_size']};
            }}
            
            QWidget {{
                color: {STYLE_CONFIG['text_main']};
                font-family: {STYLE_CONFIG['font_family']};
            }}

            QTabWidget::pane {{
                border: 1px solid {STYLE_CONFIG['border']};
                background-color: {STYLE_CONFIG['bg_main']};
                top: -1px;
            }}
            
            QTabBar::tab {{
                background: {STYLE_CONFIG['bg_panel']};
                color: {STYLE_CONFIG['text_main']};
                padding: 6px 15px;
                border: 1px solid {STYLE_CONFIG['border']};
                border-bottom: none;
                margin-right: 1px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            
            QTabBar::tab:selected {{
                background: {STYLE_CONFIG['bg_main']};
                border-bottom: 2px solid {STYLE_CONFIG['accent']};
                color: {STYLE_CONFIG['text_highlight']};
                font-weight: bold;
            }}

            QGroupBox {{
                background-color: {STYLE_CONFIG['bg_panel']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                margin-top: 18px;
                padding-top: 10px;
                font-weight: bold;
                color: {STYLE_CONFIG['text_highlight']};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                background-color: transparent;
            }}

            QPushButton {{
                background-color: {STYLE_CONFIG['bg_button']};
                color: {STYLE_CONFIG['text_highlight']};
                border: 1px solid {STYLE_CONFIG['border_light']};
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: normal;
            }}
            
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['border_light']};
                border: 1px solid {STYLE_CONFIG['accent']};
            }}
            
            QPushButton:pressed {{
                background-color: {STYLE_CONFIG['accent']};
                color: black;
            }}

            QLineEdit, QSpinBox, QComboBox {{
                background-color: {STYLE_CONFIG['bg_input']};
                color: {STYLE_CONFIG['text_highlight']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                padding: 4px 8px;
                selection-background-color: {STYLE_CONFIG['selection']};
            }}
            
            QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
                border: 1px solid {STYLE_CONFIG['border_light']};
            }}
            
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border: 1px solid {STYLE_CONFIG['accent']};
            }}

            QListWidget {{
                background-color: {STYLE_CONFIG['bg_input']};
                color: {STYLE_CONFIG['text_main']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                outline: none;
            }}
            
            QListWidget::item {{
                padding: 4px;
                border-radius: 2px;
            }}
            
            QListWidget::item:selected {{
                background-color: {STYLE_CONFIG['selection']};
                color: white;
            }}

            /* Scrollbars Blender Style */
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {STYLE_CONFIG['border_light']};
                min-height: 20px;
                border-radius: 4px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: #777;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                border: none;
                background: none;
            }}
            
            QScrollBar:horizontal {{
                border: none;
                background: transparent;
                height: 8px;
                margin: 0px;
            }}
            
            QScrollBar::handle:horizontal {{
                background: {STYLE_CONFIG['border_light']};
                min-width: 20px;
                border-radius: 4px;
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                border: none;
                background: none;
            }}

            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            QHeaderView::section {{
                background-color: {STYLE_CONFIG['bg_panel']};
                color: {STYLE_CONFIG['text_highlight']};
                padding: 4px;
                border: 1px solid {STYLE_CONFIG['border']};
                font-weight: bold;
            }}

            QTableWidget {{
                background-color: {STYLE_CONFIG['bg_input']};
                gridline-color: {STYLE_CONFIG['border']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                outline: none;
                selection-background-color: #5c4326;
                selection-color: white;
            }}
            
            QTableWidget::item:selected {{
                background-color: #5c4326;
                border: 1px solid {STYLE_CONFIG['accent']};
            }}
        """)
    
    def create_source_column(self):
        group = QGroupBox("SOURCE DATA")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)
        
        # Layout boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)
        
        # Bouton de sélection
        select_btn = QPushButton("IMPORT SOURCES")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_button']};
                border: 1px solid {STYLE_CONFIG['border_light']};
                color: {STYLE_CONFIG['text_highlight']};
                font-size: 12px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['border_light']};
                border: 1px solid {STYLE_CONFIG['accent']};
            }}
        """)
        select_btn.clicked.connect(self.select_source_files)
        btn_layout.addWidget(select_btn)
        
        # Bouton actualiser (Icone)
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setToolTip("Reload source files")
        refresh_btn.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_button']}; color: white; border: 1px solid {STYLE_CONFIG['border_light']}; font-weight: bold; padding: 0px; font-size: 16px;")
        refresh_btn.clicked.connect(self.reload_source_files)
        btn_layout.addWidget(refresh_btn)
        
        layout.addLayout(btn_layout)
        
        # Liste des fichiers importés
        self.imported_files_list = QListWidget()
        self.imported_files_list.setMaximumHeight(150)
        self.imported_files_list.setSpacing(4)
        self.imported_files_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {STYLE_CONFIG['bg_input']};
                border: 1px solid {STYLE_CONFIG['border']};
                padding: 5px;
            }}
            QListWidget::item {{
                background-color: {STYLE_CONFIG['bg_panel']};
                border-left: 4px solid {STYLE_CONFIG['accent']};
                padding: 8px;
                margin-bottom: 2px;
                color: {STYLE_CONFIG['text_highlight']};
            }}
            QListWidget::item:hover {{
                background-color: {STYLE_CONFIG['border_light']};
            }}
        """)
        layout.addWidget(QLabel("IMPORTED FILES:"))
        layout.addWidget(self.imported_files_list)
        

        
        self.source_search = QLineEdit()
        self.source_search.setPlaceholderText("Search...")
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
        
        filters = [("ALL", "all"), (".jpg", ".jpg"), (".png", ".png"), 
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
        group = QGroupBox("TEXTURE FOLDER")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)
        
        # Layout boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)

        # Bouton de sélection
        select_btn = QPushButton("SELECT FOLDER")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_button']};
                border: 1px solid {STYLE_CONFIG['border_light']};
                color: {STYLE_CONFIG['text_highlight']};
                font-size: 12px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['border_light']};
                border: 1px solid {STYLE_CONFIG['accent']};
            }}
        """)
        select_btn.clicked.connect(self.select_folder)
        btn_layout.addWidget(select_btn)
        
        # Bouton actualiser (Icone)
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setToolTip("Rescan folder")
        refresh_btn.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_button']}; color: white; border: 1px solid {STYLE_CONFIG['border_light']}; font-weight: bold; padding: 0px; font-size: 16px;")
        refresh_btn.clicked.connect(self.reload_folder_files)
        btn_layout.addWidget(refresh_btn)
        
        layout.addLayout(btn_layout)
        

        
        self.folder_search = QLineEdit()
        self.folder_search.setPlaceholderText("Search...")
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
        
        filters = [("All", "all"), ("● Both", "green"), ("● Folder only", "red")]
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
        group = QGroupBox("SUMMARY")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)
        
        # Légende
        legend_group = QGroupBox("Légende")
        legend_layout = QVBoxLayout()
        
        l_source = QLabel("🔴 - Source file only")
        l_source.setStyleSheet(f"color: {STYLE_CONFIG['status_red']}; font-weight: bold;")
        legend_layout.addWidget(l_source)
        
        l_both = QLabel("🟢 - Present in both")
        l_both.setStyleSheet(f"color: {STYLE_CONFIG['status_green']}; font-weight: bold;")
        legend_layout.addWidget(l_both)
        
        l_folder = QLabel("🟠 - Folder only")
        l_folder.setStyleSheet(f"color: {STYLE_CONFIG['status_orange']}; font-weight: bold;")
        legend_layout.addWidget(l_folder)
        
        legend_group.setLayout(legend_layout)
        layout.addWidget(legend_group)
        
        # Cartes statistiques
        self.stat_source = self.create_stat_card("IMAGE IN COURCES", STYLE_CONFIG['bg_button'], 
                                                  lambda: self.show_modal('source'))
        self.stat_folder = self.create_stat_card("IMAGE IN FOLDER", STYLE_CONFIG['bg_button'],
                                                  lambda: self.show_modal('folder'))
        self.stat_match = self.create_stat_card("MATCHING IMAGES", STYLE_CONFIG['bg_button'],
                                                 lambda: self.show_modal('match'))
        self.stat_missing = self.create_stat_card("ORPHANS", "#4d2b2b",
                                                   lambda: self.show_modal('missing'))
        self.stat_missing.setProperty("subtext", "(See and delete files)")
        
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
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {STYLE_CONFIG['text_highlight']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 6px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                padding: 15px;
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['border_light']};
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
        subtext = card.property("subtext")
        # Format avec nombre en gros, label en petit, taille en bas
        text = f"{count}\n{label}\n{size}"
        if subtext:
             text += f"\n\n{subtext}"
        card.setText(text)
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
            # Sync avec les autres onglets
            self.resize_folder_path = folder
            self.comp_folder_path = folder
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
            item = QPushButton(f"{img_name}")
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            
            item.setStyleSheet(f"""
                QPushButton {{
                    background-color: {STYLE_CONFIG['bg_input']};
                    border-radius: 4px;
                    padding: 8px;
                    margin-bottom: 2px;
                    color: {STYLE_CONFIG['text_main']};
                    border: 1px solid {STYLE_CONFIG['border']};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {STYLE_CONFIG['border_light']};
                    border: 1px solid {STYLE_CONFIG['accent']};
                    color: {STYLE_CONFIG['text_highlight']};
                }}
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
            item = QPushButton(f"{file_info['name']}")
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            
            status_color = STYLE_CONFIG['status_green'] if is_in_source else STYLE_CONFIG['status_orange']
            
            item.setStyleSheet(f"""
                QPushButton {{
                    background-color: {STYLE_CONFIG['bg_input']};
                    border-radius: 4px;
                    padding: 8px;
                    margin-bottom: 2px;
                    color: {status_color};
                    font-weight: bold;
                    border: 1px solid {STYLE_CONFIG['border']};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {STYLE_CONFIG['border_light']};
                    border: 1px solid {STYLE_CONFIG['accent']};
                    color: {STYLE_CONFIG['text_highlight']};
                }}
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
            title = "SOURCE DATA IMAGES"
            files_to_show = [{'name': name, 'path': '', 'size': 0} for name in self.source_files]
        elif modal_type == 'folder':
            title = "FOLDER IMAGES"
            files_to_show = self.folder_files
        elif modal_type == 'match':
            title = "MATCHING IMAGES [ok]"
            files_to_show = [f for f in self.folder_files if f['name'].lower() in self.source_files]
        else:  # missing
            title = "ORPHAN IMAGES [!!]"
            files_to_show = [f for f in self.folder_files if f['name'].lower() not in self.source_files]
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {STYLE_CONFIG['accent']}; padding: 10px; background-color: {STYLE_CONFIG['bg_panel']}; border-bottom: 1px solid {STYLE_CONFIG['border']};")
        layout.addWidget(title_label)
        
            # Boutons d'action pour "missing"
        if modal_type == 'missing' and files_to_show:
            action_layout = QHBoxLayout()
            
            select_all_btn = QPushButton(f"SELECT ALL ({len(files_to_show)})")
            select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            select_all_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {STYLE_CONFIG['bg_panel']};
                    color: white;
                    padding: 10px;
                    border: 1px solid {STYLE_CONFIG['border_light']};
                }}
                QPushButton:hover {{
                    background-color: {STYLE_CONFIG['accent']};
                    color: black;
                }}
            """)
            
            self.move_btn = QPushButton("MOVE SELECTION")
            self.move_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.move_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {STYLE_CONFIG['bg_panel']};
                    color: {STYLE_CONFIG['text_highlight']};
                    padding: 10px;
                    border: 1px solid {STYLE_CONFIG['border_light']};
                }}
                QPushButton:hover {{
                    background-color: {STYLE_CONFIG['accent']};
                    color: black;
                }}
                 QPushButton:disabled {{
                    background-color: {STYLE_CONFIG['bg_input']};
                    color: #555;
                    border: 1px solid {STYLE_CONFIG['border']};
                }}
            """)
            self.move_btn.setEnabled(False)

            self.delete_btn = QPushButton("DELETE SELECTION")
            self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #4d2b2b;
                    color: #ff9999;
                    padding: 10px;
                    border: 1px solid #803030;
                }}
                QPushButton:hover {{
                    background-color: #803030;
                    color: white;
                }}
                 QPushButton:disabled {{
                    background-color: {STYLE_CONFIG['bg_input']};
                    color: #555;
                    border: 1px solid {STYLE_CONFIG['border']};
                }}
            """)
            self.delete_btn.setEnabled(False)
            
            action_layout.addWidget(select_all_btn)
            action_layout.addWidget(self.move_btn)
            action_layout.addWidget(self.delete_btn)
            layout.addLayout(action_layout)
            
            # Séparateur
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(f"background-color: {STYLE_CONFIG['border']}; margin: 10px 0;")
            layout.addWidget(separator)
        
        # Statistiques
        total_size = sum(f['size'] for f in files_to_show)
        stats_label = QLabel(f"📊 {len(files_to_show)} images • {ImageThumbnail.format_file_size(total_size)}")
        stats_label.setStyleSheet(f"font-size: 13px; padding: 10px; color: {STYLE_CONFIG['text_main']};")
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
        button_box.setStyleSheet(f"QPushButton {{ background-color: {STYLE_CONFIG['bg_panel']}; color: {STYLE_CONFIG['text_highlight']}; border: 1px solid {STYLE_CONFIG['border_light']}; padding: 5px 15px; }}")
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Connecter les boutons d'action
        if modal_type == 'missing' and files_to_show:
            select_all_btn.clicked.connect(lambda: self.toggle_select_all(thumbnails, select_all_btn))
            self.delete_btn.clicked.connect(lambda: self.delete_selected_files(thumbnails, dialog))
            self.move_btn.clicked.connect(lambda: self.move_selected_files(thumbnails, dialog))
        
        dialog.setLayout(layout)
        dialog.setStyleSheet(f"QDialog {{ background-color: {STYLE_CONFIG['bg_main']}; border: 1px solid {STYLE_CONFIG['border']}; }}")
        
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
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {STYLE_CONFIG['accent']};
            padding: 10px;
            background-color: {STYLE_CONFIG['bg_panel']};
            border-bottom: 1px solid {STYLE_CONFIG['border']};
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
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_panel']};
                color: {STYLE_CONFIG['text_highlight']};
                padding: 10px;
                font-size: 14px;
                border: 1px solid {STYLE_CONFIG['border_light']};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['accent']};
                color: black;
            }}
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
        """Gestion du changement d'onglet avec synchronisation du dossier de travail"""
        # On cherche un dossier déjà ouvert dans n'importe quel onglet
        active_path = self.current_folder_path or self.resize_folder_path or self.comp_folder_path
        if not active_path:
            return

        if index == 0: # Onglet Nettoyage
            if not self.current_folder_path or self.current_folder_path != active_path:
                self.current_folder_path = active_path
                self.scan_folder(active_path)
            elif not self.folder_files and self.current_folder_path:
                self.scan_folder(self.current_folder_path)

        elif index == 1: # Onglet Resize
            if not self.resize_folder_path or self.resize_folder_path != active_path:
                self.resize_folder_path = active_path
                self.populate_resize_list()
            elif self.resize_table.rowCount() == 0 and self.resize_folder_path:
                self.populate_resize_list()

        elif index == 2: # Onglet Compression
            if not self.comp_folder_path or self.comp_folder_path != active_path:
                self.comp_folder_path = active_path
                self.refresh_comp_list()
            elif not self.comp_files and self.comp_folder_path:
                self.refresh_comp_list()
            
    def select_resize_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner dossier pour redimensionnement")
        if folder:
            self.resize_folder_path = folder
            # Sync avec les autres onglets
            self.current_folder_path = folder
            self.comp_folder_path = folder
            self.populate_resize_list()
            
    def refresh_resize_list(self):
        self.populate_resize_list()
            
    def populate_resize_list(self):
        """Remplit la liste des fichiers pour l'onglet Resize"""
    def populate_resize_list(self):
        """Remplit la liste des fichiers pour l'onglet Resize"""
        self.resize_table.setSortingEnabled(False)
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
                sort_dim = size.width() * size.height()
                item_dim = SortableTableWidgetItem(f"{size.width()}x{size.height()} px", sort_dim)
                self.resize_table.setItem(i, 1, item_dim)
                
                # Colonne 3: Poids init
                item_size = SortableTableWidgetItem(ImageThumbnail.format_file_size(file_size), file_size)
                self.resize_table.setItem(i, 2, item_size)
                
                # Colonne 4: Gain init
                item_gain = SortableTableWidgetItem("-", 0)
                item_gain.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.resize_table.setItem(i, 3, item_gain)
                
            except Exception as e:
                print(f"Erreur lecture {path}: {e}")
                
        # Lancer la prévisualisation initiale
        self.update_resize_preview()
        self.resize_table.setSortingEnabled(True)
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
        self.on_resize_row_changed() # Force update comparison viewer
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
        
        # Disable sorting temporarily to avoid rows jumping during update if sorted by dynamic values
        was_sorting = self.resize_table.isSortingEnabled()
        self.resize_table.setSortingEnabled(False)

        for i in range(count):
            item_name = self.resize_table.item(i, 0)
            item_dim = self.resize_table.item(i, 1)
            item_size = self.resize_table.item(i, 2)
            item_gain = self.resize_table.item(i, 3)
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
                item_gain.setForeground(Qt.GlobalColor.white)
                item_dim.setText(f"{orig_w}x{orig_h} px")
                # Reset sort keys to original values
                if isinstance(item_dim, SortableTableWidgetItem):
                    item_dim.sort_key = orig_w * orig_h
                
                item_size.setText(ImageThumbnail.format_file_size(orig_file_size))
                if isinstance(item_size, SortableTableWidgetItem):
                     item_size.sort_key = orig_file_size

                item_gain.setText("-")
                if isinstance(item_gain, SortableTableWidgetItem):
                    item_gain.sort_key = 0
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
            if isinstance(item_dim, SortableTableWidgetItem):
                 # Sort by new dimensions (or maybe ratio of change? stick to pixel count)
                 item_dim.sort_key = new_pixels
            
            # Col 3: Poids
            orig_fmt = ImageThumbnail.format_file_size(orig_file_size)
            new_fmt = ImageThumbnail.format_file_size(est_file_size)
            
            # Calcul du gain pour la ligne
            gain_row = orig_file_size - est_file_size
            pct_row = (gain_row / orig_file_size * 100) if orig_file_size > 0 else 0
            sign = "-" if gain_row >= 0 else "+"
            
            item_size.setText(f"{orig_fmt} ➜ ~{new_fmt}")
            if isinstance(item_size, SortableTableWidgetItem):
                item_size.sort_key = est_file_size
            
            # Col 4: Gain
            item_gain.setText(f"{sign}{abs(pct_row):.1f}%")
            if isinstance(item_gain, SortableTableWidgetItem):
                item_gain.sort_key = pct_row # Sort by reduction percentage (negative is better/more reduction)
            
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
            item_gain.setForeground(color)
        
        # Mise à jour Stats Globales
        gain = total_orig_size - total_new_size
        pct_gain = (gain / total_orig_size * 100) if total_orig_size > 0 else 0
        
        # Restore sorting
        self.resize_table.setSortingEnabled(was_sorting)

        # Restore sorting
        self.resize_table.setSortingEnabled(was_sorting)

        self.global_stats_label.setText(
            f"Optimization result : {ImageThumbnail.format_file_size(total_orig_size)} ➜ ~{ImageThumbnail.format_file_size(total_new_size)} "
            f"| Save : {ImageThumbnail.format_file_size(gain)} ({pct_gain:.1f}%)"
        )
        if gain > 0:
            self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4caf50; padding: 5px;")
        elif gain < 0:
            self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f44336; padding: 5px;")
        else:
             self.global_stats_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f1f1f1; padding: 5px;")

    def on_resize_row_changed(self):
        """Met à jour la visionneuse de comparaison pour l'onglet Resize"""
        # On garde aussi l'ancien comportement si besoin (actuellement vide)
        self.reset_resize_options_ui()
        
        selection = self.resize_table.selectedItems()
        if not selection:
            self.resize_viewer.set_images(QPixmap(), QPixmap())
            self.resize_viewer.label_left.setText("SOURCE (ORIGINAL)")
            self.resize_viewer.label_right.setText("PREVIEW (RESIZED)")
            return
            
        row = selection[0].row()
        item_name = self.resize_table.item(row, 0)
        if not item_name: return
        
        path = item_name.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path): return
        
        # Detection pour ne pas reset le zoom si c'est le même fichier
        should_reset = True
        if hasattr(self, '_last_selected_resize_path') and self._last_selected_resize_path == path:
            should_reset = False
        self._last_selected_resize_path = path
        
        # Load original
        orig_pix = QPixmap(path)
        if orig_pix.isNull(): return
        
        # Get settings for this item
        is_ratio = item_name.data(Qt.ItemDataRole.UserRole + 10)
        
        if is_ratio is not None:
            # Calculate target size
            orig_w = item_name.data(Qt.ItemDataRole.UserRole + 1)
            orig_h = item_name.data(Qt.ItemDataRole.UserRole + 2)
            ratio_mode = item_name.data(Qt.ItemDataRole.UserRole + 11)
            val = item_name.data(Qt.ItemDataRole.UserRole + 12)
            fix_w = item_name.data(Qt.ItemDataRole.UserRole + 13)
            fix_h = item_name.data(Qt.ItemDataRole.UserRole + 14)
            
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
            
            if new_w > 0 and new_h > 0:
                # On crée une version redimensionnée pour la prévisualisation
                img = QImage(path)
                scaled_img = img.scaled(new_w, new_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                comp_pix = QPixmap.fromImage(scaled_img)
                self.resize_viewer.set_images(orig_pix, comp_pix, reset_view=should_reset)
                
                # Labels
                orig_size_str = ImageThumbnail.format_file_size(item_name.data(Qt.ItemDataRole.UserRole + 3))
                self.resize_viewer.label_left.setText(f"SOURCE: {os.path.basename(path)} ({orig_w}x{orig_h} - {orig_size_str})")
                
                # Estimation du poids pour le label
                orig_pixels = orig_w * orig_h
                new_pixels = new_w * new_h
                est_size = item_name.data(Qt.ItemDataRole.UserRole + 3) * (new_pixels / orig_pixels) if orig_pixels > 0 else 0
                est_size_str = ImageThumbnail.format_file_size(est_size)
                self.resize_viewer.label_right.setText(f"PREVIEW: {new_w}x{new_h} (~{est_size_str})")
            else:
                self.resize_viewer.set_images(orig_pix, orig_pix, reset_view=should_reset)
                self.resize_viewer.label_right.setText("PREVIEW (INVALID SIZE)")
        else:
            # Pas de réglages, afficher l'original des deux côtés
            self.resize_viewer.set_images(orig_pix, orig_pix, reset_view=should_reset)
            self.resize_viewer.label_left.setText(f"SOURCE: {os.path.basename(path)}")
            self.resize_viewer.label_right.setText("PREVIEW (NO SETTINGS)")


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
             QMessageBox.warning(self, "WARNING", "No settings associated. Click 'APPLY TO SELECTION' to prepare files.")
             return
             
        selection_msg = f"{len(rows_to_process)} prepared images"

        # Dialogue choix destination
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("RUN OPTIMIZATION")
        msg_box.setText(f"Process {selection_msg}.\nSelect output method:")
        msg_box.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_main']}; color: {STYLE_CONFIG['text_main']};")
        
        btn_style_dialog = f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_panel']};
                color: {STYLE_CONFIG['text_highlight']};
                border: 1px solid {STYLE_CONFIG['border_light']};
                padding: 8px 15px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {STYLE_CONFIG['accent']}; color: black; }}
        """
        
        btn_overwrite = msg_box.addButton("OVERWRITE ORIGINALS", QMessageBox.ButtonRole.DestructiveRole)
        btn_new_folder = msg_box.addButton("CREATE IN NEW FOLDER", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("CANCEL", QMessageBox.ButtonRole.RejectRole)
        
        btn_overwrite.setStyleSheet(btn_style_dialog)
        btn_new_folder.setStyleSheet(btn_style_dialog)
        btn_cancel.setStyleSheet(btn_style_dialog)
        
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == btn_cancel:
            return
            
        target_folder = None
        overwrite = False
        
        if clicked_button == btn_overwrite:
            confirm = QMessageBox.question(self, "FINAL CONFIRMATION", "Are you SURE you want to overwrite the original files?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        elif clicked_button == btn_new_folder:
            target_folder = QFileDialog.getExistingDirectory(self, "Select Destination Directory")
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
        progress.setWindowTitle("PROCESSING...")
        progress.setFixedSize(400, 120)
        progress.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_panel']}; border: 1px solid {STYLE_CONFIG['border']};")
        progress_layout = QVBoxLayout()
        
        label_p = QLabel("OPTIMIZING TEXTURES...")
        label_p.setStyleSheet(f"color: {STYLE_CONFIG['text_highlight']}; font-weight: bold;")
        
        p_bar = QProgressBar()
        p_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {STYLE_CONFIG['bg_input']};
                border: 1px solid {STYLE_CONFIG['border']};
                border-radius: 4px;
                text-align: center;
                color: white;
            }}
            QProgressBar::chunk {{
                background-color: {STYLE_CONFIG['accent']};
                border-radius: 2px;
            }}
        """)
        
        progress_layout.addWidget(label_p)
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
        
        QMessageBox.information(self, "FINISHED", f"Processing complete.\nSuccess: {success_count}\nErrors: {error_count}")
        
        # Refresh si overwrite
        if overwrite:
            self.refresh_resize_list()

    # --- Gestion Onglet Compression ---

    def create_comp_settings_column(self):
        col = QGroupBox("COMPRESSION SETTINGS")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(15)
        
        # Format
        layout.addWidget(QLabel("Output Format:"))
        self.comp_format_combo = QComboBox()
        self.comp_format_combo.addItems(["Keep Original", "PNG", "WebP", "JPG"])
        self.comp_format_combo.currentIndexChanged.connect(self.clear_comp_previews)
        layout.addWidget(self.comp_format_combo)
        
        # Quality Slider
        quality_header_layout = QHBoxLayout()
        quality_header_layout.addWidget(QLabel("Quality / Compression :"))
        self.quality_val_label = QLabel("100% (Lossless)")
        self.quality_val_label.setStyleSheet(f"color: {STYLE_CONFIG['accent']}; font-weight: bold;")
        quality_header_layout.addStretch()
        quality_header_layout.addWidget(self.quality_val_label)
        layout.addLayout(quality_header_layout)
        
        self.comp_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.comp_quality_slider.setRange(0, 120)
        self.comp_quality_slider.setValue(100)
        self.comp_quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.comp_quality_slider.setTickInterval(20)
        self.comp_quality_slider.valueChanged.connect(self.update_quality_label)
        layout.addWidget(self.comp_quality_slider)
        
        slider_tips = QHBoxLayout()
        slider_tips.addWidget(QLabel("Max Comp (Lossy)"))
        slider_tips.addStretch()
        slider_tips.addWidget(QLabel("Original"))
        for i in range(slider_tips.count()):
            widget = slider_tips.itemAt(i).widget()
            if widget: widget.setStyleSheet("color: #666; font-size: 9px;")
        layout.addLayout(slider_tips)
        
        layout.addSpacing(20)
        
        # Stats Area
        stats_group = QGroupBox("OPTIMIZATION SUMMARY")
        stats_layout = QVBoxLayout(stats_group)
        self.comp_total_size_label = QLabel("Original Size: 0 MB")
        self.comp_new_size_label = QLabel("Estimated Size: 0 MB")
        self.comp_gain_label = QLabel("Total Gain: 0 MB (0%)")
        self.comp_gain_label.setStyleSheet(f"color: {STYLE_CONFIG['status_green']}; font-weight: bold;")
        
        stats_layout.addWidget(self.comp_total_size_label)
        stats_layout.addWidget(self.comp_new_size_label)
        stats_layout.addWidget(self.comp_gain_label)
        layout.addWidget(stats_group)
        
        # Legend Area
        legend_group = QGroupBox("HELP & LEGEND")
        legend_layout = QVBoxLayout(legend_group)
        legend_layout.setSpacing(5)
        
        l1 = QLabel("• WebP / JPG : 0% (Crushed) ➜ 100% (Lossless Quality)")
        l2 = QLabel("• PNG : Slider 0-100% maps to level 0-9 (Compression effort)")
        l3 = QLabel("• Safety : If result > original, original is ALWAYS kept.")
        
        for l in [l1, l2, l3]:
            l.setStyleSheet("color: #bbb; font-size: 10px;")
            legend_layout.addWidget(l)
            
        layout.addWidget(legend_group)
        
        layout.addStretch()
        
        # Action buttons
        self.preview_comp_btn = QPushButton("CALCULATE PREVIEW")
        self.preview_comp_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_panel']};
                color: {STYLE_CONFIG['text_highlight']};
                padding: 10px;
                border: 1px solid {STYLE_CONFIG['border_light']};
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['border_light']};
            }}
        """)
        self.preview_comp_btn.clicked.connect(self.execute_compression_preview)
        layout.addWidget(self.preview_comp_btn)
        
        self.start_comp_btn = QPushButton("EXPORT COMPRESSED")
        self.start_comp_btn.setEnabled(False)
        self.start_comp_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['bg_button']};
                color: {STYLE_CONFIG['accent']};
                font-weight: bold;
                padding: 12px;
                border: 2px solid {STYLE_CONFIG['accent']};
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['accent']};
                color: black;
            }}
            QPushButton:disabled {{
                border-color: #555;
                color: #777;
            }}
        """)
        self.start_comp_btn.clicked.connect(self.export_compressed_files)
        layout.addWidget(self.start_comp_btn)
        
        return col

    def update_quality_label(self, value):
        if value == 120:
            text = "ORIGINAL (No Change)"
        elif value == 100:
            text = "100% (Lossless)"
        else:
            text = f"{value}% (Lossy)"
        self.quality_val_label.setText(text)
        # Note: We don't clear previews here anymore to avoid flicker, 
        # use CALCULATE PREVIEW to update.

    def clear_comp_previews(self):
        """Réinitialise les gains calculés car les réglages ont changé"""
        for f in self.comp_files:
            f['new_size'] = None
            f['compressed_pixmap'] = None
        self.update_comp_table()
        self.start_comp_btn.setEnabled(False)
        self.update_global_comp_stats()

    def create_comp_preview_column(self):
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.comp_viewer = SyncedImageViewer()
        layout.addWidget(self.comp_viewer)
        
        # Zoom tips
        help_label = QLabel("Use Mouse Wheel to Zoom | Drag to Pan")
        help_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(help_label)
        
        return col

    def select_comp_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder for Compression")
        if folder:
            self.comp_folder_path = folder
            # Sync avec les autres onglets
            self.current_folder_path = folder
            self.resize_folder_path = folder
            self.refresh_comp_list()

    def refresh_comp_list(self):
        if not self.comp_folder_path: return
        
        self.comp_files = []
        extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif')
        
        if os.path.exists(self.comp_folder_path):
            for root, dirs, files in os.walk(self.comp_folder_path):
                for file in files:
                    if file.lower().endswith(extensions):
                        path = os.path.join(root, file)
                        try:
                            # Use relative path for display to distinguish files in subfolders
                            rel_name = os.path.relpath(path, self.comp_folder_path)
                            
                            reader = QImageReader(path)
                            size = reader.size()
                            self.comp_files.append({
                                'name': rel_name,
                                'path': path,
                                'size': os.path.getsize(path),
                                'width': size.width(),
                                'height': size.height(),
                                'enabled': True,
                                'new_size': None,
                                'compressed_pixmap': None
                            })
                        except:
                            pass
        
        self.update_comp_table()
        self.update_global_comp_stats()

    def update_comp_table(self):
        self.comp_table.setRowCount(0)
        for i, file_info in enumerate(self.comp_files):
            self.comp_table.insertRow(i)
            
            # Checkbox
            check = QCheckBox()
            check.setChecked(file_info['enabled'])
            check.toggled.connect(lambda checked, idx=i: self.on_comp_check_toggled(idx, checked))
            
            check_widget = QWidget()
            check_layout = QHBoxLayout(check_widget)
            check_layout.addWidget(check)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            check_layout.setContentsMargins(0, 0, 0, 0)
            
            self.comp_table.setCellWidget(i, 0, check_widget)
            
            # File Info
            self.comp_table.setItem(i, 1, QTableWidgetItem(file_info['name']))
            
            # Dimensions
            dim_item = QTableWidgetItem(f"{file_info['width']}x{file_info['height']} px")
            dim_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comp_table.setItem(i, 2, dim_item)
            
            # Size & Gain
            orig_size_str = ImageThumbnail.format_file_size(file_info['size'])
            size_text = orig_size_str
            
            if file_info['new_size'] is not None:
                new_size_str = ImageThumbnail.format_file_size(file_info['new_size'])
                diff = file_info['size'] - file_info['new_size']
                pct = (diff / file_info['size'] * 100) if file_info['size'] > 0 else 0
                
                size_text = f"{orig_size_str} ➜ {new_size_str}"
                gain_text = f" (+{pct:.1f}%)" if diff < 0 else f" (-{pct:.1f}%)"
                
                gain_item = QTableWidgetItem(size_text + gain_text)
                if diff > 0:
                    gain_item.setForeground(QColor(STYLE_CONFIG['status_green']))
                elif diff < 0:
                    gain_item.setForeground(QColor(STYLE_CONFIG['status_red']))
            else:
                gain_item = QTableWidgetItem(size_text)
                
            gain_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.comp_table.setItem(i, 3, gain_item)
            
        self.filter_comp_table()

    def update_global_comp_stats(self):
        total_orig = sum(f['size'] for f in self.comp_files if f['enabled'])
        total_new = sum(f['new_size'] if f['new_size'] is not None else f['size'] for f in self.comp_files if f['enabled'])
        
        self.comp_total_size_label.setText(f"Original Volume: {ImageThumbnail.format_file_size(total_orig)}")
        self.comp_new_size_label.setText(f"Planned Volume: {ImageThumbnail.format_file_size(total_new)}")
        
        gain = total_orig - total_new
        pct = (gain / total_orig * 100) if total_orig > 0 else 0
        self.comp_gain_label.setText(f"Total Gain: {ImageThumbnail.format_file_size(gain)} ({pct:.1f}%)")
        
        if gain > 0:
            self.comp_gain_label.setStyleSheet(f"color: {STYLE_CONFIG['status_green']}; font-weight: bold;")
        elif gain < 0:
            self.comp_gain_label.setStyleSheet(f"color: {STYLE_CONFIG['status_red']}; font-weight: bold;")
        else:
            self.comp_gain_label.setStyleSheet("color: #aaa; font-weight: bold;")

    def on_comp_check_toggled(self, idx, checked):
        if 0 <= idx < len(self.comp_files):
            self.comp_files[idx]['enabled'] = checked
            self.update_global_comp_stats()
            self.filter_comp_table()

    def filter_comp_table(self):
        if not hasattr(self, 'comp_table'):
            return
            
        search = self.comp_search.text().lower()
        show_selected_only = self.comp_show_selected_only.isChecked()
        
        for i in range(self.comp_table.rowCount()):
            name = self.comp_table.item(i, 1).text().lower()
            is_enabled = self.comp_files[i]['enabled']
            
            match_search = search in name
            match_filter = True
            if show_selected_only:
                match_filter = is_enabled
            
            self.comp_table.setRowHidden(i, not (match_search and match_filter))

    def execute_compression_preview(self):
        """Calcule une prévisualisation de la compression en arrière-plan"""
        to_process_indices = [i for i, f in enumerate(self.comp_files) if f['enabled']]
        if not to_process_indices:
            QMessageBox.warning(self, "No Selection", "Please select at least one image.")
            return

        quality = self.comp_quality_slider.value()
        format_idx = self.comp_format_combo.currentIndex()
        
        # UI state
        self.preview_comp_btn.setEnabled(False)
        self.start_comp_btn.setEnabled(False)
        
        self.comp_progress = QProgressBar()
        self.comp_progress.setRange(0, len(to_process_indices))
        self.comp_progress.setValue(0)
        self.statusBar().addPermanentWidget(self.comp_progress)
        self.statusBar().showMessage("Calculating previews in background...")

        self.comp_processed_count = 0
        self.comp_total_to_process = len(to_process_indices)

        formats = [None, "PNG", "WEBP", "JPG"]

        for idx in to_process_indices:
            f = self.comp_files[idx]
            
            if quality == 120 and format_idx == 0:
                # No change required
                self.on_compression_finished(idx, f['size'], QPixmap())
            else:
                # Dispatch to thread pool
                out_format = formats[format_idx] if format_idx != 0 else os.path.splitext(f['name'])[1][1:].upper()
                
                worker = CompressionWorker(idx, f['path'], quality, out_format, f['size'])
                worker.signals.finished.connect(self.on_compression_finished)
                self.thread_pool.start(worker)

    def on_compression_finished(self, idx, new_size, pixmap):
        """Callback quand une image a été compressée en arrière-plan"""
        if idx >= len(self.comp_files): return
        
        self.comp_files[idx]['new_size'] = new_size
        if pixmap and not pixmap.isNull():
            self.comp_files[idx]['compressed_pixmap'] = pixmap
        else:
            self.comp_files[idx]['compressed_pixmap'] = None
            
        self.comp_processed_count += 1
        self.comp_progress.setValue(self.comp_processed_count)
        
        # Mise à jour ciblée du tableau pour éviter les lags
        self.update_table_row_info(idx)
        
        # Update global stats and progress sparingly
        if self.comp_processed_count % 3 == 0 or self.comp_processed_count == self.comp_total_to_process:
            self.update_global_comp_stats()
            
        # FORCE UPDATE PREVIEW if this specific file is the one we are looking at
        selection = self.comp_table.selectedItems()
        if selection and selection[0].row() == idx:
            self.on_comp_row_changed()
            
        if self.comp_processed_count == self.comp_total_to_process:
            self.statusBar().removeWidget(self.comp_progress)
            self.statusBar().showMessage("Preview calculation complete.", 3000)
            self.preview_comp_btn.setEnabled(True)
            self.start_comp_btn.setEnabled(True)

    def update_table_row_info(self, idx):
        """Met à jour uniquement les données d'une ligne sans reconstruire tout le tableau"""
        if idx >= len(self.comp_files): return
        file_info = self.comp_files[idx]
        
        # On cherche l'item correspondant à la ligne logique 'idx'
        # Comme on ne vide pas le tableau entre les finitions de workers, l'index de ligne corresp à idx si pas de tri
        if idx < self.comp_table.rowCount():
            # Size & Gain (Colonne 3)
            orig_size_str = ImageThumbnail.format_file_size(file_info['size'])
            if file_info['new_size'] is not None:
                new_size_str = ImageThumbnail.format_file_size(file_info['new_size'])
                diff = file_info['size'] - file_info['new_size']
                pct = (diff / file_info['size'] * 100) if file_info['size'] > 0 else 0
                size_text = f"{orig_size_str} ➜ {new_size_str}"
                gain_text = f" (+{pct:.1f}%)" if diff < 0 else f" (-{pct:.1f}%)"
                
                gain_item = QTableWidgetItem(size_text + gain_text)
                if diff > 0:
                    gain_item.setForeground(QColor(STYLE_CONFIG['status_green']))
                elif diff < 0:
                    gain_item.setForeground(QColor(STYLE_CONFIG['status_red']))
                else:
                    gain_item.setForeground(QColor(STYLE_CONFIG['text_main']))
            else:
                gain_item = QTableWidgetItem(orig_size_str)
                
            gain_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.comp_table.setItem(idx, 3, gain_item)

    def export_compressed_files(self):
        to_process = [f for f in self.comp_files if f['enabled']]
        if not to_process: return
        
        # Dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("EXPORT OPTIONS")
        msg.setText(f"Export {len(to_process)} optimized images.\nChoose destination method:")
        
        btn_overwrite = msg.addButton("OVERWRITE ORIGINALS", QMessageBox.ButtonRole.DestructiveRole)
        btn_new_folder = msg.addButton("SAVE TO NEW FOLDER", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg.addButton("CANCEL", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        btn = msg.clickedButton()
        
        if btn == btn_cancel: return
        
        dest_folder = None
        if btn == btn_new_folder:
            dest_folder = QFileDialog.getExistingDirectory(self, "Select Export Directory")
            if not dest_folder: return
        else:
            confirm = QMessageBox.question(self, "CONFIRM", "Are you sure you want to OVERWRITE the original files?", 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm != QMessageBox.StandardButton.Yes: return

        # Perform save
        success = 0
        quality = self.comp_quality_slider.value()
        format_idx = self.comp_format_combo.currentIndex()
        formats = [None, "PNG", "WEBP", "JPG"]
        ext_map = ["", ".png", ".webp", ".jpg"]

        for f in to_process:
            try:
                # Use stored preview data if available and smaller
                if f['new_size'] is not None and f['new_size'] < f['size']:
                    # Re-run save with same params to file
                    img = QImage(f['path'])
                    if img.isNull(): continue
                    
                    base_name = os.path.splitext(f['name'])[0]
                    if format_idx == 0:
                        out_ext = os.path.splitext(f['name'])[1]
                        out_format = out_ext[1:].upper()
                        if out_format == "JPG": out_format = "JPEG"
                    else:
                        out_ext = ext_map[format_idx]
                        out_format = formats[format_idx]
                    
                    save_name = base_name + out_ext
                    save_path = os.path.join(dest_folder if dest_folder else os.path.dirname(f['path']), save_name)
                    
                    q_val = quality if quality <= 100 else 100
                    if out_format == "PNG":
                        q_val = 9 if quality >= 100 else int(quality / 11)
                        
                    if img.save(save_path, out_format, q_val):
                        success += 1
                else:
                    # Fallback or original copy
                    base_name = os.path.splitext(f['name'])[0]
                    out_ext = os.path.splitext(f['name'])[1] if format_idx == 0 else ext_map[format_idx]
                    save_name = base_name + out_ext
                    save_path = os.path.join(dest_folder if dest_folder else os.path.dirname(f['path']), save_name)
                    
                    if save_path != f['path']:
                        shutil.copy2(f['path'], save_path)
                    success += 1
                    
            except Exception as e:
                print(f"Export error: {e}")
                
        QMessageBox.information(self, "COMPLETED", f"Successfully exported {success} files.")
        if btn == btn_overwrite:
            self.refresh_comp_list()

    def on_comp_row_changed(self):
        selection = self.comp_table.selectedItems()
        if not selection: return
        
        row = selection[0].row()
        file_info = self.comp_files[row]
        
        # Detection pour ne pas reset le zoom si c'est le même fichier (re-preview)
        current_path = file_info['path']
        should_reset = True
        if hasattr(self, '_last_selected_comp_path') and self._last_selected_comp_path == current_path:
            should_reset = False
        self._last_selected_comp_path = current_path
        
        # Load and set images in viewer
        orig_pix = QPixmap(file_info['path'])
        if not orig_pix.isNull():
            comp_pix = file_info.get('compressed_pixmap')
            self.comp_viewer.set_images(orig_pix, comp_pix, reset_view=should_reset)
            
            # Labels
            orig_size = ImageThumbnail.format_file_size(file_info['size'])
            self.comp_viewer.label_left.setText(f"SOURCE: {file_info['name']} ({orig_size})")
            
            if file_info['new_size'] is not None:
                new_size = ImageThumbnail.format_file_size(file_info['new_size'])
                gain = ((file_info['size'] - file_info['new_size']) / file_info['size'] * 100) if file_info['size'] > 0 else 0
                self.comp_viewer.label_right.setText(f"OPTIMIZED PREVIEW: {new_size} (-{gain:.1f}%)")
            else:
                self.comp_viewer.label_right.setText("PREVIEW (CALCULATION REQUIRED)")

    def toggle_all_comp_selection(self, checked):
        """Active ou désactive tous les fichiers de la liste de compression"""
        if not hasattr(self, 'comp_files'): return
        for f in self.comp_files:
            f['enabled'] = checked
        self.update_comp_table()
        self.update_global_comp_stats()

    # --- Gestion Onglet Compression ---

    def create_comp_list_column(self):
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        header = QLabel("IMAGE SELECTION")
        header.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {STYLE_CONFIG['text_highlight']}; border-bottom: 1px solid {STYLE_CONFIG['border_light']}; padding-bottom: 2px;")
        layout.addWidget(header)
        
        # Folder Select
        folder_layout = QHBoxLayout()
        self.comp_folder_btn = QPushButton("SELECT FOLDER")
        self.comp_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.comp_folder_btn.clicked.connect(self.select_comp_folder)
        folder_layout.addWidget(self.comp_folder_btn)
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_comp_list)
        refresh_btn.setStyleSheet(f"background-color: {STYLE_CONFIG['bg_button']}; font-size: 16px; padding: 0px;")
        folder_layout.addWidget(refresh_btn)
        
        layout.addLayout(folder_layout)
        
        # Search & Filter
        search_layout = QHBoxLayout()
        self.comp_search = QLineEdit()
        self.comp_search.setPlaceholderText("Search images...")
        self.comp_search.textChanged.connect(self.filter_comp_table)
        search_layout.addWidget(self.comp_search, 2)
        
        self.comp_show_selected_only = QCheckBox("SELECTED ONLY")
        self.comp_show_selected_only.setStyleSheet(f"color: {STYLE_CONFIG['text_main']}; font-size: 11px;")
        self.comp_show_selected_only.toggled.connect(self.filter_comp_table)
        search_layout.addWidget(self.comp_show_selected_only, 1)
        
        layout.addLayout(search_layout)
        
    # Table
        self.comp_table = QTableWidget()
        self.comp_table.setColumnCount(4)
        self.comp_table.setHorizontalHeaderLabels(["", "File Name", "Dimensions", "Size / Gain"])
        self.comp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.comp_table.setColumnWidth(0, 30)
        self.comp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.comp_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.comp_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.comp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.comp_table.verticalHeader().setVisible(False)
        self.comp_table.itemSelectionChanged.connect(self.on_comp_row_changed)
        self.comp_table.setSortingEnabled(True)
        
        # Appliquer le delegate pour garder les couleurs
        self.comp_table.setItemDelegateForColumn(1, TableColorDelegate(self.comp_table))
        self.comp_table.setItemDelegateForColumn(2, TableColorDelegate(self.comp_table))
        self.comp_table.setItemDelegateForColumn(3, TableColorDelegate(self.comp_table))
        
        # Checkbox "Tout sélectionner" dans le header de la colonne 0
        self.comp_header_checkbox = QCheckBox(self.comp_table.horizontalHeader())
        self.comp_header_checkbox.setChecked(True)
        self.comp_header_checkbox.toggled.connect(self.toggle_all_comp_selection)
        # Positionnement manuel dans la première cellule du header (col 0 de 30px)
        self.comp_header_checkbox.setGeometry(10, 5, 20, 20)
        
        layout.addWidget(self.comp_table)
        return col


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
            QMessageBox.critical(None, "FATAL ERROR", f"An error occurred during startup:\n\n{error_msg}")
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
