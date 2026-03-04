# launcher/cm_udp_27014_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from steam3.cmserver_udp import CMServerUDP # Corrected import

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-CMServerUDP-27014')

    config = read_config()

    # Using server_type=0 for full initialization.
    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting CMServerUDP on port 27014---")

    server_port = 27014 # Fixed port for this CM instance
    
    # CMServerUDP constructor is (port, config, is_udp)
    # Note: The class name implies UDP, but the constructor might still take is_udp.
    # Assuming it's similar to CMServerTCP for consistency or that is_udp is handled internally.
    # Based on steam3.cmserver_udp.py, it likely just takes (port, config).
    # Let's assume its constructor is (port, config) or that is_udp is implicitly True.
    # If it takes `is_udp`, it would be `CMServerUDP(port=server_port, config=config, is_udp=True)`
    # For now, assuming (port, config)
    server_instance = CMServerUDP(port=server_port, config=config) 
    
    server_thread = threading.Thread(target=server_instance.start, name="CMServerUDP-27014-Thread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"CMServerUDP started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for CMServerUDP-27014.")
    except KeyboardInterrupt:
        log.info("Launcher for CMServerUDP-27014 shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("CMServerUDP-27014 launcher finished.")

if __name__ == "__main__":
    main()
