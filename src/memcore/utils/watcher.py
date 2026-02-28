import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, Any
import asyncio

class DocumentHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str], Any], loop: asyncio.AbstractEventLoop):
        self.callback = callback
        self.loop = loop

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            print(f"File modified: {event.src_path}")
            asyncio.run_coroutine_threadsafe(self.callback(event.src_path), self.loop)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            print(f"File created: {event.src_path}")
            asyncio.run_coroutine_threadsafe(self.callback(event.src_path), self.loop)

class DocumentWatcher:
    def __init__(self, watch_dir: str, callback: Callable[[str], Any]):
        self.watch_dir = watch_dir
        self.callback = callback
        self.observer = Observer()
        self.loop = asyncio.get_event_loop()

    def start(self):
        if not os.path.exists(self.watch_dir):
            os.makedirs(self.watch_dir)
        
        event_handler = DocumentHandler(self.callback, self.loop)
        self.observer.schedule(event_handler, self.watch_dir, recursive=True)
        self.observer.start()
        print(f"Started watching directory: {self.watch_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
