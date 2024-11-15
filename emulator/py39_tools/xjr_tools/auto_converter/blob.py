import io, struct, zlib

class Blob:
    def __init__(self, binblob):
        self.origblob = binblob
        self.kv = {}
        self.cached = {}
        
        if binblob[0:2] == b"\x01\x43":
            packedsize, dunno1, unpackedsize, dunno2, compressionlevel = struct.unpack("<IIIIH", binblob[2:20])
            
            if compressionlevel != 9:
                raise Exception("Unknown compression level!")
                
            if len(binblob) != packedsize:
                raise Exception("Wrong packed size!",  len(binblob), packedsize)
                
            if dunno1 != 0 or dunno2 != 0:
                raise Exception("dunnos not zero", hex(dunno1), hex(dunno2))
                
            binblob = zlib.decompress(binblob[20:])
            
            if len(binblob) != unpackedsize:
                raise Exception("Wrong unpacked size!", len(binblob), unpackedsize)
                
        bio = io.BytesIO(binblob)

        magic = bio.read(2)
        if magic != b"\x01\x50":
            raise Exception("Wrong blob magic", magic)
        
        totalsize, slacksize = struct.unpack("<II", bio.read(8))
        
        if len(binblob) != totalsize + slacksize:
            raise Exception("Wrong bloblen!", len(binblob), totalsize + slacksize)
            
        while bio.tell() < totalsize:
            keysize, valuesize = struct.unpack("<HI", bio.read(6))
            key = bio.read(keysize)
            value = bio.read(valuesize)
            if key in self.kv:
                raise Exception("duplicate key!", key)
                
            self.kv[key] = value
            
        self.slackdata = bio.read(slacksize)
        
        if self.slackdata != b"\x00" * slacksize:
            raise Exception("Non-zero slack!")
            
        tail = bio.read()
        
        if len(tail) != 0:
            raise Exception("Nonzero size at the end!", tail)
            
            
    def _get(self, as_blob, *path):
        if len(path) == 0:
            raise Exception("Empty path!")
            
        key = path[0]
        if type(key) is int:
            key = struct.pack("<I", key)
                
        if as_blob or len(path) >= 2:
            if key not in self.cached:
                b = Blob(self.kv[key])
                self.cached[key] = b
        
        if len(path) == 1:
            if as_blob:
                return self.cached[key]
                
            else:
                return self.kv[key]
            
        else:
            return self.cached[key]._get(as_blob, *path[1:])
            
    
    def _iterate(self, key_ints=False, as_blob=False):
        keys = self.kv.keys()
        if key_ints:
            keys = [(struct.unpack("<I", key)[0], key) for key in keys]
            keys.sort()
        else:
            keys = [(key, key) for key in keys]
            
        for outkey, key in keys:
            if as_blob:
                if key not in self.cached:
                    b = Blob(self.kv[key])
                    self.cached[key] = b
                    
                yield outkey, self.cached[key]
                
            else:
                yield outkey, self.kv[key]
        
    def get_blob(self, *path):
        return self._get(True, *path)
        
    
    def get_i32(self, *path):
        return struct.unpack("<I", self._get(False, *path))[0]

    
    def get_i64(self, *path):
        return struct.unpack("<Q", self._get(False, *path))[0]
        
    
    def get_raw(self, *path):
        return self._get(False, *path)
        
        
    def get_str(self, *path):
        s = self._get(False, *path)
        if s[-1] == 0:
            s = s[:-1]
            
        return s
        
    
    def iterate_blobs(self, key_ints=False):
        for key, value in self._iterate(key_ints, True):
            yield key, value


    def iterate_str(self, key_ints=False):
        for key, s in self._iterate(key_ints, False):
            if s[-1] == 0:
                s = s[:-1]
        
            yield key, s
            