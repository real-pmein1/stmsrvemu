# steam3/Managers/JobManager/job.py
"""
Job - Represents a server operation that requires state.

Based on Valve's GCSDK job.h:
- Jobs persist state while waiting for responses from clients
- Jobs are identified by a unique JobID (GlobalID)
- Jobs can be paused waiting for network messages, timeouts, etc.
"""

import logging
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Optional, Any, Callable
from datetime import datetime

from steam3.Types.globalid import GlobalID, generate_globalid
from steam3.Managers.JobManager.jobtime import JobTime

if TYPE_CHECKING:
    from steam3.ClientManager.client import Client

log = logging.getLogger("JobManager")


class JobState(IntEnum):
    """State of a job in its lifecycle."""
    PENDING = auto()        # Job created but not started
    RUNNING = auto()        # Job is actively processing
    WAITING_MSG = auto()    # Job is waiting for a network message
    WAITING_TIME = auto()   # Job is waiting for a timer
    COMPLETED = auto()      # Job completed successfully
    FAILED = auto()         # Job failed
    TIMED_OUT = auto()      # Job timed out waiting for response


class JobPauseReason(IntEnum):
    """
    Reason why the current job has yielded (paused).

    Based on Valve's EJobPauseReason enum.
    """
    NONE = 0
    NOT_STARTED = auto()
    NETWORK_MSG = auto()      # Waiting for network message
    SLEEP_FOR_TIME = auto()   # Sleeping for a set duration
    WAITING_FOR_LOCK = auto() # Waiting for a lock
    YIELD = auto()            # Simple yield
    SQL = auto()              # Waiting for SQL query
    WORK_ITEM = auto()        # Waiting for work item


class JobMsgInfo:
    """
    Information used to route a message to a job.

    Based on Valve's JobMsgInfo_t struct.
    """
    K_GID_NIL = 0xFFFFFFFFFFFFFFFF  # -1 as unsigned 64-bit

    def __init__(self, emsg: int = 0, job_id_source: int = K_GID_NIL, job_id_target: int = K_GID_NIL):
        self.emsg = emsg
        self.job_id_source = job_id_source
        self.job_id_target = job_id_target

    def has_valid_target(self) -> bool:
        """Check if this has a valid target job ID."""
        return self.job_id_target != self.K_GID_NIL

    def has_valid_source(self) -> bool:
        """Check if this has a valid source job ID."""
        return self.job_id_source != self.K_GID_NIL

    def __repr__(self) -> str:
        return (f"JobMsgInfo(emsg={self.emsg}, "
                f"source={self.job_id_source:#x}, "
                f"target={self.job_id_target:#x})")


