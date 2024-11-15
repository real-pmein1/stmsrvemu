import struct


class MsgClientDRMProblemReport:

    def __init__(self, appId = 0, appCrc = 0, errorCode = 0):
        self.appId = appId
        self.appCrc = appCrc
        self.errorCode = errorCode

    def __repr__(self):
        return (f"MsgClientDRMProblemReport(appId={self.appId}, "
                f"appCrc={self.appCrc}, errorCode={self.errorCode})")

    def __str__(self):
        return (f"DRM Problem Report - App ID: {self.appId}, "
                f"App CRC: {self.appCrc}, Error Code: {self.errorCode}")

    def de_serialize(self, data):
        """Deserialize the body from the packed binary data"""
        self.appId, self.appCrc, self.errorCode = struct.unpack('<III', data)

    def serialize(self):
        """Serialize the body to packed binary data"""
        return struct.pack('<III', self.appId, self.appCrc, self.errorCode)