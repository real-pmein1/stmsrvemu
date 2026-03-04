# steam3/Managers/JobManager/client_job_registry.py
"""
ClientJobRegistry - Per-client job context tracking.

This module provides a registry for tracking active job contexts on a per-client
basis. Unlike the global JobManager singleton, this is designed to be embedded
directly in Client objects for efficient access.

Key features:
  - Track multiple concurrent requests by sourceJobID
  - Stack-based tracking for nested operations
  - Thread-safe access
  - Automatic cleanup of expired contexts
"""

import logging
import threading
import time
from typing import Dict, List, Optional, TYPE_CHECKING
from collections import deque

from steam3.Managers.JobManager.job_context import JobContext, K_JOB_ID_NONE, create_job_context_from_header

if TYPE_CHECKING:
    from steam3.ClientManager.client import Client

log = logging.getLogger("ClientJobRegistry")


class ClientJobRegistry:
    """
    Per-client registry for tracking active job contexts.

    This class maintains:
      - active_context: The current request being processed
      - contexts_by_source: Map of sourceJobID -> JobContext for concurrent requests
      - context_stack: Stack of contexts for nested operations

    Thread-safe operations ensure correct behavior even with concurrent handlers.
    """

    # Default timeout for job contexts (5 minutes)
    DEFAULT_CONTEXT_TIMEOUT = 300.0

    def __init__(self, client: 'Client'):
        """
        Initialize the registry for a specific client.

        Args:
            client: The client this registry belongs to
        """
        self._client = client
        self._lock = threading.RLock()

        # Current active context (most recent request being processed)
        self._active_context: Optional[JobContext] = None

        # Map sourceJobID -> JobContext for routing responses to concurrent requests
        self._contexts_by_source: Dict[int, JobContext] = {}

        # Stack of contexts for nested operations
        self._context_stack: deque = deque(maxlen=10)

        # Statistics
        self._total_contexts_created = 0
        self._total_responses_sent = 0

    @property
    def active_context(self) -> Optional[JobContext]:
        """Get the currently active job context."""
        with self._lock:
            return self._active_context

    @property
    def has_active_context(self) -> bool:
        """Check if there's an active context."""
        with self._lock:
            return self._active_context is not None

    def create_context(self, header, handler_name: str = "") -> JobContext:
        """
        Create a new job context from a request header.

        This is the primary entry point for creating contexts. It:
          - Creates the JobContext from the header
          - Registers it by sourceJobID (if present)
          - Sets it as the active context
          - Pushes it onto the context stack

        Args:
            header: The parsed request header object
            handler_name: Name of the handler processing this request

        Returns:
            The created JobContext
        """
        context = create_job_context_from_header(header, self._client)
        context.handler_name = handler_name

        with self._lock:
            # Push current active onto stack before replacing
            if self._active_context is not None:
                self._context_stack.append(self._active_context)

            # Set as active context
            self._active_context = context

            # Register by sourceJobID for concurrent request tracking
            if context.has_job_routing():
                self._contexts_by_source[context.source_job_id] = context

            self._total_contexts_created += 1

        return context

    def get_context_for_source(self, source_job_id: int) -> Optional[JobContext]:
        """
        Get the job context for a specific sourceJobID.

        This is used when we need to find which context a response belongs to,
        particularly for async operations or concurrent requests.

        Args:
            source_job_id: The sourceJobID to look up

        Returns:
            The JobContext if found, None otherwise
        """
        if source_job_id == K_JOB_ID_NONE or source_job_id == -1:
            return None

        with self._lock:
            return self._contexts_by_source.get(source_job_id)

    def complete_context(self, context: Optional[JobContext] = None) -> None:
        """
        Mark a context as completed and remove it from tracking.

        If no context is provided, completes the active context.

        Args:
            context: The context to complete (or None for active)
        """
        with self._lock:
            if context is None:
                context = self._active_context

            if context is None:
                return

            context.mark_completed()

            # Remove from sourceJobID tracking
            if context.has_job_routing():
                self._contexts_by_source.pop(context.source_job_id, None)

            # If this was the active context, pop from stack
            if context is self._active_context:
                if self._context_stack:
                    self._active_context = self._context_stack.pop()
                else:
                    self._active_context = None

            self._total_responses_sent += context.responses_sent

    def fail_context(self, context: Optional[JobContext] = None, reason: str = "") -> None:
        """
        Mark a context as failed and remove it from tracking.

        Args:
            context: The context to fail (or None for active)
            reason: Reason for failure
        """
        with self._lock:
            if context is None:
                context = self._active_context

            if context is None:
                return

            context.mark_failed(reason)

            # Remove from tracking
            if context.has_job_routing():
                self._contexts_by_source.pop(context.source_job_id, None)

            if context is self._active_context:
                if self._context_stack:
                    self._active_context = self._context_stack.pop()
                else:
                    self._active_context = None

    def get_response_target_job_id(self) -> int:
        """
        Get the targetJobID to use in responses for the active context.

        This is a convenience method that returns the sourceJobID from the
        active context, which should be used as targetJobID in responses.

        Returns:
            The targetJobID to use, or K_JOB_ID_NONE if no active context
        """
        with self._lock:
            if self._active_context is None:
                return K_JOB_ID_NONE
            return self._active_context.get_response_target_job_id()

    def apply_to_response(self, response) -> bool:
        """
        Apply job routing from the active context to a response.

        This sets targetJobID on the response to enable correct client routing.

        Args:
            response: The response object to configure

        Returns:
            True if routing was applied, False if no active context
        """
        with self._lock:
            if self._active_context is None:
                return False

            self._active_context.apply_to_response(response)
            return True

    def cleanup_expired(self, timeout_seconds: float = None) -> int:
        """
        Clean up expired job contexts.

        Args:
            timeout_seconds: Context expiration time (default: DEFAULT_CONTEXT_TIMEOUT)

        Returns:
            Number of contexts cleaned up
        """
        if timeout_seconds is None:
            timeout_seconds = self.DEFAULT_CONTEXT_TIMEOUT

        cleaned = 0

        with self._lock:
            # Find expired contexts
            expired_sources = []
            for source_id, ctx in self._contexts_by_source.items():
                if ctx.is_expired(timeout_seconds):
                    expired_sources.append(source_id)
                    ctx.state = ctx.state  # Trigger state update

            # Remove expired contexts
            for source_id in expired_sources:
                ctx = self._contexts_by_source.pop(source_id, None)
                if ctx:
                    log.debug(f"Cleaned up expired context: source={source_id:#x}, "
                             f"age={ctx.get_elapsed_seconds():.1f}s")
                    cleaned += 1

            # Clear stack of expired entries
            # (rarely needed, but prevents memory buildup in edge cases)
            if len(self._context_stack) > 5:
                while len(self._context_stack) > 3:
                    old = self._context_stack.popleft()
                    if old.is_expired(timeout_seconds):
                        cleaned += 1

        return cleaned

    def clear_all(self) -> None:
        """
        Clear all tracked contexts.

        Called when client disconnects to clean up all pending contexts.
        """
        with self._lock:
            # Fail all pending contexts
            for ctx in self._contexts_by_source.values():
                ctx.mark_failed("Client disconnected")

            if self._active_context:
                self._active_context.mark_failed("Client disconnected")

            self._contexts_by_source.clear()
            self._context_stack.clear()
            self._active_context = None

        log.debug(f"Cleared all job contexts for client")

    def get_pending_count(self) -> int:
        """Get count of pending (not completed) contexts."""
        with self._lock:
            return len(self._contexts_by_source)

    def get_stats(self) -> dict:
        """Get statistics about this registry."""
        with self._lock:
            return {
                'total_created': self._total_contexts_created,
                'total_responses': self._total_responses_sent,
                'currently_pending': len(self._contexts_by_source),
                'stack_depth': len(self._context_stack),
                'has_active': self._active_context is not None
            }

    def __repr__(self) -> str:
        with self._lock:
            return (f"ClientJobRegistry(pending={len(self._contexts_by_source)}, "
                   f"active={self._active_context is not None})")
