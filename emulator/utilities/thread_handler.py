import importlib
import importlib.util
import inspect
import logging
import os
import sys
import threading
import time

import globalvars

log = logging.getLogger('threadhndl')

# Store metadata about each server for restart capability
server_registry = {}


class ServerMetadata:
    """Stores all information needed to restart a server."""
    def __init__(self, server_instance, identifier, print_name, extra_args=None):
        self.identifier = identifier
        self.print_name = print_name
        self.server_class = type(server_instance)
        self.class_name = self.server_class.__name__
        self.module_name = self.server_class.__module__
        self.extra_args = extra_args or {}
        # Get port from instance attribute, or fall back to extra_args if not found
        # This handles plain threading.Thread wrappers like FTPUpdateServer
        self.port = getattr(server_instance, 'port', None) or self.extra_args.get('port')
        self.config = getattr(server_instance, 'config', None)

        # Get the source file of the server class
        try:
            self.source_file = inspect.getfile(self.server_class)
        except (TypeError, OSError):
            self.source_file = None


def start_server_thread(server_instance, identifier, print_name, extra_args=None):
    """
    Start a server thread and register its metadata for potential restart.

    Args:
        server_instance: The server instance to start
        identifier: Unique string identifier for the server
        print_name: Human-readable name for logging (or None to skip)
        extra_args: Optional dict of extra constructor arguments beyond (port, config)
                   e.g., {'master_server': master_server_instance}
    """
    server_instance.daemon = True
    server_instance.start()
    globalvars.server_threads[identifier] = server_instance

    # Store metadata for restart capability
    server_registry[identifier] = ServerMetadata(server_instance, identifier, print_name, extra_args)

    if print_name:
        try:
            log.info(f"{print_name} listening on port {server_instance.port}")
        except:
            log.info(f"{print_name} Started")


def stop_server_thread(identifier):
    """Stop a server thread by its identifier."""
    thread = globalvars.server_threads.get(identifier)
    if thread:
        try:
            # Try graceful stop first
            if hasattr(thread, 'stop'):
                thread.stop()
            if hasattr(thread, 'shutdown'):
                thread.shutdown()
            if hasattr(thread, 'cleanup'):
                thread.cleanup()
        except Exception as e:
            log.warning(f"Error during graceful stop of '{identifier}': {e}")

        try:
            thread.join(timeout=5)  # Wait up to 5 seconds for thread to finish
        except Exception as e:
            log.warning(f"Error joining thread '{identifier}': {e}")

        if identifier in globalvars.server_threads:
            del globalvars.server_threads[identifier]
        log.info(f"Stopped thread '{identifier}'.")
    else:
        log.warning(f"No thread found with identifier '{identifier}'.")


def reload_module_by_name(module_name):
    """
    Reload a module and its submodules by name.
    Returns the reloaded module.
    """
    if module_name not in sys.modules:
        log.warning(f"Module '{module_name}' not in sys.modules, cannot reload")
        return None

    module = sys.modules[module_name]
    reloaded_modules = set()

    def _reload(mod):
        if mod in reloaded_modules:
            return
        reloaded_modules.add(mod)

        # Reload submodules first
        for attribute_name in dir(mod):
            try:
                attribute = getattr(mod, attribute_name)
                if isinstance(attribute, type(sys)) and attribute.__name__.startswith(mod.__name__):
                    _reload(attribute)
            except Exception:
                pass

        try:
            importlib.reload(mod)
        except Exception as e:
            log.warning(f"Failed to reload module {mod.__name__}: {e}")

    _reload(module)
    return sys.modules.get(module_name)


