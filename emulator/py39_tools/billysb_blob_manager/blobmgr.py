import copy
import os
import re
import sys
from datetime import datetime
import struct
from tkinter import filedialog
import PySimpleGUI as psg
import configparser
from pathlib import Path
from shutil import copystat
from threading import Thread
from time import sleep
from os import path, mkdir, utime, remove as osremove
from json import dumps as jsondump
from json import loads as jsonload
from bisect import bisect_right

from PySimpleGUI import WIN_CLOSED
from pyperclip import copy as clipboardcopy
from GenerateDB import FinalFileReaderv0, FinalFileReaderv1

from blobreader import ReadBlob, ReadBytes

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


# Function to strip comments from the config values
def strip_comments(value):
    # Remove everything after a semicolon, including the semicolon itself
    if value:
        return value.split(';', 1)[0].strip()
    return None


# Function to normalize the date format to YYYY-mm-dd

def normalize_date_format(steam_date):
    # Strip leading/trailing spaces
    steam_date = steam_date.strip()

    # Debug: Print raw steam_date for troubleshooting
    print(f"Raw steam_date: '{steam_date}'")

    # Replace / and _ with - to standardize the date format
    steam_date = steam_date.replace('/', '-').replace('_', '-')

    # Try to directly validate the date string as 'YYYY-MM-DD'
    try:
        datetime.strptime(steam_date, '%Y-%m-%d')
        return steam_date  # Return the date as it's now in the correct format
    except ValueError:
        print(f"Invalid date: '{steam_date}'")  # Debug for invalid date
        return None  # Return None if the format is invalid


# Function to normalize the time format to HH:MM:SS
def normalize_time_format(steam_time):
    # Strip leading/trailing spaces
    steam_time = steam_time.strip()

    # Debug: Print raw steam_time to help with troubleshooting
    print(f"Raw steam_time: '{steam_time}'")

    # Match formats like HH:MM:SS, HH-MM-SS, HH_MM_SS
    time_pattern = re.compile(r'(\d{2})[:\-_](\d{2})[:\-_](\d{2})')
    match = time_pattern.match(steam_time)

    if match:
        # Convert to HH:MM:SS format
        time_str = f"{match.group(1)}:{match.group(2)}:{match.group(3)}"

        # Debug: Print normalized time before validation
        print(f"Normalized time string: '{time_str}'")

        # Validate if it's a valid time
        try:
            datetime.strptime(time_str, '%H:%M:%S')
            return time_str
        except ValueError:
            # Debug: Invalid time detected
            print(f"Invalid time format: '{time_str}'")
            return None  # Invalid time, return None
    else:
        # Debug: Regex did not match
        print(f"Time format did not match expected pattern: '{steam_time}'")

    return None  # No match or invalid time format


