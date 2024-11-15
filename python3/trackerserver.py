import io, logging, secrets, socket, sqlite3, struct, time, traceback, configparser

# TODO replace with something faster
from CryptICE import IceKey

from tracker.config import read_config

config = read_config()

#logging.basicConfig(
#    format="%(asctime)s %(levelname)-8s %(message)s",
#    filename="logs/trackerserver_debug.log",
#    encoding="utf-8",
#    level=logging.DEBUG)

#console = logging.StreamHandler()
#console.setLevel(logging.INFO)
#console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
#logging.getLogger().addHandler(console)

logger = logging.getLogger('trkrsrv')
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    filename="logs/trackerserver_debug.log",
    encoding="utf-8",
    level=logging.DEBUG)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))

logger.addHandler(console)


class UserManager:
    def __init__(self, srv):
        self.srv = srv

        self.con = sqlite3.connect("trackerserver.db")

        res = self.con.execute("SELECT name FROM sqlite_master")
        if res.fetchone() is None:
            logger.info("creating user database")
            self.con.execute(
                "CREATE TABLE IF NOT EXISTS users(email BLOB PRIMARY KEY, username BLOB, firstname BLOB, lastname BLOB)")
            self.con.execute("CREATE TABLE IF NOT EXISTS friend(source INTEGER, target INTEGER)")

            self.con.commit()

    def get_user_by_email(self, email):
        res = self.con.execute(
            "SELECT ROWID + 0x10000, email, username, firstname, lastname FROM users WHERE email = ?", (email,))
        return res.fetchone()

    def get_user_by_uid(self, uid):
        res = self.con.execute(
            "SELECT ROWID + 0x10000, email, username, firstname, lastname FROM users WHERE ROWID + 0x10000 = ?", (uid,))
        return res.fetchone()

    def search_users(self):
        res = self.con.execute("SELECT ROWID + 0x10000, username, firstname, lastname FROM users")
        return res.fetchall()

    def auth(self, email, username):
        row = self.get_user_by_email(email)
        if row is None:
            logger.info("created user with email %s  username %s" % (email, username))
            self.con.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (email, username, b"none", b"none"))
            self.con.commit()

            row = self.get_user_by_email(email)

        else:
            logger.info("found existing user with email %s" % email)

        return row[0]

    def update_details(self, uid, username, firstname, lastname):
        self.con.execute("UPDATE users SET username = ?, firstname = ?, lastname = ? WHERE ROWID + 0x10000 = ?",
                         (username, firstname, lastname, uid))
        self.con.commit()

    def request_friend(self, source, target):
        res = self.con.execute("SELECT source, target FROM friend WHERE source = ? and target = ?", (source, target))
        rows = res.fetchone()

        if rows == None:
            self.con.execute("INSERT INTO friend VALUES (?, ?)", (source, target))
            self.con.commit()
            return True
        else:
            return False

    def get_friends_by_source(self, uid):
        res = self.con.execute("SELECT target FROM friend WHERE source = ?", (uid,))
        return [x[0] for x in res.fetchall()]

    def get_friends_by_target(self, uid):
        res = self.con.execute("SELECT source FROM friend WHERE target = ?", (uid,))
        return [x[0] for x in res.fetchall()]

    def pending_friends(self, uid):
        wannabe = self.get_friends_by_target(uid)

        realfriends = self.get_friends_by_source(uid)

        res = []
        for friendid in wannabe:
            if friendid not in realfriends:
                res.append(friendid)

        return res

    def real_friends(self, uid):
        wannabe = self.get_friends_by_target(uid)

        realfriends = self.get_friends_by_source(uid)

        res = []
        for friendid in wannabe:
            if friendid in realfriends:
                res.append(friendid)

        return res


def di(s):
    return struct.unpack("<I", s)[0]


def ei(n):
    return struct.pack("<I", n)


def parse_data(data, typed=False):
    bio = io.BytesIO(data)

    res = {}
    while True:
        datatype = bio.read(1)[0]
        if not datatype & 1:
            break

        key = b""
        while True:
            c = bio.read(1)
            if c == b"\x00":
                break

            key += c

        key = str(key, "utf8")

        sz, = struct.unpack("<H", bio.read(2))
        value = bio.read(sz)

        if datatype & 4 == 0:
            if value[-1] == 0:
                value = value[:-1]
            else:
                raise Exception("non-null terminated string")

        if typed:
            res[key] = (datatype, value)
        else:
            res[key] = value

    return res


