def userhash(username) :
    original_length = len(username)

    var4 = 0x9e3779b9
    varc = var4
    var10 = 0

    while len(username) >= 12 :
        var4  = var4  + ord(username[0]) + (ord(username[1]) << 8) + (ord(username[2])  << 16) + (ord(username[3])  << 24) & 0xffffffff
        varc  = varc  + ord(username[4]) + (ord(username[5]) << 8) + (ord(username[6])  << 16) + (ord(username[7])  << 24) & 0xffffffff
        var10 = var10 + ord(username[8]) + (ord(username[9]) << 8) + (ord(username[10]) << 16) + (ord(username[11]) << 24) & 0xffffffff

        var4 = var4 - varc - var10 & 0xffffffff
        var4 = var4 ^ (var10 >> 13)

        varc = varc - var10 - var4 & 0xffffffff
        varc = varc ^ (var4 << 8 & 0xffffffff)

        var10 = var10 - var4 - varc & 0xffffffff
        var10 = var10 ^ (varc >> 13)

        var4 = var4 - varc - var10 & 0xffffffff
        var4 = var4 ^ (var10 >> 12)

        varc = varc - var10 - var4 & 0xffffffff
        varc = varc ^ (var4 << 16 & 0xffffffff)

        var10 = var10 - var4 - varc & 0xffffffff
        var10 = var10 ^ (varc >> 5)

        var4 = var4 - varc - var10 & 0xffffffff
        var4 = var4 ^ (var10 >> 3)

        varc = varc - var10 - var4 & 0xffffffff
        varc = varc ^ (var4 << 10 & 0xffffffff)

        var10 = var10 - var4 - varc & 0xffffffff
        var10 = var10 ^ (varc >> 15)

        username = username[12:]

    var10 = var10 + original_length & 0xffffffff

    name_length = len(username)

    if name_length >= 11 :
        var10 = var10 + (ord(username[10]) << 24) & 0xffffffff

    if name_length >= 10 :
        var10 = var10 + (ord(username[9]) << 16) & 0xffffffff

    if name_length >= 9 :
        var10 = var10 + (ord(username[8]) << 8) & 0xffffffff

    if name_length >= 8 :
        varc = varc + (ord(username[7]) << 24) & 0xffffffff

    if name_length >= 7 :
        varc = varc + (ord(username[6]) << 16) & 0xffffffff

    if name_length >= 6 :
        varc = varc + (ord(username[5]) << 8) & 0xffffffff

    if name_length >= 5 :
        varc = varc + ord(username[4]) & 0xffffffff

    if name_length >= 4 :
        var4 = var4 + (ord(username[3]) << 24) & 0xffffffff

    if name_length >= 3 :
        var4 = var4 + (ord(username[2]) << 16) & 0xffffffff

    if name_length >= 2 :
        var4 = var4 + (ord(username[1]) << 8) & 0xffffffff

    if name_length >= 1 :
        var4 = var4 + ord(username[0]) & 0xffffffff

    var4 = var4 - varc - var10 & 0xffffffff
    var4 = var4 ^ (var10 >> 13)

    varc = varc - var10 - var4 & 0xffffffff
    varc = varc ^ (var4 << 8 & 0xffffffff)

    var10 = var10 - var4 - varc & 0xffffffff
    var10 = var10 ^ (varc >> 13)

    var4 = var4 - varc - var10 & 0xffffffff
    var4 = var4 ^ (var10 >> 12)

    varc = varc - var10 - var4 & 0xffffffff
    varc = varc ^ (var4 << 16 & 0xffffffff)

    var10 = var10 - var4 - varc & 0xffffffff
    var10 = var10 ^ (varc >> 5)

    var4 = var4 - varc - var10 & 0xffffffff
    var4 = var4 ^ (var10 >> 3)

    varc = varc - var10 - var4 & 0xffffffff
    varc = varc ^ (var4 << 10 & 0xffffffff)

    var10 = var10 - var4 - varc & 0xffffffff
    var10 = var10 ^ (varc >> 15)

    return var10