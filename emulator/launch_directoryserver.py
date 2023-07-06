import threading, logging, time, os, os.path, msvcrt, sys
import utilities, globalvars, emu_socket
import steamemu.logger
import python_check

from command_input import InputManager
from steamemu.config import save_config_value
from steamemu.directoryserver import directoryserver, manager as dirmanager, dirConnectionCount
from steamemu.config import read_config

config = read_config()

# Check the Python version
python_check.check_python_version()

#check for a peer_password, otherwise generate one
new_password = utilities.check_peerpassword()

global dirmanager, dirConnectionCount

class DirInputManager(InputManager):
    def process_input(self, c):
        if c == '\r':
            if self.input_buffer.strip() == 'showlist':
                print(" ")
                dirmanager.print_dirserver_list()
            elif self.input_buffer.strip() == 'connectioncount':
                print(" ")
                print("Total Number of Connections: " + str(dirConnectionCount))
            elif self.input_buffer.strip() == 'exit' or self.input_buffer.strip() == 'quit':
                os._exit(0)
            else :
                print(" ")
                print('\nCustom process_input implementation:', self.input_buffer)
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
            self.input_buffer += c
                # Check if a certain word is typed


            
    
print("Steam 2004-2011 Directory Server Emulator v" + globalvars.emuversion)
print("=====================================")
print
print("**************************")
print("Server IP: " + config["server_ip"])
if config["public_ip"] != "0.0.0.0" :
    print("Public IP: " + config["public_ip"])
print("**************************")
print

log = logging.getLogger('DirectorySRV')
log.info("...Starting Steam Server...\n")

#check local ip and set globalvars.serverip
utilities.checklocalipnet()

#launch directoryserver first so servers can heartbeat the moment they launch
if globalvars.dir_ismaster == 1 :
    log.info("Steam Master General Directory Server listening on port " + str(config["dir_server_port"]))
else:
    log.info("Steam Slave General Directory Server listening on port " + str(config["dir_server_port"]))
    
directoryserver(int(config["dir_server_port"]), config).start()
#time.sleep(1.0) #give us a little more time than usual to make sure we are initialized before servers start their heartbeat
   
log.info("Steam Directory Server is ready.")

if new_password == 1 :
    log.info("New Peer Password Generated: \033[1;33m{}\033[0m".format(globalvars.peer_password))
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")
input_buffer = ""
print("Press Escape to exit...")
input_manager = DirInputManager()
input_manager.start_input()
#input_thread = threading.Thread(target=input_manager.start_input)
#input_thread.daemon = True
#input_thread.start()
    

    