
from Crypto.PublicKey import RSA
from steamemu.config import read_config
config = read_config()


peer_password = ""
converting = "0"
checksum_temp_file = 0
servernet = "0."
serverip = ""
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
