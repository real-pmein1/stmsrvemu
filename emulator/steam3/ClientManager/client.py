import struct
import time
from datetime import datetime

from copy import copy, deepcopy

import globalvars
from steam3 import database
from steam3.Responses.friends_responses import send_statuschange_to_friends
from steam3.Types.community_types import ChatEntryType, FriendRelationship, PlayerState
from steam3.cm_packet_utils import ChatMessage
from steam3.utilities import get_packed_datetime
from utilities.database.base_dbdriver import FriendsRegistry


class Client:
    def __init__(self, ip_port: tuple = None,  symmetric_key = None, connectionid = None, steamid = None,  client_state = PlayerState.online,
            account_type = None, username = None, chatroom = None, email = '', ratelimit: int = 0, sequencenumber: int = 0, lastrecieved_seq: int = 0, serverconnectionid = 0):
        self.connectionid = connectionid
        self.serverconnectionid = serverconnectionid
        self.sessionID = 0
        self.symmetric_key = symmetric_key
        self.hmac_key = b''
        self.steamID = steamid
        self.clientID2 = None
        self.ip_port = ip_port
        self.client_state = client_state
        self.account_type = account_type
        self.username = username
        self.chatroom = chatroom
        self.email = email
        self.ratelimit = ratelimit
        self.sequence_number = sequencenumber
        self.last_recvd_sequence = lastrecieved_seq
        self.publicIP = None
        self.privateIP = None
        self.is_in_app = False
        self.is_machineID_set = False
        self.appID = 0
        self.app_ip_port = (0, 0xFFFF)
        self.avatarID = b'fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb'  # Default ? avatar
        self.session_token = None
        self.onetimepass = None
        self.is_newPacketType = False
        self.last_recvd_heartbeat = None
        self.protocol_version = 0
        self.friends_list = []
        self.friends_relationships = []
        self.groups_list = []
        self.jobID_list =[]

        self.update_status_callback = None
        self.process_heartbeat_callback = None
        self.remove_client_callback = None
        self.send_message_callback = None
        self.client_manager_callback = None

    def login_User(self, cmserver_obj, machineIDs = None):
        """Finds or creates a friendsregistry entry for the user, sets all clients variables from database
        and returns any vacbans as a list of the class VacBans from the database or None if there are no bans"""
        # First check if the userid has an associated entry in FriendsRegistry, if not we create it
        userdb_entry, isnew = database.get_or_create_registry_entry(self.steamID)

        result = database.set_last_login(self.steamID)

        self.username = deepcopy(userdb_entry.nickname)

        self.write_keys_to_file() # This is for figuring out missing packets
        # FIXME This is a hack to set any pending requests to 'friends'/3 due to not knowing how to trigger the request dialog in later steam clients
        if self.protocol_version:
            if self.protocol_version > 65550:
                # we set all friend invite relationships to 3, same for the inverse (requesting friend)
                database.fix_invites(self.steamID)

        if machineIDs:
            overwrite = True if globalvars.config['overwrite_machineids'].lower() == 'true' else False
            self.is_machineID_set = database.check_and_update_machine_ids(self.steamID, machineIDs[0], machineIDs[1], machineIDs[2], overwrite)
            # TODO do something with the machineID results.. maybe validate them to ensure the correct machine is logging in?
            #  perhaps keep a database table which contains all machine id's a user has attempted to log in with and add a column
            #  that will determine whether the machine is valid or not for logging in

        self.get_friends_list_from_db()
        self.update_status_info(cmserver_obj, PlayerState.online)
        self.get_joined_groups_list()
        # self.get_friends_relationships_from_db()  # Not needed, already called in get_friends_list_from_db()
        self.get_avatarID()
        if result:
            return self.get_vacbans()

        #print(f"Setting last login date/time failed, could not find user by userid: {cmserver_obj.steamID}")
        return False

    def write_keys_to_file(self):
        try:
            file_path = f"logs/{self.username}_symmetric_key.txt"
            with open(file_path, 'a') as file:
                file.write(f'{datetime.now().strftime("%m/%d/%Y %H:%M:%S")}:\t\t'
                           f'symmetric key: {self.symmetric_key}\n'
                           f'hmac: {self.hmac_key}\n')
            print(f"Keys written to {file_path}")
        except Exception as e:
            print(f"An error occurred while writing to the file: {e}")

    def logoff_User(self, cmserver_obj):
        """Sets all instance information to 0
        Updates the database entries to 'offline'"""
        self.update_status_info(cmserver_obj, PlayerState.offline, appID = 0, ipaddr = 0, port = 0xffff, gameserver_id = 0)
        database.set_last_logoff(self.steamID)
        self.remove_client_callback(self)

    def disconnect_Game(self, cmserver_obj):
        self.exit_app(cmserver_obj)

    def set_onetime_pass(self, otp):
        return database.set_onetime_pass(self.steamID, otp)

    def update_server_info(self, appID, ipaddr, port, gameserver_id):
        self.appID = appID
        self.app_ip_port = (ipaddr, port)
        self.is_in_app = True
        database.add_play_history(self.steamID, appID = appID, server_ip = ipaddr, server_port = port, serverID = gameserver_id)

    def update_status_info(self, cmserver_obj, new_status: PlayerState, appID = 0, ipaddr = 0, port = 0xffff, gameserver_id = 0, username = None, isloggedoff = False):
        """Sets the client instance state and DB entry to the new state
         If appID or ipaddr and port are present, it also updates the DB and instance ip_port information
         this will also update the played history database table"""

        if username:
            username = self.check_username(username)  # This checks if the nickname is different from the one in the DB and updates it, if it is

        if ipaddr != 0 and port != 0 or appID != 0:
            self.update_server_info(appID, ipaddr, port, gameserver_id)

        if self.client_state != new_status:
            self.client_state = new_status
            #if self.update_status_callback: # Should never be False/None
            #    self.update_status_callback(self.steamID, new_status, self.username, appID, ipaddr, port, username)
            self.client_state = int(new_status.value)
            database.set_user_state(self.steamID, new_status)
        send_statuschange_to_friends(self, cmserver_obj, self.client_manager_callback, int(new_status))
        return self.client_state

    def exit_app(self, cmserver_obj, isloggedoff = False):
        """Sets the client instance app_ip_port to 0 indicating they are not playing a game
        updates the client state to online
        sets last played datetime in database lastplayed history table"""
        database.exiting_app(self.steamID)
        self.update_status_info(cmserver_obj, PlayerState.online, appID = 0, ipaddr = 0, port = 0xffff, gameserver_id = 0, isloggedoff = isloggedoff)
        self.appID = 0
        self.is_in_app = False
        self.app_ip_port = (0, 0xffff)
        send_statuschange_to_friends(self, cmserver_obj, self.client_manager_callback, int(PlayerState.online))

    def get_vacbans(self):
        return database.get_vacban_by_userid(self.steamID)

    def get_friends_list_from_db(self):
        """Grabs the list of friends entries from the database
        Sets the friends_list to those entries
        returns the friend list"""
        # self.get_friends_relationships_from_db()
        returned_friends_list = database.get_user_friendslist_registry_entries(self.steamID)
        # print(f"Returned friends list size: {len(returned_friends_list)}")  # Debug print to check the size of the returned list
        self.friends_list = deepcopy(returned_friends_list)
        return self.friends_list

    def get_avatarID(self):
        self.avatarID = deepcopy(database.get_user_avatar(self.steamID))

    def get_friend_avatarID(self, steamID):
        avatarid = deepcopy(database.get_user_avatar(steamID))
        return avatarid

    def get_friend_lastseen(self, steamID):
        friendregistry_entry = deepcopy(database.get_user_details(steamID))
        last_login = get_packed_datetime(friendregistry_entry.last_login if friendregistry_entry.last_login is not None else datetime.now())
        last_logoff = get_packed_datetime(friendregistry_entry.last_logoff if friendregistry_entry.last_logoff is not None else datetime.now())
        return last_login, last_logoff

    def get_friends_nickname(self, accountID):
        """Directly fetches a friend's entry from the database by accountID."""
        # self.get_friends_relationships_from_db()
        nickname = database.get_user_nickname(accountID)
        return nickname

    def get_joined_groups_list(self):
        returned_groups_list = database.get_user_groups(self.steamID)
        for group in returned_groups_list:
            self.groups_list.append(deepcopy(group))
        return self.groups_list

    def add_friend(self, friendID, relationship = FriendRelationship.requestInitiator):
        """Adds friend to client's database friendlist, updates instance friend_list"""
        # we set all friend invite relationships to 3, same for the inverse (requesting friend)
        if self.protocol_version > 65550:
            relationship = 3

        result = database.add_friend(self.steamID, friendID, relationship)  # FIXME check add_friend in cmdb.py for info

        # We grab a 'fresh' friendslist from the database to make sure our in-memory list isnt stale
        self.get_friends_list_from_db()
        return result

    def remove_friends(self, friendID):
        """Removes friend by steamID and updates the client instances friends_list from the database"""
        database.remove_friend(self.steamID, friendID)
        # We grab a 'fresh' friendslist from the database to make sure our in-memory list isnt stale
        self.get_friends_list_from_db()

    def block_friend(self, friendID, toBlock):
        if toBlock == 1:
            result = database.manage_friendship(self.steamID, friendID, "block")
        else:
            result = database.manage_friendship(self.steamID, friendID, "unblock")

        return result

    def renew_heartbeat(self):
        # TODO use this to detect disconnected users, and remove them from the manager list
        self.last_recvd_heartbeat = datetime.now()

    def find_friend_by_account_id(self, account_id) -> FriendsRegistry:
        """Uses next() to find the first matching friend by steamID, or return None if no match is found"""
        return next((friend for friend in self.friends_list if friend.accountID == account_id), None)

    def find_relationship_by_friendsaccount_id(self, friendsaccount_id):
        """Find specific relationship from friends_relationships"""
        return next((relation for relation in self.friends_relationships if relation.friendsaccountID == friendsaccount_id), None)

    def check_username(self, username: str):
        """Checks the username against the username in the database
         if they differ, it sets the databaase username entry to the new username
         then it returns the new/current username"""
        self.username = database.get_or_set_nickname(self.steamID, username)
        return self.username

    def add_to_chat_history(self, msg_obj: ChatMessage, acked = 0):
        """Adds a new chat message to the user-to-user chat history table"""
        if ChatEntryType(msg_obj.type) == ChatEntryType.chatMsg:
            database.add_chat_history_entry(self.steamID, msg_obj.to, msg_obj.message, acked)

    def get_chat_history(self, to_accountID):
        """returns the chat history between two friends (returned as a list of FriendsChatHistory class"""
        return database.retrieve_chat_history(self.steamID, to_accountID)

    def get_heartbeat_updates(self):
        """Gets called during every heartbeat from the client
        This grabs all of the user's friends who updated their status since the last heartbeat
        and any messages clients sent to this user"""
        # TODO get rid of this, send status and messages immedietly when recieved to the intended receipient
        if self.process_heartbeat_callback:
            return self.process_heartbeat_callback(self.steamID)
        else:
            print("[CM Client] Error! cannot retrieve pending messages or status changes!")
            return None  # This means that the heartbeat callback variable wasnt set... should be impossible

    def send_message(self, cm_object, msg_obj: ChatMessage):
        """Adds the message to the chat history table
        also puts the message into the pending messages for the receipient userid"""
        self.add_to_chat_history(msg_obj)
        self.send_message_callback(cm_object, msg_obj)

    def append_jobinfo(self, EMsgID, targetjobID, sourcejobID, canary):
        self.jobID_list.append((copy(EMsgID), copy(targetjobID), copy(sourcejobID), copy(canary)))

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
        combined_friends = {friend.accountID: friend for friend in self.friends_list}
        for relationship in self.friends_relationships:
            if relationship.friendsaccountID in combined_friends:
                combined_friends[relationship.friendsaccountID].relationship = relationship.relationship_type
            else:
                combined_friends[relationship.friendsaccountID] = relationship

        # Add friends info
        details.append("Friends:")
        for friend in combined_friends.values():
            details.append(f"  {friend}")

        # Add groups info
        details.append("Groups:")
        for group in self.groups_list:
            details.append(f"  {group}")

        return "\n".join(details)

    def grab_potential_gift_targets(self, packageID):
        friends_steamid_list = []
        if self.friends_list:
            flist = self.get_friends_list_from_db()
            for friend_entry, _ in flist:
                # Access friendsaccountID attribute from the FriendsList object
                friends_steamid_list.append(int(friend_entry.accountID))
        return database.get_non_subscribed_friends(friends_steamid_list, packageID)

    def set_DBappTicket(self, appID, Ticket):
        return database.check_and_update_ownership_ticket(self.steamID, appID, Ticket)

    def get_addressEntryID(self, name, address1, address2, city, postcode, state, country_code, phone):
        return database.get_or_add_transaction_address(self.steamID, name, address1, address2, city, postcode, state, country_code, phone)

    def get_all_paymentcards(self):
        return database.get_cc_records_by_account(self.steamID)

    def get_or_set_paymentcardinfo(self, card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2, addressEntryID):
        return database.get_or_add_cc_record(self.steamID, card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2, addressEntryID)

    def add_gift_transactioninfo(self, sub_id, giftee_email, giftee_account_id, gift_message, giftee_name, sentiment, signature):
        return database.add_gift_transaction(self.steamID, sub_id, giftee_email, giftee_account_id, gift_message, giftee_name, sentiment, signature)

    def add_external_transactioninfo(self, packageID, transaction_type, transaction_data):
        return database.add_external_purchase_info(self.steamID, packageID, transaction_type, transaction_data)

    def add_new_steam3_transaction(self, transaction_type, transaction_entry_id, package_id, gift_unique_id, address_entry_id, base_cost, discounts, tax_cost, shipping_cost, shipping_entry_id, guest_passes_included):
        return database.add_steam3_transaction_record(self.steamID, transaction_type, transaction_entry_id, package_id, gift_unique_id, address_entry_id, base_cost, discounts, tax_cost, shipping_cost, shipping_entry_id, guest_passes_included)

    def cancel_transaction(self, transactionID):
        return database.update_steam3_transaction_cancelled(self.steamID, transactionID)

    def get_transaction(self, transactionID):
        return database.get_transaction_entry_details(self.steamID, transactionID)

    def set_receipt_acknowledged(self, transactionID):
        return database.set_transaction_receipt_acknowledged(self.steamID, transactionID)

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
        return clan_members[0].CommunityClanID, member[0].user_rank

    def get_email_info(self):
         return database.get_user_email_and_verification_status(self.steamID)

    def get_accountflags(self):
        return database.compute_accountflags(self.steamID)