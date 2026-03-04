import threading
from datetime import datetime, timedelta

from steam3.ClientManager.client import Client
from steam3.Types.community_types import PlayerState
from steam3.cm_packet_utils import CMPacket, MsgHdr_deprecated, ChatMessage
from steam3.Types.wrappers import AccountID, ConnectionID

class ClientManager:
    def __init__(self):
        self.clients_by_connid = {}
        self.clientsByAccountID = {}
        self.clients_by_ip_port = {}  # dictionary for IP and port mapping
        self.pending_updates = {}  # Dictionary to store pending statusupdates
        self.pending_messages = {}
        self.cmserver_obj = None
        self._lock = threading.RLock()  # Reentrant lock for thread safety

    # The following method is only used during the initialization, when we create the entry and then update the entry with steamID and connectionid when we have that information
    def add_or_update_client(self, client: Client) -> Client:
        with self._lock:
            # IMPORTANT: Use int() for all dictionary operations to ensure hash consistency
            account_id_int = int(client.accountID) if client.accountID else None

            # Check if an old client exists at the same IP/port (handles reconnection from same location)
            # This must be checked BEFORE accountID check to handle the case where a new client
            # reconnects with same IP/port but hasn't authenticated yet (no accountID)
            if client.ip_port and client.ip_port in self.clients_by_ip_port:
                old_client = self.clients_by_ip_port[client.ip_port]
                if old_client is not client:  # Don't remove self
                    # Remove old client from all dictionaries
                    old_account_id = int(old_client.accountID) if old_client.accountID else None
                    if old_account_id and old_account_id in self.clientsByAccountID:
                        del self.clientsByAccountID[old_account_id]
                    if old_client.connectionid and old_client.connectionid in self.clients_by_connid:
                        del self.clients_by_connid[old_client.connectionid]
                    del self.clients_by_ip_port[client.ip_port]

            # If this user (by accountID) already exists, remove the old entry
            # This handles reconnection from a different IP/port (e.g., client restart, NAT port change)
            if account_id_int and account_id_int in self.clientsByAccountID:
                old_client = self.clientsByAccountID[account_id_int]
                if old_client is not client:  # Don't remove self
                    # Remove old entries from all dictionaries
                    if old_client.ip_port and old_client.ip_port in self.clients_by_ip_port:
                        del self.clients_by_ip_port[old_client.ip_port]
                    if old_client.connectionid and old_client.connectionid in self.clients_by_connid:
                        del self.clients_by_connid[old_client.connectionid]
                    del self.clientsByAccountID[account_id_int]

            # Now add the new client to all dictionaries
            if client.ip_port:
                self.clients_by_ip_port[client.ip_port] = client
            if client.connectionid:
                self.clients_by_connid[client.connectionid] = client
            if account_id_int:
                self.clientsByAccountID[account_id_int] = client

            client.update_status_callback = self.queue_status_update
            client.process_heartbeat_callback = self.process_pending_updates
            client.remove_client_callback = self.remove_client
            client.send_message_callback = self.queue_message
            client.client_manager_callback = self
            return self.clients_by_ip_port.get(client.ip_port)

    def update_list(self, client):
        """Update manager lists with current id's."""
        with self._lock:
            if client:
                if client.steamID:
                    # IMPORTANT: Use int() for dictionary key to ensure hash consistency
                    self.clientsByAccountID[int(client.accountID)] = client

    def get_client_by_identifier(self, identifier) -> Client:
        """for finding a client object by steam id wrap steamID in SteamID()
        The same goes for connectionid: ConnectionID"""
        with self._lock:
            if isinstance(identifier, AccountID):
                # AccountID wrapper has different hash than plain int, convert to int for lookup
                client = self.clientsByAccountID.get(int(identifier))
            elif isinstance(identifier, ConnectionID):
                # ConnectionID wrapper has different hash than plain int, convert to int for lookup
                client = self.clients_by_connid.get(int(identifier))
            elif isinstance(identifier, tuple):
                client = self.clients_by_ip_port.get(identifier)
            else:
                client = None
            return client

    def get_client_by_accountID(self, identifier):
        """for finding a client object by account ID (as int or AccountID wrapper)"""
        with self._lock:
            # Convert to plain int for lookup (AccountID wrapper has different hash)
            account_id = int(identifier)
            client = self.clientsByAccountID.get(account_id)
            if not client:
                return None
            return client

    def get_client_by_ip(self, ip_address: str):
        """
        Return the first Client whose ip_port tuple's IP matches ip_address.
        If no client is found for that IP, returns None.
        """
        with self._lock:
            for (ip, port), client in self.clients_by_ip_port.items():
                if ip == ip_address:
                    return client
            return None

    def get_client_by_steamid(self, steam_id: int):
        """
        Find a client by their 64-bit Steam ID.
        Extracts the account ID from the Steam ID and looks up in clientsByAccountID.

        :param steam_id: 64-bit Steam ID (integer)
        :return: Client object or None if not found
        """
        from steam3.Types.steamid import SteamID

        with self._lock:
            # Convert 64-bit Steam ID to account ID for lookup
            steam_id_obj = SteamID.from_raw(steam_id)
            account_id = int(steam_id_obj.get_accountID())
            return self.clientsByAccountID.get(account_id)

    def remove_client(self, identifier):
        """Remove a client by instance or identifier."""
        with self._lock:
            if isinstance(identifier, Client):
                client = identifier
            else:
                # Note: get_client_by_identifier also uses the lock, but RLock is reentrant
                client = self.get_client_by_identifier(identifier)

            if client:
                # Clean up chatroom memberships before removing client
                try:
                    import steam3
                    if steam3.chatroom_manager and client.steamID:
                        steam3.chatroom_manager.handle_client_disconnect(client.steamID)
                except Exception as e:
                    # Don't let chatroom cleanup failure prevent client removal
                    pass

                # Clean up P2P relay sessions before removing client
                try:
                    if hasattr(self, 'cmserver_obj') and self.cmserver_obj:
                        if hasattr(self.cmserver_obj, 'relay') and self.cmserver_obj.relay:
                            client_ip = client.ip_port[0] if client.ip_port else None
                            if client_ip:
                                self.cmserver_obj.relay.unregister_session(client_ip)
                except Exception as e:
                    # Don't let relay cleanup failure prevent client removal
                    pass

                # IMPORTANT: Use int() for dictionary operations to ensure hash consistency
                account_id_int = int(client.accountID) if client.accountID else None
                if account_id_int and account_id_int in self.clientsByAccountID:
                    del self.clientsByAccountID[account_id_int]
                if client.connectionid in self.clients_by_connid:
                    del self.clients_by_connid[client.connectionid]
                if client.ip_port in self.clients_by_ip_port:
                    del self.clients_by_ip_port[client.ip_port]

    def renew_heartbeat(self, identifier):
        client = self.get_client_by_identifier(identifier)
        client.last_recvd_heartbeat = datetime.now()

    # The following is used to clean out 'stale' clients lazily; clients that
    # have not sent a heartbeat within the last few minutes.
    def check_and_remove_stale_clients(self, exclude_account_id=None):
        """
        Checks all clients and removes those whose last heartbeat is older than
        5 minutes. Offline clients are logged out and removed from the manager
        lists.

        :param exclude_account_id: AccountID to exclude from stale check (e.g., the client
                                   that just sent a heartbeat triggering this check)
        """
        current_time = datetime.now()
        stale_timeout = timedelta(minutes=5)

        # Use lock to prevent race conditions with heartbeat updates
        with self._lock:
            # Get snapshot of clients to check
            clients_snapshot = list(self.clients_by_ip_port.items())

        # Check each client (outside the lock to avoid holding it too long)
        for ip_port, client in clients_snapshot:
            # Skip the client that triggered this check (they just sent a heartbeat)
            if exclude_account_id is not None and hasattr(client, 'accountID'):
                if client.accountID == exclude_account_id:
                    continue

            last_hb = getattr(client, 'last_recvd_heartbeat', None)
            if last_hb is None:
                # Skip clients that haven't sent any heartbeat yet (newly connected)
                continue

            # Re-check the timestamp right before removal to avoid race conditions
            # (another thread may have updated it since we started iterating)
            time_since_heartbeat = current_time - last_hb
            if time_since_heartbeat > stale_timeout:
                # Double-check the timestamp is still stale (handles race with renew_heartbeat)
                current_last_hb = getattr(client, 'last_recvd_heartbeat', None)
                if current_last_hb and (datetime.now() - current_last_hb) > stale_timeout:
                    if client and hasattr(client, 'username') and client.username:
                        self.cmserver_obj.log.debug(
                            f"Removing stale client {client.username} - "
                            f"last heartbeat: {current_last_hb}, current time: {datetime.now()}"
                        )
                        client.logoff_User(self.cmserver_obj)
                        self.remove_client(AccountID(client.accountID))


    def queue_status_update(self, accountID, status, username, appID = 0, ipaddr = 0, port = 0xFFFF):
        """User changed their status, we add status change to list to all of that user's friends
        and wait for their friends to send a heartbeat"""
        # IMPORTANT: Use int() for dictionary operations to ensure hash consistency
        account_id_int = int(accountID) if accountID else None
        client = self.clientsByAccountID.get(account_id_int)
        if client and client.friends_list:
            for friend_entry, friend_relationship in client.friends_list:
                # Access friendsaccountID attribute from the FriendsList object
                friendsAccountID = int(friend_entry.accountID)  # Convert to int for dict lookup
                # print(friend_entry)
                if friendsAccountID in self.clientsByAccountID:
                    if friendsAccountID not in self.pending_updates:
                        self.pending_updates[friendsAccountID] = []
                    self.pending_updates[friendsAccountID].append((accountID, status, appID, ipaddr, port, username))

    # noinspection InjectedReferences
    def queue_message(self, cm_object, msg_obj: ChatMessage):
        """User is sending a message to a friend, we hold it until that friend sends us a heartbeat"""
        if msg_obj.toSteamID not in self.pending_messages:
            self.pending_messages[msg_obj.toSteamID] = []
        self.pending_messages[msg_obj.toSteamID].append(msg_obj)

    def process_pending_updates(self, accountID):
        status_updates_list = []
        client_pending_messages = []

        # IMPORTANT: Use int() for dictionary operations to ensure hash consistency
        account_id_int = int(accountID) if accountID else None

        # Retrieve and remove status updates if available
        if account_id_int and account_id_int in self.pending_updates:
            updates = self.pending_updates.pop(account_id_int)  # Retrieve and remove atomically
            for update_steamid, status, appID, ipaddr, port, username in updates:
                status_updates_list.append((update_steamid, status, appID, ipaddr, port, username))
                # print(f"Sending status update to {steamID}: {update_steamid} is now {status}, AppID: {appID}, IP: {ipaddr}, Port: {port}")

        # Retrieve and remove messages if available
        if account_id_int and account_id_int in self.pending_messages:
            messages = self.pending_messages.pop(account_id_int)  # Retrieve and remove atomically
            for message in messages:
                client_pending_messages.append(message)  # Assume message structure is correct as it is
                # print(f"Sending message to {steamID}: {message['sender_id']} says '{message['message']}'")

        return status_updates_list, client_pending_messages

    def get_all_connected_clients(self) -> list:
        """
        Returns a list of all connected and logged-in clients.
        A client is considered connected if:
        - They have a valid steamID (authenticated)
        - Their client_state is not offline
        - They have received at least one heartbeat (active connection)
        """
        connected_clients = []

        with self._lock:
            # Use clients_by_ip_port as the primary source since it's always populated
            for client_obj in self.clients_by_ip_port.values():
                if client_obj is None:
                    continue
                # Check if client has authenticated (steamID is set)
                if not client_obj.steamID:
                    continue
                # Check if client is not offline
                if client_obj.client_state == PlayerState.offline:
                    continue
                connected_clients.append(client_obj)

        return connected_clients