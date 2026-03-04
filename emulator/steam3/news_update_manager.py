"""
News Update Manager for Steam CM Server
Handles client update notifications when pkg files are neutered
"""

import os
import logging
import globalvars

log = logging.getLogger("NewsManager")


class NewsUpdateManager:
    """Manages news updates for connected clients"""

    def __init__(self):
        self.pkg_files_neutered = False
        self.neutering_flag_path = os.path.join('files', 'configs', '.isneutering')
        # Flag for pending client update - checked during heartbeat
        self._pending_client_update = False
        self._pending_update_news_id = 2002
    
    def check_neutering_status(self):
        """Check if neutering is currently in progress or has completed"""
        if os.path.exists(self.neutering_flag_path):
            return "in_progress"
        return "completed"
    
    def set_pkg_files_neutered(self, neutered=True):
        """Set the flag indicating pkg files were neutered"""
        self.pkg_files_neutered = neutered
        if neutered:
            log.info("Pkg files have been neutered - client updates will be sent")

    def set_client_update_pending(self, news_id=2002):
        """Set a flag indicating there is a pending client update.

        When this flag is set, the heartbeat handler will send the client
        update news to clients on their next non-UDP heartbeat.

        Args:
            news_id: The news ID to use for the update (default 2002)
        """
        self._pending_client_update = True
        self._pending_update_news_id = news_id
        self.pkg_files_neutered = True
        log.info(f"Client update pending flag set (news_id={news_id}) - will be sent on next heartbeat")

    def has_client_update_pending(self):
        """Check if there is a pending client update.

        Returns:
            bool: True if a client update is pending
        """
        return self._pending_client_update

    def clear_client_update_pending(self):
        """Clear the pending client update flag."""
        self._pending_client_update = False
        log.info("Client update pending flag cleared")

    def create_client_update_message(self, client_obj):
        """Create a client update news message for a specific client.

        This is used by the heartbeat handler to send the update through
        normal CM means instead of broadcasting to all clients.

        Args:
            client_obj: The client to create the message for

        Returns:
            CMResponse packet ready to send, or None if no update pending
        """
        if not self._pending_client_update:
            return None

        try:
            from steam3.messages.MsgClientNewsUpdate import MsgClientNewsUpdate

            steam_version, steamui_version = self.get_steam_version_info()

            news_msg = MsgClientNewsUpdate(client_obj)
            news_msg.add_client_update(
                news_id=self._pending_update_news_id,
                steam_version=steam_version,
                steamui_version=steamui_version,
                reload_cddb=True
            )

            log.debug(f"Created client update message for client {client_obj.steamID} "
                     f"(news_id={self._pending_update_news_id}, steam={steam_version}, steamui={steamui_version})")

            return news_msg.to_clientmsg()

        except Exception as e:
            log.error(f"Failed to create client update message: {e}")
            return None
    
    def get_steam_version_info(self):
        """Get Steam version information from global vars or config"""
        try:
            steam_version = globalvars.steam_ver
            steamui_version = globalvars.steamui_ver
            
            return steam_version, steamui_version
            
        except Exception as e:
            log.warning(f"Failed to get version info: {e}, using defaults")
            raise
    
    def send_client_update_to_all_clients(self, cmserver_obj, news_id=2002):
        """
        Send client update news to all connected clients
        Called when pkg files have been neutered
        """
        try:
            # Import here to avoid circular imports and early Steam3 system access
            try:
                from steam3.messages.MsgClientNewsUpdate import MsgClientNewsUpdate
            except ImportError as e:
                log.warning(f"Steam3 system not ready for news updates: {e}")
                return

            # Get version information
            steam_version, steamui_version = self.get_steam_version_info()
            
            # Get all connected/active valid client objects
            from steam3.ClientManager import Client_Manager
            connected_clients = Client_Manager.get_all_connected_clients()
            
            if not connected_clients:
                log.info("No connected clients to send news update to")
                return
            
            log.info(f"Sending client update news to {len(connected_clients)} clients")
            log.info(f"Steam version: {steam_version}, SteamUI version: {steamui_version}")
            
            # Send to each connected client
            sent_count = 0
            for client_obj in connected_clients:
                try:
                    # Determine which CM server to use - prefer client's own, fallback to passed-in
                    send_server = client_obj.objCMServer if client_obj.objCMServer else cmserver_obj

                    if not send_server:
                        log.debug(f"Skipping client {client_obj.steamID}: no CM server available")
                        continue

                    # Only require encryption key if the CM server uses encryption
                    if getattr(send_server, 'is_encrypted', False) and not client_obj.symmetric_key:
                        log.debug(f"Skipping client {client_obj.steamID}: encrypted connection but no encryption key")
                        continue

                    # Create news update message
                    news_msg = MsgClientNewsUpdate(client_obj)

                    if self.pkg_files_neutered:
                        # If pkg files were neutered, send k_EClientUpdate (type 4)
                        news_msg.add_client_update(
                            news_id=news_id,
                            steam_version=steam_version,        # m_unCurrentBootstrapperVersion
                            steamui_version=steamui_version,    # m_unCurrentClientVersion
                            reload_cddb=True  # Reload CDDB after pkg neutering
                        )
                        log.debug(f"Sending k_EClientUpdate (type 4) to client {client_obj.steamID}")
                    else:
                        # Generic news update
                        news_msg.add_steam_news_item_update(
                            news_id=news_id,
                            update_type=1
                        )
                        log.debug(f"Sending generic news update to client {client_obj.steamID}")

                    # Build and send the packet using determined CM server
                    send_server.sendReply(client_obj, [news_msg.to_clientmsg()])
                    sent_count += 1

                except Exception as e:
                    log.error(f"Failed to send news update to client {client_obj.steamID}: {e}")
            
            log.info(f"Successfully sent news updates to {sent_count} of {len(connected_clients)} clients")
            
        except Exception as e:
            log.error(f"Error sending client updates: {e}")
    
    def send_app_news_update(self, cmserver_obj, app_id, news_id=1001):
        """Send app-specific news update to clients who own the app"""
        try:
            # Import here to avoid circular imports and early Steam3 system access
            try:
                from steam3.messages.MsgClientNewsUpdate import MsgClientNewsUpdate
            except ImportError as e:
                log.warning(f"Steam3 system not ready for app news updates: {e}")
                return
            from steam3.ClientManager import Client_Manager

            connected_clients = Client_Manager.get_all_connected_clients()
            if not connected_clients:
                return

            sent_count = 0
            for client_obj in connected_clients:
                try:
                    # Determine which CM server to use - prefer client's own, fallback to passed-in
                    send_server = client_obj.objCMServer if client_obj.objCMServer else cmserver_obj

                    if not send_server:
                        log.debug(f"Skipping client {client_obj.steamID}: no CM server available")
                        continue

                    # Only require encryption key if the CM server uses encryption
                    if getattr(send_server, 'is_encrypted', False) and not client_obj.symmetric_key:
                        log.debug(f"Skipping client {client_obj.steamID}: encrypted connection but no encryption key")
                        continue

                    # Create app news update
                    news_msg = MsgClientNewsUpdate(client_obj)
                    news_msg.add_app_news_update(news_id, app_id)

                    # Use determined CM server to send
                    send_server.sendReply(client_obj, [news_msg.to_clientmsg()])
                    sent_count += 1

                except Exception as e:
                    log.error(f"Failed to send app news update to client {client_obj.steamID}: {e}")
            
            if sent_count > 0:
                log.info(f"Sent app news update for app {app_id} to {sent_count} clients")
                
        except Exception as e:
            log.error(f"Error sending app news updates: {e}")


# Global instance
news_update_manager = NewsUpdateManager()