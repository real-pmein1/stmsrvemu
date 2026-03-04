# UFS Message Handlers - Completely rebuilt based on client analysis  
# This file contains handlers for UFS (User File Storage) protocol messages
# Rebuilt to match Steam client expectations from MCP analysis

import struct
import os
import time
import hashlib
from typing import Optional, List, Any

from steam3.protobufs.steammessages_clientserver_ufs_pb2 import (
    CMsgClientUFSGetFileListForApp,
    CMsgClientUFSLoginRequest,
    CMsgClientUFSUploadFileRequest,
    CMsgClientUFSDownloadRequest,
    CMsgClientUFSFileChunk,
    CMsgClientUFSUploadFileFinished,
    CMsgClientUFSDeleteFileRequest
)
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMPacket, ExtendedMsgHdr
from steam3.ClientManager.client import Client
from steam3.Managers.cloudstoragemanager import CloudStorageManager, UFSUploadJob
from steam3.Responses.ufs_responses import (
    build_UFSGetFileListForApp_response,
    build_UFSLogin_response,
    build_UFSUploadFile_response,
    build_UFSDownloadFile_response,
    build_UFSDownloadChunk_response,
    build_UFSUploadFileFinished_response,
    build_UFSTransferHeartbeat_response,
    build_UFSDeleteFile_response
)
from steam3 import database

# UFS Constants from client analysis
UFS_FILE_CHUNK_MAX_LEN = 0x2800  # 10240 bytes - matches Steam client constant
UFS_HEARTBEAT_INTERVAL = 12      # Send heartbeat every 12 chunks


def handle_UFSGetFileListForApp(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS Get File List For App Request
    Client sends list of app IDs, server responds with file metadata for each app
    Based on: CClientJobRemoteStorageSync functionality analysis
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): UFS Get File List For App Request")
    
    is_protobuf = bool(packet.is_proto)
    app_ids = []
    
    try:
        if is_protobuf:
            # Parse protobuf format
            proto_msg = CMsgClientUFSGetFileListForApp()
            proto_msg.ParseFromString(request.data)
            app_ids = list(proto_msg.apps_to_query)
            cmserver_obj.log.debug(f"Protobuf request for apps: {app_ids}")
        else:
            # Parse binary format: AppCount (4 bytes) + AppIDs (4 bytes each)
            if len(request.data) < 4:
                cmserver_obj.log.error("Binary UFS file list request too short")
                return -1
                
            offset = 0
            app_count = struct.unpack_from('<I', request.data, offset)[0]
            offset += 4
            
            for i in range(app_count):
                if len(request.data) < offset + 4:
                    cmserver_obj.log.error(f"Truncated app ID at index {i}")
                    break
                app_id = struct.unpack_from('<I', request.data, offset)[0]
                app_ids.append(app_id)
                offset += 4
                
            cmserver_obj.log.debug(f"Binary request for apps: {app_ids}")
    
    except Exception as e:
        cmserver_obj.log.error(f"Failed to parse UFS file list request: {e}")
        return -1

    # Ensure cloud manager is available - must have completed UFS login first
    if not hasattr(client_obj, 'cloudmanager') or client_obj.cloudmanager is None:
        cmserver_obj.log.error("UFS file list request without established session - client must send ClientUFSLoginRequest first")
        # Return empty file list responses for each app instead of crashing
        from steam3.Responses.ufs_responses import build_UFSGetFileListForApp_empty_response
        responses = []
        for app_id in app_ids:
            response_packet = build_UFSGetFileListForApp_empty_response(
                client_obj, app_id, bool(packet.is_proto)
            )
            responses.append(response_packet)
        return responses

    # Build responses for each app
    responses = []
    steam_global_id = client_obj.steamID.get_static_steam_global_id()
    
    for app_id in app_ids:
        try:
            response_packet = build_UFSGetFileListForApp_response(
                client_obj, steam_global_id, app_id, is_protobuf
            )
            responses.append(response_packet)
            cmserver_obj.log.debug(f"Built file list response for app {app_id}")
        except Exception as e:
            cmserver_obj.log.error(f"Failed to build response for app {app_id}: {e}")
    
    return responses


