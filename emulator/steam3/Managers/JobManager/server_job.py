# steam3/Managers/JobManager/server_job.py
"""
ServerJob - Long-running server operations with automatic job routing.

This module provides a ServerJob class modeled after TinServer's CMServerJob.
ServerJobs are used for operations that:
  - Take significant time to complete (async I/O, database queries, etc.)
  - Need to send multiple responses to the same request
  - Should be tracked and cleaned up on client disconnect

Unlike synchronous handlers, ServerJobs run in their own thread or coroutine
and must explicitly manage their lifecycle.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Optional, Any, Callable, List

from steam3.Managers.JobManager.job_context import JobContext, K_JOB_ID_NONE, create_job_context_from_header
from steam3.Types.globalid import generate_globalid

if TYPE_CHECKING:
    from steam3.ClientManager.client import Client
    from steam3.cm_packet_utils import CMPacket

log = logging.getLogger("ServerJob")


class ServerJobState(IntEnum):
    """State of a server job in its lifecycle."""
    CREATED = auto()      # Job created but not started
    RUNNING = auto()      # Job is actively executing
    PAUSED = auto()       # Job is paused (e.g., waiting for I/O)
    COMPLETING = auto()   # Job is finishing up
    COMPLETED = auto()    # Job completed successfully
    FAILED = auto()       # Job failed
    CANCELLED = auto()    # Job was cancelled (e.g., client disconnected)


class ServerJob:
    """
    A long-running server operation with automatic job ID routing.

    ServerJob wraps a JobContext and provides:
      - Automatic targetJobID setting on all responses
      - Thread-safe response sending
      - Client disconnect handling
      - Lifecycle management and cleanup

    This is modeled after TinServer's CMServerJob class.

    Usage:
        def handle_LongRunningRequest(cmserver_obj, packet, client_obj):
            # Create a server job from the request
            job = ServerJob.from_request(packet, client_obj, name="DataFetch")

            # Run the job (in same thread or spawn new thread)
            def do_work():
                # ... do async work ...
                response = job.create_response(EMsg.SomeResponse)
                response.data = result_data
                job.send_response(response)

                # Send more responses if needed
                for chunk in data_chunks:
                    chunk_response = job.create_response(EMsg.DataChunk)
                    chunk_response.data = chunk
                    if not job.send_response(chunk_response):
                        break  # Client disconnected

                job.complete()

            # Run in thread for async operation
            job.run_threaded(do_work)

            return -1  # No immediate response
    """

    def __init__(
        self,
        context: JobContext,
        name: str = "ServerJob",
        cmserver: Any = None
    ):
        """
        Create a new ServerJob.

        Args:
            context: The JobContext for this request/response exchange.
            name: Name of this job for logging/debugging.
            cmserver: The CM server object (for sending responses).
        """
        self._context = context
        self._name = name
        self._cmserver = cmserver
        self._job_id = generate_globalid()
        self._state = ServerJobState.CREATED
        self._created_time = time.time()

        # Thread management
        self._thread: Optional[threading.Thread] = None
        self._cancelled = threading.Event()
        self._lock = threading.Lock()

        # Response tracking
        self._responses_sent = 0
        self._last_send_time = 0.0

        # Error tracking
        self._error: Optional[Exception] = None
        self._error_message: str = ""

        # Register with client for cleanup on disconnect
        if context.client:
            self._register_with_client()

        log.debug(f"ServerJob '{name}' created: job_id={self._job_id:#x}, "
                 f"source_job_id={context.source_job_id:#x}")

    @classmethod
    def from_request(
        cls,
        packet: 'CMPacket',
        client_obj: 'Client',
        name: str = "ServerJob",
        cmserver: Any = None
    ) -> 'ServerJob':
        """
        Create a ServerJob from an incoming request packet.

        This is the preferred factory method for creating ServerJobs.

        Args:
            packet: The incoming CMPacket
            client_obj: The client that sent the request
            name: Name of this job for logging
            cmserver: The CM server object

        Returns:
            A new ServerJob ready for processing
        """
        # Create job context from the request header
        request_header = packet.CMRequest
        context = create_job_context_from_header(request_header, client_obj)

        # Use cmserver from client if not provided
        if cmserver is None and hasattr(client_obj, 'objCMServer'):
            cmserver = client_obj.objCMServer

        return cls(context=context, name=name, cmserver=cmserver)

    # === Properties ===

    @property
    def job_id(self) -> int:
        """Get the internal job ID."""
        return self._job_id

    @property
    def source_job_id(self) -> int:
        """Get the client's source job ID (becomes targetJobID in responses)."""
        return self._context.source_job_id

    @property
    def name(self) -> str:
        """Get the job name."""
        return self._name

    @property
    def client(self) -> Optional['Client']:
        """Get the client this job belongs to."""
        return self._context.client

    @property
    def state(self) -> ServerJobState:
        """Get the current job state."""
        return self._state

    @property
    def context(self) -> JobContext:
        """Get the underlying JobContext."""
        return self._context

    @property
    def is_cancelled(self) -> bool:
        """Check if job has been cancelled."""
        return self._cancelled.is_set()

    @property
    def responses_sent(self) -> int:
        """Get count of responses sent."""
        return self._responses_sent

    # === Response Methods ===

    def create_response(self, emsg: int, response_class=None):
        """
        Create a response with correct job routing.

        The response will have targetJobID set to the client's sourceJobID,
        enabling proper routing on the client side.

        Args:
            emsg: The EMsg for the response
            response_class: Optional response class (defaults to CMResponse)

        Returns:
            A response object with job routing configured
        """
        return self._context.create_response(emsg, response_class)

    def send_response(self, response, priority: int = 1) -> bool:
        """
        Send a response to the client.

        This method:
          - Sets targetJobID to the correct value
          - Sends via the CM server
          - Tracks send count
          - Returns False if client disconnected

        Args:
            response: The response object to send
            priority: Send priority (default 1)

        Returns:
            True if sent successfully, False if cancelled or client gone
        """
        if self.is_cancelled:
            log.debug(f"ServerJob '{self._name}' send cancelled - client disconnected")
            return False

        if not self._cmserver:
            log.error(f"ServerJob '{self._name}' has no cmserver to send response")
            return False

        # Ensure job routing is applied
        self._context.apply_to_response(response)

        try:
            with self._lock:
                # Serialize the response if needed
                if hasattr(response, 'serialize') and not getattr(response, 'is_serialized', False):
                    response.serialize()

                # Send via CM server
                self._cmserver.sendReply(self.client, [response])

                self._responses_sent += 1
                self._last_send_time = time.time()

                log.debug(f"ServerJob '{self._name}' sent response #{self._responses_sent}")
                return True

        except Exception as e:
            log.error(f"ServerJob '{self._name}' send failed: {e}")
            return False

    def send_multi_response(self, multi_msg) -> bool:
        """
        Send a MultiMsg response containing multiple messages.

        Args:
            multi_msg: A MultiMsg containing multiple response messages

        Returns:
            True if sent successfully, False otherwise
        """
        if self.is_cancelled:
            return False

        # Apply job routing to the multi message
        if hasattr(multi_msg, 'targetJobID'):
            multi_msg.targetJobID = self._context.source_job_id

        return self.send_response(multi_msg)

    # === Lifecycle Methods ===

    def start(self):
        """Mark job as started/running."""
        self._state = ServerJobState.RUNNING
        self._context.mark_processing(self._name)
        log.debug(f"ServerJob '{self._name}' started")

    def pause(self):
        """Mark job as paused (waiting for I/O, etc.)."""
        self._state = ServerJobState.PAUSED

    def resume(self):
        """Resume job from paused state."""
        if self._state == ServerJobState.PAUSED:
            self._state = ServerJobState.RUNNING

    def complete(self, result: Any = None):
        """
        Mark job as completed successfully.

        Args:
            result: Optional result data
        """
        self._state = ServerJobState.COMPLETED
        self._context.mark_completed()
        self._unregister_from_client()

        elapsed = time.time() - self._created_time
        log.debug(f"ServerJob '{self._name}' completed: "
                 f"responses={self._responses_sent}, elapsed={elapsed:.3f}s")

    def fail(self, error: Optional[Exception] = None, message: str = ""):
        """
        Mark job as failed.

        Args:
            error: Optional exception that caused failure
            message: Error message
        """
        self._state = ServerJobState.FAILED
        self._error = error
        self._error_message = message or str(error) if error else "Unknown error"
        self._context.mark_failed(self._error_message)
        self._unregister_from_client()

        log.warning(f"ServerJob '{self._name}' failed: {self._error_message}")

    def cancel(self):
        """
        Cancel the job (e.g., client disconnected).

        This sets the cancelled flag which will cause send_response() to
        return False, allowing the job thread to exit gracefully.
        """
        self._cancelled.set()
        self._state = ServerJobState.CANCELLED
        self._unregister_from_client()
        log.debug(f"ServerJob '{self._name}' cancelled")

    # === Thread Management ===

    def run_threaded(self, work_func: Callable[[], None], daemon: bool = True):
        """
        Run the job work function in a separate thread.

        Args:
            work_func: The function to execute (takes no arguments)
            daemon: If True, thread is a daemon (dies with main thread)
        """
        self.start()

        def thread_wrapper():
            try:
                work_func()
                if self._state == ServerJobState.RUNNING:
                    self.complete()
            except Exception as e:
                self.fail(e)
                log.error(f"ServerJob '{self._name}' thread error: {e}")

        self._thread = threading.Thread(
            target=thread_wrapper,
            name=f"ServerJob_{self._name}_{self._job_id:#x}",
            daemon=daemon
        )
        self._thread.start()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the job thread to complete.

        Args:
            timeout: Maximum time to wait in seconds (None = forever)

        Returns:
            True if thread completed, False if timeout
        """
        if self._thread is None:
            return True

        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    # === Client Registration ===

    def _register_with_client(self):
        """Register this job with the client for cleanup on disconnect."""
        client = self._context.client
        if client is None:
            return

        # Add to client's active jobs list
        if not hasattr(client, '_active_server_jobs'):
            client._active_server_jobs = {}
        client._active_server_jobs[self._job_id] = self

    def _unregister_from_client(self):
        """Remove this job from the client's active jobs."""
        client = self._context.client
        if client is None:
            return

        if hasattr(client, '_active_server_jobs'):
            client._active_server_jobs.pop(self._job_id, None)

    # === Static Cleanup Methods ===

    @staticmethod
    def cancel_client_jobs(client: 'Client'):
        """
        Cancel all active ServerJobs for a client.

        Called when a client disconnects to clean up any pending jobs.

        Args:
            client: The client that disconnected
        """
        if not hasattr(client, '_active_server_jobs'):
            return

        jobs = list(client._active_server_jobs.values())
        for job in jobs:
            job.cancel()

        client._active_server_jobs.clear()

        if jobs:
            log.debug(f"Cancelled {len(jobs)} ServerJob(s) for disconnected client")

    def __repr__(self) -> str:
        return (f"ServerJob(name='{self._name}', job_id={self._job_id:#x}, "
               f"state={self._state.name}, responses={self._responses_sent})")
