"""
P2P Manager - manages P2P sessions and connections
Matches C++ P2P management functionality
"""

from __future__ import annotations
import time
import threading
import logging
from typing import Dict, List, Optional, Tuple

from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import P2PSessionError
from .p2p_session import P2PSession

log = logging.getLogger("P2PManager")


class P2PManager:
    """
    P2P Manager matching C++ P2P management functionality
    
    Manages all P2P sessions, connections, and routing between Steam clients
    Thread-safe for concurrent operations
    """
    
    def __init__(self):
        # Session tracking
        self.active_sessions: Dict[str, P2PSession] = {}
        self.session_history: List[P2PSession] = []
        
        # Connection tracking  
        self.pending_connections: Dict[str, List[P2PSession]] = {}
        self.failed_connections: Dict[str, List[Tuple[P2PSession, P2PSessionError]]] = {}
        
        # Session ID generation
        self._next_session_id = 1
        self._next_socket_id = 1000
        
        # Statistics
        self.total_sessions_created = 0
        self.total_sessions_ended = 0
        self.total_bytes_transferred = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cleanup thread
        self._cleanup_interval = 60  # seconds
        self._last_cleanup = time.time()
    
    def create_session(self, source_steam_id: SteamID, dest_steam_id: SteamID, 
                      app_id: int) -> P2PSession:
        """Create a new P2P session between two clients"""
        with self._lock:
            session = P2PSession(source_steam_id, dest_steam_id, app_id)
            session_key = session.get_session_key()
            
            # Check if session already exists
            if session_key in self.active_sessions:
                log.warning(f"P2P session already exists: {session_key}")
                return self.active_sessions[session_key]
            
            # Generate unique session ID
            session.session_id = self._generate_session_id()
            session.socket_id = self._generate_socket_id()
            
            # Add to tracking
            self.active_sessions[session_key] = session
            self.total_sessions_created += 1
            
            log.info(f"Created P2P session: {session}")
            return session
    
    def start_session(self, source_steam_id: SteamID, dest_steam_id: SteamID, 
                     app_id: int, session_flags: int = 0) -> Optional[P2PSession]:
        """Start a P2P session between two clients"""
        with self._lock:
            session_key = f"{source_steam_id}_{dest_steam_id}_{app_id}"
            
            # Get or create session
            if session_key in self.active_sessions:
                session = self.active_sessions[session_key]
            else:
                session = self.create_session(source_steam_id, dest_steam_id, app_id)
            
            # Start the session
            session.start_session(session.session_id, session.socket_id, session_flags)
            
            log.info(f"Started P2P session: {session}")
            return session
    
    def end_session(self, source_steam_id: SteamID, dest_steam_id: SteamID, 
                   app_id: int, reason: P2PSessionError = P2PSessionError.none) -> bool:
        """End a P2P session between two clients"""
        with self._lock:
            session_key = f"{source_steam_id}_{dest_steam_id}_{app_id}"
            
            if session_key not in self.active_sessions:
                log.warning(f"Cannot end non-existent P2P session: {session_key}")
                return False
            
            session = self.active_sessions[session_key]
            session.end_session(reason)
            
            # Move to history
            self.session_history.append(session)
            del self.active_sessions[session_key]
            self.total_sessions_ended += 1
            
            log.info(f"Ended P2P session: {session} (reason={reason})")
            return True
    
    def get_session(self, source_steam_id: SteamID, dest_steam_id: SteamID, 
                   app_id: int) -> Optional[P2PSession]:
        """Get an active P2P session"""
        with self._lock:
            session_key = f"{source_steam_id}_{dest_steam_id}_{app_id}"
            return self.active_sessions.get(session_key)
    
    def get_sessions_for_client(self, steam_id: SteamID) -> List[P2PSession]:
        """Get all active sessions for a specific client"""
        with self._lock:
            sessions = []
            for session in self.active_sessions.values():
                if (session.source_steam_id == steam_id or 
                    session.dest_steam_id == steam_id):
                    sessions.append(session)
            return sessions
    
    def get_sessions_for_app(self, app_id: int) -> List[P2PSession]:
        """Get all active sessions for a specific app"""
        with self._lock:
            sessions = []
            for session in self.active_sessions.values():
                if session.app_id == app_id:
                    sessions.append(session)
            return sessions
    
    def record_connection_attempt(self, source_steam_id: SteamID, dest_steam_id: SteamID, 
                                app_id: int):
        """Record a P2P connection attempt"""
        with self._lock:
            session = self.create_session(source_steam_id, dest_steam_id, app_id)
            
            # Add to pending connections
            client_key = str(source_steam_id)
            if client_key not in self.pending_connections:
                self.pending_connections[client_key] = []
            
            self.pending_connections[client_key].append(session)
            log.debug(f"Recorded P2P connection attempt: {session}")
    
    def record_connection_failure(self, source_steam_id: SteamID, dest_steam_id: SteamID, 
                                app_id: int, error: P2PSessionError):
        """Record a P2P connection failure"""
        with self._lock:
            session_key = f"{source_steam_id}_{dest_steam_id}_{app_id}"
            
            # Remove from pending if exists
            client_key = str(source_steam_id)
            if client_key in self.pending_connections:
                self.pending_connections[client_key] = [
                    s for s in self.pending_connections[client_key] 
                    if s.get_session_key() != session_key
                ]
            
            # Add to failed connections
            if client_key not in self.failed_connections:
                self.failed_connections[client_key] = []
            
            session = P2PSession(source_steam_id, dest_steam_id, app_id)
            session.last_error = error
            self.failed_connections[client_key].append((session, error))
            
            log.warning(f"Recorded P2P connection failure: {session} (error={error})")
    
    def cleanup_expired_sessions(self, timeout_ms: int = 300000):
        """Clean up expired sessions and connection attempts"""
        with self._lock:
            current_time = time.time()
            
            # Skip if cleanup was recent
            if current_time - self._last_cleanup < self._cleanup_interval:
                return
            
            expired_sessions = []
            for session_key, session in self.active_sessions.items():
                if session.is_expired(timeout_ms):
                    expired_sessions.append(session_key)
            
            # End expired sessions
            for session_key in expired_sessions:
                session = self.active_sessions[session_key]
                self.end_session(session.source_steam_id, session.dest_steam_id, 
                               session.app_id, P2PSessionError.timeout)
            
            # Clean up old pending connections
            for client_key in list(self.pending_connections.keys()):
                self.pending_connections[client_key] = [
                    s for s in self.pending_connections[client_key] 
                    if not s.is_expired(timeout_ms)
                ]
                if not self.pending_connections[client_key]:
                    del self.pending_connections[client_key]
            
            # Limit failed connection history
            for client_key in list(self.failed_connections.keys()):
                if len(self.failed_connections[client_key]) > 100:
                    self.failed_connections[client_key] = self.failed_connections[client_key][-50:]
            
            # Limit session history
            if len(self.session_history) > 1000:
                self.session_history = self.session_history[-500:]
            
            self._last_cleanup = current_time
            
            if expired_sessions:
                log.info(f"Cleaned up {len(expired_sessions)} expired P2P sessions")
    
    def get_statistics(self) -> Dict:
        """Get P2P manager statistics"""
        with self._lock:
            total_bytes = sum(s.bytes_sent + s.bytes_received for s in self.active_sessions.values())
            total_bytes += sum(s.bytes_sent + s.bytes_received for s in self.session_history)
            
            return {
                'active_sessions': len(self.active_sessions),
                'total_sessions_created': self.total_sessions_created,
                'total_sessions_ended': self.total_sessions_ended,
                'total_bytes_transferred': total_bytes,
                'pending_connections': sum(len(conns) for conns in self.pending_connections.values()),
                'failed_connections': sum(len(conns) for conns in self.failed_connections.values()),
                'session_history_size': len(self.session_history)
            }
    
    def _generate_session_id(self) -> int:
        """Generate unique session ID"""
        session_id = self._next_session_id
        self._next_session_id += 1
        return session_id
    
    def _generate_socket_id(self) -> int:
        """Generate unique socket ID"""
        socket_id = self._next_socket_id
        self._next_socket_id += 1
        return socket_id


# Global P2P manager instance
P2P_Manager = P2PManager()