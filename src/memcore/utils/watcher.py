import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, Any, Dict, List, Optional
import asyncio


class DocumentHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str], Any], watcher):
        self.callback = callback
        self.watcher = watcher

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            print(f"File modified: {event.src_path}")
            self.watcher._track_change(event.src_path, "modified")
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(self.callback(event.src_path), loop)
            except RuntimeError:
                pass  # No running event loop (shouldn't happen in production)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            print(f"File created: {event.src_path}")
            self.watcher._track_change(event.src_path, "created")
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(self.callback(event.src_path), loop)
            except RuntimeError:
                pass

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            print(f"File deleted: {event.src_path}")
            self.watcher._track_change(event.src_path, "deleted")


class DocumentWatcher:
    def __init__(self, watch_dir: str, callback: Callable[[str], Any]):
        self.watch_dir = watch_dir
        self.callback = callback
        self.observer = Observer()
        self._files_tracked: set = set()
        self._changes_detected = 0
        self._last_scan: Optional[str] = None
        self._watching = False

    def _track_change(self, path: str, change_type: str):
        """Track file changes for statistics."""
        self._changes_detected += 1
        if change_type in ("created", "modified"):
            self._files_tracked.add(path)
        elif change_type == "deleted":
            self._files_tracked.discard(path)

    def start(self):
        if not os.path.exists(self.watch_dir):
            os.makedirs(self.watch_dir)

        event_handler = DocumentHandler(self.callback, self)
        self.observer.schedule(event_handler, self.watch_dir, recursive=True)
        self.observer.start()
        self._watching = True

        # Do initial scan of existing files
        asyncio.create_task(self._initial_scan())

        print(f"Started watching directory: {self.watch_dir}")

    async def _initial_scan(self):
        """Scan existing files on startup."""
        print(f"[Vault] Starting initial scan of {self.watch_dir}...")
        await self.force_rescan()

    async def force_rescan(self, vault_path: Optional[str] = None) -> Dict[str, Any]:
        """Force a full rescan of the vault directory."""
        target_dir = vault_path or self.watch_dir

        if not os.path.exists(target_dir):
            return {
                "success": False,
                "error": f"Directory does not exist: {target_dir}"
            }

        files_scanned = 0
        files_added = 0
        files_updated = 0
        errors = []

        print(f"[Vault] Scanning {target_dir} for .md files...")

        for root, _, files in os.walk(target_dir):
            for filename in files:
                if filename.endswith(".md"):
                    filepath = os.path.join(root, filename)
                    files_scanned += 1

                    try:
                        # Track the file
                        is_new = filepath not in self._files_tracked
                        self._files_tracked.add(filepath)

                        # Call the callback to ingest the file
                        await self.callback(filepath)

                        if is_new:
                            files_added += 1
                        else:
                            files_updated += 1

                    except Exception as e:
                        errors.append(f"{filepath}: {str(e)}")
                        print(f"[Vault] Error processing {filepath}: {e}")

        self._last_scan = datetime.now().isoformat()

        result = {
            "success": True,
            "files_scanned": files_scanned,
            "files_added": files_added,
            "files_updated": files_updated,
            "files_removed": 0,
            "errors": errors
        }

        print(f"[Vault] Scan complete: {files_scanned} files scanned, {files_added} added, {files_updated} updated")
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get current watcher statistics."""
        return {
            "watching": self._watching,
            "vault_path": self.watch_dir,
            "files_tracked": len(self._files_tracked),
            "changes_detected": self._changes_detected,
            "last_scan": self._last_scan
        }

    def stop(self):
        self._watching = False
        self.observer.stop()
        self.observer.join()
