"""Modern QSS Themes (Dark and Light) for Just Translate."""

DARK_THEME_QSS = """
/* Global Window Styling */
QMainWindow, QDialog {
    background-color: #18181B;
    color: #F4F4F5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: transparent;
    color: #F4F4F5;
}

/* Control Bar & Toolbars */
QFrame#controlBar {
    background-color: #27272A;
    border-radius: 8px;
    padding: 6px;
    border: 1px solid #3F3F46;
}

/* Splitter */
QSplitter::handle:horizontal {
    background-color: #3F3F46;
    width: 6px;
    margin: 4px 1px;
    border-radius: 2px;
}
QSplitter::handle:horizontal:hover {
    background-color: #6366F1;
}

/* Mode Buttons / Segmented Controls */
QPushButton#modeBtn {
    background-color: transparent;
    color: #A1A1AA;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#modeBtn:hover {
    background-color: #3F3F46;
    color: #FAFAFA;
}
QPushButton#modeBtn:checked {
    background-color: #4F46E5;
    color: #FFFFFF;
}

/* Primary Action Buttons */
QPushButton#primaryBtn {
    background-color: #4F46E5;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton#primaryBtn:hover {
    background-color: #4338CA;
}
QPushButton#primaryBtn:pressed {
    background-color: #3730A3;
}
QPushButton#primaryBtn:disabled {
    background-color: #3F3F46;
    color: #71717A;
}

/* Secondary Action Buttons */
QPushButton#secondaryBtn {
    background-color: #27272A;
    color: #D4D4D8;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton#secondaryBtn:hover {
    background-color: #3B3B42;
    color: #FFFFFF;
    border-color: #6366F1;
}
QPushButton#secondaryBtn:pressed {
    background-color: #52525B;
}

/* Sky Accent Button (Input sentence translate / quick actions) */
QPushButton#accentBtnSky {
    background-color: rgba(2, 132, 199, 0.15);
    color: #38BDF8;
    border: 1px solid #0284C7;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#accentBtnSky:hover {
    background-color: #0284C7;
    color: #FFFFFF;
    border-color: #38BDF8;
}
QPushButton#accentBtnSky:pressed {
    background-color: #0369A1;
    color: #FFFFFF;
}

/* Emerald Accent Button (Output sentence retranslate) */
QPushButton#accentBtnEmerald {
    background-color: rgba(5, 150, 105, 0.15);
    color: #34D399;
    border: 1px solid #059669;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#accentBtnEmerald:hover {
    background-color: #059669;
    color: #FFFFFF;
    border-color: #34D399;
}
QPushButton#accentBtnEmerald:pressed {
    background-color: #047857;
    color: #FFFFFF;
}

/* Danger / Stop Button */
QPushButton#dangerBtn {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#dangerBtn:hover {
    background-color: #B91C1C;
}
QPushButton#dangerBtn:disabled {
    background-color: #3F3F46;
    color: #71717A;
}

/* Language Menu Button (comboLikeBtn) */
QPushButton#comboLikeBtn {
    background-color: #27272A;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 6px 12px;
    color: #F4F4F5;
    font-size: 13px;
    text-align: left;
    min-width: 140px;
}
QPushButton#comboLikeBtn:hover {
    background-color: #3F3F46;
    border-color: #52525B;
}
QPushButton#comboLikeBtn:pressed {
    background-color: #18181B;
}

/* API Status Indicator Card */
QFrame#statusIndicator {
    background-color: #1F1F23;
    border: 1px solid #3F3F46;
    border-radius: 6px;
}
QFrame#statusIndicator:hover {
    background-color: #27272A;
    border-color: #52525B;
}
QLabel#statusLatency {
    color: #E4E4E7;
    font-size: 12px;
    font-weight: 500;
}
QLabel#statusSep {
    color: #3F3F46;
    font-size: 11px;
}

/* Image Preview Card */
QFrame#imagePreviewCard {
    background-color: #27272A;
    border-radius: 6px;
    padding: 4px;
    border: 1px solid #3F3F46;
}

/* Dialog Labels */
QLabel#metaTime {
    color: #E4E4E7;
    font-weight: bold;
}
QLabel#metaModel {
    color: #A1A1AA;
    font-size: 12px;
}
QLabel#existingSentenceLabel {
    background-color: #27272A;
    color: #D4D4D8;
    border-left: 3px solid #71717A;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 13px;
}

/* ComboBox */
QComboBox {
    background-color: #27272A;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #6366F1;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #27272A;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}

/* Text Editors & Browsers */
QPlainTextEdit, QTextBrowser, QLineEdit {
    background-color: #202024;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #4F46E5;
    font-size: 14px;
    line-height: 1.6;
}
QPlainTextEdit:focus, QTextBrowser:focus, QLineEdit:focus {
    border: 1px solid #6366F1;
}

/* Panels */
QFrame#panelBox {
    background-color: #18181B;
    border: 1px solid #27272A;
    border-radius: 10px;
    padding: 4px;
}

/* Dictionary Native Cards */
QFrame#dictCard {
    background-color: #202024;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 8px;
}
QLabel#dictWordTitle {
    font-size: 18px;
    font-weight: 700;
    color: #F4F4F5;
}
QLabel#dictPron {
    font-size: 13px;
    font-family: "Lucida Sans Unicode", "Segoe UI", sans-serif;
    color: #38BDF8;
    background-color: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 4px;
    padding: 2px 6px;
}
QLabel#dictSectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #A1A1AA;
    margin-bottom: 2px;
}
QLabel#posBadge {
    font-size: 11px;
    font-weight: 700;
    color: #38BDF8;
    background-color: rgba(56, 189, 248, 0.15);
    border-radius: 3px;
    padding: 1px 6px;
    min-width: 28px;
}
QLabel#dictDefText {
    font-size: 13px;
    font-weight: 500;
    color: #F4F4F5;
}
QLabel#dictDefTrans {
    font-size: 12px;
    color: #A1A1AA;
}
QLabel#exampleSource {
    font-size: 13px;
    font-weight: 500;
    color: #F4F4F5;
}
QLabel#exampleTarget {
    font-size: 12px;
    color: #A1A1AA;
}
QFrame#dictExampleItemBox {
    background-color: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
}
QLabel#chipBlue {
    background-color: rgba(56, 189, 248, 0.15);
    color: #38BDF8;
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QLabel#chipEmerald {
    background-color: rgba(52, 211, 153, 0.15);
    color: #34D399;
    border: 1px solid rgba(52, 211, 153, 0.25);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QLabel#chipAmber {
    background-color: rgba(251, 191, 36, 0.15);
    color: #FBBF24;
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
/* Dictionary Mini Action Buttons (TTS speak & copy) */
QPushButton#dictActionBtn {
    border: 1px solid rgba(255, 255, 255, 0.08);
    background-color: rgba(255, 255, 255, 0.04);
    color: #D4D4D8;
    border-radius: 5px;
    font-size: 13px;
    padding: 2px 6px;
    min-width: 24px;
    min-height: 22px;
}
QPushButton#dictActionBtn:hover {
    background-color: rgba(99, 102, 241, 0.25);
    border-color: rgba(99, 102, 241, 0.5);
    color: #FFFFFF;
}
QPushButton#dictActionBtn:pressed {
    background-color: rgba(79, 70, 229, 0.45);
    border-color: #818CF8;
}
/* Dictionary Header Buttons (🔊 朗读发音 & 📋 复制词头) */
QPushButton#dictHeaderBtn {
    border: 1px solid #3F3F46;
    background-color: #27272A;
    color: #D4D4D8;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 10px;
    height: 24px;
    min-height: 24px;
    max-height: 24px;
}
QPushButton#dictHeaderBtn:hover {
    background-color: #3F3F46;
    border-color: #52525B;
    color: #FAFAFA;
}
QPushButton#dictHeaderBtn:pressed {
    background-color: #18181B;
}
QPushButton#dictHeaderBtn:disabled {
    background-color: #27272A;
    border-color: #27272A;
    color: #52525B;
}

/* Labels */
QLabel {
    color: #D4D4D8;
}
QLabel#headerTitle {
    font-weight: 700;
    font-size: 14px;
    color: #FFFFFF;
}
QLabel#statusLabel {
    color: #A1A1AA;
    font-size: 12px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #18181B;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3F3F46;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #52525B;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* TabWidget */
QTabWidget::pane {
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 10px;
    background-color: #202024;
}
QTabBar::tab {
    background: #27272A;
    color: #A1A1AA;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #4F46E5;
    color: #FFFFFF;
}

/* Context Menus & Popups (QMenu) */
QMenu {
    background-color: #1E1E22;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 6px 4px;
    font-size: 13px;
}
QMenu::item {
    background-color: transparent;
    color: #E4E4E7;
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    margin: 2px 4px;
    font-size: 13px;
    border: 1px solid transparent;
}
QMenu::item:selected, QMenu::item:hover {
    background-color: #4F46E5;
    color: #FFFFFF;
    font-weight: 500;
    border: 1px solid #6366F1;
}
QMenu::item:pressed {
    background-color: #4338CA;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #71717A;
    background-color: transparent;
    border-color: transparent;
}
QMenu::separator {
    height: 1px;
    background-color: #333338;
    margin: 5px 8px;
}
QMenu::icon {
    padding-left: 6px;
}

/* About Tab Card & Typography */
QFrame#aboutCard {
    background-color: #202024;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 12px;
}
QLabel#aboutTitle {
    font-size: 20px;
    font-weight: 700;
    color: #F4F4F5;
    letter-spacing: 0.5px;
}
QLabel#aboutDesc {
    font-size: 12px;
    color: #A1A1AA;
}
QLabel#aboutCopyright {
    font-size: 11px;
    color: #71717A;
}
"""

