#!/usr/bin/env python3
"""
Run MemCore Web Dashboard.

Usage:
    uv run scripts/run_dashboard.py
    uv run scripts/run_dashboard.py --port 8081
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.dashboard import run_dashboard

if __name__ == "__main__":
    sys.exit(run_dashboard())
