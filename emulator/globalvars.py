
from Crypto.PublicKey import RSA
from steamemu.config import read_config
config = read_config()

main_key_sign = RSA.construct((
    # n
    #0x86724794f8a0fcb0c129b979e7af2e1e309303a7042503d835708873b1df8a9e307c228b9c0862f8f5dbe6f81579233db8a4fe6ba14551679ad72c01973b5ee4ecf8ca2c21524b125bb06cfa0047e2d202c2a70b7f71ad7d1c3665e557a7387bbc43fe52244e58d91a14c660a84b6ae6fdc857b3f595376a8e484cb6b90cc992f5c57cccb1a1197ee90814186b046968f872b84297dad46ed4119ae0f402803108ad95777615c827de8372487a22902cb288bcbad7bc4a842e03a33bd26e052386cbc088c3932bdd1ec4fee1f734fe5eeec55d51c91e1d9e5eae46cf7aac15b2654af8e6c9443b41e92568cce79c08ab6fa61601e4eed791f0436fdc296bb373L,
    
    int(config["main_key_n"], 16),
    # e
    #0x07e89acc87188755b1027452770a4e01c69f3c733c7aa5df8aac44430a768faef3cb11174569e7b44ab2951da6e90212b0822d1563d6e6abbdd06c0017f46efe684adeb74d4113798cec42a54b4f85d01e47af79259d4670c56c9c950527f443838b876e3e5ef62ae36aa241ebc83376ffde9bbf4aae6cabea407cfbb08848179e466bcb046b0a857d821c5888fcd95b2aae1b92aa64f3a6037295144aa45d0dbebce075023523bce4243ae194258026fc879656560c109ea9547a002db38b89caac90d75758e74c5616ed9816f3ed130ff6926a1597380b6fc98b5eeefc5104502d9bee9da296ca26b32d9094452ab1eb9cf970acabeecde6b1ffae57b56401L,
    
    int(config["main_key_e"], 16),
    # d
    0x11L,
))

network_key = RSA.construct((
    # n
    #0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
    int(config["net_key_n"], 16),
    # e
    0x11L,
    # d
    #0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
    int(config["net_key_d"], 16),
))

network_key_sign = RSA.construct((
    # n
    #0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
    int(config["net_key_n"], 16),
    # e
    #0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
    int(config["net_key_d"], 16),
    # d
    0x11L,
))

converting = "0"
checksum_temp_file = 0
servernet = "0."
udpdata = ""
udpaddr = ""
hl1serverlist = list(xrange(10000))
hl1challengenum = 0
hl2serverlist = list(xrange(10000))
hl2challengenum = 0
tracker = 0
tgt_version = "2"

ip_addresses = (
"69.28.148.250",
"69.28.156.250",
"68.142.64.162",
"68.142.64.163",
"68.142.64.164",
"68.142.64.165",
"68.142.64.166",
"207.173.176.215",
"207.173.176.216",
"207.173.178.127",
"207.173.178.178",
"207.173.178.196",
"207.173.178.198",
"207.173.178.214",
"207.173.179.14",
"207.173.179.87"
)

extraips = (
"207.173.177.12:27010",
"207.173.177.11:27010",
"207.173.177.12:27011",
"207.173.177.11:27011"
)
                    
replacestrings = (
    ('http://www.steampowered.com/platform/update_history/"',
     "http://" + config["http_ip"] + config["http_port"] + config["platformnews_url"],
     "Platform News URL"),
    ('http://www.steampowered.com/index.php?area=subscriber_agreement',
     "http://" + config["http_ip"] + config["http_port"] + config["ssa_url"],
     "SSA URL"),
    ('http://www.steampowered.com/index.php?area=news',
     "http://" + config["http_ip"] + config["http_port"] + config["steamnews_url"],
     "News URL"),
    ('http://storefront.steampowered.com/v/?client=1',
     "http://" + config["http_ip"] + config["http_port"],
     "Storefront URL"),
    ('http://storefront.steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "Storefront URL"),
    ('http://www.steampowered.com/?area=news"',
     "http://" + config["http_ip"] + config["http_port"] + '/news.php"',
     "News URL"),
    ('http://www.steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "SteamPowered URL"),
    ('http://steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "SteamPowered URL"),
    ("gds1.steampowered.com:27030 gds2.steampowered.com:27030",
     config["server_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
     "DNS directory server fallback"))
                    
replacestringsext = (
    ('http://www.steampowered.com/platform/update_history/"',
     "http://" + config["http_ip"] + config["http_port"] + config["platformnews_url"],
     "Platform News URL"),
    ('http://www.steampowered.com/index.php?area=subscriber_agreement',
     "http://" + config["http_ip"] + config["http_port"] + config["ssa_url"],
     "SSA URL"),
    ('http://www.steampowered.com/index.php?area=news',
     "http://" + config["http_ip"] + config["http_port"] + config["steamnews_url"],
     "News URL"),
    ('http://storefront.steampowered.com/v/?client=1',
     "http://" + config["http_ip"] + config["http_port"],
     "Storefront URL"),
    ('http://storefront.steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "Storefront URL"),
    ('http://www.steampowered.com/?area=news"',
     "http://" + config["http_ip"] + config["http_port"] + '/news.php"',
     "News URL"),
    ('http://www.steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "SteamPowered URL"),
    ('http://steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "SteamPowered URL"),
    ("gds1.steampowered.com:27030 gds2.steampowered.com:27030",
     config["public_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
     "DNS directory server fallback"))
                    
replacestrings2003 = (
    ('http://storefront.steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "Storefront URL"),
    ('http://www.steampowered.com/platform/update_history/"',
     "http://" + config["http_ip"] + config["http_port"] + config["platformnews_url"],
     "Platform News URL"),
    ("gds1.steampowered.com:27030 gds2.steampowered.com:27030",
     config["server_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
     "DNS directory server fallback"))
                    
replacestrings2003ext = (
    ('http://storefront.steampowered.com',
     "http://" + config["http_ip"] + config["http_port"],
     "Storefront URL"),
    ('http://www.steampowered.com/platform/update_history/"',
     "http://" + config["http_ip"] + config["http_port"] + config["platformnews_url"],
     "Platform News URL"),
    ("gds1.steampowered.com:27030 gds2.steampowered.com:27030",
     config["public_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
     "DNS directory server fallback"))
                    
replacestringsCDR = (
    ('http://storefront.steampowered.com/marketing',
     "http://" + config["http_ip"] + config["http_port"] + "/marketing",
     "Messages Old URL"),
    ('http://www.steampowered.com/marketing',
     "http://" + config["http_ip"] + config["http_port"] + "/marketing",
     "Messages Old URL"),
    ('http://storefront.steampowered.com/Steam/Marketing',
     "http://" + config["http_ip"] + config["http_port"] + "/Steam/Marketing",
     "Messages New URL"),
    ('http://www.steampowered.com/Steam/Marketing/',
     "http://" + config["http_ip"] + config["http_port"] + "/Steam/Marketing/",
     "Messages New URL"))
    
    #('http://storefront.steampowered.com/v2/',
     #config["http_ip"] + ":" + config["http_port"] + "/" + config["online_webpage"],
     #"Storefront URL"))
