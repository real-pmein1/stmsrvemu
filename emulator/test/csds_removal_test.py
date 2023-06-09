import struct
import random
import string

def send_for_removal():
    ip_address = generate_random_ip()
    port = random.randint(1024, 65535)
    region = generate_random_region()

    ipaddr = ip_address.encode('utf-8')
    reg = region.encode('utf-8')

    packed_info = struct.pack('!16s I 16s', ipaddr, port, reg)

    return packed_info

def generate_random_ip():
    # Generate a random IP address
    segments = []
    for _ in range(4):
        segment = str(random.randint(0, 255))
        segments.append(segment)
    ip_address = '.'.join(segments)
    return ip_address

def generate_random_region():
    # Generate a random region name
    region = ''.join(random.choice(string.ascii_uppercase) for _ in range(16))
    return region

def unpack_send_for_removal(packed_info):
    unpacked_info = struct.unpack('!16s I 16s', packed_info)
    ip_address = unpacked_info[0].decode('utf-8').rstrip('\x00')
    port = unpacked_info[1]
    region = unpacked_info[2].decode('utf-8').rstrip('\x00')
    return ip_address,port,region

# Example usage:
packed_data = send_for_removal()
print(packed_data)
print("")
print unpack_send_for_removal(packed_data)
