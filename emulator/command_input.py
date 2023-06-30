import msvcrt
import sys


class InputManager(object):
    def __init__(self):
        self.input_buffer = ''

    def process_input(self, c):
        if c == '\r':
            # Process the entered command or perform any action
            print('\nEntered command:', self.input_buffer)
            # Clear the input buffer for next input
            self.input_buffer = ''
        elif c == '\x08':
            self.input_buffer = self.input_buffer[:-1]  # Remove the last character
        else:
            self.input_buffer += c

    def start_input(self):
        while True:
            if msvcrt.kbhit():
                char = msvcrt.getch()
                if char == '\x03':  # Handle Ctrl+C
                    break
                if sys.version_info.major == 3:
                    char = char.decode(sys.stdin.encoding)
                self.process_input(char)
                sys.stdout.write(char)  # Display the character immediately
                sys.stdout.flush()  # Flush the output to ensure it's displayed

# Create an instance of InputManager
#input_manager = InputManager()
