python -m PyInstaller --noconsole -F -i icon.ico ^
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
  --hidden-import=platform ^
  --add-data "resources;resources" blobmgr.py
move dist\blobmgr.exe "..\..\"
