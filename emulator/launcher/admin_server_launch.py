# launcher/admin_server_launch.py
import logging
import os
import sys
import threading 
import time

# Adjust path to access root-level modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.administrationserver import administrationserver # Corrected import

def main():
    # Basic Logging Setup
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout) 
    ])
    log = logging.getLogger('Launcher-AdminServer')

    # Load Configuration
    config = read_config()

    # Initialize Utilities
    if not hasattr(globalvars, 'current_os'):
        import platform
        globalvars.current_os = platform.system()
        
    globalvars.aio_server = True 

    if not hasattr(globalvars, 'cs_region'): 
        globalvars.cs_region = 'US' if config.get("override_ip_country_region", "false").lower() == 'false' else config.get("override_ip_country_region").upper()
        globalvars.cellid = int(config.get("cellid", 0))
        globalvars.dir_ismaster = config.get("dir_ismaster", "true").lower()

    # Initialize utils (loads emulator.ini, prepares globalvars)
    # utils.initialize() # This is called by standalone_parent_initializer
    
    # For standalone servers, use standalone_parent_initializer with a server_type ID.
    # AdminServer doesn't have a specific type ID in the standalone_parent_initializer's current design (0-6).
    # So, we'll replicate the necessary parts of parent_initializer or call initialize() and finalinitialize() directly.
    # Let's follow the template's Option 2 more closely.
    
    utils.initialize(server_type=0) # server_type=0 is for main emulator, implies full init. For Admin, this might be okay.
                                     # Or use a new server_type ID if appropriate, e.g. 7 for Admin.
                                     # Given template, calling initialize() directly is the pattern.

    config['server_ip'] = globalvars.server_ip # Ensure config object has updated IPs
    config['public_ip'] = globalvars.public_ip
    
    # Finalize initialization (loads blobs, etc.)
    # The log object for finalinitialize should be the launcher's log.
    utils.finalinitialize(log, server_type=0) # server_type=0 for Admin specific finalization parts if any.

    log.info(f"---Starting AdminServer---")

    server_port_key = 'admin_server_port' 
    server_port = int(config.get(server_port_key, 32666)) # Default if not found
    if server_port == 0:
        log.error(f"Port for AdminServer ({server_port_key}) not found or invalid in config.")
        return

    server_instance = administrationserver(server_port, config) # Pass config to server
    
    server_thread = threading.Thread(target=server_instance.start, name="AdminServerThread")
    server_thread.daemon = True 
    server_thread.start()
    log.info(f"AdminServer started on port {server_port}")

    try:
        while True:
            time.sleep(60) 
            log.debug("Launcher keep-alive for AdminServer.")
    except KeyboardInterrupt:
        log.info("Launcher for AdminServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop() 
    finally:
        log.info("AdminServer launcher finished.")

if __name__ == "__main__":
    main()
