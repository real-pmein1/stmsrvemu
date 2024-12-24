import configparser  # , logging
import re

config_data = {}

def get_config():
    return config_data


def read_config():
    global config_data  # Declare config_data as global to modify it directly

    # log = logging.getLogger("root")

    # log.info("Reloading config")

    myDefaults = {
            # IP Binding and other Network Related Configurations
            'auto_public_ip':                      "true",
            'auto_server_ip':                      "true",
            'public_ip':                           "0.0.0.0",
            'server_ip':                           "0.0.0.0",
            'server_sm':                           "255.255.255.0",

            # Log Configurations
            'log_level':                           "logging.INFO",
            'log_to_file':                         "true",
            'logging_enabled':                     "true",

            # File Path Configurations
            'configsdir':                          "files/configs/",
            'betastoragedir':                      "files/betastorages/",
            'storagedir':                          "files/storages/",
            'v2storagedir':                        "files/v2storages/",  # FIXME Eventually Deprecate After v.8 Release
            'v3storagedir2':                       "files/v3storages2/",  # FIXME Eventually Deprecate After v.8 Release
            'v4storagedir':                        "files/v4storages/",  # FIXME Eventually Deprecate After v.8 Release
            'betamanifestdir':                     "files/betamanifests/",
            'manifestdir':                         "files/manifests/",
            'v2manifestdir':                       "files/v2manifests/",  # FIXME Eventually Deprecate After v.8 Release
            'v3manifestdir2':                      "files/v3manifests2/",  # FIXME Eventually Deprecate After v.8 Release
            'v4manifestdir':                       "files/v4manifests/",  # FIXME Eventually Deprecate After v.8 Release
            'customstoragedir':                    "files/custom_storages/",  # FIXME not needed, if i can get sdk stuff working
            'custommanifestdir':                   "files/custom_manifests/",  # FIXME not needed, if i can get sdk stuff working
            'steam2sdkdir':                        "files/steam2_sdk_depots/",
            'packagedir':                          "files/packages/",
            'blobdir':                             "files/blobs/",
            'vacmoduledir':                        "files/vacmodules/",

            # Cafe Configurations
            'cafeuser':                            "noaccountconfigured",
            'cafepass':                            "bar",
            'cafemacs':                            "00-00-00-00-00-00;",
            'cafetime':                            "60",
            'cafe_use_mac_auth':                   "false",

            # SDK/SteamWorks ContentServer Configurations
            'sdk_ip':                              "0.0.0.0",
            'sdk_port':                            "27030",
            'use_sdk':                             "false",
            'use_sdk_as_cs':                       "false",

            # White/Black List Configurations
            'enable_whitelist':                    "false",
            'enable_blacklist':                    "true",
            'ip_blacklist':                        "ip_blacklist.txt",
            'ip_whitelist':                        "ip_whitelist.txt",

            # Email/SMTP Configurations
            'smtp_enabled':                        "false",
            'smtp_serverip':                       "",  # Formerly smtp_server
            'smtp_serverport':                     "",  # Formerly smtp_port
            'smtp_username':                       "",
            'smtp_security':                       "tls",
            'smtp_password':                       "",
            'network_logo':                        "",  # Used in email template
            'network_name':                        "STMServer",  # Used in email template
            'email_location_support':              "false",  # Adds ip location to email for change password attempts or failed logins
            'force_email_verification':            "false",  # Sets whether to require email accounts to be verified before logging in
            'support_email':                       "support@stmserver.com",  # Used in email template as replyto: email

            # Database Configurations
            'use_builtin_mysql':                   "true",
            'database_username':                   "stmserver",
            'database_password':                   "",
            'database':                            "stmserver",
            'database_host':                       "127.0.0.1",
            'database_port':                       "3306",

            # Server Port Configurations
            'ftp_server_port':                     "21",
            'tracker_server_port':                 "1200",
            'masterhl1_server_port':               "27010",
            'masterhl2_server_port':               "27010",
            'masterrdkf_server_port':              "27010",
            'vac_server_port':                     "27012",
            'cser_server_port':                    "27013",
            'cm_unencrypted_server_port':          "27014",  # Formerly friends_server_port
            'cm_encrypted_server_port':            "27017",  # Formerly cm_server_port
            'content_server_port':                 "27030",
            'clupd_server_port':                   "27031",
            'harvest_server_port':                 "27032",
            'config_server_port':                  "27035",
            'contentdir_server_port':              "27037",
            'dir_server_port':                     "27038",
            'auth_server_port':                    "27039",
            'validation_port':                     "27040",
            'vtt_server_port':                     "27046",  # Formerly vss_server_port1
            'cafe_server_port':                    "27047",  # Formerly vss_server_port2
            'admin_server_port':                   "32677",  # TODO finish for v.81; For remote administration tool
            'ping_server_port':                    "27057",  # server used to ping clients to calculate latency

            # Content Server and CM Related Configurations
            'cellid':                              "1",
            'override_ip_country_region':          "false",  # Formerly server_region and prior to that: cs_region
            'enable_custom_banner':                "false",
            'custom_banner_url':                   "",
            'cache_sdk_depot':                     "false",

            # RSA Key Configurations
            'main_key_n':                          "0x86724794f8a0fcb0c129b979e7af2e1e309303a7042503d835708873b1df8a9e307c228b9c0862f8f5dbe6f81579233db8a4fe6ba14551679ad72c01973b5ee4ecf8ca2c21524b125bb06cfa0047e2d202c2a70b7f71ad7d1c3665e557a7387bbc43fe52244e58d91a14c660a84b6ae6fdc857b3f595376a8e484cb6b90cc992f5c57cccb1a1197ee90814186b046968f872b84297dad46ed4119ae0f402803108ad95777615c827de8372487a22902cb288bcbad7bc4a842e03a33bd26e052386cbc088c3932bdd1ec4fee1f734fe5eeec55d51c91e1d9e5eae46cf7aac15b2654af8e6c9443b41e92568cce79c08ab6fa61601e4eed791f0436fdc296bb373",
            'main_key_e':                          "0x07e89acc87188755b1027452770a4e01c69f3c733c7aa5df8aac44430a768faef3cb11174569e7b44ab2951da6e90212b0822d1563d6e6abbdd06c0017f46efe684adeb74d4113798cec42a54b4f85d01e47af79259d4670c56c9c950527f443838b876e3e5ef62ae36aa241ebc83376ffde9bbf4aae6cabea407cfbb08848179e466bcb046b0a857d821c5888fcd95b2aae1b92aa64f3a6037295144aa45d0dbebce075023523bce4243ae194258026fc879656560c109ea9547a002db38b89caac90d75758e74c5616ed9816f3ed130ff6926a1597380b6fc98b5eeefc5104502d9bee9da296ca26b32d9094452ab1eb9cf970acabeecde6b1ffae57b56401",
            'net_key_n':                           "0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059",
            'net_key_d':                           "0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9d",

            # Apache/HTTP Configurations
            'use_webserver':                       "true",
            'use_external_webserver':              "false",
            'store_url_new':                       "/storefront",
            'support_url_new':                     "/support",
            'http_ip':                             "",
            'http_domainname':                     "",  # Formerly http_name
            'community_ip':                        "",
            'community_domainname':                "",
            'community_port':                      "443",
            'apache_root':                         "files/webserver/apache24/",
            'web_root':                            "files/webserver/webroot/",
            'community_root':                      "files/webserver/community/",
            'http_maxconnections':                 "20",
            'http_signature':                      "STMServer Network",
            'http_webmaster_email':                "webmaster@stmserver.com",  # formerly admin_email

            # Blob Configurations
            'steam_date':                          "2004^10^01",
            'steam_time':                          "00:14:03",
            'subtract_time':                       "0",
            'auto_blobs':                          "false",
            'disable_steam3_purchasing':           "true",
            'alter_preload_unlocks':               "true",

            # (Create Account) Suggested Name Configurations
            'amount_of_suggested_names':           "10",
            'use_builtin_suggested_name_modifiers':"true",

            # Misc Configurations
            'emu_auto_update':                     "true",
            'enable_steam3_servers':               "false",
            'allow_harvest_upload':                "True",
            'storage_check':                       "false",  # Not Needed
            'universe':                            "1",
            'hldsupkg':                            "",
            'ticket_expiration_time_length':       "0d0h45m0s",
            'run_all_servers':                     "false",

            # Split-Server Related Configurations (Unused until servers can be split apart)
            'harvest_ip':                          "0.0.0.0",
            'masterdir_ipport':                    "127.0.0.1:27038",  # TODO Finish for v.81
            'csds_ipport':                         "",
            'tracker_ip':                          "",
            'dir_ismaster':                        "true",
            'peer_password':                       "",

            # (CM) Connection Manager Server Configurations
            'overwrite_machineids':                "true",

            # Developer Related Configurations
            'reset_clears_client':                 "false",
            'disable_storage_neutering':           "false",  # Formerly disable_gcf_converter
            'uat':                                 "0",
            'from_source':                         "false",  # if true, runs neuter app from source from py39_tools/neuter/neuter_app.py

            # Admin Server Related Configurations
            'admin_inactive_timout':               "600",  # TODO Release for .81 - adminserver related

            # Security Related
            'use_random_keys':                     "false",

            # Script reload paths
            'DirectoryServer_script_path':         "servers/directoryserver.py",
            'FTPUpdateServer_script_path':         "steamweb/ftp.py",
            'CMUDP27014_script_path':              "steam3/cmserver_udp.py",
            'CMUDP27017_script_path':              "steam3/cmserver_udp.py",
            'CMTCP27014_script_path':              "steam3/cmserver_tcp.py",
            'CMTCP27017_script_path':              "steam3/cmserver_tcp.py",
            'ContentListServer_script_path':       "servers/contentlistserver.py",
            'AuthServer_script_path':              "servers/authserver.py",
            'Beta1Server_script_path':             "servers/beta_authserver.py",
            'ClientUpdateServer_script_path':      "servers/clientupdateserver.py",
            'ConfigServer_script_path':            "servers/configserver.py",
            'ContentServer_script_path':           "servers/contentserver.py",
            'CSERServer_script_path':              "servers/cserserver.py",
            'HarvestServer_script_path':           "servers/harvestserver.py",
            'MasterServer_script_path':            "servers/masterserver.py",
            'TrackerServer_script_path':           "servers/trackerserver_beta.py",
            'ValidationServer_script_path':        "servers/validationserver.py",
            'VAC1Server_script_path':              "servers/valve_anticheat1.py",
            'VTTServer_script_path':               "servers/vttserver.py",
            'CafeServer_script_path':              "servers/vttserver.py",
    }

    c = configparser.ConfigParser(defaults=myDefaults)
    c.read("emulator.ini")

    values = {}

    for name, value in c.items("config"):
        # Regex pattern to handle quoted values and comments correctly
        match = re.match(r'^\s*"([^"]*)"|\'([^\']*)\'|([^;#]*)', value)
        if match:
            if match.group(1):
                clean_value = match.group(1)  # Matched double-quoted part
            elif match.group(2):
                clean_value = match.group(2)  # Matched single-quoted part
            else:
                clean_value = match.group(3).strip()  # Matched unquoted part
            values[name] = clean_value
        else:
            values[name] = value.strip()  # Fallback strip for any unexpected format

    config_data = values  # Update the global config_data directly

    # FIXME Technically we shouldnt return ANYTHING as the code should be using get_config to grab it from memory to keep things consistent and less confusing!
    return values


read_config()


def save_config_value(key, value, old_key=None):
    file_path = 'emulator.ini'

    # Read the existing content of the file
    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Check if the old_key or key already exists
    key_exists = False
    for i, line in enumerate(lines):
        # Check for the key (active or commented)
        if ((old_key and line.startswith(old_key + '=')) or
            line.startswith(key + '=') or
            line.lstrip().startswith(';' + key + '=')):
            # If key is commented, remove the comment
            if line.lstrip().startswith(';' + key + '='):
                line = line.lstrip()[1:]
                lines[i] = line  # Ensure the modified line is saved back to the list

            # Replace the line with new key and value
            lines[i] = key + '=' + value + '\n'
            key_exists = True
            break

    # If the key doesn't exist, add it as a new line
    lastchar = lines[len(lines) - 1][-1:]
    if lastchar != "\n":
        lastline = lines[-1:][0]
        del lines[-1:]
        lines.append(lastline + "\n")
    if not key_exists:
        lines.append(key + '=' + value + '\n')

    # Write the modified content back to the file
    with open(file_path, 'w') as file:
        file.writelines(lines)