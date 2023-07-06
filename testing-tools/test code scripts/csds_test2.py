import utilities
import struct

def receive_heartbeat(decrypted_data, peer_password):
    #decrypted_data = utilities.decrypt(encrypted_data[1:], peer_password)

    ip_address = ""
    ip_index = 0
    while decrypted_data[ip_index] != '\x00':
        ip_address += decrypted_data[ip_index]
        ip_index += 1
    ip_index += 1

    port = struct.unpack('H', decrypted_data[ip_index:ip_index + 2])[0]
    ip_index += 2

    region = ""
    while decrypted_data[ip_index] != '\x00':
        region += decrypted_data[ip_index]
        ip_index += 1
    ip_index += 1

    timestamp = ""
    while decrypted_data[ip_index] != '\x00':
        timestamp += decrypted_data[ip_index]
        ip_index += 1
    timestamp = float(timestamp)
    ip_index += 1

    applist_data = decrypted_data[ip_index:]
    applist = []

    app_index = 0
    while app_index < len(applist_data):
        appid = ""
        version = ""
        while app_index < len(applist_data) and applist_data[app_index] != '\x00':
            appid += applist_data[app_index]
            app_index += 1
        app_index += 1

        while app_index < len(applist_data) and applist_data[app_index:app_index + 2] != '\x00\x00':
            version += applist_data[app_index]
            app_index += 1
        app_index += 2

        applist.append([appid, version])

    return ip_address, port, region, timestamp, applist

# Example usage
contentserver_info = {
    'ip_address': '192.168.1.100',
    'port': 8080,
    'region': 'US',
    'timestamp': 1623276000
}
applist = "34123132\x001\x00\x004342\x00333\x00\x003\x001287653\x00\x00"

packed_info = ""
packed_info += contentserver_info['ip_address'] + '\x00'
packed_info += struct.pack('H', contentserver_info['port'])
packed_info += contentserver_info['region'] + '\x00'
packed_info += str(contentserver_info['timestamp']) + '\x00'
packed_info += applist

encrypted_data = "\x2b" + packed_info #utilities.encrypt(packed_info, "password")

ip_address, port, region, timestamp, received_applist = receive_heartbeat(encrypted_data, "password")
print("IP Address:", ip_address)
print("Port:", port)
print("Region:", region)
print("Timestamp:", timestamp)
print("App List:")
for appid, version in received_applist:
    print("  App ID:", appid)
    print("  Version:", version)