LIGHT_THEME_QSS = """
/* Global Window Styling (Light Mode) */
QMainWindow, QDialog {
    background-color: #F8FAFC;
    color: #0F172A;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: transparent;
    color: #0F172A;
}

/* Control Bar & Toolbars */
QFrame#controlBar {
    background-color: #FFFFFF;
    border-radius: 8px;
    padding: 6px;
    border: 1px solid #E2E8F0;
}

/* Splitter */
QSplitter::handle:horizontal {
    background-color: #CBD5E1;
    width: 6px;
    margin: 4px 1px;
    border-radius: 2px;
}
QSplitter::handle:horizontal:hover {
    background-color: #4F46E5;
}

/* Mode Buttons / Segmented Controls */
QPushButton#modeBtn {
    background-color: transparent;
    color: #64748B;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#modeBtn:hover {
    background-color: #F1F5F9;
    color: #0F172A;
}
QPushButton#modeBtn:checked {
    background-color: #4F46E5;
    color: #FFFFFF;
}

/* Primary Action Buttons */
QPushButton#primaryBtn {
    background-color: #4F46E5;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton#primaryBtn:hover {
    background-color: #4338CA;
}
QPushButton#primaryBtn:pressed {
    background-color: #3730A3;
}
QPushButton#primaryBtn:disabled {
    background-color: #E2E8F0;
    color: #94A3B8;
}

/* Secondary Action Buttons */
QPushButton#secondaryBtn {
    background-color: #FFFFFF;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton#secondaryBtn:hover {
    background-color: #F8FAFC;
    color: #0F172A;
    border-color: #4F46E5;
}
QPushButton#secondaryBtn:pressed {
    background-color: #F1F5F9;
}

/* Sky Accent Button (Input sentence translate / quick actions) */
QPushButton#accentBtnSky {
    background-color: #E0F2FE;
    color: #0284C7;
    border: 1px solid #38BDF8;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#accentBtnSky:hover {
    background-color: #0284C7;
    color: #FFFFFF;
    border-color: #0284C7;
}
QPushButton#accentBtnSky:pressed {
    background-color: #0369A1;
    color: #FFFFFF;
}

/* Emerald Accent Button (Output sentence retranslate) */
QPushButton#accentBtnEmerald {
    background-color: #D1FAE5;
    color: #059669;
    border: 1px solid #34D399;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#accentBtnEmerald:hover {
    background-color: #059669;
    color: #FFFFFF;
    border-color: #059669;
}
QPushButton#accentBtnEmerald:pressed {
    background-color: #047857;
    color: #FFFFFF;
}

/* Danger / Stop Button */
QPushButton#dangerBtn {
    background-color: #EF4444;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#dangerBtn:hover {
    background-color: #DC2626;
}
QPushButton#dangerBtn:disabled {
    background-color: #E2E8F0;
    color: #94A3B8;
}

/* Language Menu Button (comboLikeBtn) */
QPushButton#comboLikeBtn {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 12px;
    color: #0F172A;
    font-size: 13px;
    text-align: left;
    min-width: 140px;
}
QPushButton#comboLikeBtn:hover {
    background-color: #F8FAFC;
    border-color: #4F46E5;
}
QPushButton#comboLikeBtn:pressed {
    background-color: #F1F5F9;
}

/* API Status Indicator Card */
QFrame#statusIndicator {
    background-color: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
}
QFrame#statusIndicator:hover {
    background-color: #E2E8F0;
    border-color: #94A3B8;
}
QLabel#statusLatency {
    color: #334155;
    font-size: 12px;
    font-weight: 500;
}
QLabel#statusSep {
    color: #CBD5E1;
    font-size: 11px;
}

/* Image Preview Card */
QFrame#imagePreviewCard {
    background-color: #F1F5F9;
    border-radius: 6px;
    padding: 4px;
    border: 1px solid #E2E8F0;
}

/* Dialog Labels */
QLabel#metaTime {
    color: #0F172A;
    font-weight: bold;
}
QLabel#metaModel {
    color: #64748B;
    font-size: 12px;
}
QLabel#existingSentenceLabel {
    background-color: #F1F5F9;
    color: #334155;
    border-left: 3px solid #94A3B8;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 13px;
}

/* ComboBox */
QComboBox {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #4F46E5;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}

/* Text Editors & Browsers */
QPlainTextEdit, QTextBrowser, QLineEdit {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #C7D2FE;
    selection-color: #1E1B4B;
    font-size: 14px;
    line-height: 1.6;
}
QPlainTextEdit:focus, QTextBrowser:focus, QLineEdit:focus {
    border: 1px solid #4F46E5;
}

/* Panels */
QFrame#panelBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 4px;
}

/* Dictionary Native Cards (Light) */
QFrame#dictCard {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 8px;
}
QLabel#dictWordTitle {
    font-size: 18px;
    font-weight: 700;
    color: #0F172A;
}
QLabel#dictPron {
    font-size: 13px;
    font-family: "Lucida Sans Unicode", "Segoe UI", sans-serif;
    color: #0284C7;
    background-color: #E0F2FE;
    border: 1px solid #BAE6FD;
    border-radius: 4px;
    padding: 2px 6px;
}
QLabel#dictSectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #64748B;
    margin-bottom: 2px;
}
QLabel#posBadge {
    font-size: 11px;
    font-weight: 700;
    color: #0284C7;
    background-color: #E0F2FE;
    border-radius: 3px;
    padding: 1px 6px;
    min-width: 28px;
}
QLabel#dictDefText {
    font-size: 13px;
    font-weight: 500;
    color: #0F172A;
}
QLabel#dictDefTrans {
    font-size: 12px;
    color: #64748B;
}
QLabel#exampleSource {
    font-size: 13px;
    font-weight: 500;
    color: #0F172A;
}
QLabel#exampleTarget {
    font-size: 12px;
    color: #64748B;
}
QFrame#dictExampleItemBox {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
}
QLabel#chipBlue {
    background-color: #E0F2FE;
    color: #0369A1;
    border: 1px solid #BAE6FD;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QLabel#chipEmerald {
    background-color: #D1FAE5;
    color: #065F46;
    border: 1px solid #A7F3D0;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QLabel#chipAmber {
    background-color: #FEF3C7;
    color: #92400E;
    border: 1px solid #FDE68A;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
/* Dictionary Mini Action Buttons (TTS speak & copy) */
QPushButton#dictActionBtn {
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    color: #475569;
    border-radius: 5px;
    font-size: 13px;
    padding: 2px 6px;
    min-width: 24px;
    min-height: 22px;
}
QPushButton#dictActionBtn:hover {
    background-color: #EEF2FF;
    border-color: #C7D2FE;
    color: #4F46E5;
}
QPushButton#dictActionBtn:pressed {
    background-color: #E0E7FF;
    border-color: #818CF8;
}
/* Dictionary Header Buttons (🔊 朗读发音 & 📋 复制词头) */
QPushButton#dictHeaderBtn {
    border: 1px solid #CBD5E1;
    background-color: #FFFFFF;
    color: #334155;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 10px;
    height: 24px;
    min-height: 24px;
    max-height: 24px;
}
QPushButton#dictHeaderBtn:hover {
    background-color: #F8FAFC;
    border-color: #94A3B8;
    color: #0F172A;
}
QPushButton#dictHeaderBtn:pressed {
    background-color: #F1F5F9;
}
QPushButton#dictHeaderBtn:disabled {
    background-color: #F8FAFC;
    border-color: #E2E8F0;
    color: #94A3B8;
}

/* Labels */
QLabel {
    color: #334155;
}
QLabel#headerTitle {
    font-weight: 700;
    font-size: 14px;
    color: #0F172A;
}
QLabel#statusLabel {
    color: #64748B;
    font-size: 12px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #F1F5F9;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* TabWidget */
QTabWidget::pane {
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 10px;
    background-color: #FFFFFF;
}
QTabBar::tab {
    background: #F1F5F9;
    color: #64748B;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #4F46E5;
    color: #FFFFFF;
}

/* Context Menus & Popups (QMenu) */
QMenu {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 6px 4px;
    font-size: 13px;
}
QMenu::item {
    background-color: transparent;
    color: #1E293B;
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    margin: 2px 4px;
    font-size: 13px;
    border: 1px solid transparent;
}
QMenu::item:selected, QMenu::item:hover {
    background-color: #4F46E5;
    color: #FFFFFF;
    font-weight: 500;
    border: 1px solid #6366F1;
}
QMenu::item:pressed {
    background-color: #4338CA;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #94A3B8;
    background-color: transparent;
    border-color: transparent;
}
QMenu::separator {
    height: 1px;
    background-color: #E2E8F0;
    margin: 5px 8px;
}
QMenu::icon {
    padding-left: 6px;
}

/* About Tab Card & Typography */
QFrame#aboutCard {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px;
}
QLabel#aboutTitle {
    font-size: 20px;
    font-weight: 700;
    color: #0F172A;
    letter-spacing: 0.5px;
}
QLabel#aboutDesc {
    font-size: 12px;
    color: #64748B;
}
QLabel#aboutCopyright {
    font-size: 11px;
    color: #94A3B8;
}
"""

def get_theme_qss(is_dark: bool = True) -> str:
    """Returns QSS stylesheet for the given dark/light state."""
    return DARK_THEME_QSS if is_dark else LIGHT_THEME_QSS
