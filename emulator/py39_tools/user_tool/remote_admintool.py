import os
import curses
import curses.textpad

from getpass import getpass

from globals import server_ip, server_port, username, configuration

from networking import perform_handshake_and_authenticate
from server_management import servermanagement_menu
from user_management import user_management

"""from server_management import servermanagement_menu
from user_management import adminmanagement_menu, usermanagement_menu"""

config = configuration.read_config()

# Load or prompt for configuration
# Load or prompt for configuration
def load_configuration():
    try:
        adminserverip = config['adminserverip']
        adminserverport = int(config['adminserverport'])
        adminusername = config['adminusername']
        adminpassword = config['adminpassword']
        server_ip = adminserverip
        server_port = adminserverport
        username = adminusername
        if adminpassword == "" or adminusername == "" or adminserverip == "0.0.0.0":
            return prompt_for_configuration()
    except KeyError:
        return prompt_for_configuration()
    #return prompt_for_configuration()
    return adminserverip, adminserverport, adminusername, adminpassword

def prompt_for_configuration():
    curses.wrapper(inner_prompt_for_configuration)

def inner_prompt_for_configuration(screen):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)

    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    curses.curs_set(1)

    labels = [
        "Enter the admin server IP: ",
        "Enter the admin server port: (Default: 32666) ",
        "Enter the admin username: ",
        "Enter the admin password: "
    ]
    positions = [(2, 2), (3, 2), (4, 2), (5, 2)]
    inputs = ["", "", "", ""]
    max_input_length = 50

    for i, (label, pos) in enumerate(zip(labels, positions)):
        screen.addstr(pos[0], pos[1], label)

    current_input = 0
    input_positions = [(pos[0], pos[1] + len(label)) for label, pos in zip(labels, positions)]

    while True:
        for i, (pos, inp) in enumerate(zip(input_positions, inputs)):
            screen.attron(curses.color_pair(3) if i == current_input else curses.color_pair(4))
            screen.addstr(pos[0], pos[1], inp + " " * (max_input_length - len(inp)))
            screen.attroff(curses.color_pair(3) if i == current_input else curses.color_pair(4))

        screen.move(input_positions[current_input][0], input_positions[current_input][1] + len(inputs[current_input]))
        screen.refresh()

        key = screen.getch()

        if key == curses.KEY_MOUSE:
            _, mx, my, _, _ = curses.getmouse()
            for i, (y, x) in enumerate(input_positions):
                if y == my and x <= mx < x + max_input_length:
                    current_input = i
                    screen.move(y, x + len(inputs[i]))

        elif key in [curses.KEY_BACKSPACE, 127, 8]:
            y, x = screen.getyx()
            if x > input_positions[current_input][1]:
                # Remove character and update screen
                offset = x - input_positions[current_input][1]
                inputs[current_input] = inputs[current_input][:offset - 1] + inputs[current_input][offset:]
                screen.addstr(y, input_positions[current_input][1], inputs[current_input].ljust(max_input_length))
                screen.move(y, x - 1)

        elif key == curses.KEY_UP or key == 353:  # Shift+Tab
            current_input = (current_input - 1) % len(inputs)
            screen.move(input_positions[current_input][0], input_positions[current_input][1] + len(inputs[current_input]))

        elif key == curses.KEY_DOWN or key == 9:  # Tab
            current_input = (current_input + 1) % len(inputs)
            screen.move(input_positions[current_input][0], input_positions[current_input][1] + len(inputs[current_input]))

        elif key in [curses.KEY_ENTER, 10, 13]:
            if current_input == 3:
                break
            else:
                current_input = (current_input + 1) % len(inputs)

        elif 32 <= key <= 126:  # Printable characters
            y, x = screen.getyx()
            if len(inputs[current_input]) < max_input_length:
                offset = x - input_positions[current_input][1]
                inputs[current_input] = inputs[current_input][:offset] + chr(key) + inputs[current_input][offset:]
                screen.addstr(y, input_positions[current_input][1], inputs[current_input].ljust(max_input_length))
                screen.move(y, x + 1)

    adminserverip = inputs[0]
    adminserverport = int(inputs[1] or 32666)
    adminusername = inputs[2]
    adminpassword = inputs[3]

    configuration.save_config_value('adminserverip', adminserverip)
    configuration.save_config_value('adminserverport', adminserverport)
    configuration.save_config_value('adminusername', adminusername)
    configuration.save_config_value('adminpassword', adminpassword)

    return adminserverip, adminserverport, adminusername, adminpassword


def main_menu(screen):
    curses.curs_set(0)
    screen.keypad(1)

    menu = [
        "User Management",
        "Server Management",
        "Admin User Management",
        "Print Connection Information",
        "Quit"
    ]

    current_row = 0

    while True:
        screen.clear()
        screen.addstr(1, 2, f"You are Successfully Authenticated")
        screen.addstr(2, 2, f"Server: {server_ip}:{server_port}")
        screen.addstr(3, 2, f"User: {username}")

        for idx, row in enumerate(menu):
            x = 2
            y = 5 + idx
            if idx == current_row:
                screen.attron(curses.color_pair(1))
                screen.addstr(y, x, row)
                screen.attroff(curses.color_pair(1))
            else:
                screen.addstr(y, x, row)

        key = screen.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(menu) - 1:
            current_row += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            if current_row == 0:
                usermgmt_instance = user_management()
                curses.endwin()
                usermgmt_instance.select_steam_menu()

            elif current_row == 1:
                servermanagement_menu()
            elif current_row == 2:
                #adminmanagement_menu()
                pass
            elif current_row == 3:
                pass
                #print_connection_info()
            elif current_row == 4:
                break

        screen.refresh()

def start_curses_app():
    curses.wrapper(main_curses)

def main_curses(screen):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)

    server_ip, server_port, username, password = load_configuration()
    if perform_handshake_and_authenticate(config):
        main_menu(screen)

if __name__ == "__main__":
    start_curses_app()