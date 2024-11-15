import random
import threading
import time

from utilities.master_packethandler import PacketHandler


class Server:
    def __init__(self, address, isoldserver, islan, _time, uniqueid, isproxy, isProxyTarget, proxyTarget,
                 players, maxplayers, bots, gamedir, sv_map, os, password, dedicated, secure, info, info_length):
        self.time = int(0)
        self.address = address
        self.isoldserver = isoldserver
        self.islan = islan
        self.time = time.time()
        self.uniqueid = uniqueid
        self.isproxy = isproxy
        self.isProxyTarget = isProxyTarget
        self.proxyTarget = proxyTarget
        self.players = players
        self.max = maxplayers
        self.bots = bots
        self.gamedir = gamedir
        self.map = sv_map
        self.os = os
        self.password = password
        self.dedicated = dedicated
        self.secure = secure
        self.info = info
        self.info_length = info_length


class MasterServerManager:
    def __init__(self):
        self.last_unique_id = None
        self.servers = []
        self.indexes = {
            'address': {},
            # 'isoldserver': {},
            'islan': {},
            # 'time': {},
            'isproxy': {},
            'isProxyTarget': {},
            # 'proxyTarget': {},
            'players': {},
            'max': {},
            'gamedir': {},
            'map': {},
            'os': {},
            'password': {},
            'dedicated': {},
            'secure': {}
        }
        self.lock = threading.Lock()
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_servers).start()

    def _cleanup_old_servers(self):
        while True:
            time.sleep(60)  # Check every minute
            current_time = int(time.time())
            with self.lock:
                self.servers = [server for server in self.servers if current_time - server.time <= 15 * 60]
                # Rebuild indexes
                for key in self.indexes.keys():
                    self.indexes[key].clear()
                    for server in self.servers:
                        self._add_to_index(key, server)

    def _add_to_index(self, key, server):
        if server.__dict__[key] not in self.indexes[key]:
            self.indexes[key][server.__dict__[key]] = []
        self.indexes[key][server.__dict__[key]].append(server)

    def add_server(self, server):
        self.servers.append(server)
        for key in self.indexes.keys():
            self._add_to_index(key, server)

    def remove_server_by_address(self, address):
        servers_to_remove = self.get_servers_by_attribute('address', address)
        with self.lock:
            self.servers = [server for server in self.servers if server not in servers_to_remove]
        for key in self.indexes.keys():
            self.indexes[key].clear()
            for server in self.servers:
                self._add_to_index(key, server)

    def get_servers_by_attribute(self, attribute, value):
        return self.indexes.get(attribute, {}).get(value, [])

    def get_all_servers(self):
        return self.servers

    def print_all_servers(self):
        for server in self.get_all_servers():
            print(f"Address: {server.address}, IsOldServer: {server.isoldserver}, "
                  f"IsLAN: {server.islan}, Time: {server.time}, UniqueID: {server.uniqueid}, "
                  f"IsProxy: {server.isproxy}, IsProxyTarget: {server.isProxyTarget}, "
                  f"ProxyTarget: {server.proxyTarget}, Players: {server.players}, "
                  f"MaxPlayers: {server.max}, Bots: {server.bots}, GameDir: {server.gamedir}, "
                  f"Map: {server.map}, OS: {server.os}, Password: {server.password}, "
                  f"Dedicated: {server.dedicated}, Secure: {server.secure}, "
                  f"Info: {server.info}, InfoLength: {server.info_length}")

    def generate_unique_id(self):
        self.last_unique_id += 1  # Increment the counter to get the next unique ID
        return self.last_unique_id

    def parse_criteria_from_info(self, info):
        criteria = {}
        # packet_handler = PacketHandler(info.encode())  # Assuming info is a string

        # Extract key-value pairs for criteria
        criteria_keys = ['map', 'gamedir', 'dedicated', 'secure', 'full', 'empty', 'linux', 'proxy', 'proxytarget']
        for key in criteria_keys:
            value = PacketHandler.info_value_for_key(info, key)
            if value:
                # Convert values to appropriate types if necessary
                if key in ['dedicated', 'secure', 'full', 'empty', 'proxy']:
                    criteria[key] = value == '1'  # Convert to boolean
                else:
                    criteria[key] = value

        return criteria

    def parse_criteria_from_info_client(self, info):
        criteria = {}
        criteria_keys = {
            'map': 'string',
            'gamedir': 'string',
            'dedicated': 'boolean',
            'secure': 'boolean',
            'full': 'boolean',
            'empty': 'boolean',
            'linux': 'boolean',
            'proxy': 'boolean',
            'proxytarget': 'string'  # Assuming 'proxytarget' is a string
        }

        for key, value_type in criteria_keys.items():
            value = PacketHandler.info_value_for_key(info, key)
            if value:
                if value_type == 'boolean':
                    criteria[key] = value == '1'
                elif value_type == 'integer':
                    criteria[key] = int(value)
                else:  # 'string' or any other types
                    criteria[key] = value
        # print(criteria['proxy'])
        return criteria

    def is_server_in_list(self, address):
        """
        Check if a server with the given IP address and port is in the list and return it.

        :param address: The IP address and port tuple to check (e.g., ('192.168.1.1', 27015)).
        :return: The server object if found, None otherwise.
        """
        with self.lock:
            for server in self.servers:
                if server.address == address:
                    return server
            return None

    def server_passes_criteria(self, server, criteria):
        if not criteria:
            return True

        if 'gamedir' in criteria and criteria['gamedir'] and server.gamedir != criteria['gamedir']:
            return False

        if 'map' in criteria and criteria['map'] and server.map != criteria['map']:
            return False

        if 'dedicated' in criteria and criteria['dedicated'] and not server.dedicated:
            return False

        if 'secure' in criteria and criteria['secure'] and not server.secure:
            return False

        if 'linux' in criteria and criteria['linux'] and server.os.lower() != 'linux':
            return False

        if 'empty' in criteria and criteria['empty'] and server.players == 0:
            return False

        if 'full' in criteria and criteria['full'] and server.players >= server.max:
            return False

        if 'proxy' in criteria and server.isproxy != criteria['proxy']:
            return False

        if 'proxytarget' in criteria and criteria['proxytarget'] and server.proxyTarget != criteria['proxytarget']:
            return False

        return True


