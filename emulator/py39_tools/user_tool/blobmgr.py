import os
import json
import re
import sys
import logging
from datetime import datetime
# from pathlib import Path # No longer directly needed for Path object manipulations
from threading import Thread
import configparser # For client_config.ini
from time import sleep

# Ensure repository root (containing `libs`) is on the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import libs.PySimpleGUI as psg
from libs.PySimpleGUI import WIN_CLOSED
# Updated networking imports
import networking
from networking import (
    request_blobmgr_file_list,
    request_blobmgr_swap,
    authenticated,
)
from pyperclip import copy as clipboardcopy

# Function to strip comments from the config values (can be kept if emulator.ini is still read for other purposes)
def strip_comments(value):
    """Remove trailing comment markers from configuration values."""
    if value is None:
        return None
    for marker in (';', '#'):
        if marker in value:
            value = value.split(marker, 1)[0]
    return value.strip()

# Date and time normalization functions might still be useful if server sends varied formats,
# but the server should ideally send a consistent format for 'Date'.
# Keeping them for now, but they might become obsolete if server data is clean.
def normalize_date_format(steam_date):
    steam_date = steam_date.strip()
    steam_date = steam_date.replace('/', '-').replace('_', '-')
    try:
        datetime.strptime(steam_date, '%Y-%m-%d')
        return steam_date
    except ValueError:
        return None

def normalize_time_format(steam_time):
    steam_time = steam_time.strip()
    time_pattern = re.compile(r'(\d{2})[:\-_](\d{2})[:\-_](\d{2})')
    match = time_pattern.match(steam_time)
    if match:
        time_str = f"{match.group(1)}:{match.group(2)}:{match.group(3)}"
        try:
            datetime.strptime(time_str, '%H:%M:%S')
            return time_str
        except ValueError:
            return None
    return None


