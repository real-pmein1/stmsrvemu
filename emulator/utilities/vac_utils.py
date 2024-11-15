import struct
import os
import random
from io import BytesIO
import numpy as np

import config

config_var = config.get_config()

class DataBuffer:
    def __init__(self, data):
        if not isinstance(data, bytes):
            raise TypeError("Data must be a bytes object")
        self.data = data
        self.cursor = 0
        self.A = 0
        self.B = 0
        self.C = 0
        self.command = None

    def unpack_header(self):
        self.A = self.unpack_int()
        self.B = self.unpack_byte()
        self.C = self.unpack_byte()


        if self.B != 0x77:
            self.command = self.unpack_string()
        else:
            self.command = b"CheckAccess"

        #self.log.debug(f"unpacked header: A: {self.A}, B: {self.B}, C: {self.C}, command: {self.command}")

    def unpack_int(self):
        try:
            value = struct.unpack_from('<i', self.data, self.cursor)[0]
            self.cursor += 4
            return value
        except struct.error:
            raise ValueError("Insufficient data for unpacking an int")

    def unpack_uint(self):
        try:
            value = struct.unpack_from('<I', self.data, self.cursor)[0]
            self.cursor += 4
            return value
        except struct.error:
            raise ValueError("Insufficient data for unpacking an unsigned int")

    def unpack_short(self):
        try:
            value = struct.unpack_from('<H', self.data, self.cursor)[0]
            self.cursor += 2
            return value
        except struct.error:
            raise ValueError("Insufficient data for unpacking a short")

    def unpack_byte(self):
        try:
            value = struct.unpack_from('B', self.data, self.cursor)[0]
            self.cursor += 1
            return value
        except struct.error:
            raise ValueError("Insufficient data for unpacking a byte")

    def unpack_bytes(self, length):
        if self.cursor + length > len(self.data):
            raise ValueError("Insufficient data for unpacking bytes")
        value = struct.unpack_from(f'{length}s', self.data, self.cursor)[0]
        self.cursor += length
        return value

    def unpack_string(self):
        end = self.data.find(b'\x00', self.cursor)
        if end == -1:
            raise ValueError("Null terminator not found in string data")
        string_data = self.data[self.cursor:end]
        self.cursor = end + 1
        return string_data.decode('latin-1')


