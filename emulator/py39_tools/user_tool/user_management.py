#!/usr/bin/env python3
"""
User Management Module for the Administration Client.

This module provides a class with functions to manage user accounts,
ban/unban users, change user info, manage subscriptions, etc.
It uses the networking.send_request_to_server function with the new packet format.
"""

import binascii
import hashlib
import json
import logging
import os
import re
import struct
import sys
from datetime import timedelta

from networking import (
    send_request_to_server,
    request_full_dirserver_json,
    request_add_dirserver_entry,
    request_del_dirserver_entry,
)
from utilities import clear_console, display_menu

class user_management:
    def __init__(self):
        self.current_userid = 0
        self.username = ""
        self.email_address = ""

    def remove_user(self, commandid):
        parameters = [self.current_userid]
        try:
            response = send_request_to_server(commandid, parameters)
            if response == b'\x00':
                print("User removed successfully.")
            else:
                print(f"Error: {response.decode('latin-1')}")
                self.current_userid = None
        except Exception as e:
            print(f"Exception in remove_user: {e}")
        self.select_steam_menu()

    def ban_user(self, commandid):
        ban_duration = input("How long should the user be banned for (Format 'xxdays xxhours'): ").strip()
        try:
            days, hours = map(int, re.findall(r'\d+', ban_duration))
            ban_duration_seconds = int(timedelta(days=days, hours=hours).total_seconds())
        except Exception as e:
            print(f"Invalid duration format: {e}")
            return
        parameters = [self.current_userid, str(ban_duration_seconds)]
        try:
            response = send_request_to_server(commandid, parameters)
            if response:
                result = int(response[0])
                if result == 0:
                    print("User banned successfully.")
                else:
                    error_message = response[1:].strip(b'\x00').decode('latin-1')
                    print(f"Error: {error_message}")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in ban_user: {e}")
        self.show_post_action_menu()

    def change_user_info(self, command_code, action):
        if action == "question":
            question_list = {
                "What is your mother's maiden name?": "What is your mother's maiden name?",
                "What is the name of your pet?": "What is the name of your pet?",
                "Who was your childhood hero?": "Who was your childhood hero?",
                "What city were you born in?": "What city were you born in?",
                "What is the name of your school?": "What is the name of your school?",
                "What is your favorite team?": "What is your favorite team?"
            }
            selected_items = display_menu(question_list, items_per_page=6, ismulti=False, list_only=False)
            selected_question = selected_items[0] if selected_items else None
            if selected_question:
                print(f"Selected Question: {selected_question}")
            else:
                print("Exited without selection.")
        new_info = input(f"Please enter the new {action}: ").strip()
        if action == "password":
            salt = os.urandom(8)
            hashed_password = hashlib.sha1(salt[:4] + new_info.encode() + salt[4:]).digest()
            hashed_password_hex = binascii.hexlify(hashed_password).decode()
            salt_hex = binascii.hexlify(salt).decode()
            new_info = [salt_hex, hashed_password_hex]
        elif action == "answer":
            salt = os.urandom(8)
            hashed_answer = hashlib.sha1(salt[:4] + new_info.encode() + salt[4:]).digest()
            salted_answertoguestion_digest = binascii.hexlify(hashed_answer).decode()
            salt_hex = binascii.hexlify(salt).decode()
            new_info = [selected_question, salt_hex, salted_answertoguestion_digest]
        parameters = [self.current_userid] + new_info
        try:
            response = send_request_to_server(command_code, parameters)
            if response:
                result = int(response[0])
                if result == 0:
                    print(f"{action.capitalize()} changed successfully.")
                else:
                    error_message = response[1:].strip(b'\x00').decode('latin-1')
                    print(f"Error: {error_message}")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in change_user_info: {e}")
        self.show_post_action_menu()

    def add_subscription(self, commandid):
        print("Enter subscription IDs (comma separated):")
        subscription_ids = input("Subscription IDs: ").strip()
        subscription_ids_list = [s.strip() for s in subscription_ids.split(',')]
        parameters = [self.current_userid, str(len(subscription_ids_list))] + subscription_ids_list
        try:
            response = send_request_to_server(commandid, parameters)
            if response:
                result = int(response[0])
                if result == 0:
                    print("Subscriptions added successfully.")
                else:
                    error_message = response[1:].strip(b'\x00').decode('latin-1')
                    print(f"Error: {error_message}")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in add_subscription: {e}")
        self.show_post_action_menu()

    def display_subscription_list(self, commandid, as_menu=False):
        try:
            response = send_request_to_server(commandid, [self.current_userid])
            if response:
                subscription_count = struct.unpack('>I', response[:4])[0]
                subscription_data = response[4:].decode('utf-8').split('|')
                if subscription_count == 0:
                    print(f"No subscriptions found for user {self.username}.")
                    return
                if not as_menu:
                    print(f"Subscriptions for {self.username}:")
                    for subscription in subscription_data:
                        parts = subscription.split(',')
                        if len(parts) >= 2:
                            print(f"Subscription ID: {parts[0]}, Subscription Name: {parts[1]}")
                    input("Press Enter to return to the menu.")
                else:
                    return subscription_data
            else:
                print("No response from server.")
                return []
        except Exception as e:
            print(f"Exception in display_subscription_list: {e}")
            return []

    def remove_subscription(self, commandid):
        subscriptions = self.display_subscription_list(commandid, as_menu=True)
        if not subscriptions:
            return
        options = [f"Subscription ID: {sub.split(',')[0]}, Subscription Name: {sub.split(',')[1]}"
                   for sub in subscriptions if ',' in sub]
        selected_items = display_menu(options, items_per_page=25, ismulti=True)
        if not selected_items:
            print("No subscriptions selected.")
            return
        parameters = [self.current_userid, str(len(selected_items))] + selected_items
        try:
            response = send_request_to_server(commandid, parameters)
            if response:
                result = int(response[0])
                if result == 0:
                    print("Subscriptions removed successfully.")
                else:
                    error_message = response[1:].strip(b'\x00').decode('latin-1')
                    print(f"Error: {error_message}")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in remove_subscription: {e}")
        self.show_post_action_menu()

    def manage_subs_menu(self, commandid):
        while True:
            clear_console()
            print("Subscription Management Menu")
            print("1. List Subscriptions")
            print("2. Add Subscription")
            print("3. Remove Subscription")
            print("4. List Guest Passes")
            print("5. Add Guest Pass")
            print("6. Remove Guest Pass")
            print("0. Back")
            choice = input("Select: ").strip()
            if choice == '1':
                resp = request_list_user_subscriptions(self.current_userid)
                print(resp)
                input("Press Enter...")
            elif choice == '2':
                sub = input("Subscription ID: ")
                print(request_add_subscription(self.current_userid, sub))
                input("Press Enter...")
            elif choice == '3':
                sub = input("Subscription ID to remove: ")
                print(request_remove_subscription(self.current_userid, sub))
                input("Press Enter...")
            elif choice == '4':
                print(request_list_guest_passes(self.current_userid))
                input("Press Enter...")
            elif choice == '5':
                gp = input("Guest Pass ID: ")
                print(request_add_guest_pass(self.current_userid, gp))
                input("Press Enter...")
            elif choice == '6':
                gp = input("Guest Pass ID to remove: ")
                print(request_remove_guest_pass(self.current_userid, gp))
                input("Press Enter...")
            elif choice == '0':
                break
            else:
                print("Invalid")

    def list_all_users(self, commandid):
        try:
            response = send_request_to_server(commandid, [])
            if response:
                user_count = struct.unpack('>I', response[:4])[0]
                user_data = response[4:].decode('utf-8').split('|')
                if user_count == 0:
                    print("No users found.")
                    return None
                options = [f"ID: {data.split(',')[0]}, Username: {data.split(',')[1]}, Email: {data.split(',')[2]}"
                           for data in user_data if len(data.split(',')) >= 3]
                selected_index = display_menu(options, items_per_page=25)
                selected_info = options[selected_index]
                user_id = selected_info.split(',')[0].split(':')[1].strip()
                print(f"Selected User ID: {user_id}")
                return user_id
            else:
                print("No response from server.")
                return None
        except Exception as e:
            print(f"Exception in list_all_users: {e}")
            return None

    def add_vac_ban(self, commandid):
        print("Enter VAC ban details:")
        starting_appid = input("Enter the starting AppID: ").strip()
        while not starting_appid.isdigit():
            starting_appid = input("Invalid AppID. Enter the starting AppID: ").strip()
        ending_appid = input("Enter the ending AppID: ").strip()
        while not ending_appid.isdigit():
            ending_appid = input("Invalid AppID. Enter the ending AppID: ").strip()
        ban_days = input("Enter amount of days: ").strip()
        ban_hours = input("Enter amount of hours: ").strip()
        try:
            ban_duration_seconds = int(timedelta(days=int(ban_days), hours=int(ban_hours)).total_seconds())
        except Exception as e:
            print(f"Invalid duration: {e}")
            return
        parameters = [self.current_userid, starting_appid, ending_appid, str(ban_duration_seconds)]
        try:
            response = send_request_to_server(commandid, parameters)
            if response:
                if response.startswith(b'error:'):
                    print(response.decode('latin-1'))
                else:
                    print(f"Successfully added VAC ban to AccountID: {self.current_userid} for AppID Range {starting_appid} to {ending_appid} for {ban_days} days {ban_hours} hours")
                    self.current_userid = struct.unpack_from("I", response, 0)[0]
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in add_vac_ban: {e}")
        self.show_post_action_menu()

    def parse_vac_bans(self, formatted_list):
        vac_ban_entries = formatted_list.strip('|').split('|')
        parsed_bans = []
        for entry in vac_ban_entries:
            try:
                ban_id, start_appid, end_appid, length = entry.split(',')
                parsed_bans.append((int(ban_id), int(start_appid), int(end_appid), int(length)))
            except Exception as e:
                print(f"Error parsing ban entry: {entry} - {e}")
        return parsed_bans

    def remove_vac_ban(self, commandid):
        parameters = [self.current_userid]
        try:
            response = send_request_to_server(b'\x1f', parameters)
            if response:
                if not response.startswith(b"error:"):
                    vac_bans_buffer = response[1:].decode('latin-1')
                    vac_bans = vac_bans_buffer.strip('|').split('|')
                    if vac_bans:
                        print("VAC Bans for the user:")
                        for idx, ban in enumerate(vac_bans):
                            try:
                                ban_id, start_appid, end_appid, ban_length = ban.split(',')
                                print(f"{idx+1}. Ban ID: {ban_id}, Start AppID: {start_appid}, End AppID: {end_appid}, Length: {ban_length} seconds")
                            except Exception as e:
                                print(f"Error parsing ban at index {idx+1}: {e}")
                        choice = input("Enter the number of the ban to remove or 0 to go back: ").strip()
                        if choice.isdigit() and int(choice) > 0 and int(choice) <= len(vac_bans):
                            ban_id = vac_bans[int(choice)-1].split(',')[0]
                            parameters = [self.current_userid, ban_id]
                            remove_response = send_request_to_server(b'\x17', parameters)
                            if remove_response:
                                remove_result = int(remove_response)
                                if remove_result == 0:
                                    print("VAC ban removed successfully.")
                                else:
                                    print(f"Error: {remove_response.decode('latin-1')}")
                            else:
                                print("No response from server.")
                        elif choice == '0':
                            return
                        else:
                            print("Invalid choice.")
                    else:
                        print("No VAC bans found for the user.")
                else:
                    print(f"Error: {response.decode('latin-1')}")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in remove_vac_ban: {e}")
        self.show_post_action_menu()

    def beta1_list_all_users(self, commandid):
        try:
            response = send_request_to_server(commandid, [])
            if response:
                user_count = struct.unpack('>I', response[:4])[0]
                user_data = response[4:].decode('latin-1').split('|')
                if user_count == 0:
                    print("No users found.")
                    return
                users = {f"User ID: {data.split(',')[0]}, Username: {data.split(',')[1]}":
                         f"{data.split(',')[0]}, {data.split(',')[1]}" for data in user_data if len(data.split(',')) >= 2}
                selected_items = display_menu(users, items_per_page=10, ismulti=False, list_only=False)
                if selected_items:
                    selected_user = selected_items[0].split(', ')
                    self.current_userid = selected_user[0]
                    self.username = selected_user[1]
                    print(f"Selected User ID: {self.current_userid}, Username: {self.username}")
                else:
                    print("Exited without selection.")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in beta1_list_all_users: {e}")

    def beta1_get_uniqueid_by_email(self, commandid):
        email = input("Enter the email address: ").strip()
        try:
            response = send_request_to_server(commandid, [email])
            if response:
                print(f"UniqueID: {response.decode('latin-1')}")
                self.email_address = email
                self.current_userid = response.decode('latin-1')
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in beta1_get_uniqueid_by_email: {e}")
        self.show_post_action_menu()

    def beta1_get_email_by_uniqueid(self, commandid):
        uniqueid = input("Enter the unique ID: ").strip()
        try:
            response = send_request_to_server(commandid, [uniqueid])
            if response:
                print(f"Email: {response.decode('latin-1')}")
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in beta1_get_email_by_uniqueid: {e}")
        self.show_post_action_menu()

    def beta1_list_user_subscriptions(self, commandid):
        uniqueid = input("Enter the unique ID: ").strip()
        try:
            response = send_request_to_server(commandid, [uniqueid])
            if response:
                print("User's Subscriptions:")
                # This implementation may need further processing depending on server format
                print(response.decode('latin-1'))
            else:
                print("No response from server.")
        except Exception as e:
            print(f"Exception in beta1_list_user_subscriptions: {e}")
        self.show_post_action_menu()

    def beta1_remove_subscription(self, commandid):
        uniqueid = input("Enter the unique ID: ").strip()
        subid = input("Enter the subscription ID: ").strip()
        try:
            response = send_request_to_server(commandid, [uniqueid, subid])
            if response == b"\x00":
                print("Subscription removed successfully.")
            else:
                print(response.decode('latin-1'))
        except Exception as e:
            print(f"Exception in beta1_remove_subscription: {e}")

    def show_post_action_menu(self):
        while True:
            print("1. Perform Another Action")
            print("2. Select a Different User Account to Manage")
            print("0. Main Menu")
            print("x. Quit")
            choice = input("Enter your choice: ").strip()
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
            print("7.) List All VAC Bans")
            print("8.) Ban A User")
            print("9.) Remove User Account")
            print()
            print("0.) Go Back to Management Menu")
            print("X.) Exit")
            print()
            choice = input("Enter your choice: ").strip()
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
            choice = input("Enter your choice: ").strip()
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

    def user_action_menu(self):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Manage User Account")
            print("2.) Manage User Subscriptions & Gifts")
            print("3.) Manage User Community Information")
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()
            choice = input("Enter your choice: ").strip()
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
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()
            choice = input("Enter your choice: ").strip()
            commandid = b"\x02"
            if choice == '1':
                self.manage_user_menu(commandid)
            elif choice == '2':
                self.manage_subs_menu(commandid)
            elif choice == '0':
                break
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def send_email_query(self, email_address):
        try:
            response = send_request_to_server(b'\x0A', [email_address])
            if response:
                parts = response.split(b'|')
                user_count = int(parts[0])
                if user_count > 1:
                    clear_console()
                    print(f"Found {user_count} accounts associated with email: {email_address}")
                    options = [f"User ID: {user.split(b',')[0].decode('latin-1')}, Username: {user.split(b',')[1].decode('latin-1')}"
                               for user in parts[1:]]
                    selected_index = display_menu(options, 25)
                    selected_user_id, username = parts[selected_index+1].split(b',')
                    print(f"Selected User ID: {selected_user_id.decode('latin-1')}")
                    self.username = username.decode('latin-1')
                    self.email_address = email_address
                    return selected_user_id.decode('latin-1')
                elif user_count == 1:
                    user_id, username = parts[1].split(b',')
                    print(f"User found - User ID: {user_id.decode('latin-1')}, Username: {username.decode('latin-1')}, Email: {email_address}")
                    self.username = username.decode('latin-1')
                    self.email_address = email_address
                    return user_id.decode('latin-1')
                else:
                    print("No users found.")
                    return False
            else:
                print("No response from server.")
                return False
        except Exception as e:
            logging.error(f"Error during communication with the server: {e}")
            return False

    def send_username_query(self, username):
        try:
            response = send_request_to_server(b'\x0B', [username])
            if response:
                parts = response.split(b'|')
                user_count = int(parts[0])
                if user_count > 1:
                    clear_console()
                    print(f"Multiple users found for username: {username}")
                    options = [f"User ID: {user.split(b',')[0].decode('latin-1')}, Username: {user.split(b',')[1].decode('latin-1')}"
                               for user in parts[1:]]
                    selected_index = display_menu(options, 25)
                    selected_user_id, email_address = parts[selected_index+1].split(b',')
                    print(f"Selected User ID: {selected_user_id.decode('latin-1')}")
                    self.username = username
                    self.email_address = email_address.decode('latin-1')
                    return selected_user_id.decode('latin-1')
                elif user_count == 1:
                    user_id, email_address = parts[1].split(b',')
                    print(f"User found - User ID: {user_id.decode('latin-1')}, Username: {username}")
                    self.username = username
                    self.email_address = email_address.decode('latin-1')
                    return user_id.decode('latin-1')
                else:
                    print("No users found.")
                    return False
            else:
                print("No response from server.")
                return False
        except Exception as e:
            logging.error(f"Error during communication with the server: {e}")
            return False

    def send_userid_query(self, user_id):
        try:
            response = send_request_to_server(b'\x0C', [str(user_id)])
            if response:
                if response.endswith(b'\x00'):
                    print(response.decode('utf-8').strip('\x00'))
                    return None
                user_details = response.decode('utf-8').split('|')
                self.username = user_details[0]
                self.email_address = user_details[1]
                return user_id
            else:
                print("No response from server.")
                return None
        except Exception as e:
            print(f"Exception in send_userid_query: {e}")
            return None

    def list_all_users_menu(self):
        try:
            response = send_request_to_server(b'\x0D', ['padding1', 'padding2'])
            if response:
                user_count = struct.unpack('>I', response[:4])[0]
                user_data = response[4:].decode('utf-8').split('|')
                if user_count == 0:
                    print("No users found.")
                    return None
                options = [f"ID: {user.split(',')[0]}, Username: {user.split(',')[1]}, Email: {user.split(',')[2]}"
                           for user in user_data if len(user.split(',')) >= 3]
                selected_index = display_menu(options, items_per_page=25)
                selected_info = options[selected_index]
                user_id = selected_info.split(',')[0].split(':')[1].strip()
                return user_id
            else:
                print("No response from server.")
                return None
        except Exception as e:
            print(f"Exception in list_all_users_menu: {e}")
            return None

    def show_post_action_menu(self):
        while True:
            print("1. Perform Another Action")
            print("2. Select a Different User Account to Manage")
            print("0. Main Menu")
            print("x. Quit")
            choice = input("Enter your choice: ").strip()
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
            print("7.) List All VAC Bans")
            print("8.) Ban A User")
            print("9.) Remove User Account")
            print()
            print("0.) Go Back to Management Menu")
            print("X.) Exit")
            print()
            choice = input("Enter your choice: ").strip()
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
            choice = input("Enter your choice: ").strip()
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

    def user_action_menu(self):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Manage User Account")
            print("2.) Manage User Subscriptions & Gifts")
            print("3.) Manage User Community Information")
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()
            choice = input("Enter your choice: ").strip()
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
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()
            choice = input("Enter your choice: ").strip()
            commandid = b"\x02"
            if choice == '1':
                self.manage_user_menu(commandid)
            elif choice == '2':
                self.manage_subs_menu(commandid)
            elif choice == '0':
                break
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

    def send_email_query(self, email_address):
        try:
            response = send_request_to_server(b'\x0A', [email_address])
            if response:
                parts = response.split(b'|')
                user_count = int(parts[0])
                if user_count > 1:
                    clear_console()
                    print(f"Found {user_count} accounts associated with email: {email_address}")
                    options = [f"User ID: {user.split(b',')[0].decode('latin-1')}, Username: {user.split(b',')[1].decode('latin-1')}"
                               for user in parts[1:]]
                    selected_index = display_menu(options, 25)
                    selected_user_id, username = parts[selected_index+1].split(b',')
                    print(f"Selected User ID: {selected_user_id.decode('latin-1')}")
                    self.username = username.decode('latin-1')
                    self.email_address = email_address
                    return selected_user_id.decode('latin-1')
                elif user_count == 1:
                    user_id, username = parts[1].split(b',')
                    print(f"User found - User ID: {user_id.decode('latin-1')}, Username: {username.decode('latin-1')}, Email: {email_address}")
                    self.username = username.decode('latin-1')
                    self.email_address = email_address
                    return user_id.decode('latin-1')
                else:
                    print("No users found.")
                    return False
            else:
                print("No response from server.")
                return False
        except Exception as e:
            logging.error(f"Error during email query: {e}")
            return False

    def send_username_query(self, username):
        try:
            response = send_request_to_server(b'\x0B', [username])
            if response:
                parts = response.split(b'|')
                user_count = int(parts[0])
                if user_count > 1:
                    clear_console()
                    print(f"Multiple users found for username: {username}")
                    options = [f"User ID: {user.split(b',')[0].decode('latin-1')}, Username: {user.split(b',')[1].decode('latin-1')}"
                               for user in parts[1:]]
                    selected_index = display_menu(options, 25)
                    selected_user_id, email_address = parts[selected_index+1].split(b',')
                    print(f"Selected User ID: {selected_user_id.decode('latin-1')}")
                    self.username = username
                    self.email_address = email_address.decode('latin-1')
                    return selected_user_id.decode('latin-1')
                elif user_count == 1:
                    user_id, email_address = parts[1].split(b',')
                    print(f"User found - User ID: {user_id.decode('latin-1')}, Username: {username}")
                    self.username = username
                    self.email_address = email_address.decode('latin-1')
                    return user_id.decode('latin-1')
                else:
                    print("No users found.")
                    return False
            else:
                print("No response from server.")
                return False
        except Exception as e:
            logging.error(f"Error during username query: {e}")
            return False

    def send_userid_query(self, user_id):
        try:
            response = send_request_to_server(b'\x0C', [str(user_id)])
            if response:
                if response.endswith(b'\x00'):
                    print(response.decode('utf-8').strip('\x00'))
                    return None
                user_details = response.decode('utf-8').split('|')
                self.username = user_details[0]
                self.email_address = user_details[1]
                return user_id
            else:
                print("No response from server.")
                return None
        except Exception as e:
            print(f"Exception in send_userid_query: {e}")
            return None

    def list_all_users_menu(self):
        try:
            response = send_request_to_server(b'\x0D', ['padding1', 'padding2'])
            if response:
                user_count = struct.unpack('>I', response[:4])[0]
                user_data = response[4:].decode('utf-8').split('|')
                if user_count == 0:
                    print("No users found.")
                    return None
                options = [f"ID: {user.split(',')[0]}, Username: {user.split(',')[1]}, Email: {user.split(',')[2]}"
                           for user in user_data if len(user.split(',')) >= 3]
                selected_index = display_menu(options, items_per_page=25)
                selected_info = options[selected_index]
                user_id = selected_info.split(',')[0].split(':')[1].strip()
                return user_id
            else:
                print("No response from server.")
                return None
        except Exception as e:
            print(f"Exception in list_all_users_menu: {e}")
            return None

    def show_post_action_menu(self):
        while True:
            print("1. Perform Another Action")
            print("2. Select a Different User Account to Manage")
            print("0. Main Menu")
            print("x. Quit")
            choice = input("Enter your choice: ").strip()
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
            print("7.) List All VAC Bans")
            print("8.) Ban A User")
            print("9.) Remove User Account")
            print()
            print("0.) Go Back to Management Menu")
            print("X.) Exit")
            print()
            choice = input("Enter the number of your choice: ").strip()
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
            choice = input("Enter the number of your choice: ").strip()
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

    def user_action_menu(self):
        while True:
            clear_console()
            print("\nSelect an option:")
            print("1.) Manage User Account")
            print("2.) Manage User Subscriptions & Gifts")
            print("3.) Manage User Community Information")
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()
            choice = input("Enter the number of your choice: ").strip()
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
            print()
            print("0.) Go Back")
            print("X.) Exit")
            print()
            choice = input("Enter the number of your choice: ").strip()
            commandid = b"\x02"
            if choice == '1':
                self.manage_user_menu(commandid)
            elif choice == '2':
                self.manage_subs_menu(commandid)
            elif choice == '0':
                break
            elif choice.lower() == 'x':
                sys.exit("Exiting program...")
            else:
                print("Invalid choice.")

