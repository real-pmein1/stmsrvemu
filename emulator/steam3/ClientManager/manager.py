from datetime import datetime, timedelta

from overload import overload

from steam3.ClientManager.client import Client
from steam3.Types.community_types import PlayerState
from steam3.cm_packet_utils import CMPacket, MsgHdr_deprecated, ChatMessage
from steam3.Types.wrappers import ConnectionID, SteamID


class ClientManager:
    def __init__(self):
        self.clients_by_connid = {}
        self.clients_by_steamid = {}
        self.clients_by_ip_port = {}  # dictionary for IP and port mapping
        self.pending_updates = {}  # Dictionary to store pending statusupdates
        self.pending_messages = {}
        self.cmserver_obj = None

    # The following method is only used during the initialization, when we create the entry and then update the entry with steamID and connectionid when we have that information
    def add_or_update_client(self, client: Client) -> Client:
        if client.ip_port not in self.clients_by_ip_port:
            self.clients_by_ip_port[client.ip_port] = client
        if client.connectionid and client.connectionid not in self.clients_by_connid:
            self.clients_by_connid[client.connectionid] = client
        if client.steamID and client.steamID not in self.clients_by_steamid:
            self.clients_by_steamid[client.steamID] = client

        client.update_status_callback = self.queue_status_update
        client.process_heartbeat_callback = self.process_pending_updates
        client.remove_client_callback = self.remove_client
        client.send_message_callback = self.queue_message
        client.client_manager_callback = self
        return self.clients_by_ip_port.get(client.ip_port)

    def update_list(self, client):
        """Update manager lists with current id's."""
        if client:
            if client.steamID:
                self.clients_by_steamid[client.steamID] = client

    def get_client_by_identifier(self, identifier) -> Client:
        """for finding a client object by steam id wrap steamID in SteamID()
        The same goes for connectionid: ConnectionID"""
        if isinstance(identifier, SteamID):
            client = self.clients_by_steamid.get(identifier.id)
        elif isinstance(identifier, ConnectionID):
            client = self.clients_by_connid.get(identifier.id)
        elif isinstance(identifier, tuple):
            client = self.clients_by_ip_port.get(identifier)
        else:
            client = None
        return client

    @overload
    def remove_client(self, identifier):
        client = self.get_client_by_identifier(identifier)
        if client:
            if client.steamID in self.clients_by_steamid:
                del self.clients_by_steamid[client.steamID]
            if client.connectionid in self.clients_by_connid:
                del self.clients_by_connid[client.connectionid]
            if client.ip_port in self.clients_by_ip_port:
                del self.clients_by_ip_port[client.ip_port]

    def renew_heartbeat(self, identifier) -> Client:
        if isinstance(identifier, SteamID):
            client = self.get_client_by_identifier(identifier)

            client.last_recvd_heartbeat = datetime.now()

    # The following is used to clean out 'stale' clients, lazily; who have not sent a heartbeat in the past 5 minutees
    def check_and_remove_stale_clients(self):
        # FIXME figure out how/where to call this; seperate thread, during heartbeats, etc...
        """
        Checks all clients and removes those whose last heartbeat is older than 15 minutes.
        """
        current_time = datetime.now()
        stale_clients = []

        # Check all clients by connection ID for stale heartbeats
        for connid, client in list(self.clients_by_ip_port.items()):
            if hasattr(client, 'last_recvd_heartbeat') and (current_time - client.last_recvd_heartbeat > timedelta(minutes=3)):
                stale_clients.append((connid,client))

        # Remove all stale clients
        for connid, client in stale_clients:
            client.logoff_User(self.cmserver_obj) # This will set the user to the correct state if they time out
            self.remove_client(client)
            self.cmserver_obj.log.debug(f"Removed stale client {client.username} due to inactivity.")

    @overload
    def remove_client(self, client: Client):
        if client:
            if client.steamID in self.clients_by_steamid:
                del self.clients_by_steamid[client.steamID]
            if client.connectionid in self.clients_by_connid:
                del self.clients_by_connid[client.connectionid]
            if client.ip_port in self.clients_by_ip_port:
                del self.clients_by_ip_port[client.ip_port]

    def queue_status_update(self, steamid, status, username, appID = 0, ipaddr = 0, port = 0xFFFF):
        """User changed their status, we add status change to list to all of that user's friends
        and wait for their friends to send a heartbeat"""
        client = self.clients_by_steamid.get(steamid)
        if client and client.friends_list:
            for friend_entry, friend_relationship in client.friends_list:
                # Access friendsaccountID attribute from the FriendsList object
                friend_steamid = friend_entry.accountID  # Corrected this line
                # print(friend_entry)
                if friend_steamid in self.clients_by_steamid:
                    if friend_steamid not in self.pending_updates:
                        self.pending_updates[friend_steamid] = []
                    self.pending_updates[friend_steamid].append((steamid, status, appID, ipaddr, port, username))

    # noinspection InjectedReferences
    def queue_message(self, cm_object, msg_obj: ChatMessage):
        """User is sending a message to a friend, we hold it until that friend sends us a heartbeat"""
        if msg_obj.to not in self.pending_messages:
            self.pending_messages[msg_obj.to] = []
        self.pending_messages[msg_obj.to].append(msg_obj)

    def process_pending_updates(self, steamid):
        status_updates_list = []
        client_pending_messages = []

        # Retrieve and remove status updates if available
        if steamid in self.pending_updates:
            updates = self.pending_updates.pop(steamid)  # Retrieve and remove atomically
            for update_steamid, status, appID, ipaddr, port, username in updates:
                status_updates_list.append((update_steamid, status, appID, ipaddr, port, username))
                # print(f"Sending status update to {steamID}: {update_steamid} is now {status}, AppID: {appID}, IP: {ipaddr}, Port: {port}")

        # Retrieve and remove messages if available
        if steamid in self.pending_messages:
            messages = self.pending_messages.pop(steamid)  # Retrieve and remove atomically
            for message in messages:
                client_pending_messages.append(message)  # Assume message structure is correct as it is
                # print(f"Sending message to {steamID}: {message['sender_id']} says '{message['message']}'")

        return status_updates_list, client_pending_messages