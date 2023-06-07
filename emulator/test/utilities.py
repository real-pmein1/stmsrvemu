import struct

def encrypt(message, password):
    encrypted = ""
    for i in range(len(message)):
        char = message[i]
        key = password[i % len(password)]
        encrypted += chr(ord(char) ^ ord(key))
    return encrypted


def decrypt(encrypted, password):
    decrypted = ""
    for i in range(len(encrypted)):
        char = encrypted[i]
        key = password[i % len(password)]
        decrypted += chr(ord(char) ^ ord(key))
    return decrypted
def decodeIP(string) :
    (oct1, oct2, oct3, oct4, port) = struct.unpack("<BBBBH", string)
    ip = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
    return ip, port

def encodeIP((ip, port)) :
    if type(port) == str :
        port = int(port)
    oct = ip.split(".")
    string = struct.pack("<BBBBH", int(oct[0]), int(oct[1]), int(oct[2]), int(oct[3]), port)
    return string
