import ConfigParser, os

from package import Package
from steamemu.config import read_config

filenames = ("SteamNew.exe", "Steam.dll", "SteamUI.dll", "Public\Account.html", "caserver.exe", "cacdll.dll", "CASClient.exe", "unicows.dll", "GameUI.dll")#, "steamclient.dll", "GameOverlayUI.exe", "serverbrowser.dll", "gamoverlayui.dll", "steamclient64.dll", "AppOverlay.dll", "AppOverlay64.dll", "SteamService.exe", "friendsUI.dll", "SteamService.dll")

config = read_config()

replacestrings = (
("30820120300d06092a864886f70d01010105000382010d00308201080282010100d1543176ee6741270dc1a32f4b04c3a304d499ad0570777dba31483d01eb5e639a05eb284f93cf9260b1ef9e159403ae5f7d3997e789646cfc70f26815169a9b4ba4dc5700ea4480f78466eae6d2bdf5e4181da076ca2e95b32b79c016eb91b5f158e8448d2dd5a42f883976a935dcccbbc611dc2bdf0ea3b88ca72fba919501fb8c6187b4ecddbbb6623d640e819302a6be35be74460cbad9bff0ab7dff0c5b4b8f4aff8252815989ec5fffb460166c5a75b81dd99d79b05f23d97476eb3a5d44c74dcd1136e776f5d2bb52e77f530fa2a5ad75f16c1fb5d8218d71b93073bddad930b3b4217989aa58b30566f1887907ca431e02defe51d19489486caf033d020111",
 "30820120300d06092a864886f70d01010105000382010d00308201080282010100" + config["main_key_n"][2:] + "020111",
 "Main RSA key (1024-bit)"),
("30819d300d06092a864886f70d010101050003818b0030818702818100d3bb0de9bbab4becf8efc894c0723c54c3d7f8ff7bcef9f4d9c810668ca1cad7a292017c537bab1a68db17f8bd9a94751c2e37f30a7fab23c6a0443edd2d6896c1f5fcc89bb4e32291a44044777eb72c5e1ff1a9c113c75b49abdfd5bdc732c7807a18c836944279d63ef9bb4a38f50805b157ad32556e07e6575a112ca346ff020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819d300d06092a864886f70d010101050003818b0030818702818100c8667b365a9801ed17ec2456a2a4b06377a943354064332c4ce558f43ad5980e16e462b9da48ba3797905d2681a6993d0a3aaaa1613bb78869894b96064edd4c54e8d1b5492937527c88ed98afeee3ee126dbcd98b9a8c8af038ecf3800ee1150c87235da973da40102d88248b61f6dcb4c40bbd48082c191eaefea0f85579dd020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100DFEC1AD62C10662C17353A14B07C59117F9DD3D82B7AE3E015CD191E46E87B8774A2184631A9031479828EE945A24912A923687389CF69A1B16146BDC1BEBFD6011BD881D4DC90FBFE4F527366CB9570D7C58EBA1C7A3375A1623446BB60B78068FA13A77A8A374B9EC6F45D5F3A99F99EC43AE963A2BB881928E0E714C04289020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100AED14BC0A3368BA0390B43DCED6AC8F2A3E47E098C552EE7E93CBBE55E0F1874548FF3BD56695B1309AFC8BEB3A14869E98349658DD293212FB91EFA743B552279BF8518CB6D52444E0592896AA899ED44AEE26646420CFB6E4C30C66C5C16FFBA9CB9783F174BCBC9015D3E3770EC675A3348F746CE58AAECD9FF4A786C834B020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100A8FE013BB6D7214B53236FA1AB4EF10730A7C67E6A2CC25D3AB840CA594D162D74EB0E724629F9DE9BCE4B8CD0CAF4089446A511AF3ACBB84EDEC6D8850A7DAA960AEA7B51D622625C1E58D7461E09AE43A7C43469A2A5E8447618E23DB7C5A896FDE5B44BF84012A6174EC4C1600EB0C2B8404D9E764C44F4FC6F148973B413020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100D0052CE98095CD3083A8E9259663CECC485D5C5200DB1E78D76A4C2CC8418CCC8746FB1BC9E86E4F7A6BC3E70FD5A95D6CD4EEA2CC805AD3CE5359E68091C4C0D5F06323916970C5BBBD05E24F7D9012EDAC4F86963C89CC921563CB5770B9C3AE084FC85616B00CC6C88A80D237F77FAB93BBE6DE9578B811C9E562ADBC0C87020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B00308187028181009E20ECC73E7722F42AD952210A59B9668CB3C615445F87504E12FD84D723958864DFBD2D1F4B9D5C918B34E9EA9C07AF0FB9E42940F78EB757AB730F3A4722DE4E06BD15D890D87E62ACB41CB2639F75C014CD72884C4D763E2EA553759CE62CD19831E697027E3C63D1282F3FD9C06DBB034CF4A34D85F13B8EB6F7FB9D1FA1020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("gds1.steampowered.com:27030 gds2.steampowered.com:27030",
 config["server_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
 "DNS directory server fallback"),
("afakehost.example.com:27030 bfakehost.example.com:27030",
 config["server_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
 "DNS directory server fallback"),
("cm0.steampowered.com",
 config["server_ip"],
 "DNS content server fallback"),
("127.0.0.1" + ('\x00' * 3) + "207.173.176.215",
 config["server_ip"] + '\x00' + "207.173.176.215",
 "DNS loopback directory server"),
("68.142.92.67" + ('\x00' * 3),
 "888.888.888.888",
 "CAS IP 1"),
("68.142.92.66" + ('\x00' * 3),
 "888.888.888.889",
 "CAS IP 2"),
("207.173.176.132",
 "888.888.888.890",
 "CAS IP 3"),
("207.173.176.131",
 "888.888.888.891",
 "CAS IP 4"),
("207.173.176.216" + '\x00' + "207.173.179.87" + '\x00\x00' + "207.173.178.127" + '\x00' + "207.173.178.178",
 config["server_ip"] + ":" + config["dir_server_port"] + '\x00' + config["server_ip"] + ":" + config["dir_server_port"] + '\x00' + config["server_ip"] + ":" + config["dir_server_port"],
 "DNS extra directory servers"),
('http://www.steampowered.com/platform/update_history/"',
 "http://" + config["http_ip"] + config["http_port"] + '/platform/update_history/"',
 "Platform News URL"),
("http://www.steampowered.com/platform/banner/random.php",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/random.php",
 "Banner URL"),
("http://storefront.steampowered.com/platform/update_history/index.php",
 "http://" + config["http_ip"] + config["http_port"] + config["store_url_new"] + "/platform/update_history/index.php",
 "Client news URL"),
("http://www.steampowered.com/?area=news",
 "http://" + config["http_ip"] + config["http_port"] + "/?area=news",
 "Steam news URL 1"),
("http://www.steampowered.com/index.php?area=news",
 "http://" + config["http_ip"] + config["http_port"] + "/index.php?area=news",
 "Steam news URL 2"),
("http://www.steampowered.com/platform/friends/",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/friends/",
 "Tracker URL"),
("http://www.steampowered.com/index.php?area=subscriber_agreement",
 "http://" + config["http_ip"] + config["http_port"] + "/index.php?area=subscriber_agreement",
 "SSA URL"),
('http://storefront.steampowered.com/v/?client=1',
 "http://" + config["http_ip"] + config["http_port"] + "/v/?client=1",
 "Storefront URL 1"),
("http://storefront.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"] + config["store_url_new"],
 "Storefront URL 2"),
("http://support.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"] + config["support_url_new"],
 "Support URL"),
("http://cdntest.steampowered.com/steamcommunity/beta/",
 "http://" + config["community_ip"] + "/steamcommunity/beta/",
 "Community beta URL"),
("http://localhost/community/public/",
 "http://" + config["community_ip"] + "/community/public/",
 "Community local URL"),
("http://media.steampowered.com/steamcommunity/public/",
 "http://" + config["community_ip"] + "/steamcommunity/public/",
 "Community media URL"),
("http://steamcommunity.com/",
 "http://" + config["community_ip"] + "/",
 "Community URL"),
("http://www.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"],
 "Steampowered URL 1"),
