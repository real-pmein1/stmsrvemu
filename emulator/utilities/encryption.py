import binascii
import hashlib
import hmac
import io
import struct
import sys
import os
import warnings

from itertools import cycle
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import scrypt
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from config import read_config as get_config

config = get_config()

BS = 16
pad = lambda s: s + (BS - len(s) % BS) * struct.pack('B', BS - len(s) % BS)

def check_file_hashes():
    """
    Check the presence and hash of two RSA key files based on the configuration.
    Returns:
        bool: True or False based on the logic described.
    """
    # File paths
    file_paths = {
        "main_key": "files/configs/main_key_1024.der",
        "network_key": "files/configs/network_key_512.der"
    }

    # Known hash byte strings
    known_hashes = {
        "main_key": bytes.fromhex("bd3ea0f03ef40047fab588ce14f15ed77916277194196674b4a0d90da4c79951"),
        "network_key": bytes.fromhex("b77dd5f52fefc2bd0511bbb0e88b7b7b310cf4253f4dabd0d493423ccdce0d2c")
    }

    # Hashing algorithm
    algorithm = "sha256"

    # Helper function to compute file hash
    def compute_hash(filepath, algorithm):
        hash_func = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):  # Read file in chunks
                hash_func.update(chunk)
        return hash_func.digest()

    # If use_random_keys is True
    if config['use_random_keys'].lower() == "true":
        # Check if both key files exist
        if all(os.path.exists(path) for path in file_paths.values()):
            # Compute hashes and compare with known hashes
            computed_hashes = {
                key: compute_hash(path, algorithm)
                for key, path in file_paths.items()
            }
            if all(computed_hashes[key] == known_hashes[key] for key in file_paths):
                # If hashes match, delete files and return False
                for path in file_paths.values():
                    os.remove(path)
                return False
            else:
                # If hashes don't match, return True
                return True
        else:
            # If either file is missing, delete existing files and return False
            for path in file_paths.values():
                if os.path.exists(path):
                    os.remove(path)
            return False

    # If use_random_keys is False
    else:
        # Check if both key files exist
        if all(os.path.exists(path) for path in file_paths.values()):
            # Compute hashes and compare with known hashes
            computed_hashes = {
                key: compute_hash(path, algorithm)
                for key, path in file_paths.items()
            }
            if all(computed_hashes[key] == known_hashes[key] for key in file_paths):
                # If hashes match, return True
                return True
            else:
                # If hashes don't match, delete files and return False
                for path in file_paths.values():
                    os.remove(path)
                return False
        else:
            # If either file is missing, delete existing files and return False
            for path in file_paths.values():
                if os.path.exists(path):
                    os.remove(path)
            return False


def generate_and_export_rsa_keys():
    if config['use_random_keys'].lower() == "false":
        rsa_1024 = RSA.construct((
                # n
                int(config["main_key_n"], 16),

                # e
                0x11,

                # d
                int(config["main_key_e"], 16),
        ))

        rsa_512 = RSA.construct((
                # n
                # 0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
                int(config["net_key_n"], 16),
                # e
                0x11,
                # d
                # 0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
                int(config["net_key_d"], 16),
        ))
    else:
        # e is set to 17 (0x11)
        e = 17

        # Generate the 1024-bit RSA key
        rsa_1024 = RSA.generate(2048, e = 17)

        rsa_512 = RSA.generate(1024, e = 17)

    # Export the keys in binary (DER) format
    key_1024_binary = rsa_1024.export_key(format='DER')
    key_512_binary = rsa_512.export_key(format='DER')

    # Save binary keys to files (optional)
    with open('files/configs/main_key_1024.der', 'wb') as f:
        f.write(key_1024_binary)
    with open('files/configs/network_key_512.der', 'wb') as f:
        f.write(key_512_binary)

    return


def import_rsa_keys():
    # Import the 1024-bit key from binary format
    with open('files/configs/main_key_1024.der', 'rb') as f:
        key_1024_binary = f.read()
    key_1024 = RSA.import_key(key_1024_binary)

    # Import the 512-bit key from binary format
    with open('files/configs/network_key_512.der', 'rb') as f:
        key_512_binary = f.read()
    key_512 = RSA.import_key(key_512_binary)

    main_key = RSA.construct((
            # n
            key_1024.n,

            # e
            key_1024.e,

            # d
            key_1024.d,
    ))

    network_key = RSA.construct((
            # n
            key_512.n,
            # e
            key_512.e,
            # d
            key_512.d,
    ))

    return main_key, network_key

# Import the keys from binary
main_key = None
network_key = None
BERstring = None
signed_mainkey_reply = None
def get_aes_key(encryptedstring, rsakey):
    return PKCS1_OAEP.new(rsakey).decrypt(encryptedstring)


