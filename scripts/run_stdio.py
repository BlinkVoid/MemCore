#!/usr/bin/env python3
"""
Run MemCore in stdio mode (for client-spawned processes).

This is the default mode for MCP clients that spawn the process.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.main import main

if __name__ == "__main__":
    if "--mode" not in sys.argv:
        sys.argv.extend(["--mode", "stdio"])
    main()
