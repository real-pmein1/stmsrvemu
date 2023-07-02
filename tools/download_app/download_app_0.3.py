import logging, struct, sys, zlib, os, random, time, threading, Queue, socket, binascii

from Steam.impsocket import impsocket
from Steam import oldsteam03
from Steam.fileclient import *
from Steam import client
from Steam import blob
from Steam import contentblob
from Steam.manifest import Manifest

config={}
execfile("config.py", config)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='download.log',
                    filemode='w')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

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

def compare_and_write_file(filename, data) :
    if os.path.isfile(filename) :
        f = open(filename, "rb")
        old_data = f.read()
        f.close()

        if data == old_data :
            print "Files are equal", os.path.basename(filename)
        else :
            timex = str(int(time.time()))
            os.rename(filename, filename + "." + timex + ".bak")
            f = open(filename, "wb")
            f.write(data)
            f.close()

            print "Files are DIFFERENT", os.path.basename(filename)
    else :
        f = open(filename, "wb")
        f.write(data)
        f.close()

        print "New file", os.path.basename(filename)

def download_app(appid, version) :
    storage = oldsteam03.Storage(str(appid), config["storagedir"])

    numservers = 10
    servers = client.get_fileservers(contentserver, appid, version, numservers)

    if not len(servers) :
        logging.warning("No servers for app %i ver %i found" % (appid, version))
        return

    thisclient = False
    for server in servers :
        try :
            print "Content server:", server
            thisclient = fileclient(server[2], appid, version, steamticket)
            break
        except ConnectionError :
            print "Refused connection, retrying with another server"

    if not thisclient or thisclient.connected == False :
        return
        
    while True :
        try :
            manifest_bin = thisclient.download_manifest()
            break
        except socket.error :
            print "Connection reset by peer?"
            pass

    manifest_filename = config["manifestdir"] + str(appid) + "_" + str(version) + ".manifest"
    compare_and_write_file(manifest_filename, manifest_bin)

    manif = Manifest(manifest_bin)
    
    while True :
        try :
            checksums_bin = thisclient.download_checksums()
            break
        except socket.error :
            print "Connection reset by peer?"
            pass

    checksums_filename = config["storagedir"] + str(appid) + ".checksums"
    compare_and_write_file(checksums_filename, checksums_bin)

    checksums = oldsteam03.Checksum(checksums_bin)

    for dir_id in manif.dir_entries :
        fileid = manif.dir_entries[dir_id].fileid
        if fileid == 0xffffffff :
            continue

        numchecksums = checksums.numchecksums(fileid)

        if numchecksums == 0 :
            continue

        if storage.indexes.has_key(fileid):
            continue

        print fileid, numchecksums

        if numchecksums == 1 and checksums.getchecksum(fileid, 0) == 0 :
            print "Empty file", fileid
            file = [""]
            filemode = 1
        else :
            (file, filemode) = thisclient.get_file(fileid, numchecksums)

        if filemode == 1 :
            goodchunks = 0
            for i in range(numchecksums) :

                data = file[i]

                try :
                    unpacked = zlib.decompress(data)
                except zlib.error :
                    logging.error("zlib error, possibly encrypted packet")
                    unpacked = ""

                if checksums.validate(fileid, i, unpacked) :
                    goodchunks = goodchunks + 1

            if numchecksums != goodchunks :
                logging.error("Checksum failed in app %i file %i" % (appid, fileid))

        storage.writefile(fileid, file, filemode)
        print " "

    thisclient.disconnect()

if len(sys.argv) == 1 :
    print
    print("USAGE 1: download_app list                : List available depot IDs")
    sys.exit("USAGE 2: download_app [depotid] [version] : Download a specific depot version")
    
dirserver = random.choice(config["dirservers"])
servers = client.get_contentserver(dirserver)
print "Content List servers:", repr(servers)
contentserver = servers[0]

cblob = blob.load_from_file(config["datadir"] + "contentblob.bin")
applist = contentblob.get_app_list(cblob)

userblob = blob.load_from_file(config["datadir"] + "userblob.bin")

f = open(config["datadir"] + "steamticket.bin", "rb")
steamticket = f.read()
f.close()

subscribelist = []
for subscription_id in userblob["\x07\x00\x00\x00"] :

    if userblob["\x07\x00\x00\x00"][subscription_id]["\x03\x00\x00\x00"] == "\x01\x00" :
        for app_id in cblob["\x02\x00\x00\x00"][subscription_id]["\x06\x00\x00\x00"] :
            app_id_int = struct.unpack("<L", app_id)[0]
            if not app_id_int in subscribelist :
                subscribelist.append(app_id_int)

subscribelist.sort()

if sys.argv[1] == "list" :
    print "Available apps:"
    count = 0
    for appid in subscribelist :
        print appid,
        count += 1
        if count % 10 == 0 :
            print
    sys.exit()
print

subscribelist2 = []
appcount = 0
while appcount < 999999 :
    subscribelist2.append(appcount)
    appcount += 1

#print count

if len(sys.argv) > 1 and int(sys.argv[1]) not in subscribelist2 :
    sys.exit("Don't have that app")

if len(sys.argv) == 2 :
    sys.exit("Missing version number")

for appid in subscribelist2 :

    if appid == int(sys.argv[1]) :
        version = int(sys.argv[2])
        logging.info("Downloading app %i version %i" % (appid, version))
        print
        download_app(appid, version)
        #app = applist[appid]

        # app not downloadable
        #if app.id in config["empty_apps"] :
            #continue

        #if len(sys.argv) > 1 and app.id != int(sys.argv[1]) :
            #continue
        
        #if len(sys.argv) > 2 :
            #version = int(sys.argv[2])
        #else :
            #version = app.betaversion

        #logging.info("Downloading app %i version %i (%s)" % (app.id, version, app.name))
        #download_app(app.id, version)
        print("DONE")