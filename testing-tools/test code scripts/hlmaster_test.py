import socket
import time

def send_heartbeat(server_info):
    # Emulate sending a heartbeat to the master server
    print("Sending heartbeat:", server_info)

def emulate_hlds_server(config):
    server_ip = config['server_ip']
    server_port = config['server_port']
    master_server_ip = config['master_server_ip']
    master_server_port = config['master_server_port']
    server_type = config['server_type']

    server_info = {
        'ip_address': server_ip,
        'port': server_port,
        'server_type': server_type,
        'timestamp': int(time.time())
    }

    # Create a TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect to the master server
    sock.connect((master_server_ip, master_server_port))

    while True:
        # Send the heartbeat packet to the master server
        heartbeat_packet = b'0\n'
        heartbeat_packet += "\\protocol\\43\\challange\\1234567\\max\\12\\players\10\\gamedir\\valve\\map\\test.bsp\\dedicated\\0\\password\\0\\os\\w\n"
        sock.sendall(heartbeat_packet)

        # Emulate processing other server tasks
        # ...

        # Emulate sending a heartbeat to the master server every 30 minutes
        time.sleep(1800)

if __name__ == "__main__":
    # Configuration
    config = {
        'server_ip': '127.0.0.1',
        'server_port': 27015,
        'master_server_ip': '127.0.0.1',
        'master_server_port': 27010,
        'server_type': 'HLDS'
    }

    emulate_hlds_server(config)
