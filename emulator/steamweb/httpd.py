import os
import re
import shutil

# Get the absolute path of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the new path for DocumentRoot and <Directory>
#new_path = os.path.join(script_dir, 'webroot')

# Define the path to the Apache configuration file
#apache_conf_path = os.path.join(script_dir, 'apache24', 'conf', 'httpd.conf')
#default_apache_conf_path = os.path.join(script_dir, 'apache24', 'conf', 'httpd.conf')

# Regular expression patterns for matching relevant lines
docroot_pattern = r'^\s*DocumentRoot\s+"[^"]*"'
dir_pattern = r'^\s*<Directory\s+"[^"]*">'

# Function to check if a line contains the path
def contains_path(line, path):
    return path in line

# Function to modify paths and save the changes
def modify_apache_config(file_path, ip, port, webroot):
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
    updated_signature = '{}'.format('"Steam Web Server ' + port + '"')

    with open(file_path, 'r') as f:
        for line in f:
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
            elif line.strip().startswith('Listen '):
                new_line = 'Listen {}:{}'.format(ip, port)
                new_lines.append(new_line)
                config_modified = True
            elif line.strip().startswith('SecServerSignature'):
                # Replace the existing line with the updated value
                new_line = 'SecServerSignature {}'.format(updated_signature)
                new_lines.append(new_line)
                config_modified = True
            elif re.match(r'^\s*QS_SrvMaxConn\s+', line):
                # Replace QS_SrvMaxConn line
                new_line = 'QS_SrvMaxConn {}'.format("99999")
                new_lines.append(new_line)
                config_modified = True
            elif line.strip().startswith('ServerAdmin'):
                new_line = 'ServerAdmin {}'.format("admin@stmserver.com")
                new_lines.append(new_line)
                config_modified = True
            else:
                new_lines.append(line.rstrip())  # Remove extra newline

    if config_modified:
        with open(file_path, 'w') as f:
            f.write('\n'.join(new_lines))
        #print("Apache configuration file modified successfully.")
    #else:
        #print("No relevant configuration found.")


def check_config(apache_conf_path, ip, port, webroot, default_apache_conf_path):
    # Modify the Apache configuration file
    if os.path.isfile(apache_conf_path):
        modify_apache_config(apache_conf_path, ip, port, webroot)
    else:
        shutil.copyfile(default_apache_conf_path, apache_conf_path)
        modify_apache_config(apache_conf_path, ip, port, webroot)
