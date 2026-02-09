
__author__ = 'RenardDev'
__url__ = 'https://github.com/RenardDev/CryptICE'
__version__ = '2.0'

__all__ = [
	'IceKey'
]

class RLIST(list):
	'''RestrictLIST'''
	def __setattr__(self, name, value):
		raise AttributeError('AttributeError: \'{}\' object has no attribute \'{}\''.format(type(self), name))
	def __setitem__(self, name, value):
		raise TypeError('TypeError: \'{}\' object does not support item assignment'.format(type(self)))

class RINT(int):
	'''RestrictINT'''
	_MAXVALUE = 2 ** 32
	def __new__(cls, value:int=0):
		return int.__new__(cls, value % cls._MAXVALUE)
	def __add__(self, *args, **kwargs):
		return self.__new__(type(self), int.__add__(self, *args, **kwargs))
	def __radd__(self, *args, **kwargs):
		return self.__new__(type(self), int.__radd__(self, *args, **kwargs))
	def __sub__(self, *args, **kwargs):
		return self.__new__(type(self), int.__sub__(self, *args, **kwargs))
	def __rsub__(self,*args, **kwargs):
		return self.__new__(type(self), int.__rsub__(self, *args, **kwargs))
	def __mul__(self, *args, **kwargs):
		return self.__new__(type(self), int.__mul__(self, *args, **kwargs))
	def __rmul__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rmul__(self, *args, **kwargs))
	def __div__(self, *args, **kwargs):
		return self.__new__(type(self), int.__floordiv__(self, *args, **kwargs))
	def __rdiv__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rfloordiv__(self, *args, **kwargs))
	def __truediv__(self, *args, **kwargs):
		return self.__new__(type(self), int.__floordiv__(self, *args, **kwargs))
	def __rtruediv__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rfloordiv__(self, *args, **kwargs))
	def __pow__(self, *args, **kwargs):
		return self.__new__(type(self), int.__pow__(self, *args, **kwargs))
	def __rpow__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rpow__(self, *args, **kwargs))
	def __lshift__(self, *args, **kwargs):
		return self.__new__(type(self), int.__lshift__(self, *args, **kwargs))
	def __rlshift__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rlshift__(self, *args, **kwargs))
	def __rshift__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rshift__(self, *args, **kwargs))
	def __rrshift__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rrshift__(self, *args, **kwargs))
	def __and__(self, *args, **kwargs):
		return self.__new__(type(self), int.__and__(self, *args, **kwargs))
	def __rand__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rand__(self, *args, **kwargs))
	def __or__(self, *args, **kwargs):
		return self.__new__(type(self), int.__ror__(self, *args, **kwargs))
	def __ror__(self, *args, **kwargs):
		return self.__new__(type(self), int.__ror__(self, *args, **kwargs))
	def __xor__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rxor__(self, *args, **kwargs))
	def __rxor__(self, *args, **kwargs):
		return self.__new__(type(self), int.__rxor__(self, *args, **kwargs))

