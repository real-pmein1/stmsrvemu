import binascii
import hashlib
import logging
import os
import struct
import sys
import re
from datetime import timedelta

import utilities
from networking import send_request_to_server
from utilities import clear_console, display_menu


class user_management():
    current_userid = 0
    username = ""
    email_address = ""

    def remove_user(self, commandid):
        parameters = [self.current_userid]
        response = send_request_to_server(commandid, parameters)

        if response:
            if response == b'\x00':
                print("User removed successfully.")
            else:
                print(f"{response}")
                self.current_userid = None
        else:
            print("Failed to get a response from the server.")

        self.select_steam_menu()

    def ban_user(self, commandid):
        ban_duration = input("How long should the user be banned for (Format 'xxdays xxhours'): ")
        days, hours = map(int, re.findall(r'\d+', ban_duration))
        ban_duration_seconds = int(timedelta(days = days, hours = hours).total_seconds())

        parameters = [self.current_userid, str(ban_duration_seconds)]
        response = send_request_to_server(commandid, parameters)

        if response:
            result = int(response[0])
            if result == 0:
                print("User banned successfully.")
            else:
                error_message = response[1:].strip('\x00')
                print(f"Error: {error_message}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def change_user_info(self, command_code, action):
        if action is "question":
            question_list = {
                    "What is your mother's maiden name?":"What is your mother's maiden name?",
                    "What is the name of your pet?":     "What is the name of your pet?",
                    "Who was your childhood hero?":      "Who was your childhood hero?",
                    "What city were you born in?":       "What city were you born in?",
                    "What is the name of your school?":  "What is the name of your school?",
                    "What is your favorite team?":       "What is your favorite team?"
            }

            selected_items = display_menu(question_list, items_per_page = 6, ismulti = False, list_only = False)
            selected_question = selected_items[0] if selected_items else None
            if selected_question:
                print(f"Selected Question: {selected_question}")
            else:
                print("Exited without selection.")

        new_info = input(f"Please enter the new {action}: ")

        if action is "password":
            # Generate a random 8-byte salt
            salt = os.urandom(8)

            # Hash the password with the salt
            hashed_password = hashlib.sha1(salt[:4] + new_info.encode() + salt[4:]).digest()
            hashed_password_hex = binascii.hexlify(hashed_password).decode()

            # Convert salt to hex for storage
            salt_hex = binascii.hexlify(salt).decode()
            new_info = [salt_hex, hashed_password_hex]

        elif action is "answer":

            # Generate a random 8-byte salt
            salt = os.urandom(8)

            # Hash the password with the salt
            hashed_answer = hashlib.sha1(salt[:4] + new_info.encode() + salt[4:]).digest()
            salted_answertoguestion_digest = binascii.hexlify(hashed_answer).decode()

            # Convert salt to hex for storage
            salt_hex = binascii.hexlify(salt).decode()
            new_info = [selected_question, salt_hex, salted_answertoguestion_digest]

        parameters = [self.current_userid] + new_info
        response = send_request_to_server(command_code, parameters)

        if response:
            result = int(response[0])
            if result == 0:
                print(f"{action.capitalize()} changed successfully.")
            else:
                error_message = response[1:].strip('\x00')
                print(f"Error: {error_message}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def add_subscription(self, commandid):
        print("To add a subscription, enter the subscription IDs (comma separated if multiple).")
        subscription_ids = input("Please enter the subscription IDs (comma separated): ")

        subscription_ids_list = subscription_ids.split(',')

        parameters = [self.current_userid, str(len(subscription_ids_list))] + subscription_ids_list
        response = send_request_to_server(commandid, parameters)

        if response:
            result = int(response[0])
            if result == 0:
                print("Subscriptions added successfully.")
            else:
                error_message = response[1:].strip('\x00')
                print(f"Error: {error_message}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def display_subscription_list(self, commandid, as_menu = False):
        response = send_request_to_server(commandid, [self.current_userid])

        if response:
            # Parse the number of subscriptions
            subscription_count = struct.unpack('>I', response[:4])[0]
            subscription_data = response[4:].decode('utf-8').split('|')

            if subscription_count == 0:
                print(f"No subscriptions found for user {self.username}.")
                return
            if not as_menu:
                # Display the subscription list
                print(f"Subscriptions for {self.username}:")
                for subscription in subscription_data:
                    sub_id, sub_name = subscription.split(',')
                    print(f"Subscription ID: {sub_id}, Subscription Name: {sub_name}")

                # Prompt to return to menu
                print("\nPress enter to return to the menu.")
                input()
            else:
                return subscription_data
        else:
            print("Failed to get a response from the server.")
            return []

    def remove_subscription(self, commandid):
        subscriptions = self.display_subscription_list(as_menu = True)
        if not subscriptions:
            return

        options = [f"Subscription ID: {sub.split(',')[0]}, Subscription Name: {sub.split(',')[1]}" for sub in subscriptions]
        selected_items = display_menu(options, items_per_page = 25, ismulti = True)
        if not selected_items:
            print("No subscriptions selected.")
            return

        response = send_request_to_server(commandid, [self.current_userid, str(len(selected_items))] + selected_items)

        if response:
            result = int(response[0])
            if result == 0:
                print("Subscriptions removed successfully.")
            else:
                error_message = response[1:].strip('\x00')
                print(f"Error: {error_message}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def list_all_users(self, commandid):
        response = send_request_to_server(commandid, [])

        if response:
            result = int(response[0])
            if result == 0:
                num_users = int.from_bytes(response[1:5], 'little')
                users_info = response[5:].split('\x00')
                with open('dumped_usernames.txt', 'w') as file:
                    for i in range(num_users):
                        user_id = int.from_bytes(users_info[i * 2].encode(), 'little')
                        username = users_info[i * 2 + 1]
                        file.write(f"{user_id}\t{username}\n")
                print("User list has been dumped to dumped_usernames.txt.")
            else:
                error_message = response[1:].strip('\x00')
                print(f"Error: {error_message}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def add_vac_ban(self, commandid):
        print("VAC Ban's use a range of AppIDs to determine what games the user can no longer use secure servers on.\n"
              "For example:\n"
              "ex1.) Half-Life 1 (GoldSRC) the first AppID: 10, the last AppID: 80\n"
              "ex2.) Half-Life 2 (Source) the first AppID: 220, last AppID: 320\n"
              "ex3.) Banning a user from a single App/Game: first AppID: 10, last AppID: 10")
        print("Please enter the range of application IDs to ban the user from.")

        starting_appid = input("Enter the starting AppID: ")
        while not starting_appid.isdigit():
            print("Invalid AppID. Please enter a numeric value.")
            starting_appid = input("Enter the starting AppID: ")

        ending_appid = input("Enter the ending AppID: ")
        while not ending_appid.isdigit():
            print("Invalid AppID. Please enter a numeric value.")
            ending_appid = input("Enter the ending AppID: ")
        print("How long should the user be banned for?")
        ban_days = input("Enter Amount of days: ")
        ban_hours = input("Enter Amount of hours: ")
        ban_duration_seconds = int(timedelta(days = ban_days, hours = ban_hours).total_seconds())

        parameters = [self.current_userid, starting_appid, ending_appid, str(ban_duration_seconds)]
        response = send_request_to_server(commandid, parameters)

        if response:
            if response.startswith(b'error:'):
                print(response)
            else:
                print(f"Successfully Added Vac Bans to AccountID: {self.current_userid}\n AppID Range {starting_appid} to {ending_appid} for {ban_days}days {ban_hours}hours")
                self.current_userid = struct.unpack_from("I", response, 0)
        else:
            print("Failed to get a response from the server.")
            return  # Exit the function if no response

        self.show_post_action_menu()

    def parse_vac_bans(self, formatted_list):
        # Remove the trailing pipe '|' and split the string by '|'
        vac_ban_entries = formatted_list.strip('|').split('|')

        # Initialize an empty list to hold parsed VAC ban data
        parsed_bans = []

        # Iterate over each VAC ban entry
        for entry in vac_ban_entries:
            # Split each entry by comma to extract individual values
            ban_id, start_appid, end_appid, length = entry.split(',')

            # Convert to appropriate types (assuming they should be integers for IDs and length)
            ban_id = int(ban_id)
            start_appid = int(start_appid)
            end_appid = int(end_appid)
            length = int(length)

            # Add the parsed values as a tuple to the list
            parsed_bans.append((ban_id, start_appid, end_appid, length))

        return parsed_bans

    def remove_vac_ban(self, commandid):
        parameters = [self.current_userid]
        response = send_request_to_server(b'\x1f', parameters)

        if response:
            if not response.startswith(b"error:"):
                # Parse the VAC bans from the response, assuming it's formatted by format_vac_ban_list
                vac_bans_buffer = response[1:].decode('latin-1')  # Assuming the buffer is bytes encoded in 'latin-1'
                vac_bans = vac_bans_buffer.strip('|').split('|')  # Split the buffer by '|' and remove trailing '|'

                if vac_bans:
                    print("VAC Bans for the user:")
                    for idx, ban in enumerate(vac_bans):
                        try:
                            # Safely split each ban by ',' to get the individual values
                            ban_id, start_appid, end_appid, ban_length = ban.split(',')
                            print(f"{idx + 1}. Ban ID: {ban_id}, Start AppID: {start_appid}, End AppID: {end_appid}, Length: {ban_length} seconds")
                        except ValueError:
                            print(f"Error parsing ban at index {idx + 1}")
                            continue

                    choice = input("\nEnter the number of the ban to remove or 0 to go back: ")

                    if choice.isdigit() and 0 < int(choice) <= len(vac_bans):
                        # Get the selected ban ID
                        ban_id = vac_bans[int(choice) - 1].split(',')[0]
                        parameters = [self.current_userid, ban_id]
                        remove_response = send_request_to_server(b'\x17', parameters)

                        if remove_response:
                            remove_result = int(remove_response)
                            if remove_result == 0:
                                print("VAC ban removed successfully.")
                            else:
                                print(f"Error: {remove_response}")
                        else:
                            print("Failed to get a response from the server.")
                    elif choice == '0':
                        # Go back to the previous menu
                        return
                    else:
                        print("Invalid choice.")
                else:
                    print("No VAC bans found for the user.")
            else:
                print(f"Error: {response}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def beta1_list_all_users(self, commandid):
        response = send_request_to_server(commandid, [])
        if response:
            user_count = struct.unpack('>I', response[:4])[0]
            user_data = response[4:].decode('latin-1').split('|')
            users = {f"User ID: {data.split(',')[0]}, Username: {data.split(',')[1]}":f"{data.split(',')[0]}, {data.split(',')[1]}" for data in user_data}

            selected_items = display_menu(users, items_per_page = 10, ismulti = False, list_only = False)
            if selected_items:
                selected_user = selected_items[0].split(', ')
                self.current_userid = selected_user[0]
                self.username = selected_user[1]
                print(f"Selected User ID: {self.current_userid}, Username: {self.username}")
            else:
                print("Exited without selection.")
        else:
            print("Failed to get a response from the server.")

    def beta1_get_uniqueid_by_email(self, commandid):
        email = input("Enter the email address: ")
        response = send_request_to_server(commandid, [email])
        if response:
            print(f"UniqueID: {response}")
            self.email_address = email
            self.current_userid = response
        else:
            print("Failed to get a response from the server.")
        self.show_post_action_menu()

    def beta1_get_email_by_uniqueid(self, commandid):
        uniqueid = input("Enter the unique ID: ")
        response = send_request_to_server(commandid, [uniqueid])
        if response:
            print(f"Email: {response}")
        else:
            print("Failed to get a response from the server.")
        self.show_post_action_menu()

    def beta1_list_user_subscriptions(self, commandid):
        uniqueid = input("Enter the unique ID: ")
        response = send_request_to_server(commandid, [uniqueid])
        if response:
            print("User's Subscriptions:")
            for subscription in response:
                print(f"Subscription ID: {subscription[0]}, Subtime: {subscription[1]}")
        else:
            print("Failed to get a response from the server.")

        self.show_post_action_menu()

    def beta1_remove_subscription(self, commandid):
        uniqueid = input("Enter the unique ID: ")
        subid = input("Enter the subscription ID: ")
        response = send_request_to_server(commandid, [uniqueid, subid])
        if response == "\x00":
            print("Subscription removed successfully.")
        else:
            print(response)

    def show_post_action_menu(self):
        while True:
            print("1. Perform Another Action")
            print("2. Select a Different User Account to Manage")
            print("0. Main Menu")
            print("x. Quit")

            choice = input("Enter your choice: ")

            if choice == '1':
                self.user_action_menu()
            elif choice == '2':
                self.select_user_menu()
                break
            elif choice == '0':
                return
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice. Please try again.")

    def manage_user_menu(self, commandid):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Change User's Username")
            print("2.) Change User's Email Address")
            print("3.) Change User's Password")
            print("4.) Change User's Secret Question & Answer")
            print("5.) Add VAC Ban to Account")
            print("6.) Remove VAC Ban from Account")
            print("7.) List All Vac Bans")
            print("8.) Ban A User")
            print("9.) Remove User Account")
            print()
            print("0.) Go Back to Management Menu")
            print("X.) Exit")
            print()

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                self.change_user_info(b'\x12', 'username')
            elif choice == '2':
                self.change_user_info(b'\x13', 'email')
            elif choice == '3':
                self.change_user_info(b'\x15', 'password')
            elif choice == '4':
                self.change_user_info(b'\x14', 'answer')
            elif choice == '5':
                self.add_vac_ban(b'\x16')
            elif choice == '6':
                self.remove_vac_ban(b'\x17')
            elif choice == '7':
                self.list_vac_bans(b'\x1f')
            elif choice == '8':
                self.ban_user(b'\x18')
            elif choice == '9':
                self.remove_user(b'\x19')
            elif choice == '0':
                self.user_action_menu()
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def manage_usercommunity_menu(self, commandid):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Change User's Username")
            print("2.) Change User's Email Address")
            print("3.) Change User's Password")
            print("4.) Change User's Secret Question & Answer")
            print("4.) Modify User's Community Profile")
            print("5.) Add VAC Ban to Account")
            print("6.) Remove VAC Ban from Account")
            print("7.) Ban A User")
            print("8.) Remove User Account")
            print()
            print("0.) Go Back to Main User Menu")
            print("X.) Exit")
            print()

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                self.change_user_info(commandid + b'\x01', 'username')
            elif choice == '2':
                self.change_user_info(commandid + b'\x02', 'email')
            elif choice == '3':
                self.change_user_info(commandid + b'\x03', 'password')
            elif choice == '4':
                self.change_user_info(commandid + b'\x04', 'answer')
            elif choice == '5':
                self.add_vac_ban(commandid + b'\x05')
            elif choice == '6':
                self.remove_vac_ban(commandid + b'\x06')
            elif choice == '7':
                self.ban_user(commandid + b'\x07')
            elif choice == '8':
                self.remove_user(commandid + b'\x08')
            elif choice == '0':
                self.user_action_menu()
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def display_subscription_list(self, commandid, as_menu = False):
        response = send_request_to_server(commandid, [self.current_userid])

        if response:
            # Parse the number of subscriptions
            subscription_count = struct.unpack('>I', response[:4])[0]
            subscription_data = response[4:].decode('utf-8').split('|')

            if subscription_count == 0:
                print(f"No subscriptions found for user {self.username}.")
                return
            if as_menu == False:
                # Display the subscription list
                print(f"Subscriptions for {self.username}:")
                for subscription in subscription_data:
                    sub_id, sub_name = subscription.split(',')
                    print(f"Subscription ID: {sub_id}, Subscription Name: {sub_name}")

                # Prompt to return to menu
                print("\nPress enter to return to the menu.")
                input()
            else:
                return subscription_data
        else:
            print("Failed to get a response from the server.")

    def manage_subs_menu(self, commandid):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) List User's Subscriptions")
            print("2.) Add A Subscription to A User's Account")
            print("3.) Remove A Subscription From A User's Account")
            # print("4.) List User's Guest Passes & Gifts")
            # print("5.) Add Guest Pass to Account")
            # print("6.) Remove Guest Pass to Account")
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                self.display_subscription_list(b'\x20', True)
            elif choice == '2':
                self.add_subscription(commandid + b'\x02')
            elif choice == '3':
                self.remove_subscription(commandid + b'\x03')
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def user_action_menu(self):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Manage User Account")
            print("2.) Manage User Subscriptions & Gifts")
            print("3.) Manage User Community Information")
            # print("4.) Manage User Friends")
            # print("5.) Manage User Clans")
            # print("6.) Manage User Chatrooms")
            # print("7.) Manage User Items")
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()

            choice = input("Enter the number of your choice: ")
            commandid = b"\x01"
            if choice == '1':
                self.manage_user_menu(commandid)
            elif choice == '2':
                self.manage_subs_menu(commandid)
            elif choice == '3':
                self.manage_usercommunity_menu(commandid)
            elif choice == '0':
                break
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def beta1_user_action_menu(self):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Manage User Account")
            print("2.) Manage User Subscriptions & Gifts")
            # print("3.) Manage User Tracker Information")
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()

            choice = input("Enter the number of your choice: ")
            commandid = b"\x02"
            if choice == '1':
                self.manage_user_menu(commandid)
            elif choice == '2':
                self.manage_subs_menu(commandid)
            elif choice == '3':
                # TODO beta 1tracker management
                pass
            elif choice == '0':
                break
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def send_email_query(self, email_address):
        log = logging.getLogger('Client')
        try:
            response = send_request_to_server('\x0A', [email_address])

            if response:
                user_count, *user_data = response.split('|')
                user_count = int(user_count)

                if user_count > 1:
                    clear_console()
                    print(f"Found {user_count} accounts associated with email: {email_address}")
                    options = [f"User ID: {user.split(',')[0]}, Username: {user.split(',')[1]}" for user in user_data]
                    selected_index = display_menu(options, 25)
                    selected_user_id, username = user_data[selected_index].split(',')
                    print(f"Selected User ID: {selected_user_id}")
                    self.username = username
                    self.email_address = email_address
                    return selected_user_id
                elif user_count == 1:
                    user_id, username = user_data[0].split(',')
                    print(f"User found - User ID: {user_id}, Username: {username}, Email: {email_address}")
                    self.username = username
                    self.email_address = email_address
                    return user_id
                else:
                    print("No users found.")
                    return False
            else:
                print("No response from server or invalid response received.")
                return False

        except Exception as e:
            log.error(f"Error during communication with the server: {e}")
            return False

    def send_username_query(self, username):
        log = logging.getLogger('Client')
        try:
            response = send_request_to_server('\x0B', [username])

            if response:
                user_count, *user_data = response.split('|')
                user_count = int(user_count)
                if user_count > 1:
                    clear_console()
                    print(f"Could not find specific user with name: {username}")
                    print(f"Potential Number of users found: {user_count}")
                    options = [f"User ID: {user.split(',')[0]}, Username: {user.split(',')[1]}" for user in user_data]
                    selected_index = display_menu(options, 25)
                    selected_user_id, email_address = user_data[selected_index].split(',')
                    print(f"Selected User ID: {selected_user_id}")
                    self.username = username
                    self.email_address = email_address
                    return selected_user_id
                elif user_count == 1:
                    user_id, email_address = user_data[0].split(',')
                    print(f"Only one user found - User ID: {user_id}, Username: {username}")
                    self.username = username
                    self.email_address = email_address
                    return user_id
                else:
                    print("No users found.")
                    return False
            else:
                print("No response from server or invalid response received.")
                return False
        except Exception as e:
            log.error(f"Error during communication with the server: {e}")
            return False

    def send_userid_query(self, user_id):
        response = send_request_to_server('\x0C', [str(user_id)])

        if response:
            # Check if the response is an error message
            if response.endswith(b'\x00'):
                print(response.decode('utf-8').strip('\x00'))
                return None

            # Parse the response to get username and email
            user_details = response.decode('utf-8').split('|')
            username, email = user_details[0], user_details[1]
            self.username = username
            self.email_address = email
            return user_id
        else:
            print("Failed to get a response from the server.")
            return None

    def list_all_users_menu(self):
        response = send_request_to_server('\x0D', ['padding1', 'padding2'])

        if response:
            user_count = struct.unpack('>I', response[:4])[0]
            user_data = response[4:].decode('utf-8').split('|')

            if user_count == 0:
                print("No users found.")
                return None

            options = [f"ID: {user.split(',')[0]}, Username: {user.split(',')[1]}, Email: {user.split(',')[2]}" for user in user_data]

            selected_index = display_menu(options, items_per_page = 25)
            print(f"user management selected index: {selected_index}")
            # Extract the string from the list
            user_info = selected_index[0]

            # Split the string by commas and then by colon to get the ID
            user_id = user_info.split(',')[0].split(':')[1].strip()

            # print(user_id)  # Output: 3
            return user_id

        else:
            print("Failed to get a response from the server.")
            return None

    def list_vac_bans(self, command_code):
        parameters = [self.current_userid]
        response = send_request_to_server(command_code, parameters)

        if response:
            if not response.startswith(b"error:"):
                # Parse the VAC bans from the response, assuming it's formatted by format_vac_ban_list
                vac_bans_buffer = response[1:].decode('latin-1')  # Assuming the buffer is bytes encoded in 'latin-1'
                vac_bans = vac_bans_buffer.strip('|').split('|')  # Split the buffer by '|' and remove trailing '|'

                if vac_bans:
                    print("VAC Bans for the user:")
                    for idx, ban in enumerate(vac_bans):
                        try:
                            # Safely split each ban by ',' to get the individual values
                            ban_id, start_appid, end_appid, ban_length = ban.split(',')
                            print(f"{idx + 1}. Ban ID: {ban_id}, Start AppID: {start_appid}, End AppID: {end_appid}, Length: {ban_length} seconds")
                        except ValueError:
                            print(f"Error parsing ban at index {idx + 1}")
                            continue
                else:
                    print("No VAC Bans found!")

    def select_user_menu(self):
        while True:
            clear_console()
            utilities.print_centered_bar("Retail Steam User Managment")
            print()
            print()
            print("\nSelect an option to specify an identity to search the user:")
            print("1. Enter user's Unique UserID")
            print("2. Enter User's Username")
            print("3. Enter User's Email Address")
            print("4. Select From User List")
            print("5. Create New User")  # TODO
            print()
            print("0. Go Back")
            print("x. Exit")
            print()

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                user_id = input("Please enter the UserID: ")
                if user_id.isdigit():
                    self.current_userid = self.send_userid_query(user_id)
                    # break
                else:
                    print("Invalid UserID. It should contain only numbers.")
            elif choice == '2':
                username = input("Please enter the Username: ")
                if username.isalnum():
                    self.current_userid = self.send_username_query(username.lower())
                    # break
                else:
                    print("Invalid Username. It should contain only alphanumeric characters.")
            elif choice == '3':
                email = input("Please enter the Email address: ")
                if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    self.current_userid = self.send_email_query(email.lower())
                    # break
                else:
                    print("Invalid Email address.")
            elif choice == '4':
                self.current_userid = self.list_all_users_menu()
                # break
            elif choice == '5':
                self.create_new_user()
            elif choice == '0':
                return
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice. Please try again.")

            self.user_action_menu()

    def create_new_user(self):
        username = input("Enter New Username: ")
        email = input("Enter New User's Email: ")

        while True:
            password = input("Enter password (minimum 5 characters): ")
            if len(password) < 5:
                print("Please enter a password that is ATLEAST 5 characters long")
            else:
                break

        # Generate a random 8-byte salt
        passwordsalt = os.urandom(8)

        # Hash the password with the salt
        hashed_password = hashlib.sha1(passwordsalt[:4] + password.encode() + passwordsalt[4:]).digest()
        salted_password_digest = binascii.hexlify(hashed_password).decode()

        # Convert salt to hex for storage
        password_salt_hex = binascii.hexlify(passwordsalt).decode()
        question_list = {
                "What is your mother's maiden name?":"What is your mother's maiden name?",
                "What is the name of your pet?":     "What is the name of your pet?",
                "Who was your childhood hero?":      "Who was your childhood hero?",
                "What city were you born in?":       "What city were you born in?",
                "What is the name of your school?":  "What is the name of your school?",
                "What is your favorite team?":       "What is your favorite team?"
        }

        # Convert dictionary keys to a list for easy access
        questions = list(question_list.keys())
        selected_question = None

        while True:
            # Display the questions with numbered options
            print("Please select a security question:")
            for i, question in enumerate(questions, 1):
                print(f"{i}. {question}")
            print("0. Exit")

            # Get user input
            try:
                choice = int(input("Enter the number of your choice: "))

                # Handle exit condition
                if choice == 0:
                    return  # Exit the method if user selects 0

                # Check if the choice is valid
                if 1 <= choice <= len(questions):
                    selected_question = question_list[questions[choice - 1]]
                    break
                else:
                    print("Invalid choice. Please select a valid option.")
            except ValueError:
                print("Please enter a valid number.")
        print(f"{selected_question}\n")
        question_answer = input("Enter Answer: ")

        # Generate a random 8-byte salt
        questionsalt = os.urandom(8)

        # Hash the password with the salt
        hashed_answer = hashlib.sha1(questionsalt[:4] + question_answer.encode() + questionsalt[4:]).digest()
        salted_answertoguestion_digest = binascii.hexlify(hashed_answer).decode()

        # Convert salt to hex for storage
        answer_salt_hex = binascii.hexlify(questionsalt).decode()
        # Place this around the part where username is checked with the server
        while True:
            parameters = [f"{username}, {email}, {password_salt_hex}, {salted_password_digest}, {selected_question}, {answer_salt_hex}, {salted_answertoguestion_digest}"]
            response = send_request_to_server(b"\x0e", parameters)

            if response:
                if response.startswith(b'error:'):
                    if response.decode('latin-1') == "error:Username Is Taken":
                        print(f"Username {username} is already taken!\nPlease try a different username.")
                        username = input("Enter a different Username: ")
                        continue  # Go back to recheck the username
                else:
                    self.current_userid = struct.unpack_from("I", response, 0)
                    break  # Exit the loop once a valid username is accepted
            else:
                print("Failed to get a response from the server.")
                return  # Exit the function if no response

        self.show_post_action_menu()


    def beta1_select_user_menu(self):
        while True:
            clear_console()
            utilities.print_centered_bar("Beta 1 Steam User Managment")
            print()
            print()
            print("\nSelect an option to specify an identity to search the user:")
            print("1. Enter user's Unique UserID")
            print("2. Select From User List")
            print("3. Create New User")
            print()
            print("0. Go Back")
            print("x. Exit")
            print()

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                user_id = input("Please enter the UserID: ")
                if user_id.isdigit():
                    self.current_userid = self.send_userid_query(user_id)
                    # break
                else:
                    print("Invalid UserID. It should contain only numbers.")
            elif choice == '2':
                self.current_userid = self.current_userid = self.list_all_users_menu()
            elif choice == '3':
                self.beta1_create_new_user()
            elif choice == '0':
                return
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice. Please try again.")

            self.beta1_user_action_menu()

    def beta1_create_new_user(self):
        username = input("Enter New Username: ")

        while True:
            password = input("Enter password (minimum 6 characters): ")
            if len(password) < 6:
                print("Please enter a password that is ATLEAST 6 characters long")
            else:
                break

        # Generate a random 8-byte salt
        passwordsalt = os.urandom(8)

        # Hash the password with the salt
        hashed_password = hashlib.sha1(passwordsalt[:4] + password.encode() + passwordsalt[4:]).digest()
        salted_password_digest = binascii.hexlify(hashed_password).decode()

        # Convert salt to hex for storage
        password_salt_hex = binascii.hexlify(passwordsalt).decode()

        while True:
            parameters = [f"{username}, {password_salt_hex}, {salted_password_digest}"]
            response = send_request_to_server(b"\xbe", parameters)

            if response:
                if response.startswith(b'error:'):
                    if response.decode('latin-1') == "error:Username Is Taken":
                        print(f"Username {username} is already taken!\nPlease try a different username.")
                        username = input("Enter a different Username: ")
                        continue  # Go back to recheck the username
                else:
                    self.current_userid = struct.unpack_from("I", response, 0)
                    break  # Exit the loop once a valid username is accepted
            else:
                print("Failed to get a response from the server.")
                return  # Exit the function if no response

        self.show_post_action_menu()

    def select_steam_menu(self):
        while True:
            clear_console()
            print("\nSelect Which Steam User Database To Edit:")
            print("1. Retail Steam (Beta 2 [2003] to 2010")
            print("2. Beta 1 Steam [2002]")
            print()
            print("0. Go Back")
            print("x. Exit")
            print()

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                self.select_user_menu()
                # break
            elif choice == '2':
                self.beta1_select_user_menu()
            elif choice == '0':
                return
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice. Please try again.")