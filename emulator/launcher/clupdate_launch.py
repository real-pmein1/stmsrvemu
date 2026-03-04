# launcher/clupdate_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.clientupdateserver import ClientUpdateServer

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-ClientUpdateServer')

    config = read_config()

    # Use standalone_parent_initializer for ClientUpdateServer (server_type=6)
    utils.standalone_parent_initializer(server_type=6)
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting ClientUpdateServer---")

    server_port_key = 'client_update_server_port' 
    server_port = int(config.get(server_port_key, 0))
    if server_port == 0:
        log.error(f"Port for ClientUpdateServer ({server_port_key}) not found or invalid in config.")
        return

    server_instance = ClientUpdateServer(server_port, config)
    
    server_thread = threading.Thread(target=server_instance.start, name="ClientUpdateServerThread")
    server_thread.daemon = True
    server_thread.start()
    log.info(f"ClientUpdateServer started on port {server_port}")

    try:
        while True:
            time.sleep(60)
            log.debug("Launcher keep-alive for ClientUpdateServer.")
    except KeyboardInterrupt:
        log.info("Launcher for ClientUpdateServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop()
    finally:
        log.info("ClientUpdateServer launcher finished.")

if __name__ == "__main__":
    main()
