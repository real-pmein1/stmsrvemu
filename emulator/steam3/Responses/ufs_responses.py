# UFS Response Builders - Completely rebuilt based on client analysis
# This file contains response builders for UFS (User File Storage) operations
# All functions rebuild based on MCP analysis of Steam client expectations

import struct
from typing import List, Optional, Any, Dict

from steam3.Types.steam_types import EResult
from steam3.Types.remotefile import RemoteFile
from steam3.cm_packet_utils import CMResponse, CMProtoResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_ufs_pb2 import (
    CMsgClientUFSLoginResponse,
    CMsgClientUFSUploadFileResponse,
    CMsgClientUFSDownloadResponse,
    CMsgClientUFSFileChunk,
    CMsgClientUFSGetFileListForAppResponse,
    CMsgClientUFSUploadFileFinished
)


def build_UFSLogin_response(client_obj, result: EResult, app_ids: List[int], is_protobuf: bool = False):
    """
    Build UFS Login Response
    Client expects: result, app_ids list
    Based on: MsgClientUFSLoginResponse_t structure analysis
    """
    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        proto_msg = CMsgClientUFSLoginResponse()
        proto_msg.eresult = result.value
        proto_msg.apps.extend(app_ids)

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSLoginResponse, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        return response
    else:
        # Binary format - matches client expectations
        # Structure: EResult (4 bytes) + AppCount (4 bytes) + AppIDs (4 bytes each)
        data = struct.pack('<I', result.value)  # EResult
        data += struct.pack('<I', len(app_ids))  # App count
        for app_id in app_ids:
            data += struct.pack('<I', app_id)  # Each app ID
            
        response = CMResponse(eMsgID=EMsg.ClientUFSLoginResponse, client_obj=client_obj)
        response.data = data
        return response


def build_UFSUploadFile_response(client_obj, result: EResult, file_sha: bytes, 
                                job_id: int, source_job_id: int, is_protobuf: bool = False):
    """
    Build UFS Upload File Response
    Client expects: result, SHA, job IDs for tracking
    Based on: MsgClientUFSUploadFileResponse_t structure analysis
    """
    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        proto_msg = CMsgClientUFSUploadFileResponse()
        proto_msg.eresult = result.value
        proto_msg.sha_file = file_sha
        if job_id:
            proto_msg.ugcid = job_id  # Steam uses UGC ID for job tracking

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSUploadFileResponse, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        response.proto.jobid_source = job_id if job_id else 18446744073709551615
        response.proto.jobid_target = source_job_id if source_job_id else 18446744073709551615
        return response
    else:
        # Binary format - matches client expectations
        # Structure: EResult (4 bytes) + SHA (20 bytes) + padding/job info
        data = struct.pack('<I', result.value)  # EResult
        data += file_sha[:20].ljust(20, b'\x00')  # SHA1 (20 bytes)
        
        response = CMResponse(eMsgID=EMsg.ClientUFSUploadFileResponse, client_obj=client_obj)
        response.data = data
        response.sourceJobID = job_id
        response.targetJobID = source_job_id
        return response


def build_UFSDownloadFile_response(client_obj, result: EResult, app_id: int, 
                                  filename: str, file_size: int, raw_file_size: int,
                                  file_sha: bytes, timestamp: int, is_protobuf: bool = False):
    """
    Build UFS Download File Response - Initial response before chunks
    Client expects: result, file metadata for download preparation
    Based on: MsgClientUFSDownloadResponse_t structure analysis
    """
    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        proto_msg = CMsgClientUFSDownloadResponse()
        proto_msg.eresult = result.value
        proto_msg.app_id = app_id
        proto_msg.file_size = file_size
        proto_msg.raw_file_size = raw_file_size
        proto_msg.sha_file = file_sha
        proto_msg.time_stamp = timestamp
        proto_msg.is_explicit_delete = False  # Not a delete operation

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSDownloadResponse, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        return response
    else:
        # Binary format - FIXED: Correct field order from IDA Pro analysis
        # Offset 0: result (4 bytes)
        # Offset 4: app_id (4 bytes)
        # Offset 8: raw_file_size (4 bytes) - FIXED
        # Offset 12: file_size (4 bytes) - FIXED
        # Offset 16: sha (20 bytes)
        # Offset 36: timestamp (8 bytes) - FIXED: was 4 bytes
        data = struct.pack('<I', result.value)      # EResult (4 bytes)
        data += struct.pack('<I', app_id)           # App ID (4 bytes)
        data += struct.pack('<I', raw_file_size)    # Raw file size (4 bytes) - FIXED: swapped
        data += struct.pack('<I', file_size)        # File size (4 bytes) - FIXED: swapped
        data += file_sha[:20].ljust(20, b'\x00')    # SHA1 (20 bytes)
        data += struct.pack('<Q', timestamp)        # Timestamp (8 bytes) - FIXED: was '<I'

        response = CMResponse(eMsgID=EMsg.ClientUFSDownloadResponse, client_obj=client_obj)
        response.data = data
        return response