class Challenge:
    def __init__(self, address, challenge, time):
        self.address = address
        self.challenge = challenge
        self.time = time


class ChallengeManager:
    def __init__(self):
        self.challenges = []
        self.lock = threading.Lock()
        self.cleanup_thread = threading.Thread(target = self._cleanup_old_challenges).start()

    def check_challenge(self, address):
        with self.lock:
            current_time = int(time.time())
            for challenge in self.challenges:
                if challenge.address == address and current_time - challenge.time <= 15 * 60:
                    return challenge.challenge
            return None

    def validate_challenge(self, address, challenge_value):
        challenge = self.check_challenge(address)
        return challenge is not None and challenge == challenge_value

    def create_challenge(self, address):
        with self.lock:
            current_time = int(time.time())
            new_challenge_value = (random.randint(0, 0xFFFF) << 16 | random.randint(0, 0xFFFF)) & ~(1 << 31)
            new_challenge = Challenge(address, new_challenge_value, current_time)
            self.challenges.append(new_challenge)
            return new_challenge_value

    def _cleanup_old_challenges(self):
        while True:
            time.sleep(180)  # Cleanup every 180 seconds
            current_time = int(time.time())
            with self.lock:
                self.challenges = [c for c in self.challenges if current_time - c.time <= 15 * 60]


challenge_manager = ChallengeManager()
server_manager = MasterServerManager()

"""def server_passes_criteria(self, server, criteria):
if not criteria:
    return True

if 'gamedir' in criteria and criteria['gamedir'] and server.gamedir != criteria['gamedir']:
    return False

if 'map' in criteria and criteria['map'] and server.map != criteria['map']:
    return False

if 'dedicated' in criteria and criteria['dedicated'] and not server.dedicated:
    return False

if 'secure' in criteria and criteria['secure'] and not server.secure:
    return False

if 'linux' in criteria and criteria['linux'] and server.os.lower() != 'linux':
    return False

if 'empty' in criteria and criteria['empty'] and server.players == 0:
    return False

if 'full' in criteria and criteria['full'] and server.players >= server.max:
    return False

if 'proxy' in criteria and server.isproxy != criteria['proxy']:
    return False

if 'proxytarget' in criteria and criteria['proxytarget'] and server.proxyTarget != criteria['proxytarget']:
    return False

return True"""