from datetime import datetime, timedelta
import logging
import os
import threading

from steam3.utilities import BitVector64

log = logging.getLogger("GlobalID")


class GlobalID:
    def __init__(self, gid=0xFFFFFFFFFFFFFFFF):
        self.gidBits = BitVector64(gid)

    @property
    def SequentialCount(self):
        return self.gidBits[0, 0xFFFFF]

    @SequentialCount.setter
    def SequentialCount(self, value):
        self.gidBits[0, 0xFFFFF] = value

    @property
    def StartTime(self):
        start_time = self.gidBits[20, 0x3FFFFFFF]
        return datetime(2005, 1, 1) + timedelta(seconds=start_time)

    @StartTime.setter
    def StartTime(self, value):
        start_time = int((value - datetime(2005, 1, 1)).total_seconds())
        self.gidBits[20, 0x3FFFFFFF] = start_time

    @property
    def ProcessID(self):
        return self.gidBits[50, 0xF]

    @ProcessID.setter
    def ProcessID(self, value):
        self.gidBits[50, 0xF] = value

    @property
    def BoxID(self):
        return self.gidBits[54, 0x3FF]

    @BoxID.setter
    def BoxID(self, value):
        self.gidBits[54, 0x3FF] = value

    @property
    def Value(self):
        return self.gidBits.Data

    @Value.setter
    def Value(self, value):
        self.gidBits.Data = value

    def __eq__(self, other):
        if not isinstance(other, GlobalID):
            return False
        return self.gidBits.Data == other.gidBits.Data

    def __hash__(self):
        return hash(self.gidBits.Data)

    def __str__(self):
        return str(self.Value)

    @staticmethod
    def from_ulong(gid):
        return GlobalID(gid)

    def __int__(self):
        return self.gidBits.Data

# Implicit conversion methods
def ulong_to_globalid(gid):
    return GlobalID(gid)

def globalid_to_ulong(globalid):
    return int(globalid)

# Sealed UGCHandle class derived from GlobalID
class UGCHandle(GlobalID):
    def __init__(self, ugcId=0xFFFFFFFFFFFFFFFF):
        super().__init__(ugcId)


# Reference epoch for GlobalID start times
GLOBALID_EPOCH = datetime(2005, 1, 1)


