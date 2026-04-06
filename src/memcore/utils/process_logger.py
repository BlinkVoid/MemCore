"""
Process logging utility for MemCore.

Tracks process startup information for debugging and monitoring.
"""
import os
import sys
import psutil
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class ProcessLogger:
    """
    Logs process startup information to help diagnose issues.

    Captures:
    - Process ID and parent process
    - Command line arguments
    - Working directory
    - Environment info (relevant variables)
    - Python executable path
    - Hostname
    """

    LOG_FILE_NAME = "process_startup.log"

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / self.LOG_FILE_NAME

    def log_startup(self, extra_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Log process startup information.

        Args:
            extra_info: Additional context to log

        Returns:
            Dictionary of logged information
        """
        process = psutil.Process()
        parent = process.parent()

        info = {
            "timestamp": datetime.now().isoformat(),
            "hostname": socket.gethostname(),
            "pid": process.pid,
            "ppid": process.ppid(),
            "parent_name": parent.name() if parent else "unknown",
            "parent_cmdline": parent.cmdline() if parent else [],
            "python_executable": sys.executable,
            "python_version": sys.version,
            "working_directory": os.getcwd(),
            "command_line": sys.argv,
            "script_path": os.path.abspath(sys.argv[0]) if sys.argv else "unknown",
            "environment": {
                "MEMCORE_MODE": os.environ.get("MEMCORE_MODE", "not_set"),
                "MEMCORE_PORT": os.environ.get("MEMCORE_PORT", "not_set"),
                "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", "not_set"),
                "OBSIDIAN_VAULT_PATH": os.environ.get("OBSIDIAN_VAULT_PATH", "not_set"),
            }
        }

        if extra_info:
            info.update(extra_info)

        # Write to log file
        self._write_log(info)

        return info

    def _write_log(self, info: Dict[str, Any]):
        """Write log entry to file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"MemCore Startup: {info['timestamp']}\n")
            f.write(f"{'='*60}\n")
            f.write(f"PID: {info['pid']}\n")
            f.write(f"Parent PID: {info['ppid']}\n")
            f.write(f"Parent Name: {info['parent_name']}\n")
            f.write(f"Parent Command: {' '.join(info['parent_cmdline'])}\n")
            f.write(f"\nPython: {info['python_executable']}\n")
            f.write(f"Working Dir: {info['working_directory']}\n")
            f.write(f"Script: {info['script_path']}\n")
            f.write(f"Command Line: {' '.join(info['command_line'])}\n")
            f.write(f"\nEnvironment:\n")
            for key, value in info['environment'].items():
                f.write(f"  {key}={value}\n")
            f.write(f"{'='*60}\n\n")

    def get_recent_starts(self, count: int = 5) -> list:
        """
        Get recent startup log entries.

        Args:
            count: Number of recent entries to return

        Returns:
            List of startup info dictionaries
        """
        if not self.log_file.exists():
            return []

        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse entries between ===== lines
        entries = []
        current_entry = []

        for line in content.split('\n'):
            if line.startswith('=' * 40):
                if current_entry:
                    entries.append('\n'.join(current_entry))
                    current_entry = []
            else:
                current_entry.append(line)

        if current_entry:
            entries.append('\n'.join(current_entry))

        # Return last N entries
        return entries[-count:] if entries else []


def log_process_startup(data_dir: str, **extra_info) -> Dict[str, Any]:
    """
    Convenience function to log process startup.

    Args:
        data_dir: Directory for log files
        **extra_info: Additional info to log

    Returns:
        Startup info dictionary
    """
    logger = ProcessLogger(data_dir)
    return logger.log_startup(extra_info)