("http://store.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"],
 "Steam Store URL"),
("http://developer.valvesoftware.com/wiki/Main_Page",
 "http://" + config["http_ip"] + config["http_port"],
 "Dev Wiki URL"),
("http://www.steampowered.com/platform/banner/",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/",
 "New banner URL 1"),
("http://cdn.steampowered.com/platform/banner/cs_25.html",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/cs_25.html",
 "New banner URL 2"),
("http://cdn.steampowered.com/platform/banner/",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/",
 "New banner URL 3"),
("http://207.173.176.210/community/",
 "http://" + config["community_ip"] + "/community/",
 "Community IP URL"),
("StorefrontURL",
 "StorefrontURM",
 "Storefront redirector"),
("SteamNewsURL",
 "SteamNewsURM",
 "Steam news redirector"),
("media.steampowered.com" + '\x00' + '\x00',
 "client-download.steampowered.com",
 "Steam 2013 Package URL"),
("http://steampowered.com/img/steam_logo_onwhite.gif",
 "http://" + config["http_ip"] + config["http_port"] + "/img/steam_logo_onwhite.gif",
 "New account logo 1"),
("http://steampowered.com/img/print.gif",
 "http://" + config["http_ip"] + config["http_port"] + "/img/print.gif",
 "New account logo 2"),
