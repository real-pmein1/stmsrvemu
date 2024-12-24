import errno
import os

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
    "logs",
    "client",
    "clientstats",
    "clientstats/clientstats",
    "clientstats/gamestats",
    "clientstats/bugreports",
    "clientstats/steamstats",
    "clientstats/phonehome",
    "clientstats/exceptionlogs",
    "clientstats/crashdump",
    "clientstats/surveys",
    "clientstats/downloadstats",
    "files",
    config['configsdir'],
    "files/temp",
    "files/cache",
    "files/beta1_ftp",
    "files/email_tpl",
    "files/sql",
    "files/mdb",
    "files/mdb/data",
    "files/mod_blob",
    "files/mod_pkg/steam/global",
    "files/mod_pkg/steamui/global",
    config["steam2sdkdir"],
    "debug",
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