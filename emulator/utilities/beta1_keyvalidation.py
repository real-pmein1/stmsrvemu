import hashlib, hmac



def validateBeta1Key(accountID = 0, recievedKey = b''):
    alphabet = "abcdefghijk-mnopqrstuvwxyzABCDEFGHIJKLMN+PQRSTUVWXYZ?=23456789@#"
    key = hashlib.sha1(b"SteamBeta#1").digest()

    digest = hmac.digest(key, accountID, hashlib.sha1)

    res = ""
    for c in digest[:8]:
        res += alphabet[c & 0x3f]

    return res == recievedKey