def handle_ClientUFSLoginRequest(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS Login Request
    Establishes UFS session and validates client credentials
    Based on: Steam client UFS session establishment analysis
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): UFS Login Request")
    
    is_protobuf = not isinstance(request, ExtendedMsgHdr)
    app_ids = []
    session_token = None
    
    try:
        if is_protobuf:
            # Parse protobuf format
            proto_msg = CMsgClientUFSLoginRequest()
            proto_msg.ParseFromString(request.data)
            app_ids = list(proto_msg.apps)
            session_token = proto_msg.am_session_token
            cmserver_obj.log.debug(f"Protobuf UFS login for apps: {app_ids}")
        else:
            # Parse binary format: Token + AppCount + AppIDs
            from steam3.messages.MsgClientUFSLoginRequest import MsgClientUFSLoginRequest
            parser = MsgClientUFSLoginRequest(request.data)
            app_ids = parser.app_ids
            session_token = parser.cm_session_token
            cmserver_obj.log.debug(f"Binary UFS login for apps: {app_ids}")
    
    except Exception as e:
        cmserver_obj.log.error(f"Failed to parse UFS login request: {e}")
        return build_UFSLogin_response(client_obj, EResult.Fail, [], is_protobuf)
    
    # Validate session token
    try:
        token_valid = database.compareUFSSessionToken(
            request.steamID.get_accountID(),
            session_token
        )
        if token_valid != 1:
            cmserver_obj.log.warning(f"Invalid UFS session token for user {request.steamID.get_accountID()}")
            return build_UFSLogin_response(client_obj, EResult.AccessDenied, [], is_protobuf)
    except Exception as e:
        cmserver_obj.log.error(f"Session token validation failed: {e}")
        return build_UFSLogin_response(client_obj, EResult.Fail, [], is_protobuf)
    
    # Initialize cloud storage manager for client
    try:
        # Use configured cloud root or default path
        cloud_root = cmserver_obj.config.get("cloud_root", "files/webserver/webroot/cloud")
        
        client_obj.cloudmanager = CloudStorageManager(
            cloud_root=cloud_root,
            job_manager=client_obj.job_manager
        )
        
        cmserver_obj.log.info(f"UFS session established for user {client_obj.steamID.get_accountID()}")
        return build_UFSLogin_response(client_obj, EResult.OK, app_ids, is_protobuf)
        
    except Exception as e:
        cmserver_obj.log.error(f"Failed to initialize cloud storage manager: {e}")
        return build_UFSLogin_response(client_obj, EResult.Fail, [], is_protobuf)


def handle_ClientUFSFileUploadRequest(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS File Upload Request
    Initiates a new file upload with metadata and creates upload job
    Based on: CClientJobRemoteStorageSync upload initiation analysis
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): UFS File Upload Request")
    
    # Ensure cloud manager is available
    if not hasattr(client_obj, 'cloudmanager') or client_obj.cloudmanager is None:
        cmserver_obj.log.error("UFS upload request without established session")
        return build_UFSUploadFile_response(
            client_obj, EResult.AccessDenied, b'\x00' * 20, 0, 0, bool(packet.is_proto)
        )
    
    is_protobuf = bool(packet.is_proto)
    
    try:
        if is_protobuf:
            # Parse protobuf format
            proto_msg = CMsgClientUFSUploadFileRequest()
            proto_msg.ParseFromString(request.data)
            
            app_id = proto_msg.app_id
            filename = proto_msg.file_name
            file_size = proto_msg.file_size
            raw_file_size = proto_msg.raw_file_size or file_size
            expected_sha = proto_msg.sha_file
            timestamp = proto_msg.time_stamp
            client_source_job_id = getattr(proto_msg, 'client_sourcejobid', 0)
            
        else:
            # Parse binary format
            from steam3.messages.MsgClientUFSUploadFileRequest import MsgClientUFSUploadFileRequest
            parser = MsgClientUFSUploadFileRequest(request.data)
            
            app_id = parser.appId
            filename = parser.filename
            file_size = parser.size
            raw_file_size = parser.rawSize
            expected_sha = parser.sha
            timestamp = parser.time
            client_source_job_id = request.sourceJobID
        
        cmserver_obj.log.debug(f"Upload request: app={app_id}, file='{filename}', size={file_size}, sourcejobid={client_source_job_id}, targetjobid={request.targetJobID}")

        # Create upload job
        result, upload_job = client_obj.cloudmanager.new_upload_job(
            app_id=app_id,
            filename=filename,
            file_size=file_size,
            raw_size=raw_file_size,
            expected_sha=expected_sha,
            timestamp=timestamp,
            client_source_job_id=client_source_job_id
        )
        source_job_id = request.sourceJobID if hasattr(request, 'sourceJobID') else client_source_job_id
        
        return build_UFSUploadFile_response(
            client_obj, result, expected_sha, upload_job.job_id, client_source_job_id, is_protobuf
        )
        
    except Exception as e:
        cmserver_obj.log.error(f"UFS upload request failed: {e}")
        return build_UFSUploadFile_response(
            client_obj, EResult.Fail, b'\x00' * 20, 0, 0, is_protobuf
        )


