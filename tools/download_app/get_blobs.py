import binascii, socket, time, sys, struct, sha, random, os

from Steam import client

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

def log_write(text):
    print text
    f = open(config["blobdir"] + "update_blobs.txt", "ab")
    f.write(text + "\r\n")
    f.close()

t = time.gmtime()
#serveraddress = ("63.145.202.3", 27038)
dirserver = random.choice(config["dirservers"])
servers = client.get_configserver(dirserver)
print "Config servers:", repr(servers)
print
serveraddress = servers[0]
t_string = time.strftime("%Y-%m-%d %H_%M_%S", t)

log_write("Starting download of blobs at %s GMT" % time.asctime(t) )

try :
    f = open(config["datadir"] + "versionblob.bin", "rb")
    versionblob = f.read()
    f.close()
except :
    versionblob = ""

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(serveraddress)
s.send("\x00\x00\x00\x03")
print binascii.b2a_hex(s.recv(5))
s.send("\x00\x00\x00\x01\x01")
reply = s.recv(4)
replylen = struct.unpack(">L", reply)[0]
reply = s.recv(replylen)
s.close()

if versionblob == reply :
    log_write("The version blob matches the latest one")
else :
    log_write("Storing new version blob")
    f = open(config["blobdir"] + "versionblob.bin." + t_string, "wb")
    f.write(reply)
    f.close()

    f = open(config["datadir"] + "versionblob.bin", "wb")
    f.write(reply)
    f.close()

try :
    f = open(config["datadir"] + "contentblob.bin", "rb")
    contentblob = f.read()
    f.close()
except :
    contentblob = ""

s = sha.new()
s.update(contentblob)
hash = s.digest()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(serveraddress)
s.send("\x00\x00\x00\x03")
print binascii.b2a_hex(s.recv(5))
s.send("\x00\x00\x00\x15\x09" + hash)
reply = s.recv(11)
if reply != binascii.a2b_hex("00000001312d000000012c") :
    print "Differing unknown data", binascii.b2a_hex(reply)
    sys.exit()
reply = s.recv(4)
replylen = struct.unpack(">L", reply)[0]
print replylen

if replylen == 0 :
    log_write("The content blob matches the latest one")
    s.close()
else :
    log_write("Storing new content blob")
    reply = ""
    while len(reply) < replylen :
        left = replylen - len(reply)
        reply = reply + s.recv(left)

    s.close()

    print len(reply)

    f = open(config["blobdir"] + "contentblob.bin." + t_string, "wb")
    f.write(reply)
    f.close()

    f = open(config["datadir"] + "contentblob.bin", "wb")
    f.write(reply)
    f.close()
