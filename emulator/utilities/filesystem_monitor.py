import logging
import os
import sys
import threading
import time
import shutil
import hashlib

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import utils
import globalvars
from config import get_config as read_config
from utilities.database import ccdb
import utilities.blobs

log = logging.getLogger('FileMonitor')

# Suppress noisy debug logging from watchdog's internal inotify components on Linux
# These log IN_OPEN, IN_ISDIR, IN_ACCESS events that we don't care about
for _logger_name in ('watchdog.observers.inotify_buffer',
                      'watchdog.observers.inotify',
                      'watchdog.observers.inotify_c'):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

config = read_config()

# Define the extensions to watch within directories
WATCHED_EXTENSIONS = {'.bin', '.py', '.xml', '.json'}


def _get_file_mtime_size(file_path):
    """Get file mtime and size for quick change detection."""
    try:
        stat = os.stat(file_path)
        return (stat.st_mtime, stat.st_size)
    except OSError:
        return (None, None)


def _compute_file_hash(file_path):
    """Compute MD5 hash of a file."""
    md5_hash = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except OSError:
        return None


def get_file_size_and_hash(file_path, cached_info=None):
    """
    Returns (mtime, size, md5hash) for the given file.
    Uses mtime/size short-circuit: only computes hash if mtime or size changed.
    cached_info: optional (mtime, size, hash) tuple from previous call.
    """
    if not os.path.isfile(file_path):
        return (None, None, None)

    mtime, size = _get_file_mtime_size(file_path)

    # Short-circuit: if mtime and size are unchanged, reuse cached hash
    if cached_info and len(cached_info) >= 3:
        old_mtime, old_size, old_hash = cached_info[0], cached_info[1], cached_info[2]
        if mtime == old_mtime and size == old_size and old_hash is not None:
            return (mtime, size, old_hash)

    # Compute hash only when mtime/size changed
    file_hash = _compute_file_hash(file_path)
    return (mtime, size, file_hash)


def load_directory_info(directory, cached_info=None):
    """
    Returns a dict of { file_path: (mtime, size, md5hash) } for all files in the directory
    that match WATCHED_EXTENSIONS.
    Uses cached_info to short-circuit hash computation when mtime/size unchanged.
    """
    cached_info = cached_info or {}
    info_map = {}
    for entry in os.scandir(directory):
        if entry.is_file():
            _, ext = os.path.splitext(entry.path)
            if ext.lower() in WATCHED_EXTENSIONS:
                cached = cached_info.get(entry.path)
                info_map[entry.path] = get_file_size_and_hash(entry.path, cached)
    return info_map


