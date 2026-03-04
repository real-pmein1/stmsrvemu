import logging

import globalvars
from utilities.database import dbengine, base_dbdriver

log = logging.getLogger('SETTINGSDB')


class settings_dbdriver:
    def __init__(self):
        while not globalvars.mariadb_initialized:
            continue
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()
        self.session = self.db_driver.get_session()
        self.StmserverSettings = base_dbdriver.StmserverSettings

    def set_setting(self, key, value):
        try:
            record = (
                self.session.query(self.StmserverSettings)
                .filter_by(setting=key)
                .first()
            )
            if record:
                record.value = value
            else:
                record = self.StmserverSettings(setting=key, value=value)
                self.session.add(record)
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"Failed to set setting {key}: {e}")
            self.session.rollback()
            return False

    def get_setting(self, key):
        rec = (
            self.session.query(self.StmserverSettings)
            .filter_by(setting=key)
            .first()
        )
        return rec.value if rec else None

    def get_all_settings(self):
        """Fetch all settings in a single query. Returns dict of key->value."""
        try:
            records = self.session.query(self.StmserverSettings).all()
            return {rec.setting: rec.value for rec in records}
        except Exception as e:
            log.error(f"Failed to get all settings: {e}")
            return {}

    def batch_sync_settings(self, settings_dict):
        """Batch upsert settings. Only updates changed values.

        Args:
            settings_dict: Dictionary of key->value pairs to sync.
        """
        try:
            # Fetch all existing settings in one query
            existing = self.get_all_settings()

            # Collect changes
            to_update = []
            to_insert = []

            for key, value in settings_dict.items():
                if key in existing:
                    if existing[key] != value:
                        to_update.append((key, value))
                else:
                    to_insert.append((key, value))

            # Apply updates
            if to_update:
                for key, value in to_update:
                    self.session.query(self.StmserverSettings).filter_by(
                        setting=key
                    ).update({'value': value})

            # Apply inserts
            if to_insert:
                for key, value in to_insert:
                    record = self.StmserverSettings(setting=key, value=value)
                    self.session.add(record)

            # Single commit for all changes
            if to_update or to_insert:
                self.session.commit()
                log.debug(f"Synced {len(to_update)} updates, {len(to_insert)} inserts")

            return True
        except Exception as e:
            log.error(f"Failed to batch sync settings: {e}")
            self.session.rollback()
            return False