class BlobManager(object):
    window = None

    def __init__(self) -> None:
        self.log = logging.getLogger('BlobManager')
        self.windowico = os.path.join(os.path.dirname(__file__), "icon.ico")
        # psg.LOOK_AND_FEEL_TABLE setup can remain
        psg.LOOK_AND_FEEL_TABLE['SteamGreen.json'] = {
                "BACKGROUND":    "#4c5844",
                "TEXT":          "#ffffff",
                "INPUT":         "#ffffff",
                "TEXT_INPUT":    "#000000",
                "SCROLL":        "#5a6a50",
                "BUTTON":        ("#889180", "#4c5844"),
                "PROGRESS":      ("#958831", "#3e4637"),
                "BORDER":        1,
                "SLIDER_DEPTH":  0,
                "PROGRESS_DEPTH":0,
                "COLOR_LIST":    ["#ff00fd", "#ff00fd", "#ff00fd", "#ff00fd"],
                "DESCRIPTION":   ["Grey", "Green", "Vintage"],
        }
        psg.set_options(font = ('Verdana', 9), icon = self.windowico)
        psg.theme('SteamGreen.json')

        # Show initial dialog to choose between 'Files' and 'Database'
        choice_layout = [
                [psg.Text('Would you like to read the blobs from the database or from files?')],
                [psg.Radio('Files', 'RADIO1', key='-FILES-')],
                [psg.Radio('Database', 'RADIO1', default=True, key='-DATABASE-')],
                [psg.Button('OK'), psg.Button('Cancel')]
        ]
        choice_window = psg.Window('Choose Data Source', choice_layout, finalize=True)
        event, values = choice_window.read()
        if event == 'Cancel' or event == psg.WIN_CLOSED:
            choice_window.close()
            sys.exit(0)
        elif event == 'OK':
            if values['-FILES-']:
                self.blob_source_type = 'File'
            elif values['-DATABASE-']:
                self.blob_source_type = 'DB'
            else:
                self.blob_source_type = 'DB'  # Default to database
        choice_window.close()

        # Check if already authenticated via remote_admintool
        self.connected_to_admin_server = networking.authenticated

        self.row = None
        self.multiple_rows = None
        self.Rows = [] # Will be populated from server
        self.Selected = None
        self.Language = "" # Localization config can remain
        self.config = configparser.ConfigParser() # For blobmanager.ini (localization)

        # Initial data population - only if authenticated
        if self.connected_to_admin_server:
            self.Rows = self.PopulateRowsFromServer(self.blob_source_type)
        else:
            # Handle case where connection failed - PopulateRowsFromServer should return empty or error indication
            self.Rows = [[ "Error: Not connected to admin server. Launch from remote_admintool.", "", "", "", "", "", {} ]]


        # --- Rest of __init__ for GUI setup ---
        # The loading layout can be simplified or removed if connection is fast
        loadinglayout = [
                [psg.Push(), psg.Text("Loading Blob Information...", justification = 'center', key = '-STATUS-'), psg.Push()],
                [psg.ProgressBar(100, orientation = 'h', expand_x = True, size = (20, 20), border_width = 1, key = '-PBAR-', relief = psg.RELIEF_SUNKEN, style = 'xpnative')]
        ]

        loader = psg.Window("Blob Manager", loadinglayout, size = (400, 70), finalize = True, disable_close = True)
        # Simulate some loading time or update status after PopulateRowsFromServer
        loader['-STATUS-'].update(value = 'Processing table data...' if self.connected_to_admin_server else 'Connection Failed.')
        sleep(0.5) # Brief pause

        EnglishDefault = { # Localization can remain
                'label_swap':                'Change',
                'label_custom':              'Custom',
                'label_yes':                 'Yes',
                'label_no':                  'No',
                'label_date':                'Date',
                'label_description':         'Description',
                'label_blobmgr':             'Blob Manager',
                'label_version':             'Version',
                'label_selected':            'Selected:',
                'label_selected_none':       'None',
                'label_use_preprocessed':    'USING PACKED BLOB FILE',
                'label_copyclip':            'SELECTION STORED TO CLIPBOARD',
                'label_blobinfo_title':      'Blob Information',
                'label_appsdetected':        'Apps Detected:',
                'label_subsdetected':        'Subs Detected:',
                'label_search_fail':         'Search didn\'t find anything.',
                'label_simulation_title':    'Time simulation',
                'label_simulation_play':     'Start',
                'label_simulation_pause':    'Pause',
                'label_simulation_unpause':  'Unpause',
                'label_simulation_stop':     'Stop',
                'label_simulation_date':     'Current Date:',
                'label_simulation_speed':    'Time Speed:',
                'label_simulation_speed2':   'How many seconds should pass per minute.',
                'label_installed_blob1':     'Installed FirstBlob: ',
                'label_installed_blob1_none':'This will display once you install a blob from...',
                'label_installed_blob2':     'Installed SecondBlob: ',
                'label_installed_blob2_none':'...the table below',
                'label_extract_success':     'SUCCESSFULLY EXTRACTED SELECTED BLOBS.',
                'label_swap_success':        'SUCCESSFULLY INSTALLED SELECTED BLOBS.',
                'label_swapping':            'INSTALLING SELECTED BLOB, ONE SECOND.',
                'label_extract_failure':     'FAILED TO EXTRACT PACKED BLOBS.',
                'label_swap_error1':         'NO FIRSTBLOBS! SWAP ABORTED.',
                'label_swap_error2':         'FAILED TO DETECT FIRSTBLOB! SWAP ABORTED.',
                'label_swap_error3':         'FAILED! COULD NOT WRITE/READ FILE. SWAP ABORTED',
                'label_error_title':         'Error.',
                'label_error_text1':         "Error! You need to run this program in the same folder as the emulator.\r\nFailed to find emulator.ini",
                'label_error_text2':         'Failed to preserve file dates of copied blobs.',
                'label_error_text3':         'The extraction destination must be a folder.',
                'label_error_generic':       'An error occured while performing the selected action\r\nPlease show BillySB a screenshot of the error below.\r\n',
                'label_menu1_item1':         '&Extract',
                'label_menu1_item2_1':       '!&Packed',
                'label_menu1_item2_2':       '&Packed',
                'label_menu1_item3':         'Extract',
                'label_menu1_item4':         'Close',
        }

        # Configuration Management
        DefaultConfigAge = 39

        loader['-STATUS-'].update(value = 'Checking configurations..')
        if not self.DoesFileExist('./blobmanager.ini'):
            # Create settings file.
            self.config['settings'] = {
                    'ConfigAge':        DefaultConfigAge,
                    'DebugMode':        False,
                    'Language':         'english',
                    'WindowRefreshTime':0.25,
                    'WindowUpdateTime': 120
            }
            self.config['english'] = EnglishDefault
            try:
                with open('./blobmanager.ini', 'w') as configfile:
                    self.config.write(configfile)
            except:
                pass
        else:
            # Load settings file.
            self.config.read('./blobmanager.ini')
            try:
                if int(self.config['settings']['ConfigAge']) < DefaultConfigAge:
                    self.config['english'] = EnglishDefault
                    try:
                        with open('./blobmanager.ini', 'w') as configfile:
                            self.config.write(configfile)
                    except:
                        pass
            except Exception as ex:
                psg.popup('Legacy configuration detected.\r\nPlease delete blobmanager.ini')
        if self.config.getboolean('settings', 'DebugMode'):
            # psg.show_debugger_window() # Comment me out!!
            psg.Print('Re-routing the stdout', do_not_reroute_stdout = False)
        loader['-PBAR-'].update(current_count = 10)
        # self.PackReader = None # Likely obsolete
        # self.VersionPak = 'Unknown' # Likely obsolete

        # loader['-PBAR-'].update(current_count = 35) # Progress bar may not be needed for this step

        # loader['-STATUS-'].update(value = 'Processing table data...') # Status updated above

        # EnglishDefault['label_selected_none'] = 'None' # Keep localization
        self.WindowUpdateTime = 0.75
        self.WindowRefreshTime = 120
        try:
            self.WindowUpdateTime = int(self.config['settings']['WindowUpdateTime'])
        except:
            pass
        try:
            self.WindowRefreshTime = float(self.config['settings']['WindowRefreshTime'])
        except:
            pass

        self.Lang = self.config['settings']['Language']

        # Define table headers
        self.TopRow = [self.GetLocale('label_custom'), 'Steam', 'SteamUI', self.GetLocale('label_date'), self.GetLocale('label_description'), 'Type']

        self.WindowUpdateTime = int(self.config.get('settings', 'WindowUpdateTime', fallback=120))
        self.WindowRefreshTime = float(self.config.get('settings', 'WindowRefreshTime', fallback=0.25))
        
        self.Lang = self.config.get('settings', 'Language', fallback='english')

        self.TopRow = [self.GetLocale('label_custom'), 'Steam', 'SteamUI', self.GetLocale('label_date'), self.GetLocale('label_description'), 'Type']
        
        tbl1 = psg.Table(
                values=self.Rows, 
                headings=self.TopRow,
                auto_size_columns=False,
                def_col_width=10, 
                col_widths=[8, 8, 8, 18, 30, 8], 
                hide_vertical_scroll=False,
                display_row_numbers=False,
                background_color='#3e4637',
                justification='left',
                key='-LIST-',
                selected_row_colors=('#ffffff', '#958831'),
                header_background_color='#4c5844',
                header_text_color='#ffffff',
                enable_events=True,
                expand_x=True,
                expand_y=True,
                enable_click_events=True,
                right_click_menu=['&Right', ['!View Details (Not Implemented)', '---', '&Exit Application::EXITAPP']], # Simplified menu
                right_click_selects=True
        )

        layout = [
                [psg.Text("Status: Unknown", key='-IFB-')], # To be updated after connection
                [psg.Text("", key='-ISB-')],
                [psg.HSep(color='#4c5844')],
                [
                    psg.Push(),
                    psg.Text("", key='-STATEMSG-', text_color='#c4b550'),
                    psg.Push(),
                    psg.Button('Search', key='-SEARCH-', button_color=('#c4b550', '#4c5844')),
                    psg.Button('Refresh', key='-REFRESH-', button_color=('#c4b550', '#4c5844'), disabled=not self.connected_to_admin_server),
                    psg.Button(self.GetLocale('label_swap'), key='-SWAP-', disabled=not self.connected_to_admin_server, button_color=('#c4b550', '#4c5844')),
                ],
                [tbl1],
                [psg.Text(f"{self.GetLocale('label_selected')} {self.GetLocale('label_selected_none')}", key='-SELECTTEXT-', font=('Verdana underline', 9), justification='center', enable_events=True)],
        ]
        loader.close() 

        blob_source_display = "Database Blobs" if self.blob_source_type == 'DB' else "File Based Blobs"
        self.window = psg.Window(
                f"Blob Manager (via AdminTool) - {blob_source_display} - {self.GetLocale('label_version')} 2.0",
                layout,
                size=(950, 500),
                finalize=True,
                resizable=True,
                return_keyboard_events=True
        )

        self.window['-LIST-'].update(values=self.Rows)  # Update table with fetched or error data
        self._apply_row_coloring()
        # Enable/disable buttons based on connection state
        self.window['-REFRESH-'].update(disabled=not self.connected_to_admin_server)
        self.window['-SWAP-'].update(disabled=not self.connected_to_admin_server)

        self.window.bind('<Control-f>', 'CTRL+F')
        self.window['-LIST-'].bind("<Double-Button-1>", " Double")
        self.window['-SELECTTEXT-'].bind("<Double-Button-1>", " Double")
        
        self.LastSelected = None
        self.sort_state = {header: False for header in self.TopRow}
        self.last_message_row = None

        if self.connected_to_admin_server:
             self.window['-IFB-'].update("Status: Using shared connection from remote_admintool. Blob list loaded.")
             self.window['-ISB-'].update(f"{len(self.Rows)} blob(s) found.")
             self.window['-SWAP-'].update(disabled=False)
        else:
             self.window['-IFB-'].update("Status: Not authenticated. Please launch from remote_admintool (B menu option).")
             self.window['-ISB-'].update("Blob listing and swap functionality disabled.")
             self.window['-SWAP-'].update(disabled=True)
             self.window['-SEARCH-'].update(disabled=True)




    def _fetch_server_blob_list(self):
        # This method is now obsolete as PopulateRowsFromServer will use request_detailed_blob_list
        # Kept for reference if any part of old SwapBlobs (which is being disabled) still calls it.
        # For the new design, this method should not be the primary source of self.Rows.
        return []


    def WindowRefresher(self):
        while True:
            sleep(self.WindowRefreshTime)
            self.window.refresh()

    def DoesFileExist(self, filepath: str) -> bool:
        """Return True if the given file path exists.

        This helper previously existed in older revisions of the tool and was
        inadvertently removed during refactoring.  The blob manager still
        relies on it when preparing configuration files during start-up."""
        return os.path.isfile(filepath)

    def set_heading_color(self, element, pressed_color, highlight_color, disabled_color):
        print('Hacking table colours.')
        psg.ttk.Style().map(
                element + ".Heading",
                background = [
                        ('pressed', '!focus', pressed_color),
                        ('active', highlight_color),
                        ('disabled', disabled_color),
                ],
                foreground = [
                        ('pressed', '!focus', '#ffffff'),  # Set font color to white (or any visible color)
                        ('active', '#ffffff'),  # Set font color during hover to white
                        ('disabled', '#ffffff'),  # Set font color for disabled state
                ]
        )


    def GetLocale(self, variable):
        try:
            return self.config[self.Lang][variable]
        except:
            print(f'MISSING LANGUAGE STRING: {self.Lang}_{variable}')
            return f'{self.Lang}_{variable}'

    def PopulateRows(self):
        """
        Fills self.Rows from self.SecondBlobs, parsing timestamps
        and finding the matching first-blob name.
        """
        # This thread might not be strictly necessary if GUI updates are event-driven
        # or if server doesn't push updates that require immediate refresh.
        # For now, keeping it if it was for periodic UI refresh unrelated to data change.
        while self.window and self.connected_to_admin_server: # Check if window still exists
            sleep(self.WindowRefreshTime if self.WindowRefreshTime > 0 else 1.0) # Ensure positive sleep
            try:
                if self.window: self.window.refresh()
            except Exception as e:
                print(f"Error in WindowRefresher: {e}") # Log error, don't crash thread
                break # Exit thread on window error

    def PopulateRowsFromServer(self, blob_type='DB'):
        """Fetch and normalise the blob list from the administration server.

        Uses the new compressed blob list endpoint that can handle 30000+ blobs.
        The server returns a JSON encoded dictionary with a 'blobs' array.
        This method processes the data into a uniform table format while being
        defensive about missing fields or network failures.

        Args:
            blob_type: 'DB' for database blobs, 'File' for file-based blobs.

        Assumes the connection is already established by remote_admintool.
        """

        if not networking.authenticated:
            return [["Error: Not authenticated. Launch from remote_admintool.", "", "", "", "", "", {}]]

        # Use the new compressed blob list endpoint with blob type
        response_data = request_blobmgr_file_list(blob_type)
        processed_rows = []

        if response_data is None:
            return [["Error: Failed to fetch blob data from server.", "", "", "", "", "", {}]]

        # Extract blobs array from response
        blob_list = response_data.get('blobs', [])
        if not blob_list:  # Empty list from server
            return [["No blobs reported by server.", "", "", "", "", "", {}]]

        for idx, blob_item in enumerate(blob_list):
            # Normalise boolean/custom fields (most DB blobs are not custom)
            custom_val = blob_item.get('Custom', blob_item.get('custom', False))
            custom_display = "Yes" if custom_val in (True, "Yes", "yes", 1, "1") else "No"

            # Extract version numbers using multiple fallbacks
            steam_version = (
                blob_item.get('steam_version') or 
                blob_item.get('SteamVersion') or 
                blob_item.get('steam') or 
                'N/A'
            )
            steamui_version = (
                blob_item.get('steamui_version') or 
                blob_item.get('SteamUIVersion') or 
                blob_item.get('steamui') or 
                'N/A'
            )

            # Extract other fields
            date_val = blob_item.get('date') or blob_item.get('Date') or 'N/A'
            description_val = blob_item.get('description') or blob_item.get('Description') or ''
            blob_type = blob_item.get('type') or blob_item.get('Type') or 'DB'
            filename = blob_item.get('filename') or blob_item.get('Filename') or 'N/A'

            row_entry = [
                custom_display,
                str(steam_version),
                str(steamui_version), 
                str(date_val),
                str(description_val),
                str(blob_type),
                blob_item,  # Store the original dictionary for reference
            ]
            processed_rows.append(row_entry)

        self.log.info(f"Processed {len(processed_rows)} blobs from server")
        return processed_rows

    def refresh_rows(self):
        """Refresh the table contents by querying the server again.

        A small helper used by the GUI event loop and by the periodic refresh
        timer.  The function reuses :func:`PopulateRowsFromServer` and handles
        updating the PySimpleGUI ``Table`` element while preserving the current
        selection if possible.  Any errors are surfaced in the status line so
        they are visible to the operator.
        """

        previous_selection = self.row
        self.Rows = self.PopulateRowsFromServer(self.blob_source_type)
        self.window['-LIST-'].update(values=self.Rows)
        self._apply_row_coloring()
        if previous_selection is not None and previous_selection < len(self.Rows):
            try:
                self.window['-LIST-'].Widget.selection_set(previous_selection)
                self.window['-LIST-'].Widget.see(previous_selection)
                self.row = previous_selection
            except Exception:
                self.row = None
        self.window['-STATEMSG-'].update(self.GetLocale('label_blobmgr'))

    def _apply_row_coloring(self):
        """Applies coloring to rows based on package existence."""
        if not self.window or not hasattr(self.window['-LIST-'].Widget, 'tag_configure') or not self.Rows:
            return # Window not ready, or no data

        try:
            treeview = self.window['-LIST-'].Widget

            # Configure the tag with more explicit styling
            treeview.tag_configure('missing_pkg_red', foreground='#FF0000', background='')

            # Force update the table display
            self.window['-LIST-'].update()

            item_ids = treeview.get_children('')
            packages_missing_count = 0

            for i, item_id in enumerate(item_ids):
                if i < len(self.Rows):
                    # Clear any existing tags first
                    treeview.item(item_id, tags=())

                    original_blob_dict = self.Rows[i][-1] # Last element is the original dict
                    if isinstance(original_blob_dict, dict):
                        steam_exists = original_blob_dict.get('steam_pkg_exists', False)
                        steamui_exists = original_blob_dict.get('steamui_pkg_exists', False)

                        if not steam_exists or not steamui_exists:
                            treeview.item(item_id, tags=('missing_pkg_red',))
                            packages_missing_count += 1

            # Force a refresh after applying tags
            self.window.refresh()

        except Exception as e:
            print(f"Error applying row coloring: {e}")


    def SwapBlobs(self):
        """Request the server to swap to the selected blob."""

        if self.row is None or self.row >= len(self.Rows):
            self.window['-STATEMSG-'].update('No blob selected')
            return

        blob_dict = self.Rows[self.row][-1]
        # Extract filename from the blob data
        filename = blob_dict.get('Filename') or blob_dict.get('filename')
        # Use the blob source type from the startup dialog selection
        blob_type = self.blob_source_type
        
        if not filename:
            # Try to construct filename from available data for DB blobs
            steam_version = blob_dict.get('SteamVersion', blob_dict.get('steam'))
            steamui_version = blob_dict.get('SteamUIVersion', blob_dict.get('steamui'))
            date_val = blob_dict.get('Date', blob_dict.get('date'))
            
            if steam_version and steamui_version and date_val:
                # For database blobs, use the expected format: secondblob.bin.YYYY-MM-DD HH_MM_SS
                if isinstance(date_val, str) and len(date_val) >= 10:
                    # Convert date format if needed (from various formats to YYYY-MM-DD HH_MM_SS)
                    try:
                        # Handle different date formats
                        if ' ' in date_val:
                            date_part = date_val.replace(' ', ' ').replace(':', '_')
                        else:
                            date_part = date_val.replace(':', '_')
                        filename = f"secondblob.bin.{date_part}"
                    except:
                        filename = f"secondblob.bin.{date_val}"
                else:
                    self.window['-STATEMSG-'].update('Cannot determine blob date for filename')
                    return
            else:
                self.window['-STATEMSG-'].update('Cannot determine blob filename - missing data')
                return

        # Check if we still have an authenticated connection
        if not networking.authenticated:
            self.window['-STATEMSG-'].update('Swap failed: not authenticated')
            return

        self.window['-STATEMSG-'].update(self.GetLocale('label_swapping'))
        self.log.info(f"Attempting to swap to {blob_type} blob: {filename}")
        
        try:
            # Call with both filename and blob type
            response = request_blobmgr_swap(filename, blob_type)
        except Exception as e:
            response = None
            self.log.error(f"Blob swap request failed: {e}")

        if response:
            self.window['-STATEMSG-'].update(response)
            # Refresh blob list to show current selection
            self.refresh_rows()
        else:
            self.window['-STATEMSG-'].update('Swap failed.')

    def sort_table(self, col_index):
        # Sort logic can largely remain, but ensure it accesses self.Rows correctly
        # and handles the appended original_blob_dict if it affects sorting.
        # For visible columns, it should be fine.
        reverse = self.sort_state[self.TopRow[col_index]]  # Get current sort order

        # Define which columns should be sorted numerically
        numerical_columns = ['Steam', 'SteamUI']

        # Get the column name based on index
        column_name = self.TopRow[col_index]

        if column_name in numerical_columns:
            # Sort numerically
            def numeric_key(x):
                try:
                    return float(x[col_index])
                except ValueError:
                    return 0  # Assign a default value if conversion fails

            self.Rows.sort(key = numeric_key, reverse = reverse)

        elif column_name == self.GetLocale('label_date'):  # Assuming 'label_date' corresponds to the Date column
            def date_key(x):
                try:
                    # Parse the date string into a datetime object for sorting
                    date_obj = datetime.strptime(x[col_index], '%m/%d/%Y %I:%M:%S %p')
                    return date_obj.timestamp()  # Return the timestamp for correct date sorting
                except ValueError:
                    return 0  # Return 0 for invalid dates

            # Sort by the parsed dates
            self.Rows.sort(key = date_key, reverse = reverse)

        elif column_name == self.GetLocale('label_description'):  # Assuming 'label_description' corresponds to 'Description'
            if not reverse:  # Ascending
                def description_asc_key(x):
                    # Entries with descriptions have priority (0), others have lower priority (1)
                    has_description = 0 if x[4].strip() else 1
                    try:
                        # Parse the date string back to a datetime object
                        date_obj = datetime.strptime(x[3], '%m/%d/%Y %I:%M:%S %p')
                        date_ts = date_obj.timestamp()
                    except ValueError:
                        date_ts = 0  # Assign a default timestamp if parsing fails
                    return (has_description, date_ts)

                self.Rows.sort(key = description_asc_key, reverse = False)

            else:  # Descending
                def description_desc_key(x):
                    try:
                        # Parse the date string back to a datetime object
                        date_obj = datetime.strptime(x[3], '%m/%d/%Y %I:%M:%S %p')
                        date_ts = date_obj.timestamp()
                    except ValueError:
                        date_ts = 0  # Assign a default timestamp if parsing fails

                    # Entries with descriptions should be at the bottom (1), others at the top (0)
                    has_description = 1 if x[4].strip() else 0
                    # Negative timestamp for descending sort
                    return (-date_ts, has_description)

                self.Rows.sort(key = description_desc_key, reverse = False)

        else:
            # Sort as strings for all other columns
            self.Rows.sort(key = lambda x:x[col_index], reverse = reverse)

        # Toggle the sort order for the next click
        self.sort_state[self.TopRow[col_index]] = not reverse

        # Update the table with the sorted values
        self.window['-LIST-'].update(values = self.Rows)


