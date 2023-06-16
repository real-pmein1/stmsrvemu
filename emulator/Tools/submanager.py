# uncompyle6 version 3.9.0
# Python bytecode version base 2.7 (62211)
# Decompiled from: Python 2.7.18 (v2.7.18:8d21aa21f2, Apr 20 2020, 13:19:08) [MSC v.1500 32 bit (Intel)]
# Embedded file name: Y:\source\Tools\submanager\submanager.py
import os, sys, ast, struct, binascii, shutil
subslist = []
try:
    username = sys.argv[1]
    subslist = sys.argv[2]
except:
    print '\nUsage: ' + sys.argv[0] + ' username subscriptions\n'
    print 'Subscription example: 0,2,3,10'
    print 'NOTE: 0 must always be included'
    os._exit(0)

try:
    shutil.copyfile('files/users/' + username + '.py', 'files/users/' + username + '.py.bak')
    userblobnew = {}
    sublist = []
    with open('files/users/' + username + '.py', 'r') as (f):
        userblob = {}
        userblobstr = f.read()
        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
        invalid = {'\x07\x00\x00\x00'}

        def without_keys(d, keys):
            return {x: d[x] for x in d if x not in keys}


        userblobnew = without_keys(userblob, invalid)
        l = len(sys.argv[2])
        li = sys.argv[2].split(',')
        sublist = li
        tempdict = {}
        i = 0
        for sub in li:
            subhex = struct.pack('<I', int(sub))
            subhex = binascii.hexlify(subhex)
            subhex = '\\x' + ('\\x').join(subhex[i:i + 2] for i in range(0, len(subhex), 2))
            if i == 0:
                tempstr = "{'\\x07\\x00\\x00\\x00': {'" + subhex + "': {'\\x01\\x00\\x00\\x00': '\\xe0\\xe0\\xe0\\xe0\\xe0\\xe0\\xe0\\x00', '\\x02\\x00\\x00\\x00': '\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00', '\\x03\\x00\\x00\\x00': '\\x01\\x00', '\\x05\\x00\\x00\\x00': '\\x00', '\\x06\\x00\\x00\\x00': '\\x1f\\x00'}"
            else:
                tempstr += ", '" + subhex + "': {'\\x01\\x00\\x00\\x00': '\\xe0\\xe0\\xe0\\xe0\\xe0\\xe0\\xe0\\x00', '\\x02\\x00\\x00\\x00': '\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00', '\\x03\\x00\\x00\\x00': '\\x01\\x00', '\\x05\\x00\\x00\\x00': '\\x00', '\\x06\\x00\\x00\\x00': '\\x1f\\x00'}"
            i += 1

        tempstr += '}}'
        tempdict = ast.literal_eval(tempstr)
        userblobnew.update(tempdict)
    with open('files/users/' + username + '.py', 'w') as (g):
        g.write('user_registry = ')
        g.write(str(userblobnew))
    print '\nWritten subscriptions ' + str(sublist) + ' to user description record'
except:
    print 'An error has occured, please try again'