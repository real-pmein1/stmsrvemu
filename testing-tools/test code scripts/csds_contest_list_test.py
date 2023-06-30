import struct
import utilities

# Define the structure of contentserver_info
contentserver_info_structure = struct.Struct('!16s I 16s 21s I')

# Define the global list contentserver_list
contentserver_list = []


class ContentServerInfo:
    def __init__(self, ip_address, port, region, timestamp):
        self.ip_address = ip_address
        self.port = port
        self.region = region
        self.timestamp = timestamp
        self.applist = []


def create_contentserver_info(ip_address, port, region, timestamp):
    contentserver_info = ContentServerInfo(ip_address, port, region, timestamp)
    contentserver_list.append(contentserver_info)
    return contentserver_info


def add_app(contentserver_info, app_id, version):
    contentserver_info.applist.append((app_id, version))


def pack_contentserver_info(contentserver_info):
    ip_address = contentserver_info.ip_address.encode('utf-8')
    port = contentserver_info.port
    region = contentserver_info.region.encode('utf-8')
    timestamp = contentserver_info.timestamp.encode('utf-8')

    applist_length = len(contentserver_info.applist)
    packed_applist = struct.pack('!I', applist_length)

    for app in contentserver_info.applist:
        app_id, version = app
        packed_applist += struct.pack('!II', app_id, version)

    packed_info = contentserver_info_structure.pack(ip_address, port, region, timestamp, len(packed_applist))

    return packed_info + packed_applist


def unpack_contentserver_info(buffer):
    info_size = contentserver_info_structure.size
    info_data = buffer[:info_size]
    unpacked_info = contentserver_info_structure.unpack(info_data)
    ip_address = unpacked_info[0].decode('utf-8').rstrip('\x00')
    port = unpacked_info[1]
    region = unpacked_info[2].decode('utf-8').rstrip('\x00')
    timestamp = unpacked_info[3].decode('utf-8').rstrip('\x00')

    unpacked_applist = []
    applist_data = buffer[info_size:]

    applist_length, = struct.unpack('!I', applist_data[:4])
    applist_data = applist_data[4:]

    for _ in range(applist_length):
        app_id, version = struct.unpack('!II', applist_data[:8])
        unpacked_applist.append((app_id, version))
        applist_data = applist_data[8:]

    unpacked_info = ContentServerInfo(ip_address, port, region, timestamp)
    unpacked_info.applist = unpacked_applist

    return unpacked_info


# Example usage
info1 = create_contentserver_info("192.168.0.1", 8080, "US", "2023-06-08T10:00:00")
add_app(info1, 1234, 1)
add_app(info1, 5678, 2)

buffer = pack_contentserver_info(info1)
print("Packed buffer:", repr(buffer))
enc_buffer = utilities.encrypt(buffer, "password")
print("\nencrypted buffer: " +enc_buffer)
print ""
dec_buffer = utilities.decrypt(enc_buffer, "password")
print("decrypted buffer :"+dec_buffer)
unpacked_info = unpack_contentserver_info(dec_buffer)



print("\nUnpacked contentserver_info:")
print("IP Address:", unpacked_info.ip_address)
print("Port:", unpacked_info.port)
print("Region:", unpacked_info.region)
print("Timestamp:", unpacked_info.timestamp)
print("App List:", unpacked_info.applist)
