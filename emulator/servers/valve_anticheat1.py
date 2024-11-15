import threading
import logging
import os
import struct
import numpy as np

import config
from utilities.networkhandler import UDPNetworkHandler
from utilities.vac_utils import Module, Req, ReqAccept, ReqBlock, ReqCheckAccess, ReqFile, ReqGet, ReqNext


config_var = config.get_config()

class vacemu:
    TestModuleDir = (config_var['vacmoduledir'] + '//beta/').encode('latin-1')
    @staticmethod
    def Cmd_Accept(module_id):
        data = struct.pack('<I', -1 & 0xFFFFFFFF)
        data += struct.pack('BB', 75, 0)
        data += b'ACCEPT\x00'
        data += struct.pack('<I', module_id)
        return data

    @staticmethod
    def Cmd_Abort(message):
        data = struct.pack('<I', -1 & 0xFFFFFFFF)
        data += struct.pack('BB', 75, 0)
        data += b'ABORT\x00'
        data += message.encode('utf-8') + b'\x00'
        return data

    @staticmethod
    def Cmd_Finish():
        data = struct.pack('<I', -1 & 0xFFFFFFFF)
        data += struct.pack('BB', 75, 0)
        data += b'FINISH\x00'
        return data

    @staticmethod
    def Cmd_File(size, header):
        data = bytearray()
        data += struct.pack('<I', -1 & 0xFFFFFFFF)
        data += struct.pack('BB', 75, 0)
        data += b'FILE\x00'
        data += struct.pack('<I', size)
        data += header
        return bytes(data)

    @staticmethod
    def Cmd_Block(block_data):
        if isinstance(block_data, np.ndarray):
            block_data = block_data.tobytes()
        elif not isinstance(block_data, (bytes, bytearray)):
            raise TypeError(f"block_data must be bytes, bytearray, or numpy.ndarray, got {type(block_data)}")
        data = bytearray()
        data += struct.pack('<I', -1 & 0xFFFFFFFF)
        data += struct.pack('BB', 75, 0)
        data += b'BLOCK\x00'
        data += struct.pack('<H', len(block_data))
        data += block_data
        return bytes(data)

    @staticmethod
    def Cmd_AccessGranted(module_id, byte_value):
        data = struct.pack('<I', -1 & 0xFFFFFFFF)
        data += struct.pack('BB', 78, 0)
        data += struct.pack('<I', module_id)
        data += struct.pack('B', byte_value)
        data += b'\x00\x00\x00\x00\x00'
        return data

class VAC1Session(threading.Thread):
    def __init__(self, parent, address):
        threading.Thread.__init__(self)
        self.parent = parent
        self.address = address
        self.received_packet = None
        self.lock = threading.Event()
        self.daemon = True
        self.log = parent.log
        self.running = True
        self.module = None
        self.state = 'INITIAL'

    def send(self, data):
        self.parent.serversocket.sendto(data, self.address)

    def receive(self, timeout=50):
        if self.lock.wait(timeout):
            data = self.received_packet
            self.received_packet = None
            self.lock.clear()
            return data
        else:
            raise Exception("Receive timed out")

    def packet(self, data):
        self.received_packet = data
        self.lock.set()

    def run(self):
        clientid = str(self.address) + ": "
        self.log.info(clientid + "Connected to Valve Anti-Cheat 1 Server")
        try:
            data = self.receive()
            req = Req(data)
            req.read()
            if req.Cmd != 'CHALLENGE':
                req_check_access = ReqCheckAccess(data)
                if req_check_access.legal:
                    self.log.info(clientid + "'Check access'")
                    data_to_send = vacemu.Cmd_AccessGranted(req_check_access.Id, 1)
                    self.send(data_to_send)
                    self.parent.close_session(self)
                    return
                else:
                    data_to_send = vacemu.Cmd_Abort("error")
                    self.send(data_to_send)
                    raise Exception("Protocol violation")
            else:
                data_to_send = vacemu.Cmd_Accept(Module.Id)
                self.send(data_to_send)
                # Now wait for GET request
                data = self.receive()
                req_get = ReqGet(data)
                if not req_get.legal:
                    self.log.error(f"Invalid GET request from {self.address}")
                    data_to_send = vacemu.Cmd_Abort("Protocol violation")
                    self.send(data_to_send)
                    raise Exception("Protocol violation")
                self.log.info(f"{clientid}Request for file {req_get.FileName}")
                if vacemu.TestModuleDir == req_get.TestDir:
                    self.log.info(" [beta]")
                if Module.Id != req_get.Id:
                    data_to_send = vacemu.Cmd_Abort("Challenge error")
                    self.send(data_to_send)
                    raise Exception(f"Module order error: request id={req_get.Id} while expecting id={Module.Id}")
                if not req_get.FileName[0].isalnum():
                    self.log.info(f"! Attempt to get file {req_get.FileName}")
                    self.parent.close_session(self)
                    return
                try:
                    # Sanitize filename
                    safe_filename = os.path.normpath(req_get.FileName)
                    if os.path.isabs(safe_filename) or '..' in safe_filename.split(os.sep):
                        raise Exception("Invalid file path")
                    module = Module(safe_filename)
                    self.module = module
                except Exception as e:
                    data_to_send = vacemu.Cmd_Abort("file not found")
                    self.send(data_to_send)
                    self.log.error(f"! File not found: {req_get.FileName}")
                    self.log.error(f"Exception: {e}")
                    self.parent.close_session(self)
                    return
                data_to_send = vacemu.Cmd_File(self.module.Size, self.module.Header)
                self.send(data_to_send)
                # Now enter loop to send file blocks
                while True:
                    data = self.receive()
                    req_next = ReqNext(data)
                    if req_next.Cmd == 'ABORT':
                        self.log.info(f"{clientid}Connection closed")
                        self.parent.close_session(self)
                        return
                    if not req_next.legal or req_next.Pos < 0 or req_next.Pos > self.module.Size:
                        data_to_send = vacemu.Cmd_Abort("error")
                        self.send(data_to_send)
                        raise Exception(f"Protocol violation: {req_next.Cmd}")
                    if req_next.Pos == self.module.Size:
                        data_to_send = vacemu.Cmd_Finish()
                        self.send(data_to_send)
                        self.log.info(f"{clientid}File {self.module.Name} transferred")
                        self.parent.close_session(self)
                        return
                    size = self.module.Size - req_next.Pos
                    if size > 1024:
                        size = 1024
                    block_data = self.module.Data[req_next.Pos:req_next.Pos + size].tobytes()
                    data_to_send = vacemu.Cmd_Block(block_data)
                    self.send(data_to_send)
        except Exception as e:
            self.log.error(f"Exception occurred: {e}")
            self.parent.close_session(self)
            return

class VAC1Server(UDPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "VAC1Server"
        super(VAC1Server, self).__init__(config, int(port), self.server_type)
        self.client_sessions = {}
        self.log = logging.getLogger(self.server_type)

    def close_session(self, session):
        address = session.address
        if address in self.client_sessions:
            del self.client_sessions[address]

    def run(self):
        self.serversocket.bind((self.config['server_ip'], int(self.port)))
        while True:
            try:
                data, address = self.serversocket.recvfrom(16384)
            except Exception as e:
                continue  # Ignore exceptions on recvfrom

            # Handle per-client sessions
            session = self.client_sessions.get(address)
            if session is None:
                # Create a new session
                session = VAC1Session(self, address)
                self.client_sessions[address] = session
                session.start()
                session.packet(data)
            else:
                # Pass the packet to the existing session
                session.packet(data)