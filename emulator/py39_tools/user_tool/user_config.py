import configparser  # , logging
import re


def get_config():
    return config_data


def read_config():

    myDefaults = {
            # IP Binding and other Network Related Configurations
            'adminserverip':  "0.0.0.0",
            'adminserverport':"32666",
            'adminusername':  "",
            'adminpassword':  "",

            # Log Configurations
            'log_level':      "logging.INFO",
            'log_to_file':    "true",
            'logging_enabled':"true",
    }

    c = configparser.ConfigParser(defaults=myDefaults)
    c.read("client_config.ini")

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

    return values


config_data = read_config()


def save_config_value(key, value, old_key=None):
    file_path = 'client_config.ini'

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
            print(f"key {key} value {value}")
            if isinstance(value, int):
                value = str(value)
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