def build_UFSDownloadChunk_response(client_obj, file_sha: bytes,
                                   offset: int, chunk_data: bytes, is_protobuf: bool = False,
                                   result: EResult = None):
    """
    Build UFS Download Chunk Response - Individual chunk data
    FIXED: Removed result field - chunks don't have result codes per IDA Pro analysis
    Client expects: SHA for identification, offset, chunk data (NO result field)
    Based on: MsgClientUFSFileChunk_t structure analysis from EYieldingDownloadFile

    Note: result parameter kept for backward compatibility but is ignored
    """
    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        proto_msg = CMsgClientUFSFileChunk()
        proto_msg.sha_file = file_sha
        proto_msg.file_start = offset
        proto_msg.data = chunk_data

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSDownloadChunk, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        return response
    else:
        # Binary format - FIXED: Correct structure from IDA Pro analysis
        # Offset 0: sha_file (20 bytes)
        # Offset 20: offset (4 bytes)
        # Offset 24: data (variable length)
        # NO result field, NO length field
        data = file_sha[:20].ljust(20, b'\x00')  # SHA1 (20 bytes)
        data += struct.pack('<I', offset)        # Offset (4 bytes)
        data += chunk_data                       # Chunk data

        response = CMResponse(eMsgID=EMsg.ClientUFSDownloadChunk, client_obj=client_obj)
        response.data = data
        return response


def build_UFSUploadFileFinished_response(client_obj, result: EResult, file_sha: bytes,
                                        is_protobuf: bool = False, source_job_id: int = None,
                                        target_job_id: int = None):
    """
    Build UFS Upload File Finished Response
    Client expects: result, SHA for verification
    Based on: MsgClientUFSUploadFileFinished_t structure analysis
    """
    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        proto_msg = CMsgClientUFSUploadFileFinished()
        proto_msg.eresult = result.value
        proto_msg.sha_file = file_sha

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSUploadFileFinished, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        if source_job_id:
            response.proto.jobid_source = source_job_id
        if target_job_id:
            response.proto.jobid_target = target_job_id
        return response
    else:
        # Binary format - matches client expectations
        # Structure: EResult (4 bytes) + SHA (20 bytes)
        data = struct.pack('<I', result.value)      # EResult
        data += file_sha[:20].ljust(20, b'\x00')    # SHA1 (20 bytes)
        
        response = CMResponse(eMsgID=EMsg.ClientUFSUploadFileFinished, client_obj=client_obj)
        response.data = data
        if source_job_id:
            response.sourceJobID = source_job_id
        if target_job_id:
            response.targetJobID = target_job_id
        return response


def build_UFSGetFileListForApp_empty_response(client_obj, app_id: int, is_protobuf: bool = False):
    """
    Build an empty UFS Get File List For App Response
    Used when cloudmanager is not initialized (client sent request before UFS login)
    Returns empty file list to prevent client from hanging

    Protocol version handling:
    - >= 65557: New format (AppID + FileCount)
    - < 65557 or not set: Legacy format (FileCount only)
    """
    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        # Note: CMsgClientUFSGetFileListForAppResponse has no app_id or file_count fields
        # at the top level - app_id is per-file, file_count is implicit (len of files list)
        proto_msg = CMsgClientUFSGetFileListForAppResponse()
        # No files added - empty response

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSGetFileListForAppResponse, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        return response
    else:
        # Binary format - check protocol version for format selection
        protocol_version = getattr(client_obj, 'protocol_version', 0) or 0

        if protocol_version >= 65557:
            # New format (protocol >= 65557): AppID + FileCount
            data = struct.pack('<I', app_id)  # App ID (4 bytes)
            data += struct.pack('<I', 0)      # File count = 0 (4 bytes)
        else:
            # Legacy format (protocol < 65557 or not set): FileCount only
            data = struct.pack('<I', 0)       # File count = 0 (4 bytes)

        response = CMResponse(eMsgID=EMsg.ClientUFSGetFileListForAppResponse, client_obj=client_obj)
        response.data = data
        return response


