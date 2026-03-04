import logging
import logging.handlers
import os
import re
import sys
import traceback
import queue
import threading
from logging.handlers import QueueHandler, QueueListener

from config import get_config

config = get_config()
loglevel = config["log_level"]
logtofile = config["log_to_file"].lower()
logging_enabled = config["logging_enabled"].lower()

# LOG LEVELS:
# CRITICAL
# ERROR
# WARNING
# INFO
# DEBUG
# NOTSET

# Custom logging level for storage neutering (GCF checksum) logs
# Level 15 is between DEBUG (10) and INFO (20)
STORAGENEUTER = 15
logging.addLevelName(STORAGENEUTER, "STORAGENEUTER")

# Custom logging level for verbose debug including heartbeats
# Level 5 is below DEBUG (10) - more verbose, includes heartbeat messages
DEBUGPLUS = 5
logging.addLevelName(DEBUGPLUS, "DEBUGPLUS")


def storageneuter(self, message, *args, **kwargs):
    """Log a message at the STORAGENEUTER level."""
    if self.isEnabledFor(STORAGENEUTER):
        self._log(STORAGENEUTER, message, args, **kwargs)


def debugplus(self, message, *args, **kwargs):
    """Log a message at the DEBUGPLUS level (more verbose than DEBUG, includes heartbeats)."""
    if self.isEnabledFor(DEBUGPLUS):
        self._log(DEBUGPLUS, message, args, **kwargs)


# Add the storageneuter method to Logger class
logging.Logger.storageneuter = storageneuter
# Add the debugplus method to Logger class
logging.Logger.debugplus = debugplus

if sys.platform == 'win32':
    os.system('color')  # NEEDED FOR WINDOWS SERVER COLORING

log_queue = queue.Queue()
log_flush_lock = threading.Lock()
queue_listener = None  # Will be set by init_logger() on Windows


def shutdown_logging():
    """
    Properly shutdown the logging system, ensuring all pending log messages
    are flushed before the process exits.

    This MUST be called before os._exit() or sys.exit() to ensure all log
    messages are written.
    """
    global queue_listener

    # Close test logging if active (must be done before closing other handlers)
    # Note: close_test_logging is defined later in this module, so we use globals() lookup
    try:
        if 'close_test_logging' in globals():
            globals()['close_test_logging']()
    except Exception:
        pass

    # Stop the queue listener if it's running (Windows)
    if queue_listener is not None:
        try:
            queue_listener.stop()
        except Exception:
            pass

    # Flush all handlers on the root logger
    root = logging.getLogger()
    for handler in root.handlers:
        try:
            handler.flush()
        except Exception:
            pass

    # Also flush the standard streams
    try:
        sys.stdout.flush()
        sys.stderr.flush() if hasattr(sys.stderr, 'flush') else None
    except Exception:
        pass


class MessageLogContext:
    def __init__(self, logger, context_id=None):
        self.logger = logger
        self.records = []
        self.context_id = context_id or ""
        self.start_time = None

    def log(self, level, msg, *args, **kwargs):
        # Add timestamp if this is the first log in the context
        if not self.records and not self.start_time:
            import time
            self.start_time = time.time()
        self.records.append((level, msg, args, kwargs))

    def debug(self, msg, *args, **kwargs):
        self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs.setdefault('exc_info', True)
        self.log(logging.ERROR, msg, *args, **kwargs)

    def flush(self):
        if not self.records:
            return
            
        with log_flush_lock:
            # Add context header
            if self.context_id:
                header = f"{'='*60}\n[{self.context_id}] Message Processing Context\n{'='*60}"
                self.logger.info(header)
            
            # Log all records in order
            for level, msg, args, kwargs in self.records:
                self.logger.log(level, msg, *args, **kwargs)
                
            # Add context footer
            if self.context_id:
                import time
                duration = time.time() - self.start_time if self.start_time else 0
                footer = f"{'='*60}\n[{self.context_id}] End Context (Duration: {duration:.3f}s)\n{'='*60}"
                self.logger.info(footer)
                
        self.records.clear()


