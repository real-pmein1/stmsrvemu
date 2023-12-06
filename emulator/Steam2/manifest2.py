import struct, os.path, ConfigParser, logging
from bytebuffer import ByteBuffer
from steamemu.config import read_config

config = read_config()

class ManifestNode:
    pass

class Manifest2 :
    def __init__(self, *args) :
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
            d.filename = mdata.readDelim("\x00", True)
            self.nodes[i] = d

        for i in self.nodes.keys():
            d = self.nodes[i]
            fullFilename = d.filename
            while d.parentIndex != 0xffffffff:
                d = self.nodes[d.parentIndex]
                fullFilename = d.filename + "/" + fullFilename
            
            if len(fullFilename) and fullFilename[0] == "/":
                fullFilename = fullFilename[1:] # remove leading slash
            
            d = self.nodes[i]
            d.fullFilename = fullFilename

    @classmethod
    def filename(cls, appId, appVersion):
        if os.path.isfile("files/cache/" + str(appId) + "_" + str(appVersion) + "/" + str(appId) + "_" + str(appVersion) + ".manifest") :
            return os.path.join("files/cache/" + str(appId) + "_" + str(appVersion) + "/",("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["v2manifestdir"] + str(appId) + "_" + str(appVersion) + ".manifest") :
            return os.path.join(config["v2manifestdir"],("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isfile(config["manifestdir"] + str(appId) + "_" + str(appVersion) + ".manifest") :
            return os.path.join(config["manifestdir"],("%i_%i.manifest" % (appId, appVersion)))
        elif os.path.isdir(config["v3manifestdir2"]) :
            if os.path.isfile(config["v3manifestdir2"] + str(appId) + "_" + str(appVersion) + ".manifest") :
                return os.path.join(config["v3manifestdir2"],("%i_%i.manifest" % (appId, appVersion)))
            else :
                logging.error("Manifest not found for %s %s " % (appId, appVersion))
        else :
            logging.error("Manifest not found for %s %s " % (appId, appVersion))
