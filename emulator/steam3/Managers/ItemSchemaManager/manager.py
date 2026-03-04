"""
Item Schema Manager for loading and validating game item schemas.

Loads item schemas from JSON files in the item_schemas directory and provides
lookup functions for item validation and definition retrieval.
"""
import json
import logging
import os
from typing import Dict, Optional, List, Any

log = logging.getLogger('ITEMSCHEMA')


class ItemSchemaManager:
    """
    Manages item schemas for various games (TF2, CS:GO, Dota 2, Portal 2, etc).

    Provides functionality to:
    - Load item schemas from JSON files
    - Validate item definition indices
    - Look up item definitions by defindex
    - Get quality names and origin information
    """

    # Mapping of app IDs to schema file names
    APP_ID_TO_SCHEMA = {
        440: 'TeamFortress2.json',          # TF2
        520: 'TeamFortress2Beta.json',      # TF2 Beta
        730: 'CounterStrikeGlobalOffensive.json',  # CS:GO
        570: 'Dota2.json',                  # Dota 2
        205790: 'Dota2Test.json',           # Dota 2 Test
        620: 'Portal2.json',                # Portal 2
        252490: 'ItemsSchema_252490.json',  # Rust
    }

    def __init__(self, schema_base_path: str):
        """
        Initialize the item schema manager.

        Args:
            schema_base_path: Base path to the item schema files directory
        """
        self.schema_base_path = schema_base_path
        self.schemas: Dict[int, Dict[str, Any]] = {}  # app_id -> schema data
        self.items_by_defindex: Dict[int, Dict[int, Dict]] = {}  # app_id -> {defindex -> item}
        self.qualities: Dict[int, Dict[str, int]] = {}  # app_id -> {name -> value}
        self.origins: Dict[int, Dict[int, str]] = {}  # app_id -> {origin_id -> name}

    def load_schema(self, app_id: int) -> bool:
        """
        Load the item schema for a specific app.

        Args:
            app_id: The application ID to load the schema for

        Returns:
            True if schema loaded successfully, False otherwise
        """
        if app_id in self.schemas:
            return True  # Already loaded

        schema_file = self.APP_ID_TO_SCHEMA.get(app_id)
        if not schema_file:
            log.warning(f"No schema file mapping for app_id {app_id}")
            return False

        schema_path = os.path.join(self.schema_base_path, schema_file)

        if not os.path.exists(schema_path):
            log.error(f"Schema file not found: {schema_path}")
            return False

        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract the result section
            result = data.get('result', data)

            self.schemas[app_id] = result

            # Index items by defindex for fast lookup
            self.items_by_defindex[app_id] = {}
            items = result.get('items', [])
            for item in items:
                defindex = item.get('defindex')
                if defindex is not None:
                    self.items_by_defindex[app_id][defindex] = item

            # Index qualities
            self.qualities[app_id] = result.get('qualities', {})

            # Index origins
            self.origins[app_id] = {}
            for origin_entry in result.get('originNames', []):
                origin_id = origin_entry.get('origin')
                origin_name = origin_entry.get('name')
                if origin_id is not None and origin_name:
                    self.origins[app_id][origin_id] = origin_name

            log.info(f"Loaded item schema for app {app_id}: {len(items)} items")
            return True

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse schema JSON for app {app_id}: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to load schema for app {app_id}: {e}")
            return False

    def get_item_definition(self, app_id: int, defindex: int) -> Optional[Dict]:
        """
        Get an item definition by its definition index.

        Args:
            app_id: The application ID
            defindex: The item definition index

        Returns:
            Item definition dict or None if not found
        """
        # Ensure schema is loaded
        if app_id not in self.schemas:
            self.load_schema(app_id)

        return self.items_by_defindex.get(app_id, {}).get(defindex)

    def is_valid_defindex(self, app_id: int, defindex: int) -> bool:
        """
        Check if a definition index is valid for the given app.

        Args:
            app_id: The application ID
            defindex: The item definition index

        Returns:
            True if the defindex exists in the schema
        """
        return self.get_item_definition(app_id, defindex) is not None

    def get_all_defindices(self, app_id: int) -> List[int]:
        """
        Get all valid definition indices for an app.

        Args:
            app_id: The application ID

        Returns:
            List of all defindices in the schema
        """
        if app_id not in self.schemas:
            self.load_schema(app_id)

        return list(self.items_by_defindex.get(app_id, {}).keys())

    def get_quality_value(self, app_id: int, quality_name: str) -> int:
        """
        Get the numeric value for a quality name.

        Args:
            app_id: The application ID
            quality_name: The quality name (e.g., 'unique', 'strange')

        Returns:
            Quality value or 0 if not found
        """
        if app_id not in self.schemas:
            self.load_schema(app_id)

        return self.qualities.get(app_id, {}).get(quality_name.lower(), 0)

    def get_origin_name(self, app_id: int, origin_id: int) -> str:
        """
        Get the name for an origin ID.

        Args:
            app_id: The application ID
            origin_id: The origin ID

        Returns:
            Origin name or 'Unknown' if not found
        """
        if app_id not in self.schemas:
            self.load_schema(app_id)

        return self.origins.get(app_id, {}).get(origin_id, 'Unknown')

    def get_item_name(self, app_id: int, defindex: int) -> str:
        """
        Get the name of an item by its definition index.

        Args:
            app_id: The application ID
            defindex: The item definition index

        Returns:
            Item name or 'Unknown Item' if not found
        """
        item = self.get_item_definition(app_id, defindex)
        if item:
            return item.get('item_name', item.get('name', 'Unknown Item'))
        return 'Unknown Item'

    def get_item_type(self, app_id: int, defindex: int) -> str:
        """
        Get the type of an item by its definition index.

        Args:
            app_id: The application ID
            defindex: The item definition index

        Returns:
            Item type name or 'Unknown' if not found
        """
        item = self.get_item_definition(app_id, defindex)
        if item:
            return item.get('item_type_name', item.get('type', 'Unknown'))
        return 'Unknown'


# Global instance
_manager = None


def get_item_schema_manager() -> ItemSchemaManager:
    """Get the global item schema manager instance."""
    global _manager
    if _manager is None:
        import globalvars
        schema_path = os.path.join(
            globalvars.config.get('web_root', 'files'),
            'item_schemas', 'GC_Schemas', 'ItemSchema'
        )
        _manager = ItemSchemaManager(schema_path)
    return _manager
