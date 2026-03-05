#!/usr/bin/env python3
"""
Administration Client Main Module

Uses the networking module for all network operations.
The UI (curses menus) is kept largely as is, with only minor text adjustments.
"""

import curses
import sys
import time
# Removed: import libs.PySimpleGUI as psg 
from networking import (perform_handshake_and_authenticate,
                        login_to_server,
                        send_request_to_server,
                        stream_status,
                        get_local_ip,
                        request_blob_list,
                        request_blob_swap,
                        request_server_list,
                        CMD_LIST_AUTH_SERVERS,
                        CMD_LIST_CONFIG_SERVERS,
                        request_full_dirserver_json,
                        CMD_GET_FULL_DIRSERVER_LIST,
                        request_add_dirserver_entry,
                        CMD_ADD_DIRSERVER_ENTRY,
                        request_del_dirserver_entry,
                        CMD_DEL_DIRSERVER_ENTRY,
                        request_full_contentserver_json,
                        CMD_GET_FULL_CONTENTSERVER_LIST,
                        request_add_contentserver_entry,
                        CMD_ADD_CONTENTSERVER_ENTRY,
                        request_del_contentserver_entry,
                        CMD_DEL_CONTENTSERVER_ENTRY,
                        request_find_content_servers_by_appid,
                        CMD_FIND_CONTENT_SERVERS_BY_APPID,
                        request_interactive_content_server_finder,
                        CMD_INTERACTIVE_CONTENT_SERVER_FINDER,
                        request_ip_list,
                        CMD_GET_IP_WHITELIST,
                        CMD_GET_IP_BLACKLIST,
                        request_add_ip_to_list,
                        CMD_ADD_TO_IP_WHITELIST,
                        CMD_ADD_TO_IP_BLACKLIST,
                        request_del_ip_from_list,
                        CMD_DEL_FROM_IP_WHITELIST,
                        CMD_DEL_FROM_IP_BLACKLIST,
                        request_restartable_servers_list,
                        request_restart_server_thread,
                        request_restart_server_no_reload,
                        CMD_GET_RESTARTABLE_SERVERS,
                        CMD_RESTART_SERVER_THREAD,
                        CMD_RESTART_SERVER_NO_RELOAD,
                        request_list_admins,
                        request_edit_admin_rights,
                        request_remove_admin,
                        request_create_admin,
                        request_change_admin_username,
                        request_change_admin_email,
                        request_change_admin_password,
                        request_list_user_subscriptions,
                        request_add_subscription,
                        request_remove_subscription,
                        request_list_available_subscriptions,
                        request_list_guest_passes,
                        request_add_guest_pass,
                        request_remove_guest_pass,
                        request_list_ftp_users,
                        request_add_ftp_user,
                        request_remove_ftp_user,
                        request_live_log,
                        request_auth_stats,
                        request_set_rate_limit,
                        request_bandwidth_usage,
                        request_connection_count,
                        request_edit_configuration,
                        request_toggle_feature,
                        request_user_session_report,
                        request_set_ftp_quota,
                        request_hot_reload_config,
                        request_chatroom_op,
                        request_clan_op,
                        request_gift_op,
                        request_news_op,
                        request_license_op,
                        request_token_op,
                        request_inventory_op,
                        logout_from_server,
                        CMD_LOGOFF,
                        request_list_approved_apps,
                        request_get_approved_app,
                        request_update_approved_app,
                        request_approve_with_subscriptions,
                        request_reparse_pending,
                        request_delete_approved_app,
                        start_heartbeat_thread,
                        stop_heartbeat_thread)
                        # Removed: request_detailed_blob_list
import os # For path joining
import struct # For struct.unpack

import local_utils  # Local utilities (decodeIP, etc.) - avoids dependency on server's config.py
import json  # For parsing full dirserver list and creating add/del entry payload
import subprocess  # For launching auxiliary tools

from user_config import get_config as read_user_config

# Load configuration from client_config.ini so the tool uses the same
# credentials as the server.  This replaces the old hard-coded defaults that
# caused handshake failures when the peer password differed from the server's
# configuration.
config = read_user_config()

def curses_get_string_input(screen, r, c, prompt_string, edit_len=30):
    """Helper function to get string input in curses."""
    screen.addstr(r, c, prompt_string)
    screen.refresh()
    curses.echo()
    curses.curs_set(1)
    input_bytes = screen.getstr(r, c + len(prompt_string), edit_len)
    curses.noecho()
    curses.curs_set(0)
    return input_bytes.decode('utf-8').strip()

def curses_menu(screen, title, items):
    """Display a menu using arrow keys for navigation."""
    current = 0
    curses.curs_set(0)
    while True:
        screen.clear()
        screen.addstr(1, 2, title)
        for i, (label, _) in enumerate(items):
            y = 3 + i
            if i == current:
                screen.addstr(y, 4, label, curses.A_REVERSE)
            else:
                screen.addstr(y, 4, label)
        screen.refresh()
        ch = screen.getch()
        if ch == curses.KEY_UP:
            current = (current - 1) % len(items)
        elif ch == curses.KEY_DOWN:
            current = (current + 1) % len(items)
        elif ch in (curses.KEY_ENTER, 10, 13):
            label, handler = items[current]
            screen.clear()
            screen.refresh()
            if handler:
                handler(screen)
            else:
                break


def curses_select_from_list(screen, title, options):
    """Display a selectable (paginated) list and return the chosen index."""
    if not options:
        return None
    current = 0
    offset = 0
    curses.curs_set(0)
    page_size = max(1, curses.LINES - 5)
    while True:
        screen.clear()
        screen.addstr(1, 2, title)
        for i in range(page_size):
            idx = offset + i
            if idx >= len(options):
                break
            text = str(options[idx])
            y = 3 + i
            if idx == current:
                screen.addstr(y, 4, text[: curses.COLS - 6], curses.A_REVERSE)
            else:
                screen.addstr(y, 4, text[: curses.COLS - 6])
        screen.refresh()
        ch = screen.getch()
        if ch == curses.KEY_UP:
            if current > 0:
                current -= 1
            if current < offset:
                offset = current
        elif ch == curses.KEY_DOWN:
            if current < len(options) - 1:
                current += 1
            if current >= offset + page_size:
                offset = current - page_size + 1
        elif ch in (curses.KEY_ENTER, 10, 13):
            return current
        elif ch in (27, ord('q')):
            return None

def main_menu(screen):
    items = [
        ("1. User Management Commands", user_management_menu),
        ("2. Subscription Commands", subscription_menu),
        ("3. Admin Commands", admin_commands_menu),
        ("4. FTP Upload Review", ftp_review_menu),
        ("U. FTP User Management", ftp_user_management_menu),
        ("C. Chatroom Management", chatroom_management_menu),
        ("G. Clan Management", clan_management_menu),
        ("N. News Management", news_management_menu),
        ("L. License Management", license_management_menu),
        ("I. Inventory Management", inventory_management_menu),
        ("M. Monitoring/Config", monitoring_menu),
        ("5. Request Streaming Status", lambda s: (
            s.addstr(curses.LINES - 4, 2, f"Status: {stream_status() or 'N/A'}"),
            s.refresh(), curses.napms(2000),
            s.move(curses.LINES - 4, 2), s.clrtoeol()
        )),
        ("6. List Available Blobs (AdminTool Format)", ui_list_blobs),
        ("7. Directory Server List Manager", directory_server_management_menu),
        ("8. Content Server Management", content_server_management_menu),
        ("9. IP List Management", ip_list_management_menu),
        ("S. Server Process Management", server_process_management_menu),
        ("B. Launch Blob Manager", run_blobmgr_ui),
        ("0. Exit", None)
    ]
    curses_menu(screen, "Administration Client Main Menu", items)


def server_process_management_menu(screen):
    """Menu to restart running server processes."""

    # Get full server info (raw=True returns list of dicts with identifier, class, port, is_alive, module)
    servers = request_restartable_servers_list(raw=True)
    items = []

    def make_server_handler(server_info):
        """Create a handler that shows restart options for a specific server."""
        sid = server_info.get('identifier', 'Unknown') if isinstance(server_info, dict) else str(server_info)

        def _handler(sc):
            # Show server details and restart options
            sc.clear()
            sc.addstr(1, 2, f"Server: {sid}")

            if isinstance(server_info, dict):
                sc.addstr(3, 2, f"Class: {server_info.get('class', 'N/A')}")
                sc.addstr(4, 2, f"Port: {server_info.get('port', 'N/A')}")
                sc.addstr(5, 2, f"Status: {'Running' if server_info.get('is_alive') else 'Stopped'}")
                sc.addstr(6, 2, f"Module: {server_info.get('module', 'N/A')}")
                y_offset = 8
            else:
                y_offset = 4

            sc.addstr(y_offset, 2, "Select restart option:")
            sc.addstr(y_offset + 2, 4, "1. Hot-Reload (reload code from disk)")
            sc.addstr(y_offset + 3, 4, "2. Simple Restart (keep current code)")
            sc.addstr(y_offset + 4, 4, "3. Cancel")
            sc.refresh()

            choice = sc.getch()
            sc.clear()

            if choice == ord('1'):
                sc.addstr(1, 2, f"Hot-reloading {sid} (reloading code from disk)...")
                sc.refresh()
                resp = request_restart_server_thread(sid, reload_code=True)
                sc.addstr(3, 2, f"Response: {resp if resp else 'No response or error.'}")
            elif choice == ord('2'):
                sc.addstr(1, 2, f"Restarting {sid} (no code reload)...")
                sc.refresh()
                resp = request_restart_server_thread(sid, reload_code=False)
                sc.addstr(3, 2, f"Response: {resp if resp else 'No response or error.'}")
            else:
                sc.addstr(1, 2, "Cancelled.")

            sc.addstr(curses.LINES - 1, 2, "Press any key to return...")
            sc.getch()

        return _handler

    if servers:
        for srv in servers:
            if isinstance(srv, dict):
                # Format: "ServerName (Running) - port:27014"
                sid = srv.get('identifier', 'Unknown')
                status = 'Running' if srv.get('is_alive') else 'Stopped'
                port = srv.get('port', '?')
                label = f"{sid} ({status}) - port:{port}"
            else:
                # Fallback for old format (list of strings)
                sid = str(srv)
                label = sid
            items.append((label, make_server_handler(srv)))
    else:
        items.append(("No restartable servers", lambda s: (s.addstr(3, 2, "Press any key..."), s.getch())))

    items.append(("Back", None))
    curses_menu(screen, "Server Process Management", items)


