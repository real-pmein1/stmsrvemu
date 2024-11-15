import threading

from config import get_config as read_config
from utilities.database.cmdb import cm_dbdriver

config = read_config()
database = cm_dbdriver(config)

# Create a thread-local storage object
thread_local_data = threading.local()

def set_thread_variable(value):
    """
    Set a variable that is only valid within the current thread.
    """
    thread_local_data.extended_msg = value
    #print(f"Set variable in thread {threading.current_thread().name}: {thread_local_data.variable}")

def get_thread_variable():
    """
    Get the variable that is only valid within the current thread.
    """
    try:
        return thread_local_data.extended_msg
    except AttributeError:
        return None