("tracker.valvesoftware.com:1200",
 config["tracker_ip"] + ":1200",
 "Tracker DNS"),
("207.173.177.11:27010",
 config["server_ip"] + ":27010",
 "HL Master Server 1"),
("207.173.177.12:27010",
 config["server_ip"] + ":27010",
 "HL Master Server 2"),
("http://steampowered.com/troubleshooter/",
 "http://" + config["http_ip"] + config["http_port"] + "/troubleshooter/",
 "Troubleshooter"),
('http://steampowered.com',
 "http://" + config["http_ip"] + config["http_port"],
 "SteamPowered URL 2"))

replacestringsext = (
("30820120300d06092a864886f70d01010105000382010d00308201080282010100d1543176ee6741270dc1a32f4b04c3a304d499ad0570777dba31483d01eb5e639a05eb284f93cf9260b1ef9e159403ae5f7d3997e789646cfc70f26815169a9b4ba4dc5700ea4480f78466eae6d2bdf5e4181da076ca2e95b32b79c016eb91b5f158e8448d2dd5a42f883976a935dcccbbc611dc2bdf0ea3b88ca72fba919501fb8c6187b4ecddbbb6623d640e819302a6be35be74460cbad9bff0ab7dff0c5b4b8f4aff8252815989ec5fffb460166c5a75b81dd99d79b05f23d97476eb3a5d44c74dcd1136e776f5d2bb52e77f530fa2a5ad75f16c1fb5d8218d71b93073bddad930b3b4217989aa58b30566f1887907ca431e02defe51d19489486caf033d020111",
 "30820120300d06092a864886f70d01010105000382010d00308201080282010100" + config["main_key_n"][2:] + "020111",
 "Main RSA key (1024-bit)"),
("30819d300d06092a864886f70d010101050003818b0030818702818100d3bb0de9bbab4becf8efc894c0723c54c3d7f8ff7bcef9f4d9c810668ca1cad7a292017c537bab1a68db17f8bd9a94751c2e37f30a7fab23c6a0443edd2d6896c1f5fcc89bb4e32291a44044777eb72c5e1ff1a9c113c75b49abdfd5bdc732c7807a18c836944279d63ef9bb4a38f50805b157ad32556e07e6575a112ca346ff020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819d300d06092a864886f70d010101050003818b0030818702818100c8667b365a9801ed17ec2456a2a4b06377a943354064332c4ce558f43ad5980e16e462b9da48ba3797905d2681a6993d0a3aaaa1613bb78869894b96064edd4c54e8d1b5492937527c88ed98afeee3ee126dbcd98b9a8c8af038ecf3800ee1150c87235da973da40102d88248b61f6dcb4c40bbd48082c191eaefea0f85579dd020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100DFEC1AD62C10662C17353A14B07C59117F9DD3D82B7AE3E015CD191E46E87B8774A2184631A9031479828EE945A24912A923687389CF69A1B16146BDC1BEBFD6011BD881D4DC90FBFE4F527366CB9570D7C58EBA1C7A3375A1623446BB60B78068FA13A77A8A374B9EC6F45D5F3A99F99EC43AE963A2BB881928E0E714C04289020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100AED14BC0A3368BA0390B43DCED6AC8F2A3E47E098C552EE7E93CBBE55E0F1874548FF3BD56695B1309AFC8BEB3A14869E98349658DD293212FB91EFA743B552279BF8518CB6D52444E0592896AA899ED44AEE26646420CFB6E4C30C66C5C16FFBA9CB9783F174BCBC9015D3E3770EC675A3348F746CE58AAECD9FF4A786C834B020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100A8FE013BB6D7214B53236FA1AB4EF10730A7C67E6A2CC25D3AB840CA594D162D74EB0E724629F9DE9BCE4B8CD0CAF4089446A511AF3ACBB84EDEC6D8850A7DAA960AEA7B51D622625C1E58D7461E09AE43A7C43469A2A5E8447618E23DB7C5A896FDE5B44BF84012A6174EC4C1600EB0C2B8404D9E764C44F4FC6F148973B413020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B0030818702818100D0052CE98095CD3083A8E9259663CECC485D5C5200DB1E78D76A4C2CC8418CCC8746FB1BC9E86E4F7A6BC3E70FD5A95D6CD4EEA2CC805AD3CE5359E68091C4C0D5F06323916970C5BBBD05E24F7D9012EDAC4F86963C89CC921563CB5770B9C3AE084FC85616B00CC6C88A80D237F77FAB93BBE6DE9578B811C9E562ADBC0C87020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("30819D300D06092A864886F70D010101050003818B00308187028181009E20ECC73E7722F42AD952210A59B9668CB3C615445F87504E12FD84D723958864DFBD2D1F4B9D5C918B34E9EA9C07AF0FB9E42940F78EB757AB730F3A4722DE4E06BD15D890D87E62ACB41CB2639F75C014CD72884C4D763E2EA553759CE62CD19831E697027E3C63D1282F3FD9C06DBB034CF4A34D85F13B8EB6F7FB9D1FA1020111",
 "30819d300d06092a864886f70d010101050003818b0030818702818100" + config["net_key_n"][2:] + "020111",
 "Unknown RSA key (512-bit), not replaced yet"),
("gds1.steampowered.com:27030 gds2.steampowered.com:27030",
 config["public_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
 "DNS directory server fallback"),
("afakehost.example.com:27030 bfakehost.example.com:27030",
 config["public_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"],
 "DNS directory server fallback"),
("cm0.steampowered.com",
 config["public_ip"],
 "DNS content server fallback"),
("127.0.0.1" + ('\x00' * 3) + "207.173.176.215",
 config["public_ip"] + '\x00' + "207.173.176.215",
 "DNS loopback directory server"),
("68.142.92.67" + ('\x00' * 3),
 "888.888.888.888",
 "CAS IP 1"),
("68.142.92.66" + ('\x00' * 3),
 "888.888.888.889",
 "CAS IP 2"),
("207.173.176.132",
 "888.888.888.890",
 "CAS IP 3"),
("207.173.176.131",
 "888.888.888.891",
 "CAS IP 4"),
("207.173.176.216" + '\x00' + "207.173.179.87" + '\x00\x00' + "207.173.178.127" + '\x00' + "207.173.178.178",
 config["public_ip"] + ":" + config["dir_server_port"] + '\x00' + config["server_ip"] + ":" + config["dir_server_port"] + '\x00' + config["server_ip"] + ":" + config["dir_server_port"],
 "DNS extra directory servers"),
('http://www.steampowered.com/platform/update_history/"',
 "http://" + config["http_ip"] + config["http_port"] + '/platform/update_history/"',
 "Platform News URL"),
("http://www.steampowered.com/platform/banner/random.php",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/random.php",
 "Banner URL"),
("http://storefront.steampowered.com/platform/update_history/index.php",
 "http://" + config["http_ip"] + config["http_port"] + config["store_url_new"] + "/platform/update_history/index.php",
 "Client news URL"),
("http://www.steampowered.com/?area=news",
 "http://" + config["http_ip"] + config["http_port"] + "/?area=news",
 "Steam news URL 1"),
("http://www.steampowered.com/index.php?area=news",
 "http://" + config["http_ip"] + config["http_port"] + "/index.php?area=news",
 "Steam news URL 2"),
("http://www.steampowered.com/platform/friends/",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/friends/",
 "Tracker URL"),
("http://www.steampowered.com/index.php?area=subscriber_agreement",
 "http://" + config["http_ip"] + config["http_port"] + "/index.php?area=subscriber_agreement",
 "SSA URL"),
('http://storefront.steampowered.com/v/?client=1',
 "http://" + config["http_ip"] + config["http_port"] + "/v/?client=1",
 "Storefront URL 1"),
("http://storefront.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"] + config["store_url_new"],
 "Storefront URL 2"),
("http://support.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"] + config["support_url_new"],
 "Support URL"),