class Module:
    Id = 305419896  # Equivalent to 0x12345678 in hex
    pattern = [5, 97, 122, 237, 27, 202, 13, 155, 74, 241, 100, 199, 181, 142, 223, 160]

    pattern2 = [32, 7, 19, 97, 3, 69, 23, 114, 10, 45, 72, 12, 74, 18, 169, 181]

    def __init__(self, filename=None, data_input_stream=None):
        self.Name = ''
        self.Size = 0
        self.Header = None
        self.Data = None

        if filename:
            # Get the directory where server.py is located
            script_dir = os.path.abspath(config_var['vacmoduledir'])
            # Construct the absolute path to the file
            file_path = os.path.join(script_dir, filename)
            # Normalize the path
            file_path = os.path.normpath(file_path)
            # Output the file path for debugging
            print(f"Attempting to open file: {file_path}")
            # Check if the file exists
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            with open(file_path, 'rb') as f:
                self.Name = filename  # Store the filename
                self.read(f)
        else:
            raise ValueError("Filename must be provided")

    def read(self, file):

        def read_utf(file_stream):
            length = struct.unpack('>H', file_stream.read(2))[0]
            return file_stream.read(length).decode('utf-8')

        def read_int(file_stream):
            return struct.unpack('>i', file_stream.read(4))[0]

        self.Name = read_utf(file)
        i = read_int(file)
        self.Header = file.read(i)
        i = read_int(file)
        data_bytes = file.read(i)
        # Create a writable NumPy array
        self.Data = np.frombuffer(data_bytes, dtype=np.uint8).copy()
        self.Size = i

        # Correctly call the encode method on self.Data
        self.encode(self.Data, self.Id)

    def write(self):
        # Ensure the directory exists
        directory = os.path.dirname(self.Name)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(self.Name, 'wb') as f:
            self.write_to_stream(f)

    def write_to_stream(self, file):
        # Write the Data to the file
        file.write(self.Data)

    @staticmethod
    def decode(data, module_id):
        for i in range(0, len(data), 1024):
            chunk_size = min(1024, len(data) - i)
            Module.decode_chunk(data, module_id, i, chunk_size)

    @staticmethod
    def encode(data, module_id):
        for i in range(0, len(data), 1024):
            chunk_size = min(1024, len(data) - i)
            Module.encode_chunk(data, module_id, i, chunk_size)

    @staticmethod
    def encode_chunk(data, module_id, offset, length):
        i = module_id ^ 0xFFFFFFFF
        b = 0
        pattern = Module.pattern
        for j in range(offset, offset + length, 4):
            if j + 3 >= len(data):
                break

            data[j] ^= i & 0xFF
            data[j + 1] ^= (i >> 8) & 0xFF
            data[j + 2] ^= (i >> 16) & 0xFF
            data[j + 3] ^= (i >> 24) & 0xFF

            b1 = data[j]
            b2 = data[j + 1]
            b3 = data[j + 2]
            b4 = data[j + 3]

            data[j], data[j + 1], data[j + 2], data[j + 3] = b4, b3, b2, b1

            data[j] ^= (pattern[(b + 0) & 0xF] | 0xA5) & 0xFF
            data[j + 1] ^= (pattern[(b + 1) & 0xF] | 0xA7) & 0xFF
            data[j + 2] ^= (pattern[(b + 2) & 0xF] | 0xAD) & 0xFF
            data[j + 3] ^= (pattern[(b + 3) & 0xF] | 0xBF) & 0xFF

            data[j] ^= module_id & 0xFF
            data[j + 1] ^= (module_id >> 8) & 0xFF
            data[j + 2] ^= (module_id >> 16) & 0xFF
            data[j + 3] ^= (module_id >> 24) & 0xFF

            b += 1

    @staticmethod
    def decode_chunk(data, module_id, offset, length):
        i = module_id ^ 0xFFFFFFFF
        b = 0
        pattern = Module.pattern
        for j in range(offset, offset + length, 4):
            if j + 3 >= len(data):
                break

            # Java bytes are signed (-128 to 127), so we need to handle negative values
            data[j] = (data[j] ^ (module_id & 0xFF)) & 0xFF
            data[j + 1] = (data[j + 1] ^ ((module_id >> 8) & 0xFF)) & 0xFF
            data[j + 2] = (data[j + 2] ^ ((module_id >> 16) & 0xFF)) & 0xFF
            data[j + 3] = (data[j + 3] ^ ((module_id >> 24) & 0xFF)) & 0xFF

            b1 = data[j]
            b2 = data[j + 1]
            b3 = data[j + 2]
            b4 = data[j + 3]

            data[j], data[j + 1], data[j + 2], data[j + 3] = b4, b3, b2, b1

            data[j] = (data[j] ^ ((pattern[(b + 0) & 0xF] | 0xA5) & 0xFF)) & 0xFF
            data[j + 1] = (data[j + 1] ^ ((pattern[(b + 1) & 0xF] | 0xA7) & 0xFF)) & 0xFF
            data[j + 2] = (data[j + 2] ^ ((pattern[(b + 2) & 0xF] | 0xAD) & 0xFF)) & 0xFF
            data[j + 3] = (data[j + 3] ^ ((pattern[(b + 3) & 0xF] | 0xBF) & 0xFF)) & 0xFF

            data[j] = (data[j] ^ (i & 0xFF)) & 0xFF
            data[j + 1] = (data[j + 1] ^ ((i >> 8) & 0xFF)) & 0xFF
            data[j + 2] = (data[j + 2] ^ ((i >> 16) & 0xFF)) & 0xFF
            data[j + 3] = (data[j + 3] ^ ((i >> 24) & 0xFF)) & 0xFF

            b += 1

    def compareHeader(self, other_module):
        if not other_module.Header or not self.Header:
            return False
        if len(self.Header) != len(other_module.Header) or len(self.Header) < 20:
            return False
        return self.Header[:20] == other_module.Header[:20]


