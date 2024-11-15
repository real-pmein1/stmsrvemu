import logging
import logging.handlers
import os
import re
import sys
import traceback

from config import read_config

config = read_config()
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

os.system('color')  # NEEDED FOR WINDOWS SERVER COLORING

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
            self.logger.log(self.log_level, message.rstrip())

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
    logger = logging.getLogger("EXCEPTION")
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, tb))
    # Log the exception
    logger.critical("Uncaught exception: " + tb_str)


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
        if config.get("enable_progress_bar", False) and record.name == "GCFCHKSUM" or record.name == "converter":
            return False  # Do not log to console for this logger if progress bar is enabled
        else:
            return True


sys.excepthook = custom_exception_handler
sys.unraisablehook = custom_exception_handler


class ColoredFormatter(logging.Formatter):

    COLORS = {"MODULE": "\033[93m",  # yellow
            "LEVEL":    "\033[90m",  # Aqua for level indicator
            "WARNING":  "\033[93m",  # Yellow
            "INFO":     "\033[32;10m",  # Green
            "DEBUG":    "\033[94m",  # Blue
            "CRITICAL": "\033[91m",  # Red
            "ERROR":    "\033[91m",  # Red
            "EXCEPTION":"\033[31",  # Dark Red for Exceptions
            "TIME":     "\033[37m", "RESET":"\033[0m"  # Reset
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

    def formatTime(self, record, datefmt = None):
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
    blue = "\033[94m"  # debug
    green = "\033[32;10m"  # info
    time = "\033[37m"
    module = "\033[93m"  # yellow (was also for warning)
    level = "\033[90m"  # aqua
    reset = "\x1b[0m"

    # "EXCEPTION":"\033[31",  # Dark Red for Exceptions

    format_time = time + "%(asctime)-24s"
    format_name = module + "%(name)-14s"
    format_level = level + "%(levelname)-9s"
    format_message = "%(message)s"

    FORMATS = {
        logging.DEBUG: format_time + format_name + format_level + blue + format_message + reset,
        logging.INFO: format_time + format_name + format_level + green + format_message + reset,
        logging.WARNING: format_time + format_name + format_level + yellow + format_message + reset,
        logging.ERROR: format_time + format_name + format_level + red + format_message + reset,
        logging.CRITICAL: format_time + format_name + format_level + critical_red + format_message + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.grey + "%(message)s" + self.reset)
        formatter = logging.Formatter(log_fmt, "%Y-%m-%d %H:%M:%S")
        formatted_msg = formatter.format(record)

        # Check if the record is an exception and apply red coloring
        if record.exc_info:
            formatted_msg = self.red + formatted_msg + self.reset

        return formatted_msg

def init_logger():
    if not logging_enabled:  # This creates a dummy logger class so that any logging calls will be sent into a blackhole rather than erroring
        class DummyLogger:
            def __getattr__(self, _):
                def dummy(*args, **kwargs):
                    pass
                return dummy
        logging.getLogger = lambda *args, **kwargs: DummyLogger()
        return

    fh = logging.handlers.RotatingFileHandler('logs\\neuter_debug.log', maxBytes = 20000000, backupCount = 10)
    fh.setLevel(logging.DEBUG)
    fh2 = logging.handlers.RotatingFileHandler('logs\\neuter_info.log', maxBytes = 20000000, backupCount = 5)
    fh2.setLevel(logging.INFO)
    er = logging.handlers.RotatingFileHandler('logs\\neuter_error.log', maxBytes = 20000000, backupCount = 2)
    er.setLevel(logging.WARNING)
    #ch = logging.StreamHandler(sys.stdout)

    level = getattr(logging, loglevel.split('.')[-1], logging.INFO)
    #ch.setLevel(level)

    sys.stderr = StderrToLogger()
    fh.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    fh2.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    er.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    # ch.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
    #ch.setFormatter(CustomFormatter())
    #ch.addFilter(SpecificDebugFilter())
    #ch.addFilter(ProgressBarFilter())  # Apply the new filter

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    if logtofile:
        root.addHandler(fh)
        root.addHandler(fh2)
        root.addHandler(er)
    #root.addHandler(ch)