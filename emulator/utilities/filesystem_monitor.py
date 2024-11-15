import logging
import os
import threading
import time
import shutil

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import utils
import globalvars
from config import read_config
from utilities.database import ccdb

log = logging.getLogger('FileMonitor')

config = read_config()

# Define the extensions to watch within directories
WATCHED_EXTENSIONS = {'.bin', '.py', '.xml'}

class CustomEventHandler(FileSystemEventHandler):
    def __init__(self, paths_to_monitor, directories_to_watch):
        super().__init__()
        # Separate files and directories
        self.files_to_monitor = {os.path.abspath(path) for path in paths_to_monitor}
        self.directories_to_watch = {os.path.abspath(path) for path in paths_to_monitor if os.path.isdir(path)}
        self.directories_to_watch.update(directories_to_watch)  # Include additional directories
        self.last_handled = {}  # Tracks the last handled time for each file individually
        self.debounce_seconds = 10  # Increase debounce period to 10 seconds
        self.lock = threading.Lock()  # Add a lock for thread-safe operations
        self.working_now = False
        self.processing = set()  # Tracks files that are currently being processed

    def on_modified(self, event):
        file_path = os.path.normpath(event.src_path)
        if self._is_specific_file(file_path):
            if not event.is_directory and not self.working_now:
                self.working_now = True
                self.handle_blob_on_modified(event)
        elif self._is_watched_directory_event(event):
            if not event.is_directory and self._has_watched_extension(file_path):
                self.handle_directory_event(event, 'modified')

    def on_deleted(self, event):
        file_path = os.path.normpath(event.src_path)
        if self._is_watched_directory_event(event):
            if self._has_watched_extension(file_path):
                self.handle_directory_event(event, 'deleted')

    def on_moved(self, event):
        src_path = os.path.normpath(event.src_path)
        dest_path = os.path.normpath(event.dest_path)
        if self._is_specific_file(src_path) or self._is_specific_file(dest_path):
            if not event.is_directory and not self.working_now:
                self.working_now = True
                self.handle_blob_on_modified(event)
        elif self._is_watched_directory_event(event):
            if self._has_watched_extension(src_path) or self._has_watched_extension(dest_path):
                self.handle_directory_event(event, 'moved')

    def _is_specific_file(self, file_path):
        for file in self.files_to_monitor:
            if file_path in self.files_to_monitor:
                return True
        return False

    def _is_watched_directory_event(self, event):
        # Check if the event is within any of the watched directories
        for directory in self.directories_to_watch:
            if os.path.commonpath([directory, event.src_path]) == directory:
                return True
        return False

    def _has_watched_extension(self, file_path):
        _, ext = os.path.splitext(file_path)
        return ext.lower() in WATCHED_EXTENSIONS

    def should_handle_file(self, file_path, current_time):
        with self.lock:  # Ensure thread-safe access
            if (file_path not in self.last_handled or
                current_time - self.last_handled.get(file_path, 0) >= self.debounce_seconds) \
                    and file_path not in self.processing:
                self.last_handled[file_path] = current_time
                self.processing.add(file_path)  # Mark as processing
                return True
            return False

    def mark_processing_done(self, file_path):
        """Mark the file's processing as completed."""
        with self.lock:
            self.processing.discard(file_path)  # Remove from processing set

    def handle_directory_event(self, event, event_type):
        file_path = os.path.normpath(event.src_path)
        current_time = time.time()
        log.debug(f"NOTICE: Detected {event_type} event in directory: {file_path}")
        if self.should_handle_file(file_path, current_time):
            self.wrap_reload_blobs()
            self.mark_processing_done(file_path)

    def handle_blob_on_modified(self, event):
        file_path = os.path.normpath(event.src_path)
        current_time = time.time()
        log.debug(f"NOTICE: Detected change in file: {file_path}")
        if self.should_handle_file(file_path, current_time):
            if "firstblob.bin" in file_path:
                self.wrap_load_filesys_blob(file_path)
            else:
                self.wrap_check_secondblob_changed(file_path)
        self.working_now = False

    def wrap_reload_blobs(self):
        os.remove('files/cache/blobhash')
        utils.check_secondblob_changed()

    def wrap_check_secondblob_changed(self, file_path):
        if self.wait_until_file_is_ready(file_path):
            if 'secondblob' in file_path:
                globalvars.ini_changed_by_server = True
                new_ini = ""
                with open('emulator.ini', 'r') as f:
                    mainini = f.readlines()
                for line in mainini:
                    if line.startswith("steam_date=") or line.startswith("steam_time="):
                        line = ';' + line
                    new_ini = new_ini + line
                with open('emulator.ini', 'w') as g:
                    g.write(new_ini)
                shutil.copy2("emulator.ini", "files/cache/emulator.ini.cache")
            utils.check_secondblob_changed()
            self.mark_processing_done(file_path)

    def wrap_load_filesys_blob(self, file_path):
        if self.wait_until_file_is_ready(file_path):
            # ccdb.load_filesys_blob()
            if os.path.isfile("files/cache/firstblob.bin"): os.remove("files/cache/firstblob.bin")
            ccdb.load_ccdb()
            self.mark_processing_done(file_path)

    @staticmethod
    def wait_until_file_is_ready(file_path, retries=15, delay=1):
        for _ in range(retries):
            if not os.path.exists(file_path):
                # If the file doesn't exist, wait and retry
                time.sleep(delay)
                continue
            try:
                # Attempt to open the file in exclusive mode to check if it's still being written to
                with open(file_path, 'rb+') as file:
                    return True  # Successfully opened for writing, assume the file is ready
            except IOError:
                # If an IOError occurs, the file is likely still being written or is locked
                time.sleep(delay)

        return False  # File was not ready after retries


class DirectoryMonitor:
    def __init__(self, paths, directories_to_watch, event_handler_class=CustomEventHandler):
        self.paths = paths
        self.directories_to_watch = directories_to_watch
        self.event_handler_class = event_handler_class
        self.observer = Observer()

    def start(self):
        event_handler = self.event_handler_class(self.paths, self.directories_to_watch)
        for path in self.paths:
            watch_path = path if os.path.isdir(path) else os.path.dirname(path)
            self.observer.schedule(event_handler, watch_path, recursive=False)

        # Start observer in a new thread
        self.observer_thread = threading.Thread(target=self.observer.start)
        self.observer_thread.daemon = True  # Daemonize thread
        self.observer_thread.start()
        print("Monitoring started.")

    def stop(self):
        self.observer.stop()
        self.observer_thread.join()
        print("Monitoring stopped.")