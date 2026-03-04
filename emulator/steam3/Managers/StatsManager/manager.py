import os
import logging
import threading
from typing import Dict, Optional, Tuple
from io import BytesIO

from steam3.Types.userstats.userstatsschema import UserStatsSchema
from steam3.Types.userstats.userstats import UserStats
from steam3.Types.keyvaluesystem import KeyValuesSystem
from steam3.Types.steam_types import EResult
from datetime import datetime

log = logging.getLogger("StatsManager")


class StatsManager:
    """
    Manages user statistics and achievement schemas/data.
    Loads schemas from binary files and manages user stats persistence.
    """
    
    def __init__(self, database=None):
        self.schema_cache: Dict[int, UserStatsSchema] = {}  # appid -> schema
        self.user_stats_cache: Dict[Tuple[int, int], UserStats] = {}  # (steamid, appid) -> stats
        self.cache_lock = threading.RLock()
        
        # Database connection through steam3 database object
        self.database = database
        
        # Schema directory paths
        self.schema_dir = os.path.join("files", "statschemas", "2010-2023")
        self.user_stats_dir = os.path.join("files", "GameStats", "user_stats")
    
    
    def get_schema(self, appid: int) -> Optional[UserStatsSchema]:
        """
        Get the user stats schema for a specific game.
        First checks cache, then loads from binary file.
        """
        with self.cache_lock:
            if appid in self.schema_cache:
                return self.schema_cache[appid]
            
            # Try to load schema from file
            schema = self._load_schema_from_file(appid)
            if schema:
                self.schema_cache[appid] = schema
                log.debug(f"Loaded schema for appid {appid}")
            else:
                log.warning(f"No schema found for appid {appid}")
            
            return schema
    
    def get_raw_schema_data(self, appid: int) -> bytes:
        """
        Get raw binary schema data for a specific game without parsing.
        Used for attaching schema to client responses.
        """
        if not os.path.exists(self.schema_dir):
            log.error(f"Schema directory not found: {self.schema_dir}")
            return b""
        
        # Look for schema files matching this appid
        # Format: UserGameStatsSchema_{appid}_v{version}.bin
        pattern_prefix = f"UserGameStatsSchema_{appid}_"
        
        best_file = None
        best_version = -1
        
        try:
            for filename in os.listdir(self.schema_dir):
                if filename.startswith(pattern_prefix) and filename.endswith(".bin"):
                    # Extract version from filename
                    version_part = filename[len(pattern_prefix):-4]  # Remove prefix and .bin
                    if version_part.startswith("v"):
                        try:
                            version_str = version_part[1:].split("-")[0].split("_")[0]  # Handle v123-2020 or v123_1
                            version = int(version_str)
                            if version > best_version:
                                best_version = version
                                best_file = filename
                        except ValueError:
                            continue
            
            if best_file:
                schema_path = os.path.join(self.schema_dir, best_file)
                with open(schema_path, "rb") as f:
                    return f.read()
            else:
                log.warning(f"No schema file found for appid {appid}")
                return b""
                
        except Exception as e:
            log.error(f"Error loading raw schema data for appid {appid}: {e}")
            return b""
    
    def _load_schema_from_file(self, appid: int) -> Optional[UserStatsSchema]:
        """
        Load UserStatsSchema from binary file in files/statschemas/2010-2023/
        """
        if not os.path.exists(self.schema_dir):
            log.error(f"Schema directory not found: {self.schema_dir}")
            return None
        
        # Look for schema files matching this appid
        # Format: UserGameStatsSchema_{appid}_v{version}.bin
        pattern_prefix = f"UserGameStatsSchema_{appid}_"
        
        best_file = None
        best_version = -1
        
        try:
            for filename in os.listdir(self.schema_dir):
                if filename.startswith(pattern_prefix) and filename.endswith(".bin"):
                    # Extract version from filename
                    version_part = filename[len(pattern_prefix):-4]  # Remove prefix and .bin
                    if version_part.startswith("v"):
                        try:
                            version_str = version_part[1:].split("-")[0].split("_")[0]  # Handle v123-2020 or v123_1
                            version = int(version_str)
                            if version > best_version:
                                best_version = version
                                best_file = filename
                        except ValueError:
                            continue
            
            if not best_file:
                log.debug(f"No schema file found for appid {appid}")
                return None
            
            filepath = os.path.join(self.schema_dir, best_file)
            log.debug(f"Loading schema from {filepath}")
            
            # Load the binary schema file
            with open(filepath, "rb") as f:
                data = f.read()
            
            # Parse as KeyValues
            kvs = KeyValuesSystem()
            stream = BytesIO(data)
            kvs.deserialize(stream)
            
            # Create UserStatsSchema from the parsed data
            schema = UserStatsSchema(registry=kvs)
            return schema
            
        except Exception as e:
            log.error(f"Error loading schema for appid {appid}: {e}")
            return None
    
    def get_user_stats(self, steamid: int, appid: int) -> Optional[UserStats]:
        """
        Get user statistics for a specific user and game.
        First checks cache, then loads from database, then file, or creates new.
        """
        cache_key = (steamid, appid)
        
        with self.cache_lock:
            if cache_key in self.user_stats_cache:
                return self.user_stats_cache[cache_key]
            
            # Try to load user stats from database first
            user_stats = self._load_user_stats_from_db(steamid, appid)
            
            # If not in database, try to load from file
            if not user_stats:
                user_stats = self._load_user_stats_from_file(steamid, appid)
            
            # If still not found, create new user stats with schema
            if not user_stats:
                schema = self.get_schema(appid)
                if schema:
                    user_stats = UserStats(schema)
                    log.debug(f"Created new user stats for steamid {steamid}, appid {appid}")
                else:
                    log.warning(f"Cannot create user stats without schema for appid {appid}")
                    return None
            
            self.user_stats_cache[cache_key] = user_stats
            return user_stats
    
    def _load_user_stats_from_file(self, steamid: int, appid: int) -> Optional[UserStats]:
        """
        Load UserStats from binary file in files/GameStats/user_stats/
        """
        if not os.path.exists(self.user_stats_dir):
            log.debug(f"User stats directory not found: {self.user_stats_dir}")
            return None
        
        # Format: UserGameStats_{steamid}_{appid}.bin
        filename = f"UserGameStats_{steamid}_{appid}.bin"
        filepath = os.path.join(self.user_stats_dir, filename)
        
        if not os.path.exists(filepath):
            log.debug(f"User stats file not found: {filepath}")
            return None
        
        try:
            # Load the schema first
            schema = self.get_schema(appid)
            
            # Load user stats from file
            user_stats = UserStats.from_file(filepath)
            if schema:
                user_stats.setSchema(schema)
            
            log.debug(f"Loaded user stats from {filepath}")
            return user_stats
            
        except Exception as e:
            log.error(f"Error loading user stats from {filepath}: {e}")
            return None
    
    def store_user_stats(self, steamid: int, appid: int, user_stats: UserStats) -> bool:
        """
        Store/update user statistics to cache and persistence.
        """
        cache_key = (steamid, appid)
        
        with self.cache_lock:
            # Update cache
            self.user_stats_cache[cache_key] = user_stats
            
            # Persist to database if available
            if self.database:
                try:
                    self._persist_user_stats_to_db(steamid, appid, user_stats)
                except Exception as e:
                    log.error(f"Failed to persist stats to database: {e}")
                    # Continue anyway - cache is updated
            
            log.debug(f"Stored user stats for steamid {steamid}, appid {appid}")
            return True
    
    def update_user_stats(self, steamid: int, appid: int, stats_update: Dict[int, int], 
                         explicit_reset: bool, failed_validation_stats: Dict[int, int],
                         check_current_crc: int = 0) -> EResult:
        """
        Update user statistics with validation.
        """
        user_stats = self.get_user_stats(steamid, appid)
        if not user_stats:
            return EResult.Fail
        
        # Perform the update
        result = user_stats.updateStats(stats_update, explicit_reset, failed_validation_stats, check_current_crc)
        
        if result != EResult.Fail:
            # Store the updated stats
            self.store_user_stats(steamid, appid, user_stats)
        
        return EResult(result)
    
    def get_stats_crc(self, steamid: int, appid: int) -> int:
        """
        Get the current CRC for a user's stats.
        """
        user_stats = self.get_user_stats(steamid, appid)
        if user_stats:
            return user_stats.computeCrc()
        return 0
    
    def clear_cache(self):
        """Clear all cached data"""
        with self.cache_lock:
            self.schema_cache.clear()
            self.user_stats_cache.clear()
            log.info("Stats cache cleared")
    
    def _persist_user_stats_to_db(self, steamid: int, appid: int, user_stats: UserStats):
        """
        Persist user stats to database using cmdb functions.
        """
        # Persist cache metadata
        schema_version = user_stats.schema.getVersion() if user_stats.schema else None
        self.database.persist_user_stats_cache(
            steamid, appid, user_stats.crc, user_stats.pendingChanges, schema_version
        )
        
        # Persist stats data
        if user_stats.stats:
            self.database.persist_user_stats_data(steamid, appid, user_stats.stats)
        
        # Persist achievement data
        if user_stats.achievedAt:
            # Convert to the format expected by cmdb
            achievements_data = {}
            for stat_id, achieved_at in user_stats.achievedAt.items():
                achievements_data[stat_id] = {}
                for bit_pos in range(32):
                    if achieved_at.bit[bit_pos] != 0:
                        achievements_data[stat_id][bit_pos] = achieved_at.bit[bit_pos]
            
            if achievements_data:
                self.database.persist_user_achievements_data(steamid, appid, achievements_data)
        
        log.debug(f"Persisted stats to database for steamid {steamid}, appid {appid}")
    
    def _load_user_stats_from_db(self, steamid: int, appid: int) -> Optional[UserStats]:
        """
        Load user stats from database using cmdb functions.
        """
        if not self.database:
            return None
        
        try:
            # Check if we have stats in the database
            cache_data = self.database.get_user_stats_cache(steamid, appid)
            if not cache_data:
                return None
            
            # Load the schema
            schema = self.get_schema(appid)
            if not schema:
                log.warning(f"No schema available for appid {appid}")
                return None
            
            # Create UserStats object
            user_stats = UserStats(schema)
            user_stats.crc = cache_data['crc']
            user_stats.pendingChanges = cache_data['pending_changes']
            
            # Load stats data
            stats_data = self.database.get_user_stats_data(steamid, appid)
            user_stats.stats.update(stats_data)
            
            # Load achievement data
            from steam3.Types.userstats import AchievedAt
            achievements_data = self.database.get_user_achievements_data(steamid, appid)
            
            for stat_id, achievements in achievements_data.items():
                if stat_id not in user_stats.achievedAt:
                    user_stats.achievedAt[stat_id] = AchievedAt()
                
                for bit_pos, achieved_at in achievements.items():
                    user_stats.achievedAt[stat_id].bit[bit_pos] = achieved_at
            
            log.debug(f"Loaded stats from database for steamid {steamid}, appid {appid}")
            return user_stats
            
        except Exception as e:
            log.error(f"Error loading stats from database: {e}")
            return None