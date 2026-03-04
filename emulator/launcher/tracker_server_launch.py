# launcher/tracker_server_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.trackerserver_beta import TrackerServer # Using TrackerServer from trackerserver_beta

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-TrackerServer')

    config = read_config()

    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting TrackerServer---")

    server_port_key = 'tracker_server_port' 
    # Default Tracker port is often 1200 or 27015 for some games.
    # Check emulator.ini or config.py for the actual key.
    server_port = int(config.get(server_port_key, 0)) 
    if server_port == 0:
        log.error(f"Port for TrackerServer ({server_port_key}) not found or invalid in config.")
        return

    # TrackerServer constructor might be (port, config) or need specific params.
    # Assuming (port, config) for now.
    server_instance = TrackerServer(server_port, config) 
    
    server_thread = threading.Thread(target=server_instance.start, name="TrackerServerThread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"TrackerServer started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for TrackerServer.")
    except KeyboardInterrupt:
        log.info("Launcher for TrackerServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("TrackerServer launcher finished.")

if __name__ == "__main__":
    main()
