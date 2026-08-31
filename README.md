# STMServer Emulator
Source code for the server emulator for clients 2002-2011

* Install the required dependencies in the ``emulator`` folder using:
``python -m pip install -r requirements.txt``

* Compile on Python 3.9.13 using:
``python -m PyInstaller -F -i source-content.ico emulator.py --add-data "steam3/protobufs/:steam3/protobufs/" --add-data "files/icons/*.ico;files/icons/" --hidden-import tkinter``

> *Please note the code is constant work-in-progress and might not compile or operate correctly, please use the release zip for full functionality*

### Credits
+ pmein1 - Server developer and support
+ cystface-man - Server developer and support
+ Dormine - Original python poc emulator code and updates
+ Other credits can be found in credits.txt

# NOTICE
The aim of this emulator is for people to experience old clients.  We do not condone piracy and as such do not provide any client, game or other copyrighted material, nor do we condone or involve ourselves in sharing illegally obtained or leaked material.  We are not affiliated with Valve in any way.
