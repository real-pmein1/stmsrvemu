import binascii
import hashlib
import hmac
import io
import struct
import sys
from itertools import cycle

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import scrypt
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from config import read_config as get_config

config = get_config()

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


def rsa_sign_message(rsakey, message):
    signature = pkcs1_15.new(rsakey).sign(SHA1.new(message))
    return signature


def rsa_sign_message_1024(rsakey, message):
    signature = pkcs1_15.new(rsakey).sign(SHA1.new(message))
    return signature


def get_mainkey_reply():
    signature = rsa_sign_message_1024(main_key, BERstring)

    # signature = utils.rsa_sign_message(steam.network_key_sign, BERstring)
    return struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature


def generate_dll_signature(data_to_sign: bytes) -> bytes:
    """Generate a 128-byte RSA signature for the data using SHA-1."""
    global network_key

    # Hash the data using SHA-1
    hashed_data = SHA1.new(data_to_sign)

    # Sign the hash using the provided network_key
    signature = pkcs1_15.new(network_key).sign(hashed_data)

    # Return the first 128 bytes of the signature
    return signature[:128]
