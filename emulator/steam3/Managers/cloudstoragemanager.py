# Cloud Storage Manager - Completely rebuilt based on client analysis
# This file manages UFS upload/download jobs and file storage operations
# Rebuilt to match Steam client expectations from MCP analysis

import os
import hashlib
import struct
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from io import BytesIO

from steam3.Types.steam_types import EResult


# ============================================================================
# Cloud Job System - Simple job tracking for UFS operations
# This is a lightweight job system specifically for cloud storage operations.
# For protocol-level job routing (sourceJobID/targetJobID), see Managers/JobManager/
# ============================================================================

_cloud_job_id_counter = 1


class CloudJob:
    """
    Represents a cloud storage job with arbitrary metadata.
    Used for tracking UFS upload/download operations.
    """

    def __init__(self, client: Any, name: str, metadata: Optional[Dict[str, Any]] = None):
        global _cloud_job_id_counter

        self.job_id = _cloud_job_id_counter
        _cloud_job_id_counter += 1

        self.client = client
        self.name = name
        self.metadata = metadata or {}
        self.started_at = datetime.now()
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


class CloudJobManager:
    """Per-client registry and lifecycle for CloudJob objects."""

    def __init__(self, client: Any):
        self.client = client
        self._jobs: Dict[int, CloudJob] = {}

    def create_job(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> CloudJob:
        job = CloudJob(self.client, name, metadata)
        self._jobs[job.job_id] = job
        job.start()
        return job

    def get_job(self, jobid: int) -> CloudJob:
        return self._jobs[jobid]

    def all_jobs(self) -> List[CloudJob]:
        return list(self._jobs.values())

    def get_jobs_by_type(self, name: str) -> List[CloudJob]:
        """Return all jobs whose name matches the given name."""
        return [job for job in self._jobs.values() if job.name == name]

    def cancel_job(self, jobid: int):
        job = self._jobs.pop(jobid, None)
        if job:
            job.stop()


# ============================================================================
# UFS Upload/Download Jobs
# ============================================================================


class UFSUploadJob(CloudJob):
    """
    UFS Upload Job - Handles chunked file uploads with proper sequencing
    Based on client analysis: CClientJobRemoteStorageSync functionality
    """
    
    def __init__(self, client, cloud_root: str, app_id: int, filename: str,
                 file_size: int, raw_file_size: int, expected_sha: bytes,
                 timestamp: int, client_source_job_id: int):
        super().__init__(client, "ufs_upload", {
            "app_id": app_id,
            "filename": filename,
            "file_size": file_size,           # Size of data to receive (may be compressed)
            "raw_file_size": raw_file_size,   # Size after decompression 
            "expected_sha": expected_sha,     # SHA1 of final file content
            "timestamp": timestamp,
            "client_source_job_id": client_source_job_id,
            "bytes_received": 0,
            "chunks_received": 0,
            "last_chunk_time": time.time(),
            "is_complete": False,
            "verification_passed": False
        })
        
        # Build file path: files/webserver/webroot/cloud/<steamid>/<appid>/<path>/<filename>
        steam_id = str(client.steamID.get_accountID())
        self.storage_root = os.path.join(cloud_root, steam_id, str(app_id))
        os.makedirs(self.storage_root, exist_ok=True)

        # Sanitize to a safe relative path and preserve subdirectories
        rel = filename.replace('\\', '/').lstrip('/\\')
        rel = os.path.normpath(rel)
        if rel.startswith('..') or os.path.isabs(rel):
            raise ValueError(f"Invalid path: {filename}")
        self.file_path = os.path.join(self.storage_root, rel)
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        # Initialize chunk buffer for out-of-order chunk assembly
        self.chunk_buffer = bytearray(file_size)
        self.chunk_map = {}  # offset -> length mapping for received chunks
        
    def write_chunk(self, offset: int, chunk_data: bytes) -> bool:
        """
        Write a chunk at the specified offset. Returns True if upload is complete.
        Handles out-of-order chunks as per Steam client expectations.
        """
        if self.metadata["is_complete"]:
            return True
            
        chunk_size = len(chunk_data)
        file_size = self.metadata["file_size"]
        
        # Validate chunk bounds
        if offset < 0 or offset + chunk_size > file_size:
            raise ValueError(f"Chunk out of bounds: offset={offset}, size={chunk_size}, file_size={file_size}")
            
        # Write chunk to buffer
        self.chunk_buffer[offset:offset + chunk_size] = chunk_data
        
        # Track chunk reception (handle overlapping chunks)
        new_bytes = 0
        chunk_end = offset + chunk_size
        
        # Check for new coverage
        for existing_offset, existing_size in self.chunk_map.items():
            existing_end = existing_offset + existing_size
            # Calculate overlap
            overlap_start = max(offset, existing_offset)
            overlap_end = min(chunk_end, existing_end)
            if overlap_start < overlap_end:
                new_bytes -= (overlap_end - overlap_start)
                
        self.chunk_map[offset] = chunk_size
        new_bytes += chunk_size
        
        # Update metadata
        self.metadata["bytes_received"] += max(0, new_bytes)
        self.metadata["chunks_received"] += 1
        self.metadata["last_chunk_time"] = time.time()
        
        # Check if upload is complete
        if self.metadata["bytes_received"] >= file_size:
            return self._finalize_upload()
            
        return False
        
    def _finalize_upload(self) -> bool:
        """
        Finalize the upload: verify SHA, decompress if needed, write to disk
        """
        try:
            # Get complete file data
            file_data = bytes(self.chunk_buffer)
            
            # Handle potential ZIP compression (Steam client may send compressed data)
            final_data = file_data
            if self._is_zip_data(file_data):
                final_data = self._decompress_zip(file_data)
                
            # Verify SHA1 hash
            calculated_sha = hashlib.sha1(final_data).digest()
            expected_sha = self.metadata["expected_sha"]
            
            if calculated_sha != expected_sha:
                raise ValueError(f"SHA mismatch: expected {expected_sha.hex()}, got {calculated_sha.hex()}")
                
            # Write final file to disk
            with open(self.file_path, 'wb') as f:
                f.write(final_data)
                f.flush()
                os.fsync(f.fileno())
                
            # Update file timestamp if provided
            if self.metadata["timestamp"] > 0:
                os.utime(self.file_path, (self.metadata["timestamp"], self.metadata["timestamp"]))
                
            self.metadata["is_complete"] = True
            self.metadata["verification_passed"] = True
            self.stop()
            return True
            
        except Exception as e:
            self.metadata["error"] = str(e)
            self.stop()
            return False
            
    def _is_zip_data(self, data: bytes) -> bool:
        """Check if data starts with ZIP magic number"""
        return len(data) >= 4 and data[:4] == b'PK\x03\x04'
        
    def _decompress_zip(self, zip_data: bytes) -> bytes:
        """Decompress ZIP data (Steam client may compress files)"""
        import zipfile
        with zipfile.ZipFile(BytesIO(zip_data), 'r') as zf:
            names = zf.namelist()
            if not names:
                raise ValueError("Empty ZIP file")
            # Use first file in ZIP
            return zf.read(names[0])


class UFSDownloadJob(CloudJob):
    """
    UFS Download Job - Handles chunked file downloads
    Based on client analysis of download flow expectations
    """
    
    def __init__(self, client, cloud_root: str, app_id: int, filename: str):
        super().__init__(client, "ufs_download", {
            "app_id": app_id,
            "filename": filename,
            "bytes_sent": 0,
            "chunks_sent": 0,
            "last_chunk_time": time.time()
        })
        
        # Build file path preserving subdirectories
        steam_id = str(client.steamID.get_accountID())
        rel = filename.replace('\\', '/').lstrip('/\\')
        rel = os.path.normpath(rel)
        if rel.startswith('..') or os.path.isabs(rel):
            raise ValueError(f"Invalid path: {filename}")
        self.file_path = os.path.join(cloud_root, steam_id, str(app_id), rel)
        
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {filename}")
            
        self.file_size = os.path.getsize(self.file_path)
        self.metadata["file_size"] = self.file_size
        
    def read_chunk(self, offset: int, max_size: int) -> bytes:
        """Read a chunk of the file at the specified offset"""
        with open(self.file_path, 'rb') as f:
            f.seek(offset)
            chunk_data = f.read(max_size)
            
        self.metadata["bytes_sent"] += len(chunk_data)
        self.metadata["chunks_sent"] += 1
        self.metadata["last_chunk_time"] = time.time()
        
        # Stop job when all data has been sent
        if offset + len(chunk_data) >= self.file_size:
            self.stop()
            
        return chunk_data
        
    def get_file_metadata(self) -> Dict[str, Any]:
        """Get file metadata for download response"""
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
            
        return {
            "file_size": self.file_size,
            "raw_file_size": self.file_size,  # No compression for downloads
            "sha_file": hashlib.sha1(file_data).digest(),
            "timestamp": int(os.path.getmtime(self.file_path))
        }


class CloudStorageManager:
    """
    Cloud Storage Manager - Main UFS backend system
    Manages file storage for Steam Cloud functionality
    Files stored in: files/webserver/webroot/cloud/<steamid>/
    """
    
    # Constants from client analysis
    UFS_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB default limit
    UFS_MAX_FILES_PER_APP = 1000  # Max files per app
    UFS_CHUNK_SIZE = 0x2800  # 10KB chunks (matches client constant)
    
    def __init__(self, cloud_root: str, job_manager: CloudJobManager):
        self.cloud_root = cloud_root
        self.job_manager = job_manager
        
        # Ensure cloud root exists
        os.makedirs(cloud_root, exist_ok=True)
        
    def get_user_cloud_path(self, steam_id: str) -> str:
        """Get the cloud storage path for a specific user"""
        return os.path.join(self.cloud_root, steam_id)
        
    def get_app_cloud_path(self, steam_id: str, app_id: int) -> str:
        """Get the cloud storage path for a specific app"""
        return os.path.join(self.cloud_root, steam_id, str(app_id))
        
    def list_files(self, app_id: int) -> List[Dict[str, Any]]:
        """
        List all files for an app. Returns metadata in client-expected format.
        """
        client = self.job_manager.client
        steam_id = str(client.steamID.get_accountID())
        app_path = self.get_app_cloud_path(steam_id, app_id)
        
        files = []
        if not os.path.exists(app_path):
            return files
            
        for filename in os.listdir(app_path):
            file_path = os.path.join(app_path, filename)
            if os.path.isfile(file_path):
                # Calculate SHA1
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    file_sha = hashlib.sha1(file_data).digest()
                    
                files.append({
                    "app_id": app_id,
                    "file_name": filename,
                    "sha_file": file_sha,
                    "raw_file_size": len(file_data),
                    "time_stamp": int(os.path.getmtime(file_path))
                })
                
        return files
        
    def new_upload_job(self, app_id: int, filename: str, file_size: int, 
                       raw_size: int, expected_sha: bytes, timestamp: int,
                       client_source_job_id: int) -> Tuple[EResult, Optional[UFSUploadJob]]:
        """
        Create a new upload job with proper validation
        """
        client = self.job_manager.client
        
        # Validate file size
        if file_size > self.UFS_MAX_FILE_SIZE:
            return EResult.LimitExceeded, None
            
        # Check existing file count
        existing_files = self.list_files(app_id)
        if len(existing_files) >= self.UFS_MAX_FILES_PER_APP:
            return EResult.LimitExceeded, None
            
        # Check for duplicate file (same SHA)
        for file_info in existing_files:
            if file_info["sha_file"] == expected_sha:
                return EResult.DuplicateRequest, None
                
        # Create upload job
        try:
            upload_job = UFSUploadJob(
                client=client,
                cloud_root=self.cloud_root,
                app_id=app_id,
                filename=filename,
                file_size=file_size,
                raw_file_size=raw_size,
                expected_sha=expected_sha,
                timestamp=timestamp,
                client_source_job_id=client_source_job_id
            )
            
            # Register with job manager
            job_id = self.job_manager.create_job("ufs_upload", upload_job.metadata).job_id
            upload_job.job_id = job_id
            self.job_manager._jobs[job_id] = upload_job
            
            return EResult.OK, upload_job
            
        except Exception as e:
            return EResult.Fail, None
            
    def new_download_job(self, app_id: int, filename: str) -> UFSDownloadJob:
        """
        Create a new download job
        """
        client = self.job_manager.client
        
        download_job = UFSDownloadJob(
            client=client,
            cloud_root=self.cloud_root,
            app_id=app_id,
            filename=filename
        )
        
        # Register with job manager
        job_id = self.job_manager.create_job("ufs_download", download_job.metadata).job_id
        download_job.job_id = job_id
        self.job_manager._jobs[job_id] = download_job
        
        return download_job
        
    def find_upload_job_by_sha(self, expected_sha: bytes) -> Optional[UFSUploadJob]:
        """Find an active upload job by its expected SHA"""
        for job in self.job_manager._jobs.values():
            if (isinstance(job, UFSUploadJob) and 
                job.metadata.get("expected_sha") == expected_sha and
                not job.metadata.get("is_complete", False)):
                return job
        return None
        
    def cleanup_expired_jobs(self, max_age_seconds: int = 3600):
        """Clean up jobs that have been inactive for too long"""
        current_time = time.time()
        expired_jobs = []
        
        for job_id, job in self.job_manager._jobs.items():
            if isinstance(job, (UFSUploadJob, UFSDownloadJob)):
                last_activity = job.metadata.get("last_chunk_time", 0)
                if current_time - last_activity > max_age_seconds:
                    expired_jobs.append(job_id)
                    
        for job_id in expired_jobs:
            job = self.job_manager._jobs.get(job_id)
            if job:
                job.stop()
                del self.job_manager._jobs[job_id]