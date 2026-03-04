# launcher/cm_tcp_27014_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from steam3.cmserver_tcp import CMServerTCP # Corrected import

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-CMServerTCP-27014')

    config = read_config()

    # Using server_type=0 for full initialization.
    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting CMServerTCP on port 27014---")

    server_port = 27014 # Fixed port for this CM instance
    
    # CMServerTCP constructor is (port, config, is_udp)
    server_instance = CMServerTCP(port=server_port, config=config, is_udp=False) 
    
    server_thread = threading.Thread(target=server_instance.start, name="CMServerTCP-27014-Thread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"CMServerTCP started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for CMServerTCP-27014.")
    except KeyboardInterrupt:
        log.info("Launcher for CMServerTCP-27014 shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("CMServerTCP-27014 launcher finished.")

if __name__ == "__main__":
    main()
