
from datetime import datetime, timedelta
from enum import IntEnum
import queue

from copy import copy, deepcopy
import os
import threading
import time


class ConnectionState(IntEnum):
    """
    Connection state machine matching Valve's CUDPConnection states.
    From IDA analysis of steamclient_linux.so CUDPConnection class.
    """
    UNCONNECTED = 0      # No connection
    CONNECTING = 1       # Handshake in progress
    CONNECTED = 2        # Fully connected, ready for data
    DISCONNECTING = 3    # Connection teardown in progress

import globalvars
from steam3.Managers.cloudstoragemanager import CloudStorageManager, CloudJobManager
from steam3.Managers.JobManager.client_job_registry import ClientJobRegistry
from steam3.ClientManager.client_permissions import PERM_ADD_FRIENDS, PERM_CHANGE_EMAIL, PERM_CHANGE_PASSWORD, PERM_CHANGE_SECURITY_QUESTION, PERM_CREATE_CLANS, PERM_CREATE_GROUPS, PERM_CREATE_LOBBY, PERM_JOIN_CLANS, PERM_JOIN_GAMES, PERM_JOIN_GROUPS, PERM_LAUNCH_APPLICATIONS, PERM_LOGIN, PERM_MUTE_FRIENDS, PERM_PURCHASE, PERM_RECEIVE_FRIEND_REQUESTS, PERM_REGISTER_CDKEYS, PERM_RUN_SERVER, PERM_SEND_GUEST_PASSES
from steam3 import database
from steam3.Responses.friends_responses import send_statuschange_to_friends
from steam3.Types.community_types import FriendRelationship, PlayerState
from steam3.Types.chat_types import ChatEntryType
from steam3.cm_packet_utils import ChatMessage
from utilities.database.base_dbdriver import FriendsRegistry
from utilities.impsocket import is_lan_ip

