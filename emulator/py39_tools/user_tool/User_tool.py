import binascii
import hashlib
import os
import re
import sys
from datetime import datetime

from sqlalchemy import Column, DECIMAL, Date, ForeignKey, Integer, String, Text, create_engine, TypeDecorator, DateTime
from sqlalchemy.orm import Session, declarative_base, scoped_session, sessionmaker

from base_dbdriver import AccountPaymentCardInfoRecord, AccountPrepurchasedInfoRecord, AccountSubscriptionsBillingInfoRecord, AccountSubscriptionsRecord, Base, SteamApplications, SteamSubApps, SteamSubscriptions, UserRegistry, VACBans


def read_config(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    config = {}
    current_section = None
    for line in lines:
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith(';'):
            continue
        # Detect section headers
        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1].strip()
            config[current_section] = {}
        elif '=' in line and current_section:
            # Parse key-value pairs
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.split(';')[0].strip()  # Remove inline comments
            config[current_section][key] = value
        # No other parsing required

    return config


# Read the configuration
config = read_config('emulator.ini')

# Retrieve the database type and filename
db_filename = config.get('config', {}).get('database')

db_host = config.get('config', {}).get('database_host')
db_port = config.get('config', {}).get('database_port')
db_user = config.get('config', {}).get('database_username')
db_password = config.get('config', {}).get('database_password')
engine = create_engine(f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_filename}')

session_factory = sessionmaker(bind = engine)
session = scoped_session(session_factory)


Base.query = session.query_property()


Base.metadata.create_all(engine)
Session = scoped_session(sessionmaker(bind = engine))


def wait_for_keypress():
    """Wait for a key press and return True if ESC is pressed."""
    try:
        # For Windows
        import msvcrt
        print("Press any key to continue (ESC to stop)...", end = "", flush = True)
        key = msvcrt.getch()
        if key == b'\x1b':  # ESC key
            return True
    except ImportError:
        # For Unix-based systems
        import tty
        import termios
        print("Press any key to continue (ESC to stop)...", end = "", flush = True)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            if key == '\x1b':  # ESC key
                return True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return False


