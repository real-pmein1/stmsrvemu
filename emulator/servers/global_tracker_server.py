"""
Global Tracker Server for Steam Emulator Cross-Network Communication

This server enables multiple tracker server networks to interconnect,
allowing users from different networks to search, friend, and chat with each other.

Protocol: TCP with newline-delimited JSON messages
Architecture: Hub-and-spoke with centralized friendship registry
"""

import asyncio
import json
import logging
import os
import secrets
import threading
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class NetworkInfo:
    network_id: str
    name: str
    block: int
    capabilities: List[str]
    last_heartbeat: float
    connection: Optional[asyncio.StreamWriter] = None


@dataclass
class GlobalUser:
    global_id: int
    username: str
    network: str
    local_id: int
    status: int
    last_seen: float
    game_data: Optional[Dict] = None
    email: str = ""
    firstname: str = ""
    lastname: str = ""


class GlobalFriendshipManager:
    """Manages cross-network friendship relationships"""

    def __init__(self):
        self.friendships: Dict[int, Set[int]] = {}
        self.pending_requests: Dict[int, Set[int]] = {}

    def add_friendship(self, user1_global_id: int, user2_global_id: int) -> bool:
        """Add bidirectional friendship"""
        if user1_global_id == user2_global_id:
            return False

        self.friendships.setdefault(user1_global_id, set()).add(user2_global_id)
        self.friendships.setdefault(user2_global_id, set()).add(user1_global_id)

        # Remove any pending requests
        self.remove_pending_request(user1_global_id, user2_global_id)
        self.remove_pending_request(user2_global_id, user1_global_id)

        return True

    def remove_friendship(self, user1_global_id: int, user2_global_id: int) -> bool:
        """Remove bidirectional friendship"""
        removed = False

        if user1_global_id in self.friendships:
            self.friendships[user1_global_id].discard(user2_global_id)
            removed = True

        if user2_global_id in self.friendships:
            self.friendships[user2_global_id].discard(user1_global_id)
            removed = True

        return removed

    def get_friends(self, global_id: int) -> Set[int]:
        """Get all friends of a user"""
        return self.friendships.get(global_id, set())

    def are_friends(self, user1_global_id: int, user2_global_id: int) -> bool:
        """Check if two users are friends"""
        return user2_global_id in self.friendships.get(user1_global_id, set())

    def add_pending_request(self, from_global_id: int, to_global_id: int) -> bool:
        """Add pending friend request"""
        if self.are_friends(from_global_id, to_global_id):
            return False

        self.pending_requests.setdefault(to_global_id, set()).add(from_global_id)
        return True

    def remove_pending_request(self, from_global_id: int, to_global_id: int) -> bool:
        """Remove pending friend request"""
        if to_global_id in self.pending_requests:
            return from_global_id in self.pending_requests[to_global_id] and \
                   self.pending_requests[to_global_id].discard(from_global_id) is None
        return False

    def get_pending_requests(self, global_id: int) -> Set[int]:
        """Get all pending friend requests for a user"""
        return self.pending_requests.get(global_id, set())


class StatusNotificationEngine:
    """Handles cross-network status notifications"""

    def __init__(self, friendship_manager: GlobalFriendshipManager, network_manager):
        self.friendship_manager = friendship_manager
        self.network_manager = network_manager
        self.online_users: Dict[int, GlobalUser] = {}

    async def handle_user_login(self, global_id: int, user: GlobalUser):
        """Handle user login and notify friends"""
        self.online_users[global_id] = user
        await self._notify_friends_status_change(global_id, user.status, user.game_data)

    async def handle_user_logout(self, global_id: int):
        """Handle user logout and notify friends"""
        if global_id in self.online_users:
            await self._notify_friends_status_change(global_id, 0)  # Status 0 = offline
            del self.online_users[global_id]

    async def handle_status_change(self, global_id: int, status: int, game_data: Optional[Dict] = None):
        """Handle status change and notify friends"""
        if global_id in self.online_users:
            self.online_users[global_id].status = status
            self.online_users[global_id].game_data = game_data
            self.online_users[global_id].last_seen = time.time()

        await self._notify_friends_status_change(global_id, status, game_data)

    async def _notify_friends_status_change(self, global_id: int, status: int, game_data: Optional[Dict] = None):
        """Notify all online friends of a status change"""
        friends = self.friendship_manager.get_friends(global_id)

        for friend_global_id in friends:
            if friend_global_id in self.online_users:
                target_network_id = self.network_manager.get_network_id_by_global_id(friend_global_id)
                if target_network_id:
                    await self.network_manager.send_to_network(target_network_id, {
                        "type": "friend_status_update",
                        "target_global_id": friend_global_id,
                        "friend_global_id": global_id,
                        "status": status,
                        "game_data": game_data
                    })