def validate_msg(msg, mandatory, optional=()):
    for key in mandatory:
        if key not in msg:
            raise Exception("missing key", key)

    for key in msg:
        if key != "_id" and key not in mandatory and key not in optional:
            raise Exception("unexpected key", key)


class Message:
    def __init__(self, client, cmdid, ack=False):
        self.client = client
        self.sessionid = client.sessionid
        self.kv = {}
        self.msg = b""
        self.cmdid = cmdid
        self.seqnum = client.seqnum
        self.reply_to = client.r_seqnum
        self.padding = b""
        self.ack = ack
        self.add_int("_id", cmdid)

    def add_kv(self, mode, key, value):
        if key in self.kv:
            raise Exception("duplicate key", key)

        self.kv[key] = (mode, value)

        self.msg += bytes([mode])
        self.msg += bytes(key, "utf8") + b"\x00"
        self.msg += struct.pack("<H", len(value))
        self.msg += value

    def add_bin(self, key, s):
        self.add_kv(5, key, s)

    def add_int(self, key, n):
        self.add_kv(5, key, ei(n))

    def add_str(self, key, s):
        self.add_kv(1, key, s + b"\x00")

    def getpacket(self):
        logger.debug("preparing packet with id %d  clientid  %d  sessionid %d  seqnum %d  replyto %d" %
                      (self.cmdid, self.client.clientid, self.sessionid, self.seqnum, self.reply_to))
        logger.debug("keyvalues %s" % self.kv)

        data = struct.pack("<IIIIBB", self.client.clientid, self.sessionid, self.seqnum, self.reply_to, 1, 1)
        data += self.msg + b"\x00" + self.padding

        if not self.ack:
            while len(data) % 8 != 4:
                data += b"\x00"

        data = b"\x04\x16" + struct.pack("<H", len(data) + 4) + data

        if not self.ack:
            return b"\xfe\xff\xff\xff" + ice.Encrypt(data)
        else:
            return data


network_key = (
    # n
    0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059,
    # e
    0x11,
    # d
    0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9d,
)

newkey = bytes.fromhex("30819d300d06092a864886f70d010101050003818b0030818702818100") + network_key[0].to_bytes(128,
                                                                                                               byteorder="big") + bytes.fromhex(
    "020111")

ice = IceKey(1, [13, 85, 243, 211, 173, 6, 87, 71])


class Client:
    def __init__(self, addr, clientid, sessionid, seqnum, r_seqnum):
        self.addr = addr
        self.clientid = clientid
        self.sessionid = sessionid
        self.seqnum = seqnum
        self.expected = r_seqnum
        self.r_seqnum = r_seqnum
        self.ackd = 0
        self.queue = {}
        self.update_timeout(15)
        self.init = False
        self.uid = 0

    def keep_alive(self):
        self.staletime = time.time() + self.timeout

    def update_timeout(self, timeout):
        self.timeout = timeout
        self.keep_alive()


class Packet:
    def __init__(self, data):
        if data[0:4] == b"\xfe\xff\xff\xff":
            data = ice.Decrypt(data[4:])
            logger.debug("decrypted %s" % data.hex())

        if data[0:2] != b"\x04\x16" or len(data) < 0x16:
            raise Exception("BAD HEADER", data.hex())

        self.version, self.headersize, self.packetsize, self.clientid, self.sessionid, self.seqnum, self.seqack, self.packetnum, self.totalpackets = struct.unpack(
            "<BBHIIIIBB", data[:0x16])

        if self.packetsize != len(data):
            raise Exception("BAD SIZE", data.hex())

        data += b"\x00"  # workaround to ensure keyvalues are terminated

        self.data = data


