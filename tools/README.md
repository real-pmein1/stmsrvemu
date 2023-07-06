# Emulator Tools
Source code for the various tools used for manipulation of the emulator

Compile on Python 2.7 x86-32 or x86-64 if you want to run/build from source using:

python.exe -m PyInstaller -F -i source-content.ico emulator.py

OR

python.exe setup.py py2exe

> *Please note these are only designed for server emulator admins and offer no specific features for end-users*

### Credits
+ pmein1 - Developer and support
+ Dormine - Original python tools

### Tool Info:
+ blob: Converts firstblob (CCDB) and secondblob (CDDB) .bin files to and from .py readable blobs
+ download_app: Can be used to download depots from a local server emulator directly into v0.2 or v0.3 storages/manifests
+ gcf/ncf_to_storage_0.2: Creates v0.2 storages/manifests from GCF or NCF+common files
+ gcf/ncf_to_storage_0.3: Creates v0.3 storages/manifests from GCF or NCF+common files
+ pkg: Extracts and creates Steam and SteamUI .pkg files
+ resetpassword: Changes the password contained in the userblob (SADB) .py file for a non-legacy user
+ submanager: Adds or removes subscriptions in the specificed user's SADB
+ toggleblock: Enables or disables the block flag within the specificed user's SADB