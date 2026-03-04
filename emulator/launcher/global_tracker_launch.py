import asyncio
import logging
import os
import sys
import time

# Ensure project root is on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import globalvars
import utils
from config import get_config as read_config
from servers.global_tracker_server import GlobalTrackerThread


def main():
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.StreamHandler(sys.stdout)
    ])
    log = logging.getLogger('Launcher-GlobalTracker')

    config = read_config()

    # Initialize environment similar to other standalone launchers
    utils.standalone_parent_initializer(server_type=0)
    config['server_ip'] = globalvars.server_ip
    config['public_ip'] = globalvars.public_ip

    port = int(config.get('global_tracker_port', 1300))
    log.info("---Starting GlobalTrackerServer---")

    server_thread = GlobalTrackerThread(port)
    server_thread.start()
    log.info(f"GlobalTrackerServer started on port {port}")

    try:
        while True:
            time.sleep(60)
            log.debug('Launcher keep-alive for GlobalTrackerServer.')
    except KeyboardInterrupt:
        log.info('Launcher for GlobalTrackerServer shutting down...')
    finally:
        log.info('GlobalTrackerServer launcher finished.')


if __name__ == '__main__':
    main()
