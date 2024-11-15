import importlib
import importlib.util
import logging
import os
import sys
import threading
import time

import globalvars

log = logging.getLogger('threadhndl')

def start_server_thread(server_instance, identifier, print_name):
    server_instance.daemon = True
    server_instance.start()
    globalvars.server_threads[identifier] = server_instance
    if print_name:
        try:
            log.info(f"{print_name} listening on port {server_instance.port}")
        except:
            log.info(f"{print_name} Started")


def stop_server_thread(identifier):
    thread = globalvars.server_threads.get(identifier)
    if thread:
        thread.stop()
        thread.join()  # Wait for the thread to finish
        del globalvars.server_threads[identifier]
        print(f"Stopped thread '{identifier}'.")
    else:
        print(f"No thread found with identifier '{identifier}'.")



def reload_module(module):
    # Recursively reload all submodules
    reloaded_modules = set()

    def _reload(module):
        if module in reloaded_modules:
            return
        reloaded_modules.add(module)
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isinstance(attribute, type(sys)) and attribute.__name__.startswith(module.__name__):
                _reload(attribute)
        importlib.reload(module)

    _reload(module)


def reload_server_thread(identifier):
    stop_server_thread(identifier)

    if getattr(sys, 'frozen', False):
        # If running as a compiled executable, skip reloading the script
        log.info(f"Running as a compiled executable. Restarting {identifier} without reloading script.")
        module_name = None
        module = None
    else:
        script_path = identifier + "_script_path"
        script_path = globalvars.config[script_path]
        module_name = os.path.splitext(os.path.basename(script_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        reload_module(module)  # Recursively reload the module and its dependencies

    if module_name and module:
        server_class_name = module_name.capitalize()  # Assuming class name matches file name
        server_class = getattr(module, server_class_name)
    else:
        server_class_name = identifier.lower()
        server_class = globals()[server_class_name]

    port = int(globalvars.config[f'{identifier.lower()}_server_port'])
    server_instance = server_class(port, globalvars.config)

    start_server_thread(server_instance, identifier, server_class_name)
    log.info(f"Reloaded and restarted {identifier}")


def start_watchdog():
    watchdog = Watchdog(check_interval=5)  # Check every 5 seconds
    watchdog.start()
    globalvars.watchdog = watchdog  # Store the watchdog instance if needed

def stop_watchdog():
    if hasattr(globalvars, 'watchdog'):
        globalvars.watchdog.stop()
        globalvars.watchdog.join()

class Watchdog(threading.Thread):
    def __init__(self, check_interval=5):
        super().__init__()
        self.check_interval = check_interval  # Time in seconds between checks
        self.daemon = True  # Daemonize the watchdog thread
        self.stop_event = threading.Event()
        self.log = logging.getLogger('watchdog')

    def run(self):
        self.log.info("Watchdog started.")
        while not self.stop_event.is_set():
            for identifier, thread in list(globalvars.server_threads.items()):
                if not thread.is_alive():
                    self.log.error(f"Thread '{identifier}' has stopped unexpectedly.")
                    # Optionally, check if the thread has an exception attribute
                    if hasattr(thread, 'exception') and thread.exception:
                        self.log.error(f"Thread '{identifier}' terminated due to exception: {thread.exception}")
                    # Attempt to restart the thread
                    self.restart_thread(identifier)
            time.sleep(self.check_interval)
        self.log.info("Watchdog stopping.")

    def restart_thread(self, identifier):
        self.log.info(f"Attempting to restart thread '{identifier}'.")
        try:
            # Use the existing reload_server_thread function to restart
            reload_server_thread(identifier)
            self.log.info(f"Thread '{identifier}' restarted successfully.")
        except Exception as e:
            self.log.error(f"Failed to restart thread '{identifier}': {e}", exc_info=True)

    def stop(self):
        self.stop_event.set()