# launcher/cser_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.cserserver import CSERServer

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-CSERServer')

    config = read_config()

    # Use standalone_parent_initializer for CSERServer (server_type=3 for CSDS components)
    utils.standalone_parent_initializer(server_type=3)
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting CSERServer---")

    server_port_key = 'cser_server_port' 
    server_port = int(config.get(server_port_key, 0))
    if server_port == 0:
        log.error(f"Port for CSERServer ({server_port_key}) not found or invalid in config.")
        return

    server_instance = CSERServer(server_port, config)
    
    server_thread = threading.Thread(target=server_instance.start, name="CSERServerThread")
    server_thread.daemon = True
    server_thread.start()
    log.info(f"CSERServer started on port {server_port}")

    try:
        while True:
            time.sleep(60)
            log.debug("Launcher keep-alive for CSERServer.")
    except KeyboardInterrupt:
        log.info("Launcher for CSERServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop()
    finally:
        log.info("CSERServer launcher finished.")

if __name__ == "__main__":
    main()
