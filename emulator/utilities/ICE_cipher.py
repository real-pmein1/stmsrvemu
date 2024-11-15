from builtins import bytes, object, range

__author__ = 'RenardDev//chatGPT'
__url__ = 'https://github.com/RenardDev/CryptICE'
__version__ = '2.1'

__all__ = ['IceKey']


class IceKey(object):
    '''
    Modulo values for the S-boxes
    '''
    __SMOD = (
        ( 333, 313, 505, 369 ),
        ( 379, 375, 319, 391 ),
        ( 361, 445, 451, 397 ),
        ( 397, 425, 395, 505 )
    )
    
    '''
    XOR values for the S-boxes
    '''
    __SXOR = (
        ( 0x83, 0x85, 0x9B, 0xCD ),
        ( 0xCC, 0xA7, 0xAD, 0x41 ),
        ( 0x4B, 0x2E, 0xD4, 0x33 ),
        ( 0xEA, 0xCB, 0x2E, 0x04 )
    )

    '''
    Expanded permutation values for the P-box
    '''
    __PBOX = (
        0x00000001, 0x00000080, 0x00000400, 0x00002000,
        0x00080000, 0x00200000, 0x01000000, 0x40000000,
        0x00000008, 0x00000020, 0x00000100, 0x00004000,
        0x00010000, 0x00800000, 0x04000000, 0x20000000,
        0x00000004, 0x00000010, 0x00000200, 0x00008000,
        0x00020000, 0x00400000, 0x08000000, 0x10000000,
        0x00000002, 0x00000040, 0x00000800, 0x00001000,
        0x00040000, 0x00100000, 0x02000000, 0x80000000
    )

    '''
    The key rotation schedule
    '''
    __KEYROT = (
        0, 1, 2, 3, 2, 1, 3, 0,
        1, 3, 2, 0, 3, 1, 0, 2
    )
    
    __KEY_SCHEDULE = dict()
    __SBOX = dict()
    __bIsInitializedSBOX = False
    __nSIZE = 0
    __nROUNDS = 0

    def __GenerateArray(self, size, value = 0):
        data = list()
        for _ in range(size):
            data.append(type(value)(value))
        return data

    '''
    Galois Field multiplication of a by b, modulo m.
    Just like arithmetic multiplication, except that additions and subtractions are replaced by XOR.
    '''

    def _gf_mult(self, a, b, m):
        result = 0
        while b:
            if b & 1:
                result ^= a
            a <<= 1
            b >>= 1
            if a >= 256:
                a ^= m
        return result

    '''
    Galois Field exponentiation.
    Raise the base to the power of 7, modulo m.
    '''

    def _gf_exp7(self, b, m):
        if b == 0:
            return 0
        x = self._gf_mult(b, b, m)
        x = self._gf_mult(b, x, m)
        x = self._gf_mult(x, x, m)
        return self._gf_mult(b, x, m)

    '''
    Carry out the ICE 32-bit P-box permutation.
    '''

    def _perm32(self, x):
        result = 0
        i = 0
        while x:
            if x & 1:
                result |= self.__PBOX[i]
            i += 1
            x >>= 1
        return result

    '''
    Create a new ICE object.
    '''

    def __init__(self, n, key):
        if self.__bIsInitializedSBOX != True:
            self.__SBOX.clear()
            for i in range(0, 4):
                self.__SBOX[i] = dict()
                for l in range(0, 1024):
                    self.__SBOX[i][l] = 0
            for i in range(0, 1024):
                col = (i >> 1) & 0xFF
                row = (i & 0x1) | ((i & 0x200) >> 8)
                self.__SBOX[0][i] = self._perm32(self._gf_exp7(col ^ self.__SXOR[0][row], self.__SMOD[0][row]) << 24)
                self.__SBOX[1][i] = self._perm32(self._gf_exp7(col ^ self.__SXOR[1][row], self.__SMOD[1][row]) << 16)
                self.__SBOX[2][i] = self._perm32(self._gf_exp7(col ^ self.__SXOR[2][row], self.__SMOD[2][row]) << 8)
                self.__SBOX[3][i] = self._perm32(self._gf_exp7(col ^ self.__SXOR[3][row], self.__SMOD[3][row]))
            self.__bIsInitializedSBOX = True
        if n < 1:
            self.__nSIZE = 1
            self.__nROUNDS = 8
        else:
            self.__nSIZE = n
            self.__nROUNDS = n * 16
        for i in range(0, self.__nROUNDS):
            self.__KEY_SCHEDULE[i] = dict()
            for j in range(0, 3):
                self.__KEY_SCHEDULE[i][j] = 0
        if self.__nROUNDS == 8:
            kb = self.__GenerateArray(4)
            for i in range(0, 4):
                t = i * 2
                kb[3 - i] = (key[t] << 8) | key[t + 1]
            for i in range(0, 8):
                kr = self.__KEYROT[i]
                isk = self.__KEY_SCHEDULE[i]
                for j in range(0, 15):
                    for k in range(0, 4):
                        t = (kr + k) & 3
                        kbb = kb[t]
                        bit = kbb & 1
                        isk[j % 3] = (isk[j % 3] << 1) | bit
                        kb[t] = (kbb >> 1) | ((bit ^ 1) << 15)
        else:
            for i in range(0, self.__nSIZE):
                kb = self.__GenerateArray(4)
                for j in range(0, 4):
                    t = i * 8 + j * 2
                    kb[3 - j] = (key[t] << 8) | key[t + 1]
                for l in range(0, 8):
                    kr = self.__KEYROT[l]
                    t = i * 8 + l
                    for m in range(3):
                        self.__KEY_SCHEDULE[t][m] = 0
                    isk = self.__KEY_SCHEDULE[t]
                    for j in range(0, 15):
                        for k in range(0, 4):
                            t = (kr + k) & 3
                            kbb = kb[t]
                            bit = kbb & 1
                            isk[j % 3] = (isk[j % 3] << 1) | bit
                            kb[t] = (kbb >> 1) | ((bit ^ 1) << 15)
                for l in range(0, 8):
                    kr = self.__KEYROT[8 + l]
                    t = self.__nROUNDS - 8 - i * 8 + l
                    for m in range(3):
                        self.__KEY_SCHEDULE[t][m] = 0
                    isk = self.__KEY_SCHEDULE[t]
                    for j in range(0, 15):
                        for k in range(0, 4):
                            t = (kr + k) & 3
                            kbb = kb[t]
                            bit = kbb & 1
                            isk[j % 3] = (isk[j % 3] << 1) | bit
                            kb[t] = (kbb >> 1) | ((bit ^ 1) << 15)

    '''
    The single round ICE f function.
    '''

    def _ice_f(self, p, sk):
        tl = ((p >> 16) & 0x3FF) | (((p >> 14) | (p << 18)) & 0xFFC00)
        tr = (p & 0x3FF) | ((p << 2) & 0xFFC00)
        al = sk[2] & (tl ^ tr)
        ar = al ^ tr ^ sk[1]
        al ^= tl ^ sk[0]
        return self.__SBOX[0][al >> 10] | self.__SBOX[1][al & 0x3FF] | self.__SBOX[2][ar >> 10] | self.__SBOX[3][ar & 0x3FF]

    '''
    Return the key size, in bytes.
    '''

    def KeySize(self):
        return int(self.__nSIZE) * 8

    '''
    Return the block size, in bytes.
    '''

    def BlockSize(self):
        return 8

    '''
    Encrypt a block of 8 bytes of data with the given ICE key.
    '''

    def EncryptBlock(self, data):
        out = self.__GenerateArray(8)
        l = 0
        r = 0
        for i in range(0, 4):
            t = 24 - i * 8
            l |= (ord(data[i]) & 0xFF) << t
            r |= (ord(data[i + 4]) & 0xFF) << t
        for i in range(0, self.__nROUNDS, 2):
            l ^= self._ice_f(r, self.__KEY_SCHEDULE[i])
            r ^= self._ice_f(l, self.__KEY_SCHEDULE[i + 1])
        for i in range(0, 4):
            out[3 - i] = r & 0xFF
            out[7 - i] = l & 0xFF
            r >>= 8
            l >>= 8
        return out

    '''
    Decrypt a block of 8 bytes of data with the given ICE key.
    '''

    def DecryptBlock(self, data):
        l = 0
        r = 0
        for i in range(0, 4):
            t = 24 - i * 8
            l |= (ord(data[i]) & 0xFF) << t
            r |= (ord(data[i + 4]) & 0xFF) << t
        for i in range(self.__nROUNDS - 1, 0, -2):
            l ^= self._ice_f(r, self.__KEY_SCHEDULE[i])
            r ^= self._ice_f(l, self.__KEY_SCHEDULE[i - 1])
        out = self.__GenerateArray(8)
        for i in range(0, 4):
            out[3 - i] = r & 0xFF
            out[7 - i] = l & 0xFF
            r >>= 8
            l >>= 8
        return out

    '''
    Encrypt the data byte array with the given ICE key.
    '''

    def Encrypt(self, data):
        out = bytearray()
        blocksize = self.BlockSize()
        datalen = len(data)
        bytesleft = datalen
        i = 0
        while bytesleft >= blocksize:
            out.extend(self.EncryptBlock(data[i:i + blocksize]))
            bytesleft -= blocksize
            i += blocksize
        if bytesleft > 0:
            out.extend(data[datalen - bytesleft:datalen])
        return bytes(out)

    '''
    Decrypt the data byte array with the given ICE key.
    '''

    def Decrypt(self, data):
        out = bytearray()
        blocksize = self.BlockSize()
        datalen = len(data)
        bytesleft = datalen
        i = 0
        while bytesleft >= blocksize:
            out.extend(self.DecryptBlock(data[i:i + blocksize]))
            bytesleft -= blocksize
            i += blocksize
        if bytesleft > 0:
            out.extend(data[datalen - bytesleft:datalen])
        return bytes(out)