#!/usr/bin/env python3
"""
Server Management Menu for the Administration Client.

This module displays options for managing various servers. Many options are stubs
for future implementation.
"""
import json
import struct
import sys

from globals import RECORD_VERSION, STEAM_VERSION
from utilities import clear_console
import local_utils  # Local utilities - avoids dependency on server's config.py
from networking import (
    request_full_dirserver_json,
    request_add_dirserver_entry,
    request_del_dirserver_entry,
    request_full_contentserver_json,
    request_add_contentserver_entry,
    request_del_contentserver_entry,
    request_blobmgr_file_list,
    request_blobmgr_swap,
    request_find_content_servers_by_appid,
    request_restartable_servers_list,
    request_restart_server_thread,
    CMD_GET_RESTARTABLE_SERVERS,
    CMD_RESTART_SERVER_THREAD,
)


def servermanagement_menu():
    options = {
        1: "Directory Server Management",
        2: "Content-List Server Management",
        3: "Purge Content Versions",
        4: "Re-Add Content Versions",
        5: "Change Blob / CDR",
        6: "CSER Statistics",
        7: "Restart Server Menu",
        8: "Emulator Configuration Menu",
        9: "Edit White/Black IP Listing",
        10:"Name Suggestion Menu",
        11:"Check for Server Updates",
        'x': "Exit"
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
        choice = input("Enter a number or 'x' to select an option: ").strip()
        if choice.isdigit():
            choice = int(choice)
        if choice == 0:
            print("Going back...")
            break
        elif choice == 1:
            directory_server_menu()
        elif choice == 2:
            content_list_server_menu()
        elif choice == 3:
            content_purge_menu()
        elif choice == 4:
            content_readd_menu()
        elif choice == 5:
            blob_cdr_menu()
        elif choice == 6:
            statistics_menu()
        elif choice == 7:
            server_restart_menu()
        elif choice == 8:
            print("Emulator Configuration Menu is not yet implemented.")
        elif choice == 9:
            edit_ip_list_menu()
        elif choice == 10:
            name_suggestion_menu()
        elif choice == 11:
            print("Checking for server updates...")
        elif choice in ('x', 'X'):
            sys.exit("Exiting program...")
        else:
            print("Invalid option. Please try again.")

def server_restart_menu():
    clear_console()
    server_list = request_restartable_servers_list()

    if server_list is None:
        print("Error: Could not retrieve list of restartable servers.")
        input("Press Enter to continue...")
        return
    if not server_list:
        print("No restartable server processes found on the server.")
        input("Press Enter to continue...")
        return

    print("\nServer Restart Menu:")
    for idx, identifier in enumerate(server_list, start=1):
        print(f"{idx}.) {identifier}")
    print()
    print("0.) Go Back")
    print("X.) Exit")
    print()

    choice = input("Enter a number, '0' to return or 'x' to exit: ").strip()

    if choice == '0':
        return
    elif choice.lower() == 'x':
        sys.exit("Exiting program...")
    elif choice.isdigit() and 1 <= int(choice) <= len(server_list):
        identifier = server_list[int(choice) - 1]
        print(f"Issuing restart for {identifier}...")
        response = request_restart_server_thread(identifier)
        print(f"Server Response: {response if response else 'No response or error.'}")
        input("Press Enter to continue...")
    else:
        print("Invalid option. Please try again.")
        input("Press Enter to continue...")

def edit_ip_list_menu():
    options = {
        1: "Edit White Listed IP Addresses",
        2: "Edit Black Listed IP Addresses"
    }
    while True:
        clear_console()
        print("\nSelect an Option For Managing Black Listed and White Listed IP Addresses:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()
        choice = input("Enter a number, '0' to return, or 'x' to exit: ").strip()
        if choice == '0':
            break
        elif choice.lower() == 'x':
            sys.exit("Exiting program...")
        elif choice.isdigit() and int(choice) in options:
            print(f"You selected: {options[int(choice)]}")
            input("Press Enter to continue...")
        else:
            print("Invalid option. Please try again.")

def name_suggestion_menu():
    options = {
        1: "Edit Suggestion Prepends (<prepend>username)",
        2: "Edit Suggestion Append (username<append>)"
    }
    while True:
        clear_console()
        print("\nSelect an Option To Make Changes:")
        for key, value in options.items():
            print(f"{key}.) {value}")
        print()
        print("0.) Go Back")
        print("X.) Exit")
        print()
        choice = input("Enter a number, '0' to return, or 'x' to exit: ").strip()
        if choice == '0':
            break
        elif choice.lower() == 'x':
            sys.exit("Exiting program...")
        elif choice.isdigit() and int(choice) in options:
            print(f"You selected: {options[int(choice)]}")
            input("Press Enter to continue...")
        else:
            print("Invalid option. Please try again.")


# ??? Directory Server Management ?????????????????????????????????????????????
def directory_server_menu():
    while True:
        clear_console()
        print("\nDirectory Server List Manager:")
        print("1) List all categories")
        print("2) List all servers (all categories)")
        print("3) List servers in a category")
        print("4) Add server to category")
        print("5) Remove server from category")
        print("6) Edit server entry")
        print("0) Back")
        ch = input("Select: ")
        if ch == '1':
            show_dirserver_categories()
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

def _fetch_dirservers():
    data = request_full_dirserver_json()
    try:
        return json.loads(data) if data else []
    except Exception:
        return []

def show_dirserver_categories():
    servers = _fetch_dirservers()
    categories = sorted({srv.get('server_type') for srv in servers})
    print("Categories:")
    for cat in categories:
        print(f" - {cat}")
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
    details = {
        'wan_ip': wan,
        'lan_ip': lan,
        'port': int(prt),
        'server_type': cat,
    }
    rsp = request_add_dirserver_entry(json.dumps(details).encode('utf-8'))
    print(rsp if rsp else "No response")
    input("Press Enter to continue...")

def remove_dirserver():
    key = input("Key (WAN:Port): ")
    cat = input("Category: ")
    parts = key.split(":")
    identifier = {
        'wan_ip': parts[0],
        'lan_ip': parts[0],
        'port': int(parts[1]) if len(parts) > 1 else 0,
        'server_type': cat,
    }
    rsp = request_del_dirserver_entry(json.dumps(identifier).encode('utf-8'))
    print(rsp if rsp else "No response")
    input("Press Enter to continue...")

def edit_dirserver():
    print("Edit server entry")
    key = input("Existing key (WAN:Port): ")
    cat = input("Existing Category: ")
    parts = key.split(":")
    identifier = {
        'wan_ip': parts[0],
        'lan_ip': parts[0],
        'port': int(parts[1]) if len(parts) > 1 else 0,
        'server_type': cat,
    }
    request_del_dirserver_entry(json.dumps(identifier).encode('utf-8'))
    print("Enter new details:")
    add_dirserver()


# ??? Content-List Server Management ???????????????????????????????????????????
def content_list_server_menu():
    clear_console()
    print("1) List content-list servers")
    print("2) Add content-list server")
    print("3) Remove content-list server")
    print("4) Find content servers by AppID")
    print("0) Back")
    ch = input("Select: ")
    if ch == '1':
        rsp_json = request_full_contentserver_json()
        print(rsp_json if rsp_json else "No response")
    elif ch == '2':
        wan = input("WAN IP : ")
        lan = input("LAN IP : ")
        prt = input("Port   : ")
        details = {
            "wan_ip": wan,
            "lan_ip": lan,
            "port": int(prt),
            "region": "US",
            "applist": "",
            "cell_id": 0,
            "permanent": 1,
            "package_cs": False,
        }
        rsp = request_add_contentserver_entry(json.dumps(details).encode('utf-8'))
        print(rsp if rsp else "No response")
    elif ch == '3':
        key = input("Key (WAN:Port): ")
        parts = key.split(":")
        identifier = {"wan_ip": parts[0], "lan_ip": parts[0], "port": int(parts[1]) if len(parts)>1 else 0, "server_type": ""}
        rsp = request_del_contentserver_entry(json.dumps(identifier).encode('utf-8'))
        print(rsp if rsp else "No response")
    elif ch == '4':
        appid = input("AppID: ")
        version = input("Version: ")
        try:
            appid_i = int(appid); version_i = int(version)
            resp = request_find_content_servers_by_appid(appid_i, version_i)
            if resp is None:
                print("No response")
            elif len(resp) < 2:
                print("Malformed response")
            else:
                count = struct.unpack('>H', resp[:2])[0]
                data = resp[2:]
                expected = count * 6
                if len(data) < expected:
                    print("Incomplete response")
                else:
                    print(f"Found {count} server(s):")
                    for i in range(count):
                        chunk = data[i*6:(i+1)*6]
                        ip, port = local_utils.decodeIP(chunk)
                        print(f" {i+1}. {ip}:{port}")
        except ValueError:
            print("Invalid numbers entered")
    input("Press Enter to continue...")


# ??? Purge and Re-Add Content Versions ????????????????????????????????????????
def content_purge_menu():
    appid = input("Enter AppID to purge: ")
    version = input("Enter version to purge: ")
    try:
        appid_i = int(appid)
        version_i = int(version)
    except ValueError:
        print("Invalid numbers entered.")
        input("Press Enter to continue...")
        return
    msg = request_content_purge(appid_i, version_i)
    print(msg if msg else "No response")
    input("Press Enter to continue...")


def content_readd_menu():
    print("Content re-add feature is not implemented.")
    input("Press Enter to continue...")

def blob_cdr_menu():
    from blobmgr import BlobManager

    # 1) grab the list from server
    try:
        info = request_blobmgr_file_list()
        if info is None:
            raise RuntimeError("Failed to fetch blob list")
    except Exception as e:
        print("Error fetching blob list:", e)
        input("Press Enter to continue?")
        return

    # 2) launch your GUI
    mgr = BlobManager()

    # Override the code that loads from files/DB:
    mgr.BlobsFolder = None
    mgr.load_from_database = False
    mgr.CacheFolder = None

    # Feed it the server?side list:
    mgr.ServerFirstBlobs  = info["first"]
    mgr.ServerSecondBlobs = info["second"]

    # Monkey?patch PopulateRows to use those lists:
    def PopulateRowsFromServer(self):
        self.Rows = []
        self.FirstBlobs = self.ServerFirstBlobs[:]
        self.SecondBlobs = self.ServerSecondBlobs[:]
        # re?use blobmgr?s filename?parsing logic to fill self.Rows, FirstBlobDates, etc.
        # (you can call its own PopulateRows code, but operate on self.BlobsFiles = ServerSecondBlobs)
        self.BlobsFiles = []  # disable local file usage
        return super(BlobManager, self).PopulateRows()  # or copy that block here
    mgr.PopulateRows = PopulateRowsFromServer.__get__(mgr, BlobManager)

    # Monkey?patch SwapBlobs to call CMD_BLOB_SWAP
    def SwapBlobsToServer(self):
        first = self.matching_first_blob
        second = self.Rows[self.row][-1]  # selected secondblob filename
        try:
            msg = request_blobmgr_swap(second)
            if msg:
                self.window['-STATEMSG-'].update(msg)
            else:
                self.window['-STATEMSG-'].update("Swap failed")
        except Exception as e:
            self.window['-STATEMSG-'].update(str(e))
    mgr.SwapBlobs = SwapBlobsToServer.__get__(mgr, BlobManager)

    mgr.run()    # or whatever kicks off its event loop



# ??? CSER Statistics (download tar of recent stats) ???????????????????????????
def statistics_menu():
    stats = request_server_statistics()
    if not stats:
        print("Failed to retrieve statistics.")
    else:
        for key, val in stats.items():
            print(f"{key}: {val}")
    input("Press Enter to continue...")


if __name__ == "__main__":
    servermanagement_menu()
