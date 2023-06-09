# Stm Server Emulator
Source code for the server emulator for clients 2004-2011

Compile on Python 2.7 x86-32 if you want to run/build from source using:

python.exe -m PyInstaller -F -i source-content.ico emulator.py

> *Please note the code is constant work-in-progress and might not compile or operate correctly, please use the release zip for full functionality*

### Credits
+ pmein1 - Developer and support
+ cystface-man - Developer and provided descriptions of CCDB records and service packet information
+ Dormine - Original python poc emulator code and updates
+ Tane - Original app update code
+ steamCooker - Help with some of the intricacies of the Steam services
+ GenoKirby - Provided description of section 5 of the SADB


### shefben/cystfaceman fork info:
I am using this fork to integrate all packets and services that have been found through reverse engineering.
The point is to hopefully one day have a complete steam network for the 2004-2008 clients that allow game authentication
game registration, and other things.

some other changes i hope to make are as followed:
  
+ Replaced user's .py file with a mysql database
+ Create a php script to query the database and also add/remove users and also add / remove subscriptions
+ Get tracker/friends server working for all steam versions
+ Get steam v2 (2003) working properly
+ Add Packets to allow for outside server's to be added to directoryserver list (like having multiple content servers that can automatically add to the directoryserver list)
