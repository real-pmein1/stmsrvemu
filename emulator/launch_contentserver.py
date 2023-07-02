import threading, logging, time, os, os.path, msvcrt, sys
import utilities, globalvars, emu_socket
import steamemu.logger
import python_check
from command_input import InputManager
from steamemu.config import save_config_value
from steamemu.contentserver import contentserver, csConnectionCount, app_list
from steamemu.config import read_config

global csConnectionCount, app_list
config = read_config()

# Check the Python version
python_check.check_python_version()

class CSInputManager(InputManager):
    def process_input(self, c):
        if c == '\r':
            if self.input_buffer.strip() == 'showapplist':
                print(" ")
                print("App List:")
                for app_id, version in app_list:
                    print("appid: {}\nversion: {}\n".format(app_id, version))
            elif self.input_buffer.strip() == 'connectioncount':
                print(" ")
                print("Total Number of Connections: " + str(csConnectionCount))
            elif self.input_buffer.strip() == 'exit' or self.input_buffer.strip() == 'quit':
                os._exit(0)
            else :
                print("\n Unknown Command:  " + self.input_buffer)
            self.input_buffer = ''
        elif c == '\x08':
            if self.input_buffer:
                 # Clear the last character on the screen
                sys.stdout.write('\b ')
                sys.stdout.flush()
                # Remove the last character
                self.input_buffer = self.input_buffer[:-1]
        elif c == '\x1b':
            os._exit(0)
        else:
            self.input_buffer += c #this allows for more than 1 character at a time      

#check for a peer_password, otherwise generate one
new_password = utilities.check_peerpassword()

print("Steam 2004-2011 Content Server Emulator v" + globalvars.emuversion)
print("=====================================")
print
print("**************************")
print("Server IP: " + config["server_ip"])
if config["public_ip"] != "0.0.0.0" :
    print("Public IP: " + config["public_ip"])
print("**************************")
print

log = logging.getLogger('ContentSRV')
log.info("...Starting Steam Server...\n")

#check local ip and set globalvars.serverip
utilities.checklocalipnet()

contentserver(int(config["content_server_port"]), config).start()
log.info("Steam Content Server listening on port " + str(config["content_server_port"]))
time.sleep(0.5)

log.info("Steam Content Server is ready.")

if new_password == 1 :
    log.info("New Peer Password Generated: \033[1;33m{}\033[0m".format(globalvars.peer_password))
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

input_buffer = ""
print("Press Escape to exit...")
input_manager = CSInputManager()
input_manager.start_input()

