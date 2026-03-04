import os
import logging
from sqlalchemy.orm import Session
from sqlalchemy import delete

from utilities.database.dbengine import DatabaseDriver
from utilities.database.base_dbdriver import LegacyGameKeys

# Lazy logger initialization
_log = None


def get_log():
    global _log
    if _log is None:
        _log = logging.getLogger("LegacyGameKeys")
    return _log


# Default game keys
keys = {
    "2620": ["HKPHWT3S8XHU2YHW46C4"],
    "2630": ["XEZLGZWXXQZGGEGUEEFC"],
    "2640": ["74B3JN4N4WT4WRHN64BF"],
    "2930": ["Serial           = FNHa7-VDtR5-pGpb8-XKYVS-Cimi8-DSI1879",
             "Serial           = 67WJK-BaDe7-b6oeC-V5P9C-GNeiD-AGE1764"],
    "3000": ["37A7R-AL9CF-WR3WT-Y4L4F-FLR33"],
    "3010": ["LCWCR-EXEW7-TXCL9-XCK49-XRFWY"],
    "3970": ["D23BDPBABCRPTABP 15"],
    "9050": ["2DR3ABTCAJLBBLJH 4C"],
    "9070": ["BSSDWJBAS7CBDPDH 44"],
    "10000": ["SSGWPH3HT3DCWP2T 76"],
    "13230": ["G8FQ-6MAW-4ZB4-WYAE",
              "YZAR-RBU8-C43Q-YCJX",
              "FCMJ-EYS8-4BAW-VPN2",
              "6MG4-ZNSV-896A-F3LN",
              "UCQH-F6CJ-ASME-BT5N",
              "DNQF-26CY-8NDD-BTUR",
              "FKAK-UAC6-NDSB-Y5B4",
              "AJDD-SGUX-KUCT-HXMQ",
              "MRTW-8CTL-LAZU-8PB2",
              "UCMG-FYSP-99MW-DA7U",
              "NL64-W2T4-DXEA-2M5C",
              "47RY-59AT-Q395-TVQT",
              "F7CJ-4FSC-WNSM-ZG4M",
              "8XC9-MF45-867R-ZKYD",
              "9RD6-9GS4-CA7U-ZUZT",
              "TFTB-MCVH-KB4Z-Q3TG",
              "FY8K-N755-EFAQ-KE94",
              "2HXU-RLBH-T28Y-6WGG",
              "P2Q2-S72U-BHEK-B65C",
              "M8AX-6BUU-DHHL-GSFM",
              "WC2M-FS5V-V8JE-L55V",
              "3GWT-PJD2-6PQG-NYHV",
              "DF2E-LSKZ-2PVH-LSPB",
              "VUEF-FKUA-FAMN-EJJJ",
              "BVFB-GMUA-9RU6-WPEA",
              "MW3X-JVVG-MQH9-L9JF",
              "HHWN-QJTT-6FTG-6E3G",
              "UY4G-PXT9-U8MQ-5B8J",
              "FAUJ-AEBG-CRAF-964N",
              "SHZC-RQT6-4X4Y-P5Z2",
              "SLQC-X6SN-SWLA-T75T",
              "ENDM-2G4K-ZWAV-HJKF",
              "TG3B-PUV6-8ALY-4Y4C",
              "8489-X7VU-CSPJ-KFXG"]
}


def insert_gamekeys(db_host=None, db_user=None, db_pass=None, db_port=None, database=None):
    """
    Insert legacy game keys into the database using SQLAlchemy.

    Parameters are kept for backwards compatibility but are ignored.
    The database connection is handled by DatabaseDriver using globalvars.config.
    """
    try:
        db_driver = DatabaseDriver()
        session_factory = DatabaseDriver.get_session()

        with session_factory() as session:
            # Clear existing entries
            session.execute(delete(LegacyGameKeys))
            session.commit()

            # Load extra game keys from config file if it exists
            all_keys = keys.copy()
            extra_keys_path = "files/configs/extra_gamekeys.txt"

            if os.path.isfile(extra_keys_path):
                with open(extra_keys_path, 'r') as f:
                    file_lines = f.readlines()

                for line in file_lines:
                    line = line.strip('\n').strip('\r')
                    if '=' in line:
                        parts = line.split('=')
                        if len(parts) >= 2:
                            appid = parts[0].strip()
                            gamekey = parts[1].strip()

                            if appid in all_keys:
                                if gamekey not in all_keys[appid]:
                                    all_keys[appid].append(gamekey)
                            else:
                                all_keys[appid] = [gamekey]

            # Insert all game keys
            for appid, gamekeys in all_keys.items():
                for gamekey in gamekeys:
                    entry = LegacyGameKeys(
                        AppID=int(appid),
                        GameKey=gamekey,
                        SteamID=None
                    )
                    session.add(entry)

            session.commit()
            get_log().info(f"Inserted {sum(len(v) for v in all_keys.values())} legacy game keys")

    except Exception as e:
        get_log().error(f"Error inserting legacy game keys: {e}")
        raise