("http://cdntest.steampowered.com/steamcommunity/beta/",
 "http://" + config["community_ip"] + "/steamcommunity/beta/",
 "Community beta URL"),
("http://localhost/community/public/",
 "http://" + config["community_ip"] + "/community/public/",
 "Community local URL"),
("http://media.steampowered.com/steamcommunity/public/",
 "http://" + config["community_ip"] + "/steamcommunity/public/",
 "Community media URL"),
("http://steamcommunity.com/",
 "http://" + config["community_ip"] + "/",
 "Community URL"),
("http://www.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"],
 "Steampowered URL 1"),
("http://store.steampowered.com",
 "http://" + config["http_ip"] + config["http_port"],
 "Steam Store URL"),
("http://developer.valvesoftware.com/wiki/Main_Page",
 "http://" + config["http_ip"] + config["http_port"],
 "Dev Wiki URL"),
("http://www.steampowered.com/platform/banner/",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/",
 "New banner URL 1"),
("http://cdn.steampowered.com/platform/banner/cs_25.html",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/cs_25.html",
 "New banner URL 2"),
("http://cdn.steampowered.com/platform/banner/",
 "http://" + config["http_ip"] + config["http_port"] + "/platform/banner/",
 "New banner URL 3"),
("http://207.173.176.210/community/",
 "http://" + config["community_ip"] + "/community/",
 "Community IP URL"),