def main_cli():
    while True:
        clear_console()
        print("Administration CLI")
        print("1) User Management")
        print("2) Directory Server Management")
        print("3) Administrator Management")
        print("4) Subscription Management")
        print("0) Exit")
        choice = input("Select: ")
        if choice == '1':
            um = user_management()
            um.select_user_menu()
        elif choice == '2':
            directory_server_management_menu()
        elif choice == '3':
            admin_management_menu()
        elif choice == '4':
            subscription_management_menu()
        elif choice == '0':
            break
        else:
            print("Invalid option")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main_cli()


def subscription_management_menu():
    user_id = int(input("Target user ID: "))
    while True:
        clear_console()
        print("Subscription Management Menu")
        print("1. List Subscriptions")
        print("2. Add Subscription")
        print("3. Remove Subscription")
        print("4. List Guest Passes")
        print("5. Add Guest Pass")
        print("6. Remove Guest Pass")
        print("0. Back")
        choice = input("Select: ")
        if choice == '1':
            resp = request_list_user_subscriptions(user_id)
            print(resp)
            input("Press Enter...")
        elif choice == '2':
            sub = input("Subscription ID: ")
            print(request_add_subscription(user_id, sub))
            input("Press Enter...")
        elif choice == '3':
            sub = input("Subscription ID to remove: ")
            print(request_remove_subscription(user_id, sub))
            input("Press Enter...")
        elif choice == '4':
            print(request_list_guest_passes(user_id))
            input("Press Enter...")
        elif choice == '5':
            gp = input("Guest Pass ID: ")
            print(request_add_guest_pass(user_id, gp))
            input("Press Enter...")
        elif choice == '6':
            gp = input("Guest Pass ID to remove: ")
            print(request_remove_guest_pass(user_id, gp))
            input("Press Enter...")
        elif choice == '0':
            break
        else:
            print("Invalid")

