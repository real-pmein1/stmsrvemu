import atexit

import os
import signal
import subprocess
import threading
import logging
import time
import globalvars
import config as configloader

try:
    import win32api
    import msvcrt
    has_win32api = True
except ImportError:
    has_win32api = False
    pass

config = configloader.get_config()

log = logging.getLogger('InputManager')

def kill_mariadb_process():
    if globalvars.mariadb_process is not None:
        mysqlpid = globalvars.mariadb_process.pid
        if globalvars.current_os == 'Windows':
            subprocess.call(['taskkill', '/F', '/PID', str(mysqlpid)])
        else:  # Linux
            os.kill(mysqlpid, signal.SIGTERM)
        log.info("MariaDB process terminated.")

def kill_apache():
    if globalvars.httpd_process is not None:
        httpdpid = globalvars.httpd_process.pid
        if globalvars.current_os == 'Windows':
            subprocess.call(['taskkill', '/F', '/PID', str(httpdpid)])
        else:  # Linux
            os.kill(httpdpid, signal.SIGTERM)
        log.info("HTTPD process terminated.")
    if globalvars.httpd_child_pid_list:
        for httpd_children in globalvars.httpd_child_pid_list:
            if httpd_children is not None:
                if globalvars.current_os == 'Windows':
                    subprocess.call(['taskkill', '/F', '/PID', str(httpd_children.pid)])
                else:  # Linux
                    os.kill(httpd_children.pid, signal.SIGTERM)
        log.info("HTTPD child processes terminated.")

def signal_handler(sig, frame):
    log.info('Shutting down servers...')
    for server in globalvars.servers:
        server.cleanup()
    if config['use_builtin_mysql'].lower() == 'true':
        kill_mariadb_process()
    kill_apache()
    os._exit(0)

def ctrl_break_handler(dwCtrlType):
    if dwCtrlType in (0, 1, 2):  # CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT
        signal_handler(signal.SIGBREAK, None)
    return True

def watch_for_shutdown():
    if globalvars.current_os != 'Linux':
        escape_key_ord = ord('\x1b')  # Escape key ASCII value
        while True:
            # Check for Escape key press
            try:
                if msvcrt.kbhit() and msvcrt.getch() == b'\x1b':
                    signal_handler(signal.SIGINT, None)
                time.sleep(0.1)  # Small sleep to prevent busy-waiting
            except:
                break

def start_watchescape_thread():
    atexit.register(kill_mariadb_process)
    atexit.register(kill_apache)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if globalvars.current_os == 'Windows':
        signal.signal(signal.SIGBREAK, signal_handler)
        if has_win32api:
            win32api.SetConsoleCtrlHandler(ctrl_break_handler, True)

    thread = threading.Thread(target=watch_for_shutdown)
    thread.daemon = True
    thread.start()