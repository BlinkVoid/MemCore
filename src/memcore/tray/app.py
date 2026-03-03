"""
MemCore System Tray Application

A Windows system tray app for managing the MemCore server with visual status indicators
and quick access to common operations.
"""
import asyncio
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import webbrowser
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Optional imports - graceful degradation if not installed
try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    pystray = None
    Image = None
    ImageDraw = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None


class TrayApp:
    """
    System tray application for MemCore.

    Features:
    - Visual status indicator (running/stopped/error)
    - Quick start/stop controls
    - Memory statistics display
    - Quick access to reports and logs
    - Configuration management
    """

    # Server connection settings
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8080
    HEALTH_CHECK_INTERVAL = 5  # seconds

    def __init__(self, host: str = None, port: int = None):
        self.host = host or self.DEFAULT_HOST
        self.port = port or self.DEFAULT_PORT
        self.base_url = f"http://{self.host}:{self.port}"

        self.icon: Optional[pystray.Icon] = None
        self._status = "unknown"  # running, stopped, error
        self._memory_count = 0
        self._last_check = None
        self._server_process = None
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

        # Callbacks for menu actions
        self._start_server_callback: Optional[Callable] = None
        self._stop_server_callback: Optional[Callable] = None

    def _create_icon_image(self, status: str = "unknown") -> "Image.Image":
        """Create a tray icon image based on status."""
        if not Image or not ImageDraw:
            return None

        # Icon size
        width = 64
        height = 64

        # Colors based on status
        colors = {
            "running": (34, 197, 94),    # Green
            "stopped": (239, 68, 68),    # Red
            "error": (234, 179, 8),      # Yellow
            "unknown": (156, 163, 175),  # Gray
        }
        color = colors.get(status, colors["unknown"])

        # Create image with transparency
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw circle background
        margin = 4
        draw.ellipse(
            [margin, margin, width - margin, height - margin],
            fill=color
        )

        # Draw "M" letter
        draw.text(
            (width // 2, height // 2),
            "M",
            fill=(255, 255, 255, 255),
            anchor="mm",
            font_size=32
        )

        return image

    def _check_server_status(self) -> str:
        """Check if the MemCore server is running."""
        if not REQUESTS_AVAILABLE:
            return "unknown"

        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=2
            )
            if response.status_code == 200:
                return "running"
            return "error"
        except requests.ConnectionError:
            return "stopped"
        except Exception:
            return "error"

    def _get_memory_stats(self) -> dict:
        """Get memory statistics from the server."""
        if not REQUESTS_AVAILABLE:
            return {}

        try:
            # Try to get stats from mem_stats endpoint via MCP
            # For now, we'll check if we can read from the graph metadata
            data_dir = PROJECT_ROOT / "dataCrystal"
            stats_file = data_dir / "memcore_stats.json"

            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    return json.load(f)

            return {"total_memories": 0}
        except Exception:
            return {"total_memories": 0}

    def _update_status(self):
        """Update the tray icon and menu based on server status."""
        self._status = self._check_server_status()
        stats = self._get_memory_stats()
        self._memory_count = stats.get("total_memories", 0)
        self._last_check = datetime.now()

        if self.icon:
            # Update icon
            new_icon = self._create_icon_image(self._status)
            if new_icon:
                self.icon.icon = new_icon

            # Update title (tooltip)
            status_text = {
                "running": f"MemCore Running - {self._memory_count} memories",
                "stopped": "MemCore Stopped",
                "error": "MemCore Error",
                "unknown": "MemCore Status Unknown"
            }
            self.icon.title = status_text.get(self._status, "MemCore")

            # Update menu
            self.icon.menu = self._build_menu()

    def _monitor_loop(self):
        """Background thread that monitors server status."""
        while not self._stop_event.is_set():
            try:
                self._update_status()
            except Exception as e:
                print(f"[Tray] Status update error: {e}")

            # Wait for interval or until stopped
            self._stop_event.wait(self.HEALTH_CHECK_INTERVAL)

    def _build_menu(self) -> pystray.Menu:
        """Build the tray context menu."""
        if not pystray:
            return None

        # Status indicator (non-clickable)
        status_item = pystray.MenuItem(
            f"Status: {self._status.upper()}",
            lambda: None,
            enabled=False
        )

        # Memory count (non-clickable)
        memory_item = pystray.MenuItem(
            f"Memories: {self._memory_count}",
            lambda: None,
            enabled=False
        )

        # Separator
        sep1 = pystray.Menu.SEPARATOR

        # Start/Stop actions
        if self._status == "running":
            control_item = pystray.MenuItem(
                "⏹ Stop Server",
                self._on_stop_server
            )
        else:
            control_item = pystray.MenuItem(
                "▶ Start Server",
                self._on_start_server
            )

        # Quick actions
        open_dashboard = pystray.MenuItem(
            "📊 Open Dashboard",
            self._on_open_dashboard
        )

        view_report = pystray.MenuItem(
            "📈 View Report",
            self._on_view_report
        )

        view_logs = pystray.MenuItem(
            "📝 View Logs",
            self._on_view_logs
        )

        # Separator
        sep2 = pystray.Menu.SEPARATOR

        # Configuration
        config_item = pystray.MenuItem(
            "⚙️ Configuration",
            pystray.Menu(
                pystray.MenuItem(
                    "Edit .env",
                    self._on_edit_env
                ),
                pystray.MenuItem(
                    f"Host: {self.host}",
                    lambda: None,
                    enabled=False
                ),
                pystray.MenuItem(
                    f"Port: {self.port}",
                    lambda: None,
                    enabled=False
                )
            )
        )

        # Separator
        sep3 = pystray.Menu.SEPARATOR

        # Exit
        exit_item = pystray.MenuItem(
            "❌ Exit",
            self._on_exit
        )

        return pystray.Menu(
            status_item,
            memory_item,
            sep1,
            control_item,
            open_dashboard,
            view_report,
            view_logs,
            sep2,
            config_item,
            sep3,
            exit_item
        )

    # Menu action handlers
    def _on_start_server(self):
        """Start the MemCore server."""
        try:
            # Start server via subprocess
            import subprocess

            python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
            main_script = PROJECT_ROOT / "src" / "memcore" / "main.py"

            if not python_exe.exists():
                # Fallback to uv run
                subprocess.Popen(
                    ["uv", "run", "src/memcore/main.py", "--mode", "http"],
                    cwd=PROJECT_ROOT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    [str(python_exe), str(main_script), "--mode", "http"],
                    cwd=PROJECT_ROOT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )

            # Wait a moment for server to start
            time.sleep(2)
            self._update_status()

        except Exception as e:
            print(f"[Tray] Failed to start server: {e}")

    def _on_stop_server(self):
        """Stop the MemCore server."""
        try:
            # Find and terminate the Python process running main.py
            import subprocess

            # Try graceful shutdown first (could implement a shutdown endpoint)
            # For now, we'll just show a message
            webbrowser.open(f"{self.base_url}/health")

        except Exception as e:
            print(f"[Tray] Failed to stop server: {e}")

    def _on_open_dashboard(self):
        """Open the web dashboard."""
        webbrowser.open(f"{self.base_url}/status")

    def _on_view_report(self):
        """Open the latest HTML report."""
        report_path = PROJECT_ROOT / "dataCrystal" / "reports" / "latest.html"
        if report_path.exists():
            webbrowser.open(f"file://{report_path}")
        else:
            # Fallback to web status
            webbrowser.open(f"{self.base_url}/status")

    def _on_view_logs(self):
        """Open the log file."""
        log_path = PROJECT_ROOT / "dataCrystal" / "logs" / "memcore.log"
        if log_path.exists():
            # Open with default text editor
            os.startfile(log_path)
        else:
            print(f"[Tray] Log file not found: {log_path}")

    def _on_edit_env(self):
        """Open .env file for editing."""
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            os.startfile(env_path)
        else:
            # Create from example if it doesn't exist
            example_path = PROJECT_ROOT / ".env.example"
            if example_path.exists():
                os.startfile(example_path)

    def _on_exit(self):
        """Exit the tray application."""
        self.stop()

    def start(self):
        """Start the tray application."""
        if not PYSTRAY_AVAILABLE:
            print("[Tray] pystray not installed. Run: uv add pystray pillow")
            return False

        if not REQUESTS_AVAILABLE:
            print("[Tray] requests not installed. Run: uv add requests")
            return False

        # Create initial icon
        icon_image = self._create_icon_image("unknown")

        # Create menu
        menu = self._build_menu()

        # Create icon
        self.icon = pystray.Icon(
            "memcore",
            icon_image,
            "MemCore - Checking...",
            menu
        )

        # Start monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        print("[Tray] System tray app started")
        print(f"[Tray] Monitoring: {self.base_url}")

        # Run the icon (blocks until stopped)
        self.icon.run()

        return True

    def stop(self):
        """Stop the tray application."""
        self._stop_event.set()

        if self.icon:
            self.icon.stop()

        print("[Tray] System tray app stopped")


def run_tray_app(host: str = None, port: int = None):
    """
    Run the system tray application.

    Usage:
        uv run python -m src.memcore.tray
    """
    if not PYSTRAY_AVAILABLE:
        print("Error: pystray is required for the system tray app.")
        print("Install with: uv add pystray pillow")
        return 1

    if not REQUESTS_AVAILABLE:
        print("Error: requests is required for the system tray app.")
        print("Install with: uv add requests")
        return 1

    app = TrayApp(host=host, port=port)

    try:
        app.start()
        return 0
    except KeyboardInterrupt:
        app.stop()
        return 0
    except Exception as e:
        print(f"[Tray] Error: {e}")
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MemCore System Tray App")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")

    args = parser.parse_args()

    sys.exit(run_tray_app(host=args.host, port=args.port))