def handle_ClientUFSDownloadRequest(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS File Download Request
    Initiates file download and sends initial response followed by chunks
    Based on: Steam client download flow analysis
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): UFS Download Request")
    
    # Ensure cloud manager is available
    if not hasattr(client_obj, 'cloudmanager') or client_obj.cloudmanager is None:
        cmserver_obj.log.error("UFS download request without established session")
        return -1
    
    is_protobuf = bool(packet.is_proto)
    response_packets = []
    
    try:
        if is_protobuf:
            # Parse protobuf format
            proto_msg = CMsgClientUFSDownloadRequest()
            proto_msg.ParseFromString(request.data)
            app_id = proto_msg.app_id
            filename = proto_msg.file_name
        else:
            # Parse binary format
            from steam3.messages.MsgClientUFSDownloadRequest import MsgClientUFSDownloadRequest
            parser = MsgClientUFSDownloadRequest(request.data)
            app_id = parser.app_id
            filename = parser.filename
        
        cmserver_obj.log.debug(f"Download request: app={app_id}, file='{filename}'")
        
        # Create download job
        download_job = client_obj.cloudmanager.new_download_job(app_id, filename)
        file_metadata = download_job.get_file_metadata()
        
        # Send initial download response
        initial_response = build_UFSDownloadFile_response(
            client_obj=client_obj,
            result=EResult.OK,
            app_id=app_id,
            filename=filename,
            file_size=file_metadata["file_size"],
            raw_file_size=file_metadata["raw_file_size"],
            file_sha=file_metadata["sha_file"],
            timestamp=file_metadata["timestamp"],
            is_protobuf=is_protobuf
        )
        response_packets.append(initial_response)
        
        # Stream file in chunks
        offset = 0
        total_size = file_metadata["file_size"]
        
        while offset < total_size:
            chunk_data = download_job.read_chunk(offset, UFS_FILE_CHUNK_MAX_LEN)
            if not chunk_data:
                break
                
            # FIXED: Removed result parameter from chunk response (chunks don't have result codes)
            chunk_response = build_UFSDownloadChunk_response(
                client_obj=client_obj,
                file_sha=file_metadata["sha_file"],
                offset=offset,
                chunk_data=chunk_data,
                is_protobuf=is_protobuf
            )
            response_packets.append(chunk_response)
            offset += len(chunk_data)
            
        cmserver_obj.log.info(f"Download completed: {filename} ({offset} bytes)")
        
    except FileNotFoundError:
        cmserver_obj.log.warning(f"File not found: app={app_id}, file='{filename}'")
        error_response = build_UFSDownloadFile_response(
            client_obj=client_obj,
            result=EResult.FileNotFound,
            app_id=app_id,
            filename=filename or "",
            file_size=0,
            raw_file_size=0,
            file_sha=b'\x00' * 20,
            timestamp=0,
            is_protobuf=is_protobuf
        )
        response_packets.append(error_response)
        
    except Exception as e:
        cmserver_obj.log.error(f"UFS download failed: {e}")
        error_response = build_UFSDownloadFile_response(
            client_obj=client_obj,
            result=EResult.Fail,
            app_id=app_id if 'app_id' in locals() else 0,
            filename=filename if 'filename' in locals() else "",
            file_size=0,
            raw_file_size=0,
            file_sha=b'\x00' * 20,
            timestamp=0,
            is_protobuf=is_protobuf
        )
        response_packets.append(error_response)
    
    return response_packets