def reload_steam3_modules():
    """
    Reload all steam3 modules in the correct order, similar to how they load during initial start.
    This is used for CM server hot reloading.

    Returns:
        tuple: (success: bool, message: str, count: int)
    """
    if getattr(sys, 'frozen', False):
        return False, "Running as compiled executable, module reload not supported", 0

    # Get all loaded steam3 modules
    steam3_modules = [name for name in sys.modules.keys() if name.startswith('steam3')]

    if not steam3_modules:
        return False, "No steam3 modules found in sys.modules", 0

    log.info(f"Hot reloading {len(steam3_modules)} steam3 modules...")

    # Sort modules by depth (deepest first) to handle dependencies correctly
    # e.g., steam3.Handlers.authentication should reload before steam3.Handlers before steam3
    def module_depth(name):
        return name.count('.')

    steam3_modules_sorted = sorted(steam3_modules, key=module_depth, reverse=True)

    reloaded_count = 0
    failed_modules = []

    # First pass: reload all leaf modules (deepest in hierarchy)
    for module_name in steam3_modules_sorted:
        if module_name not in sys.modules:
            continue

        try:
            module = sys.modules[module_name]
            # Skip modules without a file (built-ins, namespace packages without __init__.py)
            if not hasattr(module, '__file__') or module.__file__ is None:
                continue

            importlib.reload(module)
            reloaded_count += 1
            log.debug(f"Reloaded: {module_name}")
        except Exception as e:
            failed_modules.append((module_name, str(e)))
            log.warning(f"Failed to reload {module_name}: {e}")

    # Second pass: re-import the main steam3 module and its key components
    # to ensure all handlers are properly re-registered
    try:
        # Re-import the main steam3 __init__ to reset managers
        if 'steam3' in sys.modules:
            importlib.reload(sys.modules['steam3'])
            log.info("Reloaded steam3 __init__.py")

        # Re-import cmserver_base to rebuild handler registry
        if 'steam3.cmserver_base' in sys.modules:
            importlib.reload(sys.modules['steam3.cmserver_base'])
            log.info("Reloaded steam3.cmserver_base")

        # Re-import CM server implementations
        for cm_module in ['steam3.cmserver_tcp', 'steam3.cmserver_udp']:
            if cm_module in sys.modules:
                importlib.reload(sys.modules[cm_module])
                log.info(f"Reloaded {cm_module}")

    except Exception as e:
        log.error(f"Error during final steam3 re-import: {e}")
        return False, f"Partial reload completed but final re-import failed: {e}", reloaded_count

    if failed_modules:
        failed_list = ', '.join([m[0] for m in failed_modules[:5]])
        if len(failed_modules) > 5:
            failed_list += f" and {len(failed_modules) - 5} more"
        return True, f"Reloaded {reloaded_count} modules with {len(failed_modules)} failures: {failed_list}", reloaded_count

    return True, f"Successfully reloaded {reloaded_count} steam3 modules", reloaded_count


