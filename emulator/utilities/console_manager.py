#!/usr/bin/env python3
"""
Console Manager for Steam Emulator
Supports two modes:
- TUI Console (prompt_toolkit based) - default
- Simple Console (Ben's console) - set use_ben_console=true in config

Both consoles share the same command implementations via ConsoleCommandsBase.
"""

import logging
import os
import sys
import time
import threading
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import deque

import globalvars
from utilities import inputmanager
from logger import shutdown_logging
from utilities.cdr_manipulator import cleanup_all_ephemeral_blobs

# Check which console type to use
from config import get_config
_config = get_config()
USE_BEN_CONSOLE = _config.get('use_ben_console', 'false').lower() == 'true'

# ============================================================================
# SHARED CONSOLE COMMANDS BASE CLASS
# ============================================================================


class ConsoleCommandsBase:
    """
    Base class containing all console commands.
    Both SimpleConsoleManager and TUIConsoleManager inherit from this.
    Subclasses must implement _output() method for their specific output mechanism.
    """

    def __init__(self):
        self.log = logging.getLogger("ConsoleManager")
        self.log.setLevel(logging.WARNING)
        self.running = True

        # Shared command registry - all commands available in both console types
        self.commands = {
            'help': self.cmd_help,
            'status': self.cmd_status,
            'servers': self.cmd_servers,
            'restartserver': self.cmd_restart_server,
            'reloadserver': self.cmd_reload_server,
            'config': self.cmd_config,
            'blob': self.cmd_blob,
            'changeblob': self.cmd_changeblob,
            'loglevel': self.cmd_set_loglevel,
            'openlog': self.cmd_openlog,
            'info': self.cmd_info,
            'clear': self.cmd_clear,
            'ftpmenu': self.cmd_ftpmenu,
            'exit': self.cmd_exit,
            'quit': self.cmd_exit,
            'shutdown': self.cmd_exit,
        }

    def _output(self, msg):
        """Output a message. Must be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement _output()")

    def _do_exit(self):
        """Perform exit cleanup. Can be overridden by subclasses for additional cleanup."""
        pass

    # ======================== SHARED COMMANDS ========================

    def cmd_help(self, args):
        """Show available commands."""
        self._output("Commands: " + ", ".join(sorted(self.commands.keys())))

    def cmd_status(self, args):
        """Show server status."""
        self._output(f"Server Status: {'Running' if globalvars.aio_server else 'Stopped'}")
        self._output(f"Uptime: {self._get_uptime()}")
        self._output(f"Active Connections: {getattr(globalvars, 'active_connections', 'Unknown')}")
        self._output(f"Database Status: {'Connected' if getattr(globalvars, 'mariadb_initialized', False) else 'Disconnected'}")
        self._output(f"Current Blob: {self._get_current_blob_info()}")
        self._output(f"Log Level: {logging.getLevelName(logging.getLogger().level)}")

    def cmd_servers(self, args):
        """List all registered servers and their status."""
        from utilities.thread_handler import get_server_info, get_restartable_servers
        info = get_server_info()
        if not info:
            self._output("No servers registered.")
            return

        self._output("Registered servers:")
        # Consolidate CM servers for display
        cm_servers = []
        for ident, data in sorted(info.items()):
            if ident.startswith('CMTCP') or ident.startswith('CMUDP'):
                cm_servers.append((ident, data))
            else:
                status = "RUNNING" if data['is_alive'] else "STOPPED"
                port_str = f"port {data['port']}" if data['port'] else "no port"
                self._output(f"  [{status}] {ident}: {data['class']} ({port_str})")

        # Show consolidated CM server entry
        if cm_servers:
            all_running = all(d['is_alive'] for _, d in cm_servers)
            status = "RUNNING" if all_running else "PARTIAL"
            ports = ', '.join(str(d['port']) for _, d in cm_servers if d['port'])
            self._output(f"  [{status}] CMSERVER: CMServer (ports {ports})")

        self._output(f"Restartable servers: {', '.join(sorted(get_restartable_servers()))}")

    def cmd_restart_server(self, args):
        """Restart a specific server without code reload."""
        if not args:
            self._output("Usage: restartserver <server_identifier>")
            self._output("Use 'servers' command to see available server identifiers.")
            return

        from utilities.thread_handler import restart_server, get_restartable_servers, reload_steam3_modules

        available_servers = get_restartable_servers()
        # Case-insensitive match against available servers
        identifier = None
        for server in available_servers:
            if server.upper() == args[0].upper():
                identifier = server
                break

        if identifier is None:
            self._output(f"Server '{args[0]}' not found.")
            self._output(f"Available: {', '.join(sorted(available_servers))}")
            return

        self._output(f"Restarting server '{identifier}'...")
        if identifier == 'CMSERVER':
            success, message, count = reload_steam3_modules()
            if success:
                self._output(f"CMSERVER restart complete: {message}")
            else:
                self._output(f"CMSERVER restart failed: {message}")
        else:
            if restart_server(identifier, reload_code=False):
                self._output(f"Server '{identifier}' restarted successfully.")
            else:
                self._output(f"Failed to restart server '{identifier}'. Check logs for details.")

    def cmd_reload_server(self, args):
        """Restart a server with code reload (hot-reload)."""
        if not args:
            self._output("Usage: reloadserver <server_identifier>")
            self._output("Use 'servers' command to see available server identifiers.")
            return

        from utilities.thread_handler import restart_server, get_restartable_servers, reload_steam3_modules

        available_servers = get_restartable_servers()
        # Case-insensitive match against available servers
        identifier = None
        for server in available_servers:
            if server.upper() == args[0].upper():
                identifier = server
                break

        if identifier is None:
            self._output(f"Server '{args[0]}' not found.")
            self._output(f"Available: {', '.join(sorted(available_servers))}")
            return

        self._output(f"Reloading and restarting server '{identifier}'...")
        if identifier == 'CMSERVER':
            success, message, count = reload_steam3_modules()
            if success:
                self._output(f"CMSERVER hot-reload complete: {message}")
            else:
                self._output(f"CMSERVER hot-reload failed: {message}")
        else:
            if restart_server(identifier, reload_code=True):
                self._output(f"Server '{identifier}' reloaded and restarted successfully.")
            else:
                self._output(f"Failed to reload server '{identifier}'. Check logs for details.")

    def cmd_config(self, args):
        """Show configuration value."""
        if args:
            key = args[0]
            try:
                from config import get_config
                config = get_config()
                value = config.get(key, 'Not found')
                self._output(f"{key}: {value}")
            except:
                self._output("Config system not available")
        else:
            self._output("Use 'config <key>' to show specific configuration value")

    def cmd_blob(self, args):
        """Show current blob information."""
        try:
            blob_info = self._get_current_blob_info()
            self._output(f"Current blob: {blob_info}")
        except:
            self._output("Unable to get current blob information")

    def cmd_changeblob(self, args):
        """Change the blob date/time."""
        if not args:
            self._output("Usage: changeblob <iso8601-blobdate> <24h-blobtime>")
            self._output("")
            self._output("Example: changeblob 2003-12-21 15:21:40")
            return
        if args[0]:
            steamdate = self._normalize_date_to_iso(args[0])
            if steamdate == "invalid_date":
                self._output("Invalid date specified")
                return
        try:
            steamtime = self._normalize_time_to_underscores(args[1])
            if steamtime == "invalid_time":
                steamtime = "00_00_01"
        except:
            steamtime = "00_00_01"
        try:
            with open("emulator.ini", "r") as f:
                lines = f.readlines()
            with open("emulator.ini", "w") as f:
                for line in lines:
                    if line.startswith("steam_date="):
                        f.write(f"steam_date={steamdate}\n")
                    elif line.startswith("steam_time="):
                        f.write(f"steam_time={steamtime}\n")
                    else:
                        f.write(line)
            self._update_config()
            self._output(f"Client date changed to {steamdate} {steamtime.replace('_', ':')}")
        except Exception as e:
            self._output(f"Error changing blob: {e}")

    def cmd_set_loglevel(self, args):
        """Set the logging level."""
        if args:
            logging.getLogger().setLevel(logging.getLevelName(args[0].upper()))
            self._output(f"Logging changed to {logging.getLevelName(logging.getLogger().level)}")
        else:
            self._output("Please specify a log level e.g. loglevel debug. Options are: error, warn, info, debug")

    def cmd_openlog(self, args):
        """Open a log file."""
        if args:
            if args[0] in ["info", "debug", "error"]:
                log_path = f"{os.path.dirname(os.path.abspath(sys.argv[0]))}/logs/emulator_{args[0]}.log"
                if os.path.exists(log_path):
                    if globalvars.IS_WINDOWS:
                        os.startfile(log_path)
                    else:
                        os.system(f"xdg-open '{log_path}' &")
                    self._output(f"Opened {log_path}")
                else:
                    self._output(f"Log file not found: {log_path}")
            else:
                self._output("Please specify a log file e.g. openlog debug. Options are: info, debug, error")
        else:
            self._output("Please specify a log file e.g. openlog debug. Options are: info, debug, error")

    def cmd_info(self, args):
        """Show system information."""
        import platform
        self._output(f"System: {platform.system()} {platform.release()}")
        self._output(f"Python: {platform.python_version()}")
        try:
            import psutil
            self._output(f"CPU: {psutil.cpu_percent()}%")
            self._output(f"Memory: {psutil.virtual_memory().percent}%")
            self._output(f"Disk: {psutil.disk_usage('/').percent if not globalvars.IS_WINDOWS else psutil.disk_usage('C:').percent}%")
        except ImportError:
            self._output("System monitoring unavailable (psutil not installed)")

    def cmd_clear(self, args):
        """Clear the console/screen."""
        # Default implementation - subclasses can override
        if globalvars.IS_WINDOWS:
            os.system('cls')
        else:
            os.system('clear')
        self._output("Console cleared")

    def cmd_ftpmenu(self, args):
        """Open FTP management menu."""
        # Default implementation - subclasses can override for TUI handling
        try:
            from utilities.ftp_menu import run_ftp_menu
            self._output("Opening FTP Management Menu...")
            run_ftp_menu()
            self._output("Returned from FTP menu")
        except ImportError as e:
            self._output(f"FTP menu not available: {e}")
            self._output("Make sure windows-curses is installed on Windows: pip install windows-curses")
        except Exception as e:
            self._output(f"Error opening FTP menu: {e}")

    def cmd_exit(self, args=None):
        """Shutdown server gracefully."""
        self._output("Shutting down server...")
        self.running = False
        globalvars.shutdown_requested = True

        # Clean up ephemeral blobs before shutdown
        try:
            cleanup_all_ephemeral_blobs()
        except Exception as e:
            self._output(f"Error cleaning up ephemeral blobs: {e}")

        # Stop watchdog first
        try:
            from utilities.thread_handler import stop_watchdog
            stop_watchdog()
        except Exception:
            pass

        # Stop all servers
        try:
            for server in globalvars.servers:
                try:
                    server.cleanup()
                except Exception as e:
                    self._output(f"Error stopping server: {e}")
        except Exception:
            pass

        # Kill processes
        try:
            inputmanager.kill_mariadb_process()
            inputmanager.kill_apache()
        except Exception as e:
            self._output(f"Error stopping processes: {e}")

        self._output("Graceful shutdown completed.")

        # Subclass-specific cleanup
        self._do_exit()

        shutdown_logging()
        os._exit(0)

    # ======================== SHARED UTILITY METHODS ========================

    def _get_uptime(self):
        """Get server uptime."""
        if hasattr(globalvars, 'start_time'):
            start_dt = datetime.fromtimestamp(globalvars.start_time)
            now_dt = datetime.now()
            delta = relativedelta(now_dt, start_dt)
            parts = []
            if delta.years:
                parts.append(f"{delta.years}y")
            if delta.months:
                parts.append(f"{delta.months}mo")
            if delta.days:
                parts.append(f"{delta.days}d")
            parts.append(f"{delta.hours}h")
            parts.append(f"{delta.minutes}m")
            parts.append(f"{delta.seconds}s")
            return " ".join(parts)
        return "Unknown"

    def _normalize_date_to_iso(self, date_str: str) -> str:
        """Normalize date string to ISO format."""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        cleaned = re.sub(r"\D", "-", date_str)
        try:
            dt = datetime.strptime(cleaned, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return "invalid_date"

    def _normalize_time_to_underscores(self, time_str: str) -> str:
        """Normalize time string to underscore format."""
        cleaned = re.sub(r"\D", "_", time_str)
        try:
            dt = datetime.strptime(cleaned, "%H_%M_%S")
        except ValueError:
            return "invalid_time"
        return dt.strftime("%H_%M_%S")

    def _update_config(self):
        """Reload the configuration."""
        try:
            from config import read_config
            read_config()
        except Exception:
            pass

    def _get_current_blob_info(self):
        """Get current blob information."""
        try:
            from config import get_config
            cfg = get_config()
            return f"{cfg.get('steam_date', '?')} {cfg.get('steam_time', '?').replace('_', ':')}"
        except Exception:
            return "Unknown"

    def _get_status_text(self):
        """Get full status text for display."""
        if globalvars.formatted_underscore_date < "2003-09-11":
            ui_ver = f"  PLATFORM pkg    : {globalvars.steamui_ver}"
        else:
            ui_ver = f"  SteamUI pkg     : {globalvars.steamui_ver}"
        lines = [
            f"Server Status: {'Running' if globalvars.aio_server else 'Stopped'}",
            f"Uptime: {self._get_uptime()}",
            f"Active Connections: {getattr(globalvars, 'active_connections', 'Unknown')}",
            f"Database Status: {'Connected' if getattr(globalvars, 'mariadb_initialized', False) else 'Disconnected'}",
            f"Log Level: {logging.getLevelName(logging.getLogger().level)}",
            "",
            "Steam Environment Information:",
            f"  Steam pkg       : {globalvars.steam_ver}",
            ui_ver,
            f"  Steam Date/Time : {self._get_current_blob_info()}",
        ]
        return "\n".join(lines)


# ============================================================================
# SIMPLE CONSOLE MANAGER (Ben's Console)
# ============================================================================

if globalvars.IS_WINDOWS:
    try:
        import msvcrt
        import ctypes
        from ctypes import wintypes

        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        HAS_WINDOWS_CONSOLE = True
    except ImportError:
        HAS_WINDOWS_CONSOLE = False
else:
    try:
        import termios
        import tty
        import select
        HAS_UNIX_CONSOLE = True
    except ImportError:
        HAS_UNIX_CONSOLE = False


class SimpleConsoleManager(ConsoleCommandsBase):
    """
    Simple console manager that doesn't use TUI.
    Prints directly to stdout with basic command input.
    Inherits all commands from ConsoleCommandsBase.
    """

    def __init__(self):
        super().__init__()
        self.command_buffer = ""
        self.cursor_pos = 0
        self.history = deque(maxlen=50)
        self.history_pos = -1
        self.temp_buffer = ""
        self.input_thread = None
        self.last_backspace_time = 0

        self._terminal_fd = None
        self._old_terminal_settings = None

    def _output(self, msg):
        """Output a message to stdout."""
        print(msg)

    def _do_exit(self):
        """Restore terminal settings before exit."""
        self._restore_terminal()

    def start(self):
        """Start the console manager."""
        if not self.running:
            return

        try:
            self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
            self.input_thread.start()
        except Exception as e:
            self.log.error(f"Failed to start Console Manager: {e}")
            self.running = False

    def stop(self):
        """Stop the console manager."""
        self.running = False
        if self.input_thread:
            self.input_thread.join(timeout=1)

    def _input_loop(self):
        """Handle keyboard input including escape key detection."""
        time.sleep(3)

        print("\nSteam Server Console - Type 'help' for commands, or press ESC to shutdown")

        if globalvars.IS_WINDOWS and HAS_WINDOWS_CONSOLE:
            self._windows_input_loop()
        elif not globalvars.IS_WINDOWS and HAS_UNIX_CONSOLE:
            self._unix_input_loop()
        else:
            self._fallback_input_loop()

    def _windows_input_loop(self):
        """Windows-specific input loop with escape key detection, history navigation, cursor movement, and double Ctrl+C clear."""
        command_buffer = ""
        cursor_pos = 0
        history_pos = -1
        temp_buffer = ""
        last_ctrlc_time = 0
        print("> ", end="", flush=True)

        def redraw_line():
            """Redraw the command line with cursor at correct position."""
            nonlocal command_buffer, cursor_pos
            # Move cursor to start of line content, clear, reprint, position cursor
            chars_after_cursor = len(command_buffer) - cursor_pos
            # Move to end, clear everything, go back to start
            if chars_after_cursor > 0:
                print('\x1b[' + str(chars_after_cursor) + 'C', end="", flush=True)  # move right
            print('\r> ', end="", flush=True)
            print(command_buffer, end="", flush=True)
            # Move cursor back to correct position
            if chars_after_cursor > 0:
                print('\x1b[' + str(chars_after_cursor) + 'D', end="", flush=True)

        def clear_line_and_print(new_text):
            """Clear current line content and print new text."""
            nonlocal command_buffer, cursor_pos
            # Clear entire line and reprint
            print('\r> ' + ' ' * len(command_buffer) + '\r> ', end="", flush=True)
            command_buffer = new_text
            cursor_pos = len(command_buffer)
            print(command_buffer, end="", flush=True)

        while self.running:
            try:
                if msvcrt.kbhit():
                    char = msvcrt.getch()

                    if char == b'\x1b':  # Escape key
                        print("\nEscape key pressed, shutting down gracefully...")
                        self.cmd_exit()
                        break
                    elif char == b'\xe0':  # Extended key prefix (arrow keys, etc.)
                        extended_char = msvcrt.getch()
                        if extended_char == b'H':  # Up arrow - history
                            if self.history:
                                if history_pos == -1:
                                    temp_buffer = command_buffer
                                    history_pos = len(self.history) - 1
                                elif history_pos > 0:
                                    history_pos -= 1
                                if 0 <= history_pos < len(self.history):
                                    clear_line_and_print(self.history[history_pos])
                        elif extended_char == b'P':  # Down arrow - history
                            if history_pos != -1:
                                if history_pos < len(self.history) - 1:
                                    history_pos += 1
                                    clear_line_and_print(self.history[history_pos])
                                else:
                                    history_pos = -1
                                    clear_line_and_print(temp_buffer)
                        elif extended_char == b'K':  # Left arrow - move cursor left
                            if cursor_pos > 0:
                                cursor_pos -= 1
                                print('\b', end="", flush=True)
                        elif extended_char == b'M':  # Right arrow - move cursor right
                            if cursor_pos < len(command_buffer):
                                print(command_buffer[cursor_pos], end="", flush=True)
                                cursor_pos += 1
                    elif char == b'\r':  # Enter key
                        if command_buffer.strip():
                            print()
                            self._execute_command(command_buffer.strip())
                        command_buffer = ""
                        cursor_pos = 0
                        history_pos = -1
                        temp_buffer = ""
                        print("> ", end="", flush=True)
                    elif char == b'\x08':  # Backspace
                        if cursor_pos > 0:
                            # Delete character before cursor
                            command_buffer = command_buffer[:cursor_pos-1] + command_buffer[cursor_pos:]
                            cursor_pos -= 1
                            # Redraw from cursor position
                            tail = command_buffer[cursor_pos:]
                            print('\b' + tail + ' ' + '\b' * (len(tail) + 1), end="", flush=True)
                    elif char == b'\x03':  # Ctrl+C
                        current_time = time.time()
                        if current_time - last_ctrlc_time < 1.0:
                            if command_buffer:
                                print('\r> ' + ' ' * len(command_buffer) + '\r> ', end="", flush=True)
                                command_buffer = ""
                                cursor_pos = 0
                            last_ctrlc_time = 0
                        else:
                            last_ctrlc_time = current_time
                    elif len(char) == 1 and ord(char) >= 32:
                        try:
                            decoded_char = char.decode('latin-1', errors='ignore')
                            if decoded_char:
                                # Insert character at cursor position
                                command_buffer = command_buffer[:cursor_pos] + decoded_char + command_buffer[cursor_pos:]
                                # Print from cursor to end, then move back
                                tail = command_buffer[cursor_pos:]
                                print(tail, end="", flush=True)
                                cursor_pos += 1
                                # Move cursor back if we printed chars after cursor
                                chars_after = len(tail) - 1
                                if chars_after > 0:
                                    print('\b' * chars_after, end="", flush=True)
                                if history_pos != -1:
                                    history_pos = -1
                                    temp_buffer = ""
                        except:
                            pass
                else:
                    time.sleep(0.01)
            except (EOFError, KeyboardInterrupt):
                print("\nReceived interrupt signal, shutting down gracefully...")
                self.cmd_exit()
                break
            except Exception as e:
                print(f"\nInput error: {e}")
                time.sleep(0.1)

    def _unix_input_loop(self):
        """Unix/Linux-specific input loop with escape key detection, history navigation, cursor movement, and double Ctrl+C clear."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        self._terminal_fd = fd
        self._old_terminal_settings = old_settings
        command_buffer = ""
        cursor_pos = 0
        history_pos = -1
        temp_buffer = ""
        last_ctrlc_time = 0

        def clear_line_and_print(new_text):
            """Clear current line content and print new text."""
            nonlocal command_buffer, cursor_pos
            # Clear entire line and reprint
            print('\r> ' + ' ' * len(command_buffer) + '\r> ', end="", flush=True)
            command_buffer = new_text
            cursor_pos = len(command_buffer)
            print(command_buffer, end="", flush=True)

        try:
            tty.setcbreak(fd)
            print("> ", end="", flush=True)

            while self.running:
                try:
                    if sys.stdin in select.select([sys.stdin], [], [], 0.01)[0]:
                        char = sys.stdin.read(1)

                        if char == '\x1b':  # Escape sequence start
                            if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                next_char = sys.stdin.read(1)
                                if next_char == '[':
                                    if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                        arrow_char = sys.stdin.read(1)
                                        if arrow_char == 'A':  # Up arrow - history
                                            if self.history:
                                                if history_pos == -1:
                                                    temp_buffer = command_buffer
                                                    history_pos = len(self.history) - 1
                                                elif history_pos > 0:
                                                    history_pos -= 1
                                                if 0 <= history_pos < len(self.history):
                                                    clear_line_and_print(self.history[history_pos])
                                        elif arrow_char == 'B':  # Down arrow - history
                                            if history_pos != -1:
                                                if history_pos < len(self.history) - 1:
                                                    history_pos += 1
                                                    clear_line_and_print(self.history[history_pos])
                                                else:
                                                    history_pos = -1
                                                    clear_line_and_print(temp_buffer)
                                        elif arrow_char == 'D':  # Left arrow - move cursor left
                                            if cursor_pos > 0:
                                                cursor_pos -= 1
                                                print('\b', end="", flush=True)
                                        elif arrow_char == 'C':  # Right arrow - move cursor right
                                            if cursor_pos < len(command_buffer):
                                                print(command_buffer[cursor_pos], end="", flush=True)
                                                cursor_pos += 1
                            else:
                                print("\nEscape key pressed, shutting down gracefully...")
                                self.cmd_exit()
                                break
                        elif char == '\n':  # Enter key
                            if command_buffer.strip():
                                print()
                                self._execute_command(command_buffer.strip())
                            command_buffer = ""
                            cursor_pos = 0
                            history_pos = -1
                            temp_buffer = ""
                            print("> ", end="", flush=True)
                        elif char == '\x7f':  # Backspace
                            if cursor_pos > 0:
                                # Delete character before cursor
                                command_buffer = command_buffer[:cursor_pos-1] + command_buffer[cursor_pos:]
                                cursor_pos -= 1
                                # Redraw from cursor position
                                tail = command_buffer[cursor_pos:]
                                print('\b' + tail + ' ' + '\b' * (len(tail) + 1), end="", flush=True)
                        elif char == '\x03':  # Ctrl+C
                            current_time = time.time()
                            if current_time - last_ctrlc_time < 1.0:
                                if command_buffer:
                                    print('\r> ' + ' ' * len(command_buffer) + '\r> ', end="", flush=True)
                                    command_buffer = ""
                                    cursor_pos = 0
                                last_ctrlc_time = 0
                            else:
                                last_ctrlc_time = current_time
                        elif ord(char) >= 32:
                            # Insert character at cursor position
                            command_buffer = command_buffer[:cursor_pos] + char + command_buffer[cursor_pos:]
                            # Print from cursor to end, then move back
                            tail = command_buffer[cursor_pos:]
                            print(tail, end="", flush=True)
                            cursor_pos += 1
                            # Move cursor back if we printed chars after cursor
                            chars_after = len(tail) - 1
                            if chars_after > 0:
                                print('\b' * chars_after, end="", flush=True)
                            if history_pos != -1:
                                history_pos = -1
                                temp_buffer = ""
                    else:
                        time.sleep(0.01)
                except (EOFError, KeyboardInterrupt):
                    print("\nReceived interrupt signal, shutting down gracefully...")
                    self.cmd_exit()
                    break
                except Exception as e:
                    print(f"\nInput error: {e}")
                    time.sleep(0.1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _fallback_input_loop(self):
        """Fallback input loop using standard input."""
        print("> ", end="", flush=True)

        while self.running:
            try:
                command = input()
                if command.strip():
                    self._execute_command(command.strip())
                print("> ", end="", flush=True)
            except (EOFError, KeyboardInterrupt):
                print("\nReceived interrupt signal, shutting down gracefully...")
                self.cmd_exit()
                break
            except Exception as e:
                print(f"\nInput error: {e}")
                time.sleep(0.1)

    def _execute_command(self, command):
        """Execute command."""
        parts = command.split()
        if not parts:
            return

        cmd_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if not self.history or self.history[-1] != command:
            self.history.append(command)

        if cmd_name in self.commands:
            try:
                self.commands[cmd_name](args)
            except Exception as e:
                print(f"Error executing command '{cmd_name}': {e}")
        else:
            print(f"Unknown command: {cmd_name}. Type 'help' for available commands.")

    def _restore_terminal(self):
        """Restore terminal settings on Unix/Linux."""
        if not globalvars.IS_WINDOWS and self._old_terminal_settings is not None:
            try:
                termios.tcsetattr(self._terminal_fd, termios.TCSADRAIN, self._old_terminal_settings)
            except Exception:
                pass


# ============================================================================
# TUI CONSOLE MANAGER (prompt_toolkit based) - Original Layout & Styling
# ============================================================================

# Only import prompt_toolkit if we're using TUI console
if not USE_BEN_CONSOLE:
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FloatContainer, ScrollablePane
        from prompt_toolkit.widgets import Frame, TextArea
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.styles import Style
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.buffer import Buffer
        from prompt_toolkit.document import Document
        from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.application.current import get_app
        HAS_PROMPT_TOOLKIT = True
    except ImportError:
        HAS_PROMPT_TOOLKIT = False
else:
    HAS_PROMPT_TOOLKIT = False


class TUIConsoleManager(ConsoleCommandsBase):
    """
    TUI-based console manager using prompt_toolkit.
    Original layout with:
    - Top: Title bar with version
    - Logs pane (scrollable)
    - Status pane
    - Command Output pane
    - Input line at bottom with stmserver:> prompt

    Inherits all commands from ConsoleCommandsBase.
    """

    def __init__(self):
        super().__init__()

        # Add TUI-specific commands
        self.commands.update({
            'pause': self.cmd_pause,
            'resume': self.cmd_resume,
            'restart': self.cmd_reload,
            'reload': self.cmd_reload,
            'return': self.cmd_return,
        })

        if not HAS_PROMPT_TOOLKIT:
            self.log.error("prompt_toolkit not available, TUI console disabled")
            self.running = False
            return

        def centered_label(text: str, style: str = "") -> Window:
            def get_text():
                width = get_app().output.get_size().columns
                return text.center(width, "─")

            return Window(
                height=1,
                content=FormattedTextControl(get_text),
                style=style,
                always_hide_cursor=True,
                dont_extend_width=False,
            )

        def get_log_text():
            combined = []
            for entry in self.log_buffer:
                combined.extend(entry)
                combined.append(("", "\n"))
            return FormattedText(combined)

        # Buffers for UI
        self.log_buffer = deque(maxlen=1000)
        self.output_buffer = deque(maxlen=200)
        self.log_paused = False

        # Log area using ScrollablePane with HSplit for individual log entries
        self.inner = HSplit(children=[Window(FormattedTextControl(text=f""))])
        self.log_area = ScrollablePane(content=self.inner)

        # Status and Output areas with fixed heights
        self.status_area = TextArea(style="class:status", scrollbar=False, focusable=False, height=10)
        self.output_area = TextArea(style="class:output", scrollbar=False, focusable=False, height=3)

        # Input area with stmserver:> prompt
        self.input_buffer = Buffer()
        self.input_field = Window(BufferControl(buffer=self.input_buffer), height=1, style="class:root")
        self.input_area = VSplit([
            Window(content=FormattedTextControl('stmserver:>'), width=11, style="class:root"),
            self.input_field,
        ])

        # Key bindings
        self.kb = self._setup_key_bindings()

        # Original color scheme - dark green/olive theme
        self.style = Style.from_dict({
            "log": "bg:#000000 #c4b550",
            "status": "bg:#3e4637 #c4b550",
            "output": "bg:#3e4637 #c4b550",
            "input": "bg:#3e4637 #ffffff",
            "prompt": "bg:#3e4637 #ffffff",
            "title": "bg:#4c5844 #c4b550",
            "root": "bg:#4c5844 #ffffff",
        })

        # Logging styles for different log levels
        self.logging_styles = {
            logging.DEBUG: "fg:cyan",
            logging.INFO: "fg:green",
            logging.WARNING: "fg:yellow",
            logging.ERROR: "fg:red",
            logging.CRITICAL: "fg:white bg:red",
        }

        # Layout - Original vertical stacked layout
        self.layout = FloatContainer(
            content=HSplit([
                centered_label(f" Steam 2002-2011 Server Emulator v{globalvars.local_ver} ", "class:title"),
                Window(height=1, content=FormattedTextControl("  Logs (scroll with CTRL + ↑ / CTRL + ↓)"), style="class:root"),
                self.log_area,
                Window(height=1, content=FormattedTextControl("  Status"), style="class:root"),
                self.status_area,
                Window(height=1, content=FormattedTextControl("  Command Output"), style="class:root"),
                self.output_area,
                self.input_area,
            ]),
            floats=[],
        )

        # Application
        self.app = Application(
            layout=Layout(self.layout, focused_element=self.input_field),
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True,
        )

        # Logging hook
        self._setup_logging_handler()

        # Background update thread
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)

    def _output(self, msg):
        """Output a message to the command output pane."""
        self.output_buffer.append(msg)

    def _do_exit(self):
        """TUI-specific exit cleanup."""
        self.app.exit(result=None)

    def add_line(self, formattedtxt):
        """Add a new line to the log area and focus it."""
        self.inner.children.append(Window(FormattedTextControl(text=formattedtxt)))
        self.app.layout.focus(self.inner.children[-1])
        time.sleep(0.1)
        self.app.layout.focus(self.input_area)

    def _setup_logging_handler(self):
        """Redirect logging into the log area using the original style."""

        class ConsoleLogHandler(logging.Handler):
            def __init__(self, console_manager):
                super().__init__()
                self.console_manager = console_manager

            def emit(self, record):
                if (not self.console_manager.log_paused and record.name != "ConsoleManager"):
                    msg = self.format(record)
                    style = self.console_manager.logging_styles.get(record.levelno, "")
                    log_entry = f"{datetime.now().strftime('%Y/%m/%d %H:%M:%S')} - {record.name} - {record.levelname} - {msg}"
                    formatted_msg = FormattedText([(style, log_entry)])
                    self.console_manager.add_line(formatted_msg)

        handler = ConsoleLogHandler(self)
        self._log_handler = handler

        # Remove any existing stdout/stderr handlers to avoid duplication
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)

        root.addHandler(handler)

    def _setup_key_bindings(self):
        kb = KeyBindings()

        @kb.add("enter")
        def _(event):
            """Execute command on Enter."""
            text = self.input_buffer.text.strip()
            if text:
                self._execute_command(text)
            self.input_buffer.document = Document()

        @kb.add("escape")
        def _(event):
            """Exit on ESC."""
            self.cmd_exit()

        @kb.add("c-c")
        @kb.add("c-q")
        def _(event):
            """Exit on Ctrl+C or Ctrl+Q."""
            self.cmd_exit()

        @kb.add("c-up")
        def scroll_up(event):
            try:
                current_index = self.inner.children.index(event.app.layout.current_window)
                if current_index > 0:
                    event.app.layout.focus(self.inner.children[current_index - 1])
            except (ValueError, IndexError):
                pass

        @kb.add("c-down")
        def scroll_down(event):
            try:
                current_index = self.inner.children.index(event.app.layout.current_window)
                if current_index < len(self.inner.children) - 1:
                    event.app.layout.focus(self.inner.children[current_index + 1])
            except (ValueError, IndexError):
                pass

        return kb

    def start(self):
        """Start the full-screen application."""
        if not self.running or not HAS_PROMPT_TOOLKIT:
            return

        self.update_thread.start()
        while self.running:
            with patch_stdout(raw=True):
                result = self.app.run()

            if result == "__FTPMENU__":
                if hasattr(self, '_ftpmenu_callback'):
                    self._ftpmenu_callback()
                    delattr(self, '_ftpmenu_callback')
                self._recreate_app()
            elif result == "__RESTART__":
                time.sleep(1)
                for root_dir, dirs, files in os.walk("."):
                    for filename in files:
                        if filename.endswith((".pyc", ".pyo")):
                            try:
                                os.remove(os.path.join(root_dir, filename))
                            except OSError:
                                pass
                    if "__pycache__" in dirs:
                        try:
                            import shutil
                            shutil.rmtree(os.path.join(root_dir, "__pycache__"), ignore_errors=True)
                        except:
                            pass
                python = sys.executable
                os.execv(python, [python] + sys.argv)
            elif result == "__EXIT__":
                break
            else:
                break

    def _recreate_app(self):
        """Recreate the prompt_toolkit application for reentry after FTP menu."""
        self.app = Application(
            layout=Layout(self.layout, focused_element=self.input_field),
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True,
        )

    def stop(self):
        self.running = False
        if hasattr(self, '_log_handler'):
            logging.getLogger().removeHandler(self._log_handler)
        if self.app.is_running:
            self.app.exit()

    def _update_loop(self):
        """Background loop to refresh UI."""
        while self.running:
            self.status_area.text = self._get_status_text()
            self.output_area.text = "\n".join(list(self.output_buffer)[-50:])
            time.sleep(0.5)

    def _execute_command(self, command):
        self.output_buffer.clear()
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in self.commands:
            try:
                self.commands[cmd](args)
            except Exception as e:
                self._output(f"Error executing {cmd}: {e}")
        else:
            self._output(f"Unknown command: {cmd}. Type 'help' for a list of commands.")

    # ======================== TUI-SPECIFIC COMMANDS ========================

    def cmd_pause(self, args):
        """Pause log display."""
        self.log_paused = True
        self._output("Log paused.")

    def cmd_resume(self, args):
        """Resume log display."""
        self.log_paused = False
        self._output("Log resumed.")

    def cmd_clear(self, args):
        """Clear the log display."""
        self.log_buffer.clear()
        self.inner.children = [Window(FormattedTextControl(text=f""))]
        self._output("Logs cleared.")

    def cmd_ftpmenu(self, args):
        """Open FTP management menu (exits TUI temporarily)."""
        self._output("Opening FTP Management Menu...")
        self._output("The TUI will be suspended. Press any key after menu closes to resume.")

        def run_menu_after_exit():
            try:
                from utilities.ftp_menu import run_ftp_menu
                run_ftp_menu()
            except ImportError as e:
                print(f"FTP menu not available: {e}")
                print("Make sure windows-curses is installed on Windows: pip install windows-curses")
            except Exception as e:
                print(f"Error opening FTP menu: {e}")

        self._ftpmenu_callback = run_menu_after_exit
        self.app.exit(result="__FTPMENU__")

    def cmd_return(self, args=None):
        """Exit TUI mode and return to watchescape thread."""
        from utilities.inputmanager import start_watchescape_thread
        start_watchescape_thread()
        self.app.exit(result=None)

    def cmd_reload(self, args=None):
        """Restart the entire server."""
        self._output("Restarting...")
        self.running = False
        globalvars.shutdown_requested = True
        self.app.exit(result="__RESTART__")


# ============================================================================
# MODULE-LEVEL FUNCTIONS
# ============================================================================

console_manager = None


def start_console_manager():
    """Start the appropriate console manager based on config."""
    global console_manager

    if console_manager is None:
        if USE_BEN_CONSOLE:
            console_manager = SimpleConsoleManager()
        else:
            console_manager = TUIConsoleManager()
        console_manager.start()


def stop_console_manager():
    """Stop the console manager."""
    global console_manager
    if console_manager:
        console_manager.stop()
        console_manager = None


def get_console_manager():
    """Get the console manager instance."""
    return console_manager
