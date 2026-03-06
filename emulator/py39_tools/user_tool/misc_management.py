#!/usr/bin/env python3
"""
Miscellaneous Management Functions for the Administration Client.

This module implements functions like listing a user's subscriptions.
"""
from networking import send_request_to_server
from admin_management import show_post_action_menu

def list_user_subscriptions(info_type, user_info):
    parameters = [info_type, user_info]
    try:
        response = response = send_request_to_server(b'\x20', [user_info])
        if response:
            result = int(response[0])
            if result == 0:
                subscriptions = response[1:].split(b'\x00')
                print("Subscriptions:")
                for sub in subscriptions:
                    print(sub.decode('latin-1'))
            else:
                error_message = response[1:].strip(b'\x00').decode('latin-1')
                print(f"Error: {error_message}")
        else:
            print("No response from server.")
    except Exception as e:
        print(f"Error in list_user_subscriptions: {e}")
    show_post_action_menu()

if __name__ == "__main__":
    list_user_subscriptions("info_type", "user_info")
