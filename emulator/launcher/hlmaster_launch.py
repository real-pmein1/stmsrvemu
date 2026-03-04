# launcher/hlmaster_launch.py (MasterServer Launcher)
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.masterserver import MasterServer

def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-MasterServer')

    config = read_config()

    # Using server_type=0 for full initialization.
    utils.standalone_parent_initializer(server_type=0) 
    
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip
    
    log.info(f"---Starting MasterServer---")

    server_port_key = 'master_server_port' # Or specific like 'hlmaster_port' if distinguished
    server_port = int(config.get(server_port_key, 27010)) # Default HL1 master port
    if server_port == 0:
        log.error(f"Port for MasterServer ({server_port_key}) not found or invalid in config.")
        # Attempting a common fallback if the primary key isn't found
        server_port_key = 'hlmaster_port'
        server_port = int(config.get(server_port_key, 27010)) 
        if server_port == 0:
             log.error(f"Fallback port for MasterServer ({server_port_key}) also not found or invalid.")
             return

    # MasterServer might have a specific constructor or might be a list of instances
    # for different game types. This launcher will start one instance.
    # Assuming MasterServer constructor takes (port, config, game_type_or_similar_param)
    # For a generic master, game_type might be None or a default.
    # From emulator.py, it's often MasterServer(port, config, is_hl2=False) for HL1.
    server_instance = MasterServer(server_port, config, is_hl2=False) # Assuming HL1 master for this
    
    server_thread = threading.Thread(target=server_instance.start, name="MasterServerThread")
    server_thread.daemon = True
    server_thread.start()
    log.info(f"MasterServer (HL1) started on port {server_port}")

    # If HL2 master runs on a different port or needs a separate instance:
    # server_port_key_hl2 = 'hl2master_port'
    # server_port_hl2 = int(config.get(server_port_key_hl2, 27011)) # Default HL2 master port
    # if server_port_hl2 != 0 and server_port_hl2 != server_port:
    #     server_instance_hl2 = MasterServer(server_port_hl2, config, is_hl2=True)
    #     server_thread_hl2 = threading.Thread(target=server_instance_hl2.start, name="HL2MasterServerThread")
    #     server_thread_hl2.daemon = True
    #     server_thread_hl2.start()
    #     log.info(f"MasterServer (HL2) started on port {server_port_hl2}")


    try:
        while True:
            time.sleep(60)
            log.debug("Launcher keep-alive for MasterServer.")
    except KeyboardInterrupt:
        log.info("Launcher for MasterServer shutting down...")
        if hasattr(server_instance, 'stop') and callable(getattr(server_instance, 'stop')):
            server_instance.stop()
        # if 'server_instance_hl2' in locals() and hasattr(server_instance_hl2, 'stop'):
        #    server_instance_hl2.stop()
    finally:
        log.info("MasterServer launcher finished.")

if __name__ == "__main__":
    main()