class IceKey(object):
	# Modulo values for the S-boxes
	__rSMOD = RLIST([
		[ RINT(333), RINT(313), RINT(505), RINT(369) ],
		[ RINT(379), RINT(375), RINT(319), RINT(391) ],
		[ RINT(361), RINT(445), RINT(451), RINT(397) ],
		[ RINT(397), RINT(425), RINT(395), RINT(505) ]
	])
	# XOR values for the S-boxes
	__rSXOR = RLIST([
		[ RINT(0x83), RINT(0x85), RINT(0x9B), RINT(0xCD) ],
		[ RINT(0xCC), RINT(0xA7), RINT(0xAD), RINT(0x41) ],
		[ RINT(0x4B), RINT(0x2E), RINT(0xD4), RINT(0x33) ],
		[ RINT(0xEA), RINT(0xCB), RINT(0x2E), RINT(0x04) ]
	])
	# Expanded permutation values for the P-box
	__rPBOX = RLIST([
		RINT(0x00000001), RINT(0x00000080), RINT(0x00000400), RINT(0x00002000),
		RINT(0x00080000), RINT(0x00200000), RINT(0x01000000), RINT(0x40000000),
		RINT(0x00000008), RINT(0x00000020), RINT(0x00000100), RINT(0x00004000),
		RINT(0x00010000), RINT(0x00800000), RINT(0x04000000), RINT(0x20000000),
		RINT(0x00000004), RINT(0x00000010), RINT(0x00000200), RINT(0x00008000),
		RINT(0x00020000), RINT(0x00400000), RINT(0x08000000), RINT(0x10000000),
		RINT(0x00000002), RINT(0x00000040), RINT(0x00000800), RINT(0x00001000),
		RINT(0x00040000), RINT(0x00100000), RINT(0x02000000), RINT(0x80000000)
	])
	# The key rotation schedule
	__rKEYROT = RLIST([
		RINT(0), RINT(1), RINT(2), RINT(3), RINT(2), RINT(1), RINT(3), RINT(0),
		RINT(1), RINT(3), RINT(2), RINT(0), RINT(3), RINT(1), RINT(0), RINT(2)
	])
	__rKEY_SCHEDULE = dict()
	__rSBOX = dict()
	__rSBOX_INITIALISED = False
	__rSIZE = RINT(0)
	__rROUNDS = RINT(0)
	# Helpful functions
	def __GenerateArray(self, size:int, value:int=0) -> list:
		array = list()
		for _ in range(size):
			array.append(value)
		return array
	# Main functions
	'''
	Galois Field multiplication of a by b, modulo m.
	Just like arithmetic multiplication, except that additions and subtractions are replaced by XOR.
	'''
	def _gf_mult(self, a:RINT, b:RINT, m:RINT) -> RINT:
		res = RINT(0)
		while b:
			if b & RINT(1):
				res ^= a
			a <<= RINT(1)
			b >>= RINT(1)
			if a >= RINT(256):
				a ^= m
		return res
	'''
	Galois Field exponentiation.
	Raise the base to the power of 7, modulo m.
	'''
	def _gf_exp7(self, b:RINT, m:RINT) -> RINT:
		if b == RINT(0):
			return RINT(0)
		x = self._gf_mult(b, b, m)
		x = self._gf_mult(b, x, m)
		x = self._gf_mult(x, x, m)
		return self._gf_mult(b, x, m)
	'''
	Carry out the ICE 32-bit P-box permutation.
	'''
	def _perm32(self, x:RINT) -> RINT:
		res = RINT(0)
		i = 0
		while x:
			if x & RINT(1):
				res |= self.__rPBOX[i]
			i += 1
			x >>= RINT(1)
		return res
	'''
	Create a new ICE object.
	'''
	def __init__(self, n:int, key:bytes):
		if self.__rSBOX_INITIALISED != True:
			self.__rSBOX.clear()
			for i in range(0, 4):
				self.__rSBOX[i] = dict()
				for l in range(0, 1024):
					self.__rSBOX[i][l] = RINT(0x00)
			for i in range(0, 1024):
				i = RINT(i)
				col = (i >> RINT(1)) & RINT(0xFF)
				row = (i & RINT(0x1)) | ((i & RINT(0x200)) >> RINT(8))
				self.__rSBOX[0][i] = self._perm32(self._gf_exp7(col ^ self.__rSXOR[0][row], self.__rSMOD[0][row]) << RINT(24))
				self.__rSBOX[1][i] = self._perm32(self._gf_exp7(col ^ self.__rSXOR[1][row], self.__rSMOD[1][row]) << RINT(16))
				self.__rSBOX[2][i] = self._perm32(self._gf_exp7(col ^ self.__rSXOR[2][row], self.__rSMOD[2][row]) << RINT(8))
				self.__rSBOX[3][i] = self._perm32(self._gf_exp7(col ^ self.__rSXOR[3][row], self.__rSMOD[3][row]))
			self.__rSBOX_INITIALISED = True
		if n < 1:
			self.__rSIZE = RINT(1)
			self.__rROUNDS = RINT(8)
		else:
			self.__rSIZE = RINT(n)
			self.__rROUNDS = RINT(n) * RINT(16)
		for i in range(0, self.__rROUNDS):
			self.__rKEY_SCHEDULE[i] = dict()
			for j in range(0, 3):
				self.__rKEY_SCHEDULE[i][j] = RINT(0x00)
		if self.__rROUNDS == 8:
			kb = self.__GenerateArray(4)
			for i in range(0, 4):
				i = RINT(i)
				kb[RINT(3) - i] = (key[i * RINT(2)] << RINT(8)) | key[i * RINT(2) + RINT(1)]
			for i in range(0, 8):
				i = RINT(i)
				kr = self.__rKEYROT[i]
				isk = self.__rKEY_SCHEDULE[i]
				for j in range(0, 15):
					j = RINT(j)
					for k in range(0, 4): 
						k = RINT(k)
						bit = kb[(kr + k) & RINT(3)] & RINT(1)
						isk[j % RINT(3)] = (isk[j % RINT(3)] << RINT(1)) | bit
						kb[(kr + k) & RINT(3)] = (kb[(kr + k) & RINT(3)] >> RINT(1)) | ((bit ^ RINT(1)) << RINT(15))
		else:
			for i in range(0, self.__rSIZE):
				i = RINT(i)
				kb = self.__GenerateArray(4)
				for j in range(0, 4):
					j = RINT(j)
					kb[RINT(3) - j] = (key[i * RINT(8) + j * RINT(2)] << RINT(8)) | key[i * RINT(8) + j * RINT(2) + RINT(1)]
				for l in range(0, 8):
					l = RINT(l)
					kr = self.__rKEYROT[l]
					for m in range(3):
						self.__rKEY_SCHEDULE[((i * RINT(8)) + l)][m] = RINT(0)
					isk = self.__rKEY_SCHEDULE[((i * RINT(8)) + l)]
					for j in range(0, 15):
						j = RINT(j)
						for k in range(0, 4):
							k = RINT(k)
							bit = kb[(kr + k) & RINT(3)] & RINT(1)
							isk[j % RINT(3)] = (isk[j % RINT(3)] << RINT(1)) | bit
							kb[(kr + k) & RINT(3)] = (kb[(kr + k) & RINT(3)] >> RINT(1)) | ((bit ^ RINT(1)) << RINT(15))
				for l in range(0, 8):
					l = RINT(l)
					kr = self.__rKEYROT[RINT(8) + l]
					for m in range(3):
						self.__rKEY_SCHEDULE[((self.__rROUNDS - RINT(8) - i * RINT(8)) + l)][m] = RINT(0)
					isk = self.__rKEY_SCHEDULE[((self.__rROUNDS - RINT(8) - i * RINT(8)) + l)]
					for j in range(0, 15): 
						j = RINT(j)
						for k in range(0, 4):
							k = RINT(k)
							bit = kb[(kr + k) & RINT(3)] & RINT(1)
							isk[j % RINT(3)] = (isk[j % RINT(3)] << RINT(1)) | bit
							kb[(kr + k) & RINT(3)] = (kb[(kr + k) & RINT(3)] >> RINT(1)) | ((bit ^ RINT(1)) << RINT(15))
	'''
	The single round ICE f function.
	'''
	def _ice_f(self, p:RINT, sk:dict) -> int:
		tl = ((p >> RINT(16)) & RINT(0x3FF)) | (((p >> RINT(14)) | (p << RINT(18))) & RINT(0xFFC00))
		tr = (p & RINT(0x3FF)) | ((p << RINT(2)) & RINT(0xFFC00))
		al = sk[2] & (tl ^ tr)
		ar = al ^ tr
		al ^= tl
		al ^= sk[0]
		ar ^= sk[1]
		return self.__rSBOX[0][al >> RINT(10)] | self.__rSBOX[1][al & RINT(0x3FF)] | self.__rSBOX[2][ar >> RINT(10)] | self.__rSBOX[3][ar & RINT(0x3FF)]
	'''
	Return the key size, in bytes.
	'''
	def KeySize(self) -> int:
		return int(self.__rSIZE) * 8
	'''
	Return the block size, in bytes.
	'''
	def BlockSize(self) -> int:
		return 8
	'''
	Encrypt a block of 8 bytes of data with the given ICE key.
	'''
	def EncryptBlock(self, data:list) -> list:
		out = self.__GenerateArray(8)
		l = RINT(0)
		r = RINT(0)
		for i in range(0, 4):
			i = RINT(i)
			l |= (data[i] & RINT(0xFF)) << (RINT(24) - i * RINT(8))
			r |= (data[i + RINT(4)] & RINT(0xFF)) << (RINT(24) - i * RINT(8))
		for i in range(0, self.__rROUNDS, 2):
			i = RINT(i)
			l ^= self._ice_f(r, self.__rKEY_SCHEDULE[i])
			r ^= self._ice_f(l, self.__rKEY_SCHEDULE[i + RINT(1)])
		for i in range(0, 4):
			i = RINT(i)
			out[RINT(3) - i] = r & RINT(0xFF)
			out[RINT(7) - i] = l & RINT(0xFF)
			r >>= RINT(8)
			l >>= RINT(8)
		return out
	'''
	Decrypt a block of 8 bytes of data with the given ICE key.
	'''
	def DecryptBlock(self, data:list) -> list:
		out = self.__GenerateArray(8)
		l = RINT(0)
		r = RINT(0)
		for i in range(0, 4):
			i = RINT(i)
			l |= (data[i] & RINT(0xFF)) << (RINT(24) - i * RINT(8))
			r |= (data[i + 4] & RINT(0xFF)) << (RINT(24) - i * RINT(8))
		for i in range(self.__rROUNDS - 1, 0, -2):
			i = RINT(i)
			l ^= self._ice_f(r, self.__rKEY_SCHEDULE[i])
			r ^= self._ice_f(l, self.__rKEY_SCHEDULE[i - RINT(1)])
		for i in range(0, 4):
			i = RINT(i)
			out[RINT(3) - i] = r & RINT(0xFF)
			out[RINT(7) - i] = l & RINT(0xFF)
			r >>= RINT(8)
			l >>= RINT(8)
		return out
	'''
	Encrypt the data byte array with the given ICE key.
	'''
	def Encrypt(self, data:bytes, cmspadding:bool=False) -> bytes:
		if cmspadding:
			blocksize = self.BlockSize()
			padding_length = blocksize - (len(data) % blocksize)
			data += bytes(self.__GenerateArray(padding_length, padding_length))
		out = bytearray()
		blocksize = self.BlockSize()
		bytesleft = len(data)
		i = 0
		while bytesleft >= blocksize:
			out.extend(self.EncryptBlock(data[i:i + blocksize]))
			bytesleft -= blocksize
			i += blocksize
		if bytesleft > 0:
			out.extend(data[len(data)-bytesleft:len(data)])
		return bytes(out)
	'''
	Decrypt the data byte array with the given ICE key.
	'''
	def Decrypt(self, data:bytes, cmspadding:bool=False) -> bytes:
		out = bytearray()
		blocksize = self.BlockSize()
		bytesleft = len(data)
		i = 0
		while bytesleft >= blocksize:
			out.extend(self.DecryptBlock(data[i:i + blocksize]))
			bytesleft -= blocksize
			i += blocksize
		if bytesleft > 0:
			out.extend(data[len(data)-bytesleft:len(data)])
		if cmspadding:
			out_length = len(out)
			for i in range(1, out[-1] + 1):
				del out[out_length - i]
		return bytes(out)
