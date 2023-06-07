import sys
import msvcrt #for keyboard escape key watcher
import os

def check_python_version():
    # Get the major and minor version numbers
    major_version = sys.version_info[0]
    minor_version = sys.version_info[1]

    # Check if the version is Python 2.7
    if major_version == 2 and minor_version == 7:
        pass
    # Check if the version is lower than Python 2.7
    else:
        print("You must use a version of Python 2.7 in order to run this script")
        print("Stopping Execution\n Press Escape to close...")
        while True:
            if msvcrt.kbhit() and ord(msvcrt.getch()) == 27:  # 27 is the ASCII code for Escape
                os._exit(0)
    
