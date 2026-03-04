# steam3/Managers/JobManager/job_context.py
"""
JobContext - Request/Response context for Steam CM message routing.

This module provides the core job context system for tracking request/response
pairs and ensuring correct job ID routing. Based on TinServer's approach where
job IDs flow explicitly through the code.

Key concept: When a client sends a request with sourceJobID=X, our response
MUST have targetJobID=X so the client's CJobMgr can route it to the waiting job.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Optional, Any, Dict

from steam3.Types.globalid import generate_globalid

if TYPE_CHECKING:
    from steam3.ClientManager.client import Client
    from steam3.Types.emsg import EMsg

log = logging.getLogger("JobContext")


# Constant for "no job ID" - matches Valve's k_GIDNil
K_JOB_ID_NONE = 0xFFFFFFFFFFFFFFFF  # -1 as unsigned 64-bit


class JobContextState(IntEnum):
    """State of a job context in its lifecycle."""
    CREATED = auto()      # Just created, not yet processed
    PROCESSING = auto()   # Handler is processing the request
    RESPONDING = auto()   # Response(s) being sent
    COMPLETED = auto()    # All responses sent
    FAILED = auto()       # Error occurred
    TIMED_OUT = auto()    # Timed out waiting


@dataclass
class JobContext:
    """
    Context for a single request/response exchange.

    This encapsulates all the information needed to correctly route responses
    back to a client's waiting job. It follows TinServer's pattern of explicit
    job ID propagation.

    Attributes:
        source_job_id: The client's sourceJobID from the request. This becomes
                      targetJobID in our response (the key routing field).
        target_job_id: The client's targetJobID from the request (usually -1 for
                      new requests, or our job ID if this is a response to us).
        client: The client object this context belongs to.
        request_emsg: The EMsg type of the incoming request.
        internal_job_id: Our internal tracking ID (not sent to client).
        created_time: When this context was created.
        state: Current state of the job context.
        responses_sent: Count of responses sent using this context.
    """
    source_job_id: int = K_JOB_ID_NONE
    target_job_id: int = K_JOB_ID_NONE
    client: Optional['Client'] = None
    request_emsg: int = 0
    internal_job_id: int = field(default_factory=generate_globalid)
    created_time: float = field(default_factory=time.time)
    state: JobContextState = JobContextState.CREATED
    responses_sent: int = 0

    # Additional metadata for debugging
    request_header: Any = None  # Full header object for reference
    handler_name: str = ""      # Name of handler processing this

    def __post_init__(self):
        """Log creation for debugging."""
        if self.has_job_routing():
            log.debug(f"JobContext created: internal={self.internal_job_id:#x}, "
                     f"source={self.source_job_id:#x}, emsg={self.request_emsg}")

    def has_job_routing(self) -> bool:
        """
        Check if this request uses job routing.

        Returns True if the client sent a valid sourceJobID, meaning they
        expect us to route the response back with that ID as targetJobID.
        """
        return self.source_job_id != K_JOB_ID_NONE and self.source_job_id != -1

    def get_response_target_job_id(self) -> int:
        """
        Get the targetJobID to use in responses.

        This is the critical method - it returns the client's sourceJobID,
        which must be set as targetJobID in our response for proper routing.
        """
        return self.source_job_id

    def mark_processing(self, handler_name: str = ""):
        """Mark this context as being processed by a handler."""
        self.state = JobContextState.PROCESSING
        self.handler_name = handler_name

    def mark_responding(self):
        """Mark this context as sending responses."""
        self.state = JobContextState.RESPONDING

    def mark_completed(self):
        """Mark this context as completed (all responses sent)."""
        self.state = JobContextState.COMPLETED
        elapsed = time.time() - self.created_time
        if self.has_job_routing():
            log.debug(f"JobContext completed: source={self.source_job_id:#x}, "
                     f"responses={self.responses_sent}, elapsed={elapsed:.3f}s")

    def mark_failed(self, reason: str = ""):
        """Mark this context as failed."""
        self.state = JobContextState.FAILED
        log.warning(f"JobContext failed: source={self.source_job_id:#x}, reason={reason}")

    def increment_response_count(self):
        """Increment the response count. Called when sending a response."""
        self.responses_sent += 1

    def is_expired(self, timeout_seconds: float = 300.0) -> bool:
        """
        Check if this context has expired.

        Args:
            timeout_seconds: Maximum age before expiration (default 5 minutes)

        Returns:
            True if context is older than timeout_seconds
        """
        return (time.time() - self.created_time) >= timeout_seconds

    def get_elapsed_seconds(self) -> float:
        """Get seconds elapsed since context creation."""
        return time.time() - self.created_time

    def apply_to_response(self, response) -> None:
        """
        Apply job routing to a response object.

        This sets the targetJobID on the response to our source_job_id,
        enabling the client to route it to the correct waiting job.

        Args:
            response: A response header object (ExtendedMsgHdr, MsgHdrProtoBuf, etc.)
        """
        if not self.has_job_routing():
            return

        # Handle different response types
        if hasattr(response, 'targetJobID'):
            response.targetJobID = self.source_job_id
            # Also set sourceJobID to -1 (we're not waiting for a response)
            if hasattr(response, 'sourceJobID'):
                response.sourceJobID = K_JOB_ID_NONE
        elif hasattr(response, 'proto'):
            # Protobuf response
            response.proto.jobid_target = self.source_job_id
            response.proto.jobid_source = K_JOB_ID_NONE

        self.increment_response_count()
        self.mark_responding()

    def create_response(self, emsg, response_class=None):
        """
        Create a response with correct job routing.

        This is a convenience method that creates a response object with
        the targetJobID already set correctly.

        Args:
            emsg: The EMsg for the response
            response_class: Optional response class to use (defaults to CMResponse)

        Returns:
            A response object with job routing configured
        """
        if response_class is None:
            from steam3.cm_packet_utils import CMResponse
            response_class = CMResponse

        # Create the response using the client
        response = response_class(emsg, client_obj=self.client)

        # Apply job routing
        self.apply_to_response(response)

        return response

    def __repr__(self) -> str:
        return (f"JobContext(source={self.source_job_id:#x}, "
               f"emsg={self.request_emsg}, state={self.state.name}, "
               f"responses={self.responses_sent})")


def create_job_context_from_header(header, client: 'Client') -> JobContext:
    """
    Factory function to create a JobContext from a request header.

    This extracts the job IDs from various header types (ExtendedMsgHdr,
    MsgHdrProtoBuf, etc.) and creates a properly configured JobContext.

    Args:
        header: The parsed request header object
        client: The client that sent the request

    Returns:
        A JobContext configured with the correct job IDs
    """
    source_job_id = K_JOB_ID_NONE
    target_job_id = K_JOB_ID_NONE
    request_emsg = 0

    # Extract job IDs based on header type
    if hasattr(header, 'sourceJobID'):
        source_job_id = header.sourceJobID if header.sourceJobID is not None else K_JOB_ID_NONE
        target_job_id = header.targetJobID if header.targetJobID is not None else K_JOB_ID_NONE
    elif hasattr(header, 'proto'):
        # Protobuf header
        if header.proto.HasField('jobid_source'):
            source_job_id = header.proto.jobid_source
        if header.proto.HasField('jobid_target'):
            target_job_id = header.proto.jobid_target

    # Get EMsg
    if hasattr(header, 'eMsgID'):
        request_emsg = int(header.eMsgID)

    # Normalize -1 to K_JOB_ID_NONE
    if source_job_id == -1:
        source_job_id = K_JOB_ID_NONE
    if target_job_id == -1:
        target_job_id = K_JOB_ID_NONE

    return JobContext(
        source_job_id=source_job_id,
        target_job_id=target_job_id,
        client=client,
        request_emsg=request_emsg,
        request_header=header
    )