def verify_message(key, message):
    key += b"\x00" * 48
    xor_a = b"\x36" * 64
    xor_b = b"\x5c" * 64
    key_a = binaryxor(key, xor_a)
    key_b = binaryxor(key, xor_b)
    phrase_a = key_a + message[:-20]
    checksum_a = SHA1.new(phrase_a).digest()
    phrase_b = key_b + checksum_a
    checksum_b = SHA1.new(phrase_b).digest()
    if checksum_b == message[-20:]:
        return True
    else:
        return False


def sign_message(key, message):
    key += b"\x00" * 48
    xor_a = b"\x36" * 64
    xor_b = b"\x5c" * 64
    key_a = binaryxor(key, xor_a)
    key_b = binaryxor(key, xor_b)
    phrase_a = key_a + message
    checksum_a = SHA1.new(phrase_a).digest()
    phrase_b = key_b + checksum_a
    checksum_b = SHA1.new(phrase_b).digest()
    return checksum_b


def rsa_sign_message(rsakey, message):
    signature = pkcs1_15.new(rsakey).sign(SHA1.new(message))
    return signature


def get_mainkey_reply():
    signature = rsa_sign_message(main_key, BERstring)

    # signature = utils.rsa_sign_message(steam.network_key_sign, BERstring)
    return struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature


def aes_decrypt(key, IV, message):
    decrypted = b""  # Initialize as bytes

    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    i = 0

    while i < len(message):
        cipher = message[i:i + 16]

        decrypted += cryptobj.decrypt(cipher)  # Use += to concatenate bytes

        i += 16

    return decrypted


def aes_decrypt_no_IV(key, message):
    cipher = PKCS1_OAEP.new(key)
    try:
        decrypted_key = cipher.decrypt(message)
        return decrypted_key
    except ValueError as e:
        print("Decryption error:", str(e))


def aes_encrypt_no_IV(key, message):
    # Assume public_key is already created as shown above
    cipher = PKCS1_OAEP.new(key)
    # Encrypting the data
    encrypted_data = cipher.encrypt(message)
    return encrypted_data


def aes_encrypt(key, IV, message):
    """"# Ensure key, IV, and message are bytes
    key = key.encode('utf-8') if isinstance(key, str) else key
    IV = IV.encode('utf-8') if isinstance(IV, str) else IV
    message = message.encode('utf-8') if isinstance(message, str) else message"""

    # pad the message
    overflow = len(message) % 16
    message += bytes([16 - overflow] * (16 - overflow))

    encrypted = b""

    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    i = 0

    while i < len(message):
        cipher = message[i:i + 16]

        encrypted += cryptobj.encrypt(cipher)

        i += 16

    return encrypted


def encrypt_with_pad(key, IV, ptext):
    padsize = 16 - len(ptext) % 16
    ptext += bytes([padsize] * padsize)

    aes = AES.new(key, AES.MODE_CBC, IV)
    ctext = aes.encrypt(ptext)

    return ctext


def encrypt_message(ptext, key):
    IV = bytes.fromhex("92183129534234231231312123123353")
    ctext = encrypt_with_pad(key, IV, ptext)

    return IV + struct.pack(">HH", len(ptext), len(ctext)) + ctext


def binaryxor(a, b):
    if len(a) != len(b):
        raise Exception("binaryxor: string lengths doesn't match!!")

    return bytes(aa ^ bb for aa, bb in zip(a, b))


def textxor(textstring):
    key = "@#$%^&*(}]{;:<>?*&^+_-="
    xorded = ""
    j = 0
    for i in range(len(textstring)):
        if j == len(key):
            j = 0
        valA = ord(textstring[i])
        valB = ord(key[j])
        valC = valA ^ valB
        xorded += chr(valC)
        j += 1
    return xorded


def chunk_aes_decrypt(key, chunk):
    cryptobj = AES.new(key, AES.MODE_ECB)
    output = b""
    lastblock = b"\x00" * 16

    for i in range(0, len(chunk), 16):
        block = chunk[i:i + 16]
        block = block.ljust(16)
        key2 = cryptobj.encrypt(lastblock)
        output += binaryxor(block, key2)
        lastblock = block

    return output[:len(chunk)]


def encrypt_with_pad(ptext, key, IV):
    padsize = 16 - len(ptext) % 16
    ptext += bytes([padsize] * padsize)

    aes = AES.new(key, AES.MODE_CBC, IV)
    ctext = aes.encrypt(ptext)

    return ctext


# BASIC xor functions for peer packet 'encryption'
def encrypt(message, password):
    encrypted = ""
    for i in range(len(message)):
        char = message[i]
        key = password[i % len(password)]
        encrypted += chr(ord(char) ^ ord(key))
    return encrypted


