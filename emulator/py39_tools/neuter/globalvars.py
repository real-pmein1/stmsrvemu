import ipaddress
import os
import struct

from config import get_config

config = get_config()
main_script_dir = os.path.dirname(os.path.abspath(__file__))  # TODO REMOVE / UNUSED
local_ver = "0.80.RC1"
emu_ver = "0"
ui_ver = "0"
mdb_ver = "0"
update_exception1 = ""
update_exception2 = ""
clear_config = False  # TODO REMOVE / UNUSED
converting = "0"
checksum_temp_file = 0  # TODO REMOVE / UNUSED
server_net = None
mariadb_process = None
httpd_process = None
httpd_child_pid_list = []
use_webserver = config["use_webserver"].lower() == "true"
cs_region = "US"
cellid = 1
aio_server = False
peer_password = ""
dir_ismaster = "false"
# use_file_blobs = "true"
cs_applist = []  # TODO REMOVE / UNUSED
smtp_enable = "false"
force_email_verification = "false"
server_ip = ""
server_ip_b = b""
public_ip = ""
public_ip_b = b""
hide_convert_prints = False
ORIGINAL_PYTHON_EXECUTABLE = None
stop_server = False
ORIGINAL_CMD_ARGS = None
prepended_modifiers = []
appended_modifiers = []
tgt_version = "2"
# steam1_blob_sent = 0
record_ver = 0
steam_ver = 0
steamui_ver = 0
compiling_cdr = False
firstblob_eval = None
firstblob_timestamp = None
secondblob_timestamp = None
firstblob_hash = None
secondblob_hash = None
CURRENT_APPID_VERSION = ""

dedicated_server_appids = [4, 5, 153, 154, 203, 204, 205, 210, 310, 311, 313, 314, 524, 538, 560, 561, 562, 601, 602, 635, 740, 1203, 1204, 1213, 1241, 1253, 1254, 1273, 2144, 2145, 2403, 2404, 2740, 2741, 2912, 2915, 2916, 4207, 4240, 4270, 4922, 4940, 8680, 8710, 8730, 8770, 13180, 13181, 13182, 17505, 17515, 17525, 17535, 17575, 17585, 17705, 17718]
game_engine_file_appids = [0, 3, 7, 8, 200, 201, 212, 216, 217, 254, 255, 256, 257, 258, 264, 315, 316, 317, 322, 521, 572, 573, 1000, 1002, 1202, 1212, 1304, 1309, 1634, 1644, 2101, 2131, 2811, 4411, 4421, 6301, 6401, 6551, 6861, 6871, 6881, 7001, 7011, 7221, 7801, 7811, 8001, 8011, 10622, 10644, 13141, 16422, 17712]

# hl1serverlist = list(range(10000))
# hl1challengenum = 0
# hl2serverlist = list(range(10000))
# hl2challengenum = 0
# rdkfserverlist = list(range(10000))
# rdkfchallengenum = 0

def to_c_string_format(s):
    """This function is used to convert a normal string into a C-style string (null byte between each character)
       It is used by the Beta1 clients
    :param s: A string to be converted
    :return: A string"""
    if isinstance(s, bytes):
        s = s.decode('latin-1')
    # Convert each character in the string to its c-string format representation (with null byte between each character)
    return b''.join(struct.pack('H', ord(char)) for char in s)


if config["http_ip"] != "":
    octal_ip = config["http_ip"]
elif config["public_ip"] != "0.0.0.0":
    octal_ip = config["public_ip"]
else:
    octal_ip = config["server_ip"]  # IF WE ARE ON LAN, AND HAVE NO PUBLIC_IP OR HTTP_IP, WOULDNT THIS MAKE SENSE?

