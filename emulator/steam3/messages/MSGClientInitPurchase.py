import struct
from io import BytesIO
from steam3.Types.keyvaluesystem import KeyValuesSystem
from steam3.Types.steam_types import EPaymentMethod


class MSGClientInitPurchase:
    """
    Handles MsgClientInitPurchase_t packet structure.
    
    struct MsgClientInitPurchase_t
    {
        uint32 m_cPackages;
        EPaymentMethod m_ePaymentMethod;
        GID_t m_gidPaymentID;
        bool m_bStorePaymentInfo;
        uint32 m_unPackageID;
        // followed by MessageObject data
    };
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        self.package_count = 1
        self.payment_method = EPaymentMethod.CreditCard
        self.payment_id = 0
        self.store_payment_info = False
        self.package_id = 0
        self.message_object_data = b""
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the InitPurchase packet data"""
        try:
            # Parse fixed header: package_count(4) + payment_method(4) + payment_id(8) + store_payment_info(1) + package_id(4)
            header_size = 21
            if len(data) < header_size:
                raise ValueError(f"Data too short for InitPurchase header: {len(data)} < {header_size}")
            
            self.package_count, payment_method_int, self.payment_id, store_payment_info, self.package_id = struct.unpack_from(
                "<IIQBI", data, 0
            )
            
            self.payment_method = EPaymentMethod(payment_method_int)
            self.store_payment_info = bool(store_payment_info)
            
            # Remaining data is MessageObject data
            if len(data) > header_size:
                self.message_object_data = data[header_size:]
            
        except (struct.error, ValueError) as e:
            raise ValueError(f"Failed to parse InitPurchase packet: {e}")
    
    def get_message_objects(self):
        """Parse and return MessageObject data as key-value structures"""
        if not self.message_object_data:
            return []

        try:
            stream = BytesIO(self.message_object_data)
            kv_system = KeyValuesSystem()
            kv_system.deserialize(stream)

            # Return parsed message objects
            message_objects = []
            if kv_system.root and kv_system.root.get_elements():
                for child in kv_system.root.get_elements():
                    if child.name == "MessageObject":
                        obj_dict = {}
                        self._extract_children(child, obj_dict)
                        message_objects.append(obj_dict)

            return message_objects

        except Exception as e:
            # If parsing fails, return empty list
            return []

    def _extract_children(self, node, result_dict):
        """
        Recursively extract all children from a node into a flat dictionary.
        Handles both leaf values and nested subkeys.
        """
        if not hasattr(node, 'get_elements'):
            return

        elements = node.get_elements()
        if not elements:
            return

        for child in elements:
            if hasattr(child, 'is_key') and child.is_key():
                # This is a subkey (like 'addressinfo') - add it to dict and also extract its children
                result_dict[child.name] = child.name  # Mark that this subkey exists
                self._extract_children(child, result_dict)
            elif hasattr(child, 'value'):
                # This is a leaf value
                result_dict[child.name] = child.value
    
    def __str__(self):
        return (f"MSGClientInitPurchase(packages={self.package_count}, "
                f"payment_method={self.payment_method}, "
                f"payment_id={self.payment_id}, "
                f"store_payment_info={self.store_payment_info}, "
                f"package_id={self.package_id})")
    
    def __repr__(self):
        return self.__str__()