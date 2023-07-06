import os, sys, ast, struct, binascii, shutil

from Crypto.Hash import SHA

try:
    username = sys.argv[1]
    password = sys.argv[2]
except:
    print("\nUsage: " + sys.argv[0] + " username newpassword\n")
    os._exit(0)
    

#try:
shutil.copyfile("files/users/" + username + ".py", "files/users/" + username + ".py.bak")
with open("files/users/" + username + ".py", 'r') as f:
    userblobstr = f.read()
    userblob = eval(userblobstr[16:len(userblobstr)])
    secretquestion = userblob['\x05\x00\x00\x00'][username]['\x03\x00\x00\x00']
    secretsha = userblob['\x05\x00\x00\x00'][username]['\x04\x00\x00\x00']
    secretsalt = userblob['\x05\x00\x00\x00'][username]['\x05\x00\x00\x00']
    salt1 = binascii.a2b_hex("fedcba98")
    salt2 = binascii.a2b_hex("76543210")
    saltfull = binascii.a2b_hex("fedcba9876543210")
    newpasswd = sys.argv[2].encode("utf-8")
    newpasswdsha = SHA.new(salt1 + newpasswd + salt2).digest()[:16] + "\x01\x02\x03\x04".encode("utf-8")
    invalid = {'\x05\x00\x00\x00'}
    def without_keys(d, keys) :
        return {x: d[x] for x in d if x not in keys}
    userblobnew = without_keys(userblob, invalid)
    l = len(sys.argv[2])
    li = sys.argv[2].split(',')
    sublist = li
    #print(sublist)
    tempdict = {}
    tempstr = "{'\\x05\\x00\\x00\\x00': {'" + str(username) + "': {'\\x01\\x00\\x00\\x00': " + str(newpasswdsha)[1:len(str(newpasswdsha))] + ", '\\x02\\x00\\x00\\x00': " + str(saltfull)[1:len(str(saltfull))] + ", '\\x03\\x00\\x00\\x00': '" + str(secretquestion) + "', '\\x04\\x00\\x00\\x00': '" + str(secretsha) + "', '\\x05\\x00\\x00\\x00': '" + str(secretsalt) + "'}}}"
    print(tempstr)
    tempdict = eval(tempstr)
    print(tempdict)
    userblobnew.update(tempdict)
    print(userblobnew)

    #with open("files/users/" + username + ".py", 'w') as g:
        #g.write("user_registry = ")
        #g.write(str(userblobnew))
        
print("\nPassword reset for " + username)
#except:
#    print("An error has occured, please try again")
