# launcher/cm_tcp_27017_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from steam3.cmserver_tcp import CMServerTCP 

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-CMServerTCP-27017')

    config = read_config()

    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting CMServerTCP on port 27017---")

    server_port = 27017 
    
    server_instance = CMServerTCP(port=server_port, config=config, is_udp=False) 
    
    server_thread = threading.Thread(target=server_instance.start, name="CMServerTCP-27017-Thread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"CMServerTCP started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for CMServerTCP-27017.")
    except KeyboardInterrupt:
        log.info("Launcher for CMServerTCP-27017 shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("CMServerTCP-27017 launcher finished.")

if __name__ == "__main__":
    main()