class NetworkManager:
    """Manages network connections and routing"""

    def __init__(self, stats: Optional['PacketStats'] = None):
        self.networks: Dict[str, NetworkInfo] = {}
        self.block_to_network_id: Dict[int, str] = {}
        self.next_block = 10000
        self.log = logging.getLogger("NetworkManager")
        self.stats = stats

    def set_stats(self, stats: 'PacketStats'):
        """Set the packet statistics tracker"""
        self.stats = stats

    def register_network(self, network_id: str, name: str, capabilities: List[str],
                        connection: asyncio.StreamWriter) -> int:
        """Register a new network and assign block"""
        if network_id in self.networks:
            # Existing network reconnecting
            network = self.networks[network_id]
            network.connection = connection
            network.last_heartbeat = time.time()
            network.capabilities = capabilities
            block = network.block
        else:
            # New network
            block = self.next_block
            self.next_block += 10000

            network = NetworkInfo(
                network_id=network_id,
                name=name,
                block=block,
                capabilities=capabilities,
                last_heartbeat=time.time(),
                connection=connection
            )

            self.networks[network_id] = network
            self.block_to_network_id[block] = network_id

        self.log.info(f"Registered network '{name}' (ID: {network_id}) with block {block}")
        return block

    def unregister_network(self, network_id: str):
        """Unregister a network connection"""
        if network_id in self.networks:
            network = self.networks[network_id]
            network.connection = None
            self.log.info(f"Unregistered network '{network.name}' (ID: {network_id})")

    def get_network_id_by_global_id(self, global_id: int) -> Optional[str]:
        """Get network ID from global ID"""
        block = (global_id // 10000) * 10000
        return self.block_to_network_id.get(block)

    def get_network_by_id(self, network_id: str) -> Optional[NetworkInfo]:
        """Get network info by ID"""
        return self.networks.get(network_id)

    async def send_to_network(self, network_id: str, message: Dict, target_user_id: Optional[int] = None) -> bool:
        """Send message to specific network"""
        network = self.networks.get(network_id)
        if network and network.connection:
            try:
                data = json.dumps(message) + "\n"
                network.connection.write(data.encode())
                await network.connection.drain()

                # Log outgoing message
                self.log.info(f"--> Sent to {network_id}: type={message.get('type', 'unknown')}")

                # Track sent packet
                if self.stats:
                    # Try to extract target user ID from message if not provided
                    user_id = target_user_id or message.get("target_global_id") or message.get("to_global_id")
                    self.stats.record_sent(network_id, user_id)

                return True
            except Exception as e:
                self.log.error(f"Failed to send to network {network_id}: {e}")
                network.connection = None
        else:
            self.log.warning(f"Cannot send to network {network_id} - not connected")
        return False

    def is_network_online(self, network_id: str) -> bool:
        """Check if network is currently connected"""
        network = self.networks.get(network_id)
        return network is not None and network.connection is not None

    def get_all_networks(self) -> List[NetworkInfo]:
        """Get all registered networks"""
        return list(self.networks.values())


class MessageRouter:
    """Routes messages between networks"""

    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
        self.log = logging.getLogger("MessageRouter")

    async def forward_message(self, from_global_id: int, to_global_id: int,
                             message_type: str, payload: Any) -> bool:
        """Forward message between networks"""
        target_network_id = self.network_manager.get_network_id_by_global_id(to_global_id)
        if not target_network_id:
            self.log.warning(f"No network found for global ID {to_global_id}")
            return False

        message = {
            "type": "deliver_message",
            "from_global_id": from_global_id,
            "to_global_id": to_global_id,
            "message_type": message_type,
            "payload": payload
        }

        success = await self.network_manager.send_to_network(target_network_id, message)
        if success:
            self.log.info(f"Forwarded {message_type} message from {from_global_id} to {to_global_id}")

        return success


class PacketStats:
    """Tracks packet statistics per user and globally"""

    def __init__(self):
        self.total_packets_received = 0
        self.total_packets_sent = 0
        self.packets_by_type: Dict[str, int] = {}
        self.packets_by_network: Dict[str, Dict[str, int]] = {}  # network_id -> {received, sent}
        self.packets_by_user: Dict[int, Dict[str, int]] = {}  # global_id -> {received, sent}
        self.start_time = time.time()

    def record_received(self, msg_type: str, network_id: str, user_global_id: Optional[int] = None):
        """Record a received packet"""
        self.total_packets_received += 1
        self.packets_by_type[msg_type] = self.packets_by_type.get(msg_type, 0) + 1

        # Track by network
        if network_id not in self.packets_by_network:
            self.packets_by_network[network_id] = {"received": 0, "sent": 0}
        self.packets_by_network[network_id]["received"] += 1

        # Track by user if provided
        if user_global_id is not None:
            if user_global_id not in self.packets_by_user:
                self.packets_by_user[user_global_id] = {"received": 0, "sent": 0}
            self.packets_by_user[user_global_id]["received"] += 1

    def record_sent(self, network_id: str, user_global_id: Optional[int] = None):
        """Record a sent packet"""
        self.total_packets_sent += 1

        # Track by network
        if network_id not in self.packets_by_network:
            self.packets_by_network[network_id] = {"received": 0, "sent": 0}
        self.packets_by_network[network_id]["sent"] += 1

        # Track by user if provided
        if user_global_id is not None:
            if user_global_id not in self.packets_by_user:
                self.packets_by_user[user_global_id] = {"received": 0, "sent": 0}
            self.packets_by_user[user_global_id]["sent"] += 1

    def get_uptime(self) -> str:
        """Get formatted uptime string"""
        elapsed = int(time.time() - self.start_time)
        days, remainder = divmod(elapsed, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of packet statistics"""
        return {
            "uptime": self.get_uptime(),
            "total_received": self.total_packets_received,
            "total_sent": self.total_packets_sent,
            "packets_by_type": dict(self.packets_by_type),
            "networks_active": len(self.packets_by_network),
            "users_tracked": len(self.packets_by_user)
        }


class GlobalTracker:
    """Main Global Tracker Server"""

    def __init__(self, port: int, state_file: str = "global_tracker_state.json"):
        self.port = port
        self.state_file = state_file
        self.log = logging.getLogger("GlobalTracker")

        # Packet statistics (create first so other components can use it)
        self.stats = PacketStats()

        # Core components
        self.network_manager = NetworkManager(self.stats)
        self.friendship_manager = GlobalFriendshipManager()
        self.status_engine = StatusNotificationEngine(self.friendship_manager, self.network_manager)
        self.message_router = MessageRouter(self.network_manager)

        # User registry
        self.users: Dict[int, GlobalUser] = {}

        # Server state
        self._server: Optional[asyncio.AbstractServer] = None
        self.request_counter = 0

        # Load persistent state
        self._load_state()

        # Start periodic tasks
        asyncio.create_task(self._periodic_heartbeat_check())
        asyncio.create_task(self._periodic_stats_display())

    def _load_state(self):
        """Load persistent state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Restore networks
                for net_id, net_data in data.get("networks", {}).items():
                    network = NetworkInfo(
                        network_id=net_id,
                        name=net_data["name"],
                        block=net_data["block"],
                        capabilities=net_data.get("capabilities", []),
                        last_heartbeat=0
                    )
                    self.network_manager.networks[net_id] = network
                    self.network_manager.block_to_network_id[network.block] = net_id

                    if network.block >= self.network_manager.next_block:
                        self.network_manager.next_block = network.block + 10000

                # Restore friendships
                for user_id_str, friend_ids in data.get("friendships", {}).items():
                    user_id = int(user_id_str)
                    self.friendship_manager.friendships[user_id] = set(friend_ids)

                # Restore users
                for user_id_str, user_data in data.get("users", {}).items():
                    user_id = int(user_id_str)
                    user = GlobalUser(
                        global_id=user_id,
                        username=user_data["username"],
                        network=user_data["network"],
                        local_id=user_data["local_id"],
                        status=0,  # Default to offline
                        last_seen=user_data.get("last_seen", 0),
                        game_data=user_data.get("game_data"),
                        email=user_data.get("email", ""),
                        firstname=user_data.get("firstname", ""),
                        lastname=user_data.get("lastname", "")
                    )
                    self.users[user_id] = user

                self.log.info(f"Loaded state: {len(self.network_manager.networks)} networks, {len(self.users)} users")

            except Exception as e:
                self.log.error(f"Failed to load state: {e}")

    def _save_state(self):
        """Save persistent state to file"""
        try:
            data = {
                "networks": {
                    net_id: {
                        "name": net.name,
                        "block": net.block,
                        "capabilities": net.capabilities
                    }
                    for net_id, net in self.network_manager.networks.items()
                },
                "friendships": {
                    str(user_id): list(friends)
                    for user_id, friends in self.friendship_manager.friendships.items()
                },
                "users": {
                    str(user_id): {
                        "username": user.username,
                        "network": user.network,
                        "local_id": user.local_id,
                        "last_seen": user.last_seen,
                        "game_data": user.game_data,
                        "email": user.email,
                        "firstname": user.firstname,
                        "lastname": user.lastname
                    }
                    for user_id, user in self.users.items()
                }
            }

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.log.error(f"Failed to save state: {e}")

    async def _periodic_heartbeat_check(self):
        """Periodically check for stale network connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                current_time = time.time()
                stale_networks = []

                for net_id, network in self.network_manager.networks.items():
                    if network.connection and (current_time - network.last_heartbeat > 120):
                        stale_networks.append(net_id)

                for net_id in stale_networks:
                    self.log.warning(f"Network {net_id} appears stale, disconnecting")
                    self.network_manager.unregister_network(net_id)

            except Exception as e:
                self.log.error(f"Error in heartbeat check: {e}")

    async def _periodic_stats_display(self):
        """Periodically display server statistics"""
        while True:
            try:
                await asyncio.sleep(300)  # Display every 5 minutes
                self._display_stats()
            except Exception as e:
                self.log.error(f"Error in stats display: {e}")

    def _display_stats(self):
        """Display current server statistics"""
        stats = self.stats.get_summary()
        online_networks = sum(1 for n in self.network_manager.networks.values() if n.connection)
        online_users = len(self.status_engine.online_users)

        self.log.info("=" * 60)
        self.log.info("SERVER STATISTICS")
        self.log.info("-" * 60)
        self.log.info(f"  Uptime: {stats['uptime']}")
        self.log.info(f"  Networks: {online_networks} online / {len(self.network_manager.networks)} registered")
        self.log.info(f"  Users: {online_users} online / {len(self.users)} registered")
        self.log.info(f"  Packets: {stats['total_received']} received / {stats['total_sent']} sent")

        if stats['packets_by_type']:
            self.log.info("  Packet Types:")
            for msg_type, count in sorted(stats['packets_by_type'].items(), key=lambda x: -x[1])[:10]:
                self.log.info(f"    {msg_type}: {count}")

        # Show per-user stats for active users
        if self.stats.packets_by_user:
            self.log.info("  Top Users by Packet Activity:")
            sorted_users = sorted(
                self.stats.packets_by_user.items(),
                key=lambda x: x[1]['received'] + x[1]['sent'],
                reverse=True
            )[:5]
            for user_id, user_stats in sorted_users:
                user = self.users.get(user_id)
                username = user.username if user else f"ID:{user_id}"
                total = user_stats['received'] + user_stats['sent']
                self.log.info(f"    {username}: {user_stats['received']} recv / {user_stats['sent']} sent (total: {total})")

        self.log.info("=" * 60)

    async def _send_response(self, writer: asyncio.StreamWriter, response: Dict):
        """Send JSON response to client"""
        try:
            data = json.dumps(response) + "\n"
            writer.write(data.encode())
            await writer.drain()
        except Exception as e:
            self.log.error(f"Failed to send response: {e}")

    async def _handle_register(self, network_name: str, network_id: str, capabilities: List[str],
                              writer: asyncio.StreamWriter) -> tuple[int, str]:
        """Handle network registration"""
        if not network_id:
            network_id = secrets.token_hex(16)

        block = self.network_manager.register_network(network_id, network_name, capabilities, writer)

        await self._send_response(writer, {
            "type": "registered",
            "block": block,
            "network_id": network_id
        })

        self._save_state()
        return block, network_id

    async def _handle_user_login(self, network_id: str, message: Dict):
        """Handle user login notification"""
        local_id = message.get("local_id", 0)
        username = message.get("username", "")
        email = message.get("email", "")
        firstname = message.get("firstname", "")
        lastname = message.get("lastname", "")

        network = self.network_manager.get_network_by_id(network_id)
        if not network:
            self.log.warning(f"Login from unknown network: {network_id}")
            return

        global_id = network.block + local_id

        # Check if user exists - update info if changed (retail trackers can change username)
        existing_user = self.users.get(global_id)
        if existing_user:
            old_username = existing_user.username
            if username and username != old_username:
                self.log.info(f"User {global_id} username changed: '{old_username}' -> '{username}'")
            # Update existing user - update all fields that are provided
            existing_user.username = username if username else existing_user.username
            existing_user.email = email if email else existing_user.email
            existing_user.firstname = firstname if firstname else existing_user.firstname
            existing_user.lastname = lastname if lastname else existing_user.lastname
            existing_user.status = message.get("status", 1)
            existing_user.last_seen = time.time()
            existing_user.game_data = message.get("game_data")
            user = existing_user
        else:
            # Create new user entry
            # Use email as fallback if username is empty
            effective_username = username if username else email if email else f"User_{local_id}"
            user = GlobalUser(
                global_id=global_id,
                username=effective_username,
                network=network.name,
                local_id=local_id,
                status=message.get("status", 1),
                last_seen=time.time(),
                game_data=message.get("game_data"),
                email=email,
                firstname=firstname,
                lastname=lastname
            )
            self.users[global_id] = user
            self.log.info(f"NEW user registered: {effective_username} (global_id: {global_id}, local_id: {local_id}) on {network.name}")
            if email:
                self.log.info(f"  Email: {email}")
            if firstname or lastname:
                self.log.info(f"  Name: {firstname} {lastname}")

        await self.status_engine.handle_user_login(global_id, user)

        # Send response
        await self.network_manager.send_to_network(network_id, {
            "type": "user_login_ack",
            "global_id": global_id,
            "request_id": message.get("request_id")
        })

        self.log.info(f"User '{user.username}' (ID: {global_id}) logged in to {network.name} with status {user.status}")
        self._save_state()

    async def _handle_user_logout(self, network_id: str, message: Dict):
        """Handle user logout notification"""
        global_id = message.get("global_id", 0)
        self.log.info(f"Logout notification for global_id: {global_id} from network: {network_id}")

        if global_id in self.users:
            username = self.users[global_id].username
            network_name = self.users[global_id].network
            await self.status_engine.handle_user_logout(global_id)
            self.log.info(f"User '{username}' (ID: {global_id}) logged out from {network_name}")
        else:
            self.log.warning(f"Logout for unknown user global_id: {global_id}")

    async def _handle_status_update(self, network_id: str, message: Dict):
        """Handle user status update"""
        global_id = message.get("global_id", 0)
        status = message.get("status", 0)
        game_data = message.get("game_data")

        user = self.users.get(global_id)
        if user:
            old_status = user.status
            self.log.info(f"Status update: '{user.username}' (ID: {global_id}) status {old_status} -> {status}")
            if game_data:
                self.log.info(f"  Game data: {game_data}")
        else:
            # User not found - create a placeholder entry
            # This can happen if status update arrives before login notification
            network = self.network_manager.get_network_by_id(network_id)
            if network:
                local_id = global_id - network.block
                user = GlobalUser(
                    global_id=global_id,
                    username=f"User_{local_id}",
                    network=network.name,
                    local_id=local_id,
                    status=status,
                    last_seen=time.time(),
                    game_data=game_data,
                    email="",
                    firstname="",
                    lastname=""
                )
                self.users[global_id] = user
                self.log.info(f"Auto-created user entry for status update: global_id={global_id}, status={status}")
            else:
                self.log.warning(f"Status update for unknown user global_id: {global_id} from unknown network: {network_id}")
                return

        await self.status_engine.handle_status_change(global_id, status, game_data)

    async def _handle_search_request(self, network_id: str, message: Dict):
        """Handle cross-network user search

        Search behavior:
        - If query contains @<network>, search for exact username match on that specific network
        - If query does not contain @, search all fields case-insensitively across all networks
        - Field-specific searches (username, email, firstname, lastname) are case-insensitive
        """
        raw_query = message.get("query", "")
        email_query = message.get("email", "").lower().strip()
        firstname_query = message.get("firstname", "").lower().strip()
        lastname_query = message.get("lastname", "").lower().strip()
        username_query = message.get("username", "").lower().strip()
        requesting_user = message.get("requesting_user", 0)

        # Parse @<network> from query if present
        target_network = None
        search_username = None
        exact_match_mode = False

        if "@" in raw_query:
            # Split on the last @ to handle usernames that might contain @
            parts = raw_query.rsplit("@", 1)
            if len(parts) == 2 and parts[1].strip():
                search_username = parts[0].lower().strip()
                target_network = parts[1].lower().strip()
                exact_match_mode = True
                self.log.info(f"Exact match search: username='{search_username}' on network='{target_network}'")

        # For general search (no @network), use the query as-is
        query = raw_query.lower().strip() if not exact_match_mode else ""

        self.log.info(f"Search request from network '{network_id}': raw_query='{raw_query}', "
                     f"exact_match={exact_match_mode}, target_network='{target_network}', "
                     f"username='{username_query}', email='{email_query}', "
                     f"firstname='{firstname_query}', lastname='{lastname_query}', "
                     f"requesting_user={requesting_user}")
        self.log.info(f"  Total users in registry: {len(self.users)}")

        results = []
        requesting_network = self.network_manager.get_network_id_by_global_id(requesting_user) if requesting_user else network_id

        for global_id, user in self.users.items():
            # Don't include the requesting user themselves
            if global_id == requesting_user:
                continue

            # Don't include users from the same network (they can search locally)
            user_network = self.network_manager.get_network_id_by_global_id(global_id)
            if user_network == requesting_network:
                continue

            matches = False

            if exact_match_mode:
                # Exact match mode: username@network specified
                # Match if username matches exactly (case-insensitive) AND network matches
                username_matches = user.username.lower() == search_username
                network_matches = user.network.lower() == target_network

                if username_matches and network_matches:
                    matches = True
                    self.log.info(f"  Exact match found: {user.username}@{user.network}")
            elif query:
                # General query: search all fields case-insensitively
                if (query in user.username.lower() or
                    query in user.email.lower() or
                    query in user.firstname.lower() or
                    query in user.lastname.lower()):
                    matches = True
            else:
                # Field-specific searches - all provided fields must match (case-insensitive)
                field_matches = []
                if username_query:
                    field_matches.append(username_query in user.username.lower())
                if email_query:
                    field_matches.append(email_query in user.email.lower())
                if firstname_query:
                    field_matches.append(firstname_query in user.firstname.lower())
                if lastname_query:
                    field_matches.append(lastname_query in user.lastname.lower())

                # If no specific fields provided, match all users (from other networks)
                if not field_matches:
                    matches = True
                else:
                    # All provided fields must match
                    matches = all(field_matches)

            if not matches:
                continue

            results.append({
                "global_id": global_id,
                "username": f"{user.username}@{user.network}",
                "network": user.network,
                "firstname": user.firstname,
                "lastname": user.lastname
            })

            # In exact match mode, we only want one result
            if exact_match_mode and matches:
                break

        self.log.info(f"Search results: {len(results)} users found")
        for r in results[:10]:
            self.log.info(f"  - {r['username']} (ID: {r['global_id']})")

        await self.network_manager.send_to_network(network_id, {
            "type": "search_response",
            "results": results,
            "request_id": message.get("request_id")
        })

    async def _handle_friend_request(self, network_id: str, message: Dict):
        """Handle cross-network friend request"""
        from_global_id = message.get("from_global_id", 0)
        to_global_id = message.get("to_global_id", 0)

        if from_global_id == to_global_id:
            return

        # Add pending request
        self.friendship_manager.add_pending_request(from_global_id, to_global_id)

        # Forward to target network
        target_network_id = self.network_manager.get_network_id_by_global_id(to_global_id)
        if target_network_id:
            from_user = self.users.get(from_global_id)
            if from_user:
                await self.network_manager.send_to_network(target_network_id, {
                    "type": "deliver_friend_request",
                    "from_global_id": from_global_id,
                    "from_username": f"{from_user.username}@{from_user.network}",
                    "to_global_id": to_global_id
                })

        self._save_state()

    async def _handle_friend_accept(self, network_id: str, message: Dict):
        """Handle friend request acceptance"""
        from_global_id = message.get("from_global_id", 0)
        to_global_id = message.get("to_global_id", 0)

        # Create friendship
        if self.friendship_manager.add_friendship(from_global_id, to_global_id):
            # Notify both networks
            for user_id in [from_global_id, to_global_id]:
                user_network_id = self.network_manager.get_network_id_by_global_id(user_id)
                if user_network_id:
                    await self.network_manager.send_to_network(user_network_id, {
                        "type": "friendship_established",
                        "user_global_id": user_id,
                        "friend_global_id": to_global_id if user_id == from_global_id else from_global_id
                    })

            self.log.info(f"Friendship established between {from_global_id} and {to_global_id}")
            self._save_state()

    async def _handle_friend_remove(self, network_id: str, message: Dict):
        """Handle friendship removal"""
        from_global_id = message.get("from_global_id", 0)
        to_global_id = message.get("to_global_id", 0)

        if self.friendship_manager.remove_friendship(from_global_id, to_global_id):
            # Notify both networks
            for user_id in [from_global_id, to_global_id]:
                user_network_id = self.network_manager.get_network_id_by_global_id(user_id)
                if user_network_id:
                    await self.network_manager.send_to_network(user_network_id, {
                        "type": "friendship_removed",
                        "user_global_id": user_id,
                        "friend_global_id": to_global_id if user_id == from_global_id else from_global_id
                    })

            self.log.info(f"Friendship removed between {from_global_id} and {to_global_id}")
            self._save_state()

    async def _handle_forward_message(self, network_id: str, message: Dict):
        """Handle message forwarding between networks"""
        from_global_id = message.get("from_global_id", 0)
        to_global_id = message.get("to_global_id", 0)
        message_type = message.get("message_type", "chat")
        payload = message.get("payload", {})

        success = await self.message_router.forward_message(
            from_global_id, to_global_id, message_type, payload
        )

        if not success:
            # Send delivery failure notification
            await self.network_manager.send_to_network(network_id, {
                "type": "message_delivery_failed",
                "from_global_id": from_global_id,
                "to_global_id": to_global_id,
                "reason": "user_offline_or_unreachable"
            })

    async def _handle_get_friends(self, network_id: str, message: Dict):
        """Handle get friends list request"""
        global_id = message.get("global_id", 0)
        friends_list = []

        for friend_global_id in self.friendship_manager.get_friends(global_id):
            friend_user = self.users.get(friend_global_id)
            if friend_user:
                friend_status = 0
                if friend_global_id in self.status_engine.online_users:
                    friend_status = self.status_engine.online_users[friend_global_id].status

                friends_list.append({
                    "global_id": friend_global_id,
                    "username": f"{friend_user.username}@{friend_user.network}",
                    "network": friend_user.network,
                    "status": friend_status
                })

        await self.network_manager.send_to_network(network_id, {
            "type": "friends_list",
            "global_id": global_id,
            "friends": friends_list,
            "request_id": message.get("request_id")
        })

    async def _handle_heartbeat(self, network_id: str, message: Dict):
        """Handle network heartbeat"""
        network = self.network_manager.get_network_by_id(network_id)
        if network:
            network.last_heartbeat = time.time()

    async def _handle_get_stats(self, network_id: str, message: Dict):
        """Handle request for server statistics"""
        stats_summary = self.stats.get_summary()
        online_networks = sum(1 for n in self.network_manager.networks.values() if n.connection)
        online_users = len(self.status_engine.online_users)

        # Get per-user stats if requested
        user_stats = {}
        if message.get("include_user_stats"):
            for user_id, user_packet_stats in self.stats.packets_by_user.items():
                user = self.users.get(user_id)
                user_stats[user_id] = {
                    "username": user.username if user else f"ID:{user_id}",
                    "network": user.network if user else "unknown",
                    "received": user_packet_stats["received"],
                    "sent": user_packet_stats["sent"]
                }

        await self.network_manager.send_to_network(network_id, {
            "type": "stats_response",
            "uptime": stats_summary["uptime"],
            "total_received": stats_summary["total_received"],
            "total_sent": stats_summary["total_sent"],
            "packets_by_type": stats_summary["packets_by_type"],
            "networks_online": online_networks,
            "networks_registered": len(self.network_manager.networks),
            "users_online": online_users,
            "users_registered": len(self.users),
            "user_stats": user_stats,
            "request_id": message.get("request_id")
        })

    async def _process_message(self, network_id: str, message: Dict):
        """Process incoming message from network"""
        msg_type = message.get("type")

        # Extract user ID for statistics if available
        user_global_id = message.get("global_id") or message.get("from_global_id") or message.get("local_id")

        # Log incoming message
        self.log.info(f"<-- Received from {network_id}: type={msg_type}")

        # Record packet received
        self.stats.record_received(msg_type or "unknown", network_id, user_global_id)

        try:
            if msg_type == "user_login":
                await self._handle_user_login(network_id, message)
            elif msg_type == "user_logout":
                await self._handle_user_logout(network_id, message)
            elif msg_type == "status_update":
                await self._handle_status_update(network_id, message)
            elif msg_type == "search_request":
                await self._handle_search_request(network_id, message)
            elif msg_type == "friend_request":
                await self._handle_friend_request(network_id, message)
            elif msg_type == "friend_accept":
                await self._handle_friend_accept(network_id, message)
            elif msg_type == "friend_remove":
                await self._handle_friend_remove(network_id, message)
            elif msg_type == "forward_message":
                await self._handle_forward_message(network_id, message)
            elif msg_type == "get_friends":
                await self._handle_get_friends(network_id, message)
            elif msg_type == "heartbeat":
                await self._handle_heartbeat(network_id, message)
            elif msg_type == "get_stats":
                await self._handle_get_stats(network_id, message)
            else:
                self.log.warning(f"Unknown message type: {msg_type} from {network_id}")
                self.log.info(f"  Full message: {message}")

        except Exception as e:
            self.log.error(f"Error processing {msg_type} from {network_id}: {e}")
            import traceback
            self.log.info(traceback.format_exc())

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming network connection"""
        client_addr = writer.get_extra_info('peername')
        network_id = None

        try:
            # Read registration message
            line = await reader.readline()
            if not line:
                writer.close()
                return

            try:
                reg_message = json.loads(line.decode().strip())
            except json.JSONDecodeError:
                self.log.error(f"Invalid JSON from {client_addr}")
                writer.close()
                return

            if reg_message.get("type") != "register":
                self.log.error(f"Expected register message from {client_addr}")
                writer.close()
                return

            # Register network
            network_name = reg_message.get("network", "")
            network_id = reg_message.get("network_id", "")
            capabilities = reg_message.get("capabilities", [])

            if not network_name:
                self.log.error(f"Missing network name from {client_addr}")
                writer.close()
                return

            block, network_id = await self._handle_register(
                network_name, network_id, capabilities, writer
            )

            self.log.info(f"Network '{network_name}' connected from {client_addr}")

            # Process messages
            while True:
                line = await reader.readline()
                if not line:
                    break

                try:
                    message = json.loads(line.decode().strip())
                    await self._process_message(network_id, message)
                except json.JSONDecodeError as e:
                    self.log.warning(f"Invalid JSON from {network_id}: {e}")
                except Exception as e:
                    self.log.error(f"Error processing message from {network_id}: {e}")

        except Exception as e:
            self.log.error(f"Error handling client {client_addr}: {e}")

        finally:
            writer.close()
            if network_id:
                self.network_manager.unregister_network(network_id)
                self.log.info(f"Network {network_id} disconnected")

    def _print_banner(self):
        """Print server startup banner"""
        banner = """
============================================================
     GLOBAL TRACKER SERVER - Steam Emulator Network Hub
============================================================
"""
        print(banner)
        print(f"  Status:     RUNNING")
        print(f"  Port:       {self.port}")
        print(f"  State File: {self.state_file}")
        print(f"  Networks:   {len(self.network_manager.networks)} registered")
        print(f"  Users:      {len(self.users)} registered")
        print(f"  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("  Listening for network connections...")
        print("  Press Ctrl+C to stop the server")
        print("============================================================")
        print()

    async def start(self):
        """Start the global tracker server"""
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self.port
        )

        self._print_banner()
        self.log.info(f"Global Tracker Server started on port {self.port}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        """Stop the global tracker server"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._save_state()

            # Display final statistics
            print()
            print("============================================================")
            print("     GLOBAL TRACKER SERVER - Shutdown Summary")
            print("============================================================")
            self._display_stats()
            self.log.info("Global Tracker Server stopped")


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


async def main():
    """Main entry point"""
    import sys

    setup_logging()

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1300
    state_file = sys.argv[2] if len(sys.argv) > 2 else "global_tracker_state.json"

    tracker = GlobalTracker(port, state_file)

    try:
        await tracker.start()
    except KeyboardInterrupt:
        await tracker.stop()


if __name__ == "__main__":
    asyncio.run(main())