def ip_list_management_menu(screen):
    items = [
        ("View IP Whitelist", lambda s: ui_view_ip_list(s, "Whitelist", CMD_GET_IP_WHITELIST)),
        ("View IP Blacklist", lambda s: ui_view_ip_list(s, "Blacklist", CMD_GET_IP_BLACKLIST)),
        ("Add IP to Whitelist", lambda s: ui_add_ip_to_list(s, "Whitelist", CMD_ADD_TO_IP_WHITELIST)),
        ("Add IP to Blacklist", lambda s: ui_add_ip_to_list(s, "Blacklist", CMD_ADD_TO_IP_BLACKLIST)),
        ("Remove IP from Whitelist", lambda s: ui_remove_ip_from_list(s, "Whitelist", CMD_DEL_FROM_IP_WHITELIST)),
        ("Remove IP from Blacklist", lambda s: ui_remove_ip_from_list(s, "Blacklist", CMD_DEL_FROM_IP_BLACKLIST)),
        ("Back", None)
    ]
    curses_menu(screen, "IP List Management Menu", items)

def ui_remove_ip_from_list(screen, list_type_str: str, command_code: bytes):
    # ... (content as before) ...
    screen.clear(); screen.addstr(1, 2, f"Remove IP from {list_type_str}")
    screen.addstr(3, 2, f"Tip: View the {list_type_str} first to ensure the IP is correct.")
    ip_to_remove = curses_get_string_input(screen, 5, 2, "Enter IP address to remove: ", 45) 
    status_line = 7
    if not ip_to_remove: screen.addstr(status_line, 2, "IP address cannot be empty."); screen.refresh(); curses.napms(1500)
    elif not ('.' in ip_to_remove or ':' in ip_to_remove): screen.addstr(status_line, 2, "Invalid IP format."); screen.refresh(); curses.napms(2000)
    else:
        screen.addstr(status_line, 2, f"Removing {ip_to_remove} from {list_type_str}..."); screen.refresh()
        response = request_del_ip_from_list(command_code, ip_to_remove) 
        screen.move(status_line, 2); screen.clrtoeol()
        screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response or error.'}")
    screen.addstr(curses.LINES - 1, 2, "Press any key to return..."); screen.getch()

def ui_add_ip_to_list(screen, list_type_str: str, command_code: bytes):
    # ... (content as before) ...
    screen.clear(); screen.addstr(1, 2, f"Add IP to {list_type_str}")
    ip_to_add = curses_get_string_input(screen, 3, 2, "Enter IP address to add: ", 45) 
    status_line = 5
    if not ip_to_add: screen.addstr(status_line, 2, "IP address cannot be empty."); screen.refresh(); curses.napms(1500)
    elif not ('.' in ip_to_add or ':' in ip_to_add): screen.addstr(status_line, 2, "Invalid IP format."); screen.refresh(); curses.napms(2000)
    else:
        screen.addstr(status_line, 2, f"Adding {ip_to_add} to {list_type_str}..."); screen.refresh()
        response = request_add_ip_to_list(command_code, ip_to_add)
        screen.move(status_line, 2); screen.clrtoeol()
        screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response or error.'}")
    screen.addstr(curses.LINES - 1, 2, "Press any key to return..."); screen.getch()

def ui_view_ip_list(screen, list_type_str: str, command_code: bytes):
    # ... (content as before) ...
    screen.clear(); screen.addstr(1, 2, f"Fetching IP {list_type_str}..."); screen.refresh()
    ip_list = request_ip_list(command_code) 
    screen.clear()
    if ip_list is None: screen.addstr(1, 2, f"Error: Could not retrieve IP {list_type_str}.")
    elif not ip_list: screen.addstr(1, 2, f"The IP {list_type_str} is empty.")
    else:
        screen.addstr(1, 2, f"IP {list_type_str} (Count: {len(ip_list)}):")
        start_index = 0; max_lines_per_page = curses.LINES - 5 
        while True:
            screen.move(3,0); screen.clrtobot() 
            current_page_ips = ip_list[start_index : start_index + max_lines_per_page]
            for i, ip_addr in enumerate(current_page_ips): screen.addstr(3 + i, 4, f"{start_index + i + 1}. {ip_addr}")
            footer_y = curses.LINES - 2
            footer_msg = "Press (n)ext, (p)revious, or (q)uit."
            if start_index + max_lines_per_page >= len(ip_list): footer_msg = "End of list. Press (q)uit."
            if start_index == 0 and start_index + max_lines_per_page >= len(ip_list): footer_msg = "Press (q)uit to return."
            screen.addstr(footer_y, 2, footer_msg); screen.clrtoeol(); screen.refresh()
            key_nav = screen.getch()
            if key_nav == ord('n') and start_index + max_lines_per_page < len(ip_list):
                start_index += max_lines_per_page
            elif key_nav == ord('p') and start_index > 0:
                start_index = max(0, start_index - max_lines_per_page)
            elif key_nav == ord('q'):
                break
    screen.addstr(curses.LINES - 1, 2, "Press any key to return...")
    screen.getch()

def user_management_menu(screen):
    def query_username(sc):
        username = curses_get_string_input(sc, 8, 2, "Enter username: ")
        resp = send_request_to_server(b'\x0B', [username])
        sc.clear(); sc.addstr(1,2,"Response:")
        sc.addstr(3,2, resp.decode('latin-1') if resp else "No response/Error.")
        sc.addstr(curses.LINES-1,2,"Press key..."); sc.getch()

    def query_email(sc):
        email = curses_get_string_input(sc, 8, 2, "Enter email: ")
        resp = send_request_to_server(b'\x0C', [email])
        sc.clear(); sc.addstr(1,2,"Response:")
        sc.addstr(3,2, resp.decode('latin-1') if resp else "No response/Error.")
        sc.addstr(curses.LINES-1,2,"Press key..."); sc.getch()

    def list_all_users(sc):
        response = send_request_to_server(b'\x0D', [])
        sc.clear(); sc.addstr(1,2,"List All Users Response:")
        if response and len(response) >=4:
            count = struct.unpack('>I', response[:4])[0]; details = response[4:].decode('latin-1')
            display_lines = details.splitlines(); start_line = 0; max_display_lines = curses.LINES - 7
            while True:
                sc.move(3,2); sc.clrtobot(); sc.addstr(3,2,f"User count: {count}")
                for i, line_text in enumerate(display_lines[start_line:start_line+max_display_lines]):
                    if 6+i < curses.LINES-1: sc.addstr(6+i,2,line_text)
                footer = "Press (n)ext, (p)revious, or (q)uit."
                if start_line + max_display_lines >= len(display_lines): footer = "End of list. Press (q)uit."
                sc.addstr(curses.LINES-1,2,footer); sc.clrtoeol()
                key_nav = sc.getch()
                if key_nav == ord('n') and start_line + max_display_lines < len(display_lines): start_line += max_display_lines
                elif key_nav == ord('p') and start_line > 0: start_line = max(0,start_line - max_display_lines)
                elif key_nav == ord('q'): break
        else:
            sc.addstr(3,2,"No response or error.")
        sc.addstr(curses.LINES-1,2,"Press key..."); sc.getch()

    items = [
        ("Query by Username", query_username),
        ("Query by Email", query_email),
        ("List All Users", list_all_users),
        ("Back", None)
    ]
    curses_menu(screen, "User Management Menu", items)

def subscription_menu(screen):
    items = [
        ("List User Subscriptions", list_user_subs),
        ("Add Subscription", add_subscription),
        ("Remove Subscription", remove_subscription),
        ("List Available Subscriptions", list_available_subscriptions),
        ("List Guest Passes", list_guest_passes),
        ("Add Guest Pass", add_guest_pass),
        ("Remove Guest Pass", remove_guest_pass),
        ("Back", None)
    ]
    curses_menu(screen, "Subscription Management", items)

def admin_commands_menu(screen):
    items = [
        ("List Administrators", list_admins),
        ("Create Admin", create_admin),
        ("Edit Admin Permissions", edit_admin_permissions),
        ("Remove Administrator", remove_admin),
        ("Change Admin Username", change_admin_username),
        ("Change Admin Password", change_admin_password),
        ("Change Admin Email", change_admin_email),
        ("Back", None)
    ]
    curses_menu(screen, "Administration User Menu", items)

