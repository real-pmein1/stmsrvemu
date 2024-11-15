import os
import re
import shutil
import sys

from config import read_config

config = read_config()

# Get the absolute path of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the new path for DocumentRoot and <Directory>
# new_path = os.path.join(script_dir, 'webroot')

# Define the path to the Apache configuration file
# apache_conf_path = os.path.join(script_dir, 'apache24', 'conf', 'httpd.conf')
# default_apache_conf_path = os.path.join(script_dir, 'apache24', 'conf', 'httpd.conf')

# Regular expression patterns for matching relevant lines
docroot_pattern = r'^\s*DocumentRoot\s+"[^"]*"'
dir_pattern = r'^\s*<Directory\s+"(?!\$\{SRVROOT}/cgi-bin)[^"]*">'


# Function to check if a line contains the path
def contains_path(line, path):
    return path in line


# Function to modify paths and save the changes
def modify_apache_config(file_path, port, webroot, community_conf_file):
    if not webroot[0] == "/" and not webroot[1] == ":":
        webroot = os.getcwd() + "/" + webroot
    webroot_temp = ""
    for slash in webroot:
        if slash == "\\":
            slash = "/"
        webroot_temp = webroot_temp + slash
    webroot = webroot_temp
    new_lines = []
    config_modified = False
    # updated_signature = '{}'.format('"Steam Web Server ' + port + '"')
    vhosts_flag = False
    ips_changed_flag = 0
    with open(file_path, 'r') as f:
        for line in f:
            if vhosts_flag:
                new_lines.append("# Virtual hosts")
                new_line = 'Include "{}"'.format(community_conf_file)
                new_lines.append(new_line)
                config_modified = True
                vhosts_flag = False
            else:
                docroot_match = re.match(docroot_pattern, line)
                dir_match = re.match(dir_pattern, line)

                if docroot_match:
                    new_line = 'DocumentRoot "{}"'.format(webroot)
                    new_lines.append(new_line)
                    config_modified = True
                elif dir_match:
                    new_line = '<Directory "{}">'.format(webroot)
                    new_lines.append(new_line)
                    config_modified = True
                elif line.strip().startswith('Listen ') and ips_changed_flag == 0:
                    if config['http_ip'] != "":
                        new_line = 'Listen {}:{}'.format(config['http_ip'], port)
                    else:
                        new_line = 'Listen {}:{}'.format(config['server_ip'], port)
                    new_lines.append(new_line)
                    config_modified = True
                    ips_changed_flag = 1
                elif line.strip().startswith('Listen ') and ips_changed_flag == 1:
                    if config['community_ip'] == "":
                        new_line = 'Listen {}:{}'.format(config['server_ip'], config['community_port'])
                    else:
                        new_line = 'Listen {}:{}'.format(config['community_ip'], config['community_port'])
                    new_lines.append(new_line)
                    config_modified = True
                    ips_changed_flag = 2
                elif ips_changed_flag == 1:
                    if config['community_ip'] == "":
                        new_line = 'Listen {}:{}'.format(config['server_ip'], config['community_port'])
                    else:
                        new_line = 'Listen {}:{}'.format(config['community_ip'], config['community_port'])
                    new_lines.append(new_line)
                    config_modified = True
                    ips_changed_flag = 2
                elif line.strip().startswith('SecServerSignature'):
                    # Check if the value already has quotes
                    sig_value = config['http_signature']
                    if not (sig_value.startswith('"') and sig_value.endswith('"')):
                        sig_value = '"' + sig_value + '"'

                    # Replace the existing line with the updated value
                    new_line = 'SecServerSignature {}'.format(sig_value)
                    new_lines.append(new_line)
                    config_modified = True
                elif re.match(r'^\s*QS_SrvMaxConn\s+', line):
                    # Replace QS_SrvMaxConn line
                    new_line = 'QS_SrvMaxConn {}'.format(config['http_maxconnections'])
                    new_lines.append(new_line)
                    config_modified = True
                elif line.strip().startswith('ServerAdmin'):
                    new_line = 'ServerAdmin {}'.format(config['http_webmaster_email'])
                    new_lines.append(new_line)
                    config_modified = True
                elif line.strip().startswith("# Virtual hosts"):
                    vhosts_flag = True
                else:
                    new_lines.append(line.rstrip())  # Remove extra newline

    if config_modified:
        with open(file_path, 'w') as f:
            f.write('\n'.join(new_lines))
        # print("Apache configuration file modified successfully.")
    # else:
        # print("No relevant configuration found.")


