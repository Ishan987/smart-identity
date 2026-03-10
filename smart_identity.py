import sys
import fitz  # PyMuPDF
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QFileDialog, QHBoxLayout, QVBoxLayout, QGraphicsView,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem,
    QSpinBox, QRadioButton, QMessageBox,
    QLineEdit, QGridLayout, QGraphicsRectItem, QButtonGroup,
    QDialog, QSlider, QTextEdit, QComboBox, QGroupBox
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QTransform, QCursor, QPen, QBrush, QColor, QFont
from PyQt5.QtCore import Qt, QPointF, QDateTime
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog


class DraggablePixmapItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, parent_widget=None):
        super().__init__(pixmap)
        self.parent_widget = parent_widget
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(QCursor(Qt.OpenHandCursor))
        # Enable smooth transformation for HD quality when scaled
        self.setTransformationMode(Qt.SmoothTransformation)

    def mousePressEvent(self, event):
        self.setCursor(QCursor(Qt.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(QCursor(Qt.OpenHandCursor))
        super().mouseReleaseEvent(event)
        if self.parent_widget:
            self.parent_widget.update_spinboxes_from_item()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.parent_widget:
            # Only update if PDF is loaded and initial positions are set
            if self.parent_widget.pdf_loaded:
                pos = value
                # Get initial position for relative coordinates
                initial_pos = self.parent_widget.get_initial_pos_for_item(self)
                self.parent_widget.x_input.blockSignals(True)
                self.parent_widget.y_input.blockSignals(True)
                # Display relative coordinates (offset from initial position)
                self.parent_widget.x_input.setValue(int(pos.x() - initial_pos.x()))
                self.parent_widget.y_input.setValue(int(pos.y() - initial_pos.y()))
                self.parent_widget.x_input.blockSignals(False)
                self.parent_widget.y_input.blockSignals(False)
        return super().itemChange(change, value)


class SmartIdentityPro(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Check if this is first run and show installer
        import os
        config_path = os.path.join(os.path.expanduser("~"), ".smart_identity_pro_config")
        self.is_first_run = not os.path.exists(config_path)
        
        if self.is_first_run:
            if not self.show_installer():
                sys.exit(0)  # User cancelled installation
            # Create config file
            try:
                with open(config_path, 'w') as f:
                    f.write("installed=true\n")
            except:
                pass
        
        self.setWindowTitle("Smart Identity Pro")
        self.resize(1400, 950)  # Increased height from 900 to 950

        self.doc = None
        self.pdf_path = None
        self.pdf_loaded = False

        self.front_data_item = None
        self.back_data_item = None
        self.front_bg_item = None
        self.back_bg_item = None
        self.front_blank_item = None
        self.back_blank_item = None
        
        # Store original pixmaps for adjustments
        self.front_data_original = None
        self.back_data_original = None
        self.front_bg_original = None
        self.back_bg_original = None
        
        # License management
        self.is_demo = True
        self.uses_left = 5  # 5 demo uses
        
        # Image adjustments
        self.brightness = 0
        self.contrast = 0
        self.is_bold = False
        self.bold_stroke = 0
        self.bold_timer = None
        self.current_text_mode = 'cropped'
        
        # Settings with defaults
        self.settings = {
            'card_elements': {
                'front_page_header': True,
                'front_page_footer_margin': True,
                'front_page_footer_text': True,
                'rear_page_header': True,
                'rear_page_footer_margin': True,
                'rear_page_footer': True,
                'rear_page_instruction': False,
                'rear_page_uid': True,
                'auto_align_contents': True,
                'photo_frame': False,
                'download_date': False,
                'generation_date': False,
                'colored_footer': True,
                'aadhaar_number': True,
                'vid': True,
                'epic_header_emblem': False
            },
            'offsets': {
                'front_header': 0,
                'rear_header': 0,
                'front_footer': 0,
                'rear_footer': 0,
                'photo': 0
            },
            'user_info': {
                'language': 'English',
                'font_size': 'Large'
            },
            'printer': {
                'type': 'card_printer',
                'pdf_printout': 'PDF PRINTOUT'
            },
            'printing_options': {
                'rotate_front': False,
                'rotate_back': False,
                'a4_cutting_guidelines': False,
                'pdf_printing': False,
                'stamp': False
            },
            'accessibility': {
                'filenames_contain_password': False,
                'show_password': False,
                'remember_last_password': False,
                'auto_detect_footer_language': True
            },
            'child_aadhaar_style': 'half_panel'
        }

        self.scene = QGraphicsScene()
        self.setup_ui()
        self.apply_dark_theme()
        self.setup_loading_overlay()
        self.check_license_on_start()
    
    def show_installer(self):
        """Show installation/setup wizard on first run"""
        installer = QDialog(self)
        installer.setWindowTitle("Smart Identity Pro - Setup Wizard")
        installer.setModal(True)
        installer.setFixedSize(700, 600)
        installer.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Logo/Title
        title = QLabel("🪪 Smart Identity Pro")
        title.setStyleSheet("font-size:32px;font-weight:bold;color:#60a5fa;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        version = QLabel("Version 1.0.0")
        version.setStyleSheet("font-size:14px;color:#94a3b8;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        layout.addSpacing(20)
        
        # Welcome message
        welcome = QLabel("Welcome to Smart Identity Pro!")
        welcome.setStyleSheet("font-size:18px;font-weight:bold;color:#e5e7eb;")
        welcome.setAlignment(Qt.AlignCenter)
        layout.addWidget(welcome)
        
        description = QLabel(
            "Professional ID Card Editor & Generator\n\n"
            "• Edit Aadhaar, PAN, Voter ID, Driving License\n"
            "• Adjust brightness, contrast, and text position\n"
            "• Generate custom employee and student ID cards\n"
            "• Export as PDF or print directly\n"
        )
        description.setStyleSheet("font-size:14px;color:#cbd5e1;line-height:1.6;")
        description.setAlignment(Qt.AlignLeft)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addSpacing(20)
        
        # Features box
        features_box = QWidget()
        features_box.setStyleSheet("background-color:#1e293b;border:2px solid #334155;border-radius:8px;padding:15px;")
        features_layout = QVBoxLayout(features_box)
        
        features_title = QLabel("✨ Key Features")
        features_title.setStyleSheet("font-size:16px;font-weight:bold;color:#93c5fd;")
        features_layout.addWidget(features_title)
        
        features_list = QLabel(
            "✓ Multi-document support (Aadhaar, PAN, DL, Voter ID)\n"
            "✓ Advanced photo editor with brightness/contrast\n"
            "✓ Drag-and-drop text repositioning\n"
            "✓ Custom ID card designer with templates\n"
            "✓ High-quality PDF export (300 DPI)\n"
            "✓ Print directly to any printer"
        )
        features_list.setStyleSheet("font-size:13px;color:#e5e7eb;line-height:1.8;")
        features_layout.addWidget(features_list)
        
        layout.addWidget(features_box)
        
        layout.addStretch()
        
        # Agreement checkbox
        agreement = QLabel("By installing, you agree to use this software responsibly and in accordance with local laws.")
        agreement.setStyleSheet("font-size:11px;color:#94a3b8;font-style:italic;")
        agreement.setWordWrap(True)
        agreement.setAlignment(Qt.AlignCenter)
        layout.addWidget(agreement)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        cancel_btn = QPushButton("✖ Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color:#64748b;
                color:white;
                padding:12px 30px;
                font-weight:bold;
                font-size:14px;
                border-radius:6px;
            }
            QPushButton:hover {
                background-color:#475569;
            }
        """)
        cancel_btn.clicked.connect(lambda: installer.done(0))
        
        install_btn = QPushButton("✅ Install & Continue")
        install_btn.setStyleSheet("""
            QPushButton {
                background-color:#10b981;
                color:white;
                padding:12px 30px;
                font-weight:bold;
                font-size:14px;
                border-radius:6px;
            }
            QPushButton:hover {
                background-color:#059669;
            }
        """)
        install_btn.clicked.connect(lambda: installer.done(1))
        install_btn.setDefault(True)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(install_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        installer.setLayout(layout)
        installer.setStyleSheet("QDialog{background-color:#0f172a;}QLabel{color:#e5e7eb;}")
        
        result = installer.exec_()
        return result == 1  # True if installed, False if cancelled
    
    def create_app_logo(self):
        """Create Smart Identity Pro logo with icon"""
        width, height = 230, 55
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Draw ID card icon background
        from PyQt5.QtGui import QLinearGradient, QBrush
        gradient = QLinearGradient(0, 0, 50, 55)
        gradient.setColorAt(0, QColor(37, 99, 235))
        gradient.setColorAt(1, QColor(124, 58, 237))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(96, 165, 250), 2))
        painter.drawRoundedRect(2, 2, 50, 50, 8, 8)

        # Icon details
        painter.setPen(QPen(Qt.white, 2))
        painter.drawLine(10, 14, 44, 14)
        painter.drawLine(10, 22, 44, 22)
        painter.drawLine(10, 30, 35, 30)

        # Photo placeholder on icon
        painter.setBrush(QColor(255, 255, 255, 150))
        painter.setPen(QPen(Qt.white, 1))
        painter.drawRect(10, 36, 12, 13)

        # "Smart Identity" text — single clean draw
        painter.setPen(Qt.white)
        font = QFont("Segoe UI", 15, QFont.Bold)
        painter.setFont(font)
        painter.drawText(60, 26, "Smart Identity")

        # "PRO" badge
        badge_x, badge_y, badge_w, badge_h = 60, 31, 36, 16
        painter.setBrush(QColor(96, 165, 250))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 4, 4)

        font2 = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font2)
        painter.setPen(QColor(15, 23, 42))
        painter.drawText(badge_x, badge_y, badge_w, badge_h, Qt.AlignCenter, "PRO")

        painter.end()
        return pixmap

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        top_layout = QHBoxLayout()
        
        # Logo (replaces title text)
        logo_label = QLabel()
        logo_pixmap = self.create_app_logo()
        logo_label.setPixmap(logo_pixmap)
        logo_label.setStyleSheet("background-color:#0f172a;padding:5px;")
        top_layout.addWidget(logo_label)
        
        # Document Type Dropdown
        doc_type_label = QLabel("Document Type:")
        doc_type_label.setStyleSheet("color:#93c5fd;font-weight:bold;")
        top_layout.addWidget(doc_type_label)
        
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems([
            "🪪 Aadhaar Card",
            "🚗 Driving License", 
            "💳 PAN Card",
            "🗳️ Voter ID Card",
            "✨ Custom ID Card"
        ])
        self.doc_type_combo.setStyleSheet("""
            QComboBox {
                background-color:#1e293b;
                border:1px solid #334155;
                border-radius:6px;
                padding:8px;
                color:#e5e7eb;
                min-width:180px;
            }
            QComboBox:hover {
                border-color:#60a5fa;
            }
            QComboBox::drop-down {
                border:none;
            }
            QComboBox::down-arrow {
                image:none;
                border-left:5px solid transparent;
                border-right:5px solid transparent;
                border-top:5px solid #60a5fa;
                width:0;
                height:0;
                margin-right:8px;
            }
            QComboBox QAbstractItemView {
                background-color:#1e293b;
                border:1px solid #334155;
                selection-background-color:#60a5fa;
                color:#e5e7eb;
            }
        """)
        self.doc_type_combo.currentIndexChanged.connect(self.on_doc_type_changed)
        self.current_doc_type = "aadhaar"
        top_layout.addWidget(self.doc_type_combo)
        
        # Custom ID Designer button (only visible when Custom selected)
        self.custom_designer_btn = QPushButton("🎨 Design")
        self.custom_designer_btn.setStyleSheet("QPushButton{background-color:#7c3aed;color:white;font-weight:bold;padding:8px 16px;border-radius:6px;}QPushButton:hover{background-color:#6d28d9;}")
        self.custom_designer_btn.setVisible(False)
        self.custom_designer_btn.clicked.connect(self.open_custom_id_designer)
        top_layout.addWidget(self.custom_designer_btn)
        
        # File selection
        self.file_label = QLabel("No PDF loaded")    
        self.file_label.setStyleSheet("background-color:#1e293b; border:1px solid #4b5563; border-radius:6px; padding:6px; color:#9ca3af;")
        self.file_label.setMaximumWidth(280)
        self.file_label.setMinimumWidth(150)
        top_layout.addWidget(self.file_label)
        
        # Browse button
        browse_btn = QPushButton("📁 Browse PDF")
        browse_btn.clicked.connect(self.browse_pdf)
        top_layout.addWidget(browse_btn)
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("PDF Password (if needed)")
        self.password_input.setMinimumWidth(200)
        self.password_input.setStyleSheet("QLineEdit { background-color:#1e293b; border:1px solid #334155; border-radius:6px; padding:6px; color:#ffffff; } QLineEdit:focus { border-color:#60a5fa; }")
        top_layout.addWidget(self.password_input)
        
        # Load button
        self.load_btn = QPushButton("Load PDF")
        self.load_btn.clicked.connect(self.load_pdf)
        self.load_btn.setStyleSheet("QPushButton{background-color:#2563eb;color:white;font-weight:bold;padding:8px 20px;border-radius:6px;}QPushButton:hover{background-color:#1d4ed8;}")
        top_layout.addWidget(self.load_btn)
        
        main_layout.addLayout(top_layout)

        center_layout = QHBoxLayout()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(250)  # Increased from 200 to 250
        info_label = QLabel("Instructions:")
        info_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd;")
        info_text = QLabel("1. Load a PDF\n2. Select Front/Back\n3. Drag the card to move\n4. Use controls to adjust\n5. Print when ready")
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color:#94a3b8; padding:10px;")
        left_layout.addWidget(info_label)
        left_layout.addWidget(info_text)
        
        # Photo Editor Button
        self.photo_editor_btn = QPushButton("🎨 Photo Editor")
        self.photo_editor_btn.setStyleSheet("QPushButton{background-color:#0891b2;color:white;font-weight:bold;padding:10px;border-radius:6px;margin-top:10px;}QPushButton:hover{background-color:#0e7490;}QPushButton:disabled{background-color:#374151;color:#6b7280;}")
        self.photo_editor_btn.clicked.connect(self.open_photo_editor)
        self.photo_editor_btn.setEnabled(False)
        left_layout.addWidget(self.photo_editor_btn)
        
        # Settings Dropdown Section
        settings_container = QWidget()
        settings_container_layout = QVBoxLayout(settings_container)
        settings_container_layout.setContentsMargins(0, 5, 0, 0)
        settings_container_layout.setSpacing(0)
        
        # Settings Header (clickable to expand/collapse)
        self.settings_header = QPushButton("⚙️ Settings ▼")
        self.settings_header.setCheckable(True)
        self.settings_header.setStyleSheet("""
            QPushButton {
                background-color:#8b5cf6;
                color:white;
                font-weight:bold;
                padding:10px;
                border-radius:6px;
                text-align:left;
                margin-top:5px;
            }
            QPushButton:hover {
                background-color:#7c3aed;
            }
            QPushButton:checked {
                background-color:#6d28d9;
            }
        """)
        settings_container_layout.addWidget(self.settings_header)
        
        # Settings Dropdown Panel (initially hidden)
        self.settings_panel = QWidget()
        self.settings_panel.setStyleSheet("background-color:#1e293b;border:1px solid #334155;border-radius:6px;padding:5px;margin-top:2px;")
        self.settings_panel.setVisible(False)
        settings_panel_layout = QVBoxLayout(self.settings_panel)
        settings_panel_layout.setSpacing(3)
        
        # Quick settings options
        quick_settings_label = QLabel("Quick Settings:")
        quick_settings_label.setStyleSheet("color:#93c5fd;font-weight:bold;font-size:12px;padding:5px;")
        settings_panel_layout.addWidget(quick_settings_label)
        
        # Language dropdown
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        lang_label.setStyleSheet("color:#e5e7eb;font-size:11px;")
        self.quick_language = QComboBox()
        self.quick_language.addItems(['English', 'Hindi', 'Tamil', 'Telugu'])
        self.quick_language.setStyleSheet("QComboBox{background-color:#0f172a;border:1px solid #334155;padding:4px;color:#e5e7eb;font-size:11px;}")
        self.quick_language.currentTextChanged.connect(lambda text: self.update_setting('user_info', 'language', text))
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.quick_language, 1)
        settings_panel_layout.addLayout(lang_layout)
        
        # Font size dropdown
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        font_label.setStyleSheet("color:#e5e7eb;font-size:11px;")
        self.quick_font_size = QComboBox()
        self.quick_font_size.addItems(['Small', 'Medium', 'Large', 'Extra Large'])
        self.quick_font_size.setCurrentText('Large')
        self.quick_font_size.setStyleSheet("QComboBox{background-color:#0f172a;border:1px solid #334155;padding:4px;color:#e5e7eb;font-size:11px;}")
        self.quick_font_size.currentTextChanged.connect(lambda text: self.update_setting('user_info', 'font_size', text))
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.quick_font_size, 1)
        settings_panel_layout.addLayout(font_layout)
        
        # Separator
        sep = QLabel("─" * 25)
        sep.setStyleSheet("color:#334155;font-size:8px;")
        settings_panel_layout.addWidget(sep)
        
        # Advanced Settings Button
        advanced_btn = QPushButton("⚙️ Advanced Settings")
        advanced_btn.setStyleSheet("QPushButton{background-color:#6d28d9;color:white;padding:6px;font-size:11px;border-radius:4px;}QPushButton:hover{background-color:#5b21b6;}")
        advanced_btn.clicked.connect(self.open_settings)
        settings_panel_layout.addWidget(advanced_btn)
        
        settings_container_layout.addWidget(self.settings_panel)
        
        # Toggle panel visibility
        self.settings_header.toggled.connect(lambda checked: self.toggle_settings_panel(checked))
        
        left_layout.addWidget(settings_container)
        
        # Add Print Button
        print_label = QLabel("Export:")
        print_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:20px;")
        
        self.print_card_btn = QPushButton("🖨️ Print Card")
        self.print_card_btn.setStyleSheet("QPushButton{background-color:#7c3aed;color:white;font-weight:bold;padding:12px;border-radius:6px;margin-top:5px;}QPushButton:hover{background-color:#6d28d9;}QPushButton:disabled{background-color:#374151;color:#6b7280;}")
        self.print_card_btn.clicked.connect(lambda: self.print_card('both'))
        self.print_card_btn.setEnabled(False)
        
        left_layout.addWidget(print_label)
        left_layout.addWidget(self.print_card_btn)
        
        # Report Issue Button
        self.report_issue_btn = QPushButton("🐛 Report Issue")
        self.report_issue_btn.setStyleSheet("QPushButton{background-color:#dc2626;color:white;font-weight:bold;padding:10px;border-radius:6px;margin-top:10px;}QPushButton:hover{background-color:#b91c1c;}")
        self.report_issue_btn.clicked.connect(self.report_issue)
        left_layout.addWidget(self.report_issue_btn)
        
        # Product License Button
        self.license_btn = QPushButton("🔑 License")
        self.license_btn.setStyleSheet("QPushButton{background-color:#f59e0b;color:white;font-weight:bold;padding:10px;border-radius:6px;margin-top:5px;}QPushButton:hover{background-color:#d97706;}")
        self.license_btn.clicked.connect(self.show_license_dialog)
        left_layout.addWidget(self.license_btn)
        
        # Help Button
        self.help_btn = QPushButton("❓ Help")
        self.help_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;font-weight:bold;padding:10px;border-radius:6px;margin-top:5px;}QPushButton:hover{background-color:#059669;}")
        self.help_btn.clicked.connect(self.show_help)
        left_layout.addWidget(self.help_btn)
        
        # Add separator
        separator1 = QLabel("─" * 20)
        separator1.setStyleSheet("color:#334155;margin-top:20px;")
        left_layout.addWidget(separator1)
        
        # Text Size Group
        size_label = QLabel("Text Size:")
        size_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:15px;")
        left_layout.addWidget(size_label)
        
        self.size_xlarge_btn = QPushButton("XL")
        self.size_large_btn = QPushButton("L")
        self.size_small_btn = QPushButton("S")
        self.size_xsmall_btn = QPushButton("XS")
        
        size_layout = QGridLayout()
        for i, btn in enumerate([self.size_xlarge_btn, self.size_large_btn, self.size_small_btn, self.size_xsmall_btn]):
            btn.setCheckable(True)
            btn.setStyleSheet("QPushButton{background-color:#1e293b;border:1px solid #334155;border-radius:4px;padding:6px;color:#e5e7eb;}QPushButton:hover{background-color:#334155;border-color:#60a5fa;}QPushButton:checked{background-color:#60a5fa;color:white;}")
            btn.setEnabled(False)
            if i < 2:
                size_layout.addWidget(btn, 0, i)
            else:
                size_layout.addWidget(btn, 1, i-2)
        
        self.size_xlarge_btn.clicked.connect(lambda: self.set_text_size(150))
        self.size_large_btn.clicked.connect(lambda: self.set_text_size(125))
        self.size_small_btn.clicked.connect(lambda: self.set_text_size(75))
        self.size_xsmall_btn.clicked.connect(lambda: self.set_text_size(50))
        
        left_layout.addLayout(size_layout)
        
        # Reset Text Size Button
        self.reset_text_size_btn = QPushButton("↺ Reset Size")
        self.reset_text_size_btn.setStyleSheet("QPushButton{background-color:#dc2626;color:white;border-radius:4px;padding:6px;font-weight:bold;}QPushButton:hover{background-color:#b91c1c;}QPushButton:disabled{background-color:#374151;color:#6b7280;}")
        self.reset_text_size_btn.setEnabled(False)
        self.reset_text_size_btn.clicked.connect(self.reset_text_size)
        left_layout.addWidget(self.reset_text_size_btn)
        
        left_layout.addStretch()

        self.canvas = QGraphicsView()
        self.canvas.setScene(self.scene)
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setRenderHint(QPainter.Antialiasing)
        self.canvas.setRenderHint(QPainter.SmoothPixmapTransform)
        self.canvas.setRenderHint(QPainter.HighQualityAntialiasing)
        self.canvas.setRenderHint(QPainter.TextAntialiasing)
        # Optimize for quality over speed
        self.canvas.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, False)
        self.canvas.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # Set maximum height to prevent hiding bottom controls
        # Make canvas square
        self.canvas.setMaximumHeight(600)
        self.canvas.setMinimumHeight(600)
        self.canvas.setMaximumWidth(600)
        self.canvas.setMinimumWidth(600)
        self.canvas.setStyleSheet("QGraphicsView{background-color:#1e293b;border:2px solid #334155;border-radius:8px;}")

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMaximumWidth(280)

        side_label = QLabel("Select Side")
        side_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd;")
        self.front_radio = QRadioButton("Front Side")
        self.back_radio = QRadioButton("Back Side")
        self.front_radio.setChecked(True)
        self.front_radio.toggled.connect(self.switch_side)
        
        # Create button group for side selection
        self.side_button_group = QButtonGroup(self)
        self.side_button_group.addButton(self.front_radio)
        self.side_button_group.addButton(self.back_radio)
        
        right_layout.addWidget(side_label)
        right_layout.addWidget(self.front_radio)
        right_layout.addWidget(self.back_radio)

        # Control Mode Selection
        mode_label = QLabel("Control Mode")
        mode_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:20px;")
        self.position_mode_radio = QRadioButton("Adjust Card Position")
        self.scale_mode_radio = QRadioButton("Adjust Zoom")
        self.position_mode_radio.setChecked(True)
        self.position_mode_radio.toggled.connect(self.update_control_mode)
        
        # Create separate button group for control mode
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.addButton(self.position_mode_radio)
        self.mode_button_group.addButton(self.scale_mode_radio)
        
        right_layout.addWidget(mode_label)
        right_layout.addWidget(self.position_mode_radio)
        right_layout.addWidget(self.scale_mode_radio)

        pos_label = QLabel("ADJUST CARD")
        pos_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:20px;")
        pos_grid = QGridLayout()
        self.x_input = QSpinBox()
        self.y_input = QSpinBox()
        self.x_input.setRange(-2000, 2000)
        self.y_input.setRange(-2000, 2000)
        self.x_input.valueChanged.connect(self.update_position_from_spinbox)
        self.y_input.valueChanged.connect(self.update_position_from_spinbox)
        pos_grid.addWidget(QLabel("X:"), 0, 0)
        pos_grid.addWidget(self.x_input, 0, 1)
        pos_grid.addWidget(QLabel("Y:"), 1, 0)
        pos_grid.addWidget(self.y_input, 1, 1)
        right_layout.addWidget(pos_label)
        right_layout.addLayout(pos_grid)

        scale_label = QLabel("ADJUST ZOOM")
        scale_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:20px;")
        scale_grid = QGridLayout()
        self.scale_x = QSpinBox()
        self.scale_y = QSpinBox()
        self.scale_x.setRange(0, 500)
        self.scale_y.setRange(0, 500)
        # FIX: initial value should be 100 (= 100%), not 0
        self.scale_x.setValue(100)
        self.scale_y.setValue(100)
        self.scale_x.setSuffix("%")
        self.scale_y.setSuffix("%")
        self.scale_x.valueChanged.connect(self.update_scale)
        self.scale_y.valueChanged.connect(self.update_scale)
        # FIX: corrected grid column indices (was 10, should be 1)
        scale_grid.addWidget(QLabel("XZ:"), 0, 0)
        scale_grid.addWidget(self.scale_x, 0, 1)
        scale_grid.addWidget(QLabel("YZ:"), 1, 0)
        scale_grid.addWidget(self.scale_y, 1, 1)
        right_layout.addWidget(scale_label)
        right_layout.addLayout(scale_grid)

        move_label = QLabel("Arrow Controls")
        move_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:20px;")
        up_btn = QPushButton("↑")
        down_btn = QPushButton("↓")
        left_btn = QPushButton("←")
        right_btn = QPushButton("→")
        btn_style = "QPushButton{background-color:#facc15;border-radius:25px;font-size:20px;font-weight:bold;color:#1f2937;border:2px solid #eab308;}QPushButton:hover{background-color:#fde047;}QPushButton:pressed{background-color:#eab308;}"
        for btn in [up_btn, down_btn, left_btn, right_btn]:
            btn.setFixedSize(50, 50)
            btn.setStyleSheet(btn_style)
        move_grid = QGridLayout()
        move_grid.setSpacing(0)
        move_grid.setColumnMinimumWidth(0, 55)   # left button column
        move_grid.setColumnMinimumWidth(1, 55)   # center column
        move_grid.setColumnMinimumWidth(2, 55)   # right button column
        move_grid.setRowMinimumHeight(0, 55)     # top button row
        move_grid.setRowMinimumHeight(1, 55)     # middle row
        move_grid.setRowMinimumHeight(2, 55)     # bottom button row
        move_grid.setContentsMargins(20, 10, 20, 10)
        move_grid.addWidget(up_btn, 0, 1, Qt.AlignCenter)
        move_grid.addWidget(left_btn, 1, 0, Qt.AlignCenter)
        move_grid.addWidget(right_btn, 1, 2, Qt.AlignCenter)
        move_grid.addWidget(down_btn, 2, 1, Qt.AlignCenter)
        up_btn.clicked.connect(lambda: self.nudge_control(0, -1))
        down_btn.clicked.connect(lambda: self.nudge_control(0, 1))
        left_btn.clicked.connect(lambda: self.nudge_control(-1, 0))
        right_btn.clicked.connect(lambda: self.nudge_control(1, 0))
        
        # Add description label for arrow buttons
        self.arrow_desc_label = QLabel("↑↓ Move Up/Down\n←→ Move Left/Right")
        self.arrow_desc_label.setStyleSheet("color:#94a3b8; font-size:11px; margin-top:5px;")
        self.arrow_desc_label.setAlignment(Qt.AlignCenter)
        
        right_layout.addWidget(move_label)

        # Wrap grid in a fixed container so it doesn't stretch on maximize
        arrow_container = QWidget()
        arrow_container.setFixedWidth(180)
        arrow_container_layout = QVBoxLayout(arrow_container)
        arrow_container_layout.setContentsMargins(0, 0, 0, 0)
        arrow_container_layout.addLayout(move_grid)

        arrow_wrapper = QHBoxLayout()
        arrow_wrapper.addStretch()
        arrow_wrapper.addWidget(arrow_container)
        arrow_wrapper.addStretch()
        right_layout.addLayout(arrow_wrapper)
        right_layout.addWidget(self.arrow_desc_label)

        zoom_label = QLabel("Canvas Zoom")
        zoom_label.setStyleSheet("font-weight:bold; font-size:14px; color:#93c5fd; margin-top:20px;")
        zoom_in = QPushButton("🔍 Zoom In")
        zoom_out = QPushButton("🔍 Zoom Out")
        zoom_reset = QPushButton("🔄 Reset")
        zoom_in.clicked.connect(lambda: self.canvas.scale(1.2, 1.2))
        zoom_out.clicked.connect(lambda: self.canvas.scale(0.8, 0.8))
        zoom_reset.clicked.connect(self.reset_view)
        right_layout.addWidget(zoom_label)
        right_layout.addWidget(zoom_in)
        right_layout.addWidget(zoom_out)
        right_layout.addWidget(zoom_reset)

        reset_btn = QPushButton("↺ Reset Position")
        reset_btn.setStyleSheet("QPushButton{background-color:#dc2626;color:white;font-weight:bold;padding:10px;border-radius:6px;margin-top:20px;}QPushButton:hover{background-color:#b91c1c;}")
        reset_btn.clicked.connect(self.reset_data_position)
        right_layout.addWidget(reset_btn)
        right_layout.addStretch()

        center_layout.addWidget(left_panel)
        center_layout.addWidget(self.canvas, 1)
        center_layout.addWidget(right_panel)
        main_layout.addLayout(center_layout)
        
        # Bottom status bar only
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color:#94a3b8; padding:5px;")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        
        main_layout.addLayout(bottom_layout)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color:#0f172a; font-family:'Segoe UI',Arial; font-size:13px; color:#e5e7eb; }
            QLabel { color:#e5e7eb; }
            QPushButton { background-color:#1e293b; border:1px solid #334155; border-radius:6px; padding:8px 16px; color:#e5e7eb; }
            QPushButton:hover { background-color:#334155; border-color:#60a5fa; }
            QPushButton:pressed { background-color:#0f172a; }
            QLineEdit, QSpinBox { background-color:#1e293b; border:1px solid #334155; border-radius:6px; padding:6px; color:#e5e7eb; }
            QLineEdit:focus, QSpinBox:focus { border-color:#60a5fa; }
            QRadioButton { color:#e5e7eb; spacing:8px; }
            QWidget { background-color:#0f172a; }
        """)

    def setup_loading_overlay(self):
        """Create a loading overlay widget"""
        self.loading_overlay = QWidget(self)
        self.loading_overlay.setStyleSheet("background-color: rgba(15, 23, 42, 220);")
        self.loading_overlay.hide()
        
        overlay_layout = QVBoxLayout(self.loading_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        
        # Loading spinner (using text for simplicity)
        self.loading_label = QLabel("⏳ Loading PDF...")
        self.loading_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #60a5fa;
            background-color: #1e293b;
            padding: 30px 50px;
            border-radius: 12px;
            border: 2px solid #334155;
        """)
        self.loading_label.setAlignment(Qt.AlignCenter)
        
        overlay_layout.addWidget(self.loading_label)
    
    def show_loading(self, message="⏳ Loading PDF..."):
        """Show loading overlay with custom message"""
        self.loading_label.setText(message)
        self.loading_overlay.setGeometry(0, 0, self.width(), self.height())
        self.loading_overlay.raise_()
        self.loading_overlay.show()
        QApplication.processEvents()
    
    def hide_loading(self):
        """Hide loading overlay"""
        self.loading_overlay.hide()
    
    def resizeEvent(self, event):
        """Ensure loading overlay covers the entire window when resized"""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.setGeometry(0, 0, self.width(), self.height())

    def browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF File", "", "PDF Files (*.pdf)")
        if path:
            self.pdf_path = path
            self.file_label.setText(path.split("/")[-1])
            self.status_label.setText(f"Selected: {path.split('/')[-1]}")

    def load_pdf(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "No PDF", "Please select a PDF file first!")
            return
        try:
            self.show_loading("⏳ Loading PDF...")
            self.status_label.setText("Loading PDF...")
            QApplication.processEvents()

            self.doc = fitz.open(self.pdf_path)
            if self.doc.needs_pass:
                pwd = self.password_input.text()
                if not pwd or not self.doc.authenticate(pwd):
                    QMessageBox.critical(self, "Error", "Wrong or missing password!")
                    return

            self.scene.clear()
            page = self.doc.load_page(0)
            pw, ph = page.rect.width, page.rect.height


            F_BG  = (0.05,   0.68,   0.5,    0.87  )  # bg   (x0,y0,x1,y1)
            F_TXT = (0.1911, 0.7156, 0.3915, 0.7629)  # text (x0,y0,x1,y1)  ← FIXED

            front_full_pix = page.get_pixmap(dpi=300, clip=fitz.Rect(pw*F_BG[0], ph*F_BG[1], pw*F_BG[2], ph*F_BG[3]))
            front_full_img = self.pixmap_to_qimage(front_full_pix)
            fbw, fbh = front_full_pix.width, front_full_pix.height  # bg pixmap pixel size

            # Store original
            self.front_bg_original = QPixmap.fromImage(front_full_img)
            
            # Calculate text region position
            ftx = int((F_TXT[0]-F_BG[0]) / (F_BG[2]-F_BG[0]) * fbw)
            fty = int((F_TXT[1]-F_BG[1]) / (F_BG[3]-F_BG[1]) * fbh)
            ftw = int((F_TXT[2]-F_TXT[0]) / (F_BG[2]-F_BG[0]) * fbw)
            fth = int((F_TXT[3]-F_TXT[1]) / (F_BG[3]-F_BG[1]) * fbh)
            
            # Layer 1 (bottom, z=1): Full background with white blanked area
            front_bg_with_blank = self.front_bg_original.copy()
            painter = QPainter(front_bg_with_blank)
            painter.fillRect(ftx, fty, ftw, fth, Qt.white)
            painter.end()
            
            self.front_bg_item = QGraphicsPixmapItem(front_bg_with_blank)
            self.front_bg_item.setZValue(1)
            self.front_bg_item.setPos(0, 0)
            self.front_bg_item.setTransformationMode(Qt.SmoothTransformation)
            self.scene.addItem(self.front_bg_item)
            
            # Layer 2 (middle, z=5): Draggable text - goes UNDER the mask layer
            front_text_pix = page.get_pixmap(dpi=300, clip=fitz.Rect(pw*F_TXT[0], ph*F_TXT[1], pw*F_TXT[2], ph*F_TXT[3]))
            self.front_data_original = QPixmap.fromImage(self.pixmap_to_qimage(front_text_pix))
            self.front_data_item = DraggablePixmapItem(self.front_data_original.copy(), self)
            self.front_data_item.setZValue(5)
            self.front_data_item.setPos(ftx, fty)
            self.front_data_initial_pos = QPointF(ftx, fty)
            self.scene.addItem(self.front_data_item)
            
            front_mask = QPixmap(self.front_bg_original.size())
            front_mask.fill(Qt.transparent)
            mask_painter = QPainter(front_mask)
            # Draw the original image EXCEPT the text area
            mask_painter.drawPixmap(0, 0, self.front_bg_original)
            # Cut out the text area to create a "window"
            mask_painter.setCompositionMode(QPainter.CompositionMode_Clear)
            mask_painter.fillRect(ftx, fty, ftw, fth, Qt.transparent)
            mask_painter.end()
            
            self.front_blank_item = QGraphicsPixmapItem(front_mask)
            self.front_blank_item.setZValue(10)
            self.front_blank_item.setPos(0, 0)
            self.front_blank_item.setTransformationMode(Qt.SmoothTransformation)
            self.scene.addItem(self.front_blank_item)

            # ── BACK CARD ───────────────────────────────────────────────
            # B_BG:  the full back card area in the PDF
            # B_TXT: the address text block within the back card  ← FIXED
            B_BG  = (0.5,    0.68,   0.94,    0.87  )  # bg
            B_TXT = (0.5198, 0.7104, 0.7648, 0.8246)  # text  ← FIXED

            back_full_pix = page.get_pixmap(dpi=300, clip=fitz.Rect(pw*B_BG[0], ph*B_BG[1], pw*B_BG[2], ph*B_BG[3]))
            back_full_img = self.pixmap_to_qimage(back_full_pix)
            bbw, bbh = back_full_pix.width, back_full_pix.height

            # Store original
            self.back_bg_original = QPixmap.fromImage(back_full_img)
            
            # Calculate text region position
            btx = int((B_TXT[0]-B_BG[0]) / (B_BG[2]-B_BG[0]) * bbw)
            bty = int((B_TXT[1]-B_BG[1]) / (B_BG[3]-B_BG[1]) * bbh)
            btw = int((B_TXT[2]-B_TXT[0]) / (B_BG[2]-B_BG[0]) * bbw)
            bth = int((B_TXT[3]-B_TXT[1]) / (B_BG[3]-B_BG[1]) * bbh)
            
            # Layer 1 (bottom, z=1): Full background with white blanked area
            back_bg_with_blank = self.back_bg_original.copy()
            painter = QPainter(back_bg_with_blank)
            painter.fillRect(btx, bty, btw, bth, Qt.white)
            painter.end()
            
            self.back_bg_item = QGraphicsPixmapItem(back_bg_with_blank)
            self.back_bg_item.setZValue(1)
            self.back_bg_item.setPos(0, 0)
            self.back_bg_item.setVisible(False)
            self.back_bg_item.setTransformationMode(Qt.SmoothTransformation)
            self.scene.addItem(self.back_bg_item)
            
            # Layer 2 (middle, z=5): Draggable text - goes UNDER the mask layer
            back_text_pix = page.get_pixmap(dpi=300, clip=fitz.Rect(pw*B_TXT[0], ph*B_TXT[1], pw*B_TXT[2], ph*B_TXT[3]))
            self.back_data_original = QPixmap.fromImage(self.pixmap_to_qimage(back_text_pix))
            self.back_data_item = DraggablePixmapItem(self.back_data_original.copy(), self)
            self.back_data_item.setZValue(5)
            self.back_data_item.setPos(btx, bty)
            self.back_data_initial_pos = QPointF(btx, bty)
            self.back_data_item.setVisible(False)
            self.scene.addItem(self.back_data_item)
            
            # Layer 3 (top, z=10): Transparent overlay with ONLY the text cutout region preserved
            back_mask = QPixmap(self.back_bg_original.size())
            back_mask.fill(Qt.transparent)
            mask_painter = QPainter(back_mask)
            # Draw the original image EXCEPT the text area
            mask_painter.drawPixmap(0, 0, self.back_bg_original)
            # Cut out the text area to create a "window"
            mask_painter.setCompositionMode(QPainter.CompositionMode_Clear)
            mask_painter.fillRect(btx, bty, btw, bth, Qt.transparent)
            mask_painter.end()
            
            self.back_blank_item = QGraphicsPixmapItem(back_mask)
            self.back_blank_item.setZValue(10)
            self.back_blank_item.setPos(0, 0)
            self.back_blank_item.setVisible(False)
            self.back_blank_item.setTransformationMode(Qt.SmoothTransformation)
            self.scene.addItem(self.back_blank_item)

            self.scene.setSceneRect(self.front_bg_item.boundingRect())
            # Reset canvas transform to show at normal size
            self.canvas.resetTransform()
            # Scale down to 50% since we're using 300 DPI (2x the original 150 DPI)
            # This gives us HD quality while displaying at normal size
            self.canvas.scale(0.5, 0.5)
            # Center the view on the scene
            self.canvas.centerOn(self.scene.sceneRect().center())
            self.pdf_loaded = True
            self.update_spinboxes_from_item()
            
            # Enable buttons
            self.print_card_btn.setEnabled(True)
            self.photo_editor_btn.setEnabled(True)
            self.size_xlarge_btn.setEnabled(True)
            self.size_large_btn.setEnabled(True)
            self.size_small_btn.setEnabled(True)
            self.size_xsmall_btn.setEnabled(True)
            self.reset_text_size_btn.setEnabled(True)
            
            self.hide_loading()
            self.status_label.setText("PDF loaded! Use Front/Back buttons to switch sides.")

        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Error", f"Failed to load PDF:\n{str(e)}")
            self.status_label.setText("Error loading PDF")

    def pixmap_to_qimage(self, pix):
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888)
        return img.copy()

    def switch_side(self):
        if not self.pdf_loaded:
            return
        is_front = self.front_radio.isChecked()
        for item, vis in [(self.front_data_item, is_front), (self.back_data_item, not is_front),
                          (self.front_bg_item,   is_front), (self.back_bg_item,   not is_front),
                          (self.front_blank_item, is_front), (self.back_blank_item, not is_front)]:
            if item:
                item.setVisible(vis)
        active_bg = self.front_bg_item if is_front else self.back_bg_item
        if active_bg:
            self.scene.setSceneRect(active_bg.boundingRect())
            # Center on the active card - maintain current zoom level
            self.canvas.centerOn(active_bg.boundingRect().center())
        self.update_spinboxes_from_item()
        self.status_label.setText(f"Showing {'Front' if is_front else 'Back'} side")

    def get_active_data_item(self):
        return self.front_data_item if self.front_radio.isChecked() else self.back_data_item

    def get_initial_pos_for_item(self, item):
        """Get the initial position for a given item"""
        if item == self.front_data_item and hasattr(self, 'front_data_initial_pos'):
            return self.front_data_initial_pos
        elif item == self.back_data_item and hasattr(self, 'back_data_initial_pos'):
            return self.back_data_initial_pos
        return QPointF(0, 0)

    def update_spinboxes_from_item(self):
        if not self.pdf_loaded:
            return
        item = self.get_active_data_item()
        if item:
            initial_pos = self.get_initial_pos_for_item(item)
            self.x_input.blockSignals(True); self.y_input.blockSignals(True)
            # Display relative coordinates
            self.x_input.setValue(int(item.x() - initial_pos.x()))
            self.y_input.setValue(int(item.y() - initial_pos.y()))
            self.x_input.blockSignals(False); self.y_input.blockSignals(False)
            t = item.transform()
            self.scale_x.blockSignals(True); self.scale_y.blockSignals(True)
            sx = int(t.m11() * 100) if t.m11() > 0 else 100
            sy = int(t.m22() * 100) if t.m22() > 0 else 100
            self.scale_x.setValue(sx)
            self.scale_y.setValue(sy)
            self.scale_x.blockSignals(False); self.scale_y.blockSignals(False)

    def update_position_from_spinbox(self):
        if not self.pdf_loaded:
            return
        item = self.get_active_data_item()
        if item:
            initial_pos = self.get_initial_pos_for_item(item)
            # Convert relative coordinates to absolute position
            new_x = initial_pos.x() + self.x_input.value()
            new_y = initial_pos.y() + self.y_input.value()
            item.setPos(new_x, new_y)

    def update_control_mode(self):
        """Update the description label when control mode changes"""
        if self.position_mode_radio.isChecked():
            self.arrow_desc_label.setText("↑↓ Move Up/Down\n←→ Move Left/Right")
            self.status_label.setText("Arrow buttons: Move position")
        else:
            self.arrow_desc_label.setText("↑ Zoom In  ↓ Zoom Out\n← X Scale-  → X Scale+")
            self.status_label.setText("Arrow buttons: Adjust zoom (↑↓ uniform, ←→ X-axis only)")

    def nudge_control(self, dx, dy):
        """Unified control method - moves position OR adjusts scale based on mode"""
        if not self.pdf_loaded:
            return
            
        item = self.get_active_data_item()
        if not item:
            self.status_label.setText("Error: No active item found")
            return
            
        if self.position_mode_radio.isChecked():
            # Position mode: move the item
            item.setPos(item.pos().x() + dx, item.pos().y() + dy)
            self.update_spinboxes_from_item()
        else:
            # Scale mode: adjust zoom
            scale_step = 5  # 5% per button press
            
            if dy != 0:  # Up/Down arrows: UNIFORM scaling (both X and Y together)
                # Up (dy=-1) means zoom in (increase scale)
                # Down (dy=+1) means zoom out (decrease scale)
                delta = -dy * scale_step  # Invert dy so up is positive
                new_scale_x = self.scale_x.value() + delta
                new_scale_y = self.scale_y.value() + delta
                self.scale_x.setValue(max(1, min(500, new_scale_x)))
                self.scale_y.setValue(max(1, min(500, new_scale_y)))
                
            if dx != 0:  # Left/Right arrows: X-axis scaling only
                # Left (dx=-1) decreases X scale
                # Right (dx=+1) increases X scale
                new_scale_x = self.scale_x.value() + (dx * scale_step)
                self.scale_x.setValue(max(1, min(500, new_scale_x)))

    def nudge(self, dx, dy):
        """Legacy position nudge method - kept for compatibility"""
        item = self.get_active_data_item()
        if item:
            item.setPos(item.pos().x() + dx, item.pos().y() + dy)
            self.update_spinboxes_from_item()

    def update_scale(self):
        if not self.pdf_loaded:
            return
        item = self.get_active_data_item()
        if item:
            sx = max(self.scale_x.value(), 1)  # prevent 0-scale (invisible)
            sy = max(self.scale_y.value(), 1)
            t = QTransform()
            t.scale(sx / 100.0, sy / 100.0)
            item.setTransform(t)

    def reset_data_position(self):
        if self.front_radio.isChecked() and self.front_data_item:
            self.front_data_item.setPos(self.front_data_initial_pos)
            self.front_data_item.setTransform(QTransform())
        elif self.back_data_item:
            self.back_data_item.setPos(self.back_data_initial_pos)
            self.back_data_item.setTransform(QTransform())
        # FIX: reset to 100 (= 100%), matching identity transform
        self.scale_x.setValue(100)
        self.scale_y.setValue(100)
        self.update_spinboxes_from_item()
        self.status_label.setText("Position reset to original")

    def reset_view(self):
        self.canvas.resetTransform()
        active_bg = self.front_bg_item if self.front_radio.isChecked() else self.back_bg_item
        if active_bg:
            # Fit to view with some padding for better viewing
            self.canvas.fitInView(active_bg.boundingRect(), Qt.KeepAspectRatio)
            # Scale to 42.5% (85% of 50%) to fit nicely with margins for 300 DPI content
            self.canvas.scale(0.425, 0.425)
    
    def check_license_on_start(self):
        """Check license status when app starts"""
        if self.is_demo:
            QMessageBox.information(self, "Demo Version", 
                f"Welcome to Smart Identity Pro!\n\n"
                f"You are using the DEMO version.\n"
                f"Remaining uses: {self.uses_left}\n\n"
                f"Click 'License' to purchase the full version.")
    
    def check_demo_usage(self):
        """Check if demo uses are remaining"""
        if self.is_demo:
            if self.uses_left <= 0:
                QMessageBox.warning(self, "Demo Expired", 
                    "Your demo period has ended.\n\n"
                    "Please purchase a license to continue using Smart Identity Pro.\n"
                    "Click the 'License' button to buy now.")
                return False
            self.uses_left -= 1
            self.status_label.setText(f"Demo uses left: {self.uses_left}")
        return True
    
    def show_license_dialog(self):
        """Show license purchase/activation dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Product License")
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QVBoxLayout()
        
        if self.is_demo:
            title = QLabel("Smart Identity Pro - DEMO VERSION")
            title.setStyleSheet("font-size:16px;font-weight:bold;color:#60a5fa;")
            title.setAlignment(Qt.AlignCenter)
            
            info = QLabel(f"Remaining demo uses: {self.uses_left}/5\n\n"
                         "Purchase a license for unlimited access!")
            info.setStyleSheet("color:#e5e7eb;padding:20px;")
            info.setWordWrap(True)
            
            license_input = QLineEdit()
            license_input.setPlaceholderText("Enter License Key")
            license_input.setStyleSheet("padding:8px;")
            
            activate_btn = QPushButton("Activate License")
            activate_btn.setStyleSheet("background-color:#10b981;color:white;padding:10px;font-weight:bold;")
            activate_btn.clicked.connect(lambda: self.activate_license(license_input.text(), dialog))
            
            buy_btn = QPushButton("Buy License ($49.99)")
            buy_btn.setStyleSheet("background-color:#7c3aed;color:white;padding:10px;font-weight:bold;")
            buy_btn.clicked.connect(lambda: QMessageBox.information(dialog, "Purchase", "Visit: www.smartidentitypro.com/buy"))
            
            layout.addWidget(title)
            layout.addWidget(info)
            layout.addWidget(license_input)
            layout.addWidget(activate_btn)
            layout.addWidget(buy_btn)
        else:
            title = QLabel("✓ Licensed Version")
            title.setStyleSheet("font-size:18px;font-weight:bold;color:#10b981;")
            title.setAlignment(Qt.AlignCenter)
            
            info = QLabel("Your product is fully licensed!\nThank you for your purchase.")
            info.setStyleSheet("color:#e5e7eb;padding:20px;")
            info.setAlignment(Qt.AlignCenter)
            
            layout.addWidget(title)
            layout.addWidget(info)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def activate_license(self, key, dialog):
        """Activate license with key"""
        # Simple validation (in real app, validate with server)
        if key.upper() == "SMART-IDENTITY-2026":
            self.is_demo = False
            self.uses_left = -1
            QMessageBox.information(dialog, "Success", "License activated successfully!")
            dialog.close()
            self.status_label.setText("Licensed Version")
        else:
            QMessageBox.warning(dialog, "Invalid Key", "The license key is invalid.")
    
    def on_doc_type_changed(self, index):
        """Handle document type dropdown change"""
        type_map = {
            0: "aadhaar",
            1: "driving",
            2: "pan",
            3: "voter",
            4: "custom"
        }
        
        self.current_doc_type = type_map.get(index, "aadhaar")
        
        # Show custom designer button only for custom type
        self.custom_designer_btn.setVisible(index == 4)
        
        # Update status
        type_names = [
            "Aadhaar Card",
            "Driving License",
            "PAN Card",
            "Voter ID Card",
            "Custom ID Card"
        ]
        if 0 <= index < len(type_names):
            self.status_label.setText(f"Selected: {type_names[index]}")
    
    def open_custom_id_designer(self):
        """Open custom ID card designer dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom ID Card Designer")
        dialog.setModal(True)
        dialog.resize(900, 700)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("✨ Custom Identity Card Designer")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#60a5fa;padding:10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Main content in scroll area
        from PyQt5.QtWidgets import QScrollArea, QFormLayout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background-color:#1e293b;border:2px solid #334155;border-radius:8px;}")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Card Type Selection
        type_group = QGroupBox("Card Type")
        type_group.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:10px;margin-top:10px;}")
        type_layout = QHBoxLayout()
        
        employee_radio = QRadioButton("👔 Employee ID")
        student_radio = QRadioButton("🎓 Student ID")
        college_radio = QRadioButton("🏫 College ID")
        generic_radio = QRadioButton("📇 Generic ID")
        
        employee_radio.setChecked(True)
        for radio in [employee_radio, student_radio, college_radio, generic_radio]:
            radio.setStyleSheet("QRadioButton{color:#e5e7eb;padding:5px;}")
            type_layout.addWidget(radio)
        
        type_group.setLayout(type_layout)
        content_layout.addWidget(type_group)
        
        # Card Information Form
        info_group = QGroupBox("Card Information")
        info_group.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:10px;margin-top:10px;}")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        org_name = QLineEdit()
        org_name.setPlaceholderText("e.g., ABC Corporation / XYZ University")
        
        card_holder_name = QLineEdit()
        card_holder_name.setPlaceholderText("Full name of card holder")
        
        id_number = QLineEdit()
        id_number.setPlaceholderText("Employee/Student ID number")
        
        designation = QLineEdit()
        designation.setPlaceholderText("e.g., Software Engineer / 3rd Year CS")
        
        department = QLineEdit()
        department.setPlaceholderText("e.g., IT Department / Computer Science")
        
        valid_from = QLineEdit()
        valid_from.setPlaceholderText("DD/MM/YYYY")
        
        valid_till = QLineEdit()
        valid_till.setPlaceholderText("DD/MM/YYYY")
        
        blood_group = QLineEdit()
        blood_group.setPlaceholderText("e.g., A+, B+, O+")
        
        contact = QLineEdit()
        contact.setPlaceholderText("Phone number")
        
        # Style all input fields
        for field in [org_name, card_holder_name, id_number, designation, department, valid_from, valid_till, blood_group, contact]:
            field.setStyleSheet("QLineEdit{background-color:#0f172a;border:1px solid #334155;border-radius:4px;padding:8px;color:#e5e7eb;}")
        
        form_layout.addRow("Organization/College:", org_name)
        form_layout.addRow("Card Holder Name:", card_holder_name)
        form_layout.addRow("ID Number:", id_number)
        form_layout.addRow("Designation/Course:", designation)
        form_layout.addRow("Department:", department)
        form_layout.addRow("Valid From:", valid_from)
        form_layout.addRow("Valid Till:", valid_till)
        form_layout.addRow("Blood Group:", blood_group)
        form_layout.addRow("Emergency Contact:", contact)
        
        info_group.setLayout(form_layout)
        content_layout.addWidget(info_group)
        
        # Photo Upload
        photo_group = QGroupBox("Cardholder Photo")
        photo_group.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:10px;margin-top:10px;}")
        photo_layout = QVBoxLayout()
        
        self.photo_label = QLabel("No photo selected")
        self.photo_label.setStyleSheet("border:2px dashed #334155;padding:20px;background-color:#0f172a;border-radius:6px;color:#94a3b8;")
        self.photo_label.setAlignment(Qt.AlignCenter)
        self.photo_label.setMinimumHeight(150)
        
        photo_btn = QPushButton("📸 Upload Photo")
        photo_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;padding:10px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#059669;}")
        photo_btn.clicked.connect(lambda: self.upload_custom_photo(self.photo_label))
        
        photo_layout.addWidget(self.photo_label)
        photo_layout.addWidget(photo_btn)
        photo_group.setLayout(photo_layout)
        content_layout.addWidget(photo_group)
        
        # Design Options
        design_group = QGroupBox("Design Customization")
        design_group.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:10px;margin-top:10px;}")
        design_layout = QVBoxLayout()
        
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Accent Color:"))
        color_combo = QComboBox()
        color_combo.addItems(["Blue", "Green", "Red", "Purple", "Orange", "Teal"])
        color_combo.setStyleSheet("QComboBox{background-color:#0f172a;border:1px solid #334155;padding:6px;color:#e5e7eb;}")
        color_layout.addWidget(color_combo)
        color_layout.addStretch()
        
        logo_btn = QPushButton("🏢 Upload Logo")
        logo_btn.setStyleSheet("QPushButton{background-color:#3b82f6;color:white;padding:8px 16px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#2563eb;}")
        color_layout.addWidget(logo_btn)
        
        design_layout.addLayout(color_layout)
        design_group.setLayout(design_layout)
        content_layout.addWidget(design_group)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        preview_btn = QPushButton("👁️ Preview Card")
        preview_btn.setStyleSheet("QPushButton{background-color:#7c3aed;color:white;padding:12px 30px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#6d28d9;}")
        preview_btn.clicked.connect(lambda: self.preview_custom_id({
            'card_type': 'Employee' if employee_radio.isChecked() else 'Student' if student_radio.isChecked() else 'College' if college_radio.isChecked() else 'Generic',
            'org_name': org_name.text(),
            'holder_name': card_holder_name.text(),
            'id_number': id_number.text(),
            'designation': designation.text(),
            'department': department.text(),
            'valid_from': valid_from.text(),
            'valid_till': valid_till.text(),
            'blood_group': blood_group.text(),
            'contact': contact.text(),
            'photo': self.photo_label.pixmap() if self.photo_label.pixmap() else None,
            'color': color_combo.currentText()
        }))
        
        generate_btn = QPushButton("✅ Generate ID Card")
        generate_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;padding:12px 30px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#059669;}")
        generate_btn.clicked.connect(lambda: self.generate_custom_id({
            'card_type': 'Employee' if employee_radio.isChecked() else 'Student' if student_radio.isChecked() else 'College' if college_radio.isChecked() else 'Generic',
            'org_name': org_name.text(),
            'holder_name': card_holder_name.text(),
            'id_number': id_number.text(),
            'designation': designation.text(),
            'department': department.text(),
            'valid_from': valid_from.text(),
            'valid_till': valid_till.text(),
            'blood_group': blood_group.text(),
            'contact': contact.text(),
            'photo': self.photo_label.pixmap() if self.photo_label.pixmap() else None,
            'color': color_combo.currentText()
        }, dialog))
        
        cancel_btn = QPushButton("✖ Cancel")
        cancel_btn.setStyleSheet("QPushButton{background-color:#64748b;color:white;padding:12px 30px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#475569;}")
        cancel_btn.clicked.connect(dialog.close)
        
        button_layout.addStretch()
        button_layout.addWidget(preview_btn)
        button_layout.addWidget(generate_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog{background-color:#0f172a;}QLabel{color:#e5e7eb;}")
        dialog.exec_()
    
    def upload_custom_photo(self, label):
        """Upload photo for custom ID card"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Photo", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled)
                label.setText("")
            else:
                QMessageBox.warning(self, "Error", "Failed to load image")
    
    def preview_custom_id(self, data):
        """Show preview of custom ID card"""
        # Validate required fields
        if not data['holder_name']:
            QMessageBox.warning(self, "Missing Information", "Please enter the card holder's name!")
            return
        if not data['org_name']:
            QMessageBox.warning(self, "Missing Information", "Please enter the organization/college name!")
            return
        
        # Create preview dialog
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("ID Card Preview")
        preview_dialog.setModal(True)
        preview_dialog.resize(700, 900)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"👁️ Preview - {data['card_type']} ID Card")
        title.setStyleSheet("font-size:18px;font-weight:bold;color:#60a5fa;padding:10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Generate the card pixmap
        card_pixmap = self.create_id_card_pixmap(data)
        
        # Display card
        card_label = QLabel()
        card_label.setPixmap(card_pixmap)
        card_label.setAlignment(Qt.AlignCenter)
        card_label.setStyleSheet("background-color:#1e293b;padding:20px;border-radius:8px;")
        layout.addWidget(card_label)
        
        # Close button
        close_btn = QPushButton("Close Preview")
        close_btn.setStyleSheet("QPushButton{background-color:#64748b;color:white;padding:10px 30px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#475569;}")
        close_btn.clicked.connect(preview_dialog.close)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
        preview_dialog.setLayout(layout)
        preview_dialog.setStyleSheet("QDialog{background-color:#0f172a;}")
        preview_dialog.exec_()
    
    def generate_custom_id(self, data, parent_dialog):
        """Generate and save custom ID card"""
        # Validate required fields
        if not data['holder_name']:
            QMessageBox.warning(self, "Missing Information", "Please enter the card holder's name!")
            return
        if not data['org_name']:
            QMessageBox.warning(self, "Missing Information", "Please enter the organization/college name!")
            return
        
        # Ask where to save
        default_name = f"{data['holder_name'].replace(' ', '_')}_ID_Card.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ID Card",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg);;PDF File (*.pdf)"
        )
        
        if not file_path:
            return
        
        try:
            # Generate the card
            card_pixmap = self.create_id_card_pixmap(data)
            
            # Save based on extension
            if file_path.lower().endswith('.pdf'):
                # Save as PDF
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(file_path)
                printer.setPageSize(QPrinter.A4)
                
                painter = QPainter(printer)
                # Center the card on A4 page
                page_rect = printer.pageRect()
                x = (page_rect.width() - card_pixmap.width()) / 2
                y = (page_rect.height() - card_pixmap.height()) / 2
                painter.drawPixmap(int(x), int(y), card_pixmap)
                painter.end()
            else:
                # Save as image
                card_pixmap.save(file_path)
            
            QMessageBox.information(self, "Success", f"ID Card saved successfully to:\n{file_path}")
            parent_dialog.close()
            self.status_label.setText("Custom ID Card generated successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save ID card:\n{str(e)}")
    
    def create_id_card_pixmap(self, data):
        """Create the actual ID card pixmap with all information"""
        # Standard ID card size: 3.375" x 2.125" at 300 DPI
        width, height = 1012, 638  # pixels at 300 DPI
        
        # Create card
        card = QPixmap(width, height)
        card.fill(Qt.white)
        
        painter = QPainter(card)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # Color mapping
        color_map = {
            'Blue': QColor(37, 99, 235),
            'Green': QColor(16, 185, 129),
            'Red': QColor(220, 38, 38),
            'Purple': QColor(124, 58, 237),
            'Orange': QColor(249, 115, 22),
            'Teal': QColor(20, 184, 166)
        }
        accent_color = color_map.get(data['color'], QColor(37, 99, 235))
        
        # Draw header band
        painter.fillRect(0, 0, width, 120, accent_color)
        
        # Organization name
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(24)
        font.setWeight(75)  # Bold
        painter.setFont(font)
        painter.drawText(20, 25, width-40, 40, Qt.AlignCenter, data['org_name'])
        
        # Card type
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(20, 70, width-40, 30, Qt.AlignCenter, f"{data['card_type']} ID CARD")
        
        # Photo (left side)
        photo_x, photo_y = 40, 150
        if data['photo']:
            photo_scaled = data['photo'].scaled(180, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(photo_x, photo_y, photo_scaled)
            # Photo border
            painter.setPen(QPen(accent_color, 3))
            painter.drawRect(photo_x-2, photo_y-2, 184, 224)
        else:
            # Placeholder
            painter.fillRect(photo_x, photo_y, 180, 220, QColor(240, 240, 240))
            painter.setPen(QColor(150, 150, 150))
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(photo_x, photo_y, 180, 220, Qt.AlignCenter, "No Photo")
        
        # Information (right side)
        info_x = 250
        info_y = 150
        line_height = 45
        
        painter.setPen(QColor(30, 30, 30))
        
        # Name (larger)
        font.setPointSize(18)
        font.setWeight(75)
        painter.setFont(font)
        painter.drawText(info_x, info_y, width-info_x-20, 40, Qt.AlignLeft, data['holder_name'])
        info_y += line_height
        
        # Other details
        font.setPointSize(12)
        font.setWeight(50)  # Normal
        painter.setFont(font)
        
        details = [
            ("ID:", data['id_number']),
            ("Designation:", data['designation']),
            ("Department:", data['department']),
            ("Blood Group:", data['blood_group']),
            ("Contact:", data['contact'])
        ]
        
        for label, value in details:
            if value:
                # Label (bold)
                font.setWeight(75)
                painter.setFont(font)
                painter.setPen(accent_color)
                painter.drawText(info_x, info_y, 150, 30, Qt.AlignLeft, label)
                
                # Add spacing - draw value further to the right
                font.setWeight(50)
                painter.setFont(font)
                painter.setPen(QColor(30, 30, 30))
                # Increased from 120 to 150 for more space between label and value
                painter.drawText(info_x + 150, info_y, width-info_x-170, 30, Qt.AlignLeft, value)
                info_y += line_height
        
        # Footer - Validity
        footer_y = height - 50
        painter.setPen(accent_color)
        font.setPointSize(10)
        font.setWeight(75)
        painter.setFont(font)
        
        if data['valid_from'] or data['valid_till']:
            validity_text = f"Valid: {data['valid_from'] or 'N/A'} to {data['valid_till'] or 'N/A'}"
            painter.drawText(20, footer_y, width-40, 30, Qt.AlignCenter, validity_text)
        
        painter.end()
        return card
    
    def show_help(self):
        """Show help dialog with instructions"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Smart Identity Pro")
        dialog.setModal(True)
        dialog.resize(600, 500)
        
        layout = QVBoxLayout()
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2 style="color:#60a5fa;">Smart Identity Pro - User Guide</h2>
        
        <h3 style="color:#93c5fd;">Getting Started:</h3>
        <ol>
            <li><b>Browse PDF:</b> Click "Browse PDF" to select your Aadhaar card PDF</li>
            <li><b>Load PDF:</b> Enter password if needed, then click "Load PDF"</li>
            <li><b>Select Side:</b> Choose Front or Back side to edit</li>
        </ol>
        
        <h3 style="color:#93c5fd;">Editing:</h3>
        <ul>
            <li><b>Drag:</b> Click and drag the text to move it</li>
            <li><b>Position Controls:</b> Use arrow buttons or X/Y inputs</li>
            <li><b>Zoom:</b> Adjust scale with zoom controls</li>
            <li><b>Photo Editor:</b> Adjust brightness/contrast</li>
            <li><b>Bold Font:</b> Make text appear bolder</li>
            <li><b>Text Size:</b> Choose XL, L, S, or XS</li>
        </ul>
        
        <h3 style="color:#93c5fd;">Control Modes:</h3>
        <ul>
            <li><b>Adjust Card Position:</b> Arrow buttons move the card</li>
            <li><b>Adjust Zoom:</b> Arrow buttons zoom in/out</li>
        </ul>
        
        <h3 style="color:#93c5fd;">Export & Tools:</h3>
        <ul>
            <li><b>Print Card:</b> Print both sides on A4 paper</li>
            <li><b>Report Issue:</b> Send bug reports or feedback</li>
            <li><b>License:</b> Activate or purchase license</li>
        </ul>
        
        <p style="color:#10b981;"><b>Demo Version:</b> Limited to 5 uses. Purchase license for unlimited access!</p>
        """)
        help_text.setStyleSheet("background-color:#1e293b;color:#e5e7eb;padding:10px;")
        
        layout.addWidget(help_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def report_issue(self):
        """Show report issue dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Report Issue")
        dialog.setModal(True)
        dialog.resize(500, 400)
        
        layout = QVBoxLayout()
        
        title = QLabel("Report a Bug or Issue")
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#60a5fa;")
        
        desc_label = QLabel("Describe the issue:")
        desc_label.setStyleSheet("color:#e5e7eb;margin-top:10px;")
        
        issue_text = QTextEdit()
        issue_text.setPlaceholderText("Please describe the issue you encountered in detail...")
        issue_text.setStyleSheet("background-color:#1e293b;color:#e5e7eb;padding:8px;")
        
        email_label = QLabel("Your email (optional):")
        email_label.setStyleSheet("color:#e5e7eb;margin-top:10px;")
        
        email_input = QLineEdit()
        email_input.setPlaceholderText("email@example.com")
        email_input.setStyleSheet("padding:8px;")
        
        submit_btn = QPushButton("Submit Report")
        submit_btn.setStyleSheet("background-color:#dc2626;color:white;padding:10px;font-weight:bold;")
        submit_btn.clicked.connect(lambda: self.submit_issue_report(issue_text.toPlainText(), email_input.text(), dialog))
        
        layout.addWidget(title)
        layout.addWidget(desc_label)
        layout.addWidget(issue_text)
        layout.addWidget(email_label)
        layout.addWidget(email_input)
        layout.addWidget(submit_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def submit_issue_report(self, issue, email, dialog):
        """Submit the issue report"""
        if not issue.strip():
            QMessageBox.warning(dialog, "Empty Report", "Please describe the issue before submitting.")
            return
        
        # In a real app, send this to a server
        QMessageBox.information(dialog, "Report Submitted", 
            "Thank you for your report!\n\n"
            "Our team will review it and get back to you soon.\n"
            f"Reference: ISSUE-{hash(issue) % 10000:04d}")
        dialog.close()
        self.status_label.setText("Issue report submitted")
    
    def toggle_settings_panel(self, checked):
        """Toggle settings dropdown panel visibility"""
        self.settings_panel.setVisible(checked)
        # Update arrow icon
        if checked:
            self.settings_header.setText("⚙️ Settings ▲")
        else:
            self.settings_header.setText("⚙️ Settings ▼")
    
    def update_setting(self, category, key, value):
        """Update a setting value immediately"""
        self.settings[category][key] = value
        self.status_label.setText(f"Setting updated: {key} = {value}")
    
    def open_settings(self):
        """Open comprehensive settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings - Smart Identity Pro")
        dialog.setModal(True)
        dialog.resize(900, 700)
        
        main_layout = QHBoxLayout()
        
        # Left side - Card Elements checkboxes
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        elements_label = QLabel("Card Elements")
        elements_label.setStyleSheet("font-weight:bold;font-size:16px;color:#60a5fa;padding:10px;")
        left_layout.addWidget(elements_label)
        
        # Scroll area for checkboxes
        from PyQt5.QtWidgets import QScrollArea, QCheckBox
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:1px solid #334155;border-radius:6px;background-color:#1e293b;}")
        
        checkbox_widget = QWidget()
        checkbox_layout = QVBoxLayout(checkbox_widget)
        
        # Create all checkboxes
        self.settings_checkboxes = {}
        checkbox_items = [
            ('front_page_header', 'Front Page Header'),
            ('front_page_footer_margin', 'Front Page Footer Margin'),
            ('front_page_footer_text', 'Front Page Footer Text'),
            ('rear_page_header', 'Rear Page Header'),
            ('rear_page_footer_margin', 'Rear Page Footer Margin'),
            ('rear_page_footer', 'Rear Page Footer'),
            ('rear_page_instruction', 'Rear Page Instruction'),
            ('rear_page_uid', 'Rear Page UID'),
            ('auto_align_contents', 'Auto Align Contents'),
            ('photo_frame', 'Photo Frame'),
            ('download_date', 'Download Date'),
            ('generation_date', 'Generation Date'),
            ('colored_footer', 'Colored Footer'),
            ('aadhaar_number', 'Aadhaar Number'),
            ('vid', 'VID'),
            ('epic_header_emblem', 'EPIC Header Emblem')
        ]
        
        for key, label in checkbox_items:
            cb = QCheckBox(label)
            cb.setChecked(self.settings['card_elements'][key])
            cb.setStyleSheet("QCheckBox{color:#e5e7eb;padding:5px;}QCheckBox::indicator{width:18px;height:18px;}")
            self.settings_checkboxes[key] = cb
            checkbox_layout.addWidget(cb)
        
        checkbox_layout.addStretch()
        scroll.setWidget(checkbox_widget)
        left_layout.addWidget(scroll)
        
        # Offsets section
        offsets_label = QLabel("Offsets")
        offsets_label.setStyleSheet("font-weight:bold;font-size:14px;color:#93c5fd;padding:10px 10px 5px 10px;")
        left_layout.addWidget(offsets_label)
        
        from PyQt5.QtWidgets import QFormLayout, QSpinBox
        offsets_form = QFormLayout()
        self.settings_spinboxes = {}
        
        for key, label in [('front_header', 'Front Header Offset'), ('rear_header', 'Rear Header Offset'), 
                          ('front_footer', 'Front Footer Offset'), ('rear_footer', 'Rear Footer Offset'),
                          ('photo', 'Photo Offset')]:
            spin = QSpinBox()
            spin.setRange(-100, 100)
            spin.setValue(self.settings['offsets'][key])
            spin.setStyleSheet("QSpinBox{background-color:#0f172a;border:1px solid #334155;padding:5px;color:#e5e7eb;}")
            self.settings_spinboxes[key] = spin
            offsets_form.addRow(label + ":", spin)
        
        left_layout.addLayout(offsets_form)
        
        # Child Aadhaar Style
        style_label = QLabel("Child Aadhaar Style")
        style_label.setStyleSheet("font-weight:bold;font-size:14px;color:#93c5fd;padding:10px 10px 5px 10px;")
        left_layout.addWidget(style_label)
        
        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        style_layout = QHBoxLayout()
        self.half_panel_radio = QRadioButton("Half Panel")
        self.full_panel_radio = QRadioButton("Full Panel")
        
        for radio in [self.half_panel_radio, self.full_panel_radio]:
            radio.setStyleSheet("QRadioButton{color:#e5e7eb;padding:5px;}")
            style_layout.addWidget(radio)
        
        if self.settings['child_aadhaar_style'] == 'half_panel':
            self.half_panel_radio.setChecked(True)
        else:
            self.full_panel_radio.setChecked(True)
        
        left_layout.addLayout(style_layout)
        left_layout.addStretch()
        
        main_layout.addWidget(left_widget)
        
        # Right side - User Info & Options
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # User Info box
        user_info_box = QGroupBox("User Info")
        user_info_box.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:15px;margin-top:10px;}")
        user_info_layout = QFormLayout()
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(['English', 'Hindi', 'Tamil', 'Telugu', 'Bengali', 'Marathi', 'Gujarati'])
        self.language_combo.setCurrentText(self.settings['user_info']['language'])
        self.language_combo.setStyleSheet("QComboBox{background-color:#0f172a;border:1px solid #334155;padding:6px;color:#e5e7eb;}")
        
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems(['Small', 'Medium', 'Large', 'Extra Large'])
        self.font_size_combo.setCurrentText(self.settings['user_info']['font_size'])
        self.font_size_combo.setStyleSheet("QComboBox{background-color:#0f172a;border:1px solid #334155;padding:6px;color:#e5e7eb;}")
        
        user_info_layout.addRow("Language:", self.language_combo)
        user_info_layout.addRow("Font Size:", self.font_size_combo)
        user_info_box.setLayout(user_info_layout)
        right_layout.addWidget(user_info_box)
        
        # Printer Type
        printer_box = QGroupBox("Printer Type")
        printer_box.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:15px;margin-top:10px;}")
        printer_layout = QVBoxLayout()
        
        self.card_printer_radio = QRadioButton("Card Printer")
        self.card_tray_radio = QRadioButton("Card Tray - Epson")
        self.a4_printer_radio = QRadioButton("A4 Sheet Printer")
        
        for radio in [self.card_printer_radio, self.card_tray_radio, self.a4_printer_radio]:
            radio.setStyleSheet("QRadioButton{color:#e5e7eb;padding:5px;}")
            printer_layout.addWidget(radio)
        
        self.card_printer_radio.setChecked(True)
        printer_box.setLayout(printer_layout)
        right_layout.addWidget(printer_box)
        
        # Printing Options
        print_opts_box = QGroupBox("Printing Options")
        print_opts_box.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:15px;margin-top:10px;}")
        print_opts_layout = QVBoxLayout()
        
        self.print_options_cbs = {}
        for key, label in [('rotate_front', 'Rotate Front'), ('rotate_back', 'Rotate Back'),
                          ('a4_cutting_guidelines', 'A4 Cutting Guidelines'), ('pdf_printing', 'PDF Printing')]:
            cb = QCheckBox(label)
            cb.setChecked(self.settings['printing_options'][key])
            cb.setStyleSheet("QCheckBox{color:#e5e7eb;padding:5px;}")
            self.print_options_cbs[key] = cb
            print_opts_layout.addWidget(cb)
        
        # Stamp with PDF combo
        stamp_layout = QHBoxLayout()
        self.stamp_cb = QCheckBox("Stamp")
        self.stamp_cb.setChecked(self.settings['printing_options'].get('stamp', False))
        self.stamp_cb.setStyleSheet("QCheckBox{color:#e5e7eb;padding:5px;}")
        stamp_layout.addWidget(self.stamp_cb)
        
        self.pdf_combo = QComboBox()
        self.pdf_combo.addItems(['PDF PRINTOUT', 'CUSTOM STAMP', 'NO STAMP'])
        self.pdf_combo.setCurrentText(self.settings['printer'].get('pdf_printout', 'PDF PRINTOUT'))
        self.pdf_combo.setStyleSheet("QComboBox{background-color:#0f172a;border:1px solid #334155;padding:6px;color:#e5e7eb;}")
        stamp_layout.addWidget(self.pdf_combo)
        print_opts_layout.addLayout(stamp_layout)
        
        print_opts_box.setLayout(print_opts_layout)
        right_layout.addWidget(print_opts_box)
        
        # Accessibility Options
        access_box = QGroupBox("Accessibility Options")
        access_box.setStyleSheet("QGroupBox{color:#93c5fd;font-weight:bold;border:2px solid #334155;border-radius:6px;padding:15px;margin-top:10px;}")
        access_layout = QVBoxLayout()
        
        self.access_cbs = {}
        for key, label in [('filenames_contain_password', 'Filenames contain Password'),
                          ('show_password', 'Show Password'), ('remember_last_password', 'Remember Last Password'),
                          ('auto_detect_footer_language', 'Auto detect footer Language')]:
            cb = QCheckBox(label)
            cb.setChecked(self.settings['accessibility'][key])
            cb.setStyleSheet("QCheckBox{color:#e5e7eb;padding:5px;}")
            self.access_cbs[key] = cb
            access_layout.addWidget(cb)
        
        access_box.setLayout(access_layout)
        right_layout.addWidget(access_box)
        
        right_layout.addStretch()
        
        main_layout.addWidget(right_widget)
        
        # Bottom buttons
        layout = QVBoxLayout()
        layout.addLayout(main_layout)
        
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("QPushButton{background-color:#64748b;color:white;padding:10px 30px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#475569;}")
        cancel_btn.clicked.connect(dialog.close)
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;padding:10px 30px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#059669;}")
        save_btn.clicked.connect(lambda: self.save_settings(dialog))
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog{background-color:#0f172a;}QLabel{color:#e5e7eb;}")
        dialog.exec_()
    
    def save_settings(self, dialog):
        """Save all settings from the dialog"""
        # Save card elements
        for key, cb in self.settings_checkboxes.items():
            self.settings['card_elements'][key] = cb.isChecked()
        
        # Save offsets
        for key, spin in self.settings_spinboxes.items():
            self.settings['offsets'][key] = spin.value()
        
        # Save user info
        self.settings['user_info']['language'] = self.language_combo.currentText()
        self.settings['user_info']['font_size'] = self.font_size_combo.currentText()
        
        # Save printer type
        if self.card_printer_radio.isChecked():
            self.settings['printer']['type'] = 'card_printer'
        elif self.card_tray_radio.isChecked():
            self.settings['printer']['type'] = 'card_tray'
        else:
            self.settings['printer']['type'] = 'a4_printer'
        
        # Save printing options
        for key, cb in self.print_options_cbs.items():
            self.settings['printing_options'][key] = cb.isChecked()
        
        self.settings['printing_options']['stamp'] = self.stamp_cb.isChecked()
        self.settings['printer']['pdf_printout'] = self.pdf_combo.currentText()
        
        # Save accessibility
        for key, cb in self.access_cbs.items():
            self.settings['accessibility'][key] = cb.isChecked()
        
        # Save child style
        self.settings['child_aadhaar_style'] = 'half_panel' if self.half_panel_radio.isChecked() else 'full_panel'
        
        QMessageBox.information(dialog, "Settings Saved", "Your settings have been saved successfully!")
        self.status_label.setText("Settings updated")
        dialog.close()
    
    def open_photo_editor(self):
        """Open photo editor dialog"""
        if not self.pdf_loaded:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Photo Editor")
        dialog.setModal(True)
        dialog.resize(450, 350)
        
        layout = QVBoxLayout()
        
        title = QLabel("Adjust Image Brightness & Contrast")
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#60a5fa;")
        title.setAlignment(Qt.AlignCenter)
        
        # Brightness control
        bright_label = QLabel(f"Brightness: {self.brightness}")
        bright_label.setStyleSheet("color:#e5e7eb;margin-top:20px;font-size:14px;")
        
        bright_slider = QSlider(Qt.Horizontal)
        bright_slider.setRange(-100, 100)
        bright_slider.setValue(self.brightness)
        bright_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1e293b;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #60a5fa;
                width: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
            QSlider::handle:horizontal:hover {
                background: #3b82f6;
            }
        """)
        
        # Store timer for debouncing brightness updates
        bright_timer = None
        
        def on_brightness_change(value):
            nonlocal bright_timer
            bright_label.setText(f"Brightness: {value}")
            self.brightness = value
            
            # Cancel previous timer if exists
            if bright_timer is not None:
                try:
                    bright_timer.stop()
                except:
                    pass
            
            # Create new timer to apply changes after slider stops moving
            from PyQt5.QtCore import QTimer
            bright_timer = QTimer()
            bright_timer.setSingleShot(True)
            bright_timer.timeout.connect(lambda: self.apply_brightness_contrast_safely())
            bright_timer.start(150)  # Wait 150ms after slider stops
        
        bright_slider.valueChanged.connect(on_brightness_change)
        
        # Contrast control
        contrast_label = QLabel(f"Contrast: {self.contrast}")
        contrast_label.setStyleSheet("color:#e5e7eb;margin-top:20px;font-size:14px;")
        
        contrast_slider = QSlider(Qt.Horizontal)
        contrast_slider.setRange(-100, 100)
        contrast_slider.setValue(self.contrast)
        contrast_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1e293b;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #60a5fa;
                width: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
            QSlider::handle:horizontal:hover {
                background: #3b82f6;
            }
        """)
        
        # Store timer for debouncing contrast updates
        contrast_timer = None
        
        def on_contrast_change(value):
            nonlocal contrast_timer
            contrast_label.setText(f"Contrast: {value}")
            self.contrast = value
            
            # Cancel previous timer if exists
            if contrast_timer is not None:
                try:
                    contrast_timer.stop()
                except:
                    pass
            
            # Create new timer to apply changes after slider stops moving
            from PyQt5.QtCore import QTimer
            contrast_timer = QTimer()
            contrast_timer.setSingleShot(True)
            contrast_timer.timeout.connect(lambda: self.apply_brightness_contrast_safely())
            contrast_timer.start(150)  # Wait 150ms after slider stops
        
        contrast_slider.valueChanged.connect(on_contrast_change)
        
        # Preview info
        preview_info = QLabel("💡 Changes apply after you stop moving the slider")
        preview_info.setStyleSheet("color:#fbbf24;font-size:11px;font-style:italic;margin-top:10px;")
        preview_info.setAlignment(Qt.AlignCenter)
        preview_info.setWordWrap(True)
        
        # Reset button
        reset_btn = QPushButton("↺ Reset to Original")
        reset_btn.setStyleSheet("QPushButton{background-color:#dc2626;color:white;padding:10px;margin-top:20px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#b91c1c;}")
        reset_btn.clicked.connect(lambda: (bright_slider.setValue(0), contrast_slider.setValue(0)))
        
        # Close button
        close_btn = QPushButton("✓ Apply & Close")
        close_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;padding:12px;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#059669;}")
        close_btn.clicked.connect(dialog.close)
        
        layout.addWidget(title)
        layout.addWidget(bright_label)
        layout.addWidget(bright_slider)
        layout.addWidget(contrast_label)
        layout.addWidget(contrast_slider)
        layout.addWidget(preview_info)
        layout.addWidget(reset_btn)
        layout.addWidget(close_btn)
        layout.addStretch()
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog{background-color:#0f172a;}")
        dialog.exec_()
    
    def apply_brightness_contrast_safely(self):
        """Apply brightness and contrast with error handling"""
        if not self.pdf_loaded:
            return
        try:
            self.status_label.setText(f"Adjusting... B:{self.brightness} C:{self.contrast}")
            QApplication.processEvents()
            self.apply_image_adjustments()
        except Exception as e:
            self.status_label.setText(f"Error adjusting image: {str(e)}")
            QMessageBox.warning(self, "Adjustment Error", f"Failed to apply adjustments:\n{str(e)}")
    
    def apply_image_adjustments(self):
        """Apply brightness and contrast to ALL layers (bg + mask + data items)"""
        if not self.pdf_loaded:
            return

        # ── FRONT ──────────────────────────────────────────────────────
        if self.front_bg_original and self.front_bg_item and self.front_data_original:
            ftx = int(self.front_data_initial_pos.x())
            fty = int(self.front_data_initial_pos.y())
            ftw = self.front_data_original.width()
            fth = self.front_data_original.height()

            # Layer 1: adjusted bg with white blank
            adj_front_bg = self.adjust_pixmap(self.front_bg_original, self.brightness, self.contrast)
            p = QPainter(adj_front_bg)
            p.fillRect(ftx, fty, ftw, fth, Qt.white)
            p.end()
            self.front_bg_item.setPixmap(adj_front_bg)

            # Layer 3: mask = adjusted bg with transparent hole
            front_mask = QPixmap(adj_front_bg.size())
            front_mask.fill(Qt.transparent)
            mp = QPainter(front_mask)
            mp.drawPixmap(0, 0, adj_front_bg)
            mp.setCompositionMode(QPainter.CompositionMode_Clear)
            mp.fillRect(ftx, fty, ftw, fth, Qt.transparent)
            mp.end()
            if self.front_blank_item:
                self.front_blank_item.setPixmap(front_mask)

            # Layer 2: data item (with bold if enabled)
            if self.front_data_item:
                src = self.make_bold(self.front_data_original) if self.bold_stroke > 0 else self.front_data_original
                self.front_data_item.setPixmap(self.adjust_pixmap(src, self.brightness, self.contrast))

        # ── BACK ───────────────────────────────────────────────────────
        if self.back_bg_original and self.back_bg_item and self.back_data_original:
            btx = int(self.back_data_initial_pos.x())
            bty = int(self.back_data_initial_pos.y())
            btw = self.back_data_original.width()
            bth = self.back_data_original.height()

            # Layer 1: adjusted bg with white blank
            adj_back_bg = self.adjust_pixmap(self.back_bg_original, self.brightness, self.contrast)
            p = QPainter(adj_back_bg)
            p.fillRect(btx, bty, btw, bth, Qt.white)
            p.end()
            self.back_bg_item.setPixmap(adj_back_bg)

            # Layer 3: mask = adjusted bg with transparent hole
            back_mask = QPixmap(adj_back_bg.size())
            back_mask.fill(Qt.transparent)
            mp = QPainter(back_mask)
            mp.drawPixmap(0, 0, adj_back_bg)
            mp.setCompositionMode(QPainter.CompositionMode_Clear)
            mp.fillRect(btx, bty, btw, bth, Qt.transparent)
            mp.end()
            if self.back_blank_item:
                self.back_blank_item.setPixmap(back_mask)

            # Layer 2: data item (with bold if enabled)
            if self.back_data_item:
                src = self.make_bold(self.back_data_original) if self.bold_stroke > 0 else self.back_data_original
                self.back_data_item.setPixmap(self.adjust_pixmap(src, self.brightness, self.contrast))

        self.status_label.setText(f"✓ Brightness: {self.brightness}  Contrast: {self.contrast}")
    
    def adjust_pixmap(self, original_pixmap, brightness, contrast):
        """Apply brightness and contrast adjustments to a pixmap - FIXED VERSION"""
        if brightness == 0 and contrast == 0:
            return original_pixmap.copy()
        
        # Convert pixmap to QImage in ARGB32 format for faster processing
        image = original_pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        
        # Calculate adjustment factors
        bright_factor = brightness * 2.55  # Convert to 0-255 range
        contrast_factor = (100.0 + contrast) / 100.0
        
        # Get image dimensions
        width = image.width()
        height = image.height()
        
        # Create lookup table for faster processing
        lookup_table = []
        for i in range(256):
            # Apply contrast
            val = int((i - 128) * contrast_factor + 128)
            # Apply brightness
            val = int(val + bright_factor)
            # Clamp
            val = max(0, min(255, val))
            lookup_table.append(val)
        
        # Process image pixel by pixel
        for y in range(height):
            for x in range(width):
                # Get pixel color
                pixel = image.pixel(x, y)
                
                # Extract ARGB components
                a = (pixel >> 24) & 0xFF
                r = (pixel >> 16) & 0xFF
                g = (pixel >> 8) & 0xFF
                b = pixel & 0xFF
                
                # Apply lookup table
                r = lookup_table[r]
                g = lookup_table[g]
                b = lookup_table[b]
                
                # Reconstruct pixel
                new_pixel = (a << 24) | (r << 16) | (g << 8) | b
                image.setPixel(x, y, new_pixel)
        
        return QPixmap.fromImage(image)
    
    def toggle_bold_font(self):
        """Toggle bold effect on text"""
        self.is_bold = self.bold_font_btn.isChecked()

        if not self.pdf_loaded:
            return

        self.apply_bold_to_items()

        if self.is_bold:
            self.status_label.setText("✓ Bold font enabled")
        else:
            self.status_label.setText("Bold font disabled")

    def apply_bold_to_items(self):
        """Apply or remove bold effect on both front and back data items"""
        if not self.pdf_loaded:
            return
        # Reuse apply_image_adjustments — it already handles bold + brightness + mask rebuild
        self.apply_image_adjustments()

    def make_bold(self, original_pixmap):
        """
        Create bold/stroke effect using the slider value (self.bold_stroke).
        0 = original, 1-10 = increasing stroke thickness.
        Stamps the original image at offsets to thicken strokes cleanly.
        """
        stroke = self.bold_stroke
        if stroke == 0:
            return original_pixmap.copy()

        w, h = original_pixmap.width(), original_pixmap.height()

        result = QPixmap(w, h)
        result.fill(Qt.white)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Build offsets based on stroke value (1 = light, 10 = heavy)
        offsets = []
        for r in range(1, stroke + 1):
            offsets += [(r, 0), (-r, 0), (0, r), (0, -r),
                        (r, r), (-r, r), (r, -r), (-r, -r)]

        # Stamp at each offset first
        for dx, dy in offsets:
            painter.drawPixmap(dx, dy, original_pixmap)

        # Draw original clean on top — keeps text crisp
        painter.drawPixmap(0, 0, original_pixmap)
        painter.end()

        return result
    
    def reset_text_size(self):
        """Reset text size back to 100% and uncheck all size buttons"""
        if not self.pdf_loaded:
            return
        
        # Uncheck all size buttons
        for btn in [self.size_xlarge_btn, self.size_large_btn, self.size_small_btn, self.size_xsmall_btn]:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        
        # Reset scale to 100%
        self.scale_x.setValue(100)
        self.scale_y.setValue(100)
        
        self.status_label.setText("Text size reset to 100%")

    def set_text_size(self, scale_percent):
        """Set text size using scale percentage"""
        if not self.pdf_loaded:
            return
        
        # Uncheck all size buttons
        for btn in [self.size_xlarge_btn, self.size_large_btn, self.size_small_btn, self.size_xsmall_btn]:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        
        # Check the clicked button
        sender = self.sender()
        sender.setChecked(True)
        
        # Apply scale
        self.scale_x.setValue(scale_percent)
        self.scale_y.setValue(scale_percent)
        
        self.status_label.setText(f"Text size set to {scale_percent}%")
    
    def set_text_mode(self, mode):
        """Switch between extracted and cropped text modes"""
        if not self.pdf_loaded:
            return
        
        self.current_text_mode = mode
        
        # Uncheck both buttons and check the selected one
        self.mode_extracted_btn.blockSignals(True)
        self.mode_cropped_btn.blockSignals(True)
        self.mode_extracted_btn.setChecked(mode == 'extracted')
        self.mode_cropped_btn.setChecked(mode == 'cropped')
        self.mode_extracted_btn.blockSignals(False)
        self.mode_cropped_btn.blockSignals(False)
        
        if mode == 'extracted':
            # Extracted mode: Show text with white background (like extracted text)
            if self.front_data_item:
                self.front_data_item.setOpacity(1.0)
            if self.back_data_item:
                self.back_data_item.setOpacity(1.0)
            if self.front_blank_item:
                self.front_blank_item.setOpacity(1.0)
            if self.back_blank_item:
                self.back_blank_item.setOpacity(1.0)
            
            self.status_label.setText("Text mode: Extracted (white background)")
        else:
            # Cropped mode: Show original cropped image
            if self.front_data_item:
                self.front_data_item.setOpacity(1.0)
            if self.back_data_item:
                self.back_data_item.setOpacity(1.0)
            if self.front_blank_item:
                self.front_blank_item.setOpacity(1.0)
            if self.back_blank_item:
                self.back_blank_item.setOpacity(1.0)
            
            self.status_label.setText("Text mode: Cropped (original)")

    def print_card(self, mode='front'):
        """Print the card(s) - mode can be 'front', 'back', or 'both'"""
        if not self.pdf_loaded:
            QMessageBox.warning(self, "No PDF", "Please load a PDF first!")
            return
        
        # Check demo usage
        if not self.check_demo_usage():
            return
        
        # Show preview dialog first
        self.show_print_preview(mode)
    
    def show_print_preview(self, mode):
        """Show print preview dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Print Preview - Smart Identity Pro")
        dialog.setModal(True)
        dialog.resize(1000, 750)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title with icon
        title_layout = QHBoxLayout()
        title = QLabel(f"🖨️ Print Preview - {mode.capitalize()} Card{'s' if mode == 'both' else ''}")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#60a5fa;padding:10px;")
        title.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title)
        layout.addLayout(title_layout)
        
        # Info banner
        info_banner = QLabel("✓ Review your card(s) before printing")
        info_banner.setStyleSheet("background-color:#0891b2;color:white;padding:12px;font-size:14px;font-weight:bold;border-radius:6px;")
        info_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_banner)
        
        layout.addSpacing(10)
        
        # Preview area with scroll
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background-color:#0f172a;border:2px solid #334155;border-radius:8px;}")
        
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setSpacing(30)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        
        # Generate preview images
        if mode == 'front' or mode == 'both':
            front_container = QWidget()
            front_container.setStyleSheet("background-color:#1e293b;border-radius:8px;padding:15px;")
            front_container_layout = QVBoxLayout(front_container)
            
            front_title = QLabel("📄 FRONT SIDE")
            front_title.setStyleSheet("font-size:16px;font-weight:bold;color:#fbbf24;padding:5px;")
            front_title.setAlignment(Qt.AlignCenter)
            front_container_layout.addWidget(front_title)
            
            front_preview = self.generate_preview_pixmap('front')
            front_label = QLabel()
            # Scale to fit nicely in preview
            scaled_front = front_preview.scaled(850, 550, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            front_label.setPixmap(scaled_front)
            front_label.setAlignment(Qt.AlignCenter)
            front_label.setStyleSheet("background-color:white;padding:15px;border:2px solid #60a5fa;border-radius:6px;")
            front_container_layout.addWidget(front_label)
            
            preview_layout.addWidget(front_container)
        
        if mode == 'both':
            # Add prominent separator
            separator = QLabel("━" * 80)
            separator.setStyleSheet("color:#475569;")
            separator.setAlignment(Qt.AlignCenter)
            preview_layout.addWidget(separator)
        
        if mode == 'back' or mode == 'both':
            back_container = QWidget()
            back_container.setStyleSheet("background-color:#1e293b;border-radius:8px;padding:15px;")
            back_container_layout = QVBoxLayout(back_container)
            
            back_title = QLabel("📄 BACK SIDE")
            back_title.setStyleSheet("font-size:16px;font-weight:bold;color:#fbbf24;padding:5px;")
            back_title.setAlignment(Qt.AlignCenter)
            back_container_layout.addWidget(back_title)
            
            back_preview = self.generate_preview_pixmap('back')
            back_label = QLabel()
            scaled_back = back_preview.scaled(850, 550, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            back_label.setPixmap(scaled_back)
            back_label.setAlignment(Qt.AlignCenter)
            back_label.setStyleSheet("background-color:white;padding:15px;border:2px solid #60a5fa;border-radius:6px;")
            back_container_layout.addWidget(back_label)
            
            preview_layout.addWidget(back_container)
        
        preview_layout.addStretch()
        scroll.setWidget(preview_widget)
        layout.addWidget(scroll)
        
        layout.addSpacing(10)
        
        # Print details info
        details = QLabel(f"📋 Paper: A4 Landscape  •  Quality: High Resolution  •  Cards to print: {1 if mode != 'both' else 2}")
        details.setStyleSheet("color:#94a3b8;padding:8px;font-size:13px;background-color:#1e293b;border-radius:4px;")
        details.setAlignment(Qt.AlignCenter)
        layout.addWidget(details)
        
        # Warning/tip
        tip = QLabel("💡 Tip: Make sure your adjustments look correct before printing. Check text position and zoom level.")
        tip.setStyleSheet("color:#fbbf24;padding:8px;font-size:12px;font-style:italic;")
        tip.setAlignment(Qt.AlignCenter)
        tip.setWordWrap(True)
        layout.addWidget(tip)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        cancel_btn = QPushButton("✖ Cancel")
        cancel_btn.setStyleSheet("QPushButton{background-color:#64748b;color:white;padding:12px 40px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#475569;}")
        cancel_btn.clicked.connect(dialog.close)
        
        save_pdf_btn = QPushButton("💾 Save as PDF")
        save_pdf_btn.setStyleSheet("QPushButton{background-color:#7c3aed;color:white;padding:12px 40px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#6d28d9;}")
        save_pdf_btn.clicked.connect(lambda: self.save_as_pdf(mode, dialog))
        
        print_btn = QPushButton("🖨️ Print to Printer")
        print_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;padding:12px 40px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#059669;}")
        print_btn.clicked.connect(lambda: self.execute_print(mode, dialog))
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_pdf_btn)
        button_layout.addWidget(print_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # Set dialog style
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
            }
        """)
        
        dialog.exec_()
    
    def generate_preview_pixmap(self, side):
        """Generate a preview pixmap of the card"""
        # Create a temporary scene with the card
        temp_scene = QGraphicsScene()
        
        if side == 'front':
            # Layer 1: Background with blanked text area
            bg_item = QGraphicsPixmapItem(self.front_bg_item.pixmap())
            bg_item.setPos(0, 0)
            bg_item.setTransformationMode(Qt.SmoothTransformation)
            temp_scene.addItem(bg_item)
            
            # Layer 2: Draggable text with current transform
            data_item = QGraphicsPixmapItem(self.front_data_item.pixmap())
            data_item.setPos(self.front_data_item.pos())
            data_item.setTransform(self.front_data_item.transform())
            data_item.setTransformationMode(Qt.SmoothTransformation)
            temp_scene.addItem(data_item)
            
            # Layer 3: Mask overlay
            if self.front_blank_item:
                mask_item = QGraphicsPixmapItem(self.front_blank_item.pixmap())
                mask_item.setPos(0, 0)
                mask_item.setTransformationMode(Qt.SmoothTransformation)
                temp_scene.addItem(mask_item)
            
            rect = bg_item.boundingRect()
        else:  # back
            # Layer 1: Background with blanked text area
            bg_item = QGraphicsPixmapItem(self.back_bg_item.pixmap())
            bg_item.setPos(0, 0)
            bg_item.setTransformationMode(Qt.SmoothTransformation)
            temp_scene.addItem(bg_item)
            
            # Layer 2: Draggable text with current transform
            data_item = QGraphicsPixmapItem(self.back_data_item.pixmap())
            data_item.setPos(self.back_data_item.pos())
            data_item.setTransform(self.back_data_item.transform())
            data_item.setTransformationMode(Qt.SmoothTransformation)
            temp_scene.addItem(data_item)
            
            # Layer 3: Mask overlay
            if self.back_blank_item:
                mask_item = QGraphicsPixmapItem(self.back_blank_item.pixmap())
                mask_item.setPos(0, 0)
                mask_item.setTransformationMode(Qt.SmoothTransformation)
                temp_scene.addItem(mask_item)
            
            rect = bg_item.boundingRect()
        
        temp_scene.setSceneRect(rect)
        
        # Render to pixmap
        pixmap = QPixmap(int(rect.width()), int(rect.height()))
        pixmap.fill(Qt.white)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        temp_scene.render(painter)
        painter.end()
        
        return pixmap
    
    def save_as_pdf(self, mode, preview_dialog):
        """Save the card(s) as PDF file - shows PDF preview first"""
        preview_dialog.close()
        
        # Show PDF preview first
        self.show_pdf_preview(mode)
    
    def show_pdf_preview(self, mode):
        """Show preview of how the PDF will look with A4 layout"""
        dialog = QDialog(self)
        dialog.setWindowTitle("PDF Preview - A4 Landscape Layout")
        dialog.setModal(True)
        dialog.resize(1100, 800)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel(f"📄 PDF Preview - {mode.capitalize()} Card{'s' if mode == 'both' else ''}")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#60a5fa;padding:10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Info banner
        info_banner = QLabel("This shows exactly how your PDF will look with A4 paper size and margins")
        info_banner.setStyleSheet("background-color:#7c3aed;color:white;padding:12px;font-size:13px;border-radius:6px;")
        info_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_banner)
        
        layout.addSpacing(10)
        
        # Generate PDF preview
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background-color:#334155;border:2px solid #475569;border-radius:8px;}")
        
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setSpacing(30)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        
        # Create temporary printer to get exact PDF layout dimensions
        temp_printer = QPrinter(QPrinter.HighResolution)
        temp_printer.setPageSize(QPrinter.A4)
        temp_printer.setOrientation(QPrinter.Landscape)
        
        # Generate preview for each page
        if mode == 'front' or mode == 'both':
            page1_pixmap = self.generate_pdf_page_preview('front', temp_printer)
            
            page1_container = QWidget()
            page1_container.setStyleSheet("background-color:#1e293b;border-radius:8px;padding:15px;")
            page1_layout = QVBoxLayout(page1_container)
            
            page1_title = QLabel("📄 PAGE 1 - FRONT CARD")
            page1_title.setStyleSheet("font-size:14px;font-weight:bold;color:#fbbf24;padding:5px;")
            page1_title.setAlignment(Qt.AlignCenter)
            page1_layout.addWidget(page1_title)
            
            page1_label = QLabel()
            # Show A4 page preview - fit it nicely with max dimensions
            max_width = 850
            max_height = 600
            scaled_page1 = page1_pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            page1_label.setPixmap(scaled_page1)
            page1_label.setAlignment(Qt.AlignCenter)
            page1_label.setStyleSheet("background-color:white;padding:5px;border:3px solid #60a5fa;")
            page1_layout.addWidget(page1_label)
            
            # Show dimensions
            dim_label = QLabel("A4 Landscape (297mm × 210mm)")
            dim_label.setStyleSheet("color:#94a3b8;font-size:11px;padding:3px;")
            dim_label.setAlignment(Qt.AlignCenter)
            page1_layout.addWidget(dim_label)
            
            preview_layout.addWidget(page1_container)
        
        if mode == 'both':
            separator = QLabel("━" * 100)
            separator.setStyleSheet("color:#475569;")
            separator.setAlignment(Qt.AlignCenter)
            preview_layout.addWidget(separator)
        
        if mode == 'back' or mode == 'both':
            page2_pixmap = self.generate_pdf_page_preview('back', temp_printer)
            
            page2_container = QWidget()
            page2_container.setStyleSheet("background-color:#1e293b;border-radius:8px;padding:15px;")
            page2_layout = QVBoxLayout(page2_container)
            
            page_num = 1 if mode == 'back' else 2
            page2_title = QLabel(f"📄 PAGE {page_num} - BACK CARD")
            page2_title.setStyleSheet("font-size:14px;font-weight:bold;color:#fbbf24;padding:5px;")
            page2_title.setAlignment(Qt.AlignCenter)
            page2_layout.addWidget(page2_title)
            
            page2_label = QLabel()
            max_width = 850
            max_height = 600
            scaled_page2 = page2_pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            page2_label.setPixmap(scaled_page2)
            page2_label.setAlignment(Qt.AlignCenter)
            page2_label.setStyleSheet("background-color:white;padding:5px;border:3px solid #60a5fa;")
            page2_layout.addWidget(page2_label)
            
            dim_label = QLabel("A4 Landscape (297mm × 210mm)")
            dim_label.setStyleSheet("color:#94a3b8;font-size:11px;padding:3px;")
            dim_label.setAlignment(Qt.AlignCenter)
            page2_layout.addWidget(dim_label)
            
            preview_layout.addWidget(page2_container)
        
        preview_layout.addStretch()
        scroll.setWidget(preview_widget)
        layout.addWidget(scroll)
        
        layout.addSpacing(10)
        
        # Details
        pages_text = "1 page" if mode != 'both' else "2 pages"
        details = QLabel(f"📋 Format: PDF  •  Size: A4 Landscape  •  Pages: {pages_text}  •  Margins: 10%")
        details.setStyleSheet("color:#94a3b8;padding:8px;font-size:13px;background-color:#1e293b;border-radius:4px;")
        details.setAlignment(Qt.AlignCenter)
        layout.addWidget(details)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet("QPushButton{background-color:#64748b;color:white;padding:12px 30px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#475569;}")
        back_btn.clicked.connect(lambda: (dialog.close(), self.show_print_preview(mode)))
        
        cancel_btn = QPushButton("✖ Cancel")
        cancel_btn.setStyleSheet("QPushButton{background-color:#64748b;color:white;padding:12px 30px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#475569;}")
        cancel_btn.clicked.connect(dialog.close)
        
        save_btn = QPushButton("💾 Save PDF")
        save_btn.setStyleSheet("QPushButton{background-color:#10b981;color:white;padding:12px 40px;font-weight:bold;font-size:14px;border-radius:6px;}QPushButton:hover{background-color:#059669;}")
        save_btn.clicked.connect(lambda: self.execute_pdf_save(mode, dialog))
        
        button_layout.addStretch()
        button_layout.addWidget(back_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog{background-color:#0f172a;}")
        dialog.exec_()
    
    def generate_pdf_page_preview(self, side, printer):
        """Generate a preview of how a PDF page will look"""
        # Create a fixed-size preview matching A4 landscape aspect ratio
        # A4 Landscape: 297mm x 210mm (aspect ratio ~1.41:1)
        preview_width = 1200  # Fixed width for preview
        preview_height = int(preview_width / 1.414)  # Maintain A4 aspect ratio
        
        # Create a pixmap representing the A4 page
        page_pixmap = QPixmap(preview_width, preview_height)
        page_pixmap.fill(Qt.white)
        
        # Create painter for the page
        painter = QPainter(page_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Get the card pixmap
        if side == 'front':
            card_base = self.front_bg_item.pixmap().copy()
            
            # Draw the draggable text on top
            card_painter = QPainter(card_base)
            card_painter.setRenderHint(QPainter.Antialiasing)
            card_painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Draw data item at its position with transform
            card_painter.save()
            card_painter.translate(self.front_data_item.pos())
            card_painter.setTransform(self.front_data_item.transform(), True)
            card_painter.drawPixmap(0, 0, self.front_data_item.pixmap())
            card_painter.restore()
            
            # Draw mask overlay
            if self.front_blank_item:
                card_painter.drawPixmap(0, 0, self.front_blank_item.pixmap())
            
            card_painter.end()
            
        else:  # back
            card_base = self.back_bg_item.pixmap().copy()
            
            # Draw the draggable text on top
            card_painter = QPainter(card_base)
            card_painter.setRenderHint(QPainter.Antialiasing)
            card_painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Draw data item at its position with transform
            card_painter.save()
            card_painter.translate(self.back_data_item.pos())
            card_painter.setTransform(self.back_data_item.transform(), True)
            card_painter.drawPixmap(0, 0, self.back_data_item.pixmap())
            card_painter.restore()
            
            # Draw mask overlay
            if self.back_blank_item:
                card_painter.drawPixmap(0, 0, self.back_blank_item.pixmap())
            
            card_painter.end()
        
        # Now scale and center the complete card on the A4 page with 10% margins
        card_width = card_base.width()
        card_height = card_base.height()
        
        # Calculate available space with margins
        margin = 0.1
        available_width = preview_width * (1 - 2*margin)
        available_height = preview_height * (1 - 2*margin)
        
        # Scale card to fit in available space
        scale_x = available_width / card_width
        scale_y = available_height / card_height
        scale = min(scale_x, scale_y)
        
        scaled_card_width = int(card_width * scale)
        scaled_card_height = int(card_height * scale)
        
        # Center position
        x_pos = int((preview_width - scaled_card_width) / 2)
        y_pos = int((preview_height - scaled_card_height) / 2)
        
        # Draw the scaled card centered on the page
        scaled_card = card_base.scaled(scaled_card_width, scaled_card_height, 
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap(x_pos, y_pos, scaled_card)
        painter.end()
        
        return page_pixmap
    
    def execute_pdf_save(self, mode, pdf_preview_dialog):
        """Actually save the PDF file"""
        pdf_preview_dialog.close()
        
        # Ask user where to save
        default_name = f"Aadhaar_Card_{mode.capitalize()}_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save as PDF", 
            default_name,
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return
        
        try:
            self.show_loading("💾 Saving as PDF...")
            
            # Create printer configured for PDF output
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)
            printer.setPageSize(QPrinter.A4)
            printer.setOrientation(QPrinter.Landscape)
            
            # Create painter for printing
            painter = QPainter()
            painter.begin(printer)
            
            if mode == 'front' or mode == 'both':
                # Render front card
                self.render_card_to_painter(painter, 'front', printer)
                
            if mode == 'both':
                # New page for back side
                printer.newPage()
                
            if mode == 'back' or mode == 'both':
                # Render back card
                self.render_card_to_painter(painter, 'back', printer)
            
            painter.end()
            
            self.hide_loading()
            self.status_label.setText(f"Successfully saved {mode} card(s) as PDF!")
            QMessageBox.information(self, "PDF Saved", f"Card(s) saved successfully to:\n{file_path}")
            
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Save Error", f"Failed to save PDF:\n{str(e)}")
            self.status_label.setText("Save failed")
    
    def execute_print(self, mode, preview_dialog):
        """Execute the actual print operation"""
        preview_dialog.close()
        
        try:
            self.show_loading("🖨️ Preparing print...")
            
            # Create printer
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            printer.setOrientation(QPrinter.Landscape)
            
            # Show print dialog
            self.hide_loading()
            dialog = QPrintDialog(printer, self)
            if dialog.exec_() != QPrintDialog.Accepted:
                return
            
            self.show_loading("🖨️ Printing...")
            
            # Create painter for printing
            painter = QPainter()
            painter.begin(printer)
            
            if mode == 'front' or mode == 'both':
                # Render front card
                self.render_card_to_painter(painter, 'front', printer)
                
            if mode == 'both':
                # New page for back side
                printer.newPage()
                
            if mode == 'back' or mode == 'both':
                # Render back card
                self.render_card_to_painter(painter, 'back', printer)
            
            painter.end()
            
            self.hide_loading()
            self.status_label.setText(f"Successfully printed {mode} card(s)!")
            QMessageBox.information(self, "Print Complete", f"Card(s) sent to printer successfully!")
            
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Print Error", f"Failed to print:\n{str(e)}")
            self.status_label.setText("Print failed")
    
    def render_card_to_painter(self, painter, side, printer):
        """Render a specific card side to the painter - FIXED VERSION"""
        # Save painter state
        painter.save()
        
        # Step 1: Render card to a pixmap at native resolution
        if side == 'front':
            bg_pixmap = self.front_bg_item.pixmap()
            card_width = bg_pixmap.width()
            card_height = bg_pixmap.height()
        else:
            bg_pixmap = self.back_bg_item.pixmap()
            card_width = bg_pixmap.width()
            card_height = bg_pixmap.height()
        
        # Create a pixmap to render the complete card
        card_pixmap = QPixmap(card_width, card_height)
        card_pixmap.fill(Qt.white)
        
        # Render all layers to this pixmap
        card_painter = QPainter(card_pixmap)
        card_painter.setRenderHint(QPainter.Antialiasing)
        card_painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        if side == 'front':
            # Layer 1: Background
            card_painter.drawPixmap(0, 0, self.front_bg_item.pixmap())
            
            # Layer 2: Draggable text with transform
            card_painter.save()
            card_painter.translate(self.front_data_item.pos())
            card_painter.setTransform(self.front_data_item.transform(), True)
            card_painter.drawPixmap(0, 0, self.front_data_item.pixmap())
            card_painter.restore()
            
            # Layer 3: Mask overlay
            if self.front_blank_item:
                card_painter.drawPixmap(0, 0, self.front_blank_item.pixmap())
        else:
            # Layer 1: Background
            card_painter.drawPixmap(0, 0, self.back_bg_item.pixmap())
            
            # Layer 2: Draggable text with transform
            card_painter.save()
            card_painter.translate(self.back_data_item.pos())
            card_painter.setTransform(self.back_data_item.transform(), True)
            card_painter.drawPixmap(0, 0, self.back_data_item.pixmap())
            card_painter.restore()
            
            # Layer 3: Mask overlay
            if self.back_blank_item:
                card_painter.drawPixmap(0, 0, self.back_blank_item.pixmap())
        
        card_painter.end()
        
        # Step 2: Scale and center this pixmap on the printer page
        page_rect = printer.pageRect()
        
        # Calculate scaling to fit card on page with 5% margins (reduced from 10%)
        margin = 0.05
        available_width = page_rect.width() * (1 - 2 * margin)
        available_height = page_rect.height() * (1 - 2 * margin)
        
        # Calculate scale to fit (maintain aspect ratio)
        scale_x = available_width / card_width
        scale_y = available_height / card_height
        scale = min(scale_x, scale_y)
        
        # Calculate final dimensions
        final_width = int(card_width * scale)
        final_height = int(card_height * scale)
        
        # Calculate centered position
        x_pos = int((page_rect.width() - final_width) / 2)
        y_pos = int((page_rect.height() - final_height) / 2)
        
        # Draw the scaled card on the page
        target_rect = QPixmap.fromImage(
            card_pixmap.toImage().scaled(
                final_width, 
                final_height, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
        )
        
        painter.drawPixmap(x_pos, y_pos, target_rect)
        
        # Restore painter state
        painter.restore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SmartIdentityPro()
    window.show()
    sys.exit(app.exec_())