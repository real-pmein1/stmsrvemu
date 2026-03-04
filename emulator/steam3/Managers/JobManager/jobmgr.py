# steam3/Managers/JobManager/jobmgr.py
"""
JobManager - Tracks and routes messages to jobs.

Based on Valve's GCSDK jobmgr.h:
- Routes incoming messages to waiting jobs by targetJobID
- Creates new jobs for incoming requests
- Handles job timeouts
- Maintains job statistics
"""

import logging
import threading
import time
from typing import Dict, Optional, List, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from steam3.Types.globalid import generate_globalid
from steam3.Managers.JobManager.job import Job, JobState, JobPauseReason, JobMsgInfo
from steam3.Managers.JobManager.jobtime import JobTime

if TYPE_CHECKING:
    from steam3.ClientManager.client import Client

log = logging.getLogger("JobManager")


@dataclass
class JobStats:
    """Statistics about job execution."""
    jobs_current: int = 0
    jobs_total: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_timed_out: int = 0
    total_runtime_us: int = 0
    max_runtime_us: int = 0
    orphaned_messages: int = 0

    def __repr__(self) -> str:
        return (f"JobStats(current={self.jobs_current}, total={self.jobs_total}, "
                f"completed={self.jobs_completed}, failed={self.jobs_failed}, "
                f"timed_out={self.jobs_timed_out}, orphaned={self.orphaned_messages})")


@dataclass
class PendingResponse:
    """Tracks a pending response for a job."""
    job: Job
    source_job_id: int  # The sourceJobID from the request (becomes targetJobID in response)
    expected_emsg: int  # The EMsg we expect in response (0 = any)
    created_time: float = field(default_factory=time.time)
    timeout_seconds: float = 30.0

    def is_expired(self) -> bool:
        """Check if this pending response has expired."""
        return (time.time() - self.created_time) >= self.timeout_seconds


