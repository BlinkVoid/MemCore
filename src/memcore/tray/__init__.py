"""
MemCore System Tray Application for Windows

Provides visual status indicator and quick controls for the MemCore server.
"""
from .app import TrayApp, run_tray_app

__all__ = ["TrayApp", "run_tray_app"]
