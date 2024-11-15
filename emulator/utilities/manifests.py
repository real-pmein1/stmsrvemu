import logging
import os.path
import struct

from config import get_config as read_config
from utilities import steam2_sdk_utils
from utilities.blobs import SDKBlob
from utilities.bytebuffer import ByteBuffer

config = read_config()


class DirectoryEntry(object):
    pass


class Manifest(object):
    def __init__(self, manifestdata = ""):
        self.dirnames_start = None
        self.dir_entries = None
        if len(manifestdata) != 0:
            self.manifestdata = manifestdata
            self.initialize()

    def load_from_file(self, filename):
        f = open(filename, "rb")
        self.manifestdata = f.read()
        f.close()

        self.initialize()

    def initialize(self):
        (self.dummy1,
         self.stored_appid,
         self.stored_appver,
         self.num_items,
         self.num_files,
         self.blocksize,
         self.dirsize,
         self.dirnamesize,
         self.info1count,
         self.copycount,
         self.localcount,
         self.dummy2,
         self.dummy3,
         self.checksum) = struct.unpack("<LLLLLLLLLLLLLL", self.manifestdata[0:56])

        self.dirnames_start = 56 + self.num_items * 28

        self.dir_entries = {}
        for i in range(self.num_items):
            index = 56 + i * 28
            d = DirectoryEntry()
            (d.nameoffset, d.itemsize, d.fileid, d.dirtype, d.parentindex, d.nextindex, d.firstindex) = struct.unpack("<LLLLLLL", self.manifestdata[index:index + 28])
            filename_start = self.dirnames_start + d.nameoffset
            filename_end = self.manifestdata.index(b"\x00", filename_start)
            d.filename = self.manifestdata[filename_start:filename_end]
            self.dir_entries[i] = d

        for i in range(self.num_items):
            d = self.dir_entries[i]
            fullfilename = d.filename
            while d.parentindex != 0xffffffff:
                d = self.dir_entries[d.parentindex]

                fullfilename = d.filename + b"/" + fullfilename

            d = self.dir_entries[i]
            d.fullfilename = fullfilename

    def make_encrypted(self, filename):
        f = open(filename, "rb")
        self.manifestdata = f.read()
        f.close()
        # print(len(self.manifestdata))

        (self.dummy1,
         self.stored_appid,
         self.stored_appver,
         self.num_items,
         self.num_files,
         self.blocksize,
         self.dirsize,
         self.dirnamesize,
         self.info1count,
         self.copycount,
         self.localcount,
         self.dummy2,
         self.dummy3,
         self.checksum) = struct.unpack("<LLLLLLLLLLLLLL", self.manifestdata[0:56])

        manifestdatanew = self.manifestdata[0:56]

        self.dirnames_start = 56 + self.num_items * 28
        # print(len(self.manifestdata[0:56]))
        # print(len(self.manifestdata[56:len(self.manifestdata)]))

        self.dir_entries = {}
        for i in range(self.num_items):
            index = 56 + i * 28
            print(str(index))
            d = DirectoryEntry()
            (d.nameoffset, d.itemsize, d.fileid, d.dirtype, d.parentindex, d.nextindex, d.firstindex) = struct.unpack("<LLLLLLL", self.manifestdata[index:index + 28])

            if len(hex(d.dirtype)) == 6:
                # print(str(d.nameoffset) + " : " + str(d.fileid) + " : " + hex(d.dirtype))
                dirtypenew = d.dirtype + 256
                # print(str(d.nameoffset) + " : " + str(d.fileid) + " : " + hex(dirtypenew))
                manifestdatanew_temp = struct.pack("<LLLLLLL", d.nameoffset, d.itemsize, d.fileid, dirtypenew, d.parentindex, d.nextindex, d.firstindex)
            else:
                # print(str(d.nameoffset) + " : " + str(d.fileid) + " : " + hex(d.dirtype))
                manifestdatanew_temp = struct.pack("<LLLLLLL", d.nameoffset, d.itemsize, d.fileid, d.dirtype, d.parentindex, d.nextindex, d.firstindex)

            manifestdatanew += manifestdatanew_temp

        manifestdatanew += self.manifestdata[len(manifestdatanew):len(self.manifestdata)]
        # print(len(self.manifestdata[0:56]))
        # print(len(self.manifestdata[56:len(self.manifestdata)]))
        # print(len(self.manifestdata))
        # print(len(manifestdatanew))
        g = open(filename + "enc.manifest", "wb")
        g.write(manifestdatanew)
        g.close()


class ManifestNode(object):
    pass