class PacketLogContext(MessageLogContext):
    """Enhanced logging context specifically for Steam packet handling"""
    
    def __init__(self, logger, packet_type=None, client_id=None, sequence=None):
        context_id = f"PACKET-{packet_type or 'Unknown'}"
        if client_id:
            context_id += f"-Client{client_id}"
        if sequence:
            context_id += f"-Seq{sequence}"
        super().__init__(logger, context_id)
        
        self.packet_type = packet_type
        self.client_id = client_id
        self.sequence = sequence
        
    def log_packet_received(self, packet_data, client_ip=None):
        """Log packet reception details"""
        msg = f"RECEIVED: {self.packet_type}"
        if client_ip:
            msg += f" from {client_ip}"
        if len(packet_data) > 0:
            msg += f" ({len(packet_data)} bytes)"
            # Show first 32 bytes of packet data
            data_preview = packet_data[:32].hex().upper()

            msg += f" Data: {data_preview}"
        self.info(msg)
        
    def log_packet_processing(self, handler_name, details=None):
        """Log packet processing details"""
        msg = f"PROCESSING: {handler_name}"
        if details:
            msg += f" - {details}"
        self.info(msg)
        
    def log_packet_response(self, response_type, response_data=None):
        """Log response packet details"""
        msg = f"SENDING: {response_type}"
        if response_data and len(response_data) > 0:
            msg += f" ({len(response_data)} bytes)"
            # Show first 32 bytes of response data
            data_preview = response_data[:32].hex().upper()
            if len(response_data) > 32:
                data_preview += "..."
            msg += f" Data: {data_preview}"
        self.info(msg)
        
    def log_error(self, error_msg, exception=None):
        """Log error with context"""
        msg = f"ERROR: {error_msg}"
        if exception:
            self.exception(msg, exc_info=exception)
        else:
            self.error(msg)

# --- Custom Logger to support extra keyword arguments ---
class CustomLogger(logging.Logger):
    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1, **kwargs):
        if extra is None:
            extra = {}
        # Inject any extra keyword arguments (e.g., category) into the LogRecord.
        extra.update(kwargs)
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel=stacklevel)

logging.setLoggerClass(CustomLogger)
# --- End Custom Logger ---

class StderrToLogger:
    """
    Redirect stderr to logging framework.
    """
    def __init__(self):
        self.logger = logging.getLogger("STDERR")
        self.log_level = logging.ERROR
        self.original_stderr = sys.__stderr__  # Save the original stderr

    def write(self, message):
        # Avoid logging newlines to the logger.
        if message.rstrip() != "":
            try:
                # Ensure the message is encodable in the system's default encoding
                safe_message = message.rstrip().encode('ascii', errors='replace').decode('ascii')
                self.logger.log(self.log_level, safe_message)
            except Exception:
                # Fallback: write directly to original stderr to avoid recursion
                try:
                    self.original_stderr.write(f"[LOGGER ERROR] {message.rstrip()}\n")
                    self.original_stderr.flush()
                except Exception:
                    pass  # Give up completely to avoid recursion

    def flush(self):
        # This flush method is required for file-like objects.
        pass

    def isatty(self):
        # File-like objects in a terminal usually return True, but since
        # this is a logger, it's not attached to a terminal.
        return False


# Set the custom exception handler
def custom_exception_handler(exc_type, exc_value, tb):
    """
    Custom exception handler that logs uncaught exceptions.
    """
    try:
        logger = logging.getLogger("EXCEPTION")
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, tb))
        # Ensure the traceback is encodable in the system's default encoding
        safe_tb_str = tb_str.encode('ascii', errors='replace').decode('ascii')
        # Log the exception
        logger.critical("Uncaught exception: " + safe_tb_str)
    except Exception:
        # Fallback: write directly to original stderr
        try:
            tb_str = "".join(traceback.format_exception(exc_type, exc_value, tb))
            sys.__stderr__.write(f"[EXCEPTION HANDLER ERROR] {tb_str}\n")
            sys.__stderr__.flush()
        except Exception:
            sys.__stderr__.write(f"[CRITICAL ERROR] Exception handler failed: {exc_type.__name__}: {exc_value}\n")
            sys.__stderr__.flush()