def restart_server(identifier, reload_code=False):
    """
    Restart a server by its identifier.

    Args:
        identifier: The server identifier
        reload_code: If True, reload the module from disk (for code changes).
                    If False, just restart with the existing code.

    Returns:
        True if successful, False otherwise
    """
    if identifier not in server_registry:
        log.error(f"No metadata found for server '{identifier}'. Cannot restart.")
        log.info(f"Available servers: {list(server_registry.keys())}")
        return False

    # Special handling for FTPUpdateServer on Linux without root privileges
    if identifier == 'FTPUpdateServer':
        ftp_port = int(globalvars.config['ftp_server_port'])
        if sys.platform.startswith('linux') and ftp_port < 1024 and os.geteuid() != 0:
            log.info(f"Skipping restart of FTPUpdateServer: privileged port {ftp_port} requires root.")
            # Mark as disabled to prevent future restart attempts
            if not hasattr(globalvars, 'disabled_servers'):
                globalvars.disabled_servers = set()
            globalvars.disabled_servers.add('FTPUpdateServer')
            # Remove from registries
            if identifier in globalvars.server_threads:
                del globalvars.server_threads[identifier]
            if identifier in server_registry:
                del server_registry[identifier]
            return False

    metadata = server_registry[identifier]
    log.info(f"Restarting server '{identifier}' ({metadata.class_name})...")

    # Stop the existing thread
    stop_server_thread(identifier)

    # Get the server class (potentially reloading the module)
    server_class = metadata.server_class

    if reload_code and not getattr(sys, 'frozen', False):
        # Reload the module to pick up code changes
        log.info(f"Reloading module '{metadata.module_name}'...")
        try:
            reloaded_module = reload_module_by_name(metadata.module_name)
            if reloaded_module:
                # Get the updated class from the reloaded module
                server_class = getattr(reloaded_module, metadata.class_name)
                log.info(f"Module '{metadata.module_name}' reloaded successfully.")
            else:
                log.warning(f"Could not reload module, using existing class.")
        except Exception as e:
            log.error(f"Failed to reload module '{metadata.module_name}': {e}")
            log.info("Using existing class definition.")
    elif getattr(sys, 'frozen', False):
        log.info("Running as compiled executable, skipping module reload.")

    # Create new server instance
    try:
        # Special handling for plain threading.Thread wrappers (like FTPUpdateServer)
        # These are Thread objects that wrap a function, not subclasses with their own logic
        if server_class is threading.Thread:
            # Handle FTPUpdateServer specially - it's a plain Thread wrapping create_ftp_server
            if identifier == 'FTPUpdateServer':
                from steamweb.ftp import create_ftp_server
                config = globalvars.config
                new_instance = threading.Thread(
                    target=create_ftp_server,
                    args=(
                        os.path.join("files", "temp"),
                        os.path.join("files", "beta1_ftp"),
                        globalvars.server_ip,
                        int(config['ftp_server_port'])
                    )
                )
            else:
                log.error(f"Cannot restart plain Thread-based server '{identifier}': no restart handler defined.")
                return False
        elif hasattr(server_class, '__mro__') and threading.Thread in server_class.__mro__:
            # This is a class that inherits from threading.Thread (like NetworkHandler subclasses)
            # These have proper constructors and can be instantiated normally
            port = metadata.port
            config = metadata.config or globalvars.config

            # Check the constructor signature to determine arguments
            sig = inspect.signature(server_class.__init__)
            params = list(sig.parameters.keys())

            # Build kwargs based on what the constructor accepts
            kwargs = {}
            args = []

            # Handle positional args (port, config are typically first)
            if 'port' in params:
                kwargs['port'] = port
            elif len(params) > 1:  # First param after 'self'
                args.append(port)

            if 'config' in params or 'in_config' in params:
                param_name = 'config' if 'config' in params else 'in_config'
                kwargs[param_name] = config
            elif len(params) > 2:  # Second param after 'self' and port
                args.append(config)

            # Add any extra arguments (like master_server for CM servers)
            if metadata.extra_args:
                for key, value in metadata.extra_args.items():
                    if key in params:
                        kwargs[key] = value

            # Create the instance
            log.debug(f"Creating Thread-based server '{identifier}' with args={args}, kwargs={kwargs}")
            if kwargs:
                new_instance = server_class(*args, **kwargs)
            else:
                new_instance = server_class(port, config)
        else:
            # Build constructor arguments for normal server classes
            port = metadata.port
            config = metadata.config or globalvars.config

            # Check the constructor signature to determine arguments
            sig = inspect.signature(server_class.__init__)
            params = list(sig.parameters.keys())

            # Build kwargs based on what the constructor accepts
            kwargs = {}
            args = []

            # Handle positional args (port, config are typically first)
            if 'port' in params:
                kwargs['port'] = port
            elif len(params) > 1:  # First param after 'self'
                args.append(port)

            if 'config' in params:
                kwargs['config'] = config
            elif len(params) > 2:  # Second param after 'self' and port
                args.append(config)

            # Add any extra arguments
            if metadata.extra_args:
                for key, value in metadata.extra_args.items():
                    if key in params:
                        kwargs[key] = value
                    else:
                        # Try adding as positional if it's expected
                        pass

            # Create the instance
            if kwargs:
                new_instance = server_class(*args, **kwargs)
            else:
                new_instance = server_class(port, config)

        # Start the new server
        start_server_thread(new_instance, identifier, metadata.print_name, metadata.extra_args)
        log.info(f"Server '{identifier}' restarted successfully.")
        return True

    except Exception as e:
        log.error(f"Failed to restart server '{identifier}': {e}", exc_info=True)
        return False


