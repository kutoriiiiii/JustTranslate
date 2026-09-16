"""LingoDesk - AI-Powered Translation, Polishing & Dictionary Desktop Tool.
Entry point for the application.
"""

import sys
import os
from pathlib import Path

# 将项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow
from core.theme_manager import ThemeManager
import ctypes

def main():
    # 设置 Windows 任务栏专属进程 ID，确保显示自定义图标
    try:
        myappid = "aiworkspace.justtranslate.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # 启用高 DPI 缩放支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Just Translate")
    app.setOrganizationName("AI Workspace")

    # 挂载应用图标
    icon_path = PROJECT_ROOT / "resources" / "icon.png"
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    # 应用主题 (黑色 / 白色 / 跟随系统)
    ThemeManager.get_instance().apply_theme()

    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
