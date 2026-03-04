import logging
import os
import struct
import time

from utilities.networkhandler import TCPNetworkHandler

# Constants matching the C++ FileUpload server implementation
# From IDA analysis of SteamUI.dll harvestserver::* functions
PROTOCOL_VERSION_MIN = 1
PROTOCOL_VERSION_MAX = 2

# Protocol version response (harvestserver::recv_protocol_response expects non-zero for OK)
PROTOCOL_VERSION_INVALID = 0x00
PROTOCOL_VERSION_VALID = 0x01

# Upload request response (harvestserver::recv_upload_request_response expects 0 for OK)
FILE_UPLOAD_SERVER_OK = 0x00
FILE_UPLOAD_SERVER_ERROR = 0x01

# Upload completion acknowledgment (harvestserver::Upload_successful expects 1 for success)
FILE_UPLOAD_ACK_SUCCESS = 0x01
FILE_UPLOAD_ACK_FAILURE = 0x00

class HarvestServer(TCPNetworkHandler):

    def __init__(self, port, config):
        self.server_type = "HarvstServer"
        super(HarvestServer, self).__init__(config, int(port), self.server_type)
        self.log = logging.getLogger("hrvstsrv")

    def allow_file_upload(self, command_type: int, file_size: int) -> bool:
        """Validate whether to accept the file upload.

        Args:
            command_type: The command type from the upload request (should be 1)
            file_size: Size of the file being uploaded in bytes

        Returns:
            True to accept the upload, False to reject
        """
        return True

    def handle_client(self, data, address):
        """Handle an incoming file upload request."""

        clientid = f"{address}: "
        self.log.info(clientid + "Connected to Harvest Server")
        self.log.debug(clientid + f"Initial data: {repr(data)}")

        # Helper to ensure we can read more data if the initial "data" isn't big enough
        def recv_n(nbytes):
            chunks = []
            bytes_left = nbytes
            while bytes_left > 0:
                chunk = self.serversocket.recv(bytes_left, blocking=True)
                if not chunk:
                    break
                chunks.append(chunk)
                bytes_left -= len(chunk)
            return b"".join(chunks)

        # 1) The C++ client sends 4 bytes big-endian for protocol version
        if len(data) < 4:
            # Not enough in initial buffer, read more
            needed = 4 - len(data)
            data += recv_n(needed)

        if len(data) < 4:
            self.log.warning(clientid + "No protocol version data received.")
            return

        protocol_version = struct.unpack(">I", data[0:4])[0]
        self.log.info(clientid + f"Protocol version = {protocol_version}")

        if (
            protocol_version < PROTOCOL_VERSION_MIN
            or protocol_version > PROTOCOL_VERSION_MAX
        ):
            self.log.info(clientid + "Invalid protocol version, rejecting.")
            self.serversocket.send(bytes([PROTOCOL_VERSION_INVALID]))
            return
        self.serversocket.send(bytes([PROTOCOL_VERSION_VALID]))

        # We'll remove those first 4 bytes from "data" so next parse is simpler
        data = data[4:]

        # 3) Read the "upload command" => first read 4 bytes big-endian length
        #    Possibly all or part is still in 'data'
        if len(data) < 4:
            needed = 4 - len(data)
            data += recv_n(needed)
        if len(data) < 4:
            self.log.error(clientid + "No upload command length data.")
            return

        cmd_len = struct.unpack(">I", data[0:4])[0]
        data = data[4:]

        # Now read cmd_len bytes for the command itself
        if len(data) < cmd_len:
            needed = cmd_len - len(data)
            data += recv_n(needed)
        if len(data) < cmd_len:
            self.log.error(clientid + f"Upload command incomplete. Expected {cmd_len} bytes.")
            return

        command_bytes = data[0:cmd_len]
        data = data[cmd_len:]  # remove from buffer

        if cmd_len < 17:
            self.log.error(clientid + "Command structure too short.")
            return

        # Command structure from IDA analysis of harvestserver::send_upload_request:
        #   [1 byte]  command_type (always 1 for upload)
        #   [4 bytes BE] file_size
        #   [4 bytes BE] reserved1 (always 0)
        #   [4 bytes BE] reserved2 (always 0)
        # Total: 17 bytes for protocol v1
        #
        # For protocol v2, there may be an additional message string after the base fields
        command_type = command_bytes[0]
        file_size = struct.unpack_from(">I", command_bytes, 1)[0]
        reserved1 = struct.unpack_from(">I", command_bytes, 5)[0]
        reserved2 = struct.unpack_from(">I", command_bytes, 9)[0]
        reserved3 = struct.unpack_from(">I", command_bytes, 13)[0]
        offset = 17
        message = ""
        if protocol_version >= 2:
            if cmd_len < offset + 4:
                self.log.error(clientid + "Command structure missing message length")
                return
            msg_len = struct.unpack_from(">I", command_bytes, offset)[0]
            offset += 4
            if cmd_len < offset + msg_len:
                self.log.error(clientid + "Command structure truncated message")
                return
            message = command_bytes[offset:offset + msg_len].decode("latin-1", errors="ignore")

        self.log.debug(
            clientid
            + f"cmdData: cmd={command_type}, size={file_size}, r1={reserved1}, r2={reserved2}, r3={reserved3}, msg={message}"
        )

        if not self.allow_file_upload(command_type, file_size):
            self.serversocket.send(bytes([FILE_UPLOAD_SERVER_ERROR]))
            return
        self.serversocket.send(bytes([FILE_UPLOAD_SERVER_OK]))

        # 5) Stream file payload directly to disk to avoid memory buffering
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        folder_path = os.path.join("clientstats", "harvest_gamestats")
        os.makedirs(folder_path, exist_ok=True)
        outfilename = f"{address[0]}_{timestamp}.cmd{command_type}.upload.bin"
        file_path = os.path.join(folder_path, outfilename)

        bytes_written = 0
        if file_size > 0:
            # Stream directly to disk - write any buffered data first, then stream the rest
            with open(file_path, "wb") as f:
                # Write any leftover data from the buffer first
                if data:
                    to_write = min(len(data), file_size)
                    f.write(data[:to_write])
                    bytes_written += to_write
                    data = data[to_write:]

                # Stream remaining data directly to disk in chunks
                chunk_size = 65536  # 64KB chunks
                while bytes_written < file_size:
                    remaining = file_size - bytes_written
                    to_read = min(chunk_size, remaining)
                    chunk = self.serversocket.recv(to_read, blocking=True)
                    if not chunk:
                        self.log.error(clientid + f"Upload data incomplete. Expected {file_size} bytes, got {bytes_written}.")
                        # Send failure acknowledgment before closing
                        self.serversocket.send(bytes([FILE_UPLOAD_ACK_FAILURE]))
                        return
                    f.write(chunk)
                    bytes_written += len(chunk)
        else:
            # Create empty file for zero-size uploads
            with open(file_path, "wb"):
                pass

        self.log.info(clientid + f"Received {bytes_written} bytes. Saved to {outfilename}.")

        # Send upload completion acknowledgment (CRITICAL - client expects this!)
        # From IDA analysis: harvestserver::Upload_successful checks for response == 1
        self.serversocket.send(bytes([FILE_UPLOAD_ACK_SUCCESS]))
        self.log.info(clientid + "Upload completed. Sent acknowledgment. Closing connection.")
        return
