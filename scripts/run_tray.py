#!/usr/bin/env python3
"""
Run MemCore System Tray Application.

Usage:
    uv run scripts/run_tray.py
    uv run scripts/run_tray.py --port 9000
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.tray import run_tray_app

if __name__ == "__main__":
    sys.exit(run_tray_app())
