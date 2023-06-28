import sys, binascii, os, zlib, time

from Steam.ncf import NCF
from Steam.checksums import Checksums
from Steam import oldsteam

def compare_checksums(less, more) :
    for fileid in range(less.numfiles) :
        if less.checksums_raw[fileid] != more.checksums_raw[fileid] :
            print "Checksums doesn't match for file", fileid, len(less.checksums_raw[fileid]), len(more.checksums_raw[fileid])
            sys.exit()

manifestdir = "./"
storagedir = "./"

filename = sys.argv[1]
foldername = sys.argv[2]

if len(sys.argv) == 4 and sys.argv[3] == "update" :
    do_updates = True
else :
    do_updates = False

do_updates = True

ncf = NCF(filename)

print ncf.appid, ncf.appversion

storage = oldsteam.Storage(ncf.appid, storagedir)

manifest_filename = manifestdir + str(ncf.appid) + "_" + str(ncf.appversion) + ".manifest"
if os.path.isfile(manifest_filename) :
    f = open(manifest_filename, "rb")
    stored_manifest_data = f.read()
    f.close()

    if stored_manifest_data != ncf.manifest_data :
        print "Manifests differ!!"
        sys.exit()
    else :
        print "Manifests match, continuing.."
else :
    print "New manifest"

    # we write a new manifest anyway
    f = open(manifest_filename, "wb")
    f.write(ncf.manifest_data)
    f.close()

ncf_checksums = Checksums(ncf.checksum_data)

checksum_filename = storagedir + str(ncf.appid) + ".checksums"
if os.path.isfile(checksum_filename) :
    stored_checksums = Checksums()
    stored_checksums.load_from_file(checksum_filename)

    if ncf_checksums.numfiles > stored_checksums.numfiles :
        print "Checksums in NCF have more files than checksums in storage"
        compare_checksums(stored_checksums, ncf_checksums)
        
        if do_updates :
            timex = str(int(time.time()))
            os.rename(checksum_filename, checksum_filename + "." + timex + ".bak")
            f = open(checksum_filename, "wb")
            f.write(ncf.checksum_data)
            f.close()
    else :
        print "Checksums in storage have equal or more files than checksums in NCF"
        compare_checksums(ncf_checksums, stored_checksums)
else :
    if do_updates :
        f = open(checksum_filename, "wb")
        f.write(ncf.checksum_data)
        f.close()
    
print "Checking files "

if do_updates :
    logopen = 0
    for (dirid, d) in ncf.manifest.dir_entries.items() :
        if d.fileid == 0xffffffff :
            continue

        if ncf_checksums.numchecksums[d.fileid] == 0 :
            continue

        if d.dirtype & 0x100 :
            print "File encrypted", d.fileid
            sys.exit()
        if not storage.indexes.has_key(d.fileid) :
            if not os.path.exists(foldername + d.fullfilename) and d.itemsize != 0 :
                if logopen == 0 :
                    f = open(str(ncf.appid) + "_" + str(ncf.appversion) + "_log.txt", "wb")
                    logopen = 1
                print "File not exists: " + foldername + d.fullfilename
                f.write("File not exists: " + foldername + d.fullfilename + "\n")

            if d.itemsize != 0 and d.itemsize != os.path.getsize(foldername + d.fullfilename) :
                filesize = os.path.getsize(foldername + d.fullfilename)
                if logopen == 0 :
                    f = open(str(ncf.appid) + "_" + str(ncf.appversion) + "_log.txt", "wb")
                    logopen = 1
                print "Incorrect file size, " + d.fullfilename + " file size: " + str(filesize) + " file size in ncf: " + str(d.itemsize)
                f.write("Incorrect file size, " + d.fullfilename + " file size: " + str(filesize) + " file size in ncf: " + str(d.itemsize) + "\n")

    if logopen == 1 :
        f.close()
        sys.exit()

for (dirid, d) in ncf.manifest.dir_entries.items() :
    if d.fileid == 0xffffffff :
        continue

    if ncf_checksums.numchecksums[d.fileid] == 0 :
        continue

    if d.dirtype & 0x100 :
        print "File encrypted", d.fileid
        sys.exit()
    if not storage.indexes.has_key(d.fileid) :
    
        print "File not in storage", d.fileid, d.fullfilename
        
        if d.dirtype & 0x100 :
            file = []
            for ncf_block in ncf.get_file(dirid) :
                file.append(ncf_block)
            file = "".join(file)
            print binascii.b2a_hex(file[:64])
            
        else :
            if do_updates :
                file = []
                if d.itemsize != 0 :
                    filesize = os.path.getsize(foldername + d.fullfilename)
                    if filesize != d.itemsize :
                        print "Length of extracted file and file size doesn't match!", filesize, d.itemsize
                        sys.exit()
                    f = open(foldername + d.fullfilename, "rb")
                    file = f.read()
                    f.close
                else :
                    file = ""
                chunks = []
                chunkid = 0
                for start in range(0, filesize, 32768) :
                    chunk = file[start:start+32768]
                    
                    if not ncf_checksums.validate_chunk(d.fileid, chunkid, chunk) :
                        print "Checksum failed!"
                        sys.exit()
                    
                    chunks.append(zlib.compress(chunk, 9))
                    chunkid += 1

                print "Writing file to storage", d.fullfilename, filesize
                storage.writefile(d.fileid, chunks, 1)
                continue
    else :
        if storage.filemodes[d.fileid] == 2 or storage.filemodes[d.fileid] == 3 :
            print "File is encrypted in storage but not in NCF", d.fileid
            sys.exit()

        storage_chunk = ""
        storage_chunkid = 0
        ncf_chunk = ""
        totalsize = 0
        for ncf_block in ncf.get_file(dirid) :
            if not storage_chunk :
                (storage_chunk, filemode) = storage.readchunk(d.fileid, storage_chunkid)
                if len(storage_chunk) :
                    storage_chunk = zlib.decompress(storage_chunk)

            ncf_chunk += ncf_block
            totalsize += len(ncf_block)
            if len(ncf_chunk) >= len(storage_chunk) :
                if ncf_chunk != storage_chunk :
                    print "Difference between chunks!!!", len(ncf_chunk), len(storage_chunk)
                    sys.exit()
                else :
                    #print "\b.",
                    pass

                storage_chunk = ""
                storage_chunkid += 1
                ncf_chunk = ""

        #print storage_chunkid, ncf_checksums.numchecksums[d.fileid]
        if totalsize != d.itemsize :
            print
            print "Different sizes, file incomplete? ", d.fileid, totalsize, d.itemsize
            #sys.exit()
        else :
            print "\b.",
