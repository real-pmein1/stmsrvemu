
import bisect
import ipaddress
import os
import time
import logging
from functools import lru_cache

log = logging.getLogger("FireHOLLoader")


def _ip_to_int(ip):
    """Convert an IPv4/IPv6 address to integer for fast comparison."""
    if isinstance(ip, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return int(ip)
    return int(ipaddress.ip_address(ip))


class FireHOLLoader:
    _instance = None  # Singleton instance
    firehol_ips = set()
    # Sorted list of (start_int, end_int) intervals for O(log n) lookup
    _ip_intervals = []
    _interval_starts = []  # Just the start values for binary search
    # LRU cache for per-IP decisions
    _ip_cache = {}
    _cache_max_size = 10000
    last_update = 0
    update_interval = 86400  # Update every 24 hours

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FireHOLLoader, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, firehol_urls=None):
        self.configsdir = os.path.join('files', 'configs')
        self.firehol_cache_file = os.path.join(self.configsdir, 'firehol_cache.txt')
        self.firehol_urls = firehol_urls or [
            "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset"
        ]

    def update_firehol_ips(self):
        import requests
        """
        Download FireHOL IP ranges and update the cached file.
        """
        try:
            log.info("Updating FireHOL IP lists...")
            with open(self.firehol_cache_file, 'w') as cache_file:
                for url in self.firehol_urls:
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        for line in response.iter_lines(decode_unicode=True):
                            if line and not line.startswith('#'):
                                cache_file.write(line + '\n')
                    else:
                        log.warning(f"Failed to download FireHOL list from {url} (status: {response.status_code})")
            log.info("FireHOL IP lists updated successfully.")
        except Exception as e:
            log.error(f"Error updating FireHOL lists: {e}")

    def load_firehol_ips(self):
        """
        Load FireHOL IP ranges from the cached file into memory.
        Builds a sorted interval structure for O(log n) lookups.
        """
        if time.time() - self.last_update < self.update_interval:
            return

        if not os.path.exists(self.firehol_cache_file):
            log.warning("FireHOL cache file not found. Updating lists...")
            self.update_firehol_ips()

        try:
            networks = []
            with open(self.firehol_cache_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            net = ipaddress.ip_network(line)
                            networks.append(net)
                        except ValueError:
                            continue

            self.firehol_ips = set(networks)

            # Build sorted interval structure for O(log n) lookups
            intervals = []
            for net in networks:
                start_int = int(net.network_address)
                end_int = int(net.broadcast_address)
                intervals.append((start_int, end_int))

            # Sort by start address
            intervals.sort(key=lambda x: x[0])
            self._ip_intervals = intervals
            self._interval_starts = [iv[0] for iv in intervals]

            # Clear the IP cache when reloading
            self._ip_cache.clear()

            self.last_update = time.time()
            log.info(f"Loaded {len(self.firehol_ips)} IP ranges from FireHOL (optimized).")
        except Exception as e:
            log.error(f"Error loading FireHOL IP ranges: {e}")

    def is_ip_blocked(self, ip):
        """
        Check if an IP is within any FireHOL range.
        Uses binary search for O(log n) lookup and memoization for repeated checks.
        :param ip: IP address to check.
        :return: True if the IP is blocked, False otherwise.
        """
        # Check memoization cache first
        if ip in self._ip_cache:
            return self._ip_cache[ip]

        try:
            ip_int = _ip_to_int(ip)

            # Binary search: find the rightmost interval that could contain this IP
            # bisect_right gives us the insertion point, so we check the interval before it
            idx = bisect.bisect_right(self._interval_starts, ip_int)

            # Check intervals that could contain this IP (the one before insertion point
            # and potentially a few before it due to overlapping ranges)
            result = False
            for i in range(max(0, idx - 1), min(idx + 1, len(self._ip_intervals))):
                start, end = self._ip_intervals[i]
                if start <= ip_int <= end:
                    result = True
                    break

            # If not found with binary search approach, check a wider range
            # (handles edge cases with overlapping/adjacent networks)
            if not result and idx > 0:
                # Check backwards from idx for any overlapping ranges
                for i in range(idx - 1, -1, -1):
                    start, end = self._ip_intervals[i]
                    if end < ip_int:
                        break  # No more possible matches
                    if start <= ip_int <= end:
                        result = True
                        break

            # Cache the result (with size limit)
            if len(self._ip_cache) >= self._cache_max_size:
                # Simple eviction: clear half the cache
                keys_to_remove = list(self._ip_cache.keys())[:self._cache_max_size // 2]
                for k in keys_to_remove:
                    del self._ip_cache[k]
            self._ip_cache[ip] = result

            return result
        except ValueError:
            log.error(f"Invalid IP address: {ip}")
        return False

fireHOL_manager = FireHOLLoader()
fireHOL_manager.load_firehol_ips()