import threading


from config import get_config as read_config

from utilities.database.cmdb import get_cmdb

config = read_config()
database = get_cmdb()
chatroom_manager = None
stats_manager = None
lobby_manager = None
clan_manager = None
# Create a thread-local storage object
thread_local_data = threading.local()

# Job ID counter to keep all jobIDs unique
job_id_counter = 1

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

def create_chatroom_manager():
    from steam3.Managers.ChatroomManager.manager import ChatroomManager
    global chatroom_manager
    chatroom_manager = ChatroomManager(database)

def create_stats_manager():
    from steam3.Managers.StatsManager.manager import StatsManager
    global stats_manager
    stats_manager = StatsManager(database)

def create_lobby_manager():
    from steam3.Managers.LobbyManager.lobby_manager import LobbyManager
    global lobby_manager
    lobby_manager = LobbyManager(database)

def create_clan_manager():
    from steam3.Managers.ClanManager.clan_manager import ClanManager
    global clan_manager
    clan_manager = ClanManager(database)

create_chatroom_manager()
create_stats_manager()
create_lobby_manager()
create_clan_manager()