def list_user_subs(screen):
    uid_str = curses_get_string_input(screen, 3, 2, "User ID: ")
    try:
        uid = int(uid_str)
    except ValueError:
        screen.addstr(5, 2, "Invalid ID")
        screen.getch(); return
    resp = request_list_user_subscriptions(uid)
    screen.clear(); screen.addstr(1,2,"Subscriptions:")
    if resp:
        data = resp.encode('latin-1')
        if len(data) >=4:
            count = struct.unpack('>I', data[:4])[0]
            detail = data[4:].decode('latin-1')
            screen.addstr(3,2,f"Count: {count}")
            line = 5
            for item in detail.split('|'):
                if item:
                    screen.addstr(line,2,item)
                    line +=1
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def add_subscription(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    sub = curses_get_string_input(screen,4,2,"Subscription ID: ")
    if uid and sub:
        resp = request_add_subscription(int(uid), sub)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def remove_subscription(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    sub = curses_get_string_input(screen,4,2,"Subscription ID: ")
    if uid and sub:
        resp = request_remove_subscription(int(uid), sub)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def list_available_subscriptions(screen):
    """Display a paginated list of all available subscriptions from the currently loaded blob."""
    try:
        screen.clear()
        screen.addstr(1, 2, "Loading available subscriptions...")
        screen.refresh()
        
        resp = request_list_available_subscriptions()
        if not resp:
            screen.clear()
            screen.addstr(1, 2, "Available Subscriptions:")
            screen.addstr(3, 2, "No response from server")
            screen.addstr(curses.LINES-1, 2, "Press any key to continue...")
            screen.getch()
            return
        
        # Parse the response - assuming it's formatted similar to other list commands
        # Format might be: count (4 bytes) + pipe-separated subscription data
        screen.clear()
        screen.addstr(1, 2, "Available Subscriptions:")
        
        try:
            data = resp.encode('latin-1')
            if len(data) >= 4:
                count = struct.unpack('>I', data[:4])[0]
                detail = data[4:].decode('latin-1')
                screen.addstr(3, 2, f"Total subscriptions: {count}")
                
                # Split the subscription data by pipe separator
                subscriptions = [item.strip() for item in detail.split('|') if item.strip()]
                
                if subscriptions:
                    # Use curses_select_from_list for paginated display
                    screen.addstr(5, 2, "Press any key to view paginated list...")
                    screen.refresh()
                    screen.getch()
                    
                    # Display paginated list - user can navigate but not select (read-only)
                    selected_idx = curses_select_from_list(screen, "Available Subscriptions (Navigate with arrow keys, ESC to exit)", subscriptions)
                    
                else:
                    screen.addstr(5, 2, "No subscriptions found in the current blob")
            else:
                # If data format is different, display raw response
                screen.addstr(3, 2, "Raw response:")
                lines = resp.split('\n')
                for i, line in enumerate(lines[:curses.LINES-6]):
                    screen.addstr(5 + i, 4, line[:curses.COLS-6])
                    
        except (struct.error, UnicodeDecodeError) as e:
            # Fallback - display response as-is if parsing fails
            screen.clear()
            screen.addstr(1, 2, "Available Subscriptions:")
            screen.addstr(3, 2, "Response (raw):")
            lines = resp.split('\n') if '\n' in resp else [resp]
            for i, line in enumerate(lines[:curses.LINES-6]):
                screen.addstr(5 + i, 4, line[:curses.COLS-6])
                    
    except Exception as e:
        screen.clear()
        screen.addstr(1, 2, "Available Subscriptions:")
        screen.addstr(3, 2, f"Error: {str(e)}")
    
    screen.addstr(curses.LINES-1, 2, "Press any key to continue...")
    screen.getch()

def list_guest_passes(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    if not uid:
        screen.addstr(5,2,"User ID required"); screen.getch(); return
    resp = request_list_guest_passes(int(uid))
    screen.clear(); screen.addstr(1,2,"Guest Passes:")
    if resp:
        data = resp.encode('latin-1')
        if len(data) >=4:
            count = struct.unpack('>I', data[:4])[0]
            screen.addstr(3,2,f"Count: {count}")
            line=5
            for item in data[4:].decode('latin-1').split('|'):
                if item:
                    screen.addstr(line,2,item); line+=1
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def add_guest_pass(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    pid = curses_get_string_input(screen,4,2,"Guest Pass ID: ")
    if uid and pid:
        resp = request_add_guest_pass(int(uid), pid)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def remove_guest_pass(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    pid = curses_get_string_input(screen,4,2,"Guest Pass ID: ")
    if uid and pid:
        resp = request_remove_guest_pass(int(uid), pid)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def list_admins(screen):
    admins = request_list_admins()
    screen.clear(); screen.addstr(1,2,"Administrators:")
    if admins:
        line=3
        for user,right in admins:
            screen.addstr(line,2,f"{user} Rights:{right}"); line+=1
    else:
        screen.addstr(3,2,"No admins or error")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def create_admin(screen):
    user = curses_get_string_input(screen,3,2,"Username: ")
    pw = curses_get_string_input(screen,4,2,"Password: ")
    rights = curses_get_string_input(screen,5,2,"Rights bitfield: ")
    if user and pw and rights:
        resp = request_create_admin(user,pw,rights)
        msg = resp or "No response"
    else:
        msg = "All fields required"
    screen.addstr(7,2,str(msg)); screen.getch()

def edit_admin_permissions(screen):
    user = curses_get_string_input(screen,3,2,"Username: ")
    rights = curses_get_string_input(screen,4,2,"New Rights: ")
    if user and rights:
        resp = request_edit_admin_rights(user, rights)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def remove_admin(screen):
    user = curses_get_string_input(screen,3,2,"Username to remove: ")
    if user:
        resp = request_remove_admin(user)
        msg = resp or "No response"
    else:
        msg = "Username required"
    screen.addstr(5,2,str(msg)); screen.getch()

def change_admin_username(screen):
    old = curses_get_string_input(screen,3,2,"Current Username: ")
    new = curses_get_string_input(screen,4,2,"New Username: ")
    if old and new:
        resp = request_change_admin_username(old,new)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def change_admin_password(screen):
    user = curses_get_string_input(screen,3,2,"Username: ")
    pw = curses_get_string_input(screen,4,2,"New Password: ")
    if user and pw:
        resp = request_change_admin_password(user,pw)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def change_admin_email(screen):
    user = curses_get_string_input(screen,3,2,"Username: ")
    em = curses_get_string_input(screen,4,2,"New Email: ")
    if user and em:
        resp = request_change_admin_email(user, em)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,str(msg)); screen.getch()

def ftp_review_menu(screen):
    items = [
        ("List Pending Uploads", list_pending_uploads),
        ("Approve an Upload", approve_upload),
        ("Approve with Modified Subscriptions", approve_upload_with_subs),
        ("Deny an Upload", deny_upload),
        ("Re-parse from XML", reparse_pending_upload),
        ("Manage Approved Applications", approved_apps_menu),
        ("Back", None)
    ]
    curses_menu(screen, "FTP Upload Review Menu", items)

def list_pending_uploads(screen):
    # ... (content as before) ...
    try:
        response = send_request_to_server(b'\x40', [])
        screen.clear(); screen.addstr(1, 2, "Pending FTP Uploads:")
        if response: screen.addstr(3, 2, response.decode('latin-1'))
        else: screen.addstr(3, 2, "No pending uploads or no response from server.")
    except Exception as e: screen.addstr(1, 2, f"Error listing pending uploads: {e}")
    screen.addstr(curses.LINES - 1, 2, "Press Enter to return."); screen.getch()

def approve_upload(screen): 
    # ... (content as before) ...
    appid = curses_get_string_input(screen, 3, 2, "Enter AppID to approve: ")
    if appid:
        local_ip = get_local_ip(); parameters = [appid, config["adminusername"], local_ip]
        try:
            response = send_request_to_server(b'\x41', parameters)
            screen.addstr(5, 2, f"Approve response: {response.decode('latin-1') if response else 'No response'}")
        except Exception as e: screen.addstr(5, 2, f"Error approving upload: {e}")
    else: screen.addstr(5,2, "AppID cannot be empty.")
    screen.addstr(curses.LINES - 1, 2, "Press Enter to return."); screen.getch()

def deny_upload(screen):
    # ... (content as before) ...
    appid = curses_get_string_input(screen, 3, 2, "Enter AppID to deny: ")
    if appid:
        local_ip = get_local_ip(); parameters = [appid, config["adminusername"], local_ip]
        try:
            response = send_request_to_server(b'\x42', parameters)
            screen.addstr(5, 2, f"Deny response: {response.decode('latin-1') if response else 'No response'}")
        except Exception as e: screen.addstr(5, 2, f"Error denying upload: {e}")
    else: screen.addstr(5,2, "AppID cannot be empty.")
    screen.addstr(curses.LINES - 1, 2, "Press Enter to return."); screen.getch()

def reparse_pending_upload(screen):
    """Re-parse metadata from XML for a pending upload."""
    screen.clear()
    screen.addstr(1, 2, "Re-parse Pending Upload from XML", curses.A_BOLD)
    screen.addstr(3, 2, "This will re-read the XML file and update subscription/app data.")
    appid = curses_get_string_input(screen, 5, 2, "Enter AppID to re-parse: ")
    if appid:
        try:
            response = request_reparse_pending(appid)
            if response:
                screen.addstr(7, 2, f"Response: {response}")
            else:
                screen.addstr(7, 2, "No response from server.")
        except Exception as e:
            screen.addstr(7, 2, f"Error: {e}")
    else:
        screen.addstr(7, 2, "AppID cannot be empty.")
    screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
    screen.getch()

def approve_upload_with_subs(screen):
    """Approve an upload with modified subscription IDs."""
    screen.clear()
    screen.addstr(1, 2, "Approve Upload with Modified Subscriptions", curses.A_BOLD)
    appid = curses_get_string_input(screen, 3, 2, "Enter AppID to approve: ")
    if not appid:
        screen.addstr(5, 2, "AppID cannot be empty.")
        screen.getch()
        return

    screen.addstr(5, 2, "Enter subscriptions in format: id1:name1|id2:name2|...")
    screen.addstr(6, 2, "Example: 1234:Game Sub|5678:DLC Sub")
    subs = curses_get_string_input(screen, 8, 2, "Subscriptions: ")

    if subs:
        local_ip = get_local_ip()
        try:
            response = request_approve_with_subscriptions(
                appid, subs, config["adminusername"], local_ip
            )
            screen.addstr(10, 2, f"Response: {response or 'No response'}")
        except Exception as e:
            screen.addstr(10, 2, f"Error: {e}")
    else:
        # Approve without modifications
        local_ip = get_local_ip()
        parameters = [appid, config["adminusername"], local_ip]
        try:
            response = send_request_to_server(b'\x41', parameters)
            screen.addstr(10, 2, f"Approve response: {response.decode('latin-1') if response else 'No response'}")
        except Exception as e:
            screen.addstr(10, 2, f"Error: {e}")

    screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
    screen.getch()

def approved_apps_menu(screen):
    """Menu for managing approved applications."""
    items = [
        ("List Approved Applications", list_approved_apps),
        ("Edit Approved Application", edit_approved_app),
        ("Delete Approved Application", delete_approved_app),
        ("Back", None)
    ]
    curses_menu(screen, "Approved Applications Management", items)

def list_approved_apps(screen):
    """List all approved applications."""
    screen.clear()
    screen.addstr(1, 2, "Approved Applications:", curses.A_BOLD)
    try:
        response = request_list_approved_apps()
        if response:
            lines = response.split('\n')
            line_num = 3
            max_lines = curses.LINES - 5
            for line in lines[:max_lines]:
                if line.strip():
                    # Truncate if too long
                    display_line = line[:curses.COLS - 4] if len(line) > curses.COLS - 4 else line
                    screen.addstr(line_num, 2, display_line)
                    line_num += 1
            if len(lines) > max_lines:
                screen.addstr(line_num, 2, f"... and {len(lines) - max_lines} more")
        else:
            screen.addstr(3, 2, "No approved applications or no response.")
    except Exception as e:
        screen.addstr(3, 2, f"Error: {e}")
    screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
    screen.getch()

def edit_approved_app(screen):
    """Edit an approved application's name or subscriptions."""
    screen.clear()
    screen.addstr(1, 2, "Edit Approved Application", curses.A_BOLD)
    appid = curses_get_string_input(screen, 3, 2, "Enter AppID to edit: ")
    if not appid:
        screen.addstr(5, 2, "AppID cannot be empty.")
        screen.getch()
        return

    # Get current app details
    screen.addstr(5, 2, "Fetching application details...")
    screen.refresh()
    try:
        app_data = request_get_approved_app(appid)
        if not app_data:
            screen.addstr(7, 2, "Application not found.")
            screen.getch()
            return

        screen.clear()
        screen.addstr(1, 2, f"Edit Application: {appid}", curses.A_BOLD)

        if isinstance(app_data, dict):
            screen.addstr(3, 2, f"Current Name: {app_data.get('app_names', 'N/A')}")
            current_subs = app_data.get('subscriptions', 'N/A')
            # Truncate long subscription display
            if len(current_subs) > curses.COLS - 20:
                current_subs = current_subs[:curses.COLS - 23] + "..."
            screen.addstr(4, 2, f"Current Subs: {current_subs}")
        else:
            screen.addstr(3, 2, f"App Info: {str(app_data)[:curses.COLS - 15]}")

        screen.addstr(6, 2, "Leave blank to keep current value.")
        new_name = curses_get_string_input(screen, 8, 2, "New App Name: ")
        screen.addstr(10, 2, "Enter subscriptions in format: id1:name1|id2:name2|...")
        new_subs = curses_get_string_input(screen, 12, 2, "New Subscriptions: ")

        if new_name or new_subs:
            response = request_update_approved_app(
                appid,
                app_names=new_name if new_name else None,
                subscriptions=new_subs if new_subs else None,
                admin_user=config["adminusername"]
            )
            screen.addstr(14, 2, f"Response: {response or 'No response'}")
        else:
            screen.addstr(14, 2, "No changes made.")

    except Exception as e:
        screen.addstr(7, 2, f"Error: {e}")

    screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
    screen.getch()

def delete_approved_app(screen):
    """Delete an approved application and its associated files."""
    screen.clear()
    screen.addstr(1, 2, "Delete Approved Application", curses.A_BOLD)

    # First show the list of approved apps
    screen.addstr(3, 2, "Current Approved Applications:")
    try:
        response = request_list_approved_apps()
        if response:
            lines = response.split('\n')
            line_num = 5
            max_lines = min(10, curses.LINES - 15)
            for line in lines[:max_lines]:
                if line.strip():
                    display_line = line[:curses.COLS - 4] if len(line) > curses.COLS - 4 else line
                    screen.addstr(line_num, 2, display_line)
                    line_num += 1
            if len(lines) > max_lines:
                screen.addstr(line_num, 2, f"... and {len(lines) - max_lines} more")
                line_num += 1
        else:
            screen.addstr(5, 2, "No approved applications found.")
            screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
            screen.getch()
            return
    except Exception as e:
        screen.addstr(5, 2, f"Error fetching list: {e}")
        screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
        screen.getch()
        return

    screen.refresh()

    # Get AppID to delete
    appid = curses_get_string_input(screen, line_num + 2, 2, "Enter AppID to delete: ")
    if not appid:
        screen.addstr(line_num + 4, 2, "AppID cannot be empty.")
        screen.getch()
        return

    # Get app details for confirmation
    try:
        app_data = request_get_approved_app(appid)
        if not app_data:
            screen.addstr(line_num + 4, 2, "Application not found.")
            screen.getch()
            return

        screen.clear()
        screen.addstr(1, 2, "Confirm Deletion", curses.A_BOLD)

        if isinstance(app_data, dict):
            screen.addstr(3, 2, f"Application: {app_data.get('app_names', 'N/A')}")
            screen.addstr(4, 2, f"AppID: {appid}")
        else:
            screen.addstr(3, 2, f"App Info: {str(app_data)[:curses.COLS - 15]}")

        screen.addstr(6, 2, "This will delete:", curses.A_BOLD)
        screen.addstr(7, 4, "- The XML file from mod_blob")
        screen.addstr(8, 4, "- All DAT/BLOB files from steam2_sdk_depots")
        screen.addstr(9, 4, "- The database entry")

        screen.addstr(11, 2, "Are you sure you want to delete this application? (y/n)")
        screen.refresh()

        key = screen.getch()
        if key in (ord('y'), ord('Y')):
            screen.addstr(13, 2, "Deleting application...")
            screen.refresh()
            response = request_delete_approved_app(
                appid,
                admin_user=config["adminusername"],
                admin_ip="0.0.0.0"
            )
            screen.addstr(15, 2, f"Response: {response or 'No response'}")
        else:
            screen.addstr(13, 2, "Deletion cancelled.")

    except Exception as e:
        screen.addstr(line_num + 4, 2, f"Error: {e}")

    screen.addstr(curses.LINES - 1, 2, "Press Enter to return.")
    screen.getch()

def ftp_user_management_menu(screen):
    items = [
        ("List FTP Users", list_ftp_users),
        ("Add FTP User", add_ftp_user),
        ("Remove FTP User", remove_ftp_user),
        ("Back", None)
    ]
    curses_menu(screen, "FTP User Management", items)

def list_ftp_users(screen):
    resp = request_list_ftp_users()
    screen.clear(); screen.addstr(1,2,"FTP Users:")
    if resp:
        line=3
        for user in resp.split('|'):
            if user:
                screen.addstr(line,2,user); line+=1
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def add_ftp_user(screen):
    user = curses_get_string_input(screen,3,2,"Username: ")
    pw = curses_get_string_input(screen,4,2,"Password: ")
    perm = curses_get_string_input(screen,5,2,"Permissions (rwd...): ")
    if user and pw and perm:
        resp = request_add_ftp_user(user,pw,perm)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(7,2,str(msg)); screen.getch()

def remove_ftp_user(screen):
    user = curses_get_string_input(screen,3,2,"Username to remove: ")
    if user:
        resp = request_remove_ftp_user(user)
        msg = resp or "No response"
    else:
        msg = "Username required"
    screen.addstr(5,2,str(msg)); screen.getch()

def chatroom_management_menu(screen):
    items = [
        ("List Chatrooms", list_chatrooms),
        ("Create Chatroom", create_chatroom),
        ("Remove Chatroom", remove_chatroom),
        ("Back", None)
    ]
    curses_menu(screen, "Chatroom Management", items)

def list_chatrooms(screen):
    resp = request_chatroom_op({'action': 'list'})
    screen.clear(); screen.addstr(1,2,"Chatrooms:")
    if resp:
        try:
            rooms = json.loads(resp)
            line=3
            for r in rooms:
                if line<curses.LINES-1:
                    screen.addstr(line,2,f"{r['id']}: {r['name']}"); line+=1
        except Exception as e:
            screen.addstr(3,2,f"Parse error {e}")
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def create_chatroom(screen):
    name = curses_get_string_input(screen,3,2,"Name: ")
    owner = curses_get_string_input(screen,4,2,"Owner ID: ")
    if name and owner.isdigit():
        resp = request_chatroom_op({'action':'create','name':name,'owner':int(owner)})
    else:
        resp = 'Invalid'
    screen.addstr(6,2,str(resp)); screen.getch()

def remove_chatroom(screen):
    cid = curses_get_string_input(screen,3,2,"Chatroom ID: ")
    if cid.isdigit():
        resp = request_chatroom_op({'action':'remove','id':int(cid)})
    else:
        resp = 'Invalid'
    screen.addstr(5,2,str(resp)); screen.getch()

def clan_management_menu(screen):
    items = [
        ("List Clans", list_clans),
        ("Create Clan", create_clan),
        ("Remove Clan", remove_clan),
        ("Back", None)
    ]
    curses_menu(screen, "Clan Management", items)

def list_clans(screen):
    resp = request_clan_op({'action':'list'})
    screen.clear(); screen.addstr(1,2,"Clans:")
    if resp:
        try:
            clans = json.loads(resp)
            line=3
            for c in clans:
                if line<curses.LINES-1:
                    screen.addstr(line,2,f"{c['id']}: {c['name']}[{c['tag']}]" ); line+=1
        except Exception as e:
            screen.addstr(3,2,f"Parse error {e}")
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def create_clan(screen):
    name = curses_get_string_input(screen,3,2,"Name: ")
    tag = curses_get_string_input(screen,4,2,"Tag: ")
    owner = curses_get_string_input(screen,5,2,"Owner ID: ")
    if name and tag and owner.isdigit():
        resp = request_clan_op({'action':'create','name':name,'tag':tag,'owner':int(owner)})
    else:
        resp = 'Invalid'
    screen.addstr(7,2,str(resp)); screen.getch()

def remove_clan(screen):
    cid = curses_get_string_input(screen,3,2,"Clan ID: ")
    if cid.isdigit():
        resp = request_clan_op({'action':'remove','id':int(cid)})
    else:
        resp = 'Invalid'
    screen.addstr(5,2,str(resp)); screen.getch()

def news_management_menu(screen):
    data = request_news_op({'action':'list'})
    screen.clear(); screen.addstr(1,2,"News Updates:")
    if data:
        try:
            items = json.loads(data)
            line=3
            for ts in items:
                if line < curses.LINES-1:
                    screen.addstr(line,2,ts); line+=1
        except Exception as e:
            screen.addstr(3,2,f"Parse error {e}")
    else:
        screen.addstr(3,2,"No data")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def license_management_menu(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    if uid.isdigit():
        data = request_license_op({'action':'list','user':int(uid)})
    else:
        data = None
    screen.clear(); screen.addstr(1,2,"Licenses:")
    if data:
        screen.addstr(3,2,str(data))
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def inventory_management_menu(screen):
    uid = curses_get_string_input(screen,3,2,"User ID: ")
    if uid.isdigit():
        data = request_inventory_op({'user':int(uid)})
    else:
        data = None
    screen.clear(); screen.addstr(1,2,"Inventory:")
    if data:
        try:
            items = json.loads(data)
            line=3
            for it in items:
                if line<curses.LINES-1:
                    screen.addstr(line,2,f"{it['item']} app:{it['app']} qty:{it['qty']}"); line+=1
        except Exception as e:
            screen.addstr(3,2,f"Parse error {e}")
    else:
        screen.addstr(3,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def monitoring_menu(screen):
    items = [
        ("View Live Log", view_live_log),
        ("Auth Attempt Stats", view_auth_stats),
        ("Set Rate Limit", set_rate_limit),
        ("Bandwidth Usage", view_bandwidth_usage),
        ("Connection Count", view_connection_count),
        ("Edit Config", edit_config),
        ("Toggle Feature", toggle_feature),
        ("Session Report", get_session_report),
        ("Set FTP Quota", set_ftp_quota),
        ("Hot Reload Config", hot_reload_config),
        ("Back", None)
    ]
    curses_menu(screen, "Monitoring and Configuration", items)

def view_live_log(screen):
    data = request_live_log()
    screen.clear(); screen.addstr(1,2,"Live Log:")
    line=3
    if data:
        for ln in data.splitlines()[-(curses.LINES-5):]:
            screen.addstr(line,2,ln[:curses.COLS-4]); line+=1
    else:
        screen.addstr(line,2,"No data")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def view_auth_stats(screen):
    resp = request_auth_stats()
    screen.clear(); screen.addstr(1,2,"Auth Stats:")
    screen.addstr(3,2,str(resp))
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def set_rate_limit(screen):
    val = curses_get_string_input(screen,3,2,"Rate limit KB/s: ")
    if val:
        resp = request_set_rate_limit(int(val))
        msg = resp or "No response"
    else:
        msg = "Input required"
    screen.addstr(5,2,msg); screen.getch()

def view_bandwidth_usage(screen):
    resp = request_bandwidth_usage()
    screen.clear(); screen.addstr(1,2,"Bandwidth Usage:")
    screen.addstr(3,2,str(resp))
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def view_connection_count(screen):
    resp = request_connection_count()
    screen.clear(); screen.addstr(1,2,"Connection Count:")
    screen.addstr(3,2,str(resp))
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def edit_config(screen):
    key = curses_get_string_input(screen,3,2,"Config key: ")
    val = curses_get_string_input(screen,4,2,"New value: ")
    if key and val:
        resp = request_edit_configuration(key,val)
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,msg); screen.getch()

def toggle_feature(screen):
    name = curses_get_string_input(screen,3,2,"Feature name: ")
    state = curses_get_string_input(screen,4,2,"Enable? 1/0: ")
    if name and state:
        resp = request_toggle_feature(name, state=='1')
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(6,2,msg); screen.getch()

def get_session_report(screen):
    resp = request_user_session_report()
    screen.clear(); screen.addstr(1,2,"Session Report:")
    if resp:
        try:
            sessions = json.loads(resp)
            line = 3
            for sess in sessions:
                s = f"{sess.get('ip')}:{sess.get('port')} user={sess.get('username','')} rights={sess.get('rights')}"
                if line < curses.LINES-2:
                    screen.addstr(line,2,s[:curses.COLS-4]); line+=1
        except Exception as e:
            screen.addstr(3,2,f"Parse error: {e}")
    else:
        screen.addstr(3,2,"No data")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def set_ftp_quota(screen):
    user = curses_get_string_input(screen,3,2,"Username: ")
    q = curses_get_string_input(screen,4,2,"Quota MB: ")
    bw = curses_get_string_input(screen,5,2,"Throttle KB/s: ")
    if user and q and bw:
        resp = request_set_ftp_quota(user,int(q),int(bw))
        msg = resp or "No response"
    else:
        msg = "Fields required"
    screen.addstr(7,2,msg); screen.getch()

def hot_reload_config(screen):
    resp = request_hot_reload_config()
    screen.addstr(3,2,str(resp or "No response")); screen.getch()

def ui_list_blobs(screen):
    screen.clear(); screen.addstr(1, 2, "Fetching blob list..."); screen.refresh()
    blobs = request_blob_list(); screen.clear()
    if blobs is None:
        screen.addstr(1, 2, "Error: Could not retrieve blob list.")
        screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()
        return
    if not blobs:
        screen.addstr(1, 2, "No blobs available.")
        screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()
        return
    labels = [f"{b['id']} - {b['name']}" for b in blobs]
    idx = curses_select_from_list(screen, "Available Blobs", labels)
    if idx is None:
        return
    blob_id = blobs[idx]['id']
    screen.clear(); screen.addstr(1, 2, f"Swapping to '{blob_id}'..."); screen.refresh()
    swap_response = request_blob_swap(blob_id)
    screen.addstr(3, 2, f"Server: {swap_response if swap_response else 'No response/Error'}")
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def ui_add_dirserver_entry(screen):
    data = request_full_dirserver_json()
    categories = []
    if data:
        try:
            categories = sorted({s.get('server_type') for s in json.loads(data)})
        except Exception:
            categories = []
    if categories:
        idx = curses_select_from_list(screen, "Select Server Type", categories + ["<New Category>"])
        if idx is None:
            return
        if idx == len(categories):
            screen.clear()
            server_type = curses_get_string_input(screen, 1, 2, "Server Type: ", 20)
        else:
            server_type = categories[idx]
    else:
        screen.clear()
        server_type = curses_get_string_input(screen, 1, 2, "Server Type: ", 20)
    screen.clear(); screen.addstr(1, 2, "Add New Directory Server Entry")
    details = {'server_type': server_type}; y_offset = 3; status_line = y_offset + 5
    details['wan_ip'] = curses_get_string_input(screen, y_offset, 2, "WAN IP: ", 40)
    details['lan_ip'] = curses_get_string_input(screen, y_offset + 1, 2, "LAN IP: ", 40)
    port_str = curses_get_string_input(screen, y_offset + 2, 2, "Port: ", 5)
    permanent_str = curses_get_string_input(screen, y_offset + 3, 2, "Permanent (0 for No, 1 for Yes): ", 1)
    try:
        details['port'] = int(port_str); details['permanent'] = int(permanent_str)
        if details['permanent'] not in [0, 1]: raise ValueError("Permanent must be 0 or 1.")
        if not (0 <= details['port'] <= 65535): raise ValueError("Port must be 0-65535.")
        if not ('.' in details['wan_ip'] and '.' in details['lan_ip']): raise ValueError("IPs malformed.")
    except ValueError as ve:
        screen.addstr(status_line, 2, f"Input Error: {ve}"); screen.refresh()
        screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    json_payload_bytes = json.dumps(details).encode('utf-8')
    screen.addstr(status_line, 2, "Sending to server..."); screen.refresh()
    response = request_add_dirserver_entry(json_payload_bytes)
    screen.move(status_line, 2); screen.clrtoeol()
    screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response/Error.'}")
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def ui_display_server_list(screen, menu_title: str, command_code: bytes):
    # ... (content as before) ...
    screen.clear(); screen.addstr(1, 2, f"Fetching: {menu_title}..."); screen.refresh()
    packed_server_list_bytes = request_server_list(command_code)
    screen.clear() 
    if packed_server_list_bytes is None: screen.addstr(1, 2, "Error: Could not retrieve server list.")
    elif not packed_server_list_bytes: screen.addstr(1, 2, f"{menu_title}: No servers or empty list.")
    else:
        try:
            if len(packed_server_list_bytes) < 2: raise ValueError("Response too short.")
            count = struct.unpack(">H", packed_server_list_bytes[:2])[0]
            server_data_bytes = packed_server_list_bytes[2:]
            expected_length = count * 6 
            if len(server_data_bytes) < expected_length: raise ValueError(f"Data length mismatch.")
            screen.addstr(1, 2, f"{menu_title} (Count: {count}):")
            current_line = 3
            for i in range(count):
                ip_port_chunk = server_data_bytes[i*6 : (i+1)*6]
                ip_str, port_int = local_utils.decodeIP(ip_port_chunk) 
                if current_line < curses.LINES - 2:
                    screen.addstr(current_line, 4, f"{i+1}. IP: {ip_str}, Port: {port_int}")
                    current_line += 1
                else: screen.addstr(current_line, 4, "More entries..."); break
            if count == 0: screen.addstr(current_line, 4, "No servers listed.")
        except (struct.error, ValueError) as e: screen.addstr(1, 2, f"Error parsing: {e}")
        except Exception as e: screen.addstr(1, 2, f"Unexpected error: {e}")
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def ui_list_full_dirservers(screen, server_list_cache=None):
    # ... (content as before) ...
    screen.clear(); status_line = curses.LINES - 2 
    if server_list_cache is None: 
        screen.addstr(1, 2, "Fetching Full Dir List (JSON)..."); screen.refresh()
        json_response_str = request_full_dirserver_json(); screen.clear()
        if json_response_str is None: screen.addstr(1, 2, "Error retrieving list."); screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
        elif not json_response_str: screen.addstr(1, 2, "No data or empty list."); screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
        try: server_list_cache = json.loads(json_response_str)
        except json.JSONDecodeError as jde: screen.addstr(1,2,f"JSON Error: {jde}"); screen.addstr(3,2,f"Raw: {json_response_str[:200]}"); screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
    if not server_list_cache: screen.addstr(1, 2, "List is empty.")
    else:
        screen.addstr(1, 2, f"All Registered Dir Servers (Count: {len(server_list_cache)}):")
        current_line = 3; max_len = curses.COLS - 5
        for i, info in enumerate(server_list_cache):
            d_str = f"{i+1}. {info.get('server_type','N/A')} WAN:{info.get('wan_ip','N/A')}:{info.get('port','N/A')} LAN:{info.get('lan_ip','N/A')}:{info.get('port','N/A')} Perm:{'Y' if info.get('permanent') else 'N'} TS:{info.get('timestamp','N/A')}"
            if current_line < curses.LINES - 4: 
                screen.addstr(current_line, 4, d_str[:max_len-(3 if len(d_str)>max_len else 0)] + ("..." if len(d_str)>max_len else ""))
                current_line += 1
            else: screen.addstr(current_line, 4, "More entries..."); current_line+=1; break
    prompt_y = current_line +1
    if prompt_y >= curses.LINES -2: prompt_y = curses.LINES -3
    if server_list_cache : 
        row_num_str = curses_get_string_input(screen, prompt_y, 2, "Enter row # to delete (0 to cancel): ", 3)
        screen.move(prompt_y, 2); screen.clrtoeol() 
        try:
            row_num = int(row_num_str)
            if row_num == 0: screen.addstr(status_line, 2, "Deletion cancelled.")
            elif 1 <= row_num <= len(server_list_cache):
                server_to_delete = server_list_cache[row_num - 1]
                identifier_dict = {"wan_ip": server_to_delete["wan_ip"], "lan_ip": server_to_delete["lan_ip"], 
                                   "port": server_to_delete["port"], "server_type": server_to_delete["server_type"]}
                json_payload_bytes = json.dumps(identifier_dict).encode('utf-8')
                screen.addstr(status_line, 2, f"Deleting entry {row_num}..."); screen.refresh()
                response = request_del_dirserver_entry(json_payload_bytes)
                screen.move(status_line, 2); screen.clrtoeol()
                screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response/Error.'}")
                if "successfully" in (response or "").lower(): ui_list_full_dirservers(screen, server_list_cache=None); return 
            else: screen.addstr(status_line, 2, "Invalid row number.")
        except ValueError: screen.addstr(status_line, 2, "Invalid input.")
        except Exception as e: screen.addstr(status_line, 2, f"Error: {e}")
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()


def _format_dirserver_entry(info):
    """Return a single-line summary of a directory server entry."""
    return (f"{info.get('server_type','N/A')} WAN:{info.get('wan_ip','N/A')}:{info.get('port','N/A')} "
            f"LAN:{info.get('lan_ip','N/A')}:{info.get('port','N/A')} Perm:{'Y' if info.get('permanent') else 'N'}")

def directory_server_management_menu(screen):
    items = [
        ("List Categories", show_dirserver_categories),
        ("List All Servers", list_all_dirservers),
        ("List Servers in Category", list_dirservers_by_category),
        ("Add Server", ui_add_dirserver_entry),
        ("Remove Server", ui_remove_dirserver_entry),
        ("Edit Server", ui_edit_dirserver_entry),
        ("Back", None)
    ]
    curses_menu(screen, "Directory Server List Manager", items)

def show_dirserver_categories(screen):
    data = request_full_dirserver_json()
    screen.clear()
    if data:
        try:
            servers=json.loads(data)
            cats=sorted({s.get('server_type') for s in servers})
            screen.addstr(1,2,"Categories:")
            line=3
            for c in cats:
                screen.addstr(line,2,str(c)); line+=1
        except Exception as e:
            screen.addstr(1,2,f"Error: {e}")
    else:
        screen.addstr(1,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def list_all_dirservers(screen):
    data = request_full_dirserver_json()
    screen.clear()
    if data:
        try:
            servers=json.loads(data)
            line=1
            for s in servers:
                if line>=curses.LINES-2: break
                screen.addstr(line,2,str(s)); line+=1
        except Exception as e:
            screen.addstr(1,2,f"Error: {e}")
    else:
        screen.addstr(1,2,"No response")
    screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch()

def list_dirservers_by_category(screen):
    data = request_full_dirserver_json()
    servers = []
    if data:
        try:
            servers = json.loads(data)
        except Exception:
            servers = []
    categories = sorted({s.get('server_type') for s in servers})
    if not categories:
        screen.clear(); screen.addstr(1, 2, "No categories"); screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    idx = curses_select_from_list(screen, "Select Category", categories)
    if idx is None:
        return
    cat = categories[idx]
    screen.clear()
    line = 1
    for s in [srv for srv in servers if srv.get('server_type') == cat]:
        if line >= curses.LINES - 2:
            break
        screen.addstr(line, 2, str(s)[: curses.COLS - 4])
        line += 1
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def ui_remove_dirserver_entry(screen):
    data = request_full_dirserver_json()
    servers = []
    if data:
        try:
            servers = json.loads(data)
        except Exception:
            servers = []
    if not servers:
        screen.clear(); screen.addstr(1, 2, "No response"); screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    categories = sorted({s.get('server_type') for s in servers})
    cat_idx = curses_select_from_list(screen, "Select Category", categories)
    if cat_idx is None:
        return
    cat = categories[cat_idx]
    cat_servers = [s for s in servers if s.get('server_type') == cat]
    srv_idx = curses_select_from_list(screen, "Select Server", [_format_dirserver_entry(s) for s in cat_servers])
    if srv_idx is None:
        return
    to_del = cat_servers[srv_idx]
    identifier = {'wan_ip': to_del['wan_ip'], 'lan_ip': to_del['lan_ip'], 'port': to_del['port'], 'server_type': to_del['server_type']}
    screen.clear()
    resp = request_del_dirserver_entry(json.dumps(identifier).encode('utf-8'))
    screen.addstr(1, 2, str(resp or 'No response'))
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def ui_edit_dirserver_entry(screen):
    data = request_full_dirserver_json()
    servers = []
    if data:
        try:
            servers = json.loads(data)
        except Exception:
            servers = []
    if not servers:
        screen.clear(); screen.addstr(1, 2, "No response"); screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    categories = sorted({s.get('server_type') for s in servers})
    cat_idx = curses_select_from_list(screen, "Select Category", categories)
    if cat_idx is None:
        return
    cat = categories[cat_idx]
    cat_servers = [s for s in servers if s.get('server_type') == cat]
    srv_idx = curses_select_from_list(screen, "Select Server", [_format_dirserver_entry(s) for s in cat_servers])
    if srv_idx is None:
        return
    original = cat_servers[srv_idx]
    details = original.copy()
    screen.clear(); screen.addstr(1, 2, "Edit Directory Server Entry")
    y = 3
    val = curses_get_string_input(screen, y, 2, f"WAN IP [{details['wan_ip']}]: ", 40)
    if val: details['wan_ip'] = val
    y += 1
    val = curses_get_string_input(screen, y, 2, f"LAN IP [{details['lan_ip']}]: ", 40)
    if val: details['lan_ip'] = val
    y += 1
    val = curses_get_string_input(screen, y, 2, f"Port [{details['port']}]: ", 5)
    if val: details['port'] = int(val)
    y += 1
    val = curses_get_string_input(screen, y, 2, f"Server Type [{details['server_type']}]: ", 20)
    if val: details['server_type'] = val
    y += 1
    val = curses_get_string_input(screen, y, 2, f"Permanent (0/1) [{details.get('permanent', 0)}]: ", 1)
    if val: details['permanent'] = int(val)
    status_line = y + 2
    identifier = {'wan_ip': original['wan_ip'], 'lan_ip': original['lan_ip'], 'port': original['port'], 'server_type': original['server_type']}
    request_del_dirserver_entry(json.dumps(identifier).encode('utf-8'))
    json_payload_bytes = json.dumps(details).encode('utf-8')
    screen.addstr(status_line, 2, "Sending to server..."); screen.refresh()
    response = request_add_dirserver_entry(json_payload_bytes)
    screen.move(status_line, 2); screen.clrtoeol()
    screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response/Error.'}")
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def content_server_management_menu(screen):
    items = [
        ("List All Registered Content Servers (JSON)", ui_list_full_contentservers),
        ("Add Content Server Entry", ui_add_contentserver_entry),
        ("Edit Content Server Entry", ui_edit_contentserver_entry),
        ("Find Content Servers by AppID", ui_find_content_servers_by_appid),
        ("Back", None)
    ]
    curses_menu(screen, "Content Server Management Menu", items)

def ui_add_contentserver_entry(screen):
    # ... (content as before) ...
    screen.clear(); screen.addstr(1, 2, "Add New Content Server Entry")
    details = {}; y = 3; x = 2; input_width = 50; 
    details['server_id'] = curses_get_string_input(screen, y, x, "Server ID (UUID, optional, Enter to skip): ", input_width); y+=1
    details['wan_ip'] = curses_get_string_input(screen, y, x, "WAN IP (Required): ", input_width); y+=1
    details['lan_ip'] = curses_get_string_input(screen, y, x, "LAN IP (Required): ", input_width); y+=1
    port_str = curses_get_string_input(screen, y, x, "Port (Required): ", 5); y+=1
    details['region'] = curses_get_string_input(screen, y, x, "Region (e.g., US, Required): ", 10); y+=1
    applist_str = curses_get_string_input(screen, y, x, "AppList (id,ver;id,ver or empty): ", input_width); y+=1
    cellid_str = curses_get_string_input(screen, y, x, "CellID (Required): ", 5); y+=1
    is_permanent_str = curses_get_string_input(screen, y, x, "Permanent (1=Yes, 0=No, Required): ", 1); y+=1
    is_pkgcs_str = curses_get_string_input(screen, y, x, "Package CS (true/false, Required): ", 5); y+=2
    status_line = y
    try:
        if not all([details['wan_ip'], details['lan_ip'], details['region'], port_str, cellid_str, is_permanent_str, is_pkgcs_str]):
            raise ValueError("All fields except Server ID and AppList are required.")
        details['port'] = int(port_str); details['cellid'] = int(cellid_str); details['is_permanent'] = int(is_permanent_str)
        if details['is_permanent'] not in [0,1]: raise ValueError("Permanent must be 0 or 1.")
        if not (0 <= details['port'] <= 65535): raise ValueError("Port must be between 0 and 65535.")
        is_pkgcs_lower = is_pkgcs_str.lower()
        if is_pkgcs_lower == 'true': details['is_pkgcs'] = True
        elif is_pkgcs_lower == 'false': details['is_pkgcs'] = False
        else: raise ValueError("Package CS must be 'true' or 'false'.")
        parsed_applist = []
        if applist_str: 
            pairs = applist_str.split(';')
            for pair in pairs:
                if not pair.strip(): continue 
                parts = pair.split(',')
                if len(parts) == 2 and parts[0].strip() and parts[1].strip(): parsed_applist.append([parts[0].strip(), parts[1].strip()])
                else: raise ValueError("AppList format error. Use 'appid1,ver1;appid2,ver2'.")
        details['received_applist'] = parsed_applist
        if not details['server_id']: details['server_id'] = None 
    except ValueError as ve:
        screen.addstr(status_line, 2, f"Input Error: {ve}"); screen.refresh()
        screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    json_payload_bytes = json.dumps(details).encode('utf-8')
    screen.addstr(status_line, 2, "Sending to server..."); screen.refresh()
    response = request_add_contentserver_entry(json_payload_bytes)
    screen.move(status_line, 2); screen.clrtoeol() 
    screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response or error.'}")
    screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch()

def ui_list_full_contentservers(screen, server_list_cache=None):
    # ... (content as before, including deletion prompt logic) ...
    screen.clear(); status_line = curses.LINES - 2 
    if server_list_cache is None:
        screen.addstr(1, 2, "Fetching Full Content Server List (JSON)..."); screen.refresh()
        json_response_str = request_full_contentserver_json(); screen.clear()
        if json_response_str is None: screen.addstr(1, 2, "Error retrieving list."); screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
        elif not json_response_str: screen.addstr(1, 2, "No content server data or empty list."); screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
        try: server_list_cache = json.loads(json_response_str)
        except json.JSONDecodeError as jde: screen.addstr(1,2,f"JSON Error: {jde}"); screen.addstr(3,2,f"Raw: {json_response_str[:200]}"); screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
    if not server_list_cache: screen.addstr(1, 2, "Content server list is empty.")
    else:
        screen.addstr(1, 2, f"All Registered Content Servers (Count: {len(server_list_cache)}):")
        current_line = 3; max_text_width = curses.COLS - 6 
        max_items_on_screen = (curses.LINES - 1 - (current_line + 2)) // 4 
        for i, info in enumerate(server_list_cache):
            if max_items_on_screen > 0 and i >= max_items_on_screen : screen.addstr(current_line, 4, "More entries (screen full)..."); current_line +=1; break
            server_id = info.get('server_id', 'N/A'); wan_ip = info.get('wan_ip', 'N/A'); lan_ip = info.get('lan_ip', 'N/A')
            port = info.get('port', 'N/A'); region = info.get('region', 'N/A'); timestamp = info.get('timestamp', 'N/A')
            applist_count = len(info.get('applist', [])); applist_summary = f"{applist_count} AppIDs"
            is_perm = "Yes" if info.get('is_permanent') else "No"; is_pkg = "Yes" if info.get('is_pkgcs') else "No"
            cellid = info.get('cellid', 'N/A')
            line1 = f"{i+1}. ID: {server_id} WAN: {wan_ip}:{port} LAN: {lan_ip}:{port}"
            line2 = f"   Region: {region}, CellID: {cellid}, Perm: {is_perm}, PkgCS: {is_pkg}"
            line3 = f"   Apps: {applist_summary}, Timestamp: {timestamp}"
            if current_line < curses.LINES - 3: screen.addstr(current_line, 4, line1[:max_text_width]); current_line +=1
            else: screen.addstr(current_line, 4, "More entries..."); current_line+=1; break
            if current_line < curses.LINES - 2: screen.addstr(current_line, 4, line2[:max_text_width]); current_line +=1
            else: screen.addstr(current_line, 4, "More entries..."); current_line+=1; break
            if current_line < curses.LINES - 1: screen.addstr(current_line, 4, line3[:max_text_width]); current_line +=1
            else: screen.addstr(current_line, 4, "More entries..."); current_line+=1; break
            if current_line < curses.LINES - 1 and i < len(server_list_cache) -1: screen.addstr(current_line, 4, "-" * (max_text_width // 2)); current_line +=1
            if current_line >= curses.LINES -1 : break 
    prompt_y = current_line + 1 if current_line < curses.LINES - 2 else curses.LINES - 3
    if prompt_y < 3 : prompt_y = 3 
    if server_list_cache : 
        row_num_str = curses_get_string_input(screen, prompt_y, 2, "Enter row # to delete (0 to cancel): ", 3)
        screen.move(prompt_y, 2); screen.clrtoeol() 
        try:
            row_num = int(row_num_str)
            if row_num == 0: screen.addstr(status_line, 2, "Deletion cancelled.")
            elif 1 <= row_num <= len(server_list_cache):
                selected_index = row_num - 1; server_to_delete = server_list_cache[selected_index]
                server_id_to_delete = server_to_delete.get("server_id")
                if not server_id_to_delete: screen.addstr(status_line, 2, f"Error: Entry {row_num} has no server_id."); screen.refresh(); curses.napms(2000)
                else:
                    identifier_dict = {"server_id": server_id_to_delete }; json_payload_bytes = json.dumps(identifier_dict).encode('utf-8')
                    screen.addstr(status_line, 2, f"Deleting entry {row_num} (ID: {server_id_to_delete})..."); screen.refresh()
                    response = request_del_contentserver_entry(json_payload_bytes)
                    screen.move(status_line, 2); screen.clrtoeol()
                    screen.addstr(status_line, 2, f"Server Response: {response if response else 'No response/Error.'}")
                    if "successfully" in (response or "").lower(): ui_list_full_contentservers(screen, server_list_cache=None); return 
            else: screen.addstr(status_line, 2, "Invalid row number.")
        except ValueError: screen.addstr(status_line, 2, "Invalid input. Please enter a number.")
        except Exception as e: screen.addstr(status_line, 2, f"Error: {e}")
    screen.addstr(curses.LINES - 1, 2, "Press any key to return..."); screen.getch()

def ui_edit_contentserver_entry(screen):
    """Edit an existing content server entry by deleting and re-adding it."""
    screen.clear()
    screen.addstr(1, 2, "Fetching current list...")
    screen.refresh()
    json_response_str = request_full_contentserver_json()
    screen.clear()
    if not json_response_str:
        screen.addstr(1, 2, "Unable to retrieve server list")
        screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    try:
        servers = json.loads(json_response_str)
    except json.JSONDecodeError:
        screen.addstr(1, 2, "Invalid JSON from server")
        screen.addstr(curses.LINES - 1, 2, "Press key..."); screen.getch(); return
    if not servers:
        screen.addstr(1,2,"No servers registered")
        screen.addstr(curses.LINES-1,2,"Press key..."); screen.getch(); return
    for i, srv in enumerate(servers, start=1):
        if i >= curses.LINES-3: break
        screen.addstr(i,2,f"{i}. {srv.get('wan_ip')}:{srv.get('port')} id={srv.get('server_id')}")
    idx_str = curses_get_string_input(screen, curses.LINES-2, 2, "Row to edit (0 cancel): ",3)
    try:
        idx = int(idx_str)
    except ValueError:
        return
    if idx < 1 or idx > len(servers):
        return
    old = servers[idx-1]
    identifier = json.dumps({'server_id': old.get('server_id')}).encode('utf-8')
    request_del_contentserver_entry(identifier)
    ui_add_contentserver_entry(screen)

def ui_find_content_servers_by_appid(screen):
    """Interactive lookup of content servers - browse AppIDs, then versions, then see servers."""
    # Get all AppIDs and versions from the server
    screen.clear()
    screen.addstr(1, 2, "Loading content server data...")
    screen.refresh()

    appid_data = request_interactive_content_server_finder()
    screen.clear()

    if appid_data is None:
        screen.addstr(1, 2, "Error retrieving content server data.")
        screen.addstr(curses.LINES-1, 2, "Press any key to return..."); screen.getch()
        return

    if not appid_data.get('appid_data'):
        screen.addstr(1, 2, "No AppIDs found in content servers.")
        screen.addstr(curses.LINES-1, 2, "Press any key to return..."); screen.getch()
        return

    app_data = appid_data['appid_data']

    # Step 1: Select AppID
    appids = sorted([int(appid) for appid in app_data.keys()])
    appid_items = [(f"AppID {appid} ({len(app_data[str(appid)])} versions)", appid) for appid in appids]

    def select_appid(screen):
        return curses_menu_with_selection(screen, "Select an AppID:", appid_items)

    selected_appid = select_appid(screen)
    if selected_appid is None:
        return

    # Step 2: Select Version for the chosen AppID
    versions = sorted([int(v) for v in app_data[str(selected_appid)].keys()])
    version_items = [(f"Version {version} ({len(app_data[str(selected_appid)][str(version)])} servers)", version) for version in versions]

    def select_version(screen):
        return curses_menu_with_selection(screen, f"Select a version for AppID {selected_appid}:", version_items)

    selected_version = select_version(screen)
    if selected_version is None:
        return

    # Step 3: Display content servers for the selected AppID and version
    servers = app_data[str(selected_appid)][str(selected_version)]

    screen.clear()
    screen.addstr(1, 2, f"Content Servers for AppID {selected_appid} Version {selected_version}:")
    screen.addstr(2, 2, f"Found {len(servers)} server(s)")
    screen.addstr(3, 2, "-" * 60)

    line = 5
    for i, server in enumerate(servers):
        if line >= curses.LINES - 2:
            break

        wan_ip = server.get('wan_ip', 'Unknown')
        lan_ip = server.get('lan_ip', 'Unknown')
        port = server.get('port', 'Unknown')
        region = server.get('region', 'Unknown')
        cellid = server.get('cellid', 'Unknown')

        screen.addstr(line, 4, f"{i+1}. WAN: {wan_ip}:{port}")
        line += 1
        if line < curses.LINES - 2:
            screen.addstr(line, 8, f"LAN: {lan_ip}:{port}")
            line += 1
        if line < curses.LINES - 2:
            screen.addstr(line, 8, f"Region: {region}, Cell: {cellid}")
            line += 2

    screen.addstr(curses.LINES - 1, 2, "Press any key to return..."); screen.getch()

def curses_menu_with_selection(screen, title, items):
    """Display a menu and return the selected value (not the label)."""
    current = 0
    curses.curs_set(0)

    while True:
        screen.clear()
        screen.addstr(1, 2, title)
        screen.addstr(2, 2, "Use arrow keys to navigate, Enter to select, 'q' to quit")

        # Calculate how many items can fit on screen
        max_items = curses.LINES - 6
        start_idx = 0
        if len(items) > max_items:
            if current >= max_items // 2:
                start_idx = min(current - max_items // 2, len(items) - max_items)

        for i in range(min(max_items, len(items))):
            item_idx = start_idx + i
            if item_idx >= len(items):
                break

            y = 4 + i
            label, value = items[item_idx]

            if item_idx == current:
                screen.addstr(y, 4, f"► {label}", curses.A_REVERSE)
            else:
                screen.addstr(y, 4, f"  {label}")

        # Show scroll indicator if needed
        if len(items) > max_items:
            screen.addstr(curses.LINES - 2, 2, f"Items {start_idx + 1}-{min(start_idx + max_items, len(items))} of {len(items)}")

        key = screen.getch()

        if key == curses.KEY_UP and current > 0:
            current -= 1
        elif key == curses.KEY_DOWN and current < len(items) - 1:
            current += 1
        elif key == ord('\n') or key == ord('\r'):  # Enter
            return items[current][1]  # Return the value, not the label
        elif key == ord('q') or key == ord('Q'):
            return None
        elif key == 27:  # Escape
            return None

def run_user_manager_cli(screen):
    """Ends curses and launches the user_management.py script for full features."""
    screen.clear()
    screen.addstr(1, 2, "Launching User Management CLI...")
    screen.addstr(2, 2, "Return here when done.")
    screen.refresh()
    curses.napms(1500)
    curses.endwin()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    um_script_path = os.path.join(current_dir, "user_management.py")
    try:
        print(f"Running {um_script_path} using {sys.executable}")
        subprocess.call([sys.executable, um_script_path])
    except Exception as e:
        print(f"Error running user management CLI: {e}")

def run_blobmgr_ui(screen):
    """Launch the blob manager using the existing authenticated session."""

    screen.clear()
    screen.addstr(1, 2, "Launching Blob Manager...")
    screen.refresh()
    curses.napms(1000)
    curses.def_prog_mode()
    curses.endwin()

    try:
        import blobmgr
        # Call the function instead of reloading the module
        blobmgr.run_blob_manager()
    except Exception as exc:
        print(f"Error launching blob manager: {exc}")
        input("Press Enter to continue...")
    finally:
        curses.reset_prog_mode()
        screen.refresh()
    # curses.wrapper in start_curses_app will handle re-initializing curses
    # when this function returns.

# Removed ui_list_blobs_gui function entirely

def start_curses_app():
    curses.wrapper(main_menu)

if __name__ == "__main__":
    if not perform_handshake_and_authenticate(config): sys.exit("Handshake failed.")
    if not login_to_server(config["adminusername"], config["adminpassword"]): sys.exit("Login failed.")
    # Start heartbeat thread to keep session alive and prevent timeout
    start_heartbeat_thread()
    try:
        start_curses_app()
    finally:
        # Ensure heartbeat thread is stopped and logout is performed on exit
        stop_heartbeat_thread()
        logout_from_server()
