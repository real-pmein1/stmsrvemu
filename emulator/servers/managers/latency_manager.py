import ipaddress
import logging
import socket
import struct
import ping3
import threading

class latencyaggregater:
    logger = logging.getLogger("latencyaggr")
    """This method is meant to send a client's IP to all of the content servers and then give us the best server for the client"""
    def __init__(self, content_server_ips, content_server_port=27057):
        self.content_server_ips = content_server_ips
        self.content_server_port = content_server_port
        self.latency_results = []
        self.lock = threading.Lock()

    def send_client_ip(self, client_ip):
        # Create a UDP socket for each server
        threads = []
        for server_ip in self.content_server_ips:
            thread = threading.Thread(target=self.contact_server, args=(server_ip, client_ip))
            threads.append(thread)
            thread.start()

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        # Find the server with the lowest latency
        if self.latency_results:
            best_server = min(self.latency_results, key=lambda x: x[1])
            return best_server[0]  # Return the server IP with the lowest latency
        else:
            return None  # No response from any server

    def contact_server(self, server_ip, client_ip):
        try:
            # Create a UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)  # 3-second timeout for each server response
            self.logger.debug(f"Sending client IP: {client_ip}")
            # Create the packet with the client's IP
            packet = self.create_packet(client_ip)

            # Send the packet to the content server
            sock.sendto(packet, (server_ip, self.content_server_port))
            self.logger.debug(f"Sent client IP: {client_ip} to content server at {server_ip}:{self.content_server_port}")

            # Receive the latency result
            data, _ = sock.recvfrom(1024)
            latency = self.unpack_response_packet(data)

            # Store the result in a thread-safe manner
            with self.lock:
                self.latency_results.append((server_ip, latency))

            self.logger.debug(f"Received latency: {latency} ms from content server {server_ip}")
        except socket.timeout:
            self.logger.debug(f"Timeout: No response from content server {server_ip}")
        finally:
            sock.close()

    def create_packet(self, client_ip):
        self.logger.debug(f"client IP: {client_ip}")
        ipaddress.ip_address(client_ip)  # This will raise ValueError if the IP is invalid
        return b"\x66\x22\x44\x12" + socket.inet_aton(client_ip)  # Only the IP address in the packet

    def unpack_response_packet(self, packet):
        latency = struct.unpack('!f', packet[4:])[0]  # Unpack the float (latency)
        return latency

"""if __name__ == "__main__":
    client_ip = "8.8.8.8"  # Simulated client IP
    content_server_ips = ["192.168.3.180", "192.168.3.181", "192.168.3.182"]  # List of content server IPs

    latency_aggregater = latencyaggregater(content_server_ips)
    best_server = latency_aggregater.send_client_ip(client_ip)

    if best_server:
        print(f"The best server is: {best_server}")
    else:
        print("No suitable server found.")"""

class latencychecker:
    """This class is meant to be called from the content server or client directory server to listen for packets from CSDS"""
    logger = logging.getLogger("latencychk")
    def __init__(self, port):
        self.server_ip = "0.0.0.0"
        self.server_port = port

    def start(self):
        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.server_ip, self.server_port))
        self.logger.debug(f"Content server listening on {self.server_ip}:{self.server_port}")

        while True:
            data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes

            if data[0:4] == b"\x66\x22\x44\x12":
                client_ip = socket.inet_ntoa(data[4:8])
                self.logger.debug(f"Received client IP: {client_ip} from {addr}")

                latency = self.ping_client(client_ip)
                if latency is not None:
                    latency_packet = self.create_response_packet(client_ip, latency)
                    sock.sendto(latency_packet, addr)
                    self.logger.debug(f"Sent latency {latency:.2f} ms to {addr}")
                else:
                    self.logger.warning(f"Failed to ping {client_ip}")

    def ping_client(self, client_ip, count=4, timeout=0.5):
        latencies = []
        threads = []
        lock = threading.Lock()

        # Ping in separate threads to speed up
        def ping_worker():
            latency = ping3.ping(client_ip, timeout=timeout)
            if latency:
                with lock:
                    latencies.append(latency * 1000)  # Convert to milliseconds

        for _ in range(count):
            thread = threading.Thread(target=ping_worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if latencies:
            return sum(latencies) / len(latencies)  # Return average latency
        return None

    def create_response_packet(self, client_ip, latency):
        client_ip_bytes = socket.inet_aton(client_ip)
        latency_bytes = struct.pack('!f', latency)  # Pack latency as float
        packet = client_ip_bytes + latency_bytes
        return packet


"""if __name__ == "__main__":
    latency_check = latencychecker() # port 27057
    latency_check.start()"""