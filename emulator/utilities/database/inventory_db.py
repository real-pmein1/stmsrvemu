"""
Inventory database driver for gameserver item operations.

Provides database operations for:
- Loading user items
- Creating items
- Granting items
- Deleting temporary items
- User group membership queries
"""
import logging
import time
from datetime import datetime

import globalvars
from utilities.database.base_dbdriver import (
    PersistentItem as DBPersistentItem,
    PersistentItemAttribute as DBPersistentItemAttribute,
    CommunityClanMembers,
    CommunityClanRegistry,
    FriendsGroupMembers,
)
from utilities.database import dbengine

log = logging.getLogger('INVENTORYDB')


class BaseInventoryDBDriver:
    """Database driver for inventory operations."""

    def __init__(self, config=None):
        # Wait until MariaDB is initialized
        while globalvars.mariadb_initialized != True:
            continue

        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()
        self.session = self.db_driver.get_session()

        # ORM classes
        self.PersistentItem = DBPersistentItem
        self.PersistentItemAttribute = DBPersistentItemAttribute
        self.CommunityClanMembers = CommunityClanMembers
        self.CommunityClanRegistry = CommunityClanRegistry
        self.FriendsGroupMembers = FriendsGroupMembers

    def get_user_items(self, steam_id, app_id):
        """
        Get all persistent items for a user in a specific app.

        Args:
            steam_id: The user's Steam ID (64-bit)
            app_id: The application ID

        Returns:
            List of PersistentItem database objects
        """
        try:
            items = (
                self.session
                .query(self.PersistentItem)
                .filter_by(steam_id=steam_id, app_id=app_id)
                .all()
            )
            return items
        except Exception as e:
            log.error(f"Failed to get user items: {e}")
            self.session.rollback()
            return []

    def get_item_by_id(self, item_id):
        """
        Get a specific item by its unique item ID.

        Args:
            item_id: The item's unique ID

        Returns:
            PersistentItem object or None
        """
        try:
            item = (
                self.session
                .query(self.PersistentItem)
                .filter_by(item_id=item_id)
                .first()
            )
            return item
        except Exception as e:
            log.error(f"Failed to get item by ID: {e}")
            self.session.rollback()
            return None

    def create_item(self, steam_id, app_id, definition_index, quality, item_level=1,
                    inventory_token=0, quantity=1, attributes=None):
        """
        Create a new persistent item for a user.

        Args:
            steam_id: The user's Steam ID (64-bit)
            app_id: The application ID
            definition_index: Item definition index
            quality: Item quality (EItemQuality)
            item_level: Item level (default 1)
            inventory_token: Inventory position (default 0)
            quantity: Item quantity (default 1)
            attributes: List of tuples (definition_index, value) for attributes

        Returns:
            Tuple of (item_id, PersistentItem) or (0, None) on failure
        """
        try:
            # Generate a unique item ID based on timestamp
            item_id = int(time.time() * 1000000) & 0x7FFFFFFFFFFFFFFF

            # Create the item
            db_item = self.PersistentItem(
                steam_id=steam_id,
                app_id=app_id,
                item_id=item_id,
                definition_index=definition_index,
                item_level=item_level,
                quality=quality,
                inventory_token=inventory_token,
                quantity=quantity,
            )
            self.session.add(db_item)
            self.session.flush()  # Get the generated ID

            # Add attributes if provided
            if attributes:
                for attr_def_index, attr_value in attributes:
                    attr = self.PersistentItemAttribute(
                        item_id=db_item.id,
                        definition_index=attr_def_index,
                        value=attr_value,
                    )
                    self.session.add(attr)

            self.session.commit()
            log.info(f"Created item {item_id} for user {steam_id}")
            return item_id, db_item

        except Exception as e:
            log.error(f"Failed to create item: {e}")
            self.session.rollback()
            return 0, None

    def grant_item(self, item_id, target_steam_id):
        """
        Grant an existing item to a different user (transfer ownership).

        Args:
            item_id: The item's unique ID
            target_steam_id: The new owner's Steam ID

        Returns:
            True on success, False on failure
        """
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                log.error(f"Item {item_id} not found for granting")
                return False

            item.steam_id = target_steam_id
            self.session.commit()
            log.info(f"Granted item {item_id} to user {target_steam_id}")
            return True

        except Exception as e:
            log.error(f"Failed to grant item: {e}")
            self.session.rollback()
            return False

    def delete_item(self, item_id):
        """
        Delete an item by its unique ID.

        Args:
            item_id: The item's unique ID

        Returns:
            True on success, False on failure
        """
        try:
            # Delete attributes first
            self.session.query(self.PersistentItemAttribute).filter(
                self.PersistentItemAttribute.item_id == self.session.query(self.PersistentItem.id).filter_by(item_id=item_id).scalar_subquery()
            ).delete(synchronize_session=False)

            # Delete the item
            deleted = (
                self.session
                .query(self.PersistentItem)
                .filter_by(item_id=item_id)
                .delete()
            )
            self.session.commit()
            if deleted:
                log.info(f"Deleted item {item_id}")
            return deleted > 0

        except Exception as e:
            log.error(f"Failed to delete item: {e}")
            self.session.rollback()
            return False

    def delete_temp_items(self, steam_id, app_id=None):
        """
        Delete all temporary items for a user.
        Temporary items have item_ids in the temporary range (high bit set).

        Args:
            steam_id: The user's Steam ID
            app_id: Optional app ID to filter by

        Returns:
            Number of items deleted
        """
        try:
            query = self.session.query(self.PersistentItem).filter(
                self.PersistentItem.steam_id == steam_id,
                self.PersistentItem.item_id >= 0x8000000000000000  # Temporary item range
            )
            if app_id:
                query = query.filter(self.PersistentItem.app_id == app_id)

            # Get item DB IDs for attribute deletion
            item_ids = [item.id for item in query.all()]

            if item_ids:
                # Delete attributes
                self.session.query(self.PersistentItemAttribute).filter(
                    self.PersistentItemAttribute.item_id.in_(item_ids)
                ).delete(synchronize_session=False)

            # Delete items
            deleted = query.delete(synchronize_session=False)
            self.session.commit()
            log.info(f"Deleted {deleted} temp items for user {steam_id}")
            return deleted

        except Exception as e:
            log.error(f"Failed to delete temp items: {e}")
            self.session.rollback()
            return 0

    def update_item_position(self, item_id, new_position):
        """
        Update an item's inventory position.

        Args:
            item_id: The item's unique ID
            new_position: The new inventory position

        Returns:
            True on success, False on failure
        """
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                log.error(f"Item {item_id} not found for position update")
                return False

            item.inventory_token = new_position
            self.session.commit()
            log.info(f"Updated item {item_id} position to {new_position}")
            return True

        except Exception as e:
            log.error(f"Failed to update item position: {e}")
            self.session.rollback()
            return False

    def get_user_group_status(self, steam_id_user, steam_id_group):
        """
        Get a user's membership status in a Steam group/clan.

        Args:
            steam_id_user: The user's Steam ID (64-bit)
            steam_id_group: The group's Steam ID (64-bit)

        Returns:
            Tuple of (clan_relationship, clan_rank) or (0, 0) if not a member
        """
        try:
            # Extract account ID from Steam ID (lower 32 bits)
            account_id = steam_id_user & 0xFFFFFFFF
            # Extract clan ID from group Steam ID
            clan_id = steam_id_group & 0xFFFFFFFF

            # Check clan membership
            membership = (
                self.session
                .query(self.CommunityClanMembers)
                .filter_by(
                    friendRegistryID=account_id,
                    CommunityClanID=clan_id
                )
                .first()
            )

            if membership:
                # Return relationship and rank from clan membership
                return membership.relationship, membership.user_rank

            # Check friends group membership
            group_membership = (
                self.session
                .query(self.FriendsGroupMembers)
                .filter_by(
                    friendRegistryID=account_id,
                    GroupID=clan_id
                )
                .first()
            )

            if group_membership:
                return group_membership.relation, 0

            return 0, 0  # Not a member

        except Exception as e:
            log.error(f"Failed to get user group status: {e}")
            self.session.rollback()
            return 0, 0

    def update_item_quantity(self, item_id, new_quantity):
        """
        Update an item's quantity.

        Args:
            item_id: The item's unique ID
            new_quantity: The new quantity value

        Returns:
            True on success, False on failure
        """
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                log.error(f"Item {item_id} not found for quantity update")
                return False

            item.quantity = new_quantity
            self.session.commit()
            log.info(f"Updated item {item_id} quantity to {new_quantity}")
            return True

        except Exception as e:
            log.error(f"Failed to update item quantity: {e}")
            self.session.rollback()
            return False

    def get_item_blob(self, item_id):
        """
        Get an item's blob data.

        Args:
            item_id: The item's unique ID

        Returns:
            Blob data as bytes, or empty bytes if not found/no blob
        """
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                log.error(f"Item {item_id} not found for blob retrieval")
                return b''

            return item.blob_data if item.blob_data else b''

        except Exception as e:
            log.error(f"Failed to get item blob: {e}")
            self.session.rollback()
            return b''

    def set_item_blob(self, item_id, blob_data):
        """
        Set an item's blob data.

        Args:
            item_id: The item's unique ID
            blob_data: The blob data to set (up to 1024 bytes)

        Returns:
            True on success, False on failure
        """
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                log.error(f"Item {item_id} not found for blob update")
                return False

            # Truncate to max 1024 bytes
            item.blob_data = blob_data[:1024] if blob_data else None
            self.session.commit()
            log.info(f"Updated item {item_id} blob data ({len(blob_data) if blob_data else 0} bytes)")
            return True

        except Exception as e:
            log.error(f"Failed to set item blob: {e}")
            self.session.rollback()
            return False


# Lazily instantiate module-level driver
_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = BaseInventoryDBDriver(None)
    return _driver


def __getattr__(name):
    """Delegate attribute access to the underlying driver instance."""
    return getattr(_get_driver(), name)