("StorefrontURL",
 "StorefrontURM",
 "Storefront redirector"),
("SteamNewsURL",
 "SteamNewsURM",
 "Steam news redirector"),
("media.steampowered.com" + '\x00' + '\x00',
 "client-download.steampowered.com",
 "Steam 2013 Package URL"),
("http://steampowered.com/img/steam_logo_onwhite.gif",
 "http://" + config["http_ip"] + config["http_port"] + "/img/steam_logo_onwhite.gif",
 "New account logo 1"),
("http://steampowered.com/img/print.gif",
 "http://" + config["http_ip"] + config["http_port"] + "/img/print.gif",
 "New account logo 2"),
("tracker.valvesoftware.com:1200",
 config["tracker_ip"] + ":1200",
 "Tracker DNS"),
("207.173.177.11:27010",
 config["public_ip"] + ":27010",
 "HL Master Server 1"),
("207.173.177.12:27010",
 config["public_ip"] + ":27010",
 "HL Master Server 2"),
("http://steampowered.com/troubleshooter/",
 "http://" + config["http_ip"] + config["http_port"] + "/troubleshooter/",
 "Troubleshooter"),
('http://steampowered.com',
 "http://" + config["http_ip"] + config["http_port"],
 "SteamPowered URL 2"))

ip_addresses_new = (
"69.28.148.250",
"69.28.156.250",
"68.142.64.162",
"68.142.64.163",
"68.142.64.164",
"68.142.64.165",
"68.142.64.166",
"207.173.176.215",
"207.173.178.196",
"207.173.178.198",
"207.173.178.214",
"207.173.179.14",
)