def _fetch_dirservers():
    data = request_full_dirserver_json()
    try:
        return json.loads(data) if data else []
    except Exception:
        return []

def list_dirserver_categories():
    servers = _fetch_dirservers()
    cats = sorted({srv.get('server_type') for srv in servers})
    print("Categories:")
    for c in cats:
        print(f" - {c}")
    input("Press Enter to continue...")

def list_all_dirservers():
    servers = _fetch_dirservers()
    if not servers:
        print("No servers returned")
    else:
        for srv in servers:
            print(srv)
    input("Press Enter to continue...")

def list_dirservers_by_category():
    category = input("Enter category: ")
    servers = [s for s in _fetch_dirservers() if s.get('server_type') == category]
    for srv in servers:
        print(srv)
    input("Press Enter to continue...")

def add_dirserver():
    wan = input("WAN IP: ")
    lan = input("LAN IP: ")
    prt = input("Port: ")
    cat = input("Category: ")
    details = {'wan_ip': wan, 'lan_ip': lan, 'port': int(prt), 'server_type': cat}
    rsp = request_add_dirserver_entry(json.dumps(details).encode('utf-8'))
    print(rsp if rsp else "No response")
    input("Press Enter to continue...")

def remove_dirserver():
    key = input("Key (WAN:Port): ")
    cat = input("Category: ")
    parts = key.split(":")
    identifier = {'wan_ip': parts[0], 'lan_ip': parts[0], 'port': int(parts[1]) if len(parts)>1 else 0, 'server_type': cat}
    rsp = request_del_dirserver_entry(json.dumps(identifier).encode('utf-8'))
    print(rsp if rsp else "No response")
    input("Press Enter to continue...")

