import argparse
import logging
import os
import sys
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import utils
import globalvars
from config import get_config as read_config
from servers.authserver import authserver
from servers.configserver import configserver
from servers.directoryserver import directoryserver
from servers.contentserver import contentserver
from servers.contentlistserver import ContentListServer
from servers.cserserver import CSERServer

SERVER_MAP = {
    'auth': authserver,
    'config': configserver,
    'directory': directoryserver,
    'content': contentserver,
    'contentlist': ContentListServer,
    'cser': CSERServer
}


def main():
    parser = argparse.ArgumentParser(description="Launch a single Steam server")
    parser.add_argument('server', choices=SERVER_MAP.keys(), help='Server type to launch')
    args = parser.parse_args()

    config = read_config()
    utils.standalone_parent_initializer()

    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format)
    log = logging.getLogger('Launcher')

    server_class = SERVER_MAP[args.server]
    port_key = f"{args.server}_server_port"
    port = int(config.get(port_key, 0))
    if port == 0:
        log.error(f"Port for {args.server} server not configured")
        return

    log.info(f"Starting {args.server} server on port {port}")
    server = server_class(port, config)
    thread = threading.Thread(target=server.start, name=f"{args.server}ServerThread")
    thread.daemon = True
    thread.start()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        if hasattr(server, 'stop'):
            server.stop()


if __name__ == '__main__':
    main()

