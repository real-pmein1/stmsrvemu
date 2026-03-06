import sys

from networking import (
    request_list_admins,
    request_edit_admin_rights,
    request_remove_admin,
    request_create_admin,
    request_change_admin_username,
    request_change_admin_password,
    request_change_admin_email,
)
from remote_admintool import main_menu
from utilities import clear_console


def admin_management_menu():
    while True:
        clear_console()
        print("\nAdministrator Management Menu:")
        print("1. List Administrators")
        print("2. Create New Admin")
        print("3. Edit Admin Permissions")
        print("4. Remove Administrator")
        print("5. Change Admin Username")
        print("6. Change Admin Password")
        print("7. Change Admin Email")
        print()
        print("0. Go Back to Main Menu")
        print("x. Exit")
        print()
        choice = input("Enter your choice: ")

        if choice == '1':
            list_administrators()
        elif choice == '2':
            create_new_admin()
        elif choice == '3':
            edit_admin_permissions()
        elif choice == '4':
            remove_admin()
        elif choice == '5':
            change_username_menu()
        elif choice == '6':
            change_password_menu()
        elif choice == '7':
            change_email_menu()
        elif choice == '0':
            main_menu()
            break
        elif choice.lower() == 'x':
            sys.exit("Exiting program...")
        else:
            print("Invalid choice. Please try again.")
            input("Press Enter to continue...")


def list_administrators():
    admins = request_list_admins()
    if admins is None:
        print("Error retrieving administrator list.")
    elif not admins:
        print("No administrators found.")
    else:
        print(f"Number of administrators: {len(admins)}")
        for idx, (username, rights) in enumerate(admins, 1):
            print(f"Admin {idx}: {username} - Rights: {rights}")
    input("Press Enter to continue...")


def create_new_admin():
    username = input("Enter new admin username: ")
    password = input("Enter password: ")
    rights = input("Enter rights bitfield: ")
    response = request_create_admin(username, password, rights)
    print(response if response else "No response from server.")
    input("Press Enter to continue...")

def change_password_menu():
    username = input("Enter admin username: ")
    new_password = input("Enter new password: ")
    response = request_change_admin_password(username, new_password)
    print(response if response else "No response from server.")
    input("Press Enter to continue...")

def change_email_menu():
    username = input("Enter admin username: ")
    new_email = input("Enter new email: ")
    response = request_change_admin_email(username, new_email)
    print(response if response else "No response from server.")
    input("Press Enter to continue...")


def edit_admin_permissions():
    username = input("Enter the username of the admin whose permissions you want to edit: ")
    new_permissions = input("Enter the new permissions (bitfield): ")
    response = request_edit_admin_rights(username, new_permissions)
    print(response if response else "No response from server.")
    input("Press Enter to continue...")


def remove_admin():
    username = input("Enter the username of the admin to remove: ")
    response = request_remove_admin(username)
    print(response if response else "No response from server.")
    input("Press Enter to continue...")


def change_username_menu():
    old_name = input("Current username: ")
    new_name = input("New username: ")
    response = request_change_admin_username(old_name, new_name)
    print(response if response else "No response from server.")
    input("Press Enter to continue...")