Manager = BlobManager()


# Date validation function (only accepts mm/dd/yyyy or yyyy)
def validate_date(date_str):
    # Match mm/dd/yyyy or yyyy
    date_pattern = r"^\d{4}$|^\d{1,2}/\d{1,2}/\d{4}$"
    if re.match(date_pattern, date_str):
        try:
            # If it's just a year, it's valid
            if len(date_str) == 4:
                return True
            # If it's in mm/dd/yyyy format, try to parse it
            datetime.strptime(date_str, "%m/%d/%Y")
            return True
        except ValueError:
            return False


def select_row(row_index):
    # Highlight the row in the table
    Manager.window['-LIST-'].update(select_rows=[row_index])
    Manager.row = row_index
    treeview = Manager.window['-LIST-'].Widget
    treeview_id = treeview.get_children()[row_index]
    treeview.see(treeview_id)
    update_selected_text()  # Use the unified update function
    Manager.window['-SWAP-'].Update(disabled=False)


def search_date_func(search_date_str, start_index):
    try:
        # Normalize the search date to mm/dd/yyyy format or just year if yyyy
        if len(search_date_str) == 4:  # Year format
            search_year = search_date_str
        else:  # Full date format
            search_date = datetime.strptime(search_date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
    except ValueError:
        return False  # Invalid date format

    closest_index = None
    closest_diff = None

    for i in range(start_index, len(Manager.Rows)):
        date_str = Manager.Rows[i][3]  # Assuming date is column index 3

        # Normalize the table date by stripping time and formatting as mm/dd/yyyy
        try:
            table_date = datetime.strptime(date_str.split(" ")[0], "%m/%d/%Y").strftime("%m/%d/%Y")
        except ValueError:
            continue  # Skip rows with invalid or incorrectly formatted dates

        # If searching by year
        if len(search_date_str) == 4 and search_year == table_date[6:10]:  # Compare year
            select_row(i)
            return True

        # Exact date match
        if len(search_date_str) != 4 and search_date == table_date:
            select_row(i)
            return True

        # Find the closest date if no exact match
        if len(search_date_str) != 4:  # Only for full date search
            search_date_obj = datetime.strptime(search_date_str, "%m/%d/%Y")
            table_date_obj = datetime.strptime(table_date, "%m/%d/%Y")
            diff = (table_date_obj - search_date_obj).days
            if diff > 0 and (closest_diff is None or diff < closest_diff):
                closest_diff = diff
                closest_index = i

    # If no exact match, select the closest future date
    if closest_index is not None:
        select_row(closest_index)
        return True

    return False


def search_description(search_phrase, start_index):
    pattern = re.escape(search_phrase).replace('\\*', '.*')
    regex = re.compile(pattern, re.IGNORECASE)

    for i in range(start_index, len(Manager.Rows)):
        description = Manager.Rows[i][4]  # Assuming description is column index 4
        if regex.search(description):
            select_row(i)
            return True

    return False


def custom_popup(message):
    layout = [[psg.Text(message)], [psg.Button('OK', key = '-OK-', bind_return_key = True)]]

    # Create the popup window
    window = psg.Window('Alert', layout, modal = True, keep_on_top = True, finalize = True)

    # Set the focus on the OK button
    window['-OK-'].set_focus()

    # Event loop for the popup
    while True:
        event, _ = window.read()
        if event == '-OK-' or event == psg.WIN_CLOSED:
            break

    # Close the window
    window.close()


def open_search_dialog():
    # Define the layouts for the tabs
    tab1_layout = [
        [psg.Text('Type in a search phrase (use * as a wildcard):')],
        [psg.Input(key='-SEARCH_PHRASE-', focus=True)],
        [psg.Button('Search', key='-SEARCH_DESC-'), psg.Button('Cancel', key='-CANCEL-DESC-BTN-')],
    ]
    tab2_layout = [
        [psg.Text('Type a date to search (formats: mm/dd/yyyy or yyyy):')],
        [psg.Input(key='-SEARCH_DATE-')],
        [psg.Button('Search', key='-SEARCH_DATE_BTN-'), psg.Button('Cancel', key='-CANCEL-DATE-BTN-')],
    ]
    tab_group = psg.TabGroup([
        [psg.Tab('Description Search', tab1_layout, key='-TAB1-'),
         psg.Tab('Date Search', tab2_layout, key='-TAB2-')],
    ], key='-TABGROUP-', enable_events=True)

    search_layout = [
        [tab_group]
    ]

    search_window = psg.Window('Search', search_layout, modal=True, return_keyboard_events=True)

    search_window.finalize()
    search_window['-SEARCH_PHRASE-'].set_focus()

    # Initialize search variables
    search_phrase = ''
    search_date = ''
    search_index = 0
    no_more_matches_found = False

    while True:
        event, values = search_window.read()

        # Handle window close or cancel button
        if event in ['-CANCEL-DESC-BTN-', '-CANCEL-DATE-BTN-'] or event == psg.WIN_CLOSED:
            search_window.close()
            break

        # Handle Enter key press
        if event == '\r':  # Enter key pressed
            current_tab = values['-TABGROUP-']
            if current_tab == '-TAB1-' and values['-SEARCH_PHRASE-']:  # Enter on Description Search
                search_phrase = values['-SEARCH_PHRASE-']
                if no_more_matches_found:
                    search_index = 0
                    no_more_matches_found = False
                found = search_description(search_phrase, search_index)
                if found:
                    search_index = Manager.row + 1
                else:
                    custom_popup('No more matches found.')
                    no_more_matches_found = True
                    search_index = 0

            elif current_tab == '-TAB2-' and values['-SEARCH_DATE-']:  # Enter on Date Search
                search_date = values['-SEARCH_DATE-']
                if no_more_matches_found:
                    search_index = 0
                    no_more_matches_found = False
                if validate_date(search_date):
                    found = search_date_func(search_date, search_index)
                    if found:
                        search_index = Manager.row + 1
                    else:
                        custom_popup('No more matches found.')
                        no_more_matches_found = True
                        search_index = 0
                else:
                    custom_popup('Invalid date format. Please enter mm/dd/yyyy or yyyy.')

        # Handle the Description Search button
        elif event == '-SEARCH_DESC-':
            search_phrase = values['-SEARCH_PHRASE-']
            if no_more_matches_found:
                search_index = 0
                no_more_matches_found = False
            found = search_description(search_phrase, search_index)
            if found:
                search_index = Manager.row + 1
            else:
                # Update the popup in both the Date and Description search results
                custom_popup('No more matches found.')

                no_more_matches_found = True
                search_index = 0

        # Inside the Date Search button handler
        elif event == '-SEARCH_DATE_BTN-':
            search_date = values['-SEARCH_DATE-']

            # Reset search_index to start from the beginning for the new search
            search_index = 0
            no_more_matches_found = False

            if validate_date(search_date):
                found = search_date_func(search_date, search_index)
                if found:
                    search_index = Manager.row + 1
                else:
                    custom_popup('No more matches found.')
                    no_more_matches_found = True
                    search_index = 0
            else:
                custom_popup('Invalid date format. Please enter mm/dd/yyyy or yyyy.')

    search_window.close()


# Function to handle selection changes
def update_selected_text():
    if Manager.row is not None and Manager.row >= 0:
        selected_row = Manager.Rows[Manager.row]
        blob_dict = selected_row[-1]  # Last element is the original dict
        
        # Create a user-friendly display string
        if isinstance(blob_dict, dict):
            steam_version = blob_dict.get('SteamVersion', blob_dict.get('steam', 'N/A'))
            steamui_version = blob_dict.get('SteamUIVersion', blob_dict.get('steamui', 'N/A'))
            date_val = blob_dict.get('Date', blob_dict.get('date', 'N/A'))
            display_text = f"Steam: {steam_version}, SteamUI: {steamui_version}, Date: {date_val}"
        else:
            display_text = str(blob_dict)
            
        Manager.window['-SELECTTEXT-'].Update(value=f"{Manager.GetLocale('label_selected')} {display_text}")
        Manager.window['-SWAP-'].Update(disabled=False)
        # Clear the message only if a different row is selected
        if Manager.last_message_row != Manager.row:
            Manager.window['-STATEMSG-'].Update(value='')
            Manager.last_message_row = Manager.row

# Bind custom events for Up and Down key handling
Manager.window.bind('<Up>', 'UP_KEY')
Manager.window.bind('<Down>', 'DOWN_KEY')

# Event loop with adjusted event handling
while True:
    event, values = Manager.window.read(Manager.WindowUpdateTime)

    if event in (psg.WIN_CLOSED, 'Exit'):
        break
    elif event == '-SEARCH-' or event == 'CTRL+F' or event == '^f':
        open_search_dialog()
    elif event == '-REFRESH-':
        Manager.refresh_rows()
        continue
    elif isinstance(event, tuple):
        if event[0] == '-LIST-' and '+CLICKED+' in event[1]:
            row, col = event[2]
            if row == -1:  # Header row is clicked
                Manager.sort_table(col)
            else:
                Manager.row = row
                update_selected_text()  # Update text when a row is clicked

        # Update multiple rows when using arrow keys or clicking
        if '-LIST-' in event and '-LIST-' in values and len(values['-LIST-']) > 0:
            Manager.multiple_rows = values['-LIST-'].copy()
            Manager.row = values['-LIST-'][0]
            update_selected_text()

    # Custom key handling for Up and Down arrows
    elif event == 'UP_KEY' or event == 'DOWN_KEY':
        current_index = Manager.row if Manager.row is not None else 0
        new_index = current_index - 1 if event == 'UP_KEY' else current_index + 1
        new_index = max(0, min(new_index, len(Manager.Rows) - 1))

        # Update the selected row in the list
        Manager.window['-LIST-'].update(select_rows = [new_index])
        Manager.row = new_index

        # Scroll to the selected row manually using the Treeview widget
        treeview = Manager.window['-LIST-'].Widget
        treeview_id = treeview.get_children()[new_index]
        treeview.see(treeview_id)

        update_selected_text()  # Update the text display after moving with arrows

    elif '-SWAP-' == event:
        Manager.window['-SWAP-'].Update(disabled=True)
        Manager.SwapBlobs()
        continue
    if '-LIST- Double' in event:
        if values['-LIST-']:
            Manager.Selected = values['-LIST-'][0]
            Manager.window['-SWAP-'].Update(disabled=True)
            Manager.SwapBlobs()
        continue

    elif '-SELECTTEXT-' in event:
        try:
            selected_row = Manager.Rows[Manager.row]
            blob_dict = selected_row[-1]  # Last element is the original dict
            
            # Copy a meaningful representation to clipboard
            if isinstance(blob_dict, dict):
                copy_text = f"Steam: {blob_dict.get('SteamVersion', blob_dict.get('steam', 'N/A'))}, " \
                           f"SteamUI: {blob_dict.get('SteamUIVersion', blob_dict.get('steamui', 'N/A'))}, " \
                           f"Date: {blob_dict.get('Date', blob_dict.get('date', 'N/A'))}, " \
                           f"Filename: {blob_dict.get('Filename', 'N/A')}"
            else:
                copy_text = str(blob_dict)
                
            clipboardcopy(copy_text)
            Manager.window['-STATEMSG-'].Update(value=Manager.GetLocale('label_copyclip'))
        except Exception as e:
            Manager.window['-STATEMSG-'].Update(value=f"Copy failed: {e}")
            pass

Manager.window.close()
# Don't logout here - we're using a shared connection from remote_admintool