def edit_dirserver():
    print("Edit server entry")
    key = input("Existing key (WAN:Port): ")
    cat = input("Existing Category: ")
    parts = key.split(":")
    identifier = {'wan_ip': parts[0], 'lan_ip': parts[0], 'port': int(parts[1]) if len(parts)>1 else 0, 'server_type': cat}
    request_del_dirserver_entry(json.dumps(identifier).encode('utf-8'))
    print("Enter new details:")
    add_dirserver()

def directory_server_management_menu():
    while True:
        clear_console()
        print("Directory Server List Manager")
        print("1) List all categories")
        print("2) List all servers")
        print("3) List servers in a category")
        print("4) Add server to category")
        print("5) Remove server from list")
        print("6) Edit server entry")
        print("0) Back")
        ch = input("Select: ")
        if ch == '1':
            list_dirserver_categories()
        elif ch == '2':
            list_all_dirservers()
        elif ch == '3':
            list_dirservers_by_category()
        elif ch == '4':
            add_dirserver()
        elif ch == '5':
            remove_dirserver()
        elif ch == '6':
            edit_dirserver()
        elif ch == '0':
            break
        else:
            print("Invalid option")
            input("Press Enter to continue...")

def _prompt_admin_rights():
    return input("Rights bitfield: ")

def list_admins_cli():
    resp = request_list_admins()
    if resp:
        for name, rights in resp:
            print(f"{name} rights={rights}")
    else:
        print("No data or error")

