import sys, ast, binascii

try:
    username = sys.argv[1]
except:
    print("\nUsage: " + sys.argv[0] + " username")
    os._exit(0)
    
try:
    userblobnew = {}
    with open("files/users/" + username + ".py", 'r') as f:
        userblob = {}
        userblobstr = f.read()
        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
        blocked = binascii.b2a_hex(userblob['\x0c\x00\x00\x00'])
        invalid = {'\x0c\x00\x00\x00'}
        def without_keys(d, keys) :
            return {x: d[x] for x in d if x not in keys}
        userblobnew = without_keys(userblob, invalid)
        if blocked == "0001" :
            tempstr = "{'\\x0c\\x00\\x00\\x00': '\\x00\\x00'}"
            print("\nAccount " + username + " is now unblocked")
        else :
            tempstr = "{'\\x0c\\x00\\x00\\x00': '\\x00\\x01'}"
            print("\nAccount " + username + " is now blocked")
        tempdict = ast.literal_eval(tempstr)
        userblobnew.update(tempdict)
        #print(userblobnew)

    with open("files/users/" + username + ".py", 'w') as g:
        g.write("user_registry = ")
        g.write(str(userblobnew))
except:
    print("An error has occured, please try again")