python -m PyInstaller --noconsole -F -i icon.ico --hidden-import=tkinter ^
  --hidden-import=tkinter.font ^
  --hidden-import=tkinter.colorchooser ^
  --hidden-import=tkinter.filedialog ^
  --hidden-import=tkinter.simpledialog ^
  --hidden-import=difflib ^
  --hidden-import=configparser ^
  --hidden-import=queue ^
  --hidden-import=itertools ^
  --hidden-import=webbrowser ^
  --hidden-import=urllib.request ^
  --hidden-import=urllib.error ^
  --hidden-import=urllib.parse ^
  --hidden-import=json ^
  --hidden-import=pydoc ^
  --hidden-import=ctypes ^
  --hidden-import=platform --add-data "../../libs/PySimpleGUI/PySimpleGUI.py;." blobmgr.py
move dist\blobmgr.exe "..\..\"