class GlobalIDGenerator:
    """
    Thread-safe generator for GlobalIDs using Valve's format.

    GlobalID Structure (64-bit):
        - Bits 0-19 (20 bits): Sequential count (0-1048575)
        - Bits 20-49 (30 bits): Start time in seconds since 2005-01-01
        - Bits 50-53 (4 bits): Process ID (0-15)
        - Bits 54-63 (10 bits): Box ID (0-1023)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._sequence_lock = threading.Lock()
        self._last_start_time = 0
        self._sequence_count = 0
        self._box_id = None
        self._process_id = os.getpid() & 0xF  # 4 bits, masked to 0-15
        self._db_available = None  # None = not checked, True/False = checked
        self._initialized = True

    def _get_box_id(self) -> int:
        """Get the box ID from config, caching the value."""
        if self._box_id is None:
            from config import get_config
            config = get_config()
            self._box_id = int(config.get('cmboxid', '1')) & 0x3FF  # 10 bits, masked to 0-1023
            log.debug(f"GlobalIDGenerator using box_id={self._box_id}")
        return self._box_id

    def _get_db_session(self):
        """Get a new database session for sequence persistence."""
        from utilities.database.base_dbdriver import GlobalIDSequence
        from utilities.database.dbengine import DatabaseDriver
        try:
            session = DatabaseDriver.get_session()()
            return session, GlobalIDSequence
        except Exception as e:
            log.debug(f"Could not get DB session: {e}")
            return None, GlobalIDSequence

    def _load_sequence_from_db(self, box_id: int, current_start_time: int):
        """Load the sequence counter from database, updating if start_time changed."""
        session = None
        try:
            session, GlobalIDSequence = self._get_db_session()
            if session is None:
                return self._sequence_count

            record = session.query(GlobalIDSequence).filter_by(box_id=box_id).first()

            if record is None:
                # Create new record
                record = GlobalIDSequence(
                    box_id=box_id,
                    last_start_time=current_start_time,
                    sequence_count=0
                )
                session.add(record)
                session.commit()
                return 0

            if record.last_start_time != current_start_time:
                # Start time changed, reset sequence
                record.last_start_time = current_start_time
                record.sequence_count = 0
                session.commit()
                return 0

            return record.sequence_count

        except Exception as e:
            log.debug(f"Failed to load sequence from DB: {e}, using in-memory fallback")
            return self._sequence_count
        finally:
            if session is not None:
                try:
                    session.close()
                except:
                    pass

    def _save_sequence_to_db(self, box_id: int, start_time: int, sequence: int):
        """Save the sequence counter to database."""
        session = None
        try:
            session, GlobalIDSequence = self._get_db_session()
            if session is None:
                return

            record = session.query(GlobalIDSequence).filter_by(box_id=box_id).first()
            if record:
                record.last_start_time = start_time
                record.sequence_count = sequence
                session.commit()
        except Exception as e:
            log.debug(f"Failed to save sequence to DB: {e}")
        finally:
            if session is not None:
                try:
                    session.close()
                except:
                    pass

    def generate(self, start_time: datetime = None) -> int:
        """
        Generate a new GlobalID.

        Args:
            start_time: Optional datetime for the GlobalID. Defaults to now.

        Returns:
            A 64-bit GlobalID integer value.
        """
        if start_time is None:
            start_time = datetime.now()

        # Calculate seconds since epoch
        start_time_seconds = int((start_time - GLOBALID_EPOCH).total_seconds()) & 0x3FFFFFFF

        box_id = self._get_box_id()

        with self._sequence_lock:
            # Check if start_time changed
            if start_time_seconds != self._last_start_time:
                # Load from DB to get current state
                self._sequence_count = self._load_sequence_from_db(box_id, start_time_seconds)
                self._last_start_time = start_time_seconds

            # Get current sequence and increment
            sequence = self._sequence_count & 0xFFFFF  # 20 bits
            self._sequence_count += 1

            # Persist to database
            self._save_sequence_to_db(box_id, start_time_seconds, self._sequence_count)

        # Build the GlobalID using bit packing
        # Bits: [63-54: BoxID][53-50: ProcessID][49-20: StartTime][19-0: Sequence]
        gid = (
            (box_id & 0x3FF) << 54 |
            (self._process_id & 0xF) << 50 |
            (start_time_seconds & 0x3FFFFFFF) << 20 |
            (sequence & 0xFFFFF)
        )

        log.debug(f"Generated GlobalID: {gid} (box={box_id}, proc={self._process_id}, "
                  f"time={start_time_seconds}, seq={sequence})")

        return gid

    def generate_globalid(self, start_time: datetime = None) -> GlobalID:
        """
        Generate a new GlobalID object.

        Args:
            start_time: Optional datetime for the GlobalID. Defaults to now.

        Returns:
            A GlobalID object.
        """
        return GlobalID(self.generate(start_time))


# Singleton instance for easy access
_generator = None


def get_globalid_generator() -> GlobalIDGenerator:
    """Get the singleton GlobalIDGenerator instance."""
    global _generator
    if _generator is None:
        _generator = GlobalIDGenerator()
    return _generator


def generate_globalid(start_time: datetime = None) -> int:
    """
    Convenience function to generate a new GlobalID.

    Args:
        start_time: Optional datetime for the GlobalID. Defaults to now.

    Returns:
        A 64-bit GlobalID integer value.
    """
    return get_globalid_generator().generate(start_time)


"""# Example usage
gid = GlobalID(123456789)
print(gid)
print(gid.Value)
gid.SequentialCount = 12345
print(gid.SequentialCount)
gid.StartTime = datetime(2022, 1, 1)
print(gid.StartTime)
gid.ProcessID = 10
print(gid.ProcessID)
gid.BoxID = 20
print(gid.BoxID)
print(gid == GlobalID(123456789))

ugc_handle = UGCHandle(987654321)
print(ugc_handle)
print(ugc_handle.Value)"""