def custom_unraisable_handler(unraisable):
    """
    Custom handler for sys.unraisablehook.
    Takes a single UnraisableHookArgs argument (different from sys.excepthook).
    """
    custom_exception_handler(
        unraisable.exc_type,
        unraisable.exc_value,
        unraisable.exc_traceback
    )


class FlushingStreamHandler(logging.StreamHandler):
    """
    A StreamHandler that always flushes after each emit.
    This fixes the issue on Linux where stdout buffering can prevent
    log messages from appearing immediately in the terminal.
    """
    def emit(self, record):
        try:
            super().emit(record)
            self.flush()
        except Exception:
            self.handleError(record)


class SpecificDebugFilter(logging.Filter):
    def filter(self, record):
        # Define a regular expression pattern that matches your specific log messages
        pattern = re.compile(r"\('(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', (\d+)\): Received data with length  - [0-9a-fA-F ]+")
        # Check if the log record matches the specific pattern
        if pattern.match(record.getMessage()):
            return False  # Exclude this specific message from the console
        return True  # Include all other messages


class ProgressBarFilter(logging.Filter):
    def filter(self, record):
        return True


sys.excepthook = custom_exception_handler
sys.unraisablehook = custom_unraisable_handler


class ColoredFormatter(logging.Formatter):

    COLORS = {
        "MODULE": "\033[93m",   # yellow
        "LEVEL": "\033[90m",    # Aqua for level indicator
        "WARNING": "\033[93m",  # Yellow
        "INFO": "\033[32;10m",  # Green
        "DEBUG": "\033[94m",    # Blue
        "CRITICAL": "\033[91m", # Red
        "ERROR": "\033[91m",    # Red
        "EXCEPTION": "\033[31", # Dark Red for Exceptions
        "TIME": "\033[37m",
        "RESET": "\033[0m"      # Reset
    }

    def formatException(self, exc_info):
        """
        Format and color the exception information, removing date/time from continuation lines.
        """
        # Standard exception format
        exception_text = super(ColoredFormatter, self).formatException(exc_info)
        # Split the exception into lines
        exception_lines = exception_text.split('\n')
        # Prepare the first line with full formatting
        first_line = f"{self.COLORS['EXCEPTION']}{exception_lines[0]}{self.COLORS['RESET']}"
        # Prepare other lines without date/time but with error color
        other_lines = [f"{self.COLORS['ERROR']}{line}{self.COLORS['RESET']}" for line in exception_lines[1:] if line.strip() != ""]
        return first_line + '\n' + '\n'.join(other_lines)

    def formatTime(self, record, datefmt=None):
        formatted_time = super(ColoredFormatter, self).formatTime(record, datefmt)
        return f"{self.COLORS['TIME']}{formatted_time}{self.COLORS['RESET']}"

    def format(self, record):
        # First, apply the initial formatting defined by the base class
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        if record.exc_info:
            # If it's an exception, format the exception specially
            record.exc_text = self.formatException(record.exc_info)
            formatted_exception = record.exc_text
        else:
            formatted_exception = ""

        formatted_record = f"{self.COLORS['TIME']}{record.asctime} {self.COLORS['RESET']}" if 'asctime' in record.__dict__ else ""
        formatted_record += f"{self.COLORS[record.levelname]}{record.levelname}: {record.message}{self.COLORS['RESET']}"

        # Append formatted exception, if any
        if formatted_exception:
            formatted_record += '\n' + formatted_exception

        return formatted_record


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    critical_red = "\033[91m"  # error/critical
    bold_red = "\x1b[31;1m"
    blue = "\033[94m"         # debug
    green = "\033[32;10m"     # info
    time = "\033[37m"
    module = "\033[93m"       # yellow (for the logger name)
    level = "\033[90m"        # aqua
    reset = "\x1b[0m"

    # Mapping of category names to their desired color codes.
    CATEGORY_COLORS = {
        'CMServer': "\033[96m",  # light blue
        'database': "\033[35m",  # purple
        # add more categories as needed
    }

    format_time = time + "%(asctime)-24s"
    format_name = module + "%(name)-14s"
    format_level = level + "%(levelname)-9s"
    format_message = "%(message)s"

    # Color for STORAGENEUTER level (cyan/teal)
    storageneuter_color = "\033[36m"
    # Color for DEBUGPLUS level (magenta/light purple - more verbose than DEBUG)
    debugplus_color = "\033[95m"

    FORMATS = {
        DEBUGPLUS:        format_time + format_name + format_level + debugplus_color + format_message + reset,
        logging.DEBUG:    format_time + format_name + format_level + blue  + format_message + reset,
        STORAGENEUTER:    format_time + format_name + format_level + storageneuter_color + format_message + reset,
        logging.INFO:     format_time + format_name + format_level + green + format_message + reset,
        logging.WARNING:  format_time + format_name + format_level + yellow+ format_message + reset,
        logging.ERROR:    format_time + format_name + format_level + red   + format_message + reset,
        logging.CRITICAL: format_time + format_name + format_level + critical_red + format_message + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.grey + "%(message)s" + self.reset)
        # Instead of altering the logger name color, change only the message color.
        # Note: 'catagory' is legacy misspelling, prefer 'category' but support both
        cat = getattr(record, 'category', getattr(record, 'catagory', None))
        if cat is not None and cat in self.CATEGORY_COLORS:
            # Determine the default message color based on the log level.
            default_level_color = {
                DEBUGPLUS: self.debugplus_color,
                logging.DEBUG: self.blue,
                logging.INFO: self.green,
                logging.WARNING: self.yellow,
                logging.ERROR: self.red,
                logging.CRITICAL: self.critical_red
            }.get(record.levelno, self.grey)
            default_message_fmt = default_level_color + self.format_message + self.reset
            new_message_fmt = self.CATEGORY_COLORS[cat] + self.format_message + self.reset
            log_fmt = log_fmt.replace(default_message_fmt, new_message_fmt, 1)
        formatter = logging.Formatter(log_fmt, "%Y-%m-%d %H:%M:%S")
        formatted_msg = formatter.format(record)
        if record.exc_info:
            formatted_msg = self.red + formatted_msg + self.reset
        
        # Ensure the formatted message is encodable
        try:
            formatted_msg.encode('ascii', errors='strict')
            return formatted_msg
        except UnicodeEncodeError:
            # Replace non-ASCII characters with safe alternatives
            safe_msg = formatted_msg.encode('ascii', errors='replace').decode('ascii')
            return safe_msg