def reload_server_thread(identifier):
    """
    Legacy function - reloads code and restarts a server.
    Use restart_server(identifier, reload_code=True) for explicit control.
    """
    return restart_server(identifier, reload_code=True)


def get_server_info(identifier=None):
    """
    Get information about registered servers.

    Args:
        identifier: If provided, get info for a specific server.
                   If None, get info for all servers.

    Returns:
        Dict of server information
    """
    if identifier:
        if identifier in server_registry:
            meta = server_registry[identifier]
            thread = globalvars.server_threads.get(identifier)
            return {
                'identifier': identifier,
                'class': meta.class_name,
                'module': meta.module_name,
                'port': meta.port,
                'source_file': meta.source_file,
                'print_name': meta.print_name,
                'is_alive': thread.is_alive() if thread else False,
                'extra_args': list(meta.extra_args.keys()) if meta.extra_args else []
            }
        return None

    # Return info for all servers
    result = {}
    for ident in server_registry:
        result[ident] = get_server_info(ident)
    return result


def list_servers():
    """Print a formatted list of all registered servers."""
    info = get_server_info()
    if not info:
        log.info("No servers registered.")
        return

    log.info("Registered servers:")
    for ident, data in info.items():
        status = "RUNNING" if data['is_alive'] else "STOPPED"
        log.info(f"  [{status}] {ident}: {data['class']} on port {data['port']}")


def get_restartable_servers():
    """
    Get a consolidated list of restartable servers.
    CM servers (CMTCP27014, CMTCP27017, CMUDP27014, CMUDP27017) are consolidated into "CMSERVER".

    Returns:
        list: List of server identifiers that can be restarted/reloaded
    """
    servers = list(server_registry.keys())
    # Consolidate CM servers into a single CMSERVER entry
    cm_servers = [s for s in servers if s.startswith('CMTCP') or s.startswith('CMUDP')]
    non_cm_servers = [s for s in servers if not (s.startswith('CMTCP') or s.startswith('CMUDP'))]
    if cm_servers:
        non_cm_servers.append('CMSERVER')
    return non_cm_servers


def is_cm_server(identifier):
    """Check if an identifier refers to a CM server (including consolidated CMSERVER)."""
    return identifier == 'CMSERVER' or identifier.startswith('CMTCP') or identifier.startswith('CMUDP')


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
            # Don't attempt restarts if shutdown has been requested
            if getattr(globalvars, 'shutdown_requested', False):
                self.log.info("Shutdown requested, watchdog stopping restart attempts.")
                break

            for identifier, thread in list(globalvars.server_threads.items()):
                # Double-check shutdown flag before each restart attempt
                if getattr(globalvars, 'shutdown_requested', False):
                    break

                # Skip servers that have been explicitly disabled
                if identifier in getattr(globalvars, 'disabled_servers', set()):
                    continue

                if not thread.is_alive():
                    self.log.error(f"Thread '{identifier}' has stopped unexpectedly.")
                    # Optionally, check if the thread has an exception attribute
                    if hasattr(thread, 'exception') and thread.exception:
                        self.log.error(f"Thread '{identifier}' terminated due to exception: {thread.exception}")
                    # Attempt to restart the thread (without code reload for crash recovery)
                    self.restart_thread(identifier)
            time.sleep(self.check_interval)
        self.log.info("Watchdog stopping.")

    def restart_thread(self, identifier):
        # Don't restart servers that have been explicitly disabled
        if identifier in getattr(globalvars, 'disabled_servers', set()):
            self.log.info(f"Thread '{identifier}' is disabled, skipping restart.")
            return

        self.log.info(f"Attempting to restart thread '{identifier}'.")
        try:
            # Use restart_server without code reload for crash recovery
            if restart_server(identifier, reload_code=False):
                self.log.info(f"Thread '{identifier}' restarted successfully.")
            else:
                self.log.error(f"Failed to restart thread '{identifier}'.")
        except Exception as e:
            self.log.error(f"Failed to restart thread '{identifier}': {e}", exc_info=True)

    def stop(self):
        self.stop_event.set()