ip_addresses_old = (
"65.122.178.71",
"67.132.200.140",
"68.142.64.162",
"68.142.64.163",
"68.142.64.164",
"68.142.64.165",
"68.142.64.166",
"69.28.140.245",
"69.28.140.246",
"69.28.140.247",
"69.28.148.250",
"69.28.151.178",
"69.28.152.198",
"69.28.153.82",
"69.28.156.250",
"69.28.191.84",
"68.142.64.162",
"68.142.64.163",
"68.142.64.164",
"68.142.64.165",
"68.142.64.166",
"68.142.72.250",
"68.142.88.34",
"68.142.91.34",
"68.142.91.35",
"69.28.145.170",
"69.28.145.171",
"69.28.151.178",
"69.28.153.82",
"72.165.61.141",
"72.165.61.142",
"72.165.61.143",
"72.165.61.161",
"72.165.61.162",
"72.165.61.185",
"72.165.61.186",
"72.165.61.187",
"72.165.61.188",
"72.165.61.189",
"72.165.61.190",
"86.148.72.250",
"87.248.196.117",
"87.248.196.194",
"87.248.196.195",
"87.248.196.196",
"87.248.196.197",
"87.248.196.198",
"87.248.196.199",
"87.248.196.200",
"127.0.0.1",
#"172.16.3.6",
#"172.16.3.10",
#"172.16.3.11",
#"172.16.3.12",
#"172.16.3.13",
#"172.16.3.14",
#"172.16.3.15",
#"172.16.3.16",
#"172.16.3.17",
#"172.16.3.18",
#"172.16.3.19",
#"172.16.3.23",
#"172.16.3.24",
#"172.16.3.26",
#"172.16.3.27",
#"172.16.3.28",
#"172.16.3.29",
#"172.16.3.30",
#"172.16.3.31",
#"172.16.3.32",
#"172.16.3.34",
#"172.16.3.39",
#"172.16.3.72",
"193.34.50.6",
"194.124.229.14",
"207.173.176.210",
"207.173.176.215",
"207.173.176.216",
"207.173.177.11",
"207.173.177.12",
"207.173.178.127",
"207.173.178.178",
"207.173.178.194",
"207.173.178.196",
"207.173.178.198",
"207.173.178.214",
"207.173.179.14",
"207.173.179.87",
"207.173.179.151",
"207.173.179.179",
"208.111.133.84",
"208.111.133.85",
"208.111.158.52",
"208.111.158.53",
"208.111.171.82",
"208.111.171.83",
"213.202.254.131",
"217.64.127.2",
"888.888.888.888",
"888.888.888.889",
"888.888.888.890",
"888.888.888.891",)

pkgadd_filelist = []

