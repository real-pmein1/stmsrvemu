import errno
import os
from os.path import join as pjoin

from config import get_config
from utils import log

config = get_config()

# List of directory paths to create
dirs_to_create = [
    config["v3storagedir2"],
    config["v3manifestdir2"],
    config["v2storagedir"],
    config["v4storagedir"],
    config["v2manifestdir"],
    config["v4manifestdir"],
    config["storagedir"],
    config["manifestdir"],
    config["betastoragedir"],
    config["betamanifestdir"],
    config["packagedir"],
    config['configsdir'],
    pjoin(config['configsdir'], "custom_neuter"),
    config["steam2sdkdir"],
    "debug",
    "logs",
    "client",
    "clientstats",
    pjoin("clientstats", "clientstats"),
    pjoin("clientstats", "gamestats"),
    pjoin("clientstats", "bugreports"),
    pjoin("clientstats", "steamstats"),
    pjoin("clientstats", "phonehome"),
    pjoin("clientstats", "exceptionlogs"),
    pjoin("clientstats", "crashdump"),
    pjoin("clientstats", "surveys"),
    pjoin("clientstats", "downloadstats"),
    "files",
    pjoin("files", "temp"),
    pjoin("files", "appcache"),
    pjoin("files", "appcache", "2008"),
    pjoin("files", "appcache", "2009_2010"),
    pjoin("files", "appcache", "2010_2011"),
    pjoin("files", "cache"),
    pjoin("files", "cache", "appinfo"),
    pjoin("files", "cache", "appinfo", "2008"),
    pjoin("files", "cache", "appinfo", "2008", "lan"),
    pjoin("files", "cache", "appinfo", "2008", "wan"),
    pjoin("files", "cache", "appinfo", "2009_2010"),
    pjoin("files", "cache", "appinfo", "2009_2010", "lan"),
    pjoin("files", "cache", "appinfo", "2009_2010", "wan"),
    pjoin("files", "cache", "appinfo", "2010_2011"),
    pjoin("files", "cache", "appinfo", "2010_2011", "lan"),
    pjoin("files", "cache", "appinfo", "2010_2011", "wan"),
    pjoin("files", "cache", "internal"),
    pjoin("files", "cache", "external"),
    pjoin("files", "beta1_ftp"),
    pjoin("files", "email_tpl"),
    pjoin("files", "sql"),
    pjoin("files", "mdb"),
    pjoin("files", "mdb", "data"),
    pjoin("files", "mod_blob"),
    pjoin("files", "mod_package"),
    pjoin("files", "mod_package", "2013"),
    pjoin("files", "mod_package", "2016"),
    pjoin("files", "mod_pkg", "steam", "global"),
    pjoin("files", "mod_pkg", "steamui", "global"),
]

def create_dirs():
    rename_custom_folder()
    # Create directories
    for dir_path in dirs_to_create:
        try:
            os.makedirs(dir_path)
        except OSError as e:
            if e.errno != errno.EEXIST:  # Ignore if the directory already exists
                raise


def rename_custom_folder():
    """Renames specific folders to new names if they exist."""
    folders_to_rename = [
        ("files/custom", "files/mod_blob"),
        ("files/pkg_add", "files/mod_pkg")
    ]

    for old_folder, new_folder in folders_to_rename:
        try:
            if os.path.exists(old_folder):
                os.rename(old_folder, new_folder)
                log.info(f"Folder renamed from {old_folder} to {new_folder}")
            else:
                pass
        except:
            pass