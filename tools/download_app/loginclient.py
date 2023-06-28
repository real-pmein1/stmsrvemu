import binascii, sys, socket, struct, time, os, random
from Crypto.Hash import SHA
from Crypto.Cipher import AES

from Steam import blob
from Steam import client
from Steam import tools
from Steam import crypto
from Steam.impsocket import impsocket
from Steam.userhash import userhash

config={}
execfile("config.py", config)

#create folders
try :
    os.mkdir(config["storagedir"])
except :
    a = 0
try :
    os.mkdir(config["manifestdir"])
except :
    a = 0
try :
    os.mkdir(config["datadir"])
except :
    a = 0
try :
    os.mkdir(config["blobdir"])
except :
    a = 0

if len(sys.argv) != 2 and len(sys.argv) != 3 :
    print """Usage:
    
 loginclient.py [username] [password]
 loginclient.py [logindata.bin]"""
 
    sys.exit()

if len(sys.argv) == 3 :
    loginname = sys.argv[1].lower()
    loginpass = sys.argv[2]
    namehash = userhash(loginname)
    timestamp = str(int(time.time()))
    filename = config["datadir"] + "login_" + loginname + timestamp + ".bin"
    dirserver = random.choice(config["dirservers"])
    servers = client.get_authserver(dirserver, namehash)
    print "Login servers:", repr(servers)
    
    authserver = servers[0]
    s = impsocket()
    s.connect(authserver)
    (local_ip, local_port) = s.getsockname()
    local_ip_bin = socket.inet_aton(local_ip)
    
    message = "\x00\x00\x00\x00\x04" + local_ip_bin[::-1] + struct.pack(">L", namehash)
    print "Sending data:", binascii.b2a_hex(message)
    s.send(message)

    reply = s.recv(5)
    print "Received data:", binascii.b2a_hex(reply)
    external_ip_bin = reply[1:5]

    namelen = struct.pack(">H", len(loginname))
    message = chr(2) + (namelen + loginname) * 2
    s.send_withlen(message)
    
    salt = s.recv(8)
    print "Received salt:", binascii.b2a_hex(salt)

    key = SHA.new(salt[:4] + loginpass + salt[4:]).digest()[:16]
    print "Password-based key:", repr(key)
   
    xorkey = SHA.new(external_ip_bin[::-1] + local_ip_bin).digest()[:8]
    steamtimestamp = tools.unixtime_to_steamtime(time.time())
    cleartext = crypto.binaryxor(xorkey, steamtimestamp) + local_ip_bin + "\x04\x04\x04\x04"
    print "Cleartext:", binascii.b2a_hex(cleartext)

    IV = binascii.a2b_hex("%032x" % random.getrandbits(128))
    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    ciphertext = cryptobj.encrypt(cleartext)
    message = IV + "\x00\x0c\x00\x10" + ciphertext
    print "Sending data:", binascii.b2a_hex(message)
    s.send_withlen(message)
    reply = s.recv(17)
    print "Received data:", binascii.b2a_hex(reply)
    print "Server sent command: %i" % ord(reply[0])
    
    if reply[0] != "\x00" :
        print "Login failed."
        s.close()
        sys.exit()
        
    (time_server, time_delta) = struct.unpack("<QQ", reply[1:17])

    if time_server != 0 :
        print "Server time: %s" % time.asctime(time.gmtime(tools.steamtime_to_unixtime(time_server)))
        print "Delta time: %s" % time.asctime(time.gmtime(tools.steamtime_to_unixtime(time_server + time_delta)))

    reply = s.recv_withlen()
    s.close()

    print len(reply)
    f = open(filename, "wb")
    f.write(key + reply)
    f.close()
else :
    f = open(sys.argv[1], "rb")
    key = f.read(16)
    reply = f.read()
    f.close()

print binascii.b2a_hex(reply[:86])

outerIV = reply[2:18]
ciphertext = reply[22:86]

plaintext = crypto.aes_decrypt(key, outerIV, ciphertext)
print "Plaintext: ", binascii.b2a_hex(plaintext)

innerkey = plaintext[:16]
print "inner key", binascii.b2a_hex(innerkey)
print repr(crypto.verify_message(innerkey, reply))

(steamid1, steamid3, steamid2) = struct.unpack("<HLL", plaintext[16:26])
print "Steam ID: %d:%d:%d" % (steamid1, steamid2, steamid3)
(time_1, time_2) = struct.unpack("<QQ", plaintext[38:54])
print hex(time_1), hex(time_2)
print "Server 1 time: %s" % time.asctime(time.gmtime(tools.steamtime_to_unixtime(time_1)))
print "Server 2 time: %s" % time.asctime(time.gmtime(tools.steamtime_to_unixtime(time_2)))

mysterylen = struct.unpack(">H", reply[86:88])[0]
print mysterylen

loginpacket = reply[86:88+mysterylen]

f = open(config["datadir"] + "steamticket.bin", "wb")
f.write(loginpacket)
f.close()

#print binascii.b2a_hex(loginpacket)
#print

startxx = 88 + mysterylen
bloblen = struct.unpack(">L", reply[startxx:startxx+4])[0]
print bloblen
blob_encrypted = reply[startxx+4:startxx+4+bloblen]
blob_encrypted = blob_encrypted[10:]

print repr(crypto.verify_message(innerkey, blob_encrypted))

innerIV = blob_encrypted[4:20]

bloblen = struct.unpack("<L", blob_encrypted[:4])[0]
print "bloblen", bloblen
plaintext = crypto.aes_decrypt(innerkey, innerIV, blob_encrypted[20:-20])
#print binascii.b2a_hex(plaintext)

f = open(config["datadir"] + "userblob.bin", "wb")
f.write(plaintext[:bloblen])
f.close()

b = blob.unserialize(plaintext[:bloblen])
print blob.dump_to_dict(b)