def encrypt_bytes(message, password):
    # Ensure both message and password are in bytes
    if isinstance(message, str):
        message = bytes(message, 'latin-1')
    if isinstance(password, str):
        password = bytes(password, 'latin-1')
    encrypted = bytearray()
    for i in range(len(message)):
        char = message[i]  # this will be an int because message is a bytes object
        key = password[i % len(password)]  # this will also be an int for the same reason
        encrypted.append(char ^ key)  # XOR operation between two integers
    return bytes(encrypted)


# Assuming password is a string and message is bytes


def decrypt(encrypted, password):
    decrypted = ""
    for i in range(len(encrypted)):
        char = encrypted[i]
        key = password[i % len(password)]
        decrypted += chr(ord(char) ^ ord(key))
    return decrypted


def decrypt_bytes(encrypted, password):
    # Ensure encrypted and password are in bytes
    if isinstance(encrypted, str):
        encrypted = bytes(encrypted, 'latin-1')
    if isinstance(password, str):
        password = bytes(password, 'latin-1')

    decrypted = bytearray()
    for i in range(len(encrypted)):
        byte = encrypted[i]  # this will be an int because encrypted is a bytes object
        key = password[i % len(password)]  # this will also be an int for the same reason
        decrypted.append(byte ^ key)  # XOR operation between two integers
    return bytes(decrypted)  # Convert bytearray back to bytes

# Beta 1 encryption functions
def beta_encrypt_message(ptext, key):
    IV = bytes.fromhex("92183129534234231231312123123353")
    ctext = encrypt_with_pad(ptext, key, IV)

    return IV + struct.pack(">HH", len(ptext), len(ctext)) + ctext


def decrypt_message(msg, key):
    bio = io.BytesIO(msg)
    IV = bio.read(16)
    ptextsize, ctextsize = struct.unpack(">HH", bio.read(4))
    ctext = bio.read(ctextsize)

    if bio.read() != b"":
        print("extra data at end of message")
        return

    aes = AES.new(key, AES.MODE_CBC, IV)
    ptext = aes.decrypt(ctext)
    #print("removing padding at end", ptext[ptextsize:].hex())
    ptext = ptext[:ptextsize]
    return ptext


def beta_decrypt_message_v1(msg, key):
    bio = io.BytesIO(msg)

    # ctextsize is just zero in steam 2002
    ptextsize, ctextsize = struct.unpack("<HH", bio.read(4))
    IV = bio.read(16)

    ctext = bio.read()
    # crop off misaligned data
    ctext = ctext[:len(ctext) & 0xfffffff0]

    if ptextsize + 1 > len(ctext):
        print("badly misaligned data")
        sys.exit()

    aes = AES.new(key, AES.MODE_CBC, IV)
    ptext = aes.decrypt(ctext)
    #print("removing padding at end", ptext[ptextsize:].hex())
    ptext = ptext[:ptextsize]
    return ptext


def validate_mac(msg, key):
    if hmac.digest(key, msg[:-20], hashlib.sha1) != msg[-20:]:
        raise Exception("Bad MAC")

    return True


def calculate_crc32_bytes(input_bytes):
    # Calculate the CRC32 hash and ensure it's treated as unsigned
    crc_hash = binascii.crc32(input_bytes) & 0xffffffff

    # Convert the hash to a 4-byte array in little-endian format
    crc_bytes = struct.pack('<I', crc_hash)

    return crc_bytes

def xor_data(data, xor_value):
    # Convert the integer to a 4-byte array
    xor_bytes = xor_value.to_bytes(4, 'little')
    # Perform XOR operation
    result = bytes(a ^ b for a, b in zip(data, cycle(xor_bytes)))
    return result

def derive_key(shared_secret, salt):
    key = scrypt(shared_secret, salt, 32, N=2**14, r=8, p=1)
    return key

def peer_encrypt_message(key, plaintext):
    cipher = AES.new(key, AES.MODE_CFB)
    ciphertext = cipher.iv + cipher.encrypt(plaintext)
    #print(f"Encrypting message. IV: {cipher.iv.hex()} Ciphertext: {ciphertext[16:].hex()}")
    return ciphertext


def peer_decrypt_message(key, ciphertext):
    iv = ciphertext[:16]
    if len(iv) != 16:
        raise ValueError(f"Incorrect IV length: {len(iv)} (expected 16 bytes)")

    cipher = AES.new(key, AES.MODE_CFB, iv=iv)
    #print(f"Decrypting message. IV: {iv.hex()} Ciphertext: {ciphertext[16:].hex()}")
    return cipher.decrypt(ciphertext[16:])