# TODO fix steamclient.dll ip address string neutering (spaces are actually null bytes):
#  127.0.0.1   207.173.176.215 172.16.3.19 172.16.3.18 172.16.3.17 172.16.3.16 172.16.3.15 172.16.3.14 172.16.3.12 172.16.3.6  72.165.61.188   72.165.61.187   72.165.61.186   72.165.61.185   208.111.133.85  208.111.133.84  68.142.91.35    68.142.91.34    208.111.171.83  208.111.171.82  208.111.158.53  208.111.158.52  69.28.145.171   69.28.145.170
ip_addresses = (
        b"65.122.178.71",
        b"67.132.200.140",
        b"68.142.64.162",
        b"68.142.64.163",
        b"68.142.64.164",
        b"68.142.64.165",
        b"68.142.64.166",
        b"69.28.140.245",
        b"69.28.140.246",
        b"69.28.140.247",
        b"69.28.148.250",
        b"69.28.151.178",
        b"69.28.152.198",
        b"69.28.153.82",
        b"69.28.156.250",
        b"69.28.191.84",
        b"68.142.64.162",
        b"68.142.64.163",
        b"68.142.64.164",
        b"68.142.64.165",
        b"68.142.64.166",
        b"68.142.72.250",
        b"68.142.88.34",
        b"68.142.91.34",
        b"68.142.91.35",
        b"69.28.145.170",
        b"69.28.145.171",
        b"69.28.151.178",
        b"69.28.153.82",
        b"72.165.61.141",
        b"72.165.61.142",
        b"72.165.61.143",
        b"72.165.61.161",
        b"72.165.61.162",
        b"72.165.61.185",
        b"72.165.61.186",
        b"72.165.61.187",
        b"72.165.61.188",
        b"72.165.61.189",
        b"72.165.61.190",
        b"86.148.72.250",
        b"87.248.196.117",
        b"87.248.196.194",
        b"87.248.196.195",
        b"87.248.196.196",
        b"87.248.196.197",
        b"87.248.196.198",
        b"87.248.196.199",
        b"87.248.196.200",
        # "127.0.0.1",
        # b"172.16.3.6",
        # b"172.16.3.10",
        # b"172.16.3.11",
        # b"172.16.3.12",
        # b"172.16.3.13",
        # b"172.16.3.14",
        # b"172.16.3.15",
        # b"172.16.3.16",
        # b"172.16.3.17",
        # b"172.16.3.18",
        # b"172.16.3.19",
        # b"172.16.3.23",
        # b"172.16.3.24",
        # b"172.16.3.26",
        # b"172.16.3.27",
        # b"172.16.3.28",
        # b"172.16.3.29",
        # b"172.16.3.30",
        # b"172.16.3.31",
        # b"172.16.3.32",
        # b"172.16.3.34",
        # b"172.16.3.39",
        # b"172.16.3.72",
        b"193.34.50.6",
        b"194.124.229.14",
        b"207.173.176.210",
        b"207.173.176.215",
        b"207.173.176.216",
        b"207.173.177.11",
        b"207.173.177.12",
        b"207.173.178.127",
        b"207.173.178.178",
        b"207.173.178.194",
        b"207.173.178.196",
        b"207.173.178.198",
        b"207.173.178.214",
        b"207.173.178.216",
        b"207.173.179.14",
        b"207.173.179.87",
        b"207.173.179.151",
        b"207.173.179.168",
        b"207.173.179.179",
        b"208.111.133.84",
        b"208.111.133.85",
        b"208.111.158.52",
        b"208.111.158.53",
        b"208.111.171.82",
        b"208.111.171.83",
        b"213.202.254.131",
        b"217.64.127.2",
        b"888.888.888.888",
        b"888.888.888.889",
        b"888.888.888.890",
        b"888.888.888.891",
        b"63.251.171.132",)

extraips = (
        b"207.173.177.12:27010",
        b"207.173.177.11:27010",
        b"207.173.177.10:27010",
        b"207.173.177.12:27011",
        b"207.173.177.11:27011",
        b"207.173.177.10:27011"
)

loopback_ips = (
        b"127.0.0.2",
        b"127.0.0.2"
)


def get_octal_ip(islan, iscommunity = False):
    http_ip = config["http_ip"] if iscommunity is False else config["community_ip"]
    http_domainname = config["http_domainname"] if iscommunity is False else config["community_domainname"]
    server_ip = config["server_ip"]
    public_ip = config["public_ip"]
    if http_ip != "":
        octal_ip = http_ip if http_domainname == "" else http_domainname
    elif http_domainname != "":
        if use_webserver:
            if islan:
                octal_ip = server_ip
            else:
                octal_ip = http_domainname
        else:
            octal_ip = http_domainname
    else:
        if islan:
            octal_ip = server_ip
        else:
            octal_ip = public_ip
    return octal_ip


def replace_string_cdr(islan):
    octal_ip = get_octal_ip(islan)

    replace_string_cdr = (
            (b'http://storefront.steampowered.com/marketing',
             b"http://" + octal_ip.encode('latin-1') + b"/marketing",
             b"Messages URL 1"),
            (b'http://www.steampowered.com/marketing',
             b"http://" + octal_ip.encode('latin-1') + b"/marketing",
             b"Messages URL 2"),
            (b'http://storefront.steampowered.com/Steam/Marketing',
             b"http://" + octal_ip.encode('latin-1') + b"/Steam/Marketing",
             b"Messages URL 3"),
            (b'http://www.steampowered.com/Steam/Marketing/',
             b"http://" + octal_ip.encode('latin-1') + b"/Steam/Marketing/",
             b"Messages URL 4"),
            (b'http://steampowered.com/Steam/Marketing/',
             b"http://" + octal_ip.encode('latin-1') + b"/Steam/Marketing/",
             b"Messages URL 5"),
            (b'http://storefront.steampowered.com/Marketing/',
             b"http://" + octal_ip.encode('latin-1') + b"/Steam/Marketing/",
             b"Messages URL 6"),
            (b'http://www.steampowered.com/index.php?area=news',
             b"http://" + octal_ip.encode('latin-1') + b"/index.php?area=news",
             b"News URL"),
            (b'http://www.steampowered.com/index.php?',
             b"http://" + octal_ip.encode('latin-1') + b"/index.php?",
             b"Index URL"),
            (b'http://storefront.steampowered.com/v/?client=1',
             b"http://" + octal_ip.encode('latin-1') + b"/v/?client=1",
             b"Storefront URL 1"),
            (b'http://storefront.steampowered.com/v2/',
             b"http://" + octal_ip.encode('latin-1') + b"/v2/",
             b"Storefront URL 1"),
            (b'http://store.steampowered.com',
             b"http://" + octal_ip.encode('latin-1'),
             b"Storefront URL 3"),
            # (b'http://www.steampowered.com/',
            # b"http://" + octal_ip.encode('latin-1'),
            # b"Steampowered.com URL"),
    )
    return replace_string_cdr


