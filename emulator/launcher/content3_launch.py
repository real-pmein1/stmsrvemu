# launcher/content3_launch.py
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.content3server import content3server


def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level = logging.INFO, format = log_format, handlers = [
            logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-Content3Server')

    config = read_config()

    utils.standalone_parent_initializer()

    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip

    log.info("---Starting Steam3 Content Server---")

    server_port = int(config.get('content3_server_port', 0))
    if server_port == 0:
        log.error("Port for Steam3 Content Server (content3_server_port) not found or invalid in config.")
        return

    server_instance = content3server(server_port, config)
    server_instance.daemon = True
    server_instance.start()

    log.info(f"Steam3 Content Server started on port {server_port}")

    try:
        while True:
            time.sleep(60)
            log.debug("Launcher keep-alive for Steam3 Content Server.")
    except KeyboardInterrupt:
        log.info("Launcher for Steam3 Content Server shutting down...")
        server_instance.cleanup()
    finally:
        log.info("Steam3 Content Server launcher finished.")


if __name__ == "__main__":
    main()
