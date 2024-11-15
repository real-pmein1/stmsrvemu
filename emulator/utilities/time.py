import struct
import time
import traceback
import re
from datetime import datetime, timedelta
from future.utils import old_div

from config import read_config

def get_current_datetime():
    # Get the current datetime object
    current_datetime = datetime.now()
    # Format the datetime object as "mm/dd/yyyy hr:mn:sec"
    formatted_datetime = current_datetime.strftime("%m/%d/%Y %H:%M:%S")
    return formatted_datetime


def add_100yrs(dt_str):
    # Check if the date string is empty or invalid
    if not dt_str or dt_str == b'\xe0' * 7 + b'\x00':
        # Return the current datetime plus 100 years
        return (datetime.now() + timedelta(days=365 * 100)).strftime("%m/%d/%Y %H:%M:%S")

    try:
        date_format = "%m/%d/%Y %H:%M:%S"
        if isinstance(dt_str, bytes):
            datetime_object = datetime.strptime(dt_str.decode('latin-1').rstrip('\x00'), date_format)
        else:
            datetime_object = datetime.strptime(dt_str.rstrip('\x00'), date_format)
        newdatetime = datetime_object + timedelta(days=365 * 100)
        return newdatetime.strftime(date_format)
    except ValueError:
        # Handle invalid date format
        return (datetime.now() + timedelta(days=365 * 100)).strftime("%m/%d/%Y %H:%M:%S")


def get_current_datetime_blob():
    # Get the current datetime object
    current_datetime = datetime.now()
    # Format the datetime object as "mm/dd/yyyy hr:mn:sec"
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H_%M_%S")
    return formatted_datetime


def sub_yrs(dt_str = get_current_datetime_blob(), years = 0, months = 0, days = 0):
    try:
        date_format = "%Y-%m-%d %H_%M_%S"
        if isinstance(dt_str, bytes):
            datetime_object = datetime.strptime(dt_str.decode('latin-1').rstrip('\x00'), date_format)
        else:
            datetime_object = datetime.strptime(dt_str.rstrip('\x00'), date_format)
        newdatetime = datetime_object + timedelta(days=365.25 * years)
        if months != 0:
            newdatetime += timedelta(days=(365.25 / 12) * months)
        if days != 0:
            newdatetime += timedelta(days=days)
        return newdatetime.strftime(date_format)
    except ValueError:
        # Handle invalid date format
        # Return the current datetime
        return (datetime.now()).strftime("%Y-%m-%d %H_%M_%S")


def steamtime_to_datetime(raw_bytes):
    steam_time = struct.unpack("<Q", raw_bytes)[0]
    unix_time = old_div(steam_time, 1000000) - 62135596800
    dt_object = datetime.utcfromtimestamp(unix_time)
    formatted_datetime = dt_object.strftime('%m/%d/%Y %H:%M:%S')
    return formatted_datetime


def datetime_to_steamtime(formatted_datetime):
    dt_object = datetime.strptime(formatted_datetime, '%m/%d/%Y %H:%M:%S')
    unix_time = int((dt_object - datetime(1970, 1, 1)).total_seconds())
    steam_time = (unix_time + 62135596800) * 1000000
    byte_array = struct.pack("<Q", steam_time)

    return byte_array


def steamtime_to_unixtime(steamtime_bin):
    steamtime = struct.unpack("<Q", steamtime_bin)[0]
    unixtime = steamtime / 1000000 - 62135596800
    return unixtime


def unixtime_to_steamtime(unixtime):
    steamtime = int((unixtime + 62135596800) * 1000000)  # Ensure steamtime is an integer
    steamtime_bin = struct.pack("<Q", steamtime)
    return steamtime_bin


def get_nanoseconds_since_time0():
    before_time0 = 62135596800
    current = int(time.time())
    now = current + before_time0
    nano = 1000000
    now *= nano
    return now


def is_datetime_older_than_15_minutes(date_time_str):
    # Convert the date/time string to a datetime object
    date_time_obj = datetime.strptime(date_time_str, "%m/%d/%Y %H:%M:%S")

    # Get the current datetime
    current_time = datetime.now()

    # Calculate the datetime that is 15 minutes before the current datetime
    time_15_minutes_ago = current_time - timedelta(minutes=15)

    # Check if the date_time_obj is older than 15 minutes
    return date_time_obj < time_15_minutes_ago


def every(delay, task):
    next_time = time.time() + delay
    while True:
        time.sleep(max(0, next_time - time.time()))
        try:
            task()
        except Exception:
            traceback.print_exc()
            # in production code you might want to have this instead of course:
            # logger.exception("Problem while executing repetitive task.")
        # skip tasks if we are behind schedule:
        next_time += (time.time() - next_time) // delay * delay + delay


def get_expiration_seconds() -> int:
    config_setting = read_config()
    config_setting = config_setting['ticket_expiration_time_length'].lower()
    # Regex to extract days, hours, minutes, and seconds from the config string
    pattern = r'(?P<days>\d+)d(?P<hours>\d+)h(?P<minutes>\d+)m(?P<seconds>\d+)s'
    match = re.match(pattern, config_setting)

    if not match:
        raise ValueError("Invalid configuration format")

    days = int(match.group('days'))
    hours = int(match.group('hours'))
    minutes = int(match.group('minutes'))
    seconds = int(match.group('seconds'))

    # Calculate total seconds
    total_seconds = days * 24 * 3600 + hours * 3600 + minutes * 60 + seconds

    return total_seconds