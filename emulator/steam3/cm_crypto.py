"""
TAKEN FROM:
https://github.com/ValvePython/steam/blob/master/steam/core/crypto.py
All function in this module take and return :class:`bytes`
"""
import sys
from os import urandom as random_bytes
from struct import pack

from Crypto.Cipher import AES as AES, PKCS1_v1_5
from Crypto.Hash import HMAC, MD5, SHA1
from Crypto.PublicKey.RSA import construct as rsa_construct

BS = 16
pad = lambda s: s + (BS - len(s) % BS) * pack('B', BS - len(s) % BS)

if sys.version_info < (3,):
    unpad = lambda s: s[0:-ord(s[-1])]
else:
    unpad = lambda s: s[0:-s[-1]]


def symmetric_encrypt(message, key):
    iv = random_bytes(BS)
    return symmetric_encrypt_with_iv(message, key, iv)

def symmetric_encrypt_ecb(message, key):
    return AES.new(key, AES.MODE_ECB).encrypt(pad(message))

def symmetric_encrypt_HMAC(message, key, hmac_secret):
    prefix = random_bytes(3)
    hmac = hmac_sha1(hmac_secret, prefix + message)
    iv = hmac[:13] + prefix
    return symmetric_encrypt_with_iv(message, key, iv)

def symmetric_encrypt_iv(iv, key):
    return AES.new(key, AES.MODE_ECB).encrypt(iv)

def symmetric_encrypt_with_iv(message, key, iv):
    encrypted_iv = symmetric_encrypt_iv(iv, key)
    cyphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(message))
    return encrypted_iv + cyphertext

def pad(s):
    return s + (BS - len(s) % BS) * pack('B', BS - len(s) % BS)


def unpad(s):
    return s[0:-s[-1]]

# Ensure that the packet is properly padded before decryption


def symmetric_decrypt_ecb(cyphertext, key):
    return unpad(AES.new(key, AES.MODE_ECB).decrypt(cyphertext))

def symmetric_decrypt_HMAC(cyphertext, key, hmac_secret):
    """:raises: :class:`RuntimeError` when HMAC verification fails"""
    iv = symmetric_decrypt_iv(cyphertext, key)
    message = symmetric_decrypt_with_iv(cyphertext, key, iv)

    hmac = hmac_sha1(hmac_secret, iv[-3:] + message)

    if iv[:13] != hmac[:13]:
        raise RuntimeError("Unable to decrypt message. HMAC does not match.")

    return message

def symmetric_decrypt(cyphertext, key):
    iv = symmetric_decrypt_iv(cyphertext, key)
    return symmetric_decrypt_with_iv(cyphertext, key, iv)

def symmetric_decrypt_iv(cyphertext, key):
    return AES.new(key, AES.MODE_ECB).decrypt(cyphertext[:BS])

def symmetric_decrypt_with_iv(cyphertext, key, iv):
    # Pad the ciphertext if needed
    if len(cyphertext[BS:]) % BS != 0:
        cyphertext = pad(cyphertext)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(cyphertext[BS:])
    return unpad(decrypted)


def hmac_sha1(secret, data):
    return HMAC.new(secret, data, SHA1).digest()

def sha1_hash(data):
    return SHA1.new(data).digest()

def md5_hash(data):
    return MD5.new(data).digest()

def rsa_publickey(mod, exp):
    return rsa_construct((mod, exp))

def pkcs1v15_encrypt(key, message):
    return PKCS1_v1_5.new(key).encrypt(message)