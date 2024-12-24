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

    def modify_file(self):
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

        # Replace the zeroed-out signature with the new signature
        self.file_data[signature_offset + 16:signature_offset + 16 + 128] = new_signature

        # Replace the certificate table
        self.file_data[signature_fields_pointer + wipe_offsets[1]:signature_fields_pointer + wipe_offsets[1] + 8] = self.certificate_table

        return bytes(self.file_data)

    def _generate_checksum(self, checksum_offset) -> int:
        """Generate a new PE file checksum."""
        checksum = 0
        size = self.signed_binary_size
        cert_table_va, cert_table_size = struct.unpack_from("<II", self.file_data, 0x90)

        for i in range(0, size, 2):
            if i in range(cert_table_va, cert_table_va + cert_table_size):
                continue
            if 0x40 <= i < 0x44:  # Skip checksum field
                continue
            if i + 1 < len(self.file_data):
                word = int.from_bytes(self.file_data[i:i + 2], 'little')
            else:
                word = self.file_data[i]
            checksum = (checksum + word) & 0xFFFFFFFF

        checksum = (checksum & 0xFFFF) + (checksum >> 16)
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
        return checksum + size

    def remove_certificates_from_bytes(self, data: bytes, table_offset) -> bytes:
        """
        Remove all certificates and reset the Certificate Table in a PE file.
        Takes a byte string as input and returns the modified byte string.
        """
        # Convert the input data to a mutable bytearray
        data_array = bytearray(data)

        # Locate the PE Header
        pe_header_offset = struct.unpack_from("<I", data_array, 0x3C)[0]  # PE Header start
        optional_header_offset = pe_header_offset + 0x18  # Optional Header start
        certificate_table_entry_offset = optional_header_offset + table_offset  # Data Directory (Certificate Table)

        # Read Certificate Table Virtual Address and Size
        cert_table_va, cert_table_size = struct.unpack_from("<II", data_array, certificate_table_entry_offset)

        # If no Certificate Table is present, return the original data
        if cert_table_va == 0 or cert_table_size == 0:
            print("No certificates found.")
            return bytes(data_array)

        print(f"Certificate Table found at offset {cert_table_va}, size {cert_table_size} bytes.")

        # Truncate the file to remove the Certificate Table
        truncated_data = data_array[:cert_table_va]  # Keep everything before the Certificate Table

        # Reset the Certificate Table in the Data Directory
        struct.pack_into("<II", truncated_data, certificate_table_entry_offset, 0, 0)

        # Return the modified byte string
        return bytes(truncated_data)

if __name__ == "__main__":
    input_file = "steamclient.dll"
    output_file = "steamclient.newsig.dll"

    with open(input_file, "rb") as f:
        file_data = f.read()

    modifier = FileSignatureModifier(file_data)
    modified_data = modifier.modify_file()

    with open(output_file, "wb") as f:
        f.write(modified_data)

    print(f"File successfully modified and saved to {output_file}")