def modify_php_config():
    # Determine the base directory based on whether the script is frozen or not
    if getattr(sys, 'frozen', False):
        # If running as a compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # If running as a normal script
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # Construct the new path with 'php' as the last component
    parent_dir = os.path.join(base_dir, config['apache_root'])
    php_dir = os.path.join(parent_dir, 'php')
    php_ext_dir = os.path.join(php_dir, 'ext')
    php_ini_path = os.path.join(php_dir, 'php.ini')

    # Ensure the paths exist
    if not os.path.exists(php_ini_path):
        raise FileNotFoundError(f"php.ini file not found at: {php_ini_path}")

    with open(php_ini_path, 'r') as file:
        lines = file.readlines()

    # Flags to track if each directive is updated or found
    directives = {
        'extension_dir': False,
        'error_log': False,
        'include_path': False,
        'upload_tmp_dir': False,
        'browscap': False,
        'session.save_path': False
    }

    # Modify existing lines if the directives are found
    for i, line in enumerate(lines):
        if line.lstrip().startswith(';'):
            continue        
        if 'extension_dir' in line:
            php_ext_dir = php_ext_dir.replace("\\", "/")
            lines[i] = f'extension_dir = "{php_ext_dir}"\n'
            directives['extension_dir'] = True
            continue

        if 'error_log' in line:
            php_error_dir = parent_dir.replace("\\", '/')
            lines[i] = f'error_log = "{php_error_dir}/logs"\n'
            directives['error_log'] = True
            continue

        if 'include_path' in line:
            php_include_dir = php_dir.replace("\\", '/')
            lines[i] = f'include_path = "{php_include_dir}/PEAR"\n'
            directives['include_path'] = True
            continue

        if 'upload_tmp_dir' in line:
            php_tmp_dir = php_dir.replace("\\", '/')
            lines[i] = f'upload_tmp_dir = "{php_tmp_dir}/tmp"\n'
            directives['upload_tmp_dir'] = True
            continue

        if 'browscap' in line:
            php_browsecap_dir = php_dir.replace("/", '\\')
            lines[i] = f'browscap = "{php_browsecap_dir}\\extras\\browscap.ini"\n'
            directives['browscap'] = True
            continue

        if 'session.save_path' in line:
            php_session_save_dir = php_dir.replace("\\", '/')
            lines[i] = f'session.save_path = "{php_session_save_dir}/tmp"\n'
            directives['session.save_path'] = True
            continue

    # Append missing directives to the end of the file
    if not directives['extension_dir']:
        php_ext_dir = php_ext_dir.replace("\\", "/")
        lines.append(f'extension_dir = "{php_ext_dir}"\n')

    if not directives['error_log']:
        php_error_dir = parent_dir.replace("\\", '/')
        lines.append(f'error_log = "{php_error_dir}/logs"\n')

    if not directives['include_path']:
        php_include_dir = php_dir.replace("\\", '/')
        lines.append(f'include_path = "{php_include_dir}/PEAR"\n')

    if not directives['upload_tmp_dir']:
        php_tmp_dir = php_dir.replace("\\", '/')
        lines.append(f'upload_tmp_dir = "{php_tmp_dir}/tmp"\n')

    if not directives['browscap']:
        php_browsecap_dir = php_dir.replace("/", '\\')
        lines.append(f'browscap = "{php_browsecap_dir}\\extras\\browscap.ini"\n')

    if not directives['session.save_path']:
        php_session_save_dir = php_dir.replace("\\", '/')
        lines.append(f'session.save_path = "{php_session_save_dir}/tmp"\n')

    # Write the modified contents back to the php.ini file
    with open(php_ini_path, 'w') as file:
        file.writelines(lines)

def make_community_config(comm_conf_file):
    if getattr(sys, 'frozen', False):
        # If running as a compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # If running as a normal script
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # Construct the new path with 'php' as the last component
    community_dir = os.path.join(base_dir, config['community_root'])
    community_dir = community_dir.replace("/", '\\')

    # Remove trailing slash if present
    community_dir = community_dir.rstrip('\\')
    if config['community_ip'] == "":
        community_ip = config['server_ip']
    else:
        community_ip = config['community_ip']
    comm_config = ''
    comm_config += '<VirtualHost ' + community_ip + ':' + config["community_port"] + '>' + '\n'
    comm_config += '\tServerAdmin ' + config['http_webmaster_email'] + '\n'
    comm_config += '\tDocumentRoot "' + community_dir + '"' + '\n'
    comm_config += '\tServerName steamcommunity.com' + '\n'
    comm_config += '\tErrorLog "logs/community_error.log"' + '\n'
    comm_config += '\t<Directory "' + community_dir + '">' + '\n'
    comm_config += '\t\tOptions Indexes FollowSymLinks Includes ExecCGI' + '\n'
    comm_config += '\t\tAllowOverride All' + '\n'
    comm_config += '\t\tRequire all granted' + '\n'
    comm_config += '\t</Directory>' + '\n'
    comm_config += '</VirtualHost>'

    with open(comm_conf_file, 'w') as conf_file:
        conf_file.write(comm_config)

def check_config(apache_conf_path, port, webroot, default_apache_conf_path, apache_conf_dir, apache_root, community_conf_file, community_conf_vh):
    # Modify the Apache configuration file

    if os.path.isfile(apache_conf_path):
        modify_apache_config(apache_conf_path, port, webroot, community_conf_vh)
    else:
        shutil.copyfile(default_apache_conf_path, apache_conf_path)
        modify_apache_config(apache_conf_path, port, webroot, community_conf_vh)
    modify_php_config()
    try:
        os.remove(community_conf_file)
    except:
        pass
    if not os.path.isfile(community_conf_file):
        make_community_config(community_conf_file)