# Base request class
class Req:
    def __init__(self, data):
        self.A = 0
        self.B = 0
        self.C = 0
        self.Cmd = ''
        self.legal = False
        self.data_buffer = DataBuffer(data)
        # Do not call self.read() here

    def read(self):
        self.A = self.data_buffer.unpack_int()
        self.B = self.data_buffer.unpack_byte()
        self.C = self.data_buffer.unpack_byte()
        if self.B != 0x77:
            self.Cmd = self.data_buffer.unpack_string()
        else:
            self.Cmd = 'CheckAccess'
        self.legal = True

    def print(self):
        print(f"A = {self.A}")
        print(f"B = {self.B}")
        print(f"C = {self.C}")
        print(f"Cmd = {self.Cmd}")


class ReqAccept(Req):
    def __init__(self, data):
        super().__init__(data)
        self.Id = 0
        self.read()

    def read(self):
        super().read()
        if self.Cmd == 'ACCEPT':
            self.Id = self.data_buffer.unpack_int()
        else:
            self.legal = False

    def print(self):
        super().print()
        print(f"Id = {hex(self.Id)}")


class ReqBlock(Req):
    def __init__(self, data):
        super().__init__(data)
        self.Size = 0
        self.Data = None
        self.read()

    def read(self):
        super().read()
        if self.Cmd == 'BLOCK':
            self.Size = self.data_buffer.unpack_short()
            self.Data = self.data_buffer.unpack_bytes(self.Size)
        else:
            self.legal = False

    def print(self):
        super().print()
        print(f"Size = {self.Size}")


class ReqCheckAccess(Req):
    def __init__(self, data):
        super().__init__(data)
        self.Id = 0
        self.read()

    def read(self):
        self.A = self.data_buffer.unpack_int()
        self.B = self.data_buffer.unpack_byte()
        self.C = self.data_buffer.unpack_byte()
        self.legal = self.A == 0xFFFFFFFF and self.B == 0x4D and self.C == 0x00  # -1, 77, 0
        self.Id = self.data_buffer.unpack_int()

    def print(self):
        super().print()
        print(f"Id = {hex(self.Id)}")


class ReqFile(Req):
    def __init__(self, data):
        super().__init__(data)
        self.Size = 0
        self.Header = None
        self.read()

    def read(self):
        super().read()
        if self.Cmd == 'FILE':
            self.Size = self.data_buffer.unpack_int()
            self.Header = self.data_buffer.unpack_bytes(34)
        else:
            self.legal = False

    def print(self):
        super().print()
        print(f"Size = {self.Size} {hex(self.Size)}")
        print(f"Header size = {len(self.Header)}")
        self.PrintArr(self.Header, len(self.Header))

    @staticmethod
    def PrintArr(arr, length):
        for b in arr[:length]:
            if 32 <= b <= 122:
                print(f"'{chr(b)}' ", end='')
            else:
                print(f"{hex(b)} ", end='')
        print()


class ReqGet(Req):
    def __init__(self, data):
        super().__init__(data)
        self.Id = 0
        self.FileName = ''
        self.D = 0
        self.TestDir = ''
        self.Random = [0, 0, 0]
        self.read()

    def read(self):
        super().read()
        if self.Cmd == 'GET':
            self.Id = self.data_buffer.unpack_int()
            self.FileName = self.data_buffer.unpack_string()
            self.D = self.data_buffer.unpack_int()
            self.TestDir = self.data_buffer.unpack_string()
            i = 0
            try:
                for i in range(3):
                    self.Random[i] = self.data_buffer.unpack_int()
            except ValueError:
                print(f"Warning: read {i} randoms from 3")
        else:
            self.legal = False

    def print(self):
        super().print()
        print(f"Id = {self.Id}")
        print(f"FileName = {self.FileName}")
        print(f"D = {self.D}")
        print(f"TestDir = {self.TestDir}")
        print(f"Random1 = {self.Random[0]}")
        print(f"Random2 = {self.Random[1]}")
        print(f"Random3 = {self.Random[2]}")


class ReqNext(Req):
    def __init__(self, data):
        super().__init__(data)
        self.Pos = 0
        self.read()

    def read(self):
        super().read()
        if self.Cmd == 'NEXT':
            self.Pos = self.data_buffer.unpack_int()
        else:
            self.legal = False

    def print(self):
        super().print()
        print(f"Pos = {self.Pos}")