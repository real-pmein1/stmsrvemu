"""
P2P Session object - manages individual P2P connections between clients
Matches C++ P2P session functionality
"""

from __future__ import annotations
import time
import threading
from typing import Optional

from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import P2PSessionError


class P2PSession:
    """
    P2P Session object matching C++ P2P session functionality
    
    Manages state and statistics for a P2P connection between two Steam clients
    """
    
    def __init__(self, source_steam_id: SteamID, dest_steam_id: SteamID, app_id: int):
        self.source_steam_id = source_steam_id
        self.dest_steam_id = dest_steam_id
        self.app_id = app_id
        
        # Session identification
        self.session_id = 0
        self.socket_id = 0
        self.session_flags = 0
        
        # Session state
        self.is_active = False
        self.start_time = 0
        self.end_time = 0
        self.last_activity = 0
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        
        # Connection info
        self.connection_type = "unknown"  # local, stun, relay
        self.local_address = ""
        self.remote_address = ""
        self.nat_type = 0
        
        # Error tracking
        self.last_error = P2PSessionError.none
        self.error_count = 0
        
        # Thread safety
        self._lock = threading.RLock()
    
    def start_session(self, session_id: int, socket_id: int = 0, session_flags: int = 0):
        """Start the P2P session with given parameters"""
        with self._lock:
            self.session_id = session_id
            self.socket_id = socket_id
            self.session_flags = session_flags
            self.is_active = True
            self.start_time = int(time.time() * 1000)  # milliseconds
            self.last_activity = self.start_time
            self.end_time = 0
    
    def end_session(self, reason: P2PSessionError = P2PSessionError.none):
        """End the P2P session with specified reason"""
        with self._lock:
            if self.is_active:
                self.is_active = False
                self.end_time = int(time.time() * 1000)
                self.last_error = reason
    
    def record_data_sent(self, bytes_count: int):
        """Record bytes sent through this session"""
        with self._lock:
            self.bytes_sent += bytes_count
            self.packets_sent += 1
            self.last_activity = int(time.time() * 1000)
    
    def record_data_received(self, bytes_count: int):
        """Record bytes received through this session"""
        with self._lock:
            self.bytes_received += bytes_count
            self.packets_received += 1
            self.last_activity = int(time.time() * 1000)
    
    def get_duration(self) -> int:
        """Get session duration in milliseconds"""
        with self._lock:
            if self.start_time == 0:
                return 0
            
            end_time = self.end_time if self.end_time > 0 else int(time.time() * 1000)
            return end_time - self.start_time
    
    def is_expired(self, timeout_ms: int = 300000) -> bool:
        """Check if session has expired (default 5 minutes)"""
        with self._lock:
            if not self.is_active:
                return True
            
            current_time = int(time.time() * 1000)
            return (current_time - self.last_activity) > timeout_ms
    
    def get_session_key(self) -> str:
        """Get unique session key for this P2P connection"""
        return f"{self.source_steam_id}_{self.dest_steam_id}_{self.app_id}"
    
    def __repr__(self):
        return (f"P2PSession(source={self.source_steam_id}, dest={self.dest_steam_id}, "
               f"app={self.app_id}, session={self.session_id}, active={self.is_active})")
    
    def __str__(self):
        return self.__repr__()