def init_logger():
    # If logging is disabled, use a null handler with a level above CRITICAL
    # to suppress all log output without replacing the global getLogger function
    if logging_enabled.lower() == "false":
        root = logging.getLogger()
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 100)  # Level above CRITICAL suppresses all
        return

    # Generate timestamp for log filenames (once per server start)
    from datetime import datetime
    startup_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    fh = logging.handlers.RotatingFileHandler(f'logs/emulator_debug_{startup_timestamp}.log', maxBytes=20000000, backupCount=10)
    fh.setLevel(DEBUGPLUS)  # Set to DEBUGPLUS (5) to capture heartbeat and verbose debug messages
    fh2 = logging.handlers.RotatingFileHandler(f'logs/emulator_info_{startup_timestamp}.log', maxBytes=20000000, backupCount=5)
    fh2.setLevel(logging.INFO)
    er = logging.handlers.RotatingFileHandler(f'logs/emulator_error_{startup_timestamp}.log', maxBytes=20000000, backupCount=2)
    er.setLevel(logging.WARNING)
    # Use FlushingStreamHandler to ensure immediate output on Linux terminals
    ch = FlushingStreamHandler(sys.stdout)

    level = getattr(logging, loglevel.split('.', 1)[-1].upper(), logging.INFO)
    ch.setLevel(level)

    sys.stderr = StderrToLogger()
    fh.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    fh2.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    er.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    # ch.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    ch.setFormatter(CustomFormatter())
    ch.addFilter(SpecificDebugFilter())
    ch.addFilter(ProgressBarFilter())  # Apply the new filter

    handlers = []
    # Fix: Compare strings properly instead of using truthiness
    if logtofile.lower() == "true":
        handlers.extend([fh, fh2, er])
    handlers.append(ch)

    root = logging.getLogger()
    root.setLevel(DEBUGPLUS)  # Set to DEBUGPLUS (5) to allow heartbeat/verbose debug messages to propagate

    # On Linux, use direct handlers instead of QueueListener to avoid threading issues
    if sys.platform != 'win32':
        # Add handlers directly to root logger
        for handler in handlers:
            root.addHandler(handler)
    else:
        # Windows: use the queue-based approach
        queue_handler = QueueHandler(log_queue)
        root.addHandler(queue_handler)

        global queue_listener
        queue_listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
        queue_listener.start()