class JobManager:
    """
    Manages all jobs for a server instance.

    Thread-safe job tracking and message routing.
    """

    _instance: Optional['JobManager'] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        """Initialize the JobManager."""
        self._jobs: Dict[int, Job] = {}  # job_id -> Job
        self._pending_responses: Dict[int, PendingResponse] = {}  # source_job_id -> PendingResponse
        self._client_jobs: Dict[str, List[int]] = {}  # client_key -> [job_ids]

        self._lock = threading.RLock()
        self._stats = JobStats()
        self._next_job_id_fallback = 1

        # Background cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()

        # Job type handlers (emsg -> handler function)
        self._job_handlers: Dict[int, Callable] = {}

        log.info("JobManager initialized")

    @classmethod
    def get_instance(cls) -> 'JobManager':
        """Get the singleton JobManager instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = JobManager()
        return cls._instance

    def start_cleanup_thread(self, interval_seconds: float = 5.0):
        """Start the background cleanup thread."""
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            return

        self._shutdown.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            args=(interval_seconds,),
            daemon=True,
            name="JobManager-Cleanup"
        )
        self._cleanup_thread.start()
        log.info(f"JobManager cleanup thread started (interval={interval_seconds}s)")

    def stop_cleanup_thread(self):
        """Stop the background cleanup thread."""
        self._shutdown.set()
        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=5.0)
            self._cleanup_thread = None
        log.info("JobManager cleanup thread stopped")

    def _cleanup_loop(self, interval_seconds: float):
        """Background loop for cleaning up expired jobs."""
        while not self._shutdown.wait(timeout=interval_seconds):
            try:
                self.cleanup_expired_jobs()
                # Update job time
                JobTime.update_job_time(int(interval_seconds * 1_000_000))
            except Exception as e:
                log.error(f"Error in cleanup loop: {e}")

    def generate_job_id(self) -> int:
        """Generate a new unique job ID."""
        try:
            return generate_globalid()
        except Exception as e:
            log.warning(f"Failed to generate GlobalID: {e}, using fallback")
            with self._lock:
                self._next_job_id_fallback += 1
                return self._next_job_id_fallback

    def create_job(
        self,
        name: str,
        client: Optional['Client'] = None,
        source_job_id: int = JobMsgInfo.K_GID_NIL,
        target_job_id: int = JobMsgInfo.K_GID_NIL,
        emsg: int = 0,
        timeout_seconds: float = 30.0
    ) -> Job:
        """
        Create and register a new job.

        Args:
            name: Name of the job for debugging.
            client: The client this job is associated with.
            source_job_id: The source job ID from the incoming request.
            target_job_id: The target job ID (usually -1 for new jobs).
            emsg: The EMsg type.
            timeout_seconds: Timeout for this job.

        Returns:
            The created Job object.
        """
        job_id = self.generate_job_id()

        job = Job(
            job_id=job_id,
            name=name,
            client=client,
            source_job_id=source_job_id,
            target_job_id=target_job_id,
            emsg=emsg
        )
        job.set_timeout(timeout_seconds)

        with self._lock:
            self._jobs[job_id] = job
            self._stats.jobs_current += 1
            self._stats.jobs_total += 1

            # Track by client
            if client is not None:
                client_key = str(client.ip_port)
                if client_key not in self._client_jobs:
                    self._client_jobs[client_key] = []
                self._client_jobs[client_key].append(job_id)

        log.debug(f"Created job: {job}")
        return job

    def register_pending_response(
        self,
        job: Job,
        expected_emsg: int = 0,
        timeout_seconds: float = 30.0
    ):
        """
        Register a job as waiting for a response.

        The response will be routed based on the job's source_job_id
        matching the response's targetJobID.

        Args:
            job: The job waiting for a response.
            expected_emsg: The EMsg expected in the response.
            timeout_seconds: Timeout for waiting.
        """
        if job.source_job_id == JobMsgInfo.K_GID_NIL:
            log.warning(f"Cannot register pending response for job {job.name} - no source_job_id")
            return

        pending = PendingResponse(
            job=job,
            source_job_id=job.source_job_id,
            expected_emsg=expected_emsg,
            timeout_seconds=timeout_seconds
        )

        with self._lock:
            self._pending_responses[job.source_job_id] = pending

        job.wait_for_message(expected_emsg, timeout_seconds)
        log.debug(f"Registered pending response for job {job.name}, source_job_id={job.source_job_id:#x}")

    def route_message_to_job(
        self,
        target_job_id: int,
        packet: Any,
        emsg: int = 0
    ) -> bool:
        """
        Route an incoming message to a waiting job.

        Args:
            target_job_id: The targetJobID from the incoming message.
            packet: The received packet.
            emsg: The EMsg of the received packet.

        Returns:
            True if message was routed to a job, False if orphaned.
        """
        if target_job_id == JobMsgInfo.K_GID_NIL:
            # No target job ID - this is a new request, not a response
            return False

        with self._lock:
            pending = self._pending_responses.get(target_job_id)
            if pending is None:
                log.debug(f"No pending job for targetJobID {target_job_id:#x}, orphaned message")
                self._stats.orphaned_messages += 1
                return False

            job = pending.job

            # Check if expected EMsg matches (if specified)
            if pending.expected_emsg != 0 and emsg != 0:
                if emsg != pending.expected_emsg:
                    log.warning(f"Job {job.name} expected EMsg {pending.expected_emsg} but got {emsg}")
                    # Still deliver it

            # Remove from pending
            del self._pending_responses[target_job_id]

        # Deliver message to job
        if job.receive_message(packet):
            log.debug(f"Routed message (EMsg={emsg}) to job {job.name}")
            return True

        return False

    def get_job(self, job_id: int) -> Optional[Job]:
        """Get a job by its ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_by_source_id(self, source_job_id: int) -> Optional[Job]:
        """Get a job by its source job ID."""
        with self._lock:
            pending = self._pending_responses.get(source_job_id)
            if pending:
                return pending.job
        return None

    def complete_job(self, job_id: int, result: Any = None):
        """
        Mark a job as completed and remove it.

        Args:
            job_id: The job ID.
            result: Optional result data.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return

            job.complete(result)
            self._stats.jobs_completed += 1
            self._remove_job_locked(job_id)

    def fail_job(self, job_id: int, reason: str = "Unknown"):
        """
        Mark a job as failed and remove it.

        Args:
            job_id: The job ID.
            reason: Reason for failure.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return

            job.fail(reason)
            self._stats.jobs_failed += 1
            self._remove_job_locked(job_id)

    def _remove_job_locked(self, job_id: int):
        """Remove a job (must be called with lock held)."""
        job = self._jobs.pop(job_id, None)
        if job is None:
            return

        self._stats.jobs_current -= 1

        # Remove from pending responses
        if job.source_job_id in self._pending_responses:
            del self._pending_responses[job.source_job_id]

        # Remove from client tracking
        if job.client is not None:
            client_key = str(job.client.ip_port)
            if client_key in self._client_jobs:
                try:
                    self._client_jobs[client_key].remove(job_id)
                except ValueError:
                    pass

    def cleanup_expired_jobs(self) -> int:
        """
        Clean up expired/timed-out jobs.

        Returns:
            Number of jobs cleaned up.
        """
        cleaned = 0
        current_time = time.time()

        with self._lock:
            # Check pending responses for expiration
            expired_source_ids = []
            for source_id, pending in self._pending_responses.items():
                if pending.is_expired():
                    expired_source_ids.append(source_id)

            for source_id in expired_source_ids:
                pending = self._pending_responses.pop(source_id, None)
                if pending:
                    pending.job.timeout()
                    self._stats.jobs_timed_out += 1
                    self._remove_job_locked(pending.job.job_id)
                    cleaned += 1
                    log.debug(f"Cleaned up expired job: {pending.job.name}")

            # Also check all jobs for timeout
            timed_out_ids = []
            for job_id, job in self._jobs.items():
                if job.check_timeout():
                    timed_out_ids.append(job_id)

            for job_id in timed_out_ids:
                self._stats.jobs_timed_out += 1
                self._remove_job_locked(job_id)
                cleaned += 1

        if cleaned > 0:
            log.debug(f"Cleaned up {cleaned} expired jobs")

        return cleaned

    def cleanup_client_jobs(self, client: 'Client'):
        """
        Clean up all jobs for a disconnected client.

        Args:
            client: The disconnected client.
        """
        client_key = str(client.ip_port)

        with self._lock:
            job_ids = self._client_jobs.pop(client_key, [])
            for job_id in job_ids:
                job = self._jobs.get(job_id)
                if job:
                    job.fail("Client disconnected")
                    self._stats.jobs_failed += 1
                    self._remove_job_locked(job_id)

        if job_ids:
            log.debug(f"Cleaned up {len(job_ids)} jobs for disconnected client {client_key}")

    def get_stats(self) -> JobStats:
        """Get current job statistics."""
        with self._lock:
            return JobStats(
                jobs_current=self._stats.jobs_current,
                jobs_total=self._stats.jobs_total,
                jobs_completed=self._stats.jobs_completed,
                jobs_failed=self._stats.jobs_failed,
                jobs_timed_out=self._stats.jobs_timed_out,
                total_runtime_us=self._stats.total_runtime_us,
                max_runtime_us=self._stats.max_runtime_us,
                orphaned_messages=self._stats.orphaned_messages
            )

    def get_job_count(self) -> int:
        """Get current number of active jobs."""
        with self._lock:
            return len(self._jobs)

    def get_pending_count(self) -> int:
        """Get number of jobs waiting for responses."""
        with self._lock:
            return len(self._pending_responses)

    def list_jobs(self, max_count: int = 100) -> List[Job]:
        """
        List current jobs.

        Args:
            max_count: Maximum number of jobs to return.

        Returns:
            List of Job objects.
        """
        with self._lock:
            return list(self._jobs.values())[:max_count]

    def dump_jobs(self, include_pending: bool = True) -> str:
        """
        Dump job information for debugging.

        Returns:
            String with job dump information.
        """
        lines = []
        lines.append("=== JobManager Dump ===")
        lines.append(f"Stats: {self._stats}")

        with self._lock:
            lines.append(f"\nActive Jobs ({len(self._jobs)}):")
            for job_id, job in self._jobs.items():
                lines.append(f"  {job}")

            if include_pending:
                lines.append(f"\nPending Responses ({len(self._pending_responses)}):")
                for source_id, pending in self._pending_responses.items():
                    expired = "EXPIRED" if pending.is_expired() else ""
                    lines.append(f"  source_id={source_id:#x} job={pending.job.name} "
                               f"expected_emsg={pending.expected_emsg} {expired}")

        lines.append("=== End JobManager Dump ===")
        return "\n".join(lines)


# Module-level singleton accessor
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get the global JobManager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager.get_instance()
    return _job_manager