class BlobManager(object):
    window = None

    def __init__(self) -> None:
        # Initialize GUI settings
        self.windowico = path.join(path.dirname(__file__), "icon.ico")
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

        self.FilesFolder = './files/'
        self.BlobsFolder = f'{self.FilesFolder}blobs/'
        self.CacheFolder = f'{self.FilesFolder}cache/'
        self.row = None
        self.multiple_rows = None

        # Table Header and Content.
        self.Rows = []
        self.SecondBlobs = []
        self.FirstBlobs = []
        self.LandMarks = {}
        self.Selected = None
        self.Language = ""
        self.config = configparser.ConfigParser()

        psg.theme('SteamGreen.json')

        # Show initial dialog to choose between 'Files' and 'Database'
        choice_layout = [
                [psg.Text('Would you like to read the blobs from the database or from files?')],
                [psg.Radio('Files', 'RADIO1', key = '-FILES-')],
                [psg.Radio('Database', 'RADIO1', default = True, key = '-DATABASE-')],
                [psg.Button('OK'), psg.Button('Cancel')]
        ]
        choice_window = psg.Window('Choose Data Source', choice_layout, finalize = True)
        event, values = choice_window.read()
        if event == 'Cancel' or event == psg.WIN_CLOSED:
            choice_window.close()
            sys.exit(0)
        elif event == 'OK':
            if values['-FILES-']:
                self.load_from_database = False
            elif values['-DATABASE-']:
                self.load_from_database = True
        choice_window.close()

        loadinglayout = [
                [psg.Push(), psg.Text("Loading", justification = 'center', key = '-STATUS-'), psg.Push()],
                [psg.ProgressBar(100, orientation = 'h', expand_x = True, size = (20, 20), border_width = 1, key = '-PBAR-', relief = psg.RELIEF_SUNKEN, style = 'xpnative')]
        ]

        loader = psg.Window("Loading Blob Information", loadinglayout, size = (500, 100), finalize = True, disable_close = True)

        EnglishDefault = {
                'label_swap':                'Swap',
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
        self.PackReader = None
        self.VersionPak = 'Unknown'
        # Manually read the emulator.ini and remove comments starting with ';'
        with open('./emulator.ini', 'r') as f:
            lines = f.readlines()
        clean_lines = [line for line in lines if not line.strip().startswith(';')]

        # Write back the clean lines to a temporary config string
        config_string = ''.join(clean_lines)
        # Use ConfigParser to read from the cleaned config string
        self.emulator_config = configparser.ConfigParser()
        self.emulator_config.read_string(config_string)

        # Only load emulator.ini if database option is selected
        if self.load_from_database:
            # Read emulator.ini
            if not self.DoesFileExist('./emulator.ini'):
                psg.PopupError(self.GetLocale('label_error_text1'), title = self.GetLocale('label_error_title'))
                exit(2)
            else:
                if 'config' in self.emulator_config:
                    db_config = self.emulator_config['config']
                    self.database_host = db_config.get('database_host', '192.168.3.180')
                    self.database_port = db_config.getint('database_port', 3388)
                    self.database_username = db_config.get('database_username', 'stmserver')
                    self.database_password = db_config.get('database_password', 'lLHRN7W6')
                else:
                    psg.PopupError('Missing [config] section in emulator.ini', title = 'Error')
                    exit(2)

                # Read steam_date and steam_time from emulator.ini
                steam_date_raw = self.emulator_config.get('config', 'steam_date', fallback = None)
                steam_time_raw = self.emulator_config.get('config', 'steam_time', fallback = None)

                # Strip comments from the values
                steam_date_clean = strip_comments(steam_date_raw)
                steam_time_clean = strip_comments(steam_time_raw)

                self.steam_datetime = None

                if steam_date_clean and steam_time_clean:
                    # Normalize the date and time to standard formats
                    steam_date_normalized = normalize_date_format(steam_date_clean)
                    steam_time_normalized = normalize_time_format(steam_time_clean)

                    # Debug: Print normalized date and time
                    print(f"Normalized date string: '{steam_date_normalized}'")
                    print(f"Normalized time string: '{steam_time_normalized}'")

                    if steam_date_normalized and steam_time_normalized:
                        try:
                            # Debug: Print combined date and time before parsing
                            print(f"Combined datetime string: '{steam_date_normalized} {steam_time_normalized}'")

                            # Attempt to parse the combined date and time
                            self.steam_datetime = datetime.strptime(f"{steam_date_normalized} {steam_time_normalized}", '%Y-%m-%d %H:%M:%S')

                        except ValueError as e:
                            # Debug: Show specific error message
                            print(f"Error while parsing datetime: {e}")
                            psg.PopupError("Invalid date/time format in emulator.ini", title = "Error")
                    else:
                        psg.PopupError("Unable to normalize date/time format in emulator.ini", title = "Error")

        loader['-PBAR-'].update(current_count = 35)

        loader['-STATUS-'].update(value = 'Processing table data...')

        EnglishDefault['label_selected_none'] = 'None'
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
        self.TopRow = [self.GetLocale('label_custom'), 'Steam', 'SteamUI', self.GetLocale('label_date'), self.GetLocale('label_description')]

        # Initialize data structures for efficient date handling
        self.FirstBlobDates = []  # List to store firstblob dates and filenames
        self.SecondBlobDates = []  # List to store secondblob dates and filenames

        if self.load_from_database:
            loader['-STATUS-'].update(value = 'Connecting to Database')
            loader['-PBAR-'].update(current_count = 35)
            # Connect to database
            self.ConnectToDatabase()
            loader['-STATUS-'].update(value = 'Processing table data...')
            # Populate rows from database
            self.PopulateRowsFromDatabase()
            loader['-PBAR-'].update(current_count = 75)
        else:
            loader['-STATUS-'].update(value = 'Sorting blobs by date...')
            self.BlobsFiles = None

            # Handle packed vs loose
            if self.PackReader is None:
                try:
                    self.BlobsFiles = sorted(Path('./files/blobs/').iterdir(), key = lambda x:x.name)
                except:
                    psg.PopupError('No files/blobs/ folder found. Cannot continue.')
                    exit(2)
            else:
                print('Attempt to parse packed blob data..')
                self.BlobsFiles = []
                for item in self.PackReader.SecondData.keys():
                    self.BlobsFiles.append(item)
            loader['-PBAR-'].update(current_count = 35)

            loader['-STATUS-'].update(value = 'Processing table data...')
            self.PopulateRows()
            loader['-PBAR-'].update(current_count = 75)

            loader['-STATUS-'].update(value = 'Parsing firstblob data...')
            self.FirstBlobThread()
            loader['-PBAR-'].update(current_count = 100)
        # PySimpleGUI layout and table
        tbl1 = None
        layout = None

        psg.theme("SteamGreen.json")

        tbl1 = psg.Table(
                values = self.Rows,
                headings = self.TopRow,
                auto_size_columns = False,
                max_col_width = 15,
                def_col_width = 3,
                hide_vertical_scroll = False,
                display_row_numbers = False,
                background_color = '#3e4637',
                justification = 'left',
                key = '-LIST-',
                selected_row_colors = ('#ffffff', '#958831'),
                header_background_color = '#4c5844',
                header_text_color = '#ffffff',
                col_widths = [10, 30, 10],
                enable_events = True,
                expand_x = True,
                expand_y = True,
                enable_click_events = True,  # Enable click events for the table
                right_click_menu = [
                        self.GetLocale('label_menu1_item1'),
                        [
                                self.GetLocale('label_menu1_item2_1'),
                                [
                                        self.GetLocale('label_menu1_item3'),
                                ],
                                self.GetLocale('label_menu1_item4'),
                        ]
                ],
                right_click_selects = True
        )

        layout = [
                [psg.Text(f"{self.GetLocale('label_installed_blob1')} {self.GetLocale('label_installed_blob1_none')}", key = '-IFB-')],
                [psg.Text(f"{self.GetLocale('label_installed_blob2')} {self.GetLocale('label_installed_blob2_none')}", key = '-ISB-')],
                # [psg.Text()],
                # [psg.Push(), psg.Input(key='-SEARCHIN-', background_color='#4c5844', text_color='#c4b550'), psg.Button("Search", key='-SEARCHBTN-'), psg.Button("Cancel"), psg.Push()],
                [psg.HSep(color = '#4c5844')],
                [
                        psg.Push(),
                        psg.Text("", key = '-STATEMSG-', text_color = '#c4b550'),
                        psg.Push(),
                        psg.Button('Search', key = '-SEARCH-', button_color = ('#c4b550', '#4c5844')),
                        #psg.Button('Settings', key = '-SETTINGS-', button_color = ('#c4b550', '#4c5844')),  # Added Settings button
                        psg.Button(self.GetLocale('label_swap'), key = '-SWAP-', disabled = True, button_color = ('#c4b550', '#4c5844')),
                ],

                [tbl1],
                [psg.Text(f"{self.GetLocale('label_selected')} {self.GetLocale('label_selected_none')}", key = '-SELECTTEXT-', font = ('Verdana underline', 9), justification = 'center', enable_events = True)],
        ]
        loader.close()
        if self.load_from_database:
            blob_base = "Database Blobs"
        else:
            blob_base = "File Based Blobs"

        self.window = psg.Window(
                f"Billy {self.GetLocale('label_blobmgr')} - {self.GetLocale('label_version')} 1.13 --- {blob_base}",
                layout,
                size = (1000, 500),
                finalize = True,
                resizable = True,
                return_keyboard_events = True
        )
        # Access the Treeview widget directly
        treeview = self.window['-LIST-'].Widget  # Access the underlying Treeview widget

        # Define styles for missing Steam and SteamUI cells
        treeview.tag_configure('missing_steam', foreground = '#ff0000')
        treeview.tag_configure('missing_steamui', foreground = '#ff0000')

        packages_dir = self.emulator_config.get('config', 'packagedir', fallback = "files/packages/")
        packages_dir = packages_dir.split(';', 1)[0].strip()  # Split at first semicolon and strip any outer spaces

        # Remove quotes if they surround the directory path
        if packages_dir.startswith(("'", '"')) and packages_dir.endswith(("'", '"')):
            packages_dir = packages_dir[1:-1]

        print(packages_dir)


        # Iterate over the existing Treeview items and apply tags based on criteria
        for idx, item_id in enumerate(treeview.get_children()):
            row = self.Rows[idx]
            steam_version = row[1]
            steamui_version = row[2]
            steam_pkg_path = f'{packages_dir}/steam_{steam_version}.pkg'
            steamui_pkg_path = f'{packages_dir}/steamui_{steamui_version}.pkg'

            # Determine tags based on file existence
            tags = []
            if not os.path.exists(steam_pkg_path):
                tags.append('missing_steam')
            if not os.path.exists(steamui_pkg_path):
                tags.append('missing_steamui')

            if tags:
                treeview.item(item_id, tags = tags)

        # Refresh the window to apply the changes
        self.window.refresh()
        self.window.bind('<Control-f>', 'CTRL+F')

        # Dirty hack for steam green theme.
        self.set_heading_color(self.window['-LIST-'].widget.configure("style")[-1], '#4c5844', '#4c5844', '#4c5844')

        self.window['-LIST-'].bind("<Double-Button-1>", " Double")
        self.window['-SELECTTEXT-'].bind("<Double-Button-1>", " Double")
        thread = Thread(target = self.WindowRefresher)
        thread.daemon = True
        thread.start()
        # Refresh window even when main thread is blocked.
        # Resize headers
        max_col_width = 45
        char_width = psg.Text.char_width_in_pixels(('Verdana', 9))  # Get character width in pixel
        table = self.window['-LIST-']
        table_widget = table.Widget
        table.expand(expand_x = True, expand_y = True)  # Expand table in both directions of 'x' and 'y'
        for cid in self.TopRow:
            table_widget.column(cid, stretch = True)

        # Update column widths based on content
        col_widths = [min([max(map(lambda x:len(str(x)), columns)) + 2, max_col_width]) * char_width for columns in zip(*self.Rows)]

        table_widget.pack_forget()
        for cid, width in zip(self.TopRow, col_widths):  # Set width for each column
            # print(cid, width)
            if cid == 'Date':
                table_widget.column(cid, width = round(width / 1.7))
            elif cid == 'Custom':
                table_widget.column(cid, width = round(width))
            else:
                table_widget.column(cid, width = width)
        table_widget.pack(side = 'left', fill = 'both', expand = True)

        self.LastSelected = None
        self.LastSelectedFirstBlob = None

        if self.PackReader is not None:
            self.window['-STATEMSG-'].Update(value = f'{self.GetLocale("label_use_preprocessed")} ({self.VersionPak})')
            self.window['-LIST-'].set_right_click_menu([
                    self.GetLocale('label_menu1_item1'),
                    [
                            self.GetLocale('label_menu1_item2_2'),
                            [
                                    self.GetLocale('label_menu1_item3'),
                            ],
                            self.GetLocale('label_menu1_item4'),
                    ]])
        self.sort_state = {header:False for header in self.TopRow}  # Initialize sort state for each column

        self.last_message_row = None  # Initialize the tracking attribute
        # After self.FirstBlobThread() add this:
        if not self.load_from_database:
            # Set -IFB- and -ISB- to display first and second blob filenames based on timestamp
            try:
                # Get the most recent firstblob.bin and secondblob.bin based on their modification timestamps
                first_blob_file = Path(f'{self.FilesFolder}firstblob.bin')
                second_blob_file = Path(f'{self.FilesFolder}secondblob.bin')

                if first_blob_file.exists() and second_blob_file.exists():
                    # Get the modification time of firstblob.bin and secondblob.bin
                    first_blob_timestamp = first_blob_file.stat().st_mtime
                    second_blob_timestamp = second_blob_file.stat().st_mtime

                    # Look for matching files in the blobs folder
                    matching_first_blob = None
                    matching_second_blob = None

                    # Check all files in the blobs folder
                    for blob_file in Path(self.BlobsFolder).iterdir():
                        if blob_file.is_file():
                            # Check for firstblob.bin match
                            if blob_file.name.startswith("firstblob.bin.") and abs(blob_file.stat().st_mtime - first_blob_timestamp) < 1:
                                matching_first_blob = blob_file.name

                            # Check for secondblob.bin match
                            elif blob_file.name.startswith("secondblob.bin.") and abs(blob_file.stat().st_mtime - second_blob_timestamp) < 1:
                                matching_second_blob = blob_file.name

                    # Update -IFB- and -ISB- with the matched filenames
                    self.matching_first_blob = matching_first_blob
                    if matching_first_blob:
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {matching_first_blob}")
                    else:
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {self.GetLocale('label_installed_blob1_none')}")

                    if matching_second_blob:
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {matching_second_blob}")
                    else:
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {self.GetLocale('label_installed_blob2_none')}")

                else:
                    # Handle case where either firstblob.bin or secondblob.bin is missing
                    self.window['-IFB-'].update(value = f"Installed FirstBlob: {self.GetLocale('label_installed_blob1_none')}")
                    self.window['-ISB-'].update(value = f"Installed SecondBlob: {self.GetLocale('label_installed_blob2_none')}")

            except Exception as e:
                self.window['-STATEMSG-'].Update(value = f"Error reading blob files: {e}")

        # After self.PopulateRowsFromDatabase(), add this:
        if self.load_from_database:
            try:
                if self.steam_datetime:
                    # Ensure both FirstBlobDates and SecondBlobDates are sorted in reverse order by timestamp
                    self.FirstBlobDates.sort(reverse = True)
                    self.SecondBlobDates.sort(reverse = True)

                    # Reset the matching blobs
                    matching_firstblob = None
                    matching_secondblob = None

                    # Find the matching firstblob based on the steam_date and steam_time from emulator.ini
                    for timestamp, filename in self.FirstBlobDates:
                        if timestamp <= self.steam_datetime.timestamp():
                            matching_firstblob = filename
                            break  # Stop after finding the most recent match

                    # Find the matching secondblob based on the steam_date and steam_time from emulator.ini
                    for timestamp, filename in self.SecondBlobDates:
                        if timestamp <= self.steam_datetime.timestamp():
                            matching_secondblob = filename
                            break  # Stop after finding the most recent match

                    # Update the -IFB- and -ISB- text elements in the window with the matched blob filenames
                    if matching_firstblob:
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {matching_firstblob}")
                    else:
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {self.GetLocale('label_installed_blob1_none')}")

                    if matching_secondblob:
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {matching_secondblob}")
                    else:
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {self.GetLocale('label_installed_blob2_none')}")

            except Exception as e:
                self.window['-STATEMSG-'].Update(value = f"Error matching blobs from database: {e}")

    def WindowRefresher(self):
        while True:
            sleep(self.WindowRefreshTime)
            self.window.refresh()

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

    def DoesFileExist(self, file):
        try:
            with open(file, 'rb') as f:
                pass
        except FileNotFoundError:
            return False
        else:
            return True

    def GetLocale(self, variable):
        try:
            return self.config[self.Lang][variable]
        except:
            print(f'MISSING LANGUAGE STRING: {self.Lang}_{variable}')
            return f'{self.Lang}_{variable}'

    def GetFirstBlobTo_Unpacked(self, SecondTarget):
        # Find SecondBlobDate from precomputed list
        SecondBlobDate = None
        for date, filename in self.SecondBlobDates:
            if filename == SecondTarget:
                SecondBlobDate = date
                break
        if SecondBlobDate is None:
            return False

        # Use bisect to find the matching firstblob
        idx = bisect_right(self.FirstBlobTimestamps, SecondBlobDate) - 1
        if idx >= 0:
            FirstTarget = self.FirstBlobDates[idx][1]
            return FirstTarget
        else:
            return False

    def PopulateRows(self):
        CurrentYear = None  # On slow drives we should start from a offset year.
        for item in self.BlobsFiles:
            filename = None
            temp = None
            # Handle packed vs loose blobs
            if self.PackReader is None:
                if not item.is_file():
                    continue
                filename = item.name
                if filename.startswith("secondblob.bin"):
                    # Extract datetime from filename
                    # Expected format: "secondblob.bin.YYYY-MM-DD HH_MM_SS - description"
                    try:
                        # Remove 'secondblob.bin.' prefix
                        name_part = filename[len("secondblob.bin."):]
                        # Split by ' - ' to separate datetime and description
                        parts = name_part.split(' - ', 1)
                        date_str = parts[0]
                        # Parse datetime from filename
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                        # Format the date and time separately
                        date_part = date_obj.strftime('%m/%d/%Y')
                        time_part = date_obj.strftime('%I:%M:%S %p')

                        # Combine with a larger space between date and time
                        date_display = f"{date_part}   {time_part}"  #
                        description = parts[1] if len(parts) > 1 else ""
                        # Check if custom
                        is_custom = '(C)' in filename
                        new_row = [
                                self.GetLocale('label_yes') if is_custom else self.GetLocale('label_no'),
                                '',  # Placeholder for Steam version
                                '',  # Placeholder for SteamUI version
                                date_display,
                                description,
                                filename
                        ]
                        self.SecondBlobs.append(filename)
                        self.SecondBlobDates.append((date_obj.timestamp(), filename))
                        self.Rows.append(new_row)
                    except Exception as e:
                        print(f"Error parsing secondblob filename '{filename}': {e}")
                        continue
                elif filename.startswith("firstblob.bin"):
                    # Handle firstblob
                    try:
                        # Remove 'firstblob.bin.' prefix
                        name_part = filename[len("firstblob.bin."):]
                        # Remove ' (C)' suffix if present
                        if ' (' in name_part:
                            name_part = name_part.split(' (')[0]
                        # Parse datetime from filename
                        date_obj = datetime.strptime(name_part, '%Y-%m-%d %H_%M_%S')
                        self.FirstBlobs.append(filename)
                        self.FirstBlobDates.append((date_obj.timestamp(), filename))
                        # Update landmarks based on year
                        if CurrentYear != date_obj.year:
                            self.LandMarks[date_obj.year] = filename
                            CurrentYear = date_obj.year
                    except Exception as e:
                        print(f"Error parsing firstblob filename '{filename}': {e}")
                        continue
            else:
                # Handle packed blobs (Assuming similar parsing logic)
                filename = item
                if filename.startswith('firstblob.bin'):
                    try:
                        date_obj = datetime.fromtimestamp(self.PackReader.FirstData[filename]['date'])
                        self.FirstBlobs.append(filename)
                        self.FirstBlobDates.append((date_obj.timestamp(), filename))
                        # Update landmarks based on year
                        if CurrentYear != date_obj.year:
                            self.LandMarks[date_obj.year] = filename
                            CurrentYear = date_obj.year
                    except Exception as e:
                        print(f"Error parsing packed firstblob '{filename}': {e}")
                        continue
                elif filename.startswith('secondblob.bin'):
                    try:
                        # Remove 'secondblob.bin.' prefix
                        name_part = filename[len("secondblob.bin."):]
                        # Split by ' - ' to separate datetime and description
                        parts = name_part.split(' - ', 1)
                        date_str = parts[0]
                        # Parse datetime from filename
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                        date_display = date_obj.strftime('%m/%d/%Y %I:%M:%S %p')

                        description = parts[1] if len(parts) > 1 else ""
                        # Check if custom
                        is_custom = '(C)' in filename
                        new_row = [
                                self.GetLocale('label_yes') if is_custom else self.GetLocale('label_no'),
                                '',  # Placeholder for Steam version
                                '',  # Placeholder for SteamUI version
                                date_display,
                                description,
                                filename
                        ]
                        self.SecondBlobs.append(filename)
                        self.SecondBlobDates.append((date_obj.timestamp(), filename))
                        self.Rows.append(new_row)
                    except Exception as e:
                        print(f"Error parsing packed secondblob filename '{filename}': {e}")
                        continue

        # After populating, sort the lists
        self.FirstBlobDates.sort()
        self.SecondBlobDates.sort()
        self.FirstBlobTimestamps = [date for date, filename in self.FirstBlobDates]


    def FirstBlobThread(self):
        print('Read FirstBlob information for table data..')

        for i in range(len(self.Rows)):
            Current = self.SecondBlobs[i]
            SecondBlobDate = self.SecondBlobDates[i][0]

            # Find the insertion point for SecondBlobDate in the sorted FirstBlobTimestamps
            idx = bisect_right(self.FirstBlobTimestamps, SecondBlobDate) - 1

            # Ensure we have a valid index and that the FirstBlobDate is not newer than SecondBlobDate
            if idx >= 0:
                # Check if the found FirstBlobDate at idx is either an exact match or older than SecondBlobDate
                if abs(self.FirstBlobTimestamps[idx] - SecondBlobDate) < 1 or self.FirstBlobTimestamps[idx] <= SecondBlobDate:
                    FirstTarget = self.FirstBlobDates[idx][1]
                else:
                    FirstTarget = None
            else:
                FirstTarget = None
            # Read first blob
            if FirstTarget is not None:
                try:
                    if self.PackReader is None:
                        Info = ReadBlob(f'{self.BlobsFolder}{FirstTarget}')
                    elif isinstance(self.PackReader, FinalFileReaderv0):
                        Data = self.PackReader.ReadFirst(FirstTarget)
                        Info = ReadBytes(Data)
                    elif isinstance(self.PackReader, FinalFileReaderv1):
                        Info = [self.PackReader.FirstData[FirstTarget]['Steam_Version'], self.PackReader.FirstData[FirstTarget]['SteamUI_Version']]
                    else:
                        Info = None
                except Exception as e:
                    print(f"Error reading firstblob '{FirstTarget}': {e}")
                    Info = None
            else:
                Info = None

            # Update the table row with Steam and SteamUI versions
            if Info is None:
                self.Rows[i][1] = 'Unknown'
                self.Rows[i][2] = 'Unknown'
            else:
                self.Rows[i][1] = str(Info[0])
                self.Rows[i][2] = str(Info[1])

        print('Done!')

    def SwapBlobs(self):
        if self.load_from_database:
            try:
                # Get the selected row data from the table, which should include both first and second blob filenames
                selected_row = self.Rows[self.row]

                # Assuming second blob filename is stored in the last column of the row
                second_blob = selected_row[-1]  # Extract secondblob filename from the row

                # Extract the date from the Date column in the selected row
                date_str = selected_row[3]  # Date is in MM/DD/YYYY HH:MM AM/PM format
                date_obj = datetime.strptime(date_str, '%m/%d/%Y %I:%M:%S %p')
                second_blob_timestamp = date_obj.timestamp()  # Convert to timestamp

                # Print second_blob information for debugging
                # print(f"Selected second_blob: {second_blob}")
                # print(f"Second blob timestamp: {second_blob_timestamp} ({date_obj})")

                # Find the first_blob with the closest timestamp (before or after the second_blob timestamp)
                closest_first_blob = None
                smallest_diff = float('inf')  # Initialize with a large value

                for timestamp, filename in self.FirstBlobDates:
                    diff = abs(timestamp - second_blob_timestamp)
                    # print(f"Checking first_blob: {filename} with timestamp: {timestamp} ({datetime.fromtimestamp(timestamp)}) - Difference: {diff}")

                    if diff < smallest_diff:
                        closest_first_blob = filename
                        smallest_diff = diff
                        # print(f"Found closer first_blob: {filename} with difference: {diff}")

                # If no matching firstblob is found, fallback to 'Unknown'
                first_blob_filename = closest_first_blob if closest_first_blob else 'Unknown'

                # Print final selected first blob for debugging
                # print(f"Final selected first_blob: {first_blob_filename}")

                # Modify steam_date and steam_time in emulator.ini if necessary
                emulator_ini_path = Path('emulator.ini')

                date_formatted = date_obj.strftime('%Y-%m-%d')
                time_formatted = date_obj.strftime('%H_%M_%S')

                steam_date_exists = False
                steam_time_exists = False

                # Store the content of the file
                file_content = ""

                # Open the original emulator.ini file, read its contents, and prepare new content
                if emulator_ini_path.exists():
                    with open(emulator_ini_path, 'r', encoding = 'latin-1') as original_file:
                        for line in original_file:
                            stripped_line = line.strip()

                            # Uncomment and update steam_date and steam_time if found (either commented or uncommented)
                            if stripped_line.startswith(';steam_date') or stripped_line.startswith('steam_date'):
                                file_content += f'steam_date={date_formatted}\n'
                                steam_date_exists = True
                            elif stripped_line.startswith(';steam_time') or stripped_line.startswith('steam_time'):
                                file_content += f'steam_time={time_formatted}\n'
                                steam_time_exists = True
                            else:
                                file_content += line

                # If steam_date or steam_time were not found, append them at the end
                if not steam_date_exists:
                    file_content += f'steam_date={date_formatted}\n'
                if not steam_time_exists:
                    file_content += f'steam_time={time_formatted}\n'

                # Write all changes at once
                with open(emulator_ini_path, 'w', encoding = 'latin-1') as new_file:
                    new_file.write(file_content)

                # Now, update the GUI to show the installed first and second blobs
                self.matching_first_blob = copy.deepcopy(first_blob_filename)
                self.window['-IFB-'].update(value = f"Installed FirstBlob: {first_blob_filename}")  # Correctly display first blob
                self.window['-ISB-'].update(value = f"Installed SecondBlob: {second_blob}")  # Correctly display second blob
                self.LastSelectedFirstBlob = first_blob_filename
                # Update the status message
                self.window['-STATEMSG-'].Update(value = 'Steam date and time updated in emulator.ini')
                self.last_message_row = self.row

            except ValueError:
                self.window['-STATEMSG-'].Update(value = 'Invalid date format in the selected row')
            except IndexError:
                self.window['-STATEMSG-'].Update(value = 'Selected entry does not have corresponding FirstBlob or SecondBlob')
            except Exception as e:
                self.window['-STATEMSG-'].Update(value = f"An unexpected error occurred: {e}")

        else:
            # Inform user
            self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swapping'))

            # Required variables
            SecondTarget = self.Rows[self.row][-1]
            try:
                idx_second = self.SecondBlobs.index(SecondTarget)
                SecondBlobDate = self.SecondBlobDates[idx_second][0]
            except ValueError:
                self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_error2'))
                return

            # Use bisect to find the matching firstblob
            idx = bisect_right(self.FirstBlobTimestamps, SecondBlobDate) - 1
            if idx >= 0:
                FirstTarget = self.FirstBlobDates[idx][1]
                IsSolved = True
            else:
                FirstTarget = None
                IsSolved = False

            if not IsSolved or FirstTarget is None:
                print(f'Failed to resolve FirstBlob for: {SecondTarget}')
                self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_error2'))
                return

            """# Define the path for emulator.ini
            emulator_ini_path = Path('emulator.ini')

            # Flags to track if steam_date and steam_time exist
            steam_date_exists = False
            steam_time_exists = False

            # Read the entire contents of the file into memory
            with open(emulator_ini_path, 'r', encoding = 'latin-1') as file:
                lines = file.readlines()

            # Modify the lines in memory
            modified_lines = []
            for line in lines:
                stripped_line = line.strip()

                if stripped_line.startswith('steam_date') and not stripped_line.startswith(';'):
                    # Comment out the steam_date by adding a semicolon
                    modified_lines.append(f';{line}')
                    steam_date_exists = True
                elif stripped_line.startswith('steam_time') and not stripped_line.startswith(';'):
                    # Comment out the steam_time by adding a semicolon
                    modified_lines.append(f';{line}')
                    steam_time_exists = True
                else:
                    # Keep the line as is
                    modified_lines.append(line)

            # Write the modified lines back to the original file
            with open(emulator_ini_path, 'w', encoding = 'latin-1') as file:
                file.writelines(modified_lines)"""

            try:
                if self.PackReader is None:
                    File1 = open(f'{self.BlobsFolder}{SecondTarget}', 'rb')
                    File2 = open(f'{self.BlobsFolder}{FirstTarget}', 'rb')

                    with open(f'{self.FilesFolder}secondblob.bin', 'wb') as f:
                        f.write(File1.read())
                        f.flush()
                        File1.close()

                    with open(f'{self.FilesFolder}firstblob.bin', 'wb') as f:
                        f.write(File2.read())
                        f.flush()
                        File2.close()

                    try:
                        copystat(f'{self.BlobsFolder}{SecondTarget}', f'{self.FilesFolder}secondblob.bin')
                        copystat(f'{self.BlobsFolder}{FirstTarget}', f'{self.FilesFolder}firstblob.bin')
                    except:
                        psg.popup(self.GetLocale('label_error_text2'))
                else:
                    FirstData = self.PackReader.ReadFirst(FirstTarget)
                    SecondData = self.PackReader.ReadSecond(SecondTarget)

                    with open(f'{self.FilesFolder}secondblob.bin', 'wb') as f:
                        f.write(SecondData)
                        f.flush()
                        f.close()
                    with open(f'{self.FilesFolder}firstblob.bin', 'wb') as f:
                        f.write(FirstData)
                        f.flush()
                        f.close()

                    try:
                        utime(f'{self.FilesFolder}secondblob.bin', (SecondBlobDate, SecondBlobDate))
                        # Assuming you have the date for firstblob as well
                        FirstBlobDate = self.FirstBlobDates[idx][0]
                        utime(f'{self.FilesFolder}firstblob.bin', (FirstBlobDate, FirstBlobDate))
                    except:
                        psg.popup(self.GetLocale('label_error_text2'))
            except Exception as ex:
                self.window['-STATEMSG-'].Update(value = f"{self.GetLocale('label_swap_error3')}\r\n{ex}")
            else:
                try:
                    osremove(f"{self.CacheFolder}secondblob.bin")
                except:
                    pass
                self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_success'))
                self.window['-IFB-'].update(value = f"{self.GetLocale('label_installed_blob1')} {FirstTarget}")
                self.window['-ISB-'].update(value = f"{self.GetLocale('label_installed_blob2')} {SecondTarget}")
                self.matching_first_blob = copy.deepcopy(FirstTarget)
                # Update the tracking attribute
                self.last_message_row = self.row

    def ConnectToDatabase(self):
        db_url = f"mysql+pymysql://{self.database_username}:{self.database_password}@{self.database_host}:{self.database_port}/"
        try:
            self.engine = create_engine(db_url)
            self.connection = self.engine.connect()
        except Exception as e:
            psg.popup(f"Failed to connect to database: {e}")
            sys.exit(1)

    def PopulateRowsFromDatabase(self):
        # Clear previous rows and blobs
        self.Rows = []
        self.FirstBlobDates = []
        self.SecondBlobDates = []
        self.SecondBlobs = []  # Add this line to initialize SecondBlobs
        configurations_dict = {}
        try:
            # Fetch filename, steam_pkg, steamui_pkg from configurations table
            configurations_query = text("""
                SELECT filename, steam_pkg, steamui_pkg, ccr_blobdatetime 
                FROM clientconfigurationdb.configurations
            """)
            configurations_result = self.connection.execute(configurations_query).fetchall()

            # Populate configurations_dict with parsed data
            for row in configurations_result:
                filename = row[0]

                # Only process filenames that start with 'firstblob.bin'
                if filename.startswith('firstblob.bin'):
                    date_str = filename.replace('firstblob.bin.', '').replace(' (C)', '')
                    parts = date_str.split(' - ', 1)
                    date_time_str = parts[0].strip()  # e.g., '2004-04-01 00_17_09'
                    try:
                        # Parse datetime from filename
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                        timestamp = date_obj.timestamp()
                        configurations_dict[filename] = {
                                'steam_pkg':  row[1],  # Steam package version
                                'steamui_pkg':row[2],  # Steam UI package version
                                'date':       date_obj  # Parsed date for matching
                        }
                        # Store date and filename for sorting
                        self.FirstBlobDates.append((timestamp, filename))
                    except ValueError:
                        # Skip entries with invalid date formats
                        print(f"Skipping invalid filename format: {filename}")
                        continue
        except Exception as e:
            psg.PopupError(f"Failed to query configurations table: {e}")
            exit(1)
        # Sort and initialize timestamps for blobs
        self.FirstBlobDates.sort()
        self.FirstBlobTimestamps = [date for date, _ in self.FirstBlobDates]

        # Fetch data from filename table (secondblob.bin)
        try:
            filename_query = text("""
                SELECT filename, blob_datetime, comments, is_custom 
                FROM contentdescriptiondb.filename
            """)
            filename_result = self.connection.execute(filename_query).fetchall()

            for row in filename_result:
                filename = row[0] or ''
                blob_datetime = row[1] or ''
                comments = row[2] or ''
                is_custom = row[3] or 0

                # Initialize display values
                steam_version = 'Unknown'
                steamui_version = 'Unknown'
                date_display = 'Unknown'

                if filename.startswith('secondblob.bin.'):
                    date_str = filename.replace('secondblob.bin.', '')

                    try:
                        # Split to separate datetime and description
                        parts = date_str.split(' - ', 1)
                        date_time_str = parts[0].strip()  # e.g., '2004-04-01 00_17_09'

                        # Parse datetime
                        date_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H_%M_%S')
                        timestamp = date_obj.timestamp()
                        # Find the most recent firstblob that is <= current date_obj
                        matching_firstblobs = [
                                (fname, config['date'])
                                for fname, config in configurations_dict.items()
                                if config['date'] <= date_obj
                        ]
                        if matching_firstblobs:
                            # Select the firstblob with the latest date
                            matching_firstblobs.sort(key = lambda x:x[1], reverse = True)
                            matched_fname = matching_firstblobs[0][0]
                            steam_version = configurations_dict[matched_fname]['steam_pkg']
                            steamui_version = configurations_dict[matched_fname]['steamui_pkg']
                            self.SecondBlobDates.append((timestamp, filename))
                        # Format date for display
                        date_part = date_obj.strftime('%m/%d/%Y')
                        time_part = date_obj.strftime('%I:%M:%S %p')

                        # Combine with a larger space between date and time
                        date_display = f"{date_part}   {time_part}"
                    except ValueError:
                        print(f"Invalid date format in filename: {filename}")
                else:
                    print(f"Filename does not start with 'secondblob.bin.': {filename}")
                if steam_version != "7" and steamui_version != "16":
                    # Append the processed row to self.Rows
                    new_row = [
                            'Yes' if is_custom else 'No',  # Custom label
                            steam_version,  # Steam version
                            steamui_version,  # SteamUI version
                            date_display,  # Date
                            comments,  # Description
                            filename
                    ]
                    self.Rows.append(new_row)
                    self.SecondBlobs.append(filename)  # Add this line to keep track of secondblob filenames
        except Exception as e:
            psg.PopupError(f"Failed to query filename table: {e}")
            exit(1)
        # After populating the table rows, find matching first and second blob based on steam_date and steam_time
        # Update the text at the top of the window after finding matching blobs

    def sort_table(self, col_index):
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
    Manager.window['-SELECTTEXT-'].Update(value=f"{Manager.GetLocale('label_selected')} {Manager.Rows[Manager.row][-1]}")
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
def open_settings_dialog():
    import configparser
    import re
    import tkinter as tk
    from tkinter import ttk

    # Read the emulator.ini file
    config = configparser.ConfigParser(inline_comment_prefixes=(';',))
    config.optionxform = str  # Preserve case sensitivity
    config.read('emulator.ini')

    # Read the emulator.ini file lines to get comments and headings
    with open('emulator.ini', 'r') as f:
        lines = f.readlines()

    # Parse settings and associate comments and group under headings
    sections = {}
    current_heading = 'General'  # Default heading
    current_comment = ''
    for index, line in enumerate(lines):
        line = line.rstrip('\n')
        stripped_line = line.strip()
        if stripped_line.startswith(';'):
            # Check if this is a heading line followed by a separator
            if index + 1 < len(lines):
                next_line = lines[index + 1].strip()
                if next_line.startswith(';') and set(next_line.strip(';')) == {'='}:
                    # It's a heading
                    heading = stripped_line.lstrip(';').strip()
                    current_heading = heading
                    if current_heading not in sections:
                        sections[current_heading] = []
                    continue
            current_comment += stripped_line.lstrip(';').strip() + '\n'
        elif '=' in stripped_line and not stripped_line.startswith('['):
            key, value = stripped_line.split('=', 1)
            key = key.strip()
            value = value.split(';', 1)[0].strip()
            # Determine the type of the setting
            if value.lower() in ('true', 'false'):
                setting_type = 'bool'
            else:
                setting_type = 'str'
                # Special handling for log_level
                if key == 'log_level':
                    setting_type = 'log_level'
                elif key.endswith('_port'):
                    setting_type = 'port'
                elif key.endswith('dir'):
                    setting_type = 'dir'
            setting_info = {'key': key, 'value': value, 'comment': current_comment.strip(), 'type': setting_type}
            if current_heading not in sections:
                sections[current_heading] = []
            sections[current_heading].append(setting_info)
            current_comment = ''
        else:
            current_comment = ''  # Reset comment if other lines

    # Create the layout for the settings dialog
    tab_layouts = []
    for heading, settings_list in sections.items():
        tab_layout = []
        for setting in settings_list:
            tooltip = setting['comment'] if setting['comment'] else None
            if setting['type'] == 'bool':
                tab_layout.append([psg.Checkbox(setting['key'], default=(setting['value'].lower() == 'true'), tooltip=tooltip, key=setting['key'])])
            elif setting['type'] == 'log_level':
                # Create combobox for log_level
                options = ['DEBUG', 'WARNING', 'ERROR', 'INFO']
                current_value = setting['value'].replace('logging.', '')
                tab_layout.append([psg.Text(setting['key'], tooltip=tooltip), psg.Combo(options, default_value=current_value, key=setting['key'])])
            elif setting['type'] == 'port':
                # Create text input with a 7-character limit for ports
                tab_layout.append([psg.Text(setting['key'], tooltip=tooltip), psg.InputText(setting['value'], size=(7, 1), key=setting['key'])])
            elif setting['type'] == 'dir':
                # Create text input with a "Select Directory" button for directory paths
                tab_layout.append([
                    psg.Text(setting['key'], tooltip=tooltip),
                    psg.InputText(setting['value'], key=setting['key'], tooltip=tooltip),
                    psg.FolderBrowse('Select Directory', key=f'{setting["key"]}_browse')
                ])
            else:
                tab_layout.append([psg.Text(setting['key'], tooltip=tooltip), psg.InputText(setting['value'], key=setting['key'])])
        tab_layouts.append(psg.Tab(heading, tab_layout))

    # Add Save and Cancel buttons
    layout = [[psg.TabGroup([tab_layouts], tab_location='top', enable_events=True)],  # Increase tab width
              [psg.Button('Save'), psg.Button('Cancel')]]

    # Create the window with a scrollable tab bar to prevent squishing
    window = psg.Window('Settings', layout, modal=True, resizable=True, size=(600, 400))  # Adjust window size

    # Event loop for the settings window
    while True:
        event, values = window.read()
        if event == 'Save':
            # Save the settings back to emulator.ini
            # Read the original file lines again to preserve comments and structure
            with open('emulator.ini', 'r') as f:
                ini_lines = f.readlines()

            # Update the values in ini_lines
            for index, line in ini_lines:
                stripped_line = line.strip()
                if '=' in stripped_line and not stripped_line.startswith(';') and not stripped_line.startswith('['):
                    key, _ = stripped_line.split('=', 1)
                    key = key.strip()
                    if key in values:
                        if key == 'log_level':
                            new_value = f'logging.{values[key]}'
                        else:
                            new_value = str(values[key])
                        # Replace the line with the new value
                        ini_lines[index] = f'{key}={new_value}\n'

            # Write back to emulator.ini
            with open('emulator.ini', 'w') as f:
                f.writelines(ini_lines)

            psg.popup('Settings saved successfully.')
            break
        elif event in (psg.WIN_CLOSED, 'Cancel'):
            break

    window.close()


# Function to handle selection changes
# Function to handle selection changes
def update_selected_text():
    if Manager.row is not None and Manager.row >= 0:
        Manager.window['-SELECTTEXT-'].Update(value=f"{Manager.GetLocale('label_selected')} {Manager.Rows[Manager.row][-1]}")
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
    elif event == '-SETTINGS-':
        open_settings_dialog()
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
    elif '-SELECTTEXT- Double' in event:
        try:
            out = f'SecondBlob: {Manager.Rows[Manager.row][-1]}\r\nFirstBlob: {Manager.matching_first_blob}'
            clipboardcopy(out)
            Manager.window['-STATEMSG-'].Update(value=Manager.GetLocale('label_copyclip'))
        except:
            pass
        continue

    elif '-SELECTTEXT-' in event:
        try:
            clipboardcopy(Manager.Rows[Manager.row][-1])
            Manager.window['-STATEMSG-'].Update(value=Manager.GetLocale('label_copyclip'))
        except:
            pass
    elif 'Extract' in event:
        folder_selected = filedialog.askdirectory()
        if folder_selected == '' or folder_selected == ():
            print('cancel')
        else:
            ThePath = Path(folder_selected)

            if ThePath.is_dir():
                # Handle extraction
                if len(Manager.multiple_rows) > 1:
                    print('Multiple blobs selected.')
                    for row in Manager.multiple_rows:
                        ThePath2 = Path(folder_selected)
                        ThePath3 = Path(folder_selected)
                        SecondName = Manager.Rows[row][-1]

                        try:
                            if Manager.PackReader is not None:
                                FirstName = Manager.GetFirstBlobTo_Packed(SecondName)
                                Manager.PackReader.WriteFirst(FirstName, ThePath)
                                Manager.PackReader.WriteSecond(SecondName, ThePath)
                            else:
                                FirstName = Manager.GetFirstBlobTo_Unpacked(SecondName)
                                with open(f'{ThePath}/secondblob.bin', 'wb') as f:
                                    with open(f'{Manager.BlobsFolder}{SecondName}', 'rb') as src:
                                        f.write(src.read())
                                with open(f'{ThePath}/firstblob.bin', 'wb') as f:
                                    with open(f'{Manager.BlobsFolder}{FirstName}', 'rb') as src:
                                        f.write(src.read())
                                copystat(f'{Manager.BlobsFolder}{SecondName}', f'{ThePath}/secondblob.bin')
                                copystat(f'{Manager.BlobsFolder}{FirstName}', f'{ThePath}/firstblob.bin')
                        except Exception as ex:
                            Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_failure'))
                            print(f"Extraction failed for {SecondName}: {ex}")
                            continue
                        Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_success'))
                else:
                    ThePath2 = Path(folder_selected)
                    ThePath3 = Path(folder_selected)
                    SecondName = Manager.Rows[Manager.row][-1]

                    try:
                        if Manager.PackReader is not None:
                            FirstName = Manager.GetFirstBlobTo_Packed(SecondName)
                            Manager.PackReader.WriteFirst(FirstName, ThePath)
                            Manager.PackReader.WriteSecond(SecondName, ThePath)
                        else:
                            FirstName = Manager.GetFirstBlobTo_Unpacked(SecondName)
                            with open(f'{ThePath}/secondblob.bin', 'wb') as f:
                                with open(f'{Manager.BlobsFolder}{SecondName}', 'rb') as src:
                                    f.write(src.read())
                            with open(f'{ThePath}/firstblob.bin', 'wb') as f:
                                with open(f'{Manager.BlobsFolder}{FirstName}', 'rb') as src:
                                    f.write(src.read())
                            copystat(f'{Manager.BlobsFolder}{SecondName}', f'{ThePath}/secondblob.bin')
                            copystat(f'{Manager.BlobsFolder}{FirstName}', f'{ThePath}/firstblob.bin')
                    except Exception as ex:
                        Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_failure'))
                        print(f"Extraction failed for {SecondName}: {ex}")
                        continue
                    Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_success'))
            else:
                Manager.custom_popup(Manager.GetLocale('label_error_text3'))
                if event in (psg.WIN_CLOSED, 'Exit'):
                    break

if Manager.load_from_database:
    # Close database connection if open, with error handling
    if hasattr(Manager, 'connection') and Manager.connection:
        try:
            Manager.connection.close()
        except OperationalError:
            print("Database connection could not be closed gracefully. Connection was already lost.")
        except Exception as e:
            print(f"An unexpected error occurred while closing the database connection: {e}")

    # Dispose of the engine if it's open, with error handling
    if hasattr(Manager, 'engine') and Manager.engine:
        try:
            Manager.engine.dispose()
        except OperationalError:
            print("Database engine disposal encountered an issue. Connection was already lost.")
        except Exception as e:
            print(f"An unexpected error occurred while disposing of the database engine: {e}")

# Close the GUI window
Manager.window.close()