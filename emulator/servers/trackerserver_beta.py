import logging
import pprint
import secrets
import socket
import struct
import threading
import time
import traceback

import globalvars
# TODO replace with something faster

from config import get_config
from utilities import encryption
from utilities.database.base_dbdriver import Beta1_TrackerRegistry
from utilities.database.betatrackerdb import beta1_dbdriver, beta2_dbdriver
from utilities.networkhandler import UDPNetworkHandler
from utilities.tracker_utils import Message, Packet, Packet_Beta, di, parse_data, parse_size_prepended_value, validate_msg

config = get_config()

# logging.basicConfig(
#    format="%(asctime)s %(levelname)-8s %(message)s",
#    filename="logs/trackerserver_debug.log",
#    encoding="utf-8",
#    level=logging.DEBUG)

# console = logging.StreamHandler()
# console.setLevel(logging.INFO)
# console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
# logging.getLogger().addHandler(console)


from enum import IntEnum

class Status(IntEnum):
    OFFLINE = 0
    AWAY = 3
    INGAME = 4
    SNOOZE = 5

class Client:
    def __init__(self, addr, clientid, sessionid, seqnum, r_seqnum):
        self.staletime = None
        self.timeout = None
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


class TrackerServer(UDPNetworkHandler):

    def __init__(self, port, config):
        self.server_type = "TrackerServer"
        super(TrackerServer, self).__init__(config, int(port), self.server_type)  # Create an instance of NetworkHandler

        self.ipaddrport = (config["server_ip"], 1200)

        self.network_key = b"\x30\x81\x9d\x30\x0d\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01\x05\x00\x03\x81\x8b\x00\x30\x81\x87\x02\x81\x81\x00" + int(encryption.network_key.n).to_bytes(128, 'big') + b"\x02\x01\x11"

        # self.serversocket.settimeout(0.2)
        self.clients = {}

        # contains logged in clients
        self.clients_by_uid = {}
        self.log = logging.getLogger('trkrsrv')
        # Pending messages/packets
        self.pending = []
        self.pending_lock = threading.Lock()

        """self.do_sends_thread = threading.Thread(target = self.do_sends_loop)
        self.do_sends_thread.daemon = True  # Optional: makes the thread exit when the main thread exits
        self.do_sends_thread.start()"""
        self.isbeta1 = False
        self.isbeta_tracker = True  # beta 1 / beta 2
        self.isretail = False
        self.usermgr = beta2_dbdriver(config)  # beta 2 / 2004



    def handle_client(self, data, addr):
        # data, addr = self.serversocket.recvfrom(16384)
        clientid = str(addr) + ": "
        self.log.info(clientid + "Connected to Tracker Server")
        if globalvars.record_ver == 0:  # 2002/beta 1
            self.isbeta1 = True
            self.usermgr = beta1_dbdriver(config)
        elif globalvars.record_ver < 1:  # 2004
            self.isbeta_tracker = False

        self.handle_incoming(data, addr)

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
                    self.log.info(f"removed stale client uid {client.uid:x}")

                del self.clients[addr]
                self.log.info(f"removed stale client addr {addr}")

                for friendid in self.usermgr.real_friends(client.uid):
                    self.send_single_user_status(friendid, client.uid)

    def enqueue(self, msg):
        # Do not increase seqnum for acks
        if msg.cmdid != 1:
            msg.client.seqnum += 1

        # Since we are sending messages directly, we can prepare and send the message immediately
        if self.isbeta_tracker:
            data = msg.getpacket_beta()
        else:
            data = msg.getpacket()

        self.serversocket.sendto(data, msg.client.addr, to_log = False)
        self.log.info(f"Sending message to {msg.client.addr} with id {msg.cmdid:d}")

    def handle_incoming(self, data, addr):
        #self.log.debug(f"received from {addr}: {data.hex()}")

        try:
            pkt = Packet_Beta(data)
            self.isbeta_tracker = True
        except:
            try:
                pkt = Packet(data)
                self.isbeta_tracker = False
                self.isbeta1 = False
                self.isretail = True
            except:
                self.log.error(f"Could not determine tracker packet type (beta1/beta2 or retail 2004) from {addr}: {data.hex()}")
                return

        self.log.debug(f"packet header {pkt.clientid:d} {pkt.sessionid:d} {pkt.seqnum:d} {pkt.seqack:d}")

        if globalvars.record_ver == 1:
            if pkt.packetnum != 1 or pkt.totalpackets != 1:
                self.log.error("multipacket not supported yet")

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
            self.log.info(f"client {client.clientid:x} is resetting connection?")
            client.clientid = pkt.clientid
            if pkt.seqnum != 1 or pkt.seqack != 0:
                self.log.error("bad values on connection reset")

            client.sessionid = pkt.sessionid
            client.seqnum = 1
            client.expected = 1
            client.ackd = 0
            client.queue = {}

        if pkt.seqnum < client.expected:
            self.log.warning(f"duplicate arrived late {pkt.seqnum:d} {client.expected:d}")

            # ugly hack to ensure we insta-send the response the other side probably missed
            # seems to happen when user is loading into a level in a game?
            found = False
            for index, (curr_attempt, sched_time, msg) in enumerate(self.pending):
                if msg.client.clientid == client.clientid and msg.reply_to == pkt.seqnum:
                    self.log.warning(f"forcing instant resend of message seqnum {msg.seqnum:d}")
                    self.pending[index] = (curr_attempt + 1, 0, msg)
                    found = True
                    break

            # if not found, send
            if not found:
                self.log.warning("forcing instant ack message")
                msg = Message(client, 1, True)
                self.enqueue(msg)

            return

        if pkt.seqnum in client.queue:
            self.log.warning(f"duplicate packet {pkt.seqnum:d} {client.queue}")
            return

        client.queue[pkt.seqnum] = pkt

        while client.expected in client.queue:
            try:
                seqnum = client.expected
                self.handle_msg(client, client.queue[seqnum])
                del client.queue[seqnum]
                client.expected += 1
            except:
                break

    def handle_msg(self, client, pkt):

        if self.isbeta_tracker:
            msg = parse_data(pkt.data[0x16:])
            cmdid = di(msg["_id"])
        else:
            msg = parse_data(pkt.data[0x0E:])
            cmdid = struct.unpack("<H", pkt.data[0x0C:0x0E])[0]

        self.log.info(f"received packet with id {cmdid:d} from uid {client.uid:x} address {client.addr}")

        self.log.debug("")

        client.r_seqnum = pkt.seqnum

        if pkt.seqack < client.ackd:
            self.log.error(f"bad seqack {pkt.seqack}, {client.ackd}")

        client.ackd = pkt.seqack

        if cmdid == 1:
            # ACK has id 1 and might have zero as sessionid, early return, we already handled ack
            return

        if (cmdid == 2001 and not self.isbeta1) or (cmdid == 2002 and self.isbeta1):
            sessionID_OK = self.check_sessionid(client, cmdid, pkt)
            if not sessionID_OK:
                return
        try:
            if cmdid == 2001:  # pre-login
                if not self.isbeta1:
                    self.pre_login(client, msg)
                else:
                    self.create_user(client, msg)

            elif cmdid == 2002:  # login
                if not self.isbeta1:
                    self.login(client, msg, pkt)
                else:
                    self.beta1_pre_login(client, msg)

            elif cmdid == 2003:  # Login Challange Response (Beta 1 Tracker Only)
                self.login(client, msg)

            elif cmdid == 2004:  # search for users
                if not self.isbeta1:
                    self.user_search(client, msg)
                else:  # Beta 1 Ping
                    msg = Message(client, 1008, True)  # 1008 = pingack
                    self.enqueue(msg)

            elif cmdid == 2005:  # status change
                if not self.isbeta1:
                    self.status_change(client, msg)
                else:
                    self.beta1_user_search(client, msg)

            elif cmdid == 2006:  # respond to friend request from other user
                if not self.isbeta1:
                    self.ack_friend_request(client, msg)
                else:
                    self.status_change(client, msg)

            elif cmdid == 2007:  # friendship reqest
                if not self.isbeta1:
                    self.friend_request(client, msg)
                else:
                    self.beta1_validate_user(client, msg)

            elif cmdid == 2008:  # get friend info
                if not self.isbeta1:
                    self.friend_info(client, msg)
                else:
                    self.ack_friend_request(client, msg)

            elif cmdid == 2009:  # change user info
                if not self.isbeta1:
                    self.user_info_change(client, msg)
                else:
                    self.friend_request(client, msg)

            elif cmdid == 2010:  # forward for user
                if not self.isbeta1:
                    self.forward_message(client, msg)
                else:
                    self.friend_info(client, msg)

            elif cmdid == 2011:  # Beta1 setinfo
                self.user_info_change(client, msg)

            elif cmdid == 2012:  # Beta1 client message
                # According to HL2 Beta Tracker Source code, this is not used!
                pass

            elif cmdid == 2013:  # Beta1 message reroute
                self.forward_message(client, msg)

            elif cmdid == 3001:  # message between users, normally chat
                self.chat_messages(client, msg)

            elif cmdid == 3002:  # update block status? not implemented!
                self.block_user(client, msg)
            elif cmdid == 3003:  # Initiate multi-user chatroom
                #contains UID and ChatID
                pass
            elif cmdid == 3004:  # invite to chatroom  / multichat add user
                # Contains UserName, IP and Port or
                # silent, UID, ChatID, FriendID, UserName, IP and Port
                pass
            elif cmdid == 3005:  # user left chatroom
                #UID, Status, ChatID, FriendID, targetID
                pass
            elif cmdid == 3006:  # user starts typing
                self.user_action(client, msg)

            else:
                self.log.error(f"unknown command {cmdid:d}")
        except Exception as e:
            self.log.error(e)

    def check_sessionid(self, client, cmdid, pkt):
        if cmdid == 2001:
            if pkt.sessionid != 0:
                self.log.error("bad sessionid for connect?")
                return False
            return True
        else:
            if not client.init:
                self.log.warning(f"clientid {client.clientid:d} hasn't been initialized, sending reset")
                msg = Message(client, 1004)
                msg.add_int("minTime", 0)
                msg.add_int("maxTime", 1)
                if not self.isbeta_tracker:
                    msg.add_int("reason", 8)
                self.enqueue(msg)

            # FIXME BEN THIS SEEMS TO RAISE WHEN CLICKING OK ON USER DETAILS DIALOG, EVEN THOUGH ID'S MATCH, WTF?
            if client.sessionid != pkt.sessionid:
                self.log.error(f"SessionID Does not match! {client.sessionid} != {pkt.sessionid}")  # self.log.error("bad sessionid", client.sessionid, pkt.sessionid)
            return True

    def user_action(self, client, msg):
        #validate_msg(msg, ("state", "ChatID", "UID", "status", "targetID"))
        state = di(msg["state"])
        chatid = di(msg["ChatID"])
        source = di(msg["UID"])
        status = di(msg["status"])
        target = di(msg["targetID"])
        self.log.info(f"user {source:x} is typing, state {state:x}  chatid {chatid:x}  status {status:x}  target {target:x}")
        msg = Message(client, 1, True)
        self.enqueue(msg)
        if target not in self.clients_by_uid:
            self.log.info(f"user with uid {target:x} is not online, can't send typing status!")

        else:
            targetclient = self.clients_by_uid[target]

            msg = Message(targetclient, 3006)
            msg.add_int("state", state)
            msg.add_int("ChatID", chatid)
            msg.add_int("UID", source)
            msg.add_int("status", status)
            msg.add_int("targetID", target)
            self.enqueue(msg)

    def block_user(self, client, msg):
        # validate_msg(msg, ("uid", "Block", "FakeStatus"))
        uid = di(msg["uid"])
        self.log.warning(f"user {client.uid:x} tried to update block status for user {uid:x} but we don't support it")
        msg = Message(client, 1, True)
        self.enqueue(msg)

    def chat_messages(self, client, msg):
        """
2024-11-09 14:46:01     trkrsrv       WARNING  (Retail) decrypted:
b'\x05\xf2q\\Y\x15jVlT\n\x01\xb9\x0b
\x05uid\x00\x04\x00\x01\x00\x00\x00
\x05targetID\x00\x04\x00\x03\x00\x00\x00
\x01gameID\x00\x0e\x00ValveCheckers\x00
\x05addOnSessionID_lo\x00\x04\x00\x00\x00\x00\x00
\x05addOnSessionID_hi\x00\x04\x00\x00\x00\x00\x00
\x05AddOnMsgID\x00\x04\x00\x0f\x00\x00\x00
\x05MsgDataLen\x00\x04\x00\x00\x00\x00\x00
\x05AddOnFlag\x00\x04\x00\x01\x00\x00\x00\x00'
2024-11-09 14:46:01     trkrsrv       WARNING  (Retail) decrypted:
b'\x05\xf2q\\Y\x15jVlU\n\x02\xb9\x0b
\x05uid\x00\x04\x00\x01\x00\x00\x00
\x05targetID\x00\x04\x00\x03\x00\x00\x00
\x01gameID\x00\x0e\x00ValveCheckers\x00
\x05addOnSessionID_lo\x00\x04\x00\xe8\x03\x00\x00
\x05addOnSessionID_hi\x00\x04\x00\x01\x00\x00\x00
\x05AddOnMsgID\x00\x04\x00\x03\x00\x00\x00
\x05MsgDataLen\x00\x04\x00P\x00\x00\x00
\x05MsgData\x00P\x00
\x05hostID\x00\x04\x00\x01\x00\x00\x00
\x01inviteName\x00\x05\x00test\x00
\x05hostNetInfo\x00 \x00\x01\x00\x00\x00\x15jVl\x8b8\x05r\xb4\x03\xa8\xc0\x7fi\x00\x00\xdc\xcd\xa3\x03\xa0p\xc2\x04\xd0\xcd\xa3\x03
\x05AddOnFlag\x00\x04\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        """
        try:
            if not self.isbeta_tracker:
                uid = di(msg["uid"])
                targetid = di(msg["targetID"])
            else:
                uid = di(msg["rID"])
                targetid = di(msg["rUserID"])
            # addon message (builtin games, other things?)
            if "AddOnFlag" in msg:
                #try:
                #    pass
                #    # validate_msg(msg, ("uid", "targetID", "gameID", "addOnSessionID", "MsgDataLen", "MsgData", "AddOnFlag"))
                #except:
                #    is_retail = True
                #    # validate_msg(msg, ("uid", "targetID", "gameID", "addOnSessionID_lo", "addOnSessionID_hi", "AddOnMsgID", "MsgDataLen", "MsgData", "AddOnFlag"), ("hostID", "inviteName", "hostNetInfo"))
                if not self.isbeta_tracker:
                    gameid = msg["gameID"]
                else:
                    gameid = di(msg["gameID"])
                if not self.isbeta_tracker:
                    addonsess = di(msg["addOnSessionID_lo"])
                    addonsess_hi = di(msg["addOnSessionID_hi"])
                    msgid = di(msg["AddOnMsgID"])
                else:
                    addonsess = di(msg["addOnSessionID"])
                addonflag = di(msg["AddOnFlag"])
                msgdatalen = di(msg["MsgDataLen"])
                if msgdatalen > 0:
                    msgdata = msg["MsgData"]

                self.log.info(f"user {uid:x} sent addon message targetid {targetid:x}  gameid {gameid}  sessionid {addonsess:d}  msg size {msgdatalen:d}")

                msg = Message(client, 1, True)
                self.enqueue(msg)

                if targetid not in self.clients_by_uid:
                    self.log.info(f"user with uid {targetid:x} is not online, can't send message!")
                else:
                    targetclient = self.clients_by_uid[targetid]
                    """b'\x05kn|n\x0fi\xfa\xb3\x1c\x0e\x00\xb9\x0b
                    \x05uid\x00\x04\x00\x01\x00\x00\x00
                    \x05targetID\x00\x04\x00\x04\x00\x00\x00
                    \x01gameID\x00\x0e\x00ValveCheckers\x00
                    \x05addOnSessionID_lo\x00\x04\x00\xe8\x03\x00\x00
                    \x05addOnSessionID_hi\x00\x04\x00\x01\x00\x00\x00
                    \x05AddOnMsgID\x00\x04\x00\xf7\x01\x00\x00
                    \x05MsgDataLen\x00\x04\x00\x00\x00\x00\x00
                    \x05AddOnFlag\x00\x04\x00\x01\x00\x00\x00\x00'"""
                    msg_send = Message(targetclient, 3001)
                    msg_send.add_int("uid", uid)
                    msg_send.add_int("targetID", targetid)

                    if not self.isbeta_tracker:
                        msg_send.add_str("gameID", gameid)
                        msg_send.add_int("addOnSessionID_lo", addonsess)
                        msg_send.add_int("addOnSessionID_hi", addonsess_hi)
                        msg_send.add_int("AddOnMsgID", msgid)
                    else:
                        msg_send.add_int("gameID", gameid)
                        msg_send.add_int("addOnSessionID", addonsess)
                    msg_send.add_int("MsgDataLen", msgdatalen)
                    if msgdatalen > 0:

                        msg_send.add_bin("MsgData", msgdata)
                    msg_send.add_int("AddOnFlag", addonflag)
                    self.enqueue(msg_send)

                # chat message
            else:
                rdata = None
                try:
                    # validate_msg(msg, ("uid", "targetID", "UserName", "status", "Text"))
                    username = msg["UserName"]
                    status = di(msg["status"])
                    text = msg["Text"]
                except:

                    rdata = msg["rData"]
                    msg2 = parse_data(rdata + b"\x00", True)
                    for key in msg2:
                        datatype, value = msg2[key]
                        self.log.warning(f"    {key} {datatype:d} {value}")
                    username = msg2['UserName'][1]

                    status = 1
                    text = bytes(msg2['Text'][1])

                self.log.info(f"user {uid:x} with username {username} sent a message targetid {targetid:x}  status {status:x}  text {text}")

                msg = Message(client, 1, True)
                self.enqueue(msg)

                if targetid not in self.clients_by_uid:
                    self.log.info(f"user with uid {targetid:x} is not online, can't send message!")

                else:
                    targetclient = self.clients_by_uid[targetid]

                    msg = Message(targetclient, 3001)
                    msg.add_int("uid", uid)
                    msg.add_int("targetID", targetid)
                    msg.add_str("UserName", username)
                    msg.add_int("status", status)
                    msg.add_str("Text", text)

                    self.enqueue(msg)
        except Exception as e:
            # Log the exception message
            self.log.error("An error occurred: %s", e)
            # Log the traceback
            self.log.error("Traceback:\n%s", traceback.format_exc())

    """b'\x05\xfb\xced2\xdc\xb5\xc5\x02\x07\x0b\x00\xda\x07
    \x05rID\x00\x04\x00\xb9\x0b\x00\x00
    \x05rUserID\x00\x04\x00\x01\x00\x00\x00
    \x05rSessionID\x00\x04\x00\xdc\xb5\xc5\x02
    \x05rServerID\x00\x04\x00\x01\x00\x00\x00
    \x05rData\x00M\x00 <-- 109 bytes
    \x05uid\x00\x04\x00\x02\x00\x00\x00
    \x05targetID\x00\x04\x00\x01\x00\x00\x00
    \x01UserName\x00\r\x00penisman3000\x00
    \x05status\x00\x04\x00\x01\x00\x00\x00
    \x01Text\x00\x03\x00hi\x00\x00\x00\x00\x00\x00\x00\x00\x00'"""

    def forward_message(self, client, msg):
        # validate_msg(msg, ("rID", "rUserID", "rSessionID", "rServerID", "rData"))
        if self.isbeta_tracker:
            rid = di(msg["rID"])
            ruserid = di(msg["rUserID"])
            rsessionid = di(msg["rSessionID"])
            rserverid = di(msg["rServerID"])
            rdata = msg["rData"]

            self.log.warning("forwarding message encountered id %d  uid %x  sessionid %d  serverid %d" % (
                    rid, ruserid, rsessionid, rserverid))
            msg2 = parse_data(rdata + b"\x00", True)
            for key in msg2:
                datatype, value = msg2[key]
                self.log.warning("    %s %d %s" % (key, datatype, value))

            msg = Message(client, 1, True)
            self.enqueue(msg)

            if ruserid not in self.clients_by_uid:
                self.log.info("user with uid %x is not online, can't send forwarded message!" % ruserid)

            else:
                targetclient = self.clients_by_uid[ruserid]

                msg = Message(targetclient, rid)
                msg.msg = rdata
                self.enqueue(msg)
        else:
            # the following code works only on retail tracker
            #validate_msg(msg, ("rID", "rUserID", "rSessionID", "rServerID", "rData"))
            rid = di(msg["rID"])
            ruserid = di(msg["rUserID"])
            rsessionid = di(msg["rSessionID"])
            rserverid = di(msg["rServerID"])
            rdata = msg["rData"]
            self.log.warning(f"forwarding message encountered id {rid:d}  uid {ruserid:x}  sessionid {rsessionid:d}  serverid {rserverid:d}")
            msg2 = parse_data(rdata + b"\x00", True)
            for key in msg2:
                datatype, value = msg2[key]
                self.log.warning(f"    {key} {datatype:d} {value}")

            ackmsg = Message(client, 1, True)
            self.enqueue(ackmsg)

            targetclient = self.clients_by_uid[ruserid]
            if rid == 3001: #forward messages from users
                username = msg2['UserName'][1]
                status = di(msg2['status'][1])
                text = bytes(msg2['Text'][1])

                msg = Message(targetclient, 3001)
                msg.add_int("uid", client.uid)
                msg.add_int("targetID", ruserid)
                msg.add_str("UserName", username)
                msg.add_int("status", status)
                msg.add_str("Text", text)
            elif rid == 1013: #forward game messages:
                """forwarding message encountered id 1013  uid 1  sessionid 4149873363  serverid 1
                uid 5 b'\x06\x00\x00\x00'
                targetID 5 b'\x01\x00\x00\x00'
                gameID 1 b'ValveCheckers'
                addOnSessionID_lo 5 b'\xe8\x03\x00\x00'
                addOnSessionID_hi 5 b'\x01\x00\x00\x00'
                AddOnMsgID 5 b'\x04\x00\x00\x00'
                MsgDataLen 5 b'E\x00\x00\x00'
                MsgData 5 b'\x05Response\x00\x04\x00\x01\x00\x00\x00\x05oppID\x00\x04\x00\x06\x00\x00\x00\x01oppName\x00\x0b\x00mntlmentos\x00\x05AppDataLen\x00\x04\x00\x00\x00\x00\x00'
                AddOnFlag 5 b'\x01\x00\x00\x00'"""
                msg = Message(targetclient, 1013)
                msg.add_int("uid", client.uid)
                msg.add_int("targetID", ruserid)
                msg.add_str("gameID", msg2['gameID'][1])
                msg.add_int("addOnSessionID_lo", di(msg2['addOnSessionID_lo'][1]))
                msg.add_int("addOnSessionID_hi", di(msg2['addOnSessionID_hi'][1]))
                msg.add_int("AddOnMsgID", di(msg2['AddOnMsgID'][1]))
                msg.add_int("MsgDataLen", di(msg2['MsgDataLen'][1]))
                if di(msg2['MsgDataLen'][1]) != 0:
                    msg.add_bin("MsgData", msg2['MsgData'][1])
                msg.add_int("AddOnFlag", di(msg2['AddOnFlag'][1]))


            self.enqueue(msg)
        """uid 5 b'\x02\x00\x00\x00'
targetID 5 b'\x01\x00\x00\x00'
UserName 1 b'penisman3000'
status 5 b'\x01\x00\x00\x00'
Text 1 b'gotta get donald duck to run the cuntry'"""
    def user_info_change(self, client, msg):
        # validate_msg(msg, ("uid", "UserName", "FirstName", "LastName"))
        uid = di(msg["uid"])
        if client.uid != uid:
            self.log.error(f"user {client.uid:x} tried to change info for another user {uid:x}!")
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

    def friend_info(self, client, msg):
        # FIXME we really should ensure that the user is 'authed' or accepted as a friend first
        # validate_msg(msg, ("uid",))
        uid = di(msg["uid"])
        self.log.info(f"requested info about uid {uid:x}")
        self.send_userinfo(client.uid, uid)

    def friend_request(self, client, msg):
        # validate_msg(msg, ("uid", "ReqReason"))
        targetuid = di(msg["uid"])
        reason = msg["ReqReason"]
        self.log.info(f"user {client.uid:x} requests friendship with {targetuid:x}, reason {reason}")
        self.usermgr.request_friend(client.uid, targetuid)
        msg = Message(client, 1, True)
        self.enqueue(msg)
        if targetuid in self.clients_by_uid:
            self.send_friend_request(self.clients_by_uid[targetuid], client.uid)

    def ack_friend_request(self, client, msg):
        # validate_msg(msg, ("targetID", "auth"))
        targetuid = di(msg["targetID"])
        auth = di(msg["auth"])

        if auth == 1:
            self.log.info(f"user {client.uid:x} acknowledged friend request from {targetuid:x}")
            #change both user and friend entries to relationship 3
            self.usermgr.accept_friend_request(client.uid, targetuid)
        else:
            self.log.error("refusing a friend request isn't implemented yet!")

        msg = Message(client, 1, True)
        self.enqueue(msg)
        # update new friend with our status and us with the friend's status
        self.send_single_user_status(client.uid, targetuid)
        self.send_single_user_status(targetuid, client.uid)

    def status_change(self, client, msg):
        # validate_msg(msg, ("status",), ("hrate", "GameIP", "GamePort", "Game"))
        client.status = di(msg["status"])
        self.log.info(f"uid {client.uid:x} changed status to {client.status:d}")
        if client.status == 4:  # ingame
            client.gameip = msg["GameIP"]
            client.gameport = msg["GamePort"]  # some weird format?
            client.game = msg["Game"]

            self.log.info(f"uid {client.uid:x} is playing a game: {client.game} on ip {socket.inet_ntoa(client.gameip)} port {client.gameport.hex()}")
        # user set status to offline, so remove from client uid mapping
        if client.status == 0:
            del self.clients_by_uid[client.uid]
            del self.clients[client.addr]
            self.log.info(f"uid {client.uid:d} logged off")
        if "hrate" in msg:
            hrate = di(msg["hrate"])
            self.log.info(f"got hrate {hrate:d}")
            client.update_timeout(hrate // 1000)
        msg = Message(client, 1, True)
        self.enqueue(msg)
        for friendid in self.usermgr.real_friends(client.uid):
            self.send_single_user_status(friendid, client.uid)

    def user_search(self, client, msg):
        # validate_msg(msg, ("uid", "Email", "UserName", "FirstName", "LastName"))

        # ignore search parameters for now, just return all users
        nsent = 0
        print(f"client id: {client.uid}")
        for row in self.usermgr.search_users():
            pprint.pprint(row)
            if client.uid != row[0]:

                msg = Message(client, 1011)  # search result
                msg.add_int("uid", row[0])
                msg.add_str("UserName", row[1])
                msg.add_str("FirstName", row[2])
                msg.add_str("LastName", row[3])
                self.enqueue(msg)
                nsent += 1

        if nsent == 0:
            print("Shouldnt have got here in user_search")
            msg = Message(client, 1, True)
            self.enqueue(msg)

    def beta1_user_search(self, client, msg):
        # validate_msg(msg, ("uid", "Email", "UserName", "FirstName", "LastName"))

        # ignore search parameters for now, just return all users
        nsent = 0

        for row in self.usermgr.search_users():
            if client.uid != row[0]:
                msg = Message(client, 1011)  # search result
                msg.add_int("uid", row[0])
                msg.add_str("Email", row[1])
                msg.add_str("UserName", row[2])
                msg.add_str("FirstName", row[3])
                msg.add_str("LastName", row[4])
                self.enqueue(msg)
                nsent += 1
            self.log.debug(f"User Search Results: UserID: {row[0]} Email: {row[1]}  UserName: {row[2]}  First Name: {row[3]}  Last Name: {row[4]}")

        if nsent == 0:
            msg = Message(client, 1, True)
            self.enqueue(msg)
    def login(self, client, msg, pkt):
        #if not self.isbeta1:
        #    # validate_msg(msg, ("challenge", "sessionID", "status", "build", "hrate", "ticket"), ("PlatformVer",))
        #else:
        #    # validate_msg(msg, ("challenge", "sessionID", "status", "build", "hrate"), ("PlatformVer",))
        try:
            self.log.info(f"Recieved login request: clientid: {pkt.clientid}, sessionid: {pkt.sessionid}, sequence: {pkt.seqnum}, acked sequence: {pkt.seqack}, unknown: {pkt.totalpackets}")
        except Exception as e:
            print(f"An exception occurred: {e}")

        challenge = di(msg["challenge"])
        sessionid = di(msg["sessionID"])
        status = di(msg["status"])
        build = di(msg["build"])
        hrate = di(msg["hrate"])

        if not self.isbeta1:
            # TODO Validate ticket properly
            #  Pretty sure the ticket is encrypted using the network public key
            ticket = parse_size_prepended_value(msg["ticket"])

        if "PlatformVer" in msg:
            platformver = di(msg["PlatformVer"])
        else:
            platformver = 0

        msg = Message(client, 1002)  # login OK

        if challenge != client.challenge:
            self.log.error("Bad Challenge")
            msg.cmdid = 1004
            msg.add_str("error", "Bad Challange.")
            self.enqueue(msg)
            return

        if sessionid != client.sessionid:
            self.log.error("Bad SessionID")
            msg.cmdid = 1004
            msg.add_str("error", "Bad SessionID.")
            self.enqueue(msg)
            return

        self.log.debug(f"User {client.email} build {build:d}  hrate {hrate:d}  PlatformVer {platformver:d}")

        if not self.isbeta1:
            uid = self.usermgr.auth(client.email, client.username)
        else:
            uid = client.uid #self.usermgr.auth(client.email, client.password)

        if not uid:
            self.log.warning(f"Email Address {client.email} Not Found!")
            msg.cmdid = 1004
            msg.add_str("error", "Email Address Not Found.")
            self.enqueue(msg)
            return

        self.log.info(f"authed user {client.email} with uid {uid:d}")
        try:
            client.uid = uid
            client.status = status
            self.clients_by_uid[client.uid] = client

            client.update_timeout(hrate // 1000)

            msg.add_int("status", status)

            if not self.isbeta1:
                msg.add_int("userID", client.uid)
                msg.add_int("sessionID", pkt.sessionid)
                msg.add_int("serverID", 1)
                msg.add_bin("IP", socket.inet_aton(client.addr[0]))
                msg.add_int("Port", client.addr[1])

            self.enqueue(msg)
        except Exception as e:
            self.log.debug(f"An exception occurred: {e}")

        self.log.info(f"Sending Tracker login OK message to user")

        # pending friend requests
        for friendid in self.usermgr.pending_friends(client.uid):
            self.log.info(f"user {client.uid:x} has pending friend request from {friendid:x}")
            self.send_friend_request(client, friendid)

        # send info about our friends' status
        self.send_friends_status(client.uid)

        # notify friends that we are online
        for friendid in self.usermgr.real_friends(client.uid):
            self.send_single_user_status(friendid, client.uid)

        # send usernames etc since they might have been updated
        for friendid in self.usermgr.get_friends_by_source(client.uid):
            self.send_userinfo(client.uid, friendid)

    def create_user(self, client, msg):
        """
            msg->ReadString("username", user.userName, 32);
            msg->ReadString("firstname", user.firstName, 32);
            msg->ReadString("lastname", user.lastName, 32);
            msg->ReadString("email", user.email, 128);
            msg->ReadString("password", user.password, 32);
        """
        # validate_msg(msg, ("username", "firstname", "lastname", "email", "password"))
        # uid can be nonzero if the client reconnects - should we skip the auth step if uid and clientid match?
        client.username = msg["username"]
        client.firstname = msg["firstname"]
        client.lastname = msg["lastname"]
        client.email = msg["email"]
        client.password = msg["password"]

        self.log.info(f"Create User Request for username {client.username}  email {client.email}")
        result = self.usermgr.create_user(client.username, client.email, client.firstname, client.lastname, client.password)

        msg = Message(client, 1010)
        msg.add_int("newUID", result)

        if not result:
            msg.cmdid = 1004
            self.log.error(f"Create User Request failed for username {client.username}  email {client.email}")
            error_str = "Server could not create user.\nEmail address already in usee.\nPlease try again at another time."
            msg.add_str("error", error_str)
        else:
            self.log.debug(f"Create User Request succeeded for username {client.username}  email {client.email}")

        self.enqueue(msg)

    def pre_login(self, client, msg):
        # validate_msg(msg, ("uid", "email", "status"), ("UserName", "FirewallWindow"))
        # uid can be nonzero if the client reconnects - should we skip the auth step if uid and clientid match?
        client.uid = di(msg["uid"])
        client.email = msg["email"]
        client.status = di(msg["status"])
        client.sessionid = 0
        if "UserName" in msg:
            client.username = msg["UserName"]
        else:
            client.username = client.email
        self.log.info(f"pre-login for uid {client.uid:d}  email {client.email}  status {client.status:d} username: {client.username}")
        new_sessionid = secrets.randbits(32)
        msg = Message(client, 1001)
        msg.add_int("sessionID", new_sessionid)
        if self.isbeta_tracker:
            client.challenge = secrets.randbits(32)
        else:
            client.challenge = 0 # retail sets this to 0 as technically this message is still session 0 until the client recieves the sessionid from the key/value in this packet

        msg.add_int("challenge", client.challenge)

        # TODO BEN move key to global codespace so it is calculated/done only a single time during init
        msg.add_kv(5, "key", self.network_key)
        if not self.isbeta_tracker:
            msg.unknownbyte = 1
        # b"0\x81\x9d0\r\x06\t*\x86H\x86\xf7\r\x01\x01\x01\x05\x00\x03\x81\x8b\x000\x81\x87\x02\x81\x81\x00\xb3\xb4g\xcd\xb8W\x8d\xe7\xdc\xabLx\x86\xb478\xa72*\x05M\x8d#>C\x85\xacD\xab\x00\x97[B'G\xafjw\xadP\xa2\x1aa\x8d}\x81\xbb\xdf\x99~`Z\xe8t\xd7BnV\x0c\x02\x8e\x152\xf6\xbd\n\x87\xa344\xcb\xe2\x1f\xde\xf4\xbfte\x1f+q\xe4\xc96Z\x1bX\x9a\x83\xfa+\xd9\xf1\x022a\xdf\xdaX\x87d\xf0r\x14A\x8ci\xfb\x19\xbc\x12k\xbbM\x00\x0f\xda\xc0SG\x81\x9c,G`\x01h'\x02\x01\x11")
        self.enqueue(msg)

        # first msg goes out with a sessionid of 0, now we put in the real sessionid
        client.sessionid = new_sessionid
        client.init = True

    def beta1_pre_login(self, client, msg):
        # validate_msg(msg, ("uid", "email", "password", "status"), ("UserName", "FirewallWindow"))
        # uid can be nonzero if the client reconnects - should we skip the auth step if uid and clientid match?
        client.uid = di(msg["uid"])
        client.email = msg["email"]
        client.password = msg["password"]
        client.status = di(msg["status"])
        client.sessionid = 0

        if client.email == "" or client.email == None:
            client.email = self.usermgr.auth(client.uid, client.password, True)
            msg = Message(client, 1012)
            msg.add_int("userID", client.uid)

        if "UserName" in msg:
            client.username = msg["UserName"]
        else:
            client.username = client.email

        self.log.info(f"pre-login for uid {client.uid:d}  email {client.email}  status {client.status:d}")
        new_sessionid = secrets.randbits(32)
        msg = Message(client, 1001)
        msg.add_int("sessionID", new_sessionid)
        client.challenge = secrets.randbits(32)

        msg.add_int("challenge", client.challenge)
        # msg.add_kv(5, "key", newkey)
        self.enqueue(msg)
        # first msg goes out with a sessionid of 0, now we put in the real sessionid
        client.sessionid = new_sessionid
        client.init = True

    def beta1_validate_user(self, client, msg):
        # validate_msg(msg, ("email", "password"))
        # uid can be nonzero if the client reconnects - should we skip the auth step if uid and clientid match?
        client.email = msg["email"]
        client.password = msg["password"]

        self.log.info(f"Validate user for email {client.email}")

        clientid = self.usermgr.auth(client.email, client.password)
        msg = Message(client, 1012)
        msg.add_int("userID", clientid)

        self.enqueue(msg)

    def beta1_heartbeat(self, client, data):
        msg = parse_data(data)
        status = di(msg["status"])
        self.log.debug(f"Heartbeat userid: {client.uid} status: {status}")

        update_game_info = False
        update_status_info = False

        if status != client.status:
            client.status = status
            update_status_info = True

        if status == Status.INGAME:
            ip = msg["GameIP"]
            port = msg["GamePort"]

            if ip != client.gameip or port != client.gameport:
                update_game_info = True
                client.game = msg["Game"]
                client.gameip = ip
                client.gameport = port
        else:
            # Clear the game info if they're not in a game
            client.gameip = 0
            client.gameport = 0
            client.game = ""

        # Check for heartbeat rate update
        if "hrate" in msg:
            heart_beat_rate_millis = di(msg["hrate"])
            client.update_timeout(heart_beat_rate_millis // 1000.0 + 30.0)

        if update_game_info or update_status_info:
            # 0 status is a log off message
            if client.status < Status.AWAY:
                # Log the user off the server
                self.beta1_logoff(client)
                return
            else:
                # Update the status in the DB
                #self.usermgr.update_details(client.uid, status = client.status, game_ip = client.gameip, game_port = client.gameport, game_type = client.game)

                # Tell the new status to friends
                self.send_friends_status(client.uid)

        # See if we need to update their status
        #if client.needs_firewall_update:
        #    # Send them a heartbeat with their new firewall window
        #    self.send_firewall_update(client)

        ## Check for messages
        #self.check_for_messages(client)


    def beta1_logoff(self, client):
        # Create a disconnect message
        msg = Message(client, 1004)
        self.log.debug(f"User: {client.uid} Logged Off")
        # Add minimum and maximum time parameters to the message
        msg.add_int("minTime", 5)
        msg.add_int("maxTime", 15)

        # Queue the message for sending, using the standard send path
        self.enqueue(msg)

    def send_friends_status(self, uid):
        if uid not in self.clients_by_uid:
            self.log.info(f"user with uid {uid:x} is not online, can't send friend status!")
            return

        client = self.clients_by_uid[uid]

        self.log.info(f"preparing to send friend status for {uid:x}")

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
            self.log.info(f"user with uid {friendid:x} is not online, can't send friend status for {subjectid:x}!")
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
        self.log.debug(f"send friend request: {friendid}, {email}, {username}, {firstname}, {lastname}")
        msg = Message(client, 1, True)
        self.enqueue(msg)
        msg = Message(client, 1015)  # friend user request
        msg.add_int("uid", friendid)
        msg.add_str("UserName", username)
        msg.add_str("FirstName", firstname)
        msg.add_str("LastName", lastname)

        self.enqueue(msg)

    def send_userinfo(self, clientuid, uid):
        """if clientuid not in self.clients_by_uid:
            self.log.info("user with uid %x is not online, can't send info about uid %d!" % (clientuid, uid))
            return"""

        client = self.clients_by_uid[clientuid]
        #if not self.isbeta1:
        uid, email, username, firstname, lastname = self.usermgr.get_user_by_uid(uid)
        self.log.debug(f"send user info: {uid}, {email}, {username}, {firstname}, {lastname}")

        msg = Message(client, 1009)
        msg.add_int("uid", uid)
        msg.add_str("UserName", username)
        msg.add_str("FirstName", firstname)
        msg.add_str("LastName", lastname)
        # beta 2 uses Email, retail uses email
        msg.add_str("email", email)
        msg.unknownbyte = 1
        #msg.msg += b'\x00\x00\x00\x00\x00\x00'
        self.enqueue(msg)