# ============================================================================
# TEST LOGGING SYSTEM - Consolidated log files for testing
# ============================================================================

_test_log_handler = None
_test_log_enabled = False
_test_log_lock = threading.Lock()


def _get_test_log_filename():
    """Generate a test log filename with current date/time and Steam/SteamUI versions."""
    from datetime import datetime
    import globalvars
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Get Steam and SteamUI versions, sanitize for filename (replace slashes/dots)
    steam_ver = str(globalvars.steam_ver).replace("/", "-").replace(".", "-")
    steamui_ver = str(globalvars.steamui_ver).replace("/", "-").replace(".", "-")
    return f"logs/test_log_{timestamp}_stv-{steam_ver}_stuiv-{steamui_ver}.log"


def init_test_logging():
    """
    Initialize the test logging system.
    Creates a new consolidated test log file that captures all log levels.
    Filename includes Steam and SteamUI version numbers.

    Returns:
        bool: True if test logging was initialized, False otherwise
    """
    global _test_log_handler, _test_log_enabled

    config = get_config()
    if config.get("enable_test_logging", "false").lower() != "true":
        return False

    with _test_log_lock:
        # Close existing handler if any
        if _test_log_handler is not None:
            close_test_logging()

        # Create logs directory if needed
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # Create new handler
        log_filename = _get_test_log_filename()
        _test_log_handler = logging.FileHandler(log_filename, encoding='utf-8')
        _test_log_handler.setLevel(logging.DEBUG)  # Capture all log levels
        _test_log_handler.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))

        # Add handler to root logger
        root = logging.getLogger()
        root.addHandler(_test_log_handler)

        _test_log_enabled = True

        # Log that test logging has started
        test_logger = logging.getLogger("TEST_LOG")
        test_logger.info(f"Test logging started - File: {log_filename}")

        return True


def rotate_test_logging():
    """
    Rotate the test log file.
    Closes the current test log and creates a new one.
    This is called after blob changes complete (when 'Steam Environment Information' is logged).
    New filename includes updated Steam and SteamUI version numbers.

    Returns:
        bool: True if rotation occurred, False otherwise
    """
    global _test_log_handler, _test_log_enabled

    config = get_config()
    if config.get("enable_test_logging", "false").lower() != "true":
        return False

    if not _test_log_enabled:
        return False

    with _test_log_lock:
        # Log that we're rotating
        test_logger = logging.getLogger("TEST_LOG")
        test_logger.info("Test log rotation - Closing current log due to blob change")

        # Close existing handler
        if _test_log_handler is not None:
            root = logging.getLogger()
            root.removeHandler(_test_log_handler)
            _test_log_handler.flush()
            _test_log_handler.close()
            _test_log_handler = None

        # Create new handler
        log_filename = _get_test_log_filename()
        _test_log_handler = logging.FileHandler(log_filename, encoding='utf-8')
        _test_log_handler.setLevel(logging.DEBUG)
        _test_log_handler.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))

        # Add handler to root logger
        root = logging.getLogger()
        root.addHandler(_test_log_handler)

        test_logger.info(f"Test logging rotated - New file: {log_filename}")

        return True


def close_test_logging():
    """
    Close the test logging system.
    Called on shutdown to finalize the test log.

    Returns:
        bool: True if test logging was closed, False otherwise
    """
    global _test_log_handler, _test_log_enabled

    if not _test_log_enabled:
        return False

    with _test_log_lock:
        if _test_log_handler is not None:
            # Log that we're closing
            test_logger = logging.getLogger("TEST_LOG")
            test_logger.info("Test logging shutdown - Closing log")

            root = logging.getLogger()
            root.removeHandler(_test_log_handler)
            _test_log_handler.flush()
            _test_log_handler.close()
            _test_log_handler = None

        _test_log_enabled = False
        return True


def is_test_logging_enabled():
    """Check if test logging is currently active."""
    return _test_log_enabled