def create_admin_cli():
    user = input("Username: ")
    pw = input("Password: ")
    rights = _prompt_admin_rights()
    print(request_create_admin(user, pw, rights))

def edit_admin_permissions_cli():
    user = input("Username: ")
    rights = _prompt_admin_rights()
    print(request_edit_admin_rights(user, rights))

def remove_admin_cli():
    user = input("Username to remove: ")
    print(request_remove_admin(user))

def change_admin_username_cli():
    old = input("Current username: ")
    new = input("New username: ")
    print(request_change_admin_username(old, new))

def change_admin_password_cli():
    user = input("Username: ")
    pw = input("New password: ")
    print(request_change_admin_password(user, pw))

def change_admin_email_cli():
    user = input("Username: ")
    em = input("New email: ")
    print(request_change_admin_email(user, em))

def admin_management_menu():
    while True:
        clear_console()
        print("Administrator Management")
        print("1) List admins")
        print("2) Create admin")
        print("3) Edit admin permissions")
        print("4) Remove admin")
        print("5) Change username")
        print("6) Change password")
        print("7) Change email")
        print("0) Back")
        choice = input("Select: ")
        if choice == '1':
            list_admins_cli(); input("Press Enter...")
        elif choice == '2':
            create_admin_cli(); input("Press Enter...")
        elif choice == '3':
            edit_admin_permissions_cli(); input("Press Enter...")
        elif choice == '4':
            remove_admin_cli(); input("Press Enter...")
        elif choice == '5':
            change_admin_username_cli(); input("Press Enter...")
        elif choice == '6':
            change_admin_password_cli(); input("Press Enter...")
        elif choice == '7':
            change_admin_email_cli(); input("Press Enter...")
        elif choice == '0':
            break
        else:
            print("Invalid option")
            input("Press Enter...")
