#!/usr/bin/env python3
"""
Run MemCore as a standalone SSE server.

Usage:
    uv run scripts/run_server.py
    uv run scripts/run_server.py --port 9000
    uv run scripts/run_server.py --host 0.0.0.0 --port 8080
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.main import main

if __name__ == "__main__":
    # Force SSE mode if not specified
    if "--mode" not in sys.argv:
        sys.argv.extend(["--mode", "sse"])
    main()