class CustomEventHandler(FileSystemEventHandler):
    def __init__(self, paths_to_monitor, directories_to_watch):
        super().__init__()
        # Separate files and directories
        self.files_to_monitor = set()
        self.directories_to_watch = set()

        # Normalize + separate file paths vs. directory paths
        for path in paths_to_monitor:
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                self.files_to_monitor.add(abs_path)
            elif os.path.isdir(abs_path):
                self.directories_to_watch.add(abs_path)

        # Also include the extra directories passed in
        for d in directories_to_watch:
            self.directories_to_watch.add(os.path.abspath(d))

        # ========== METADATA STORAGE ==========
        # Store size/hash info for each monitored file
        self.monitored_file_info = {}
        # For directories, store a dict of {file_path: (size, md5hash)}
        self.monitored_directory_info = {}

        # Initialize metadata
        self._initialize_metadata()

        self.last_handled = {}   # Tracks the last handled time for each file individually
        self.debounce_seconds = 10
        self.lock = threading.RLock()
        self.working_now = False
        self.processing = set()  # Tracks files that are currently being processed

        # Directory scan batching/debouncing
        self._pending_dir_events = {}  # {directory: (last_event_time, event_type)}
        self._dir_batch_delay = 2.0  # Seconds to wait before processing batched dir events
        self._dir_batch_timer = None
        self._dir_batch_lock = threading.Lock()

    def _initialize_metadata(self):
        """
        Sets up the initial file info for each specific file and each directory.
        """
        for fpath in self.files_to_monitor:
            self.monitored_file_info[fpath] = get_file_size_and_hash(fpath)

        for dpath in self.directories_to_watch:
            self.monitored_directory_info[dpath] = load_directory_info(dpath)

    def _refresh_file_metadata(self, file_path):
        """
        Updates the metadata for a single file. Returns True if there was a change,
        False otherwise. Uses mtime/size short-circuit to avoid unnecessary hashing.
        """
        old_info = self.monitored_file_info.get(file_path)
        new_info = get_file_size_and_hash(file_path, old_info)
        self.monitored_file_info[file_path] = new_info

        # Compare (mtime, size, hash) - if hash is same, no real change
        if old_info is None:
            return new_info[0] is not None  # File appeared
        if new_info[0] is None:
            return True  # File disappeared

        # Check if hash actually changed (mtime/size changes don't matter if hash is same)
        return old_info[2] != new_info[2] if len(old_info) >= 3 and len(new_info) >= 3 else old_info != new_info

    def _refresh_directory_metadata(self, directory_path):
        """
        Updates the metadata for every file in a directory. Returns True if at least one
        file changed (added/removed or hash changed), otherwise False.
        Uses cached mtime/size to short-circuit hash computation.
        """
        old_info_map = self.monitored_directory_info.get(directory_path, {})
        new_info_map = load_directory_info(directory_path, old_info_map)

        # Compare sets to detect new or deleted files
        old_files = set(old_info_map.keys())
        new_files = set(new_info_map.keys())

        added_files = new_files - old_files
        removed_files = old_files - new_files
        changed = False

        # If any file was added or removed, mark changed = True
        if added_files or removed_files:
            changed = True

        # Compare hash only for existing files (mtime/size changes without hash change don't matter)
        if not changed:
            for common_file in (old_files & new_files):
                old_hash = old_info_map[common_file][2] if len(old_info_map[common_file]) >= 3 else None
                new_hash = new_info_map[common_file][2] if len(new_info_map[common_file]) >= 3 else None
                if old_hash != new_hash:
                    changed = True
                    break

        # Update stored info
        self.monitored_directory_info[directory_path] = new_info_map

        return changed

    # ========================
    # Watchdog Event Handlers
    # ========================

    def on_modified(self, event):
        file_path = os.path.normpath(event.src_path)

        # If it's a specific file being monitored
        if self._is_specific_file(file_path):
            # Debounce + check if file contents actually changed
            if not event.is_directory and not self.working_now:
                # Check for real changes first
                if self._refresh_file_metadata(file_path):
                    # There's an actual change in file size/hash
                    self.working_now = True
                    self.handle_blob_on_modified(event)
                else:
                    log.debug(f"Ignored modified file event: No real change in {file_path}")

        elif self._is_watched_directory_event(event):
            # It's a directory we care about, check extension if needed
            if not event.is_directory and self._has_watched_extension(file_path):
                changed = self._refresh_relevant_directory(file_path)
                if changed:
                    self.handle_directory_event(event, 'modified')
                else:
                    log.debug(f"Ignored modified directory event: No real change in {file_path}")

    def on_created(self, event):
        file_path = os.path.normpath(event.src_path)
        if os.path.join("files", "firstblob.") in file_path or os.path.join("files", "secondblob.") in file_path:
            self.working_now = True
            self.handle_blob_on_modified(event)
            
    def on_deleted(self, event):
        file_path = os.path.normpath(event.src_path)
        if self._is_watched_directory_event(event):
            if self._has_watched_extension(file_path):
                changed = self._refresh_relevant_directory(file_path)
                if changed:
                    self.handle_directory_event(event, 'deleted')
                else:
                    log.debug(f"Ignored deleted directory event: No real change in {file_path}")

    def on_moved(self, event):
        src_path = os.path.normpath(event.src_path)
        dest_path = os.path.normpath(event.dest_path)

        if self._is_specific_file(src_path) or self._is_specific_file(dest_path):
            # Refresh both src and dest in case the path changed
            if not event.is_directory and not self.working_now:
                src_changed = self._refresh_file_metadata(src_path)
                dest_changed = self._refresh_file_metadata(dest_path)
                if src_changed or dest_changed:
                    self.working_now = True
                    self.handle_blob_on_modified(event)
                else:
                    log.debug(f"Ignored move file event: No real change in {src_path} -> {dest_path}")

        elif self._is_watched_directory_event(event):
            if (self._has_watched_extension(src_path) or
                self._has_watched_extension(dest_path)):
                changed1 = self._refresh_relevant_directory(src_path)
                changed2 = self._refresh_relevant_directory(dest_path)
                if changed1 or changed2:
                    self.handle_directory_event(event, 'moved')
                else:
                    log.debug(f"Ignored move directory event: No real change from {src_path} to {dest_path}")

    def _is_specific_file(self, file_path):
        return file_path in self.files_to_monitor

    def _is_watched_directory_event(self, event):
        # Check if the event is within any of the watched directories
        for directory in self.directories_to_watch:
            try:
                if os.path.commonpath([directory, event.src_path]) == directory:
                    return True
            except ValueError:
                # Edge case if the paths have no common prefix
                pass
        return False

    def _has_watched_extension(self, file_path):
        _, ext = os.path.splitext(file_path)
        return ext.lower() in WATCHED_EXTENSIONS

    def _refresh_relevant_directory(self, file_path):
        """
        Figures out which directory in self.directories_to_watch the file_path belongs to
        and refreshes the metadata for that directory.
        Returns True if there were changes, False otherwise.
        """
        for directory in self.directories_to_watch:
            try:
                if os.path.commonpath([directory, file_path]) == directory:
                    return self._refresh_directory_metadata(directory)
            except ValueError:
                pass
        return False

    # ================
    # Debounce Helpers
    # ================

    def _schedule_batch_dir_processing(self):
        """Schedule batch processing of pending directory events after delay."""
        with self._dir_batch_lock:
            if self._dir_batch_timer is not None:
                self._dir_batch_timer.cancel()
            self._dir_batch_timer = threading.Timer(
                self._dir_batch_delay,
                self._process_batched_dir_events
            )
            self._dir_batch_timer.daemon = True
            self._dir_batch_timer.start()

    def _process_batched_dir_events(self):
        """Process all pending directory events in a single batch."""
        with self._dir_batch_lock:
            self._dir_batch_timer = None
            if not self._pending_dir_events:
                return

            # Take a snapshot and clear pending
            pending = dict(self._pending_dir_events)
            self._pending_dir_events.clear()

        # Process each unique directory once
        for directory, (_, event_type) in pending.items():
            changed = self._refresh_directory_metadata(directory)
            if changed:
                log.debug(f"Batch processing: {event_type} in {directory}")
                self.wrap_reload_blobs()

    def _queue_directory_event(self, directory, event_type):
        """Queue a directory event for batch processing."""
        with self._dir_batch_lock:
            self._pending_dir_events[directory] = (time.monotonic(), event_type)
        self._schedule_batch_dir_processing()

    def should_handle_file(self, file_path, current_time):
        with self.lock:
            if (file_path not in self.last_handled or
                current_time - self.last_handled.get(file_path, 0) >= self.debounce_seconds) \
                    and file_path not in self.processing:
                self.last_handled[file_path] = current_time
                self.processing.add(file_path)
                return True
            return False

    def mark_processing_done(self, file_path):
        """Mark the file's processing as completed."""
        with self.lock:
            self.processing.discard(file_path)

    # =====================
    # Custom Logic Handlers
    # =====================

    def handle_directory_event(self, event, event_type):
        file_path = os.path.normpath(event.src_path)
        log.debug(f"NOTICE: Detected {event_type} event in directory: {file_path}")

        # Find which monitored directory this file belongs to
        target_dir = None
        for directory in self.directories_to_watch:
            try:
                if os.path.commonpath([directory, file_path]) == directory:
                    target_dir = directory
                    break
            except ValueError:
                pass

        if target_dir:
            # Queue for batch processing instead of immediate handling
            self._queue_directory_event(target_dir, event_type)

    def handle_blob_on_modified(self, event):
        # Skip processing if shutdown is in progress
        if getattr(globalvars, 'shutdown_requested', False):
            return
        file_path = os.path.normpath(event.src_path)
        current_time = time.monotonic()
        log.debug(f"NOTICE: Detected change in file: {file_path}")
        if self.should_handle_file(file_path, current_time):
            # Original logic from your code
            if "firstblob.bin" in file_path:
                self.wrap_load_filesys_blob(file_path)
            else:
                self.wrap_check_secondblob_changed(file_path)
        self.working_now = False

    # =================
    # Wrapper Functions
    # =================

    def wrap_reload_blobs(self):
        # Example from your code
        cache_dir = os.path.join('files', 'cache')
        blobhash = os.path.join(cache_dir, 'blobhash')
        if os.path.isfile(blobhash):
            os.remove(blobhash)
        utils.check_secondblob_changed()

    def restart_program(self):
        print("Restarting...")
        # Set shutdown flag BEFORE execv to prevent watchdog from scheduling new work
        globalvars.shutdown_requested = True
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def wrap_check_secondblob_changed(self, file_path):
        # Skip processing if shutdown is in progress
        if getattr(globalvars, 'shutdown_requested', False):
            self.mark_processing_done(file_path)
            return
        if self.wait_until_file_is_ready(file_path):
            if 'secondblob' in file_path:
                globalvars.ini_changed_by_server = True
                new_ini = ""
                with open('emulator.ini', 'r') as f:
                    mainini = f.readlines()
                for line in mainini:
                    if line.startswith("steam_date=") or line.startswith("steam_time="):
                        line = ';' + line
                    new_ini += line
                with open('emulator.ini', 'w') as g:
                    g.write(new_ini)
            elif 'emulator' in file_path:
                with open('emulator.ini', 'r') as f:
                    mainini = f.readlines()
                with open('files/cache/emulator.ini.cache', 'r') as h:
                    cacheini = h.readlines()

                ini_list = []
                cache_list = []
                for line in mainini:
                    if ";" in line:
                        line = line[:line.index(";")]
                    if "\t" in line:
                        line = line[:line.index("\t")]
                    ini_list.append(line)
                for line in cacheini:
                    if ";" in line:
                        line = line[:line.index(";")]
                    if "\t" in line:
                        line = line[:line.index("\t")]
                    cache_list.append(line)

                file_altered = False
                for line1 in ini_list:
                    if "port" in line1 or "ip" in line1 or "http_domainname" in line1 or "enable_steam3_servers" in line1:
                        lineP1, lineP2 = line1.split("=")
                        for line2 in cache_list:
                            if (line2.startswith(lineP1 + "=") or line2.startswith(lineP1[1:] + "=")) and not line2.startswith(";" + lineP1[1:] + "="):
                                if line1 != line2:
                                    file_altered = True
                                break

                if file_altered:
                    self.restart_program()

                # NOTE: Don't delete blob files here - let utils.check_secondblob_changed()
                # handle the comparison and proper cache invalidation. Premature deletion
                # causes "secondblob not found" errors when database rebuild fails.
                # The firstblob.bin can be deleted since ccdb.neuter_ccdb() will recreate it.
                for line in mainini:
                    if line.startswith("steam_date=") or line.startswith("steam_time="):
                        if os.path.isfile(os.path.join("files", "firstblob.bin")):
                            os.remove(os.path.join("files", "firstblob.bin"))
                        # Don't delete secondblob.bin here - it's needed as fallback if DB fails
                        break  # Only need to check once, not for every line

            shutil.copy2("emulator.ini", os.path.join("files", "cache", "emulator.ini.cache"))
            lanClientPath = os.path.join(config["web_root"], "client", "steam_client_lan32")
            wanClientPath = os.path.join(config["web_root"], "client", "steam_client_wan32")
            if os.path.isfile(lanClientPath):
                os.remove(lanClientPath)
            if os.path.isfile(wanClientPath):
                os.remove(wanClientPath)
            utils.check_secondblob_changed()
            self.mark_processing_done(file_path)

    def wrap_load_filesys_blob(self, file_path):
        if self.wait_until_file_is_ready(file_path):
            firstblob_path = os.path.join("files", "cache", "firstblob.bin")
            if os.path.isfile(firstblob_path):
                os.remove(firstblob_path)
            ccdb.load_ccdb()
            self.mark_processing_done(file_path)

    @staticmethod
    def wait_until_file_is_ready(file_path, retries=15, delay=1):
        """
        Checks if the file is still locked/written by another process.
        """
        for _ in range(retries):
            if not os.path.exists(file_path):
                time.sleep(delay)
                continue
            try:
                with open(file_path, 'rb+') as file:
                    return True  # Opened successfully in write mode
            except IOError:
                time.sleep(delay)
        return False


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
            # Set recursive=False or True as needed
            self.observer.schedule(event_handler, watch_path, recursive=False)

        # Start observer in a new thread
        self.observer_thread = threading.Thread(target=self.observer.start)
        self.observer_thread.daemon = True
        self.observer_thread.start()
        print("Monitoring started.")

    def stop(self):
        self.observer.stop()
        self.observer_thread.join()
        print("Monitoring stopped.")