class Client:
    def __init__(self, ip_port: tuple = None,  symmetric_key = None, connectionid = None, steamid = None,  client_state = PlayerState.offline,
            account_type = None, username = None, chatroom = None, email = '', ratelimit: int = 0, sequencenumber: int = 0, lastrecieved_seq: int = 0, serverconnectionid = 0):
        self.connectionid = connectionid
        self.isLan = False
        self.serverconnectionid = serverconnectionid
        self.sessionID = 0
        self.symmetric_key = symmetric_key
        self.hmac_key = b''
        self.steamID = steamid
        self.accountID = None
        self.ip_port = ip_port
        self.client_state = client_state
        self.account_type = account_type
        self.username = username
        self.chatroom = chatroom
        self.email = email
        self.ratelimit = ratelimit

        # === CONNECTION STATE ===
        # Tracks the state of the UDP connection (from IDA: CUDPConnection states)
        self.connection_state = ConnectionState.UNCONNECTED

        # === SEQUENCE NUMBER TRACKING ===
        # Based on IDA analysis of CUDPConnection class fields:
        #   m_nOurSeqNext (+0x94): Our next outgoing sequence number
        #   m_nOurSeqAcked (+0x98): Last of our sequences ACKed by them
        #   m_nTheirSeqReceived (+0x9C): Last sequence we received from them
        #   m_nTheirSeqAcked (+0xA0): Last of their sequences we ACKed

        # Lock for thread-safe sequence operations
        self.sequence_lock = threading.Lock()

        # Lock for serializing packet sends to this client
        # This ensures packets are sent in the order their sequence numbers are assigned
        # Using RLock to allow recursive calls (e.g., when sendReply calls itself for multiple packets)
        self.send_lock = threading.RLock()

        # Server's outgoing sequence counter - incremented only when WE send packets
        # This should NEVER be modified when receiving packets (equivalent to m_nOurSeqNext)
        self.sequence_number = sequencenumber

        # Last sequence number we received FROM the client (equivalent to m_nTheirSeqReceived)
        # Used to ACK client packets and validate incoming sequence
        self.last_recvd_sequence = lastrecieved_seq

        # Last of OUR sequence numbers that the client has ACK'd (equivalent to m_nOurSeqAcked)
        # Updated when we receive a packet with last_recv_seq field
        self.last_acked_by_client = 0

        # Pending ACKs tracking - maps our outgoing seq_num to (timestamp, packet_info)
        # Used to detect/retry unacknowledged messages
        self.pending_acks = {}
        self.pending_acks_lock = threading.Lock()
        self.publicIP = None
        self.privateIP = None
        self.is_in_app = False
        self.is_machineID_set = False
        self.appID = 0
        self.app_ip_port = (0, 0xFFFF)
        self.avatarID = b'fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb'  # Default ? avatar
        self.session_token = None
        self.onetimepass = None
        self.login_key = ''
        self.login_key_uniqueID = None
        self.is_newPacketType = False
        self.is_proto = False  # Whether client uses protobuf messages
        self.last_extended_msg = None
        self.last_recvd_heartbeat = None
        # Cache the last request's sourceJobID for job routing
        # This is used as a fallback when thread_local_data.extended_msg is not available
        self.last_request_source_job_id = None
        self.protocol_version = 0
        self.friends_list = []
        self.friends_relationships = []
        self.groups_list = []
        self.socket = None
        self.objCMServer = None

        # Flag for pending encryption request (used in UDP handshake)
        # When True, the ChannelEncryptRequest will be sent on the next packet from client
        # This implements the proper "wait for client ACK" behavior like tinserver
        self.pending_encryption_request = False

        # Per-client send queue to eliminate lock contention
        # One worker thread handles all sends for this client
        self._send_queue = queue.Queue(maxsize=200)
        self._send_worker_thread = None
        self._send_worker_running = False

        # Per-client job manager for cloud storage operations (legacy)
        self.job_manager = CloudJobManager(self)
        cloud_root = os.path.join(globalvars.config["web_root"], globalvars.config["cloud_root"])
        self.cloudmanager = CloudStorageManager(cloud_root, self.job_manager)

        # Job context registry for request/response job ID routing
        # This tracks active job contexts for proper targetJobID routing
        self.job_registry = ClientJobRegistry(self)

        # Active ServerJobs for this client (for cleanup on disconnect)
        self._active_server_jobs = {}

        self.update_status_callback = None
        self.process_heartbeat_callback = None
        self.remove_client_callback = None
        self.send_message_callback = None
        self.client_manager_callback = None

        # Owned Subscriptions
        self.owned_subs = []         # Regular subscriptions (from AccountSubscriptionsRecord)
        self.owned_steam3_subs = []    # Steam3 subscriptions (from Steam3LicenseRecord)

        # FIXME figure out how permissions should be managed!
        self.permissions = (PERM_PURCHASE | PERM_SEND_GUEST_PASSES | PERM_CHANGE_EMAIL |
                            PERM_CHANGE_PASSWORD | PERM_CHANGE_SECURITY_QUESTION | PERM_REGISTER_CDKEYS |
                            PERM_LAUNCH_APPLICATIONS | PERM_LOGIN | PERM_ADD_FRIENDS | PERM_RECEIVE_FRIEND_REQUESTS |
                            PERM_CREATE_CLANS | PERM_CREATE_GROUPS | PERM_JOIN_CLANS | PERM_JOIN_GROUPS |
                            PERM_MUTE_FRIENDS | PERM_RUN_SERVER | PERM_JOIN_GAMES | PERM_CREATE_LOBBY)

    def login_User(self, cmserver_obj, machineIDs = None):
        """Finds or creates a friendsregistry entry for the user, sets all clients variables from database
        and returns any vacbans as a list of the class VacBans from the database or None if there are no bans"""
        # First check if the userid has an associated entry in FriendsRegistry, if not we create it
        # Convert to int since get_accountID() returns an AccountID wrapper
        self.accountID = int(self.steamID.get_accountID())
        userdb_entry, isnew = database.get_or_create_registry_entry(self.accountID)

        result = database.set_last_login(self.accountID)

        # Check if the user is connecting via LAN
        if is_lan_ip(self.publicIP):
            self.isLan = True

        self.username = deepcopy(userdb_entry.nickname)

        self.write_keys_to_file() # This is for figuring out missing packets
        # Auto-accept pending friend requests for newer protocol clients
        # Store the list of auto-accepted friends for notification after login
        self.auto_accepted_friends = []
        if self.protocol_version:
            if self.protocol_version > 65550:
                # Set all pending friend invite relationships to 'friend' (3) for both sides
                self.auto_accepted_friends = database.fix_invites(self.accountID)

        if machineIDs:
            overwrite = True if globalvars.config['overwrite_machineids'].lower() == 'true' else False
            # machineIDs is now a dictionary with keys: BB3, FF2, 3B3, BBB, 333 (any can be None)
            self.is_machineID_set = database.check_and_update_machine_ids(
                self.accountID,
                bb3=machineIDs.get('BB3'),
                ff2=machineIDs.get('FF2'),
                _3b3=machineIDs.get('3B3'),
                bbb=machineIDs.get('BBB'),
                _333=machineIDs.get('333'),
                overwrite=overwrite
            )
            # TODO do something with the machineID results.. maybe validate them to ensure the correct machine is logging in?
            #  perhaps keep a database table which contains all machine id's a user has attempted to log in with and add a column
            #  that will determine whether the machine is valid or not for logging in

        self.get_friends_list_from_db()
        self.update_status_info(cmserver_obj, PlayerState.online)
        self.get_joined_groups_list()
        # self.get_friends_relationships_from_db()  # Not needed, already called in get_friends_list_from_db()
        self.get_avatarID()
        self.load_owned_subscriptions() # Load all the users currently owned subscriptions.
        
        # Create/join clan chatrooms for 2008 client compatibility
        # Based on IDA analysis: clans automatically create persistent chatrooms
        self._ensure_clan_chatrooms(cmserver_obj)
        if self.symmetric_key:
            database.update_user_session_key(self.accountID, self.symmetric_key.rstrip(b'\x00').hex())
        if result:
            return self.get_vacbans()

        #print(f"Setting last login date/time failed, could not find user by userid: {cmserver_obj.steamID}")
        return False

    def write_keys_to_file(self):
        try:
            file_path = f"logs/{self.username}_symmetric_key.txt"
            # Convert bytes to hex representation to avoid null character issues
            sym_key_hex = self.symmetric_key.hex() if self.symmetric_key else "None"
            hmac_key_hex = self.hmac_key.hex() if self.hmac_key else "None"
            with open(file_path, 'a') as file:
                file.write(f'{datetime.now().strftime("%m/%d/%Y %H:%M:%S")}:\t\t'
                           f'symmetric key: {sym_key_hex}\n'
                           f'hmac: {hmac_key_hex}\n')
            print(f"Keys written to {file_path}")
        except Exception as e:
            print(f"An error occurred while writing to the file: {e}")

    def logoff_User(self, cmserver_obj, udpDisconnect = False):
        """Sets all instance information to 0
        Updates the database entries to 'offline'"""
        # Stop the send worker first to prevent sending to disconnected client
        self.stop_send_worker()

        # Cancel all active ServerJobs for this client
        from steam3.Managers.JobManager.server_job import ServerJob
        ServerJob.cancel_client_jobs(self)

        # Clear job context registry
        if hasattr(self, 'job_registry') and self.job_registry:
            self.job_registry.clear_all()

        self.update_status_info(cmserver_obj, PlayerState.offline, appID = 0, ipaddr = 0, port = 0xffff, gameserver_id = 0)
        database.set_last_logoff(self.accountID)

        # Clear appinfo tracking for this client
        from steam3.Managers.appinfo_tracker import get_appinfo_tracker
        get_appinfo_tracker().clear_client(self.connectionid)

        if self.socket or udpDisconnect == True: # If this client is connected via TCP ONLY OR if this is from the UDP disconnect packet
            self.remove_client_callback(self)

    def set_new_loginkey(self, key_uniqueID, loginkey):
        self.login_key = loginkey
        self.login_key_uniqueID = key_uniqueID
        database.update_user_login_key(self.accountID, loginkey)

    def set_symmetric_key(self, symmetric_key):
        self.symmetric_key = symmetric_key

    def set_new_sessionkey(self, sessionkey):
        self.session_token = sessionkey
        database.update_user_session_key(self.accountID, self.session_token.rstrip(b'\x00').hex())

    def disconnect_Game(self, cmserver_obj):
        self.exit_app(cmserver_obj, isloggedoff=False)

    def set_onetime_pass(self, otp):
        return database.set_onetime_pass( self.accountID, otp)

    def update_server_info(self, appID, ipaddr, port, gameserver_id):
        self.appID = appID
        self.app_ip_port = (ipaddr, port)
        self.is_in_app = True
        database.add_play_history(self.accountID, appID = appID, server_ip = ipaddr, server_port = port, serverID = gameserver_id)

    def update_status_info(self, cmserver_obj, new_status: PlayerState, appID = 0, ipaddr = 0, port = 0xffff, gameserver_id = 0, username = None, isloggedoff = False):
        """Sets the client instance state and DB entry to the new state
         If appID or ipaddr and port are present, it also updates the DB and instance ip_port information
         this will also update the played history database table"""

        if username:
            username = self.check_username(username)  # This checks if the nickname is different from the one in the DB and updates it, if different

        if ipaddr != 0 and port != 0 or appID != 0:
            self.update_server_info(appID, ipaddr, port, gameserver_id)

        if self.client_state != new_status:
            #if self.update_status_callback: # Should never be False/None
            #    self.update_status_callback( self.accountID, new_status, self.username, appID, ipaddr, port, username)
            self.client_state = new_status
            database.set_user_state(self.accountID, new_status)
            # Only notify friends when status ACTUALLY changes to avoid flooding
            # Also check that client_manager_callback is set (it's None during initial login before
            # the client is added to ClientManager - the auth handler handles initial notifications)
            if self.client_manager_callback:
                send_statuschange_to_friends(self, cmserver_obj, self.client_manager_callback, int(new_status))
        return self.client_state

    def exit_app(self, cmserver_obj, isloggedoff = False):
        """Sets the client instance app_ip_port to 0 indicating they are not playing a game
        updates the client state to online
        sets last played datetime in database lastplayed history table"""
        database.exiting_app(self.accountID)
        self.update_status_info(cmserver_obj, PlayerState.online, appID = 0, ipaddr = 0, port = 0xffff, gameserver_id = 0, isloggedoff = isloggedoff)
        self.appID = 0
        self.is_in_app = False
        self.app_ip_port = (0, 0xffff)
        if self.client_manager_callback:
            send_statuschange_to_friends(self, cmserver_obj, self.client_manager_callback, int(PlayerState.online))

    def get_vacbans(self):
        return database.get_vacban_by_userid(self.accountID)

    def is_appid_vacbanned(self, appid):
        """
        Check if a given appid is within any range in the appid_range_list.

        :param appid: The integer app ID to check.
        :return: True if the appid is within any range, False otherwise.
        """
        appid_range_list = database.get_vacban_by_userid(self.accountID)
        if appid_range_list is not None:
            for firstappid, lastappid in appid_range_list:
                if firstappid <= appid <= lastappid:
                    return True

        return False

    def get_friends_list_from_db(self):
        """Grabs the list of friends entries from the database
        Sets the friends_list to those entries
        returns the friend list"""
        # self.get_friends_relationships_from_db()
        returned_friends_list = database.get_user_friendslist_registry_entries(self.accountID)
        # print(f"Returned friends list size: {len(returned_friends_list)}")  # Debug print to check the size of the returned list
        self.friends_list = deepcopy(returned_friends_list)
        return self.friends_list

    def get_avatarID(self):
        self.avatarID = deepcopy(database.get_user_avatar(self.accountID))

    def get_friend_avatarID(self, accountID):
        avatarid = deepcopy(database.get_user_avatar(accountID))
        return avatarid

    def get_friend_lastseen(self, accountID):
        friendregistry_entry = deepcopy(database.get_user_details(accountID))
        # Return datetime objects directly - the serializers handle conversion
        # - serialize() (binary format for older clients) converts datetime.timestamp() to packed int
        # - to_protobuf() (protobuf format for newer clients) converts datetime.timestamp() to int
        last_login = friendregistry_entry.last_login if friendregistry_entry.last_login is not None else datetime.now()
        last_logoff = friendregistry_entry.last_logoff if friendregistry_entry.last_logoff is not None else datetime.now()
        return last_login, last_logoff

    def get_friends_nickname(self, accountID):
        """Directly fetches a friend's entry from the database by accountID."""
        # self.get_friends_relationships_from_db()
        nickname = database.get_user_nickname(accountID)
        if nickname is None:
            print(f"Account {accountID}\'s nickname is None")
            return '[unknown]'
        return nickname

    def get_joined_groups_list(self):
        returned_groups_list = database.get_user_groups(self.accountID)
        for group in returned_groups_list:
            self.groups_list.append(deepcopy(group))
        return self.groups_list

    def add_friend(self, friendsAccountID, relationship = FriendRelationship.requestInitiator):
        """Adds friend to client's database friendlist, updates instance friend_list"""
        # we set all friend invite relationships to 3, same for the inverse (requesting friend) for steam clients which use community website to accept requests.
        # FIXME: implement accepting friend requests into community website, and then figure out way to trigger friendslist refresh in CM after acceptance
        if self.protocol_version > 65550 and globalvars.config["auto_friend_later_clients"].lower() == "true":
            relationship = 3

        result = database.add_friend(self.accountID, friendsAccountID, relationship)

        # We grab a 'fresh' friendslist from the database to make sure our in-memory list isnt stale
        self.get_friends_list_from_db()
        return result

    def remove_friends(self, friendsAccountID):
        """Removes friend by steamID and updates the client instances friends_list from the database"""
        database.remove_friend(self.accountID, friendsAccountID)
        # We grab a 'fresh' friendslist from the database to make sure our in-memory list isnt stale
        self.get_friends_list_from_db()

    def block_friend(self, friendsAccountID, toBlock):
        if toBlock == 1:
            result = database.manage_friendship(self.accountID, friendsAccountID, "block")
        else:
            result = database.manage_friendship(self.accountID, friendsAccountID, "unblock")

        return result

    def renew_heartbeat(self):
        # TODO use this to detect disconnected users (timeout), and remove them from the manager list
        self.last_recvd_heartbeat = datetime.now()

    def find_friend_by_account_id(self, accountID) -> FriendsRegistry:
        """Uses next() to find the first matching friend by steamID, or return None if no match is found"""
        return next((friend for friend, rel in self.friends_list if friend.accountID == accountID), None)

    def find_relationship_by_friendsaccount_id(self, friendsAccountID):
        """Find specific relationship from friends_relationships"""
        return next((relation for relation in self.friends_relationships if relation.friendsaccountID == friendsAccountID), None)

    def check_username(self, username: str):
        """Checks the username against the username in the database
         if they differ, it sets the databaase username entry to the new username
         then it returns the new/current username"""
        self.username = database.get_or_set_nickname(self.accountID, username)
        return self.username

    def add_to_chat_history(self, msg_obj: ChatMessage, acked = 0):
        """Adds a new chat message to the user-to-user chat history table"""
        if ChatEntryType(msg_obj.type) == ChatEntryType.chatMsg:
            database.add_chat_history_entry(self.accountID, msg_obj.toSteamID, msg_obj.message, acked)

    def get_chat_history(self, toAccountID):
        """returns the chat history between two friends (returned as a list of FriendsChatHistory class"""
        return database.retrieve_chat_history(self.accountID, toAccountID)

    def get_heartbeat_updates(self):
        """Gets called during every heartbeat from the client
        This grabs all of the user's friends who updated their status since the last heartbeat
        and any messages clients sent to this user"""
        # TODO get rid of this, send status and messages immedietly when recieved by the intended receipient
        if self.process_heartbeat_callback:
            return self.process_heartbeat_callback(self.accountID)
        else:
            print("[CM Client] Error! cannot retrieve pending messages or status changes!")
            return None  # This means that the heartbeat callback variable wasnt set... should be impossible

    def send_message(self, cm_object, msg_obj: ChatMessage):
        """Adds the message to the chat history table
        also puts the message into the pending messages for the receipient userid"""
        self.add_to_chat_history(msg_obj)
        self.send_message_callback(cm_object, msg_obj)

    def sendReply(self, messageObjs):
        self.objCMServer.sendReply(self, messageObjs)

    # === SEND QUEUE METHODS ===
    # These methods implement a per-client send queue to eliminate lock contention
    # when multiple handler threads try to send to the same client simultaneously

    def start_send_worker(self):
        """Start the dedicated send worker thread for this client.

        Called after client is fully initialized and ready to receive packets.
        The send worker processes packets from the queue in order, ensuring
        sequence numbers are assigned and sent correctly without races.
        """
        if self._send_worker_running:
            return

        self._send_worker_running = True
        self._send_worker_thread = threading.Thread(
            target=self._send_worker_loop,
            daemon=True,
            name=f"send_worker_{self.ip_port}"
        )
        self._send_worker_thread.start()

    def stop_send_worker(self):
        """Stop the send worker thread gracefully."""
        self._send_worker_running = False
        # Put sentinel to unblock the queue
        try:
            self._send_queue.put_nowait((None, None))
        except queue.Full:
            pass
        if self._send_worker_thread and self._send_worker_thread.is_alive():
            self._send_worker_thread.join(timeout=2.0)
        self._send_worker_thread = None

    def queue_send(self, packets, priority=1):
        """Queue packets for ordered sending by the worker thread.

        Args:
            packets: List of response packets to send
            priority: Priority level for the packets (default 1)

        Returns:
            bool: True if queued successfully, False if queue full (client overwhelmed)
        """
        if not self._send_worker_running:
            # Fallback to direct send if worker not started
            if self.objCMServer:
                self.objCMServer.sendReply(self, packets)
            return True

        try:
            self._send_queue.put_nowait((packets, priority))
            return True
        except queue.Full:
            # Queue full - client is overwhelmed or disconnected
            return False

    def _send_worker_loop(self):
        """Worker thread loop that processes send queue.

        This runs in a dedicated thread per client, processing packets
        in queue order. This eliminates the race condition where multiple
        handler threads compete to send, causing sequence number issues.
        """
        while self._send_worker_running:
            try:
                # Wait for packets with timeout to allow checking running flag
                try:
                    packets, priority = self._send_queue.get(timeout=5.0)
                except queue.Empty:
                    continue

                # Check for sentinel value (stop signal)
                if packets is None:
                    break

                # Check if CM server is still valid
                if not self.objCMServer:
                    self._send_queue.task_done()
                    continue

                # Send packets using the CM server's method
                # This is now the only thread sending for this client
                try:
                    self.objCMServer.sendReply(self, packets)
                except Exception as e:
                    # Log but don't crash the worker
                    pass

                self._send_queue.task_done()

            except Exception as e:
                # Don't let exceptions kill the worker
                continue

    def __repr__(self):
        details = [
                f"connectionid={self.connectionid}",
                f"steamID='{self.steamID}'",
                f"ip_port={self.ip_port}",
                f"client_state={self.client_state.name}",
                f"account_type={self.account_type}",
                f"username='{self.username}'",
                f"chatroom={self.chatroom}",
                f"email='{self.email}'",
                f"ratelimit={self.ratelimit}",
                f"sequence_number={self.sequence_number}",
                f"last_recvd_sequence={self.last_recvd_sequence}",
                f"is_in_app={self.is_in_app}",
                f"appID={self.appID}",
                f"app_ip_port={self.app_ip_port}",
                f"last_recvd_heartbeat={self.last_recvd_heartbeat}",
        ]

        # Combine friends_list and friends_relationships by accountID
        combined_friends = {friend.accountID: friend for friend, rel in self.friends_list}
        for relationship in self.friends_relationships:
            if relationship.friendsaccountID in combined_friends:
                combined_friends[relationship.friendsaccountID].relationship = relationship.relationship_type
            else:
                combined_friends[relationship.friendsaccountID] = relationship

        # Add friends info
        details.append("Friends:")
        for friend in combined_friends.values():
            details.append(f"  {friend.nickname} (AccountID: {friend.accountID})")

        # Add groups info
        details.append("Groups:")
        for group in self.groups_list:
            details.append(f"  {group}")

        return "\n".join(details)

    def grab_potential_gift_targets(self, packageID):
        """Build a list of friends and mark whether they can receive a gift.

        Args:
            packageID (int): The subscription/package identifier being gifted.

        Returns:
            list[dict]: Each entry contains:
                ``index`` (int): Position in the list starting from 0.
                ``steamid`` (int): Friend's SteamID64.
                ``subscriptions`` (list[int]): Subscription IDs owned by the friend.
                ``valid`` (bool): ``True`` if the friend does **not** own ``packageID``.
        """

        friends_info = []
        if self.friends_list:
            flist = self.get_friends_list_from_db()
            for idx, (friend_entry, _) in enumerate(flist):
                friend_id = int(friend_entry.accountID)
                owned = database.get_user_owned_subscription_ids(friend_id)
                sub_ids = [entry["subscription_id"] for entry in owned]
                friends_info.append(
                    {
                        "index": idx,
                        "steamid": friend_id,
                        "subscriptions": sub_ids,
                        "valid": packageID not in sub_ids,
                    }
                )

        return friends_info

    def set_DBappTicket(self, appID, Ticket):
        return database.check_and_update_ownership_ticket(self.accountID, appID, Ticket)

    def get_addressEntryID(self, name, address1, address2, city, postcode, state, country_code, phone):
        """Get or create an address entry and return its ID."""
        return database.purchase_db.get_or_create_address(
            self.accountID, name, address1, address2, city, postcode, state, country_code, phone
        )

    def get_all_paymentcards(self):
        """Get all stored payment cards for this user."""
        return database.purchase_db.get_user_payment_methods(self.accountID)

    def get_or_set_paymentcardinfo(self, card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2):
        """Get or create a credit card entry and return its ID."""
        return database.purchase_db.get_or_create_cc_entry(
            self.accountID, card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2
        )

    def add_external_transactioninfo(self, packageID, transaction_type, transaction_data):
        """Create an external payment entry (PayPal, etc) and return its ID."""
        return database.purchase_db.create_external_payment_entry(
            self.accountID, packageID, transaction_type, transaction_data
        )

    def add_new_steam3_transaction(self, transaction_type, transaction_entry_id, package_id, address_entry_id,
                                    base_cost, discounts, tax_cost, shipping_cost, shipping_entry_id,
                                    guest_passes_included, gift_info=None):
        """Create a new transaction and return its ID."""
        return database.purchase_db.create_transaction(
            account_id=self.accountID,
            package_id=package_id,
            payment_type=transaction_type,
            payment_entry_id=transaction_entry_id,
            address_entry_id=address_entry_id,
            base_cost_cents=base_cost,
            discount_cents=discounts,
            tax_cents=tax_cost,
            shipping_cents=shipping_cost,
            shipping_entry_id=shipping_entry_id,
            pass_information=guest_passes_included,
            gift_info=gift_info
        )

    def cancel_transaction(self, transactionID):
        """Cancel a pending transaction."""
        return database.purchase_db.cancel_transaction(self.accountID, transactionID)

    def get_transaction(self, transactionID):
        """Get complete transaction details including related records."""
        return database.purchase_db.get_transaction_details(self.accountID, transactionID)

    def complete_transaction(self, transactionID):
        """Complete a transaction and grant the license."""
        return database.purchase_db.complete_transaction(self.accountID, transactionID)

    def validate_transaction(self, transactionID: int) -> int:
        """
        Validate a transaction.

        Returns:
            0 = Valid and ready for processing
            1 = Transaction not found
            2 = Transaction already completed
            3 = Transaction cancelled
            4 = Transaction expired
        """
        return database.purchase_db.validate_transaction(self.accountID, transactionID)

    def set_receipt_acknowledged(self, transactionID):
        """Mark a purchase receipt as acknowledged."""
        return database.purchase_db.acknowledge_receipt(self.accountID, transactionID)

    def load_owned_subscriptions(self):
        """
        Queries the database for owned subscriptions and separates them into two lists.
        """
        results = database.get_user_owned_subscription_ids(self.accountID)
        for entry in results:
            if entry.get('steam3'):
                self.owned_steam3_subs.append(entry['subscription_id'])
            else:
                self.owned_subs.append(entry['subscription_id'])

    def get_licenses(self):
        """
        Get all active licenses for this client from the database.

        Returns:
            List of Steam3LicenseRecord objects or empty list if none found
        """
        try:
            result = database.get_user_licenses(self.accountID)
            return result if result else []
        except Exception as e:
            # Return empty list if query fails
            return []

    def get_subscriptions(self):
        """
        Get all active subscriptions for this client from the legacy AccountSubscriptionsRecord table.

        These are subscriptions from the older Steam2 subscription system.

        Returns:
            List of AccountSubscriptionsRecord objects or empty list if none found
        """
        try:
            return database.get_user_subscriptions(self.accountID)
        except Exception as e:
            # Return empty list if query fails
            return []

    def owns_subscription(self, subscription_id: int) -> bool:
        """
        Check if the user currently owns a specific subscription.
        
        This method queries the database directly to get the current ownership state,
        rather than relying on potentially stale in-memory lists.
        
        Args:
            subscription_id: The subscription ID to check
            
        Returns:
            bool: True if the user owns this subscription, False otherwise
        """
        try:
            # Get current licenses from database
            licenses = database.get_user_licenses(self.accountID)
            if licenses:
                owned_package_ids = [license.PackageID for license in licenses]
                return subscription_id in owned_package_ids
            
            # Also check legacy owned subscriptions as backup
            results = database.get_user_owned_subscription_ids(self.accountID)
            for entry in results:
                if entry['subscription_id'] == subscription_id:
                    return True
                    
            return False
        except Exception as e:
            # If database query fails, fall back to in-memory lists as last resort
            return (subscription_id in self.owned_subs or 
                    subscription_id in self.owned_steam3_subs)

    def get_permissions(self) -> int:
        """
        Returns an integer bitmask representing this user's permissions.
        For now, it returns all permissions.
        """
        return self.permissions

    def get_owned_subscription_ids(self) -> dict:
        """
        Returns a dictionary with both lists for convenience.
        {
            'regular': self.owned_subs,
            'steam3': self.owned_steam3_subs
        }
        """
        return {'regular': self.owned_subs, 'steam3': self.owned_steam3_subs}

    def get_tax_rate_for_address(self, addressinfo_dict):
        return database.get_tax_rate_for_address(addressinfo_dict)

    def get_main_clan(self, accountid: int, relationship: int):
        """
        Retrieve the account ID of the main clan if `is_maingroup` is set to True.
        If no entry has `is_maingroup` set to True, return the `CommunityClanID` of the first clan in the list.

        :param session: SQLAlchemy Session instance
        :param account_id: The account ID to filter by
        :param relationship: The relationship value to filter by
        :return: The `CommunityClanID` of the main clan or the first clan in the list
        """

        clan_members = database.get_users_clan_list(accountid, relationship)

        if not clan_members:
            return None, None  # No entries found

        # Check if any clan has `is_maingroup` set to True
        for member in clan_members:
            if member.is_maingroup:
                return member.CommunityClanID, member.user_rank

        # If no clan has `is_maingroup` set to True, return the `CommunityClanID` of the first clan
        return clan_members[0].CommunityClanID, clan_members[0].user_rank

    def get_email_info(self):
         return database.get_user_email_and_verification_status(self.accountID)

    def get_accountflags(self):
        return database.compute_accountflags(self.accountID)

    def generate_verification_code(self):
        return database.generate_verification_code(self.accountID)

    def set_email_verified(self):
        database.set_email_verified(self.accountID)
        return

    def get_purchase_receipts(self, unacknowledged_only=False):
        """
        Retrieve completed purchase transactions for this client and convert them to receipt objects.

        Args:
            unacknowledged_only (bool): If True, only return unacknowledged receipts

        Returns:
            List of PurchaseReceipt objects for completed transactions
        """
        from steam3.Types.MessageObject.PurchaseReceipt import PurchaseReceipt
        from steam3.Types.steam_types import EPurchaseStatus, EPurchaseResultDetail, ECurrencyCode

        # Get completed transaction records using the new purchase database
        transaction_records = database.purchase_db.get_purchase_receipts(self.accountID, unacknowledged_only)
        receipts = []

        if not transaction_records:
            return receipts

        for trans_record in transaction_records:
            try:
                # Parse transaction date
                try:
                    dt = datetime.strptime(trans_record.TransactionDate, "%m/%d/%Y %H:%M:%S")
                    transaction_time_int = int(dt.timestamp())
                except Exception:
                    transaction_time_int = 0

                # Get country code from address if available
                country_code = "US"
                if trans_record.AddressEntryID:
                    address = database.purchase_db.get_address(trans_record.AddressEntryID)
                    if address and address.CountryCode:
                        country_code = address.CountryCode

                # Create PurchaseReceipt object with protocol version for format decisions
                receipt = PurchaseReceipt(
                    transaction_id=trans_record.UniqueID,
                    package_id=trans_record.PackageID,
                    purchase_status=EPurchaseStatus.Succeeded,
                    result_detail=EPurchaseResultDetail.NoDetail,
                    transaction_time=transaction_time_int,
                    payment_method=trans_record.PaymentType,
                    country_code=country_code,
                    base_price=trans_record.BaseCostInCents,
                    total_discount=trans_record.DiscountsInCents,
                    tax=trans_record.TaxCostInCents,
                    shipping=trans_record.ShippingCostInCents,
                    currency_code=ECurrencyCode.USD,
                    acknowledged=bool(trans_record.DateAcknowledged),
                    line_item_count=0,
                    protocol_version=self.protocol_version
                )

                # Add line item for the package
                receipt.add_line_item(
                    packageID=trans_record.PackageID,
                    base_price=trans_record.BaseCostInCents,
                    total_discount=trans_record.DiscountsInCents,
                    tax=trans_record.TaxCostInCents,
                    shipping=trans_record.ShippingCostInCents,
                    currency_code=ECurrencyCode.USD
                )

                receipts.append(receipt)

            except Exception as e:
                # Skip invalid records and continue
                continue

        return receipts

    def _ensure_clan_chatrooms(self, cmserver_obj):
        """
        Ensure clan chatrooms exist and are joined for 2008 client compatibility.
        
        IMPORTANT: Only creates chatrooms for users who are actually clan members.
        Does NOT assume any client is associated with a clan.
        
        Based on IDA analysis of 2008 Steam client:
        - Clans automatically have persistent chatrooms
        - Users auto-join their clan chatrooms on login ONLY if they're members
        - Clan chatrooms use ChatRoomType.clan with proper Steam IDs
        """
        try:
            # Check if user has ANY clan memberships at all
            clan_list = database.get_users_clan_list(self.accountID, relationship=3)  # Member relationship
            
            # Early return if user is not part of any clans
            if not clan_list or len(clan_list) == 0:
                cmserver_obj.log.debug(f"User {self.steamID} is not a member of any clans - skipping clan chatroom creation")
                return  # No clans to process - user is not in any clans
            
            # Get chatroom manager
            import steam3
            chatroom_manager = steam3.chatroom_manager
            
            for clan_member in clan_list:
                clan_id = clan_member.CommunityClanID
                
                try:
                    # Create clan Steam ID for the chatroom
                    from steam3.Types.steamid import SteamID
                    from steam3.Types.steam_types import EUniverse, EType, EInstanceFlag
                    
                    clan_steam_id_obj = SteamID()
                    clan_steam_id_obj.set_from_identifier(clan_id, EUniverse.PUBLIC, EType.Clan, EInstanceFlag.ALL)
                    clan_steam_id = int(clan_steam_id_obj)
                    
                    # Check if clan chatroom already exists
                    existing_chatroom = chatroom_manager.get_chatroom(clan_steam_id)
                    
                    if not existing_chatroom:
                        # Create persistent clan chatroom
                        from steam3.Types.chat_types import ChatRoomType
                        
                        chat_steam_id = chatroom_manager.register_chatroom(
                            owner_id=clan_id,  # Clan itself is owner
                            room_type=ChatRoomType.clan,
                            name=f"Clan_{clan_id}",  # Default clan chat name
                            clan_id=clan_id,
                            game_id=0,  # Clans not tied to specific games
                            officer_permission=0,  # Use defaults
                            member_permission=0,
                            all_permission=0,
                            max_members=100,  # Large member limit for clans
                            flags=0,  # Default flags
                            friend_chat_id=0,
                            invited_id=0
                        )
                        
                        if chat_steam_id != 0:
                            cmserver_obj.log.debug(f"Created clan chatroom {chat_steam_id:x} for clan {clan_id}")
                            existing_chatroom = chatroom_manager.get_chatroom(chat_steam_id)
                    
                    # Auto-join user to clan chatroom (if created or exists)
                    if existing_chatroom:
                        from steam3.Types.chat_types import ChatRoomEnterResponse
                        join_result = existing_chatroom.enter_chatroom(int(self.steamID), voice_speaker=False)
                        
                        if join_result == ChatRoomEnterResponse.success:
                            cmserver_obj.log.debug(f"User {self.steamID} auto-joined clan chatroom for clan {clan_id}")
                        else:
                            cmserver_obj.log.debug(f"User {self.steamID} failed to auto-join clan chatroom: {join_result}")
                
                except Exception as e:
                    cmserver_obj.log.error(f"Error creating/joining clan chatroom for clan {clan_id}: {e}")
                    continue
                    
        except Exception as e:
            cmserver_obj.log.error(f"Error ensuring clan chatrooms for user {self.steamID}: {e}")

    def get_user_licenses(self):
        """
        Retrieve all active licenses for this client.

        Returns:
            List of Steam3LicenseRecord objects for the client, or None if query fails
        """
        return database.get_user_licenses(self.accountID)

    # === GUEST PASS METHODS ===

    def get_guest_pass(self, guest_pass_id: int):
        """
        Retrieve a guest pass record by its unique ID.

        Args:
            guest_pass_id: The unique ID of the guest pass

        Returns:
            GuestPassRegistry object if found, None otherwise
        """
        return database.get_guest_pass_by_id(guest_pass_id)

    def redeem_guest_pass(self, guest_pass_id: int) -> tuple:
        """
        Redeem a guest pass for this client.

        Args:
            guest_pass_id: The unique ID of the guest pass to redeem

        Returns:
            Tuple of (success: bool, package_id: int, error_message: str or None)
        """
        # Get the guest pass record
        guest_pass = database.get_guest_pass_by_id(guest_pass_id)
        if not guest_pass:
            return (False, 0, "Guest pass not found")

        if guest_pass.Redeemed:
            return (False, 0, "Guest pass already redeemed")

        package_id = guest_pass.PackageID

        # Grant the license to this user (license_type=1 for guest pass)
        success = database.grant_license(
            account_id=self.accountID,
            package_id=package_id,
            license_type=1  # Guest pass license type
        )

        if not success:
            return (False, package_id, "Failed to grant license")

        # Mark the guest pass as redeemed
        database.update_GuestPass(
            gid=guest_pass_id,
            redeemed=1,
            recipient_address=str(self.accountID)
        )

        return (True, package_id, None)

    # === SEQUENCE NUMBER MANAGEMENT METHODS ===

    def get_next_sequence_number(self) -> int:
        """
        Thread-safely increment and return the next outgoing sequence number.
        This should be called when SENDING packets, not when receiving.

        Returns:
            int: The next sequence number to use for an outgoing packet
        """
        with self.sequence_lock:
            self.sequence_number += 1
            return self.sequence_number

    def get_current_sequence_number(self) -> int:
        """
        Thread-safely get the current outgoing sequence number without incrementing.

        Returns:
            int: The current sequence number
        """
        with self.sequence_lock:
            return self.sequence_number

    def set_sequence_number(self, value: int):
        """
        Thread-safely set the outgoing sequence number.
        Use sparingly - mainly for initialization during handshake.

        Args:
            value: The sequence number to set
        """
        with self.sequence_lock:
            self.sequence_number = value

    def initialize_after_handshake(self):
        """
        Initialize sequence numbers after handshake is complete.

        Based on tinserver and IDA analysis of connection handshake:
          ChallengeReq (0x01): client seq=1, ack=0
          Challenge (0x02):    server seq=1, ack=1
          Connect (0x03):      client seq=1 or 2, ack=1
          Accept (0x04):       server seq=2, ack=client_seq
          Data (0x06):         client seq=2 or 3, ack=2  <- First data packet!

        After handshake:
          - Server has sent 2 packets (Challenge + Accept): our_seq = 2
          - Client has sent 2 packets (ChallengeReq + Connect): last_recvd = 1 or 2
          - Client's Connect packet ACKed our Challenge (seq=1)
          - Next expected from client: seq 2 or 3
        """
        with self.sequence_lock:
            self.sequence_number = 2        # We've sent 2 packets (Challenge + Accept)
            self.last_recvd_sequence = 1    # Minimum: client sent at least ChallengeReq (seq=1)
            self.last_acked_by_client = 1   # Client's Connect ACKed our Challenge (seq=1)
            self.connection_state = ConnectionState.CONNECTED

        # Start the dedicated send worker thread for this client
        # This eliminates lock contention when multiple handlers send simultaneously
        self.start_send_worker()

    def set_connection_state(self, state: ConnectionState):
        """
        Set the connection state.

        Args:
            state: The new connection state
        """
        self.connection_state = state

    def get_connection_state(self) -> ConnectionState:
        """
        Get the current connection state.

        Returns:
            ConnectionState: The current connection state
        """
        return self.connection_state

    def update_client_sequence(self, client_seq: int, client_ack: int) -> bool:
        """
        Update tracking of client's sequence and their acknowledgment of our packets.
        Called when we RECEIVE a packet from the client.

        Based on tinserver UdpNetSocket::validateSequence logic:
        - If seq == expected (last_recvd + 1): Accept and update
        - If seq < expected: Duplicate packet - already processed
        - If seq > expected: Out-of-order packet - may be cached

        Args:
            client_seq: The sequence number from the client's packet (parsed_packet.sequence_num)
            client_ack: What the client is acknowledging (parsed_packet.last_recv_seq)

        Returns:
            bool: True if packet should be processed, False if duplicate/should skip
        """
        with self.sequence_lock:
            # Track what the client has acknowledged from us
            if client_ack > self.last_acked_by_client:
                self.last_acked_by_client = client_ack
                # Clean up pending ACKs for sequences that have been acknowledged
                self._cleanup_acked_packets(client_ack)

            # 0 is used for heartbeats/datagrams - always accept but don't update sequence
            if client_seq == 0:
                return True

            expected_seq = self.last_recvd_sequence + 1 if self.last_recvd_sequence > 0 else 1

            # In-order packet - this is what we expected
            if client_seq == expected_seq:
                self.last_recvd_sequence = client_seq
                return True

            # Duplicate packet - we already received and processed this
            # Client may be retransmitting because they didn't get our ACK
            elif client_seq <= self.last_recvd_sequence:
                # We'll need to send an ACK, but don't process the packet again
                return False

            # Out-of-order packet - future packet arrived before expected one
            # Tinserver tolerates up to 9 packets ahead (for packet reordering)
            elif client_seq > expected_seq:
                if client_seq <= expected_seq + 9:
                    # Within tolerance - accept and update sequence
                    # This skips the missing packets but allows connection to continue
                    self.last_recvd_sequence = client_seq
                    return True
                else:
                    # Too far out of order - reject
                    return False

            return True

    def _cleanup_acked_packets(self, acked_up_to: int):
        """
        Remove packets from pending_acks that have been acknowledged.
        Must be called while holding sequence_lock.

        Args:
            acked_up_to: All sequences up to and including this have been ACK'd
        """
        with self.pending_acks_lock:
            # Remove all pending ACKs up to the acknowledged sequence
            to_remove = [seq for seq in self.pending_acks.keys() if seq <= acked_up_to]
            for seq in to_remove:
                del self.pending_acks[seq]

    def register_sent_packet(self, seq_num: int, packet_info: str = ""):
        """
        Register a packet that we've sent and are waiting for ACK.

        Args:
            seq_num: The sequence number of the sent packet
            packet_info: Optional description of the packet for debugging
        """
        with self.pending_acks_lock:
            self.pending_acks[seq_num] = (time.time(), packet_info)

    def get_unacked_packets(self, timeout_seconds: float = 30.0) -> list:
        """
        Get list of packets that haven't been acknowledged within the timeout.

        Args:
            timeout_seconds: How long to wait before considering a packet unacked

        Returns:
            List of (seq_num, timestamp, packet_info) tuples for unacked packets
        """
        unacked = []
        current_time = time.time()
        with self.pending_acks_lock:
            for seq_num, (timestamp, packet_info) in self.pending_acks.items():
                if current_time - timestamp > timeout_seconds:
                    unacked.append((seq_num, timestamp, packet_info))
        return unacked

    def get_expected_client_sequence(self) -> int:
        """
        Get the expected next sequence number from the client.

        Returns:
            int: The expected sequence number (last_recvd + 1, or 1 if no packets received)
        """
        with self.sequence_lock:
            if self.last_recvd_sequence == 0:
                return 1  # First expected sequence from client
            return self.last_recvd_sequence + 1

    def is_duplicate_sequence(self, client_seq: int) -> bool:
        """
        Check if a client sequence number is a duplicate (already processed).

        Args:
            client_seq: The sequence number from the client's packet

        Returns:
            bool: True if this is a duplicate packet, False otherwise
        """
        with self.sequence_lock:
            if client_seq == 0:
                return False  # Heartbeats are never duplicates
            return client_seq <= self.last_recvd_sequence and self.last_recvd_sequence > 0

    def is_out_of_order_sequence(self, client_seq: int) -> tuple:
        """
        Check if a client sequence number is out of order (arrived before expected).

        Args:
            client_seq: The sequence number from the client's packet

        Returns:
            tuple: (is_out_of_order: bool, within_tolerance: bool)
                   - is_out_of_order: True if seq > expected
                   - within_tolerance: True if within 9 packets (acceptable gap)
        """
        with self.sequence_lock:
            if client_seq == 0:
                return (False, True)  # Heartbeats are always acceptable

            expected_seq = self.last_recvd_sequence + 1 if self.last_recvd_sequence > 0 else 1

            if client_seq > expected_seq:
                within_tolerance = client_seq <= expected_seq + 9
                return (True, within_tolerance)

            return (False, True)

    # ==========================================
    # Inventory Methods (TF2-era item system)
    # ==========================================
    def get_inventory_items(self, app_id: int):
        """Get all persistent inventory items for this user in the specified app."""
        if not self.steamID:
            return []
        return database.get_persistent_items_by_steamid_appid(self.steamID, app_id)

    def get_inventory_item(self, item_id: int):
        """Get a specific inventory item by its unique item ID."""
        return database.get_persistent_item_by_id(item_id)

    def update_inventory_position(self, item_id: int, app_id: int, new_position: int):
        """Update the inventory position of an item owned by this user."""
        from steam3.Types.steam_types import EResult
        if not self.steamID:
            return EResult.Fail
        return database.update_persistent_item_position(item_id, self.steamID, app_id, new_position)

    def drop_inventory_item(self, item_id: int, app_id: int):
        """Delete/drop an inventory item owned by this user."""
        from steam3.Types.steam_types import EResult
        if not self.steamID:
            return EResult.Fail
        return database.delete_persistent_item(item_id, self.steamID, app_id)

    def add_inventory_item(self, app_id: int, definition_index: int, item_level: int,
                          quality: int, inventory_token: int, quantity: int = 1,
                          attributes: list = None):
        """Add a new inventory item for this user."""
        if not self.steamID:
            return None
        item_id = database.get_next_item_id(app_id)
        return database.add_persistent_item(
            steam_id=self.steamID,
            app_id=app_id,
            item_id=item_id,
            definition_index=definition_index,
            item_level=item_level,
            quality=quality,
            inventory_token=inventory_token,
            quantity=quantity,
            attributes=attributes
        )
