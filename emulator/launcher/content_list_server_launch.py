# launcher/content_list_server_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.contentlistserver import ContentListServer # Corrected import

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-ContentListServer')

    config = read_config()

    # Use standalone_parent_initializer, assuming type 3 for CSDS components
    utils.standalone_parent_initializer(server_type=3) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting ContentListServer---")

    server_port_key = 'content_list_server_port' 
    server_port = int(config.get(server_port_key, 0)) 
    if server_port == 0:
        log.error(f"Port for ContentListServer ({server_port_key}) not found or invalid in config.")
        return

    server_instance = ContentListServer(server_port, config) 
    
    server_thread = threading.Thread(target=server_instance.start, name="ContentListServerThread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"ContentListServer started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for ContentListServer.")
    except KeyboardInterrupt:
        log.info("Launcher for ContentListServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("ContentListServer launcher finished.")

if __name__ == "__main__":
    main()