def remove_user():
    username = input("Enter the username to remove: ")
    print()
    with Session() as session:
        user = session.query(UserRegistry).filter_by(UniqueUserName = username).first()
        if not user:
            print("User not found.")
            return

        # Remove related records
        session.query(AccountSubscriptionsRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()
        session.query(AccountPaymentCardInfoRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()
        session.query(AccountPrepurchasedInfoRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()
        session.query(AccountSubscriptionsBillingInfoRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()

        # Remove the user
        session.delete(user)
        session.commit()
        print(f"User {username} removed successfully.")


def change_user_email():
    session = Session()
    username = input("Enter the username: ")
    new_email = input("Enter the new email address: ")
    print()
    user = session.query(UserRegistry).filter_by(UniqueUserName = username).first()
    if not user:
        print("User not found.")
        return

    user.AccountEmailAddress = new_email
    session.commit()
    print(f"Email address for user {username} has been updated.")
    print()
    print()
    input("Press Enter to go back to the main menu...")
    session.close()


def add_subscription():
    session = Session()  # Ensure your session is connected to your database engine properly

    while True:
        username = input("Enter the username: ")
        print()
        user = session.query(UserRegistry).filter_by(UniqueUserName=username).first()

        if not user:
            print("User not found.")
            if input("Do you want to try adding subscriptions for another user? (y/n): ").strip().lower() != 'y':
                break
            continue

        while True:  # Loop for subscription ID input
            subscription_ids_input = input("Enter the subscription IDs separated by commas: ")
            try:
                # Attempt to convert each inputted ID to an integer
                subscription_ids = [int(sid.strip()) for sid in subscription_ids_input.split(',')]
                break  # Exit the loop if input is valid
            except ValueError:
                print()
                print("Invalid subscription ID(s) entered. Please enter only numbers separated by commas.")

        # Loop through each subscription ID and add a new record for each
        for subscription_id in subscription_ids:
            new_subscription = AccountSubscriptionsRecord(
                SubscriptionID=subscription_id,
                UserRegistry_UniqueID=user.UniqueID
            )
            session.add(new_subscription)

        # Commit all new subscriptions at once
        session.commit()
        print()
        print("Subscriptions added successfully.")
        print()
        print()

        # Ask if the user wants to add subscriptions for another user
        add_another = input("Do you want to add subscriptions for another user? (y/n): ").strip().lower()
        if add_another != 'y':
            break

    session.close()


def ban_user():
    session = Session()
    username = input("Enter the username to ban/unban: ")
    print()
    user = session.query(UserRegistry).filter_by(UniqueUserName=username).first()
    if not user:
        print("User not found.")
        session.close()
        return

    if user.Banned == 1:
        # Unban the user
        user.Banned = 0
        session.commit()
        print(f"User {username} has been unbanned.")
    else:
        # Ban the user
        user.Banned = 1
        session.commit()
        print(f"User {username} has been banned.")
    print()
    print()
    input("Press Enter to go back to the main menu...")
    session.close()


def remove_subscription_from_user():
    session = Session()
    
    while True:  # Loop for user input
        username = input("Enter the username: ")
        print()
        user = session.query(UserRegistry).filter_by(UniqueUserName=username).first()

        if not user:
            print("User not found.")
            if input("Do you want to try removing subscriptions for another user? (y/n): ").strip().lower() != 'y':
                session.close()
                return
            continue

        while True:  # Loop for subscription ID input
            sub_ids_input = input("Enter the subscription IDs to remove (comma-separated): ")
            try:
                # Attempt to convert each inputted ID to an integer
                sub_ids = [int(sub_id.strip()) for sub_id in sub_ids_input.split(",")]
                break  # Exit the loop if input is valid
            except ValueError:
                print("Invalid subscription ID(s) entered. Please enter only numbers separated by commas.")

        # Track any IDs that weren't found to inform the user
        not_found_ids = []

        # Iterate over each subscription ID to remove
        for sub_id in sub_ids:
            subscription = session.query(AccountSubscriptionsRecord).filter_by(
                UserRegistry_UniqueID=user.UniqueID, SubscriptionID=sub_id).first()
            if subscription:
                session.delete(subscription)
            else:
                not_found_ids.append(sub_id)

        session.commit()

        # Print results
        if not_found_ids:
            print()
            print(f"Some subscriptions were not found for user {username}: {', '.join(map(str, not_found_ids))}")
        print()
        print("Selected subscriptions removed successfully.")
        print()
        print()

        # Ask if the user wants to remove subscriptions for another user
        remove_another = input("Do you want to remove subscriptions for another user? (y/n): ").strip().lower()
        if remove_another != 'y':
            break

    session.close()


def list_users():
    console_height, _ = os.get_terminal_size()
    count = 0

    with open('user_list.txt', 'w') as file:
        for user in session.query(UserRegistry).all():
            line = f"ID: {user.UniqueID}, Username: {user.UniqueUserName}, Email: {user.AccountEmailAddress}\n"
            print(line, end = '')
            file.write(line)
            count += 1
            if count >= console_height - 1:
                if wait_for_keypress():
                    break
                print("\n" * (console_height - 1), end = "")
                count = 0
    print()
    print("User list has been saved to user_list.txt")
    print()
    print()
    input("Press Enter to go back to the main menu...")
    session.close()


def list_subscriptions():
    console_height, _ = os.get_terminal_size()
    count = 0

    with open('subscription_list.txt', 'w') as file:
        for subscription in session.query(SteamSubscriptions).all():
            line = f"SubscriptionID: {subscription.SubscriptionID}, Name: {subscription.Name}, ...\n"
            print(line, end = '')
            file.write(line)
            count += 1
            if count >= console_height - 1:
                if wait_for_keypress():
                    break
                print("\n" * (console_height - 1), end = "")
                count = 0

    print()
    print("Subscription list has been saved to subscription_list.txt")
    print()
    print()
    input("Press Enter to go back to the main menu...")
    session.close()


def list_user_subscriptions():
    console_height, _ = os.get_terminal_size()
    count = 0
    username = input("Enter the username: ")
    print()

    # Find the UniqueID of the user
    user_record = session.query(UserRegistry).filter(UserRegistry.UniqueUserName == username).first()
    if not user_record:
        print("User not found.")
        return

    unique_id = user_record.UniqueID

    # Retrieve all subscriptions for the user
    user_subscriptions = session.query(AccountSubscriptionsRecord).filter(AccountSubscriptionsRecord.UserRegistry_UniqueID == unique_id).all()
    print(f"Subscriptions for {username}:")

    for subscription in user_subscriptions:
        # Find subscription name in SteamSubscriptions table
        steam_subscription = session.query(SteamSubscriptions).filter(SteamSubscriptions.SubscriptionID == subscription.SubscriptionID).first()
        subscription_name = steam_subscription.Name if steam_subscription else "Unknown"

        print(f"Subscription ID: {subscription.SubscriptionID}  Subscription Name: {subscription_name}")
        count += 1
        if count >= console_height - 1:
            if wait_for_keypress():
                break
            print("\n" * (console_height - 1), end = "")
            count = 0
    print()
    print()
    input("Press Enter to go back to the main menu...")
    session.close()


def list_applications_for_subscription():
    console_height, _ = os.get_terminal_size()
    count = 0

    session = Session()
    subscription_id = input("Enter the subscription ID: ")
    print()
    sub_apps_record = session.query(SteamSubApps).filter_by(SteamSubscriptions_SubscriptionID = subscription_id).first()
    if not sub_apps_record:
        print("Subscription not found.")
        session.close()
        return

    app_list = sub_apps_record.AppList.split(',')
    print(f"Applications for Subscription ID {subscription_id}:")
    for app_id in app_list:
        steam_application = session.query(SteamApplications).filter_by(AppID = app_id).first()
        if steam_application:
            print(f"AppID: {app_id}, Name: {steam_application.Name}")
            count += 1
            if count >= console_height - 1:
                if wait_for_keypress():
                    break
                print("\n" * (console_height - 1), end = "")
                count = 0
    print()
    print()
    input("Press Enter to go back to the main menu...")            
    session.close()


def rename_user():
    session = Session()
    original_username = input("Enter the current username: ")
    print()
    valid_username_pattern = r'^[A-Za-z0-9@.]+$'
    while True:
        new_username = input("Enter the new username: ")
        if re.match(valid_username_pattern, new_username):
            break
        print("Invalid username. Only letters, numbers, '@', and '.' are allowed.")

    user_record = session.query(UserRegistry).filter_by(UniqueUserName = original_username).first()
    if not user_record:
        print("User not found.")
        session.close()
        return

    user_record.UniqueUserName = new_username
    session.commit()
    print(f"Username updated from {original_username} to {new_username}")
    print()
    print()
    input("Press Enter to go back to the main menu...")
    session.close()


def update_user_password():
    username = input("Enter username: ")
    password = input("Enter password: ")
    print()

    # Generate a random 8-byte salt
    salt = os.urandom(8)

    # Hash the password with the salt
    hashed_password = hashlib.sha1(salt[:4] + password.encode() + salt[4:]).digest()
    hashed_password_hex = binascii.hexlify(hashed_password).decode()

    # Convert salt to hex for storage
    salt_hex = binascii.hexlify(salt).decode()

    with Session() as session:
        # Check if the user exists
        user = session.query(UserRegistry).filter_by(UniqueUserName = username).first()
        if user:
            # Update the user's password and salt
            user.PassphraseSalt = salt_hex
            user.SaltedPassphraseDigest = hashed_password_hex
            session.commit()
            print(f"Password updated successfully for user: {username}")
        else:
            print("User not found.")
    print()
    print()
    input("Press Enter to go back to the main menu...")        
    session.close()


def add_vac_ban_to_account():
    unique_id = None  # Initialize unique_id outside the loop to keep it for the entire session
    print()

    while True:
        if unique_id is None:  # Only ask for the user identifier if it's not already set
            print("\nSelect method to add VAC ban:")
            print("1.) Add VAC ban using UniqueID (AccountID)")
            print("2.) Add VAC ban using username")
            print("3.) Add VAC ban using email address")
            print("4.) Return to main menu")
            choice = input("Enter the number of your choice: ")

            if choice == '1':
                unique_id = input("Enter the UniqueID: ")
            elif choice in ['2', '3']:
                if choice == '2':
                    identifier = input("Enter the username: ")
                    column = UserRegistry.UniqueUserName
                else:
                    identifier = input("Enter the email address: ")
                    column = UserRegistry.AccountEmailAddress
                with Session() as session:
                    user = session.query(UserRegistry).filter(column == identifier).first()
                    if user:
                        unique_id = user.UniqueID
                    else:
                        print("User not found.")
                        continue
            elif choice == '4':
                return
            else:
                print("Invalid choice.")
                continue  # Go back to the top of the loop to re-prompt for input

        # Add VAC bans for the identified account
        print("VAC Ban's use a range of AppIDs to determine what games the user can no longer use secure servers on.\n"
              "For example:\n"
              "ex1.) Half-Life 1 (GoldSRC) the first AppID: 10, the last AppID: 80\n"
              "ex2.) Half-Life 2 (Source) the first AppID: 220, last AppID: 320\n"
              "ex3.) Banning a user from a single App/Game: first AppID: 10, last AppID: 10")

        first_appid = input("Enter the first AppID to ban the user from: ")
        last_appid = input("Enter the last AppID to ban the user from: ")
        ban_duration_hours = int(input("Enter the duration of the ban in hours: "))
        ban_creation_time = datetime.now().strftime('%m/%d/%Y %H:%M:%S')

        with Session() as session:
            vac_ban = VACBans(friendRegistryID=unique_id, starttime=ban_creation_time,
                              firstappid=first_appid, lastappid=last_appid, length_of_ban=ban_duration_hours)
            session.add(vac_ban)
            session.commit()
            print("VAC ban added successfully.")

        # Ask if the user wants to add another VAC ban
        add_another = input("Do you want to add another VAC ban for this account? (y/n): ")
        if add_another.lower() != 'y':
            unique_id = None  # Reset unique_id to allow selection of a new account or return to the menu

        # If the user answers 'y', the loop continues and they can add another VAC ban for the same account.


def remove_vac_ban_from_account():
    print()
    while True:
        print("\nSelect method to find user for VAC ban removal:")
        print("1.) Use UniqueID")
        print("2.) Use username")
        print("3.) Use email address")
        print("4.) Return to main menu")
        choice = input("Enter the number of your choice: ")

        unique_id = None
        if choice == '1':
            unique_id = input("Enter the UniqueID: ")
        elif choice in ['2', '3']:
            identifier = input("Enter the {}:".format("username" if choice == '2' else "email address"))
            column = UserRegistry.UniqueUserName if choice == '2' else UserRegistry.AccountEmailAddress
            with Session() as session:
                user = session.query(UserRegistry).filter(column == identifier).first()
                if user:
                    unique_id = user.UniqueID
                else:
                    print("User not found.")
                    continue
        elif choice == '4':
            return
        else:
            print("Invalid choice.")
            continue

        if unique_id:
            while True:  # Loop to allow multiple removals
                with Session() as session:
                    # Fetch the current VAC bans for the user
                    bans = session.query(VACBans).filter_by(friendRegistryID=unique_id).all()
                    if not bans:
                        print("No VAC bans found for this user.")
                        break  # Exit if there are no bans

                    # List current bans
                    print("\nCurrent VAC bans:")
                    for ban in bans:
                        print(f"ID: {ban.UniqueID}, First AppID: {ban.firstappid}, Last AppID: {ban.lastappid}")

                    # Prompt to remove a ban
                    ban_id_to_remove = input("Enter the ID of the ban to remove: ")
                    ban_to_remove = session.query(VACBans).filter_by(UniqueID=ban_id_to_remove).first()
                    if ban_to_remove:
                        session.delete(ban_to_remove)
                        session.commit()
                        print("VAC ban removed successfully.")
                    else:
                        print("VAC ban not found.")

                    # Ask if the user wants to remove more bans
                    next_action = input("Do you want to remove more bans? (y/n): ")
                    if next_action.lower() != 'y':
                        break  # Exit the inner loop and go back to user selection menu           


def main_menu():
    while True:
        print("\nSelect an option:")
        print("1.) Remove A User")
        print("2.) Ban/Unban A User")
        print("3.) Change A User's UserName")
        print("4.) Change A User's Email Address")
        print("5.) Change A User's Password")
        print("6.) Add A Subscription to A User's Account")
        print("7.) Remove A Subscription From A User's Account")
        print("8.) List All Users In The Database")
        print("9.) List A User's Subscriptions")
        print("10.) List Subscriptions")
        print("11.) List Applications Included With Subscription")
        print("12.) Add VAC Ban to Account (SteamUI_87+ With CM)")
        print("13.) Remove VAC Ban from Account (SteamUI_87+ With CM)")
        print()
        print("0.) Quit")
        print()

        choice = input("Enter the number of your choice: ")

        if choice == '1':
            remove_user()
        elif choice == '2':
            ban_user()
        elif choice == '3':
            rename_user()
        elif choice == '4':
            change_user_email()
        elif choice == '5':
            update_user_password()
        elif choice == '6':
            add_subscription()
        elif choice == '7':
            remove_subscription_from_user()
        elif choice == '8':
            list_users()
        elif choice == '9':
            list_user_subscriptions()
        elif choice == '10':
            list_subscriptions()
        elif choice == '11':
            list_applications_for_subscription()
        elif choice == '12':
            add_vac_ban_to_account()
        elif choice == '13':
            remove_vac_ban_from_account()
        elif choice == '0':
            break
        else:
            print("Invalid choice.")

def goback_menu():
    while True:
        print("\nSelect an option:")
        print("0.) Go back to main menu")
        print("1.) Exit")
        choice = input("Enter the number of your choice: ")
        if choice == '0':
            return  # Go back to the main menu
        elif choice == '1':
            exit()  # Exit the program
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main_menu()
