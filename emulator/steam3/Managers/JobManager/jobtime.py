# steam3/Managers/JobManager/jobtime.py
"""
JobTime - Encapsulates the job system's version of time.

Based on Valve's GCSDK jobtime.h:
- Provides 1 microsecond resolution
- Time pauses when debugger is attached (simulated here)
- Used for job timeouts and scheduling

This is NOT wall clock time; it's a monotonic time source for job management.
"""

import time
import threading
from datetime import datetime


class JobTime:
    """
    Job time class for tracking job durations and timeouts.

    Similar to Valve's CJobTime but adapted for Python.
    Uses monotonic time to avoid issues with system clock changes.
    """

    # Class-level current time, updated each frame/tick
    _current_time_us: int = 0
    _lock = threading.Lock()

    def __init__(self):
        """Initialize with current job time."""
        self._time_us: int = JobTime.get_current_time_us()

    @classmethod
    def get_current_time_us(cls) -> int:
        """Get the current job time in microseconds."""
        with cls._lock:
            return cls._current_time_us

    @classmethod
    def update_job_time(cls, microseconds_per_frame: int = 16667):
        """
        Update the current job time.

        Should be called once per server tick/frame.
        Default is ~60fps (16.667ms per frame).
        """
        with cls._lock:
            cls._current_time_us += microseconds_per_frame

    @classmethod
    def set_current_time(cls, time_us: int):
        """Set the current job time (for testing or initialization)."""
        with cls._lock:
            cls._current_time_us = time_us

    @classmethod
    def initialize_from_wall_clock(cls):
        """Initialize job time from current wall clock."""
        # Convert current time to microseconds since a reference point
        # Using time.perf_counter_ns() for high precision monotonic time
        cls._current_time_us = time.perf_counter_ns() // 1000

    def set_to_current(self):
        """Set this JobTime to the current job time."""
        self._time_us = JobTime.get_current_time_us()

    def set_from_offset(self, offset_us: int):
        """Set this JobTime to current time plus an offset."""
        self._time_us = JobTime.get_current_time_us() + offset_us

    @property
    def time_us(self) -> int:
        """Get the time value in microseconds."""
        return self._time_us

    @time_us.setter
    def time_us(self, value: int):
        """Set the time value in microseconds."""
        self._time_us = value

    def microseconds_passed(self) -> int:
        """
        Get microseconds elapsed since this JobTime was set.

        Returns:
            Positive value if time has passed, negative if in the future.
        """
        return JobTime.get_current_time_us() - self._time_us

    def seconds_passed(self) -> float:
        """Get seconds elapsed since this JobTime was set."""
        return self.microseconds_passed() / 1_000_000.0

    def has_passed(self) -> bool:
        """Check if this JobTime has passed (is in the past)."""
        return self.microseconds_passed() >= 0

    def is_in_future(self) -> bool:
        """Check if this JobTime is in the future."""
        return self.microseconds_passed() < 0

    def add_microseconds(self, us: int):
        """Add microseconds to this JobTime."""
        self._time_us += us

    def add_milliseconds(self, ms: int):
        """Add milliseconds to this JobTime."""
        self._time_us += ms * 1000

    def add_seconds(self, seconds: float):
        """Add seconds to this JobTime."""
        self._time_us += int(seconds * 1_000_000)

    def __eq__(self, other: 'JobTime') -> bool:
        if not isinstance(other, JobTime):
            return False
        return self._time_us == other._time_us

    def __lt__(self, other: 'JobTime') -> bool:
        if not isinstance(other, JobTime):
            return NotImplemented
        return self._time_us < other._time_us

    def __le__(self, other: 'JobTime') -> bool:
        if not isinstance(other, JobTime):
            return NotImplemented
        return self._time_us <= other._time_us

    def __gt__(self, other: 'JobTime') -> bool:
        if not isinstance(other, JobTime):
            return NotImplemented
        return self._time_us > other._time_us

    def __ge__(self, other: 'JobTime') -> bool:
        if not isinstance(other, JobTime):
            return NotImplemented
        return self._time_us >= other._time_us

    def __repr__(self) -> str:
        return f"JobTime({self._time_us}us, passed={self.microseconds_passed()}us)"


# Constants
K_JOB_TIME_MAX_FUTURE = 0xFFFFFFFFFFFFFFFF  # Maximum future time value


# Initialize job time from wall clock on module load
JobTime.initialize_from_wall_clock()