def neuter_file(file, server_ip, server_port) :
    if config["public_ip"] != "0.0.0.0" :
        fullstring = replacestringsext
    else :
        fullstring = replacestrings
    
    for (search, replace, info) in fullstring :
        try :
            if file.find(search) != -1 :
                if search == "StorefrontURL1" :
                    if ":2004" in config["store_url"] :
                        file = file.replace(search, replace)
                        print "Replaced", info
                else :
                    fulllength = len(search)
                    newlength = len(replace)
                    missinglength = fulllength - newlength
                    if missinglength < 0 :
                        print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                    elif missinglength == 0 :
                        file = file.replace(search, replace)
                        print "Replaced", info
                    else :
                        file = file.replace(search, replace + ('\x00' * missinglength))
                        print "Replaced", info
        except notfound :
            print "Config line not found"

    search = "207.173.177.11:27030 207.173.177.12:27030"
    
    if config["public_ip"] != "0.0.0.0" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        print "Replaced directory server IP group 0"

    search = "207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038"
    #ip = server_ip + ":" + server_port + " "
    #if len(ip) > 19 :
        #print "IP to replace with is too wide! This MIGHT result in problems!"
        #ips = ip * 5
    #else :
        #ips = ip * 6
    
    #replace = ips.ljust(119, " ")
    
    if config["public_ip"] != "0.0.0.0" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        print "Replaced directory server IP group 1"

    search = "72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038 "
    #ip = server_ip + ":" + server_port + " "
    #if len(ip) > 19 :
        #print "IP to replace with is too wide! This MIGHT result in problems!"
        #ips = ip * 5
    #else :
        #ips = ip * 6

    #replace = ips.ljust(118, " ")
    
    if config["public_ip"] != "0.0.0.0" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        print "Replaced directory server IP group 2"

    search = "72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 87.248.196.194:27038 68.142.72.250:27038 "
    #ip = server_ip + ":" + server_port + " "
    #if len(ip) > 19 :
        #print "IP to replace with is too wide! This MIGHT result in problems!"
        #ips = ip * 5
    #else :
        #ips = ip * 6
    
    #replace = ips.ljust(120, " ")
    #replace = ips.ljust(119, " ")    119 breaks steamserver2008
    
    if config["public_ip"] != "0.0.0.0" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        print "Replaced directory server IP group 3"
            
    search = "127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030"
    if config["public_ip"] != "0.0.0.0" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        print "Replaced directory server IP group 4"
            
    search = "208.64.200.189:27030 208.64.200.190:27030 208.64.200.191:27030 208.78.164.7:27038"
    if config["public_ip"] != "0.0.0.0" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        print "Replaced directory server IP group 5"

    for ip in ip_addresses_old :
        loc = file.find(ip)
        if loc != -1 :
            if config["public_ip"] != "0.0.0.0" :
                server_ip = config["public_ip"]
                replace_ip = server_ip.ljust(16, "\x00")
                file = file[:loc] + replace_ip + file[loc+16:]
                print "Found and replaced IP %16s at location %08x" % (ip, loc)
            else :
                replace_ip = server_ip.ljust(16, "\x00")
                file = file[:loc] + replace_ip + file[loc+16:]
                print "Found and replaced IP %16s at location %08x" % (ip, loc)

    return file
    
def neuter(pkg_in, pkg_out, server_ip, server_port) :
    f = open(pkg_in, "rb")
    pkg = Package(f.read())
    f.close()
    
    for filename in filenames :
        if filename in pkg.filenames :
            file = pkg.get_file(filename)
            file = neuter_file(file, server_ip, server_port)
            pkg.put_file(filename, file)
            
    if os.path.isdir("files/pkg_add/") :
        if os.path.isdir("files/pkg_add/steamui/") and ("SteamUI_" in pkg_in) :
            path_to_remove = "files/pkg_add/steamui/"
            recursive_pkg("files/pkg_add/steamui/")
            for filename_extra in pkgadd_filelist :
                file2 = open(filename_extra, "rb")
                filedata = file2.read()
                file2.close()
                filename_extra = filename_extra[len(path_to_remove):]
                pkg.put_file(filename_extra, filedata)
        elif os.path.isdir("files/pkg_add/steam/") and ("Steam_" in pkg_in) :
            path_to_remove = "files/pkg_add/steam/"
            recursive_pkg("files/pkg_add/steam/")
            for filename_extra in pkgadd_filelist :
                file2 = open(filename_extra, "rb")
                filedata = file2.read()
                file2.close()
                filename_extra = filename_extra[len(path_to_remove):]
                pkg.put_file(filename_extra, filedata)

    f = open(pkg_out, "wb")
    f.write(pkg.pack())
    f.close()

def recursive_pkg(dir_in) :
    files = os.listdir(dir_in)
    for filename_extra in files:
        if os.path.isfile(os.path.join(dir_in,filename_extra)):
            pkgadd_filelist.append(os.path.join(dir_in,filename_extra))
        elif os.path.isdir(os.path.join(dir_in,filename_extra)):
            recursive_pkg(os.path.join(dir_in, filename_extra))
