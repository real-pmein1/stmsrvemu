import sys, binascii, os, zlib, time

from Steam.gcf import GCF
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

if len(sys.argv) == 3 and sys.argv[2] == "update" :
    do_updates = True
else :
    do_updates = False

gcf = GCF(filename)

print gcf.appid, gcf.appversion

storage = oldsteam.Storage(gcf.appid, storagedir)

manifest_filename = manifestdir + str(gcf.appid) + "_" + str(gcf.appversion) + ".manifest"
if os.path.isfile(manifest_filename) :
    f = open(manifest_filename, "rb")
    stored_manifest_data = f.read()
    f.close()

    if stored_manifest_data != gcf.manifest_data :
        print "Manifests differ!!"
        sys.exit()
    else :
        print "Manifests match, continuing.."
else :
    print "New manifest"

    # we write a new manifest anyway
    f = open(manifest_filename, "wb")
    f.write(gcf.manifest_data)
    f.close()

gcf_checksums = Checksums(gcf.checksum_data)

checksum_filename = storagedir + str(gcf.appid) + ".checksums"
if os.path.isfile(checksum_filename) :
    stored_checksums = Checksums()
    stored_checksums.load_from_file(checksum_filename)

    if gcf_checksums.numfiles > stored_checksums.numfiles :
        print "Checksums in GCF have more files than checksums in storage"
        compare_checksums(stored_checksums, gcf_checksums)
        
        if do_updates :
            timex = str(int(time.time()))
            os.rename(checksum_filename, checksum_filename + "." + timex + ".bak")
            f = open(checksum_filename, "wb")
            f.write(gcf.checksum_data)
            f.close()
    else :
        print "Checksums in storage have equal or more files than checksums in GCF"
        compare_checksums(gcf_checksums, stored_checksums)
else :
    if do_updates :
        f = open(checksum_filename, "wb")
        f.write(gcf.checksum_data)
        f.close()
    
print "Checking files "

for (dirid, d) in gcf.manifest.dir_entries.items() :
    if d.fileid == 0xffffffff :
        continue

    if gcf_checksums.numchecksums[d.fileid] == 0 :
        continue

    if d.dirtype & 0x100 :
        print "File encrypted", d.fileid
        sys.exit()
    if not storage.indexes.has_key(d.fileid) :
    
        print "File not in storage", d.fileid, d.fullfilename
        
        if d.dirtype & 0x100 :
            file = []
            for gcf_block in gcf.get_file(dirid) :
                file.append(gcf_block)
            file = "".join(file)
            print binascii.b2a_hex(file[:64])

            if do_updates :
                if len(file) != d.itemsize :
                    print "Length of extracted file and file size doesn't match!", len(file), d.itemsize
                    sys.exit()
                    
                chunks = []
                chunkid = 0
                for start in range(0, len(file), 32768) :
                    chunk = file[start:start+32768]
                    
                    if not gcf_checksums.validate_chunk(d.fileid, chunkid, chunk, checksum_filename) :
                        print "Checksum failed!"
                        #a=1
                        sys.exit()
                    
                    chunks.append(zlib.compress(chunk, 9))
                    chunkid += 1
                        
                print "Writing file to storage", d.fullfilename, len(file)
                storage.writefile(d.fileid, chunks, 1)
                continue
            
        else :
            if do_updates :
                file = []
                for gcf_block in gcf.get_file(dirid) :
                    file.append(gcf_block)
                file = "".join(file)
                
                if len(file) != d.itemsize :
                    print "Length of extracted file and file size doesn't match!", len(file), d.itemsize
                    sys.exit()
                    
                chunks = []
                chunkid = 0
                for start in range(0, len(file), 32768) :
                    chunk = file[start:start+32768]
                    
                    if not gcf_checksums.validate_chunk(d.fileid, chunkid, chunk) :
                        print "Checksum failed!"
                        sys.exit()
                    
                    chunks.append(zlib.compress(chunk, 9))
                    chunkid += 1
                        
                print "Writing file to storage", d.fullfilename, len(file)
                storage.writefile(d.fileid, chunks, 1)
                continue
    else :
        if storage.filemodes[d.fileid] == 2 or storage.filemodes[d.fileid] == 3 :
            print "File is encrypted in storage but not in GCF", d.fileid
            sys.exit()

        storage_chunk = ""
        storage_chunkid = 0
        gcf_chunk = ""
        totalsize = 0
        for gcf_block in gcf.get_file(dirid) :
            if not storage_chunk :
                (storage_chunk, filemode) = storage.readchunk(d.fileid, storage_chunkid)
                if len(storage_chunk) :
                    storage_chunk = zlib.decompress(storage_chunk)

            gcf_chunk += gcf_block
            totalsize += len(gcf_block)
            if len(gcf_chunk) >= len(storage_chunk) :
                if gcf_chunk != storage_chunk :
                    print "Difference between chunks!!!", len(gcf_chunk), len(storage_chunk)
                    sys.exit()
                else :
                    #print "\b.",
                    pass

                storage_chunk = ""
                storage_chunkid += 1
                gcf_chunk = ""

        #print storage_chunkid, gcf_checksums.numchecksums[d.fileid]
        if totalsize != d.itemsize :
            print
            print "Different sizes, file incomplete? ", d.fileid, totalsize, d.itemsize
            #sys.exit()
        else :
            print "\b.",
