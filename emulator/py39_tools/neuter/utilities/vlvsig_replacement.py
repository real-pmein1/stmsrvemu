import struct
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA

from utilities import encryption


class FileSignatureModifier:
    def __init__(self, filedata: bytes):
        self.file_data = bytearray(filedata)  # Mutable copy of the binary file data
        self.signature_version = None
        self.signed_binary_size = None
        self.signature_date = None
        self.file_signature = None
        self.magic_number = None
        self.file_checksum = None
        self.certificate_table = None

    def get_signatures(self):
        # Locate the 'vlv\0' signature
        signature_offset = self.file_data.find(b'VLV\0')
        if signature_offset == -1:
            return bytes(self.file_data)

        # Read and store signature version, signed binary size, and signature date
        self.signature_version = struct.unpack("<I", self.file_data[signature_offset + 4:signature_offset + 8])[0]
        self.signed_binary_size = struct.unpack("<I", self.file_data[signature_offset + 8:signature_offset + 12])[0]
        self.signature_date = self.file_data[signature_offset + 12:signature_offset + 16]

        # Read and store the original file signature
        self.file_signature = self.file_data[signature_offset + 16:signature_offset + 16 + 128]

        # Zero out the file signature
        self.file_data[signature_offset + 16:signature_offset + 16 + 128] = b'\x00' * 128

        # Determine the mode and wipe offsets
        signature_fields_pointer = struct.unpack("<I", self.file_data[0x3C:0x40])[0] + 24
        mode = struct.unpack("<H", self.file_data[signature_fields_pointer:signature_fields_pointer + 2])[0]

        if mode == 0x10b:
            wipe_offsets = (64, 128)
        elif mode == 0x20b:
            wipe_offsets = (64, 144)
        else:
            raise ValueError("Unsupported PE mode")

        # Extract and zero out relevant fields
        self.file_checksum = self.file_data[signature_fields_pointer + wipe_offsets[0]:signature_fields_pointer + wipe_offsets[0] + 4]
        self.file_data[signature_fields_pointer + wipe_offsets[0]:signature_fields_pointer + wipe_offsets[0] + 4] = b'\x00' * 4

        self.certificate_table = self.file_data[signature_fields_pointer + wipe_offsets[1]:signature_fields_pointer + wipe_offsets[1] + 8]
        self.file_data[signature_fields_pointer + wipe_offsets[1]:signature_fields_pointer + wipe_offsets[1] + 8] = b'\x00' * 8

        # Generate a new 128-byte file signature
        new_signature = encryption.generate_dll_signature(self.file_data[:self.signed_binary_size])

        return self.file_signature, new_signature