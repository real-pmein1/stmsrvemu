# steam3/Managers/JobManager/__init__.py
"""
Steam Job Management System

This module provides job tracking, routing, and lifecycle management for
Steam CM server request/response handling.

Based on Valve's GCSDK job system (job.h, jobmgr.h, jobtime.h) and
TinServer's CMServerJob pattern for explicit job ID routing.

Key Components:
  - JobContext: Lightweight context for request/response job ID routing
  - ServerJob: Long-running jobs with automatic job ID handling (like CMServerJob)
  - ClientJobRegistry: Per-client tracking of active job contexts
  - Job: Original job representation (for complex async workflows)
  - JobManager: Global job tracking singleton
"""

# New job context system (TinServer-inspired)
from .job_context import (
    JobContext,
    JobContextState,
    K_JOB_ID_NONE,
    create_job_context_from_header,
)
from .server_job import ServerJob, ServerJobState
from .client_job_registry import ClientJobRegistry

# Original job system (for complex workflows)
from .job import Job, JobState, JobPauseReason
from .jobmgr import JobManager, get_job_manager
from .jobtime import JobTime

__all__ = [
    # New job context system
    'JobContext',
    'JobContextState',
    'K_JOB_ID_NONE',
    'create_job_context_from_header',
    'ServerJob',
    'ServerJobState',
    'ClientJobRegistry',

    # Original job system
    'Job',
    'JobState',
    'JobPauseReason',
    'JobManager',
    'get_job_manager',
    'JobTime',
]
