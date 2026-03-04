# launcher/validation_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.validationserver import ValidationServer

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-ValidationServer')

    config = read_config()

    # Using server_type=0 for full initialization, similar to AdminServer,
    # as ValidationServer is critical and may require full setup.
    # If a more specific server_type is identified for ValidationServer, this can be adjusted.
    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting ValidationServer---")

    server_port_key = 'validation_port' 
    server_port = int(config.get(server_port_key, 0))
    if server_port == 0:
        log.error(f"Port for ValidationServer ({server_port_key}) not found or invalid in config.")
        return

    server_instance = ValidationServer(server_port, config)
    
    server_thread = threading.Thread(target=server_instance.start, name="ValidationServerThread")
    server_thread.daemon = True
    server_thread.start()
    log.info(f"ValidationServer started on port {server_port}")

    try:
        while True:
            time.sleep(60)
            log.debug("Launcher keep-alive for ValidationServer.")
    except KeyboardInterrupt:
        log.info("Launcher for ValidationServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop()
    finally:
        log.info("ValidationServer launcher finished.")

if __name__ == "__main__":
    main()
