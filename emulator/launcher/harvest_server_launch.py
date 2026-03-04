# launcher/harvest_server_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.harvestserver import HarvestServer

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-HarvestServer')

    config = read_config()

    # Using server_type=0 for full initialization.
    utils.standalone_parent_initializer(server_type=0)
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting HarvestServer---")

    server_port_key = 'harvest_server_port' 
    # HarvestServer might not have a standard port or might be part of another system.
    # Assuming it has a configurable port for this launcher.
    # A default port (e.g., 0 to disable if not configured, or a common non-standard port)
    # might be needed if not always present in emulator.ini
    server_port = int(config.get(server_port_key, 0)) 
    if server_port == 0:
        log.error(f"Port for HarvestServer ({server_port_key}) not found, invalid, or server disabled.")
        return

    server_instance = HarvestServer(server_port, config)
    
    server_thread = threading.Thread(target=server_instance.start, name="HarvestServerThread")
    server_thread.daemon = True
    server_thread.start()
    log.info(f"HarvestServer started on port {server_port}")

    try:
        while True:
            time.sleep(60)
            log.debug("Launcher keep-alive for HarvestServer.")
    except KeyboardInterrupt:
        log.info("Launcher for HarvestServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop()
    finally:
        log.info("HarvestServer launcher finished.")

if __name__ == "__main__":
    main()
