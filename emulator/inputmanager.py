import msvcrt
import sys

class InputManager(object):
    def __init__(self):
        self.input_buffer = ''

    def process_input(self, c):
        if c == '\r':
            print('\nEntered command:', self.input_buffer)
            self.input_buffer = ''
        elif c == '\x08':
            if self.input_buffer:
                 # Clear the last character on the screen
                sys.stdout.write('\b ')
                sys.stdout.flush()
                # Remove the last character
                self.input_buffer = self.input_buffer[:-1]
        else:
            self.input_buffer += c

    def start_input(self):
        while True:
            if msvcrt.kbhit():
                char = msvcrt.getch()
                if char == '\x03':
                    break
                if sys.version_info.major == 3:
                    char = char.decode(sys.stdin.encoding)
                self.process_input(char)
                sys.stdout.write(char)
                sys.stdout.flush()


# Usage:
#input_manager = InputManager()
#input_manager.start_input()
