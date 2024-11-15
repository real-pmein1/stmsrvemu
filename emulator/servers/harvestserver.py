import logging
import struct
import time

from utilities.networkhandler import UDPNetworkHandler


# This server is used for collecting mini-crash dumps, Bugreport zips,
class HarvestServer(UDPNetworkHandler):

    def __init__(self, port, config):
        self.server_type = "HarvstServer"
        super(HarvestServer, self).__init__(config, int(port), self.server_type)  # Create an instance of NetworkHandler
        self.log = logging.getLogger("hrvstsrv")
        
    def handle_client(self, data, address):
        
        clientid = str(address) + ": "
        self.log.info(clientid + "Connected to Harvest Server")
        self.log.debug(clientid + ("Received message: %s, from %s" % (repr(data), address)))

        protocol_ver = data[0:1]
        if protocol_ver in [1, 2, 3]:
            self.serversocket.sendto(b"\x01", address)
        else:
            self.serversocket.sendto(b"\x00", address)  # bad protocol version
        data = self.serversocket.recv(256)
        unknown1 = struct.unpack('I', data[0:4])[0]
        unknown2 = struct.unpack('B', data[4:5])[0]
        unknown3 = struct.unpack('I', data[5:9])[0]
        dump_file_size = struct.unpack('I', data[9:13])[0]
        # Skip 8 bytes
        unknown4 = struct.unpack('I', data[21:25])[0]

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        txtfilename = f"stats/crashdump/{address}.{timestamp}.txt"
        filename = f"stats/crashdump/{address}.{timestamp}.{data[25:]}"

        # Writing to a file
        with open(txtfilename, 'w') as file:
            file.write(f'unknown1: {unknown1}\n')  # One of these SHOULD be the sessionid from CSER
            file.write(f'unknown2: {unknown2}\n')
            file.write(f'unknown3: {unknown3}\n')
            file.write(f'dump_file_size: {dump_file_size}\n')
            file.write(f'unknown4: {unknown4}\n')
            file.write(f'filename: {filename}\n')

        self.serversocket.sendto(b"\x01", address)  # send x01 for ok - accept upload or x00 for refuse upload
        dump = self.serversocket.recv(15682, False)

        # Writing to a file
        with open(filename, 'w') as file:
            file.write(dump)

        self.serversocket.sendto(b"\x01", address)  # 0x01 for successful upload, 0x00 for failed upload
        self.serversocket.close()