class Manifest2(object):
    def __init__(self, *args):
        if len(args) == 2:
            appId, appVersion = args
            with open(self.filename(appId, appVersion), "rb") as f:
                self.manifestData = f.read()
        else:
            self.manifestData = args[0]

        mdata = ByteBuffer(self.manifestData)

        (self.headerVersion,
         self.appId,
         self.appVersion,
         self.nodeCount,
         self.fileCount,
         self.compressionBlockSize,
         self.binarySize,
         self.nameSize,
         self.hashTableKeyCount,
         self.numOfMinimumFootprintFiles,
         self.numOfUserConfigFiles,
         self.bitmask,
         self.fingerprint,
         self.checksum) = struct.unpack("<LLLLLLLLLLLLLL", mdata.read(56))

        nameTableStart = 56 + self.nodeCount * 28

        self.nodes = {}
        for i in range(self.nodeCount):
            mdata.load(0)
            d = ManifestNode()
            (d.nameOffset,
             d.countOrSize,
             d.fileId,
             d.attributes,
             d.parentIndex,
             d.nextIndex,
             d.childIndex) = struct.unpack("<LLLLLLL", mdata.read(28))
            mdata.load(1)
            mdata.seekAbsolute(nameTableStart + d.nameOffset)
            d.filename = mdata.readDelim(b"\x00", True)
            self.nodes[i] = d

        for i in self.nodes.keys():
            d = self.nodes[i]
            fullFilename = d.filename
            while d.parentIndex != 0xffffffff:
                d = self.nodes[d.parentIndex]
                fullFilename = d.filename + b"/" + fullFilename

            if len(fullFilename) and fullFilename[0] == b"/":
                fullFilename = fullFilename[1:]  # remove leading slash

            d = self.nodes[i]
            d.fullFilename = fullFilename

    @classmethod
    def filename(cls, appId, appVersion):
        if os.path.isfile("files/cache/" + str(appId) + "_" + str(appVersion) + "/" + str(appId) + "_" + str(appVersion) + ".manifest"):
            return os.path.join("files/cache/" + str(appId) + "_" + str(appVersion) + "/", ("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["manifestdir"] + str(appId) + "_" + str(appVersion) + ".v4.manifest"):
            return os.path.join(config["manifestdir"], ("%i_%i.v4.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["v4manifestdir"] + str(appId) + "_" + str(appVersion) + ".manifest"):
            return os.path.join(config["v4manifestdir"], ("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["manifestdir"] + str(appId) + "_" + str(appVersion) + ".v2.manifest"):
            return os.path.join(config["manifestdir"], ("%i_%i.v2.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["v2manifestdir"] + str(appId) + "_" + str(appVersion) + ".manifest"):
            return os.path.join(config["v2manifestdir"], ("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["manifestdir"] + str(appId) + "_" + str(appVersion) + ".v3e.manifest"):
            return os.path.join(config["manifestdir"], ("%i_%i.v3e.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["manifestdir"] + str(appId) + "_" + str(appVersion) + ".v3.manifest"):
            return os.path.join(config["manifestdir"], ("%i_%i.v3.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["manifestdir"] + str(appId) + "_" + str(appVersion) + ".manifest"):
            return os.path.join(config["manifestdir"], ("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isdir(config["v3manifestdir2"]):
            if os.path.isfile(config["v3manifestdir2"] + str(appId) + "_" + str(appVersion) + ".manifest"):
                return os.path.join(config["v3manifestdir2"], ("%i_%i.manifest" % (appId, appVersion)))
            else:
                logging.error("Manifest not found for %s %s " % (appId, appVersion))
        else:
            logging.error("Manifest not found for %s %s " % (appId, appVersion))


class SDKManifest(object):
    def __init__(self, *args):
        if len(args) == 2:
            appId, appVersion = args
            # Find the corresponding blob file
            blob_filename = steam2_sdk_utils.find_blob_file(appId, appVersion)
            if not blob_filename:
                logging.warning("Blob file not found for appId: %s, appVersion: %s" % (appId, appVersion))
                return None
            with open(blob_filename, "rb") as f:
                blob_data = f.read()
        else:
            # Assume raw data is passed
            blob_data = args[0]

        # Now parse the blob data
        b = SDKBlob(blob_data)

        # Extract the manifest data
        self.manifestData = b.get_raw(3, 0)

        # Now proceed to parse the manifest data as per existing 'Manifest2' class
        mdata = ByteBuffer(self.manifestData)

        (self.headerVersion,
         self.appId,
         self.appVersion,
         self.nodeCount,
         self.fileCount,
         self.compressionBlockSize,
         self.binarySize,
         self.nameSize,
         self.hashTableKeyCount,
         self.numOfMinimumFootprintFiles,
         self.numOfUserConfigFiles,
         self.bitmask,
         self.fingerprint,
         self.checksum) = struct.unpack("<LLLLLLLLLLLLLL", mdata.read(56))

        nameTableStart = 56 + self.nodeCount * 28

        self.nodes = {}
        for i in range(self.nodeCount):
            mdata.load(0)
            d = ManifestNode()
            (d.nameOffset,
             d.countOrSize,
             d.fileId,
             d.attributes,
             d.parentIndex,
             d.nextIndex,
             d.childIndex) = struct.unpack("<LLLLLLL", mdata.read(28))
            mdata.load(1)
            mdata.seekAbsolute(nameTableStart + d.nameOffset)
            d.filename = mdata.readDelim(b"\x00", True)
            self.nodes[i] = d

        for i in self.nodes.keys():
            d = self.nodes[i]
            fullFilename = d.filename
            while d.parentIndex != 0xffffffff:
                d = self.nodes[d.parentIndex]
                fullFilename = d.filename + b"/" + fullFilename

            if len(fullFilename) and fullFilename[0:1] == b"/":
                fullFilename = fullFilename[1:]  # remove leading slash

            d = self.nodes[i]
            d.fullFilename = fullFilename

    def find_blob_file(self, appId, appVersion):
        # Implement code to find the blob file for given appId and appVersion
        # Perhaps the blob files are stored in a directory named 'blobs'
        blob_dir = config['steam2sdkdir'] # Replace with the actual path to your blob files
        for filename in os.listdir(blob_dir):
            if filename.endswith(".blob"):
                parts = filename.split(".")[0].split("_")
                if len(parts) >= 2:
                    file_appId = int(parts[0])
                    file_appVersion = int(parts[1])
                    if file_appId == appId and file_appVersion == appVersion:
                        return os.path.join(blob_dir, filename)
        return None

    def __repr__(self):
        return (f"<SDKManifest appId={self.appId}, appVersion={self.appVersion}, "
                f"nodeCount={self.nodeCount}, fileCount={self.fileCount}>")