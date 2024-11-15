import sys

from globals import RECORD_VERSION, STEAM_VERSION
#   from user_management import name_suggestion_menu
from utilities import clear_console


def servermanagement_menu():
    options = {
            1:  "Restart Server Menu",
            2:  "Server Statistics Menu",
            3:  "Change Blob (CCDB & CDR/Content Description Record)",
            4:  "Emulator Configuration Menu",
            5:  "Edit White/Black IP Listing",
            6:  "Name Suggestion Menu",
            #7:  "Upload/Download Menu",
            8:  "Check for Server Updates",
            'x':"Exit"
    }

    while True:
        clear_console()
        print("\nServer Management Menu:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()

        choice = input("Enter a number or 'x' to select an option: ")

        if choice.isdigit():
            choice = int(choice)
        if choice == 0:
            print("Going back...")
        elif choice == 1:
            server_restart_menu()
        elif choice == 2:
            print("Server Statistics Menu is not yet implemented.")
        elif choice == 3:
            print("Change Blob (CCDB & CDR) Menu is not yet implemented.")
        elif choice == 4:
            print("Emulator Configuration Menu is not yet implemented.")
        elif choice == 5:
            edit_ip_list_menu()
        elif choice == 6:
            name_suggestion_menu()
        # elif choice == 7:
        #    upload_download_menu()
        elif choice == 8:
            print("Checking for server updates...")
        elif choice == 'x':
            sys.exit("Exiting program...")
        else:
            print("Invalid option. Please try again.")


def server_restart_menu():
    print("\nServer Restart Menu:")
    print("Use this Menu to restart individual servers or to restart the entire server.")
    print("1.) Restart All")
    print("2.) Restart Authentication Server")
    print("3.) Restart Directory Server")
    print("4.) Restart Configuration Server")
    print("5.) Restart Content Server")
    print("6.) Restart Client Update Server")
    print("7.) Restart CSER Server")
    print("8.) Restart Validation Server")
    print("9.) Restart Master Server")
    print("10.) Restart Harvest Server")
    print("11.) Restart VTT & Cafe Master Servers")
    print("12.) Restart CM Servers")
    if STEAM_VERSION < 14:
        print("13.) Restart VAC1 Server")
    if RECORD_VERSION == 0:
        print("14.) Restart Beta 1 (2002 Beta Steam) Authentication Server")
        print("15.) Restart FTP Server")
    print("16.) Restart Administration Server")
    print()
    print("0.) Go Back")
    print("X.) Exit")
    print()

    choice = input("Enter a number, '0' to return or 'x' to exit: ")
    if choice == '0':
        return
    elif choice == 'x':
        sys.exit("Exiting program...")


def edit_ip_list_menu():
    options = {
            1:"Edit White Listed IP Addresses",
            2:"Edit Black Listed IP Addresses"
    }
    while True:
        clear_console()
        print(f"\nSelect An Option For Managing Black Listed and White Listed IP Addresses:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()

        choice = input("Enter a number, '0' to return, or 'x' to exit: ")
        if choice == '0':
            break
        elif choice == 'x':
            sys.exit("Exiting program...")
        elif choice.isdigit() and int(choice) in options:
            print(f"You selected: {options[int(choice)]}")
            if int(choice) == 1:
                upload_blobs_menu()
        else:
            print("Invalid option. Please try again.")


def upload_download_menu():
    options = {
            1:"Upload Blobs Menu",
            2:"Download Client Statistics Menu",
            3:"Upload Package File",
            4:"Upload Application Menu",
            5:"Upload Email Template",
            6:"Upload to FTP"
    }
    while True:
        clear_console()
        print(f"\nSelect An Option To Continue:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()

        choice = input("Enter a number, '0' to return, or 'x' to exit: ")
        if choice == '0':
            break
        elif choice == 'x':
            sys.exit("Exiting program...")
        elif choice.isdigit() and int(choice) in options:
            print(f"You selected: {options[int(choice)]}")
            if int(choice) == 1:
                upload_blobs_menu()
        else:
            print("Invalid option. Please try again.")


def upload_blobs_menu():
    options = {
            1:"Upload First Blob (CCR/CCDB)",
            2:"Upload Second Blob (CDR/CDDB)"
    }
    while True:
        clear_console()
        print(f"\nSelect An Option To Upload A Blob:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()

        choice = input("Enter a number, '0' to return, or 'x' to exit: ")
        if choice == '0':
            break
        elif choice == 'x':
            sys.exit("Exiting program...")
        elif choice.isdigit() and int(choice) in options:
            print(f"You selected: {options[int(choice)]}")
            if int(choice) == 1:
                upload_blobs_menu()
        else:
            print("Invalid option. Please try again.")

def name_suggestion_menu():
    options = {
            1:"Edit Suggestion Prepends (<prepend>username)",
            2:"Edit Suggestion Append (username<append>)"
    }
    while True:
        clear_console()
        print(f"\nSelect The Following Option To Make Changes:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()

        choice = input("Enter a number, '0' to return, or 'x' to exit: ")
        if choice == '0':
            break
        elif choice == 'x':
            sys.exit("Exiting program...")
        elif choice.isdigit() and int(choice) in options:
            print(f"You selected: {options[int(choice)]}")
            if int(choice) == 1:
                pass
        else:
            print("Invalid option. Please try again.")