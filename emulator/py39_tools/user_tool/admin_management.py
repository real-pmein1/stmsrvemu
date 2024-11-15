import sys

from networking import send_request_to_server
from utilities import clear_console


def admin_management_menu():
    while True:
        clear_console()
        print("\nAdministrator Management Menu:")
        print("1. Change Admin Password")
        print("2. Change Admin Username")
        print("3. Create New Admin")
        print("4. Edit Admin Permissions")
        print("5. Remove Administrator")
        print("6. List Administrators")
        print()
        print("0. Go Back to Main Menu")
        print("x. Exit")
        print()

        choice = input("Enter your choice: ")

        if choice == '1':
            change_password_menu()
        elif choice == '2':
            change_username_menu()
        elif choice == '3':
            create_new_admin()
        elif choice == '4':
            edit_admin_permissions()
        elif choice == '5':
            remove_admin()
        elif choice == '6':
            list_administrators()
        elif choice == '0':
            main_menu()
            break
        elif choice.lower() == 'x':
            sys.exit("Exiting program...")
        else:
            print("Invalid choice. Please try again.")


def list_administrators():
    response = send_request_to_server('\x36', [],)

    if response[0] == '\x00':
        num_admins = int.from_bytes(response[1:5], 'little')
        admins_info = response[5:].split('\x00')

        print(f"Number of administrators: {num_admins}")
        for i in range(num_admins):
            admin_info = admins_info[i * 3:(i + 1) * 3]
            userid, username, permissions = admin_info
            print(f"Admin {i + 1}:")
            print(f"  UserID: {userid}")
            print(f"  Username: {username}")
            print(f"  Permissions: {permissions}")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def change_password_menu():
    while True:
        clear_console()
        print("\nChange Password Menu:")
        print("1. Change Own Password")
        print("2. Change Other Admin Password")
        print()
        print("0. Go Back")
        print("x. Exit")
        print()

        choice = input("Enter your choice: ")

        if choice == '1':
            change_own_password()
        elif choice == '2':
            change_other_admin_password()
        elif choice == '0':
            admin_management_menu()
            break
        elif choice.lower() == 'x':
            sys.exit("Exiting program...")
        else:
            print("Invalid choice. Please try again.")


def change_own_password():
    new_password = input("Enter your new password: ")
    parameters = [new_password]
    response = send_request_to_server('\x31\x01', parameters)

    if response[0] == '\x00':
        print("Password changed successfully.")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def change_other_admin_password():
    username = input("Enter the username of the admin whose password you want to change: ")
    new_password = input("Enter the new password for that user: ")
    parameters = [username, new_password]
    response = send_request_to_server('\x31\x02', parameters)

    if response[0] == '\x00':
        print("Password changed successfully.")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def change_username_menu():
    username = input("Enter the current username of the admin: ")
    new_username = input("Enter the new username: ")
    parameters = [username, new_username]
    response = send_request_to_server('\x32', parameters)

    if response[0] == '\x00':
        print("Username changed successfully.")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def create_new_admin():
    username = input("Enter the new admin's username: ")
    password = input("Enter the new admin's password: ")
    permissions = input("Enter the new admin's permissions (as a bitwise integer): ")
    parameters = [username, password, permissions]
    response = send_request_to_server('\x33', parameters)

    if response[0] == '\x00':
        print("New admin created successfully.")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def edit_admin_permissions():
    username = input("Enter the username of the admin whose permissions you want to edit: ")
    new_permissions = input("Enter the new permissions (as a bitwise integer): ")
    parameters = [username, new_permissions]
    response = send_request_to_server('\x34', parameters)

    if response[0] == '\x00':
        print("Permissions updated successfully.")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def remove_admin():
    username = input("Enter the username of the admin to remove: ")
    parameters = [username]
    response = send_request_to_server('\x35', parameters)

    if response[0] == '\x00':
        print("Admin removed successfully.")
    else:
        error_message = response[1:].strip('\x00')
        print(f"Error: {error_message}")

    show_post_action_menu()


def show_post_action_menu():
    while True:
        print("\n1. Perform Another Action")
        print("2. Return to Admin Management")
        print("0. Main Menu")
        print("x. Quit")

        choice = input("Enter your choice: ")

        if choice == '1':
            return  # This will return to the previous menu
        elif choice == '2':
            admin_management_menu()
            break
        elif choice == '0':
            main_menu()
            break
        elif choice.lower() == 'x':
            sys.exit("Exiting program...")
        else:
            print("Invalid choice. Please try again.")