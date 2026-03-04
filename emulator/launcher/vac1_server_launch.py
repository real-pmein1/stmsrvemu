# launcher/vac1_server_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.valve_anticheat1 import VAC1Server # Corrected import

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-VAC1Server')

    config = read_config()

    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting VAC1Server---")

    server_port_key = 'vac1_server_port' 
    # VAC1 typically listens on port 27012.
    server_port = int(config.get(server_port_key, 27012)) # Default to 27012
    
    if server_port == 0: # Check if explicitly set to 0 to disable
        log.info(f"VAC1Server port set to 0 or not configured via {server_port_key}, server will not start.")
        return

    # VAC1Server constructor might be (port, config) or just (config) if port is fixed.
    # Assuming (port, config) for consistency.
    server_instance = VAC1Server(server_port, config) 
    
    server_thread = threading.Thread(target=server_instance.start, name="VAC1ServerThread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"VAC1Server started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for VAC1Server.")
    except KeyboardInterrupt:
        log.info("Launcher for VAC1Server shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("VAC1Server launcher finished.")

if __name__ == "__main__":
    main()
