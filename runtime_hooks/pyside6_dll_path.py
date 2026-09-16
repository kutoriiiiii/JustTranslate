"""Ensure PySide6 extension modules load the Qt DLLs bundled with this app."""

import os
import sys


if getattr(sys, "frozen", False):
    app_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    pyside_dir = os.path.join(app_dir, "PySide6")
    if os.path.isdir(pyside_dir):
        # Keep the handle alive for the process lifetime on Python 3.8+.
        _PYSIDE6_DLL_DIRECTORY = os.add_dll_directory(pyside_dir)
        os.environ["PATH"] = pyside_dir + os.pathsep + os.environ.get("PATH", "")
        os.environ.setdefault("QT_PLUGIN_PATH", os.path.join(pyside_dir, "plugins"))