def handle_ClientUFSUploadFileChunk(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS Upload File Chunk
    Receives and processes individual file chunks for ongoing uploads
    Based on: Steam client chunk upload flow analysis
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): UFS Upload Chunk")
    
    # Ensure cloud manager is available
    if not hasattr(client_obj, 'cloudmanager') or client_obj.cloudmanager is None:
        cmserver_obj.log.error("UFS chunk upload without established session")
        return -1
    
    is_protobuf = bool(packet.is_proto)
    
    try:
        if is_protobuf:
            # Parse protobuf format
            proto_msg = CMsgClientUFSFileChunk()
            proto_msg.ParseFromString(request.data)
            file_sha = proto_msg.sha_file
            offset = proto_msg.file_start
            chunk_data = proto_msg.data
        else:
            # Parse binary format: SHA (20 bytes) + Offset (4 bytes) + Data
            from steam3.messages.MsgClientUFSUploadFileChunk import MsgClientUFSUploadFileChunk
            chunk_msg = MsgClientUFSUploadFileChunk().deserialize(request.data)
            file_sha = chunk_msg.sha
            offset = chunk_msg.offset
            chunk_data = chunk_msg.data
        
        # Find matching upload job by SHA
        upload_job = client_obj.cloudmanager.find_upload_job_by_sha(file_sha)
        
        if not upload_job:
            cmserver_obj.log.error(f"No matching upload job found for SHA {file_sha.hex()}")
            return -1
        
        cmserver_obj.log.debug(f"Processing chunk: offset={offset}, size={len(chunk_data)}, SHA={file_sha.hex()[:8]}")
        
        # Write chunk to upload job
        upload_complete = upload_job.write_chunk(offset, chunk_data)
        
        # If upload is complete, send finished response
        if upload_complete:
            cmserver_obj.log.info(f"Upload completed for file with SHA {file_sha.hex()}")
            
            finished_response = build_UFSUploadFileFinished_response(
                client_obj=client_obj,
                result=EResult.OK,
                file_sha=file_sha,
                is_protobuf=is_protobuf,
                target_job_id=upload_job.metadata.get("client_source_job_id")
            )
            return [finished_response]
        
        # Continue receiving chunks (no explicit response needed)
        return -1
        
    except Exception as e:
        cmserver_obj.log.error(f"UFS chunk upload failed: {e}")
        return -1


def handle_ClientUFSTransferHeartbeat(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS Transfer Heartbeat
    Responds to heartbeat requests during file transfers to keep connection alive
    Based on: Steam client heartbeat mechanism analysis (every 12 chunks)
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): UFS Transfer Heartbeat")
    
    # Clean up any expired jobs during heartbeat
    if hasattr(client_obj, 'cloudmanager') and client_obj.cloudmanager:
        client_obj.cloudmanager.cleanup_expired_jobs()
    
    # Return simple OK response
    return build_UFSTransferHeartbeat_response(client_obj, EResult.OK)


def handle_ClientUFSDeleteFileRequest(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle UFS Delete File Request
    Deletes a file from cloud storage
    Based on: Steam client file deletion analysis
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): UFS Delete File Request")
    
    # Ensure cloud manager is available
    if not hasattr(client_obj, 'cloudmanager') or client_obj.cloudmanager is None:
        cmserver_obj.log.error("UFS delete request without established session")
        return build_UFSDeleteFile_response(client_obj, EResult.AccessDenied, b'\x00' * 20, bool(packet.is_proto))
    
    is_protobuf = bool(packet.is_proto)
    
    try:
        if is_protobuf:
            # Parse protobuf format
            proto_msg = CMsgClientUFSDeleteFileRequest()
            proto_msg.ParseFromString(request.data)
            app_id = proto_msg.app_id
            filename = proto_msg.file_name
        else:
            # Parse binary format (similar to upload request structure)
            if len(request.data) < 8:
                raise ValueError("Delete request too short")
            app_id = struct.unpack_from('<I', request.data, 0)[0]
            filename = request.data[4:].decode('utf-8', errors='replace').rstrip('\x00')
        
        # Build file path
        steam_id = str(client_obj.steamID.get_accountID())
        file_path = os.path.join(
            client_obj.cloudmanager.cloud_root,
            steam_id,
            str(app_id),
            os.path.basename(filename.replace('\\', '/'))
        )
        
        if not os.path.exists(file_path):
            cmserver_obj.log.warning(f"Delete request for non-existent file: {filename}")
            return build_UFSDeleteFile_response(client_obj, EResult.FileNotFound, b'\x00' * 20, is_protobuf)
        
        # Get file SHA before deletion
        with open(file_path, 'rb') as f:
            file_data = f.read()
            file_sha = hashlib.sha1(file_data).digest()
        
        # Delete the file
        os.remove(file_path)
        cmserver_obj.log.info(f"Deleted file: {filename} (SHA: {file_sha.hex()})")
        
        return build_UFSDeleteFile_response(client_obj, EResult.OK, file_sha, is_protobuf)
        
    except Exception as e:
        cmserver_obj.log.error(f"UFS file deletion failed: {e}")
        return build_UFSDeleteFile_response(client_obj, EResult.Fail, b'\x00' * 20, is_protobuf)