class TrackerServer:
    def __init__(self):
        logger.info("------------------------------------")
        logger.info("TRACKER Server 2003 beta started")
        logger.info("Made by ymgve")
        logger.info("------------------------------------")

        self.ipaddrport = (config["server_ip"], 1200)

        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind((config["server_ip"], 1200))
        self.s.settimeout(0.2)

        self.clients = {}

        # contains logged in clients
        self.clients_by_uid = {}

        self.pending = []

        self.usermgr = UserManager(self)

    def run(self):
        while True:
            try:
                data, addr = self.s.recvfrom(16384)
            except socket.timeout:
                addr = None

            if addr != None:
                try:
                    self.handle_incoming(data, addr)
                except Exception as e:
                    logger.exception(e)

            self.do_sends()

            self.remove_stale_clients()

    def remove_stale_clients(self):
        # get keys first since we are modifying the dict during iteration
        addrs = list(self.clients)

        curr_time = time.time()
        for addr in addrs:
            client = self.clients[addr]
            if client.staletime < curr_time:
                if client.uid in self.clients_by_uid:
                    del self.clients_by_uid[client.uid]
                    logger.info("removed stale client uid %x" % client.uid)

                del self.clients[addr]
                logger.info("removed stale client addr %s" % (addr,))

                for friendid in self.usermgr.real_friends(client.uid):
                    self.send_single_user_status(friendid, client.uid)

    def enqueue(self, msg):
        self.pending.append((0, 0, msg))

        # do not increase seqnum for acks
        if msg.cmdid != 1:
            msg.client.seqnum += 1

    def do_sends(self):
        newpending = []
        curr_time = time.time()

        for curr_attempt, sched_time, msg in self.pending:
            # still not acknowledged
            if msg.seqnum > msg.client.ackd:
                if sched_time < curr_time:
                    if not msg.ack:
                        if curr_attempt < 5:
                            newpending.append((curr_attempt + 1, curr_time + 5.0, msg))
                        else:
                            logger.warning("not retrying packet after several attempts")

                    if curr_attempt > 0:
                        msg.padding += b"\x00" * 8
                        logger.info("resending attempt %d" % curr_attempt)

                    data = msg.getpacket()
                    self.s.sendto(data, msg.client.addr)
                    logger.info("sending message to %s with id %d" % (msg.client.addr, msg.cmdid))
                    logger.debug("sending to %s: %s" % (msg.client.addr, data.hex()))

                else:
                    newpending.append((curr_attempt, sched_time, msg))

        self.pending = newpending

    def handle_incoming(self, data, addr):
        logger.debug("received from %s: %s" % (addr, data.hex()))

        pkt = Packet(data)

        logger.debug("packet header %d %d %d %d" % (pkt.clientid, pkt.sessionid, pkt.seqnum, pkt.seqack))

        if pkt.packetnum != 1 or pkt.totalpackets != 1:
            raise Exception("multipacket not supported yet")

        self.handle_pkt(pkt, addr)

    def handle_pkt(self, pkt, addr):
        if addr not in self.clients:
            client = Client(addr, pkt.clientid, pkt.sessionid, pkt.seqack + 1, pkt.seqnum)
            self.clients[addr] = client

        client = self.clients[addr]

        client.keep_alive()

        if pkt.seqnum == 0:  # only happens with ack packets?
            self.handle_msg(client, pkt)  # maybe change to early handling?
            return

        # if client never got ack for one of their packages, it changes clientid and resets sequence numbers
        # we also get here when a client reconnects without properly terminating the connection
        if pkt.clientid != client.clientid:
            logger.info("client %x is resetting connection?" % client.clientid)
            client.clientid = pkt.clientid
            if pkt.seqnum != 1 or pkt.seqack != 0:
                raise Exception("bad values on connection reset")

            client.sessionid = pkt.sessionid
            client.seqnum = 1
            client.expected = 1
            client.ackd = 0
            client.queue = {}

        if pkt.seqnum < client.expected:
            logger.warning("duplicate arrived late %d %d" % (pkt.seqnum, client.expected))

            # ugly hack to ensure we insta-send the response the other side probaby missed
            # seems to happen when user is loading into a level in a game?
            found = False
            for index, (curr_attempt, sched_time, msg) in enumerate(self.pending):
                if msg.client.clientid == client.clientid and msg.reply_to == pkt.seqnum:
                    logger.warning("forcing instant resend of message seqnum %d" % msg.seqnum)
                    self.pending[index] = (curr_attempt + 1, 0, msg)
                    found = True
                    break

            # if not found, s
            if not found:
                logger.warning("forcing instant ack message")
                msg = Message(client, 1, True)
                self.enqueue(msg)

            return

        if pkt.seqnum in client.queue:
            logger.warning("duplicate packet %d %s" % (pkt.seqnum, client.queue))
            return

        client.queue[pkt.seqnum] = pkt

        while client.expected in client.queue:
            seqnum = client.expected
            self.handle_msg(client, client.queue[seqnum])
            del client.queue[seqnum]
            client.expected += 1

    def handle_msg(self, client, pkt):
        msg = parse_data(pkt.data[0x16:])
        cmdid = di(msg["_id"])

        logger.info("received packet with id %d from uid %x address %s" % (cmdid, client.uid, client.addr))

        # log detailed data in packet
        msg2 = parse_data(pkt.data[0x16:], True)
        for key in msg2:
            datatype, value = msg2[key]
            logger.debug("    %s %d %s" % (key, datatype, value))

        logger.debug("")

        client.r_seqnum = pkt.seqnum

        if pkt.seqack < client.ackd:
            raise Exception("bad seqack", pkt.seqack, client.ackd)

        client.ackd = pkt.seqack

        if cmdid == 1:
            # ACK has id 1 and might have zero as sessionid, early return, we already handled ack
            return

        if cmdid == 2001:
            if pkt.sessionid != 0:
                raise Exception("bad sessionid for connect?")
        else:
            if not client.init:
                logger.warning("clientid %d hasn't been initialized, sending reset" % client.clientid)
                msg = Message(client, 1004)
                msg.add_int("minTime", 0)
                msg.add_int("maxTime", 1)
                self.enqueue(msg)
                return

            if client.sessionid != pkt.sessionid:
                raise Exception("bad sessionid", client.sessionid, pkt.sessionid)

        if cmdid == 2001:  # pre-login
            validate_msg(msg, ("uid", "email", "status"), ("UserName", "FirewallWindow"))

            # uid can be nonzero if the client reconnects - should we skip the auth step if uid and clientid match?

            client.uid = di(msg["uid"])
            client.email = msg["email"]
            client.status = di(msg["status"])
            client.sessionid = 0

            if "UserName" in msg:
                client.username = msg["UserName"]
            else:
                client.username = client.email

            logger.info("pre-login for uid %x  email %s  status %d" % (client.uid, client.email, client.status))

            new_sessionid = secrets.randbits(32)
            client.challenge = secrets.randbits(32)

            msg = Message(client, 1001)
            msg.add_int("sessionID", new_sessionid)
            msg.add_int("challenge", client.challenge)
            msg.add_kv(5, "key", newkey)

            self.enqueue(msg)

            # first msg goes out with a sessionid of 0, now we put in the real sessionid
            client.sessionid = new_sessionid
            client.init = True

        elif cmdid == 2002:  # login
            validate_msg(msg, ("challenge", "sessionID", "status", "build", "hrate", "ticket"), ("PlatformVer",))

            challenge = di(msg["challenge"])
            sessionid = di(msg["sessionID"])
            status = di(msg["status"])
            build = di(msg["build"])
            hrate = di(msg["hrate"])
            ticket = msg["ticket"]

            if "PlatformVer" in msg:
                platformver = di(msg["PlatformVer"])
            else:
                platformver = 0

            if challenge != client.challenge:
                raise Exception("bad challenge")

            if sessionid != client.sessionid:
                raise Exception("bad sessionid")

            logger.info("build %d  hrate %d  PlatformVer %d" % (build, hrate, platformver))

            # for now, assume ticket validates
            # user logs on, TODO notify all friends
            # msg = Message(client, 1, pkt.seqnum, True)

            # creates user if one doesn't exist
            uid = self.usermgr.auth(client.email, client.username)
            logger.info("authed user with uid %x" % uid)

            client.uid = uid
            client.status = status
            self.clients_by_uid[client.uid] = client

            client.update_timeout(hrate // 1000)

            msg = Message(client, 1002)  # login OK
            msg.add_int("status", status)
            msg.add_int("userID", client.uid)
            msg.add_int("serverID", 1)
            msg.add_int("sessionID", client.sessionid)
            msg.add_bin("IP", socket.inet_aton(client.addr[0]))
            msg.add_int("Port", client.addr[1])

            self.enqueue(msg)

            # pending friend requests
            for friendid in self.usermgr.pending_friends(client.uid):
                logger.info("user %x has pending friend request from %x" % (client.uid, friendid))

                self.send_friend_request(client, friendid)

            # send info about our friends' status
            self.send_friends_status(client.uid)

            # notify friends that we are online
            for friendid in self.usermgr.real_friends(client.uid):
                self.send_single_user_status(friendid, client.uid)

            # send usernames etc since they might have been updated
            for friendid in self.usermgr.get_friends_by_source(client.uid):
                self.send_userinfo(client.uid, friendid)

        elif cmdid == 2004:  # search for users
            validate_msg(msg, ("uid", "Email", "UserName", "FirstName", "LastName"))

            # ignore search parameters for now, just return all users

            nsent = 0
            for row in self.usermgr.search_users():
                if client.uid != row[0]:
                    msg = Message(client, 1011)  # search result
                    msg.add_int("uid", row[0])
                    msg.add_str("UserName", row[1])
                    msg.add_str("FirstName", row[2])
                    msg.add_str("LastName", row[3])

                    self.enqueue(msg)
                    nsent += 1

            if nsent == 0:
                msg = Message(client, 1, True)
                self.enqueue(msg)


        elif cmdid == 2005:  # status change
            validate_msg(msg, ("status",), ("hrate", "GameIP", "GamePort", "Game"))

            client.status = di(msg["status"])

            logger.info("uid %x changed status to %d" % (client.uid, client.status))

            if client.status == 4:  # ingame
                client.gameip = msg["GameIP"]
                client.gameport = msg["GamePort"]  # some weird format?
                client.game = msg["Game"]

                logger.info("uid %x is playing a game: %s on ip %s port %s" % (
                client.uid, client.game, socket.inet_ntoa(client.gameip), client.gameport.hex()))

            # user set status to offline, so remove from client uid mapping
            if client.status == 0:
                del self.clients_by_uid[client.uid]
                del self.clients[client.addr]
                logger.info("uid %d logged off" % client.uid)

            if "hrate" in msg:
                hrate = di(msg["hrate"])
                logger.info("got hrate %d" % hrate)
                client.update_timeout(hrate // 1000)

            msg = Message(client, 1, True)
            self.enqueue(msg)

            for friendid in self.usermgr.real_friends(client.uid):
                self.send_single_user_status(friendid, client.uid)


        elif cmdid == 2006:  # respond to friend request from other user
            validate_msg(msg, ("targetID", "auth"))

            targetuid = di(msg["targetID"])
            auth = di(msg["auth"])

            if auth == 1:
                logger.info("user %x acknowledged friend request from %x" % (client.uid, targetuid))
                self.usermgr.request_friend(client.uid, targetuid)

                # update friend info here
            else:
                logger.error("refusing a friend request isn't implemented yet!")

            msg = Message(client, 1, True)
            self.enqueue(msg)

            # update new friend with our status and us with the friend's status
            self.send_single_user_status(client.uid, targetuid)
            self.send_single_user_status(targetuid, client.uid)


        elif cmdid == 2007:  # friendship reqest
            validate_msg(msg, ("uid", "ReqReason"))

            targetuid = di(msg["uid"])
            reason = msg["ReqReason"]

            logger.info("user %x requests friendship with %x, reason %s" % (client.uid, targetuid, reason))

            self.usermgr.request_friend(client.uid, targetuid)

            msg = Message(client, 1, True)
            self.enqueue(msg)

            if targetuid in self.clients_by_uid:
                self.send_friend_request(self.clients_by_uid[targetuid], client.uid)


        elif cmdid == 2008:  # get friend info
            validate_msg(msg, ("uid",))

            uid = di(msg["uid"])
            logger.info("requested info about uid %x" % uid)

            self.send_userinfo(client.uid, uid)


        elif cmdid == 2009:  # change user info
            validate_msg(msg, ("uid", "UserName", "FirstName", "LastName"))

            uid = di(msg["uid"])
            if client.uid != uid:
                logger.error("user %x tried to change info for another user %x!" % (client.uid, uid))

            else:
                # TODO find proper limits here
                username = msg["UserName"][:32]
                firstname = msg["FirstName"][:32]
                lastname = msg["LastName"][:32]

                self.usermgr.update_details(client.uid, username, firstname, lastname)

                for friendid in self.usermgr.get_friends_by_target(client.uid):
                    self.send_userinfo(friendid, client.uid)

            msg = Message(client, 1, True)
            self.enqueue(msg)

        elif cmdid == 2010:  # forward for user
            validate_msg(msg, ("rID", "rUserID", "rSessionID", "rServerID", "rData"))

            rid = di(msg["rID"])
            ruserid = di(msg["rUserID"])
            rsessionid = di(msg["rSessionID"])
            rserverid = di(msg["rServerID"])
            rdata = msg["rData"]

            logger.warning("forwarding message encountered id %d  uid %x  sessionid %d  serverid %d" % (
            rid, ruserid, rsessionid, rserverid))
            msg2 = parse_data(rdata + b"\x00", True)
            for key in msg2:
                datatype, value = msg2[key]
                logger.warning("    %s %d %s" % (key, datatype, value))

            msg = Message(client, 1, True)
            self.enqueue(msg)

            if ruserid not in self.clients_by_uid:
                logger.info("user with uid %x is not online, can't send forwarded message!" % ruserid)

            else:
                targetclient = self.clients_by_uid[ruserid]

                msg = Message(targetclient, rid)
                msg.msg = rdata
                self.enqueue(msg)


        elif cmdid == 3001:  # message between users, normally chat
            uid = di(msg["uid"])
            targetid = di(msg["targetID"])

            # addon message (builtin games, other things?)
            if "AddOnFlag" in msg and di(msg["AddOnFlag"]) == 1:
                validate_msg(msg, ("uid", "targetID", "gameID", "addOnSessionID", "MsgDataLen", "MsgData", "AddOnFlag"))

                gameid = di(msg["gameID"])
                addonsess = di(msg["addOnSessionID"])
                msgdatalen = di(msg["MsgDataLen"])
                msgdata = msg["MsgData"]

                logger.info("user %x sent addon message targetid %x  gameid %d  sessionid %d  msg size %d" % (
                uid, targetid, gameid, addonsess, msgdatalen))

                msg = Message(client, 1, True)
                self.enqueue(msg)

                if targetid not in self.clients_by_uid:
                    logger.info("user with uid %x is not online, can't send message!" % targetid)

                else:
                    targetclient = self.clients_by_uid[targetid]

                    msg = Message(targetclient, 3001)
                    msg.add_int("uid", uid)
                    msg.add_int("targetID", targetid)
                    msg.add_int("gameID", gameid)
                    msg.add_int("addOnSessionID", addonsess)
                    msg.add_int("MsgDataLen", msgdatalen)
                    msg.add_bin("MsgData", msgdata)
                    msg.add_int("AddOnFlag", 1)
                    self.enqueue(msg)

                    # chat message
            else:
                validate_msg(msg, ("uid", "targetID", "UserName", "status", "Text"))

                username = msg["UserName"]
                status = di(msg["status"])
                text = msg["Text"]

                logger.info("user %x with username %s sent a message targetid %x  status %x  text %s" % (
                uid, username, targetid, status, text))

                msg = Message(client, 1, True)
                self.enqueue(msg)

                if targetid not in self.clients_by_uid:
                    logger.info("user with uid %x is not online, can't send message!" % targetid)

                else:
                    targetclient = self.clients_by_uid[targetid]

                    msg = Message(targetclient, 3001)
                    msg.add_int("uid", uid)
                    msg.add_int("targetID", targetid)
                    msg.add_str("UserName", username)
                    msg.add_int("status", status)
                    msg.add_str("Text", text)
                    self.enqueue(msg)


        elif cmdid == 3002:  # update block status? not implemented!
            validate_msg(msg, ("uid", "Block", "FakeStatus"))

            uid = di(msg["uid"])

            logger.warning(
                "user %x tried to update block status for user %x but we don't support it" % (client.uid, uid))

            msg = Message(client, 1, True)
            self.enqueue(msg)


        elif cmdid == 3006:  # user starts typing
            validate_msg(msg, ("state", "ChatID", "UID", "status", "targetID"))

            state = di(msg["state"])
            chatid = di(msg["ChatID"])
            source = di(msg["UID"])
            status = di(msg["status"])
            target = di(msg["targetID"])

            logger.info("user %x is typing, state %x  chatid %x  status %x  target %x" % (
            source, state, chatid, status, target))

            msg = Message(client, 1, True)
            self.enqueue(msg)

            if target not in self.clients_by_uid:
                logger.info("user with uid %x is not online, can't send typing status!" % target)

            else:
                targetclient = self.clients_by_uid[target]

                msg = Message(targetclient, 3006)
                msg.add_int("state", state)
                msg.add_int("ChatID", chatid)
                msg.add_int("UID", source)
                msg.add_int("status", status)
                msg.add_int("targetID", target)
                self.enqueue(msg)


        else:
            raise Exception("unknown command %d" % cmdid)

    def send_friends_status(self, uid):
        if uid not in self.clients_by_uid:
            logger.info("user with uid %x is not online, can't send friend status!" % uid)
            return

        client = self.clients_by_uid[uid]

        logger.info("preparing to send friend status for %x" % uid)

        # format of status struct - 5 or 6 dwords for each entry
        # 0 uid
        # 1 status
        # 2 sessionid
        # 3 IP
        # 4 port
        # 5 serverid (optional)

        count = 0
        data = b""
        for frienduid in self.usermgr.real_friends(uid):
            if frienduid in self.clients_by_uid:
                friendstatus = self.clients_by_uid[frienduid].status
            else:
                friendstatus = 0

            # this is OUR sessionid, not the friend's
            sessionid = client.sessionid

            # use server's IP and port since we pass through all messages
            ip = socket.inet_aton(self.ipaddrport[0])
            port = self.ipaddrport[1]

            # ip = socket.inet_aton("127.0.0.1")
            # port = 0

            data += struct.pack("<III4sII", frienduid, friendstatus, sessionid, ip, port, 1)
            count += 1

        if count != 0:
            msg = Message(client, 1005)
            msg.add_int("count", count)
            msg.add_bin("status", data)
            self.enqueue(msg)

    def send_single_user_status(self, friendid, subjectid):
        if friendid not in self.clients_by_uid:
            logger.info("user with uid %x is not online, can't send friend status for %x!" % (friendid, subjectid))
            return

        friendclient = self.clients_by_uid[friendid]

        if subjectid not in self.clients_by_uid:
            status = 0
        else:
            subjectclient = self.clients_by_uid[subjectid]
            status = subjectclient.status

        msg = Message(friendclient, 1006)  # send user status
        msg.add_int("userID", subjectid)
        msg.add_int("status", status)
        msg.add_int("sessionID", friendclient.sessionid)
        msg.add_int("serverID", 1)
        msg.add_bin("IP", socket.inet_aton(self.ipaddrport[0]))
        msg.add_int("Port", self.ipaddrport[1])

        if status == 4:
            msg.add_bin("GameIP", subjectclient.gameip)
            msg.add_bin("GamePort", subjectclient.gameport)
            msg.add_str("Game", subjectclient.game)

        self.enqueue(msg)

    def send_friend_request(self, client, friendid):
        friendid, email, username, firstname, lastname = self.usermgr.get_user_by_uid(friendid)

        msg = Message(client, 1015)  # friend user request
        msg.add_int("uid", friendid)
        msg.add_str("email", email)
        msg.add_str("UserName", username)
        msg.add_str("FirstName", firstname)
        msg.add_str("LastName", lastname)

        self.enqueue(msg)

    def send_userinfo(self, clientuid, uid):
        if clientuid not in self.clients_by_uid:
            logger.info("user with uid %x is not online, can't send info about uid %d!" % (clientuid, uid))
            return

        client = self.clients_by_uid[clientuid]
        uid, email, username, firstname, lastname = self.usermgr.get_user_by_uid(uid)

        msg = Message(client, 1009)
        msg.add_int("uid", uid)
        msg.add_str("UserName", username)
        msg.add_str("FirstName", firstname)
        msg.add_str("LastName", lastname)
        msg.add_str("Email", email)

        self.enqueue(msg)


srv = TrackerServer()
srv.run()