def build_UFSGetFileListForApp_response(client_obj, steam_global_id: int, app_id: int,
                                       is_protobuf: bool = False):
    """
    Build UFS Get File List For App Response
    Client expects: list of files with metadata for the specified app
    Based on: MsgClientUFSGetFileListForAppResponse_t structure analysis

    Protocol version handling:
    - >= 65557: New format from IDA analysis (SHA, timestamp_4, size, filename)
    - < 65557 or not set: Legacy format (app_id, filename, sha, timestamp_8, size)
    """
    # Get file list from cloud storage manager
    files_metadata = client_obj.cloudmanager.list_files(app_id)

    if is_protobuf:
        # Protobuf format - use CMProtoResponse for proper proto bit
        # Note: CMsgClientUFSGetFileListForAppResponse has no app_id or file_count fields
        # at the top level - app_id is per-file, file_count is implicit (len of files list)
        proto_msg = CMsgClientUFSGetFileListForAppResponse()

        for file_info in files_metadata:
            file_details = proto_msg.files.add()
            file_details.app_id = app_id  # app_id is per-file in protobuf format
            file_details.file_name = file_info["file_name"]
            file_details.sha_file = file_info["sha_file"]
            file_details.time_stamp = file_info["time_stamp"]
            file_details.raw_file_size = file_info["raw_file_size"]
            file_details.is_explicit_delete = False

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSGetFileListForAppResponse, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        return response
    else:
        # Binary format - check protocol version for format selection
        protocol_version = getattr(client_obj, 'protocol_version', 0) or 0

        if protocol_version >= 65557:
            # New format from IDA analysis (protocol >= 65557)
            # Structure: AppID + FileCount + [SHA + Timestamp(4) + FileSize + Filename] per file
            data = struct.pack('<I', app_id)            # App ID (4 bytes)
            data += struct.pack('<I', len(files_metadata))  # File count (4 bytes)

            for file_info in files_metadata:
                # Each file entry: SHA + Timestamp + FileSize + Filename
                data += file_info["sha_file"][:20].ljust(20, b'\x00')  # SHA1 (20 bytes)
                data += struct.pack('<I', file_info["time_stamp"])     # Timestamp (4 bytes)
                data += struct.pack('<I', file_info["raw_file_size"])  # File size (4 bytes)

                # Filename as null-terminated string
                filename_bytes = file_info["file_name"].encode('utf-8', errors='replace')
                data += filename_bytes + b'\x00'
        else:
            # Legacy format for older clients (protocol < 65557 or not set)
            # Structure: FileCount + [AppID + Filename + SHA + Timestamp(8) + FileSize] per file
            data = struct.pack('<I', len(files_metadata))  # File count (4 bytes)

            for file_info in files_metadata:
                data += struct.pack('<I', app_id)                       # App ID (4 bytes)
                filename_bytes = file_info["file_name"].encode('utf-8', errors='replace')
                data += filename_bytes + b'\x00'                        # Filename (null-terminated)
                data += file_info["sha_file"][:20].ljust(20, b'\x00')   # SHA1 (20 bytes)
                data += struct.pack('<Q', file_info["time_stamp"])      # Timestamp (8 bytes)
                data += struct.pack('<I', file_info["raw_file_size"])   # File size (4 bytes)

        response = CMResponse(eMsgID=EMsg.ClientUFSGetFileListForAppResponse, client_obj=client_obj)
        response.data = data
        return response


def build_UFSTransferHeartbeat_response(client_obj, result: EResult = EResult.OK):
    """
    Build UFS Transfer Heartbeat Response
    Simple acknowledgment for heartbeat requests during transfers
    Client expects: basic OK response to continue transfer
    """
    from steam3.Responses.general_responses import build_General_response
    return build_General_response(client_obj, result)


def build_UFSDeleteFile_response(client_obj, result: EResult, file_sha: bytes,
                                is_protobuf: bool = False):
    """
    Build UFS Delete File Response
    Client expects: result, SHA of deleted file for verification
    Based on: MsgClientUFSDeleteFileResponse_t structure analysis
    """
    if is_protobuf:
        # Use CMProtoResponse for proper proto bit
        from steam3.protobufs.steammessages_clientserver_ufs_pb2 import CMsgClientUFSDeleteFileResponse
        proto_msg = CMsgClientUFSDeleteFileResponse()
        proto_msg.eresult = result.value
        proto_msg.sha_file = file_sha

        response = CMProtoResponse(eMsgID=EMsg.ClientUFSDeleteFileResponse, client_obj=client_obj)
        response.set_response_message(proto_msg)
        response.data = proto_msg.SerializeToString()
        return response
    else:
        # Binary format - matches client expectations
        # Structure: EResult (4 bytes) + SHA (20 bytes)
        data = struct.pack('<I', result.value)      # EResult
        data += file_sha[:20].ljust(20, b'\x00')    # SHA1 (20 bytes)
        
        response = CMResponse(eMsgID=EMsg.ClientUFSDeleteFileResponse, client_obj=client_obj)
        response.data = data
        return response