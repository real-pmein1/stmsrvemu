import atexit

import os
import signal
import subprocess
import threading
import logging
import time
import globalvars
import config as configloader
from logger import shutdown_logging
from utilities.cdr_manipulator import cleanup_all_ephemeral_blobs

if globalvars.IS_WINDOWS:
    try:
        import win32api
        import msvcrt
        has_win32api = True
    except ImportError:
        has_win32api = False
else:
    import sys
    import select
    import termios
    import tty
    has_win32api = False

config = configloader.get_config()

# Store terminal settings for restoration on exit (Linux only)
_terminal_fd = None
_old_terminal_settings = None


def _restore_terminal():
    """Restore terminal settings on Unix/Linux."""
    global _old_terminal_settings, _terminal_fd
    if not globalvars.IS_WINDOWS and _old_terminal_settings is not None:
        try:
            termios.tcsetattr(_terminal_fd, termios.TCSADRAIN, _old_terminal_settings)
        except Exception:
            pass

log = logging.getLogger('InputManager')

def kill_mariadb_process():
    if globalvars.mariadb_process is not None:
        mysqlpid = globalvars.mariadb_process.pid
        if globalvars.IS_WINDOWS:
            subprocess.call(['taskkill', '/F', '/PID', str(mysqlpid)])
        else:  # Linux
            os.kill(mysqlpid, signal.SIGTERM)
        log.info("MariaDB process terminated.")

def kill_apache():
    if globalvars.httpd_process is not None:
        httpdpid = globalvars.httpd_process.pid
        if globalvars.IS_WINDOWS:
            subprocess.call(['taskkill', '/F', '/PID', str(httpdpid)])
        else:  # Linux
            os.kill(httpdpid, signal.SIGTERM)
        log.info("HTTPD process terminated.")
    if globalvars.httpd_child_pid_list:
        for httpd_children in globalvars.httpd_child_pid_list:
            if httpd_children is not None:
                if globalvars.IS_WINDOWS:
                    subprocess.call(['taskkill', '/F', '/PID', str(httpd_children.pid)])
                else:  # Linux
                    os.kill(httpd_children.pid, signal.SIGTERM)
        log.info("HTTPD child processes terminated.")

def signal_handler(sig, frame):
    log.info('Shutting down servers...')

    # Set global shutdown flag
    globalvars.shutdown_requested = True

    # Clean up ephemeral blobs before shutdown
    try:
        cleanup_all_ephemeral_blobs()
    except Exception as e:
        log.warning(f"Error cleaning up ephemeral blobs: {e}")

    # Stop watchdog first to prevent restart attempts during shutdown
    try:
        from utilities.thread_handler import stop_watchdog
        stop_watchdog()
    except Exception:
        pass

    # Stop console manager if it's running
    try:
        from utilities.console_manager import stop_console_manager
        stop_console_manager()
    except ImportError:
        pass

    for server in globalvars.servers:
        server.cleanup()
    if config['use_builtin_mysql'].lower() == 'true':
        kill_mariadb_process()
    kill_apache()

    log.info('Server shutdown complete.')

    # Restore terminal settings before exit (critical for Linux)
    _restore_terminal()

    # Flush all pending log messages before exiting
    shutdown_logging()

    os._exit(0)

def ctrl_break_handler(dwCtrlType):
    if dwCtrlType in (0, 1, 2):  # CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT
        signal_handler(signal.SIGBREAK, None)
    return True

def watch_for_shutdown():
    # Wait a bit for console manager to initialize if it's going to be started
    time.sleep(2)
    
    # Check if console manager is running and defer to it for input handling
    try:
        from utilities.console_manager import get_console_manager
        console_mgr = get_console_manager()
        if console_mgr and console_mgr.running:
            # Console manager is handling input, just wait for shutdown signal
            log.info("Input manager deferring to console manager for input handling")
            while console_mgr.running and not getattr(globalvars, 'shutdown_requested', False):
                time.sleep(1)
            return
    except ImportError:
        pass
    
    print("")
    print("Press ESC to shut down the server...")
    print("")
    
    # Fallback to original escape key monitoring
    if globalvars.IS_WINDOWS:
        while True:
            try:
                if msvcrt.kbhit() and msvcrt.getch() == b'\x1b':
                    signal_handler(signal.SIGINT, None)
                time.sleep(0.1)
            except Exception:
                break
    else:
        global _terminal_fd, _old_terminal_settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        # Store for restoration on exit
        _terminal_fd = fd
        _old_terminal_settings = old_settings
        tty.setcbreak(fd)
        try:
            while True:
                dr, _, _ = select.select([sys.stdin], [], [], 0.1)
                if dr:
                    char = sys.stdin.read(1)
                    if char == '\x1b':
                        # Check if more characters follow (arrow key sequence)
                        # Arrow keys send: ESC [ A/B/C/D
                        if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                            # More data available - this is an escape sequence, not standalone ESC
                            # Consume the rest of the sequence to avoid leaving garbage in buffer
                            next_char = sys.stdin.read(1)
                            if next_char == '[':
                                # CSI sequence - read one more character (arrow key code)
                                if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                    sys.stdin.read(1)  # Consume A/B/C/D
                            # Not a standalone ESC, continue loop
                        else:
                            # No more data - this is a standalone ESC key press
                            signal_handler(signal.SIGINT, None)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def start_watchescape_thread():
    atexit.register(kill_mariadb_process)
    atexit.register(kill_apache)
    atexit.register(cleanup_all_ephemeral_blobs)  # Clean ephemeral blobs on exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if globalvars.IS_WINDOWS:
        signal.signal(signal.SIGBREAK, signal_handler)
        if has_win32api:
            win32api.SetConsoleCtrlHandler(ctrl_break_handler, True)

    thread = threading.Thread(target=watch_for_shutdown)
    thread.daemon = True
    thread.start()
