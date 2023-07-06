from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Cipher import AES

main_key_sign = RSA.construct((
    # n
    0x86724794f8a0fcb0c129b979e7af2e1e309303a7042503d835708873b1df8a9e307c228b9c0862f8f5dbe6f81579233db8a4fe6ba14551679ad72c01973b5ee4ecf8ca2c21524b125bb06cfa0047e2d202c2a70b7f71ad7d1c3665e557a7387bbc43fe52244e58d91a14c660a84b6ae6fdc857b3f595376a8e484cb6b90cc992f5c57cccb1a1197ee90814186b046968f872b84297dad46ed4119ae0f402803108ad95777615c827de8372487a22902cb288bcbad7bc4a842e03a33bd26e052386cbc088c3932bdd1ec4fee1f734fe5eeec55d51c91e1d9e5eae46cf7aac15b2654af8e6c9443b41e92568cce79c08ab6fa61601e4eed791f0436fdc296bb373L,
    # e
    0x07e89acc87188755b1027452770a4e01c69f3c733c7aa5df8aac44430a768faef3cb11174569e7b44ab2951da6e90212b0822d1563d6e6abbdd06c0017f46efe684adeb74d4113798cec42a54b4f85d01e47af79259d4670c56c9c950527f443838b876e3e5ef62ae36aa241ebc83376ffde9bbf4aae6cabea407cfbb08848179e466bcb046b0a857d821c5888fcd95b2aae1b92aa64f3a6037295144aa45d0dbebce075023523bce4243ae194258026fc879656560c109ea9547a002db38b89caac90d75758e74c5616ed9816f3ed130ff6926a1597380b6fc98b5eeefc5104502d9bee9da296ca26b32d9094452ab1eb9cf970acabeecde6b1ffae57b56401L,
    # d
    0x11L,
))

network_key = RSA.construct((
    # n
    0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
    # e
    0x11L,
    # d
    0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
))

network_key_sign = RSA.construct((
    # n
    0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
    # e
    0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
    # d
    0x11L,
))

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

    if overflow > 0 :
        message = message + (16 - overflow) * "\x05"

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