def replace_string_name_space(islan, is2003_gcf = False):
    octal_ip = get_octal_ip(islan)
    conn_ip = config["server_ip"] if islan else config["public_ip"]
    trk_ip = config["server_ip"] if islan else (config["tracker_ip"] if config["tracker_ip"] != "" else config["public_ip"])

    octal_ip = octal_ip.encode('latin-1')
    conn_ip = conn_ip.encode('latin-1')
    trk_ip = trk_ip.encode('latin-1')
    trk_port = config['tracker_server_port'].encode('latin-1')
    hl1master_port = config['masterhl1_server_port'].encode('latin-1')
    vac1_port = config['vac_server_port'].encode('latin-1')

    replace_string_space = (
            (b'<h1><img src="http://steampowered.com/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam Account Information</h1>',
             b'<h1><img src="http://' + octal_ip + b'/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam Account Information</h1>',
             b"New account logo 1"),
            (b'<img src="http://steampowered.com/img/print.gif" height="32" width="32" alt="STEAM" align="absmiddle"> <a href="javascript:window.print();">Click here to print this page now</a>',
             b'<img src="http://' + octal_ip + b'/img/print.gif" height="32" width="32" alt="STEAM" align="absmiddle"> <a href="javascript:window.print();">Click here to print this page now</a>',
             b"New account logo 2"),
            (b'For more information about Steam accounts, see <a href="http://steampowered.com/?area=support">the support page</a>.<br><br>',
             b'For more information about Steam accounts, see <a href="http://' + octal_ip + b'/?area=support">the support page</a>.<br><br>',
             b"New account logo 3"),
            (b"http://steampowered.com/img/steam_logo_onwhite.gif",
             b"http://" + octal_ip + b"/img/steam_logo_onwhite.gif",
             b"New account logo 4"),
            (b"http://steampowered.com/img/print.gif",
             b"http://" + octal_ip + b"/img/print.gif",
             b"New account logo 5"),
            (b'<h1><img src="http://steampowered.com/img/steam_logo_whiteongreen.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam Account Information</h1>',
             b'<h1><img src="http://' + octal_ip + b'/img/steam_logo_whiteongreen.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam Account Information</h1>',
             b"New account logo 6"),
            (b'<img src="http://steampowered.com/img/print_ongreen.gif" height="32" width="32" alt="STEAM" align="absmiddle"> <a href="javascript:window.print();">Click here to print this page now</a>',
             b'<img src="http://' + octal_ip + b'/img/print_ongreen.gif" height="32" width="32" alt="STEAM" align="absmiddle"> <a href="javascript:window.print();">Click here to print this page now</a>',
             b"New account logo 7"),
            (b"http://steampowered.com/img/steam_logo_whiteongreen.gif",
             b"http://" + octal_ip + b"/img/steam_logo_whiteongreen.gif",
             b"New account logo 8"),
            (b"http://steampowered.com/img/print_ongreen.gif",
             b"http://" + octal_ip + b"/img/print_ongreen.gif",
             b"New account logo 9"),
            (b'<h1><img src="http://steampowered.com/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam - Receipt for credit card purchase</h1>',
             b'<h1><img src="http://' + octal_ip + b'/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam - Receipt for credit card purchase</h1>',
             b"GCF URL 1"),
            (b'<h1><img src="http://steampowered.com/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam - Receipt for CD key subscription</h1>',
             b'<h1><img src="http://' + octal_ip + b'/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam - Receipt for CD key subscription</h1>',
             b"GCF URL 2"),
            (b'<h1><img src="http://steampowered.com/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam Game Details</h1>',
             b'<h1><img src="http://' + octal_ip + b'/img/steam_logo_onwhite.gif" height="36" width="67" alt="STEAM" align="absmiddle"> Steam Game Details</h1>',
             b"GCF URL 3")
    )
    if not is2003_gcf:
        replace_string_space += ((b'\"http://www.steampowered.com/\"',
                                  b'"http://' + octal_ip + b'/"',
                                  b"GCF URL 4"),)

    replace_string_space += ((b'(http://steampowered.com/img/square.gif);',
                              b'(http://' + octal_ip + b'/img/square.gif);',
                              b"GCF URL 5"),
                             (b'"http://steampowered.com/img/steam_logo_onwhite.gif"',
                              b'"http://' + octal_ip + b'/img/steam_logo_onwhite.gif"',
                              b"GCF URL 6"),
                             (b'"http://steampowered.com/img/print.gif"',
                              b'"http://' + octal_ip + b'/img/print.gif"',
                              b"GCF URL 7"),
                             (b'"http://www.steampowered.com/video/requirements.php?game=240&l=english&vendorid=4098&deviceid=20042"',
                              b'"http://' + octal_ip + b'/video/requirements.php?game=240&l=english&vendorid=4098&deviceid=20042"',
                              b"GCF URL 8"),
                             (b'"http://www.steampowered.com/video/driverupdate.php?game=240&l=english&vendorid=4098&deviceid=20042"',
                              b'"http://' + octal_ip + b'/video/driverupdate.php?game=240&l=english&vendorid=4098&deviceid=20042"',
                              b"GCF URL 9"),
                             (b'"http://steampowered.com/?area=subscriber_agreement"',
                              b'"http://' + octal_ip + b'/?area=subscriber_agreement"',
                              b"GCF URL 10"),
                             (b'"http://steampowered.com/troubleshooter/live/en/s_bill_01.php"',
                              b'"http://' + octal_ip + b'/troubleshooter/live/en/s_bill_01.php"',
                              b"GCF URL 11"),
                             (b'"http://steampowered.com/?area=getsteamnow"',
                              b'"http://' + octal_ip + b'/?area=getsteamnow"',
                              b"GCF URL 12"),
                             (b'"http://www.steampowered.com/status/survey.html"',
                              b'"http://' + octal_ip + b'/status/survey.html"',
                              b"GCF URL 13"),
                             (b'http://www.steampowered.com/platform/update_history/"',
                              b"http://" + octal_ip + b'/platform/update_history/"',
                              b"Platform1 News URL"),
                             # (b'http://steampowered.custhelp.com/cgi-bin/steampowered.cfg',
                             # b"http://" + octal_ip + b"/custhelp",
                             # b"Steam Customer Help URL"),
                             # (b'Please visit www.steampowered.com for details',
                             # b'Please visit ' + octal_ip + b'for details',
                             # b"Steam Visit for details string"),
                             (b'"207.173.177.42:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 1"),
                             (b'"207.173.177.43:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 2"),
                             (b'"207.173.177.44:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 3"),
                             (b'"207.173.177.45:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 4"),
                             (b'"207.173.178.42:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 5"),
                             (b'"207.173.178.43:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 6"),
                             (b'"207.173.178.44:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 7"),
                             (b'"207.173.178.45:1200"',
                              b'"' + trk_ip + b':' + trk_port + b'"',
                              b"Tracker IP 8"),
                             (b'"207.173.177.10:27010"',
                              b'"' + conn_ip + b':' + hl1master_port + b'"',
                              b"HL Master Server 3"),
                             (b'"half-life.west.won.net:27010"',
                              b'"' + conn_ip + b':' + hl1master_port + b'"',
                              b"HL Master Server 5"),
                             (b'hlmaster.valvesoftware.com:27010',
                              conn_ip + b':' + hl1master_port,
                              b"HL Master Server 4"),
                             (b'half-life.east.won.net:27010',
                              conn_ip + b':' + hl1master_port,
                              b"HL Master Server 6"),
                             (b'half-life.central.won.net:27010',
                              conn_ip + b':' + hl1master_port,
                              b"HL Master Server 7"),
                             (b'half-life.speakeasy-nyc.hlauth.net:27012',
                              conn_ip + b':' + vac1_port,
                              b"HL VAC Secure Server 1"),
                             (b'half-life.speakeasy-sea.hlauth.net:27012',
                              conn_ip + b':' + vac1_port,
                              b"HL VAC Secure Server 2"),
                             (b'half-life.speakeasy-chi.hlauth.net:27012',
                              conn_ip + b':' + vac1_port,
                              b"HL VAC Secure Server 3"),
                             (b'"leaknet.org:27010"',
                              b'"' + conn_ip + b':' + hl1master_port + b'"',
                              b"Leaknet Master Server 1"),
                             (b'"leaknet.tk:27010"',
                              b'"' + conn_ip + b':' + hl1master_port + b'"',
                              b"Leaknet Master Server 2"),
                             (b'"94.158.153.11:27010"',
                              b'"' + conn_ip + b':' + hl1master_port + b'"',
                              b"Leaknet Master Server 3"),
                             (b'"http://www.steampowered.com/?area=news"',
                              b'"http://' + octal_ip + b"/?area=news" + b'"',
                              b"Steam news URL 1"),
                             # (b'\"http://steampowered.custhelp.com/',
                             # b'\"http://' + octal_ip + b'',
                             # b"Steam Custhelp.com"),

                             )
    # NEWS WORKS FROM URL 1
    return replace_string_space


def replace_string_name(islan, is2003_gcf = False):
    octal_ip = get_octal_ip(islan)

    octal_ip = octal_ip.encode('latin-1')
    conn_ip = config["server_ip"].encode('latin-1') if islan else config["public_ip"].encode('latin-1')

    community_ip = get_octal_ip(islan, True).encode('latin-1')
    store_url_new = config["store_url_new"].encode('latin-1')
    support_url_net = config["support_url_new"].encode('latin-1')
    hl1master_port = config['masterhl1_server_port'].encode('latin-1')

    replace_string_name = (
            (b"http://www.steampowered.com/platform/banner/random.php",
             b"http://" + octal_ip + b"/platform/banner/random.php",
             b"Banner URL"),
            (b"http://storefront.steampowered.com/platform/update_history/index.php",
             b"http://" + octal_ip + store_url_new + b"/platform/update_history/index.php",
             b"Client news URL"),
            (b"http://www.steampowered.com/?area=news",
             b"http://" + octal_ip + b"/?area=news",
             b"Steam news URL 2"),
            (b"http://www.steampowered.com/index.php?area=news",
             b"http://" + octal_ip + b"/index.php?area=news",
             b"Steam news URL 3"),
            (b"http://www.steampowered.com/platform/friends/",
             b"http://" + octal_ip + b"/platform/friends/",
             b"Tracker URL"),
            (b"http://www.steampowered.com/index.php?area=subscriber_agreement",
             b"http://" + octal_ip + b"/index.php?area=subscriber_agreement",
             b"SSA URL"),
            (b'http://storefront.steampowered.com/v/?client=1',
             b"http://" + octal_ip + store_url_new + b"/v/?client=1",
             b"Storefront URL 1"),
            (b"http://storefront.steampowered.com",
             b"http://" + octal_ip + store_url_new,
             b"Storefront URL 2"),
            (b"http://support.steampowered.com",
             b"http://" + octal_ip + support_url_net,
             b"Support URL"),
            (b"http://cdntest.steampowered.com/steamcommunity/beta/",
             b"http://" + community_ip + b"/steamcommunity/beta/",
             b"Community beta URL"),
            (b"http://localhost/community/public/",
             b"http://" + community_ip + b"/community/public/",
             b"Community local URL"),
            (b"http://media.steampowered.com/steamcommunity/public/",
             b"http://" + octal_ip + b"/steamcommunity/public/",
             b"Community media URL"),
            (b"http://steamcommunity.com/",
             b"http://" + community_ip + b"/",
             b"Community URL"),
            (b"http://beta.steamcommunity.com/",
             b"http://" + community_ip + b"/",
             b"Community URL"),
            (b"http://api.steampowered.com",
             b"http://" + octal_ip + b"/api/",
             b"Steam API URL"),

            # FIXME below is found inside gameoverlayui.exe and gameoverlayrender.dll but putting this here may mess up files that need spaces instead of nulls
            # (b"http://207.173.176.210/community/",
            # b"http://" + community_ip + b"/community/",
            # b"Community IP URL"),
    )

    if not is2003_gcf:
        replace_string_name += ((b"http://www.steampowered.com",
                                 b"http://" + octal_ip,
                                 b"Steampowered URL 1"),)

    replace_string_name += ((b"http://store.steampowered.com",
                             b"http://" + octal_ip,
                             b"Steam Store URL"),
                            (b"http://developer.valvesoftware.com/wiki/Main_Page",
                             b"http://" + octal_ip,
                             b"Dev Wiki URL"),
                            (b"http://www.steampowered.com/platform/banner/",
                             b"http://" + octal_ip + b"/platform/banner/",
                             b"New banner URL 1"),
                            (b"http://cdn.steampowered.com/platform/banner/cs_25.html",
                             b"http://" + octal_ip + b"/platform/banner/cs_25.html",
                             b"New banner URL 2"),
                            (b"http://cdn.steampowered.com/platform/banner/",
                             b"http://" + octal_ip + b"/platform/banner/",
                             b"New banner URL 3"),
                            (b"http://cdn.steampowered.com/v/gfx/apps/%d/header.jpg",
                             b"http://" + octal_ip + b"/v/gfx/apps/%d/header.jpg",
                             b"Game Headers URL"),
                            (b"StorefrontURL",
                             b"StorefrontURM",
                             b"Storefront redirector"),
                            (b"SteamNewsURL",
                             b"SteamNewsURM",
                             b"Steam news redirector"),
                            (b"media.steampowered.com" + b'\x00' + b'\x00',
                             b"client-download.steampowered.com",
                             b"Steam 2013 Package URL"),
                            (b"http://steampowered.com/troubleshooter/",
                             b"http://" + octal_ip + b"/troubleshooter/",
                             b"Troubleshooter"),
                            (b'http://steamsupport.valvesoftware.com',
                             b"http://" + octal_ip + b"/steamsupport/",
                             b"Steam Beta 1 SteamSupport URL"),
                            (b'http://valvesoftware.com',
                             b"http://" + octal_ip,
                             b"Steam Beta 1 Valvesoftware.com URL"),
                            (b'\x67\x00\x72\x00\x69\x00\x64\x00\x64\x00\x65\x00\x76\x00\x2E\x00\x76\x00\x61\x00\x6C\x00\x76\x00\x65\x00\x73\x00\x6F\x00\x66\x00\x74\x00\x77\x00\x61\x00\x72\x00\x65\x00\x2E\x00\x63\x00\x6F\x00\x6D',
                             to_c_string_format(octal_ip),
                             b"Steam Beta 1 GridDev FTP"),
                            (b'http://steampowered.com',
                             b"http://" + octal_ip,
                             b"SteamPowered URL 2"),
                            (b"\x00" + b'storefront.steampowered.com' + b"\x00",
                             b"\x00" + octal_ip + b"\x00",
                             b"Storefront App Info URL"),
                            (b"\x00" + b'half-life.west.won.net:27010' + b"\x00",
                             b"\x00" + conn_ip + b':' + hl1master_port + b"\x00",
                             b"Master Server 1")
                            )

    return replace_string_name


def replace_string(islan):
    import utilities.encryption as encryption
    conn_ip = config["server_ip"] if islan else config["public_ip"]
    trk_ip = config["server_ip"] if islan else config["public_ip"]

    conn_ip = conn_ip.encode('latin-1')
    trk_ip = trk_ip.encode('latin-1')
    trk_port = config['tracker_server_port'].encode('latin-1')
    main_key_n = hex(encryption.main_key.n)[2:].encode('latin-1')
    net_key_n = hex(encryption.network_key.n)[2:].encode('latin-1')
    dir_server_port = config["dir_server_port"].encode('latin-1')
    community_ip = get_octal_ip(islan, True).encode('latin-1')

    replace_string = (
            (b"30820120300d06092a864886f70d01010105000382010d00308201080282010100ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff020101",
             b"30820120300d06092a864886f70d01010105000382010d00308201080282010100" + main_key_n + b"020111",
             b"Steam2 main RSA key (1024-bit) 1"),
            (b"30820120300d06092a864886f70d01010105000382010d00308201080282010100d1543176ee6741270dc1a32f4b04c3a304d499ad0570777dba31483d01eb5e639a05eb284f93cf9260b1ef9e159403ae5f7d3997e789646cfc70f26815169a9b4ba4dc5700ea4480f78466eae6d2bdf5e4181da076ca2e95b32b79c016eb91b5f158e8448d2dd5a42f883976a935dcccbbc611dc2bdf0ea3b88ca72fba919501fb8c6187b4ecddbbb6623d640e819302a6be35be74460cbad9bff0ab7dff0c5b4b8f4aff8252815989ec5fffb460166c5a75b81dd99d79b05f23d97476eb3a5d44c74dcd1136e776f5d2bb52e77f530fa2a5ad75f16c1fb5d8218d71b93073bddad930b3b4217989aa58b30566f1887907ca431e02defe51d19489486caf033d020111",
             b"30820120300d06092a864886f70d01010105000382010d00308201080282010100" + main_key_n + b"020111",
             b"Steam2 main RSA key (1024-bit)"),
            (b"\x30\x81\x9d\x30\x0d\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01\x05\x00\x03\x81\x8b\x00\x30\x81\x87\x02\x81\x81\x00\xda\xde\x57\xfe\x10\x99\xf9\x4b\x81\xb9\x0d\x00\x82\x50\x5b\xe3\x74\xca\x97\x28\xab\x9a\x88\x5b\x3b\x0e\x8e\x02\x5e\x43\xe5\xcc\xd8\x1b\x00\xcd\xbd\x05\xe2\x2a\xc2\x5c\x53\x18\xbf\x84\xc3\x40\x21\x42\xa5\xc3\x8a\xc3\xf4\x27\x1b\xab\xc3\xe5\xc0\x60\x18\xed\x26\x57\xf4\x68\xc5\xda\x55\xaa\x7e\x3b\x3b\x1a\xb2\x72\x06\x17\x4a\x85\x6e\xe2\xb6\x73\x91\x9d\xeb\x47\xbd\x49\x1d\x10\x21\x3e\x90\xdb\xd5\x6e\x25\x2c\xc6\xc9\xe9\x18\x8d\x0b\xc5\x71\x9b\x57\xed\x57\x02\xc6\x45\x5f\x27\x31\x6a\xa0\xaa\x03\x78\x2f\x06\xdf\x02\x01\x11",
             b"\x30\x81\x9d\x30\x0d\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01\x05\x00\x03\x81\x8b\x00\x30\x81\x87\x02\x81\x81\x00" + int(encryption.network_key.n).to_bytes(128, 'big') + b"\x02\x01\x11",
             b"Steam Beta 1 main ASCII RSA key (512-bit)"),
            (b"30820120300d06092a864886f70d01010105000382010d0030820108028201010094db10802a3dcf16ad6755208bfb8fa411c6c290dd86dfbb14bf4fc621ee22689e97b37bc89e82dd20a92d191f5f18362031ccffdac814e01a94a2822ff68f25a79751b0084da37869ba50a9db586595bcfd7d97a952bdaa16b2c2a0629de272faa2f4d6b06132df02e3227c75731dc051a4582c36133b56fcb7b8469fe20cfe8d7111dbd3c7f05a2a238e25362dd4aef82a931801badbe7f1709d4d4bfa97cdf933cc769634d51cfb7af134a7d443938bb82a2074411567f2eaec5bc54716b785e118c93b21d9278f1b422d54debed21645adecd91fb63c41d6fc7632c3cd91b0423f4fdb0cc7697cf666d905a17b593b2e4434b9595aedc4683d29d494aca9020111",
             b"30820120300d06092a864886f70d01010105000382010d00308201080282010100" + main_key_n + b"020111",
             b"Steam1 main RSA key (1024-bit)"),
            (b"30819d300d06092a864886f70d010101050003818b0030818702818100d3bb0de9bbab4becf8efc894c0723c54c3d7f8ff7bcef9f4d9c810668ca1cad7a292017c537bab1a68db17f8bd9a94751c2e37f30a7fab23c6a0443edd2d6896c1f5fcc89bb4e32291a44044777eb72c5e1ff1a9c113c75b49abdfd5bdc732c7807a18c836944279d63ef9bb4a38f50805b157ad32556e07e6575a112ca346ff020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam2 unknown RSA key 1 (512-bit)"),
            (b"30819d300d06092a864886f70d010101050003818b0030818702818100a7ed99f0b2eb868d94d67f6a9552a9bb5e909a724a086d88694dc74148833075e89afca13c4504b0cb304d7548c5cc0aa4f3d2fbbe9cdff173f22a0844e3702696a1ec7e930323185796fb55e1b6a2e08c337e84b21f0325af7537e7e6a43ff837d0694c6ce1ff86c1562096730d075a341111c4dc83570cf7c56f62cc04a9a9020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam1 unknown RSA key 1 (512-bit)"),
            (b"30819d300d06092a864886f70d010101050003818b0030818702818100bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steamclient.dll / File Signature Verification Key"),
            (b"30819d300d06092a864886f70d010101050003818b0030818702818100bc265d3402562c8afb78904e7ec84ee5b6662a09216b6b50da4205094c54f8b09d211bdeb8219ca4df67e39d2349bcbe9cb3b0d1e18b23cf33b5b51cabbeaa529a27e2b3928bdbe1c5c5a7de6bee7e87aecfa26f82286cad35df7ee53fe12adb2d1e81e98ca5faa6db509de8c4f482fa3c4fcf875ce21d443ed635bbdcb425db020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam Beta 1 Network RSA key 3 (512-bit)"),
            (b"30819d300d06092a864886f70d010101050003818b0030818702818100c8667b365a9801ed17ec2456a2a4b06377a943354064332c4ce558f43ad5980e16e462b9da48ba3797905d2681a6993d0a3aaaa1613bb78869894b96064edd4c54e8d1b5492937527c88ed98afeee3ee126dbcd98b9a8c8af038ecf3800ee1150c87235da973da40102d88248b61f6dcb4c40bbd48082c191eaefea0f85579dd020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam2 unknown RSA key 2 (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100DFEC1AD62C10662C17353A14B07C59117F9DD3D82B7AE3E015CD191E46E87B8774A2184631A9031479828EE945A24912A923687389CF69A1B16146BDC1BEBFD6011BD881D4DC90FBFE4F527366CB9570D7C58EBA1C7A3375A1623446BB60B78068FA13A77A8A374B9EC6F45D5F3A99F99EC43AE963A2BB881928E0E714C04289020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam3 Public Universe RSA key (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100AED14BC0A3368BA0390B43DCED6AC8F2A3E47E098C552EE7E93CBBE55E0F1874548FF3BD56695B1309AFC8BEB3A14869E98349658DD293212FB91EFA743B552279BF8518CB6D52444E0592896AA899ED44AEE26646420CFB6E4C30C66C5C16FFBA9CB9783F174BCBC9015D3E3770EC675A3348F746CE58AAECD9FF4A786C834B020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam3 Beta Universe RSA key (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100A8FE013BB6D7214B53236FA1AB4EF10730A7C67E6A2CC25D3AB840CA594D162D74EB0E724629F9DE9BCE4B8CD0CAF4089446A511AF3ACBB84EDEC6D8850A7DAA960AEA7B51D622625C1E58D7461E09AE43A7C43469A2A5E8447618E23DB7C5A896FDE5B44BF84012A6174EC4C1600EB0C2B8404D9E764C44F4FC6F148973B413020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam3 Internal Universe RSA key (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100D0052CE98095CD3083A8E9259663CECC485D5C5200DB1E78D76A4C2CC8418CCC8746FB1BC9E86E4F7A6BC3E70FD5A95D6CD4EEA2CC805AD3CE5359E68091C4C0D5F06323916970C5BBBD05E24F7D9012EDAC4F86963C89CC921563CB5770B9C3AE084FC85616B00CC6C88A80D237F77FAB93BBE6DE9578B811C9E562ADBC0C87020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam3 Developers Universe RSA key (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B00308187028181009E20ECC73E7722F42AD952210A59B9668CB3C615445F87504E12FD84D723958864DFBD2D1F4B9D5C918B34E9EA9C07AF0FB9E42940F78EB757AB730F3A4722DE4E06BD15D890D87E62ACB41CB2639F75C014CD72884C4D763E2EA553759CE62CD19831E697027E3C63D1282F3FD9C06DBB034CF4A34D85F13B8EB6F7FB9D1FA1020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Steam3 RC Universe RSA key (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100B1260881BDFE84463D88C6AB8DB914A2E593893C10508B8A5ABDF692E9A5419A3EDBAE86A052849983B75E3B425C18178B260003D857DF0B6505C6CF9C84F5859FCE3B63F1FB2D4818501F6C5FA4AD1430EEB081A74ABD74CD1F4AA1FCCA3B88DD0548AED34443CEB52444EAE9099AA4FE66B2E6224D02381C248025C7044079020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"Real RSA key 1 (512-bit)"),
            (b"30819d300d06092a864886f70d010101050003818b0030818702818100c8872c9ff46cd4e7efba02dade3ea8dd0696ea2f159198910818fe0b7c06edc21682680b06a553a9a5e0126ff0b24d338f37fba66b1be58aad97a87cd0d48f680c122142ae1c8a0d33a95e54670dfeb3fffda1cde6552f5836b9f4b52701a32acedbc79a290d606137f140f0c06cd3d9e17d008e397171064c86ceb04dfd4535020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"P2P RSA Key (512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100C9B2589ACAD8EE3F52204CF260273710F71BA01C45C215C32F2AB3B669E7ABD179FE63AA238908B61FDBA231F5918955E3D73E1FDBF22FC80DF6D39F8C4E69E49BC4669D7EEC339C65279F99F7E563239A7AA896F2EAEE130B8FC67925A25D711F427533E690E208E2836481E0CD1173D19B854946EE3D7EF2896CE817A4CABB020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"FriendsUI/Serverbrowser RSA Key 1(512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100AAA1281C05F4EFD6207BA11B78BA957C43B3760BD2B8AC8BA664B5BA237FC4475A16B9AABCB94EB72D0B9DEC12B6C113F896A11938CBD33EEEF70BB3DB09B37488FD95FCE9706A75EB6D8060B756CAD693981492404228649BDE9BD63148873BB23CD2894998F34975CA8E5191642E5F437C8A6F6C546A57C7DB859A0189FD35020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"FriendsUI/Serverbrowser RSA Key 2(512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100D059A3AB5CDB348047665D6ABD847E9892BC05D2D4BC7C161C06031357BCE4CB20E609D3921CD04AE493279D7E1A7318766843CC73AAFBEC95D4E39121BE88F04F10B5907BFA6CF653DAA6C948BFAB805BB0958D6DC38252C5D1B6A698FB9813ABBED40917C2874DC6447F6C545156987ED6E17CC1C3047DC339927B45AFF049020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"FriendsUI/Serverbrowser RSA Key 3(512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100D066F58E96CFDC5A5D0595C731A2DAC882BA0B1B5AA83DC940F8C43B4A6C9CBD5258AAC53E0A8C5A76072B920F84F3ACE6B12D6B3C5AC478072451931B4C26856B3F456E1C89EBCC5FBBAA4EEF8A16AB2738025B274AD16DEE288D9F5C0BF127F480092AED69B307DE08E001A272F150BF0077A54F8C9306BE7B20B2902C1561020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"FriendsUI/Serverbrowser RSA Key 4(512-bit)"),
            (b"30819D300D06092A864886F70D010101050003818B0030818702818100F0A35BF1883A651F14738FCB702E69795F310AE71F22F37B3912654A1F0E88CF4451E477A149D3EB3468606FD097D60FFC06C975B6F99EA5394D9790F7F513F7C99788E9EF65986EEDA40D624CAF963C7D4B368CBA4C58A620E2FF9B5BCDDD0F4C1C6BE13CB1F9A33B775A873ED34137A4CBDAA49E95644B8FDB4AF35BABAA37020111",
             b"30819d300d06092a864886f70d010101050003818b0030818702818100" + net_key_n + b"020111",
             b"FriendsUI/Serverbrowser RSA Key 5(512-bit)"),
            (b"afakehost.example.com:27030 bfakehost.example.com:27030",
             conn_ip + b":" + dir_server_port + b" " + conn_ip + b":" + dir_server_port,
             b"DNS directory server fallback"),
            (b"127.0.0.1" + (b'\x00' * 3) + b"207.173.176.215",
             conn_ip + b'\x00' + b"207.173.176.215",
             b"DNS loopback directory server"),
            (b"68.142.92.67" + (b'\x00' * 3),
             b"888.888.888.888",
             b"CAS IP 1"),
            (b"68.142.92.66" + (b'\x00' * 3),
             b"888.888.888.889",
             b"CAS IP 2"),
            (b"207.173.176.132",
             b"888.888.888.890",
             b"CAS IP 3"),
            (b"207.173.176.131",
             b"888.888.888.891",
             b"CAS IP 4"),
            (b"207.173.176.216" + b'\x00' + b"207.173.179.87" + b'\x00\x00' + b"207.173.178.127" + b'\x00' + b"207.173.178.178",
             conn_ip + b":" + dir_server_port + b'\x00' + conn_ip + b":" + dir_server_port + b'\x00' + conn_ip + b":" + dir_server_port,
             b"DNS extra directory servers"),
            (b"http://207.173.176.210/community/",
             b"http://" + community_ip + b"/community/",
             b"Community IP URL"),
            (b"207.173.177.11:27010",
             conn_ip + b":27010",
             b"HL Master Server 1"),
            (b"207.173.177.12:27010",
             conn_ip + b":27010",
             b"HL Master Server 2"),
            (b'207.173.177.45:27030 207.173.177.45:27030',
             conn_ip + b":" + dir_server_port + b" " + conn_ip + b":" + dir_server_port,
             b"Steam1 directory server 1"),
            (b'207.173.177.45:27030 207.173.177.46:27030',
             conn_ip + b":" + dir_server_port + b" " + conn_ip + b":" + dir_server_port,
             b"Steam1 directory server 2"),
            (b"gds1.steampowered.com:27030 gds2.steampowered.com:27030",
             conn_ip + b":" + dir_server_port + b" " + conn_ip + b":" + dir_server_port,
             b"DNS directory server fallback"),
            (b"afakehost.example.com:27030 bfakehost.example.com:27030",
             conn_ip + b":" + dir_server_port + b" " + conn_ip + b":" + dir_server_port,
             b"DNS directory server fallback"),
            (b"cm0.steampowered.com",
             conn_ip,
             b"DNS connection manager fallback"),
            (b'"tracker.valvesoftware.com:1200"',
             b'"' + trk_ip + b':' + trk_port + b'"',
             b"Tracker DNS 1"),
            (b'tracker.valvesoftware.com:1200',
             trk_ip + b':' + trk_port,
             b"Tracker DNS 2"),
            (b'gridmaster.valvesoftware.com:27012',
             conn_ip + b":" + config['vac_server_port'].encode('latin-1'),
             b"HL1 Valve AntiCheat Default Server"),
    )

    return replace_string


def replace_string_resfiles(islan):
    octal_ip = get_octal_ip(islan)

    octal_ip = octal_ip.encode('latin-1')

    replace_public_string_space = (
            # Below are links from the steam Public folder
            (b'\"http://www.steampowered.com',
             b'\"http://' + octal_ip,
             b"http://www.Steampowered.com resfile neuter"),
            (b'"http://www.valvesoftware.com/privacy.htm"',
             b'"http://' + octal_ip + b"/valvesoftware/privacy.htm" + b'"',
             b"Steam Privacy URL 1"),
            (b'\"http://www.valvesoftware.com',
             b'\"http://' + octal_ip + b"/valvesoftware",
             b"http://www.valvesoftware.com resfile neuter"),
            (b'\"http://steampowered.com',
             b'\"http://' + octal_ip,
             b"http://SteamPowered.com resfile neuter"),
            (b'\"http://steamsupport.valvesoftware.com',
             b'\"http://' + octal_ip + b"support",
             b"http://steamsupport.valvesoftware.com resfile neuter"),
            (b'\"http://steampowered.custhelp.com',
             b'\"http://' + octal_ip + b"support",
             b"http://steamsupport.custhelp.com resfile neuter"),
    )
    return replace_public_string_space