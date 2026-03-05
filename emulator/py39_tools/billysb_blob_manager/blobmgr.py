import copy
import os
import re
import sys
from datetime import datetime
import struct
import zlib
import traceback
from tkinter import filedialog
import PySimpleGUI as psg
import configparser
from pathlib import Path
from shutil import copystat
from threading import Thread
from time import sleep, monotonic
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


# Ensure repository root (contains `utilities`, `config.py`, etc.) is importable.
# Includes source and PyInstaller-frozen execution paths.
SCRIPT_DIR = Path(__file__).resolve().parent
repo_candidates = [Path.cwd(), SCRIPT_DIR, SCRIPT_DIR.parent, SCRIPT_DIR.parent.parent]

if getattr(sys, 'frozen', False):
    exe_dir = Path(sys.executable).resolve().parent
    repo_candidates.append(exe_dir)
    repo_candidates.extend(list(exe_dir.parents)[:6])

if hasattr(sys, '_MEIPASS'):
    repo_candidates.append(Path(getattr(sys, '_MEIPASS')))

seen_candidates = set()
for candidate in repo_candidates:
    resolved = candidate.resolve()
    resolved_str = str(resolved)
    if resolved_str in seen_candidates:
        continue
    seen_candidates.add(resolved_str)

    if (resolved / 'utilities').is_dir():
        if resolved_str not in sys.path:
            sys.path.insert(0, resolved_str)
        break


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
        self.ExportLoggingEnabled = any(arg.lower() == '-logging' for arg in sys.argv[1:])
        self.ExportLogPath = Path('./blobmgr_export.log')
        if self.ExportLoggingEnabled:
            try:
                with open(self.ExportLogPath, 'a', encoding = 'utf-8') as f:
                    f.write(f"\n=== BlobMgr export session started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            except Exception:
                pass
        self.row = None
        self.multiple_rows = None
        self._header_resize_in_progress = False
        self._header_resize_dragged = False
        self._last_header_resize_at = 0.0

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
                'label_extract_failure':     'FAILED TO EXPORT SELECTED BLOBS.',
                'label_swap_error1':         'NO FIRSTBLOBS! SWAP ABORTED.',
                'label_swap_error2':         'FAILED TO DETECT FIRSTBLOB! SWAP ABORTED.',
                'label_swap_error3':         'FAILED! COULD NOT WRITE/READ FILE. SWAP ABORTED',
                'label_error_title':         'Error.',
                'label_error_text1':         "Error! You need to run this program in the same folder as the emulator.\r\nFailed to find emulator.ini",
                'label_error_text2':         'Failed to preserve file dates of copied blobs.',
                'label_error_text3':         'The extraction destination must be a folder.',
                'label_error_generic':       'An error occured while performing the selected action\r\nPlease show BillySB a screenshot of the error below.\r\n',
                'label_menu1_item1':         '&Export',
                'label_menu1_item2_1':       '!&Packed',
                'label_menu1_item2_2':       '&Packed',
                'label_menu1_item3':         'Export Blob',
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
                    self.database_host = db_config.get('database_host', '127.0.0.1')
                    self.database_port = db_config.getint('database_port', 3306)
                    self.database_username = db_config.get('database_username', 'stmserver')
                    self.database_password = db_config.get('database_password', 'stmserver')
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
                col_widths = [3, 6, 8, 14, 40],
                enable_events = True,
                expand_x = True,
                expand_y = True,
                enable_click_events = True,  # Enable click events for the table
                right_click_menu = [
                        self.GetLocale('label_menu1_item1'),
                        [
                                self.GetLocale('label_menu1_item3'),
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
        if self.load_from_database:
            blob_base = "Database Blobs"
        else:
            blob_base = "File Based Blobs"

        self.window = psg.Window(
                f"Billy {self.GetLocale('label_blobmgr')} - {self.GetLocale('label_version')} 1.14 --- {blob_base}",
                layout,
                size = (1000, 500),
                finalize = True,
                resizable = True,
                return_keyboard_events = True
        )
        #self.window.hide()
        self.window.TKroot.withdraw()
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

        pkgs_list = list(enumerate(treeview.get_children()))
        total_count = len(pkgs_list)
        next_progress_update = 5
        loader['-STATUS-'].update(value = 'Checking package files...')
        loader['-PBAR-'].update(current_count = 75)
        loader.bring_to_front()
        steam_pkgs = set()
        steamui_pkgs = set()

        # Iterate over the existing Treeview items and apply tags based on criteria
        for idx, item_id in pkgs_list: #enumerate(treeview.get_children()):
            row = self.Rows[idx]
            steam_version = row[1]
            steamui_version = row[2]
            blob_filename = row[-1] if len(row) > 5 else None
            #print(steam_version, steamui_version)
            steam_pkg_path, steamui_pkg_path = self._resolve_package_paths(packages_dir, steam_version, steamui_version, blob_filename)
            steam_pkg_key = steam_pkg_path.lower()
            steamui_pkg_key = steamui_pkg_path.lower()

            # Determine tags based on file existence
            tags = []
            if steam_pkg_key not in steam_pkgs:
                if not os.path.exists(steam_pkg_path):
                    tags.append('missing_steam')
                else:
                    steam_pkgs.add(steam_pkg_key)
            if steamui_pkg_key not in steamui_pkgs:
                if not os.path.exists(steamui_pkg_path):
                    tags.append('missing_steamui')
                else:
                    steamui_pkgs.add(steamui_pkg_key)

            if tags:
                treeview.item(item_id, tags = tags)

            # Throttle loader updates to every 5% completion for startup responsiveness.
            if total_count > 0:
                phase_percent = int(((idx + 1) * 100) / total_count)
                if phase_percent >= next_progress_update or phase_percent == 100:
                    overall_percent = 75 + int((phase_percent * 25) / 100)
                    loader['-STATUS-'].update(value = f'Checking package files... {phase_percent}%')
                    loader['-PBAR-'].update(current_count = overall_percent)
                    next_progress_update = ((phase_percent // 5) + 1) * 5

        loader['-PBAR-'].update(current_count = 100)
        loader.close()

        self.window.TKroot.deiconify()
        # Refresh the window to apply the changes
        self.window.refresh()
        self.window.bind('<Control-f>', 'CTRL+F')

        # Dirty hack for steam green theme.
        self.set_heading_color(self.window['-LIST-'].widget.configure("style")[-1], '#4c5844', '#4c5844', '#4c5844')

        self.window['-LIST-'].bind("<Double-Button-1>", " Double")
        self.window['-SELECTTEXT-'].bind("<Double-Button-1>", " Double")
        treeview.bind('<ButtonPress-1>', self._on_treeview_button_press, add = '+')
        treeview.bind('<B1-Motion>', self._on_treeview_drag, add = '+')
        treeview.bind('<ButtonRelease-1>', self._on_treeview_button_release, add = '+')
        thread = Thread(target = self.WindowRefresher)
        thread.daemon = True
        thread.start()
        # Refresh window even when main thread is blocked.
        # Apply fixed startup column widths (non-dynamic) to match legacy layout.
        char_width = psg.Text.char_width_in_pixels(('Verdana', 9))  # Get character width in pixel
        table = self.window['-LIST-']
        table_widget = table.Widget
        table.expand(expand_x = True, expand_y = True)  # Expand table in both directions of 'x' and 'y'
        fixed_char_widths = [3, 6, 8, 14, 40]
        table_widget.pack_forget()
        for idx, cid in enumerate(self.TopRow):
            if idx >= len(fixed_char_widths):
                break
            min_chars = max(fixed_char_widths[idx], len(str(cid)) + 1)
            width_px = round(min_chars * char_width)
            is_description = (idx == len(self.TopRow) - 1)
            table_widget.column(cid, width = width_px, minwidth = width_px, stretch = is_description)
        table_widget.pack(side = 'left', fill = 'both', expand = True)

        self.LastSelected = None
        self.LastSelectedFirstBlob = None

        if self.PackReader is not None:
            self.window['-STATEMSG-'].Update(value = f'{self.GetLocale("label_use_preprocessed")} ({self.VersionPak})')
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
                    # Reset the matching blobs
                    matching_firstblob = None
                    matching_secondblob = None

                    target_ts = self.steam_datetime.timestamp()

                    # Find the matching secondblob (most recent <= target timestamp).
                    for timestamp, filename in reversed(self.SecondBlobDates):
                        if timestamp <= target_ts:
                            matching_secondblob = filename
                            break  # Stop after finding the most recent match

                    # Firstblob must be resolved from the chosen secondblob timestamp, not independently from target_ts.
                    if matching_secondblob:
                        matching_firstblob = self._resolve_first_blob_for_second(matching_secondblob)

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

    def _on_treeview_button_press(self, event):
        try:
            treeview = self.window['-LIST-'].Widget
            region = treeview.identify_region(event.x, event.y)
            self._header_resize_in_progress = (region == 'separator')
            self._header_resize_dragged = False
        except Exception:
            self._header_resize_in_progress = False
            self._header_resize_dragged = False

    def _on_treeview_drag(self, event):
        if self._header_resize_in_progress:
            self._header_resize_dragged = True

    def _on_treeview_button_release(self, event):
        if self._header_resize_in_progress and self._header_resize_dragged:
            self._last_header_resize_at = monotonic()
        self._header_resize_in_progress = False
        self._header_resize_dragged = False

    def _should_ignore_header_sort_click(self):
        return (monotonic() - self._last_header_resize_at) < 0.35

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

    def _normalize_version_value(self, value):
        return str(value).strip()

    def _steamui_display_value(self, steamui_value):
        value = self._normalize_version_value(steamui_value)
        if value in ('06001000', '6001000'):
            return '0.6.0.0/1.0.0.0'
        if value in ('06101100', '6101100'):
            return '0.6.1.0/1.1.0.0'
        return value

    def _steamui_raw_value(self, steamui_value):
        value = self._normalize_version_value(steamui_value)
        if value == '0.6.0.0/1.0.0.0':
            return '06001000'
        if value == '0.6.1.0/1.1.0.0':
            return '06101100'
        if value == '6001000':
            return '06001000'
        if value == '6101100':
            return '06101100'
        return value

    def _canonical_blob_filename(self, blob_filename):
        if blob_filename is None:
            return ''
        return str(blob_filename).split(' - ', 1)[0].strip()

    def _is_beta2_platform_blob(self, blob_filename):
        canonical = self._canonical_blob_filename(blob_filename)
        return canonical in {
                'secondblob.bin.2003-01-13 23_03_03',
                'secondblob.bin.2003-01-20 03_39_01',
                'secondblob.bin.2003-06-10 05_01_47',
        }

    def _resolve_package_paths(self, packages_dir, steam_version, steamui_version, blob_filename = None):
        steam_value = self._normalize_version_value(steam_version)
        steamui_raw = self._steamui_raw_value(steamui_version)

        # Early 2002 beta package layout: files live in packagedir/betav1/steam_{0|1}.pkg
        beta_pkg_name = None
        if steamui_raw == '06001000':
            beta_pkg_name = 'steam_0.pkg'
        elif steamui_raw == '06101100':
            beta_pkg_name = 'steam_1.pkg'

        if beta_pkg_name is not None:
            beta_pkg_path = f'{packages_dir}/betav1/{beta_pkg_name}'
            steam_pkg_path = beta_pkg_path
            steamui_pkg_path = beta_pkg_path
        elif self._is_beta2_platform_blob(blob_filename):
            # For specific beta2 blobs, both checks are resolved strictly in packagedir/betav2.
            # Steam uses steam_<version>.pkg and SteamUI uses PLATFORM_<steamui_version>.pkg.
            steam_pkg_path = f'{packages_dir}/betav2/steam_{steam_value}.pkg'
            steamui_pkg_path = f'{packages_dir}/betav2/PLATFORM_{steamui_raw}.pkg'
        else:
            steam_pkg_path = f'{packages_dir}/steam_{steam_value}.pkg'
            steamui_pkg_path = f'{packages_dir}/steamui_{steamui_raw}.pkg'

        return steam_pkg_path, steamui_pkg_path

    def GetLocale(self, variable):
        try:
            return self.config[self.Lang][variable]
        except:
            print(f'MISSING LANGUAGE STRING: {self.Lang}_{variable}')
            return f'{self.Lang}_{variable}'

    def LogExport(self, message):
        if not self.ExportLoggingEnabled:
            return
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{timestamp}] {message}"
        print(line)
        try:
            with open(self.ExportLogPath, 'a', encoding = 'utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass

    def LogExportException(self, context, ex):
        if not self.ExportLoggingEnabled:
            return
        self.LogExport(f"{context}: {ex}")
        try:
            trace = traceback.format_exc()
            with open(self.ExportLogPath, 'a', encoding = 'utf-8') as f:
                f.write(trace + '\n')
        except Exception:
            pass

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

    def _extract_datetime_token(self, filename, prefix):
        if not filename.startswith(prefix):
            raise ValueError(f"Unexpected blob filename format: {filename}")
        token = filename[len(prefix):].split(' - ', 1)[0].strip()
        if ' (' in token:
            token = token.split(' (', 1)[0].strip()
        datetime.strptime(token, '%Y-%m-%d %H_%M_%S')
        return token

    def _timestamp_for_blob_name(self, filename, is_first_blob):
        source = self.FirstBlobDates if is_first_blob else self.SecondBlobDates
        for ts, name in source:
            if name == filename:
                return ts
        return None

    def _resolve_first_blob_for_second(self, second_blob_name):
        second_ts = self._timestamp_for_blob_name(second_blob_name, is_first_blob = False)
        if second_ts is None:
            try:
                dt_token = self._extract_datetime_token(second_blob_name, 'secondblob.bin.')
                second_ts = datetime.strptime(dt_token, '%Y-%m-%d %H_%M_%S').timestamp()
            except Exception:
                second_ts = None

        if second_ts is None:
            self.LogExport(f"Failed to resolve secondblob timestamp for '{second_blob_name}'")
            return False

        idx = bisect_right(self.FirstBlobTimestamps, second_ts) - 1
        if idx >= 0:
            return self.FirstBlobDates[idx][1]
        self.LogExport(f"No firstblob <= secondblob timestamp for '{second_blob_name}'")
        return False

    def _build_first_blob_from_database(self, first_blob_name):
        try:
            from utilities.database.ccdb import construct_blob_from_ccdb
            from utilities import blobs as util_blobs
        except Exception as ex:
            self.LogExportException("Import error while loading firstblob DB builders", ex)
            raise RuntimeError("Unable to load DB firstblob builder modules. Check dependencies (mariadb).") from ex

        first_token = self._extract_datetime_token(first_blob_name, 'firstblob.bin.')
        self.LogExport(f"Building firstblob from DB using timestamp '{first_token}'")
        blob_dict = construct_blob_from_ccdb(
                self.database_host,
                self.database_port,
                self.database_username,
                self.database_password,
                first_token
        )
        if not blob_dict:
            raise RuntimeError(f"Could not assemble firstblob from database for {first_blob_name}")
        data = util_blobs.blob_serialize(blob_dict)
        self.LogExport(f"Built firstblob '{first_blob_name}' ({len(data)} bytes)")
        return data

    def _build_second_blob_from_database(self, second_blob_name):
        try:
            from utilities import cdr_manipulator
            from utilities import blobs as util_blobs
        except Exception as ex:
            self.LogExportException("Import error while loading secondblob DB builders", ex)
            raise RuntimeError("Unable to load DB secondblob builder modules. Check dependencies (mariadb).") from ex

        second_token = self._extract_datetime_token(second_blob_name, 'secondblob.bin.')
        cddb = "BetaContentDescriptionDB" if second_token < "2003-09-09 18_50_46" else "ContentDescriptionDB"
        self.LogExport(f"Building secondblob from DB '{cddb}' using timestamp '{second_token}'")
        blob_dict = cdr_manipulator.construct_blob_from_cddb(
                self.database_host,
                self.database_port,
                self.database_username,
                self.database_password,
                cddb,
                second_token,
                self.CacheFolder
        )
        if not blob_dict:
            raise RuntimeError(f"Could not assemble secondblob from database for {second_blob_name}")

        # Export uses legacy uncompressed 0x0150 blob format to match historic blob files.
        data = util_blobs.blob_serialize(blob_dict)
        self.LogExport(f"Built secondblob '{second_blob_name}' ({len(data)} bytes uncompressed)")
        return data

    def _get_export_filename(self, blob_name):
        # Database/file listings may append human-readable descriptions after " - ".
        # Export should keep only the canonical blob filename portion.
        return blob_name.split(' - ', 1)[0].strip()

    def _write_export_pair(self, export_path, first_name, second_name, first_data, second_data, first_ts = None, second_ts = None):
        first_export_name = self._get_export_filename(first_name)
        second_export_name = self._get_export_filename(second_name)

        first_path = export_path / first_export_name
        second_path = export_path / second_export_name

        with open(second_path, 'wb') as f:
            f.write(second_data)
        with open(first_path, 'wb') as f:
            f.write(first_data)

        if first_ts is not None:
            try:
                utime(first_path, (first_ts, first_ts))
            except Exception:
                pass
        if second_ts is not None:
            try:
                utime(second_path, (second_ts, second_ts))
            except Exception:
                pass

        self.LogExport(
                f"Wrote export pair: '{first_export_name}' ({len(first_data)} bytes), "
                f"'{second_export_name}' ({len(second_data)} bytes) -> {export_path}"
        )

    def ExportBlobPair(self, second_blob_name, export_path):
        self.LogExport(f"Starting export for '{second_blob_name}' (DB mode: {self.load_from_database})")
        first_blob_name = self._resolve_first_blob_for_second(second_blob_name)
        if not first_blob_name:
            raise RuntimeError(f"Unable to resolve firstblob for {second_blob_name}")

        first_ts = self._timestamp_for_blob_name(first_blob_name, is_first_blob = True)
        second_ts = self._timestamp_for_blob_name(second_blob_name, is_first_blob = False)

        if self.load_from_database:
            first_data = self._build_first_blob_from_database(first_blob_name)
            second_data = self._build_second_blob_from_database(second_blob_name)
            self._write_export_pair(export_path, first_blob_name, second_blob_name, first_data, second_data, first_ts, second_ts)
            return first_blob_name

        if self.PackReader is not None:
            first_data = self.PackReader.ReadFirst(first_blob_name)
            second_data = self.PackReader.ReadSecond(second_blob_name)
            self._write_export_pair(export_path, first_blob_name, second_blob_name, first_data, second_data, first_ts, second_ts)
            return first_blob_name

        first_source = Path(f'{self.BlobsFolder}{first_blob_name}')
        second_source = Path(f'{self.BlobsFolder}{second_blob_name}')
        self.LogExport(f"Reading file blobs from '{first_source}' and '{second_source}'")
        first_export_name = self._get_export_filename(first_blob_name)
        second_export_name = self._get_export_filename(second_blob_name)
        second_dest = export_path / second_export_name
        first_dest = export_path / first_export_name

        with open(second_dest, 'wb') as f:
            with open(second_source, 'rb') as src:
                f.write(src.read())
        with open(first_dest, 'wb') as f:
            with open(first_source, 'rb') as src:
                f.write(src.read())

        copystat(second_source, second_dest)
        copystat(first_source, first_dest)
        return first_blob_name

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
                        date_part = date_obj.strftime('%Y/%m/%d')
                        time_part = date_obj.strftime('%H:%M:%S')

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
                        date_display = date_obj.strftime('%Y/%m/%d %H:%M:%S')

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
            current_second = self.Rows[i][-1]
            SecondBlobDate = self._timestamp_for_blob_name(current_second, is_first_blob = False)
            if SecondBlobDate is None:
                try:
                    second_token = self._extract_datetime_token(current_second, 'secondblob.bin.')
                    SecondBlobDate = datetime.strptime(second_token, '%Y-%m-%d %H_%M_%S').timestamp()
                except Exception:
                    SecondBlobDate = None

            if SecondBlobDate is None:
                self.Rows[i][1] = 'Unknown'
                self.Rows[i][2] = 'Unknown'
                continue

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
                self.Rows[i][1] = self._normalize_version_value(Info[0])
                self.Rows[i][2] = self._steamui_display_value(Info[1])

        print('Done!')

    def SwapBlobs(self):
        if self.load_from_database:
            try:
                # Get the selected row data from the table, which should include both first and second blob filenames
                selected_row = self.Rows[self.row]

                # Assuming second blob filename is stored in the last column of the row
                second_blob = selected_row[-1]  # Extract secondblob filename from the row

                # Resolve firstblob using strict rule: most recent firstblob <= selected secondblob timestamp.
                first_blob_filename = self._resolve_first_blob_for_second(second_blob)
                if not first_blob_filename:
                    self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_error2'))
                    return

                second_blob_timestamp = self._timestamp_for_blob_name(second_blob, is_first_blob = False)
                if second_blob_timestamp is None:
                    second_token = self._extract_datetime_token(second_blob, 'secondblob.bin.')
                    second_blob_timestamp = datetime.strptime(second_token, '%Y-%m-%d %H_%M_%S').timestamp()
                date_obj = datetime.fromtimestamp(second_blob_timestamp)

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
                # Print the blobs used
                print(f"Swapping done: FirstBlob: {first_blob_filename}, SecondBlob: {second_blob}")

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
            SecondBlobDate = self._timestamp_for_blob_name(SecondTarget, is_first_blob = False)
            if SecondBlobDate is None:
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

                # Print the blobs used
                print(f"Swapping done: FirstBlob: {FirstTarget}, SecondBlob: {SecondTarget}")

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
                FROM ClientConfigurationDB.configurations
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
                SELECT 
                    filename, 
                    blob_datetime, 
                    comments, 
                    is_custom 
                FROM 
                    BetaContentDescriptionDB.filename
                UNION
                SELECT 
                    filename, 
                    blob_datetime, 
                    comments, 
                    is_custom 
                FROM 
                    ContentDescriptionDB.filename;
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
                        date_part = date_obj.strftime('%Y/%m/%d')
                        time_part = date_obj.strftime('%H:%M:%S')

                        # Combine with a larger space between date and time
                        date_display = f"{date_part}   {time_part}"
                    except ValueError:
                        print(f"Invalid date format in filename: {filename}")
                else:
                    print(f"Filename does not start with 'secondblob.bin.': {filename}")
                if steam_version != "7" and steamui_version != "16":
                    steam_version_display = self._normalize_version_value(steam_version)
                    steamui_version_display = self._steamui_display_value(steamui_version)
                    # Append the processed row to self.Rows
                    new_row = [
                            'Yes' if is_custom else 'No',  # Custom label
                            steam_version_display,  # Steam version
                            steamui_version_display,  # SteamUI version
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
                    date_obj = datetime.strptime(x[col_index], '%Y/%m/%d %H:%M:%S')
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
                        date_obj = datetime.strptime(x[3], '%Y/%m/%d %H:%M:%S')
                        date_ts = date_obj.timestamp()
                    except ValueError:
                        date_ts = 0  # Assign a default timestamp if parsing fails
                    return (has_description, date_ts)

                self.Rows.sort(key = description_asc_key, reverse = False)

            else:  # Descending
                def description_desc_key(x):
                    try:
                        # Parse the date string back to a datetime object
                        date_obj = datetime.strptime(x[3], '%Y/%m/%d %H:%M:%S')
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
    date_pattern = r"^\d{4}/\d{2}/\d{2}$"
    if re.match(date_pattern, date_str):
        try:
            # If it's just a year, it's valid
            if len(date_str) == 4:
                return True
            # If it's in mm/dd/yyyy format, try to parse it
            datetime.strptime(date_str, "%Y/%m/%d")
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
            search_date = datetime.strptime(search_date_str, "%Y/%m/%d").strftime("%Y/%m/%d")
    except ValueError:
        return False  # Invalid date format

    closest_index = None
    closest_diff = None

    for i in range(start_index, len(Manager.Rows)):
        date_str = Manager.Rows[i][3]  # Assuming date is column index 3

        # Normalize the table date by stripping time and formatting as mm/dd/yyyy
        try:
            table_date = datetime.strptime(date_str.split(" ")[0], "%Y/%m/%d").strftime("%Y/%m/%d")
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
            search_date_obj = datetime.strptime(search_date_str, "%Y/%m/%d")
            table_date_obj = datetime.strptime(table_date, "%Y/%m/%d")
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
        [psg.Text('Type a date to search (formats: yyyy/mm/dd or yyyy):')],
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
                    custom_popup('Invalid date format. Please enter yyyy/mm/dd or yyyy.')

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
                custom_popup('Invalid date format. Please enter yyyy/mm/dd or yyyy.')

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
                if Manager._should_ignore_header_sort_click():
                    continue
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
            second_blob = Manager.Rows[Manager.row][-1]
            matching_first_blob = Manager._resolve_first_blob_for_second(second_blob)
            if not matching_first_blob:
                matching_first_blob = "Unknown"

            out = f'SecondBlob: {second_blob}\r\nFirstBlob: {matching_first_blob}'

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
    elif 'Extract' in event or 'Export Blob' in event:
        folder_selected = filedialog.askdirectory()
        if folder_selected == '' or folder_selected == ():
            print('cancel')
        else:
            ThePath = Path(folder_selected)

            if ThePath.is_dir():
                selected_rows = []
                if values.get('-LIST-'):
                    selected_rows = values['-LIST-'].copy()
                elif Manager.multiple_rows:
                    selected_rows = Manager.multiple_rows.copy()
                elif Manager.row is not None:
                    selected_rows = [Manager.row]

                if not selected_rows:
                    Manager.window['-STATEMSG-'].Update(value = 'No blob selected to export.')
                    continue

                exported_count = 0
                total_count = len(selected_rows)
                failures = []
                for row in selected_rows:
                    second_name = Manager.Rows[row][-1]

                    try:
                        first_name = Manager.ExportBlobPair(second_name, ThePath)
                        print(f"Exported -> FirstBlob: {first_name}, SecondBlob: {second_name}, Path: {ThePath}")
                        exported_count += 1
                    except Exception as ex:
                        Manager.LogExportException(f"Extraction failed for '{second_name}'", ex)
                        failures.append(f"{second_name}: {ex}")

                if exported_count == total_count:
                    Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_success'))
                elif exported_count > 0:
                    if Manager.ExportLoggingEnabled:
                        Manager.window['-STATEMSG-'].Update(
                                value = f"Exported {exported_count}/{total_count} blob set(s). See {Manager.ExportLogPath.name} for errors."
                        )
                    else:
                        Manager.window['-STATEMSG-'].Update(
                                value = f"Exported {exported_count}/{total_count} blob set(s)."
                        )
                else:
                    if failures:
                        first_error = failures[0]
                        if Manager.ExportLoggingEnabled:
                            Manager.window['-STATEMSG-'].Update(
                                    value = f"{Manager.GetLocale('label_extract_failure')} {first_error} (details in {Manager.ExportLogPath.name})"
                            )
                        else:
                            Manager.window['-STATEMSG-'].Update(
                                    value = f"{Manager.GetLocale('label_extract_failure')} {first_error}"
                            )
                    else:
                        Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_failure'))
            else:
                custom_popup(Manager.GetLocale('label_error_text3'))
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
