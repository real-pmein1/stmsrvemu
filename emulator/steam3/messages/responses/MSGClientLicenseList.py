import struct
from io import BytesIO

from steam3.Types.steam_types import EResult
from steam3.Types.MessageObject.License import Deprecated_License
from steam3.cm_packet_utils import CMResponse, CMProtoResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientLicenseList


class MSGClientLicenseList:
    """
    Response message for ClientLicenseList (EMsg 780).
    
    This message sends a list of licenses (packages) that the client owns.
    Used by the client to know which games/content they have access to.
    
    Fields:
        eresult (int): Result code (EResult)
        license_count (int): Number of licenses in the list
        licenses (list): List of License MessageObjects
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        self.eresult = EResult.OK
        self.license_count = 0
        self.licenses = []
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Deserialize incoming license list data from client (not typically used)."""
        if len(data) < 8:
            return
            
        self.eresult, self.license_count = struct.unpack_from('<II', data, 0)
        
        # Note: Client typically doesn't send license data to server,
        # this is mainly server -> client direction
    
    def add_license(self, license_obj: Deprecated_License):
        """Add a license to the list."""
        self.licenses.append(license_obj)
        self.license_count = len(self.licenses)

    def add_license_from_db_record(self, db_record):
        """Add a license from a Steam3LicenseRecord database record."""
        license_obj = Deprecated_License.from_database_record(db_record)
        self.add_license(license_obj)

    def add_license_from_subscription_record(self, sub_record):
        """Add a license from an AccountSubscriptionsRecord database record."""
        license_obj = Deprecated_License.from_subscription_record(sub_record)
        self.add_license(license_obj)
    
    def to_clientmsg(self):
        """Serialize to legacy ClientMsg format."""
        packet = CMResponse(eMsgID=EMsg.ClientLicenseList, client_obj=self.client_obj)
        
        buffer = BytesIO()
        
        # Write header
        buffer.write(struct.pack('<II', self.eresult, self.license_count))
        
        # Write each license
        for license_obj in self.licenses:
            license_data = license_obj.serialize()
            buffer.write(license_data)
        
        packet.data = buffer.getvalue()
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Serialize to protobuf format."""
        packet = CMProtoResponse(eMsgID=EMsg.ClientLicenseList, client_obj=self.client_obj)
        license_list_msg = CMsgClientLicenseList()

        license_list_msg.eresult = self.eresult

        for license_obj in self.licenses:
            license_proto = license_list_msg.licenses.add()

            # Map MessageObject fields to protobuf fields
            license_proto.package_id = license_obj.getValue('PackageID', 0)
            license_proto.time_created = license_obj.getValue('TimeCreated', 0)
            license_proto.time_next_process = license_obj.getValue('TimeNextProcess', 0)
            license_proto.minute_limit = license_obj.getValue('MinuteLimit', 0)
            license_proto.minutes_used = license_obj.getValue('MinutesUsed', 0)
            license_proto.payment_method = license_obj.getValue('PaymentMethod', 0)
            license_proto.flags = license_obj.getValue('flags', 0)

            purchase_country = license_obj.getValue('PurchaseCountryCode', 'US')
            if isinstance(purchase_country, str):
                license_proto.purchase_country_code = purchase_country
            else:
                license_proto.purchase_country_code = 'US'

            license_proto.license_type = license_obj.getValue('LicenseType', 0)
            license_proto.territory_code = license_obj.getValue('TerritoryCode', 0)
            license_proto.change_number = license_obj.getValue('ChangeNumber', 0)
            license_proto.owner_id = license_obj.getValue('OwnerID', 0)
            license_proto.initial_period = license_obj.getValue('InitialPeriod', 0)
            license_proto.initial_time_unit = license_obj.getValue('InitialTimeUnit', 0)
            license_proto.renewal_period = license_obj.getValue('RenewalPeriod', 0)
            license_proto.renewal_time_unit = license_obj.getValue('RenewalTimeUnit', 0)
            license_proto.access_token = license_obj.getValue('AccessToken', 0)
            license_proto.master_package_id = license_obj.getValue('MasterPackageID', 0)

        packet.data = license_list_msg.SerializeToString()
        packet.length = len(packet.data)

        return packet
    
    def __repr__(self):
        return f"<MSGClientLicenseList eresult={self.eresult} license_count={self.license_count}>"