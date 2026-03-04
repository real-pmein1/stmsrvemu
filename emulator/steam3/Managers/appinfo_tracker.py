"""
AppInfo Tracker

Tracks which appinfo items have been sent to each client to prevent sending
the same appinfo multiple times. Resets tracking on blob/CDR changes.

Usage:
    tracker = get_appinfo_tracker()

    # Get unsent appids for a client
    unsent = tracker.get_unsent_appids(client_id, requested_appids)

    # Mark appids as sent
    tracker.mark_appids_sent(client_id, sent_appids)

    # Reset tracking on CDR change
    tracker.reset_on_blob_change(new_blob_version)
"""
import logging
import threading
from typing import List, Set, Dict, Optional

log = logging.getLogger("AppInfoTracker")


class AppInfoTracker:
    """
    Tracks which appinfo items have been sent to each client.

    Features:
    - Per-client tracking of sent appids
    - Automatic reset on blob/CDR changes
    - Thread-safe operations
    - Client cleanup on disconnect
    """

    def __init__(self):
        # Track sent appids per client: {client_id: set(appids)}
        self.sent_appids: Dict[int, Set[int]] = {}

        # Current blob version (CDR datetime or version number)
        self.current_blob_version: Optional[str] = None

        # Lock for thread-safe operations
        self.lock = threading.Lock()

        log.info("AppInfoTracker initialized")

    def get_unsent_appids(self, client_id: int, requested_appids: List[int]) -> List[int]:
        """
        Get the list of appids that haven't been sent to this client yet.

        :param client_id: Client connection ID
        :param requested_appids: List of appids the client is requesting
        :return: List of appids that haven't been sent yet (maintains original order)
        """
        with self.lock:
            if client_id not in self.sent_appids:
                # First request from this client - all are unsent
                return requested_appids

            # Get set of already sent appids for this client
            already_sent = self.sent_appids[client_id]

            # Filter to only unsent appids (preserve order)
            unsent = [appid for appid in requested_appids if appid not in already_sent]

            log.debug(f"Client {client_id}: Requested {len(requested_appids)} appids, "
                     f"{len(already_sent)} already sent, {len(unsent)} unsent")

            return unsent

    def mark_appids_sent(self, client_id: int, appids: List[int]):
        """
        Mark the specified appids as sent to this client.

        :param client_id: Client connection ID
        :param appids: List of appids that were sent
        """
        if not appids:
            return

        with self.lock:
            if client_id not in self.sent_appids:
                self.sent_appids[client_id] = set()

            # Add to sent set
            self.sent_appids[client_id].update(appids)

            log.debug(f"Client {client_id}: Marked {len(appids)} appids as sent "
                     f"(total sent: {len(self.sent_appids[client_id])})")

    def reset_on_blob_change(self, new_blob_version: str):
        """
        Reset all tracking when the blob/CDR changes.

        This ensures clients get updated appinfo when the server data changes.

        :param new_blob_version: New blob version identifier (CDR datetime or version)
        """
        with self.lock:
            if self.current_blob_version == new_blob_version:
                # No change, don't reset
                return

            old_version = self.current_blob_version
            self.current_blob_version = new_blob_version

            # Clear all tracking
            client_count = len(self.sent_appids)
            self.sent_appids.clear()

            log.info(f"Blob version changed from '{old_version}' to '{new_blob_version}' - "
                    f"reset tracking for {client_count} clients")

    def clear_client(self, client_id: int):
        """
        Clear tracking for a specific client (called on disconnect).

        :param client_id: Client connection ID to clear
        """
        with self.lock:
            if client_id in self.sent_appids:
                count = len(self.sent_appids[client_id])
                del self.sent_appids[client_id]
                log.debug(f"Cleared tracking for client {client_id} ({count} appids tracked)")

    def get_stats(self) -> Dict:
        """
        Get statistics about current tracking state.

        :return: Dictionary with tracking statistics
        """
        with self.lock:
            total_clients = len(self.sent_appids)
            total_appids_tracked = sum(len(appids) for appids in self.sent_appids.values())
            avg_per_client = total_appids_tracked / total_clients if total_clients > 0 else 0

            return {
                'blob_version': self.current_blob_version,
                'clients_tracked': total_clients,
                'total_appids_tracked': total_appids_tracked,
                'avg_appids_per_client': avg_per_client
            }

    def get_client_sent_count(self, client_id: int) -> int:
        """
        Get the number of appids sent to a specific client.

        :param client_id: Client connection ID
        :return: Number of appids sent to this client
        """
        with self.lock:
            return len(self.sent_appids.get(client_id, set()))


# Global singleton instance
_appinfo_tracker = None


def get_appinfo_tracker() -> AppInfoTracker:
    """
    Get the global AppInfoTracker instance (singleton pattern).

    :return: AppInfoTracker instance
    """
    global _appinfo_tracker
    if _appinfo_tracker is None:
        _appinfo_tracker = AppInfoTracker()
    return _appinfo_tracker