class Job:
    """
    A job is any server operation that requires state.

    Jobs are used for operations that need to pause waiting for responses
    from clients or other servers. The job object persists state while
    waiting, and incoming messages can reactivate the job.
    """

    # Default timeout for jobs (30 seconds)
    DEFAULT_TIMEOUT_SECONDS = 30.0

    # Number of heartbeats before timeout
    DEFAULT_HEARTBEATS_BEFORE_TIMEOUT = 3

    def __init__(
        self,
        job_id: Optional[int] = None,
        name: str = "UnnamedJob",
        client: Optional['Client'] = None,
        source_job_id: int = JobMsgInfo.K_GID_NIL,
        target_job_id: int = JobMsgInfo.K_GID_NIL,
        emsg: int = 0
    ):
        """
        Create a new Job.

        Args:
            job_id: Optional job ID. If not provided, one will be generated.
            name: Name of this job for debugging.
            client: The client this job is associated with.
            source_job_id: The source job ID from the request.
            target_job_id: The target job ID for the request.
            emsg: The EMsg type that created/will complete this job.
        """
        self._job_id = job_id if job_id is not None else generate_globalid()
        self._name = name
        self._client = client
        self._source_job_id = source_job_id
        self._target_job_id = target_job_id
        self._emsg = emsg

        self._state = JobState.PENDING
        self._pause_reason = JobPauseReason.NOT_STARTED
        self._pause_resource_name: Optional[str] = None

        # Timing information
        self._time_started = JobTime()
        self._time_switched = JobTime()  # Last time we paused or continued
        self._time_next_heartbeat = JobTime()
        self._timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS

        # Response data
        self._response_packet: Optional[Any] = None
        self._result: Optional[Any] = None

        # Callback for when job completes
        self._completion_callback: Optional[Callable[['Job'], None]] = None

        # Additional context data
        self._context: dict = {}

        log.debug(f"Created job {self._name} with ID {self._job_id:#x}")

    @property
    def job_id(self) -> int:
        """Get the unique job ID."""
        return self._job_id

    @property
    def name(self) -> str:
        """Get the job name."""
        return self._name

    @property
    def client(self) -> Optional['Client']:
        """Get the associated client."""
        return self._client

    @property
    def source_job_id(self) -> int:
        """Get the source job ID (from the request that created this job)."""
        return self._source_job_id

    @property
    def target_job_id(self) -> int:
        """Get the target job ID."""
        return self._target_job_id

    @property
    def emsg(self) -> int:
        """Get the EMsg type."""
        return self._emsg

    @property
    def state(self) -> JobState:
        """Get the current job state."""
        return self._state

    @property
    def pause_reason(self) -> JobPauseReason:
        """Get the reason for pause."""
        return self._pause_reason

    @property
    def response_packet(self) -> Optional[Any]:
        """Get the response packet if one has been received."""
        return self._response_packet

    @property
    def result(self) -> Optional[Any]:
        """Get the job result."""
        return self._result

    @property
    def context(self) -> dict:
        """Get the context data dictionary."""
        return self._context

    def set_timeout(self, seconds: float):
        """Set the timeout for this job."""
        self._timeout_seconds = seconds

    def get_timeout_seconds(self) -> float:
        """Get the timeout for this job."""
        return self._timeout_seconds

    def is_waiting(self) -> bool:
        """Check if job is waiting for something."""
        return self._state in (JobState.WAITING_MSG, JobState.WAITING_TIME)

    def is_complete(self) -> bool:
        """Check if job has completed (success, fail, or timeout)."""
        return self._state in (JobState.COMPLETED, JobState.FAILED, JobState.TIMED_OUT)

    def is_timed_out(self) -> bool:
        """Check if job has timed out."""
        return self._state == JobState.TIMED_OUT

    def get_elapsed_seconds(self) -> float:
        """Get seconds elapsed since job started."""
        return self._time_started.seconds_passed()

    def start(self):
        """Mark job as started/running."""
        self._state = JobState.RUNNING
        self._pause_reason = JobPauseReason.NONE
        self._time_started.set_to_current()
        self._time_switched.set_to_current()
        log.debug(f"Job {self._name} ({self._job_id:#x}) started")

    def wait_for_message(self, expected_emsg: int = 0, timeout_seconds: Optional[float] = None):
        """
        Mark this job as waiting for a network message.

        Args:
            expected_emsg: The EMsg we're expecting (0 = any)
            timeout_seconds: Optional custom timeout
        """
        self._state = JobState.WAITING_MSG
        self._pause_reason = JobPauseReason.NETWORK_MSG
        self._pause_resource_name = f"EMsg:{expected_emsg}" if expected_emsg else "Any message"
        self._time_switched.set_to_current()
        if timeout_seconds is not None:
            self._timeout_seconds = timeout_seconds
        log.debug(f"Job {self._name} ({self._job_id:#x}) waiting for message")

    def receive_message(self, packet: Any) -> bool:
        """
        Deliver a message to this waiting job.

        Args:
            packet: The received packet.

        Returns:
            True if message was accepted, False otherwise.
        """
        if self._state != JobState.WAITING_MSG:
            log.warning(f"Job {self._name} received message but not in WAITING_MSG state")
            return False

        self._response_packet = packet
        self._state = JobState.RUNNING
        self._pause_reason = JobPauseReason.NONE
        self._time_switched.set_to_current()
        log.debug(f"Job {self._name} ({self._job_id:#x}) received message")
        return True

    def complete(self, result: Any = None):
        """
        Mark job as completed successfully.

        Args:
            result: Optional result data.
        """
        self._state = JobState.COMPLETED
        self._pause_reason = JobPauseReason.NONE
        self._result = result
        self._time_switched.set_to_current()
        log.debug(f"Job {self._name} ({self._job_id:#x}) completed")

        if self._completion_callback:
            try:
                self._completion_callback(self)
            except Exception as e:
                log.error(f"Error in job completion callback: {e}")

    def fail(self, reason: str = "Unknown"):
        """
        Mark job as failed.

        Args:
            reason: Reason for failure.
        """
        self._state = JobState.FAILED
        self._pause_reason = JobPauseReason.NONE
        self._pause_resource_name = reason
        self._time_switched.set_to_current()
        log.warning(f"Job {self._name} ({self._job_id:#x}) failed: {reason}")

        if self._completion_callback:
            try:
                self._completion_callback(self)
            except Exception as e:
                log.error(f"Error in job completion callback: {e}")

    def timeout(self):
        """Mark job as timed out."""
        self._state = JobState.TIMED_OUT
        self._pause_reason = JobPauseReason.NONE
        self._time_switched.set_to_current()
        log.warning(f"Job {self._name} ({self._job_id:#x}) timed out after {self.get_elapsed_seconds():.2f}s")

        if self._completion_callback:
            try:
                self._completion_callback(self)
            except Exception as e:
                log.error(f"Error in job completion callback: {e}")

    def check_timeout(self) -> bool:
        """
        Check if this job has timed out.

        Returns:
            True if job timed out and was marked as such.
        """
        if not self.is_waiting():
            return False

        elapsed = self.get_elapsed_seconds()
        if elapsed >= self._timeout_seconds:
            self.timeout()
            return True
        return False

    def set_completion_callback(self, callback: Callable[['Job'], None]):
        """Set a callback to be called when job completes."""
        self._completion_callback = callback

    def __repr__(self) -> str:
        return (f"<Job {self._name} id={self._job_id:#x} "
                f"state={self._state.name} "
                f"source={self._source_job_id:#x} "
                f"elapsed={self.get_elapsed_seconds():.2f}s>")
