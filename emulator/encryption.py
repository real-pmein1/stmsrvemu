import binascii, socket, struct, zlib, os, sys, logging
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Cipher import AES

from steamemu.config import read_config
config = read_config()

def get_aes_key(encryptedstring, rsakey) :
    decryptedstring = rsakey.decrypt(encryptedstring)

    if len(decryptedstring) != 127 :
        raise NameError, "RSAdecrypted string not the correct length!" + str(len(decryptedstring))

    firstpasschecksum = SHA.new(decryptedstring[20:127] + "\x00\x00\x00\x00" ).digest()
    secondpasskey = binaryxor(firstpasschecksum, decryptedstring[0:20])
    secondpasschecksum0 = SHA.new(secondpasskey + "\x00\x00\x00\x00" ).digest()
    secondpasschecksum1 = SHA.new(secondpasskey + "\x00\x00\x00\x01" ).digest()
    secondpasschecksum2 = SHA.new(secondpasskey + "\x00\x00\x00\x02" ).digest()
    secondpasschecksum3 = SHA.new(secondpasskey + "\x00\x00\x00\x03" ).digest()
    secondpasschecksum4 = SHA.new(secondpasskey + "\x00\x00\x00\x04" ).digest()
    secondpasschecksum5 = SHA.new(secondpasskey + "\x00\x00\x00\x05" ).digest()
    secondpasstotalchecksum = secondpasschecksum0 + secondpasschecksum1 + secondpasschecksum2 + secondpasschecksum3 + secondpasschecksum4 + secondpasschecksum5
    finishedkey = binaryxor(secondpasstotalchecksum[0:107], decryptedstring[20:127])
    controlchecksum = SHA.new("").digest()

    if finishedkey[0:20] != controlchecksum :
        raise NameError, "Control checksum didn't match!"

    return finishedkey[-16:]

def verify_message(key, message) :
    key = key + "\x00" * 48
    xor_a = "\x36" * 64
    xor_b = "\x5c" * 64
    key_a = binaryxor(key, xor_a)
    key_b = binaryxor(key, xor_b)
    phrase_a = key_a + message[:-20]
    checksum_a = SHA.new(phrase_a).digest()
    phrase_b = key_b + checksum_a
    checksum_b = SHA.new(phrase_b).digest()
    
    if checksum_b == message[-20:] :
        return True
    else:
        return False

def sign_message(key, message) :
    key = key + "\x00" * 48
    xor_a = "\x36" * 64
    xor_b = "\x5c" * 64
    key_a = binaryxor(key, xor_a)
    key_b = binaryxor(key, xor_b)
    phrase_a = key_a + message
    checksum_a = SHA.new(phrase_a).digest()
    phrase_b = key_b + checksum_a
    checksum_b = SHA.new(phrase_b).digest()
    return checksum_b

def rsa_sign_message(rsakey, message) :
    digest = SHA.new(message).digest()
    fulldigest = "\x00\x01" + ("\xff" * 90) + "\x00\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14" + digest
    signature = rsakey.encrypt(fulldigest, 0)[0]
    signature = signature.rjust(128, "\x00") # we aren't guaranteed that RSA.encrypt will return a certain length, so we pad it
    return signature

def rsa_sign_message_1024(rsakey, message) :
    digest = SHA.new(message).digest()
    fulldigest = "\x00\x01" + ("\xff" * 218) + "\x00\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14" + digest
    signature = rsakey.encrypt(fulldigest, 0)[0]
    signature = signature.rjust(256, "\x00") # we aren't guaranteed that RSA.encrypt will return a certain length, so we pad it
    return signature

def aes_decrypt(key, IV, message) :
    decrypted = ""
    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    i = 0

    while i < len(message) :
        cipher = message[i:i+16]
        decrypted = decrypted + cryptobj.decrypt(cipher)
        i = i + 16

    return decrypted

def aes_encrypt(key, IV, message) :
    # pad the message
    overflow = len(message) % 16
    message = message + (16 - overflow) * chr(16 - overflow)
    encrypted = ""
    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    i = 0

    while i < len(message) :
        cipher = message[i:i+16]
        encrypted = encrypted + cryptobj.encrypt(cipher)
        i = i + 16

    return encrypted

def binaryxor(stringA, stringB) :
    if len(stringA) != len(stringB) :
        print("binaryxor: string lengths doesn't match!!")
        sys.exit()

    outString =  ""
    
    for i in range( len(stringA) ) :
        valA = ord(stringA[i])
        valB = ord(stringB[i])
        valC = valA ^ valB
        outString = outString + chr(valC)
        
    return outString
    
def textxor(textstring) :  
    key = "@#$%^&*(}]{;:<>?*&^+_-="
    xorded = ""
    j = 0
    
    for i in range( len(textstring) ) :
        if j == len(key) :
            j = 0  
        valA = ord(textstring[i])
        valB = ord(key[j])
        valC = valA ^ valB
        xorded = xorded + chr(valC)
        j = j + 1
        
    return xorded

def chunk_aes_decrypt(key, chunk) :
    cryptobj = AES.new(key, AES.MODE_ECB)
    output = ""
    lastblock = "\x00" * 16

    for i in range(0, len(chunk), 16) :
        block = chunk[i:i+16]
        block = block.ljust(16)
        key2 = cryptobj.encrypt(lastblock)
        output += binaryxor(block, key2)
        lastblock = block

    return output[:len(chunk)]
