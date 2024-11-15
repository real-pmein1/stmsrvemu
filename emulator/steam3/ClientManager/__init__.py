from steam3.ClientManager.manager import ClientManager


GLOBAL_CLIENT_ENTRIES = {}
Client_Manager = ClientManager()

def remove_client_entry(connectionID):
    if connectionID in GLOBAL_CLIENT_ENTRIES:
        del GLOBAL_CLIENT_ENTRIES[connectionID]

def update_client_entry(connectionID, **kwargs):
    if connectionID not in GLOBAL_CLIENT_ENTRIES:
        # If the entry doesn't exist, create a new one
        GLOBAL_CLIENT_ENTRIES[connectionID] = kwargs
    else:
        # If the entry exists, update its attributes
        GLOBAL_CLIENT_ENTRIES[connectionID].update(kwargs)

def find_chat_entry(connectionID):
    return GLOBAL_CLIENT_ENTRIES.get(connectionID, None)

def get_client_key(packet):
    connectionID = packet.source_id
    if connectionID not in GLOBAL_CLIENT_ENTRIES:
        # Create a new ChatRegistry entry if it doesn't exist
        GLOBAL_CLIENT_ENTRIES[connectionID] = {
                "connectionID":      connectionID,
                "client":              None
        }
    return GLOBAL_CLIENT_ENTRIES[connectionID]