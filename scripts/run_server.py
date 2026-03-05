#!/usr/bin/env python3
"""
Run MemCore as a standalone unified HTTP server (MCP + Dashboard).

Usage:
    uv run scripts/run_server.py
    uv run scripts/run_server.py --port 8080
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.main import main

if __name__ == "__main__":
    # Force HTTP mode
    if "--mode" not in sys.argv:
        sys.argv.extend(["--mode", "http"])
    
    # Default to 8080 if not specified
    if "--port" not in sys.argv:
        sys.argv.extend(["--port", "8080"])
        
    main()
