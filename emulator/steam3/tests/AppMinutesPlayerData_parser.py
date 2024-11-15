import struct
from io import BytesIO


class MinutesPlayed:
    def __init__(self, minutes_played_total=0, minutes_played_last_2_weeks=0):
        """
        Initialize the MinutesPlayed object with total and last 2 weeks minutes.
        :param minutes_played_total: Total minutes played (int)
        :param minutes_played_last_2_weeks: Minutes played in the last 2 weeks (int)
        """
        self.minutes_played_total = minutes_played_total
        self.minutes_played_last_2_weeks = minutes_played_last_2_weeks

    def __repr__(self):
        return f"MinutesPlayed(total={self.minutes_played_total}, last_2_weeks={self.minutes_played_last_2_weeks})"


class MsgClientAppMinutesPlayedData:
    def __init__(self):
        """
        Initialize the MsgClientAppMinutesPlayedData with a dictionary to hold appId and MinutesPlayed pairs.
        """
        self.apps_minutes_played = {}

    def serialize(self):
        """
        Serializes the MsgClientAppMinutesPlayedData object into a byte buffer.
        :return: byte buffer containing the serialized data
        """
        stream = BytesIO()

        # Write the count of apps (number of appId-MinutesPlayed pairs) (4 bytes, int32)
        count = len(self.apps_minutes_played)
        stream.write(struct.pack('<I', count))

        # Write each appId and corresponding MinutesPlayed data
        for app_id, minutes_played in self.apps_minutes_played.items():
            # Write appId (4 bytes, int32)
            stream.write(struct.pack('<I', app_id))

            # Write minutesPlayedTotal and minutesPlayedLast2Weeks (4 bytes each, int32)
            stream.write(struct.pack('<II', minutes_played.minutes_played_total, minutes_played.minutes_played_last_2_weeks))

        return stream.getvalue()

    @classmethod
    def deserialize(cls, byte_buffer):
        """
        Deserializes a byte buffer into a MsgClientAppMinutesPlayedData object.
        :param byte_buffer: byte buffer containing the serialized data
        :return: MsgClientAppMinutesPlayedData object
        """
        stream = BytesIO(byte_buffer)

        # Create an instance of the class
        instance = cls()

        # Read the count of apps (4 bytes, int32)
        count = struct.unpack('<I', stream.read(4))[0]

        # Read each appId and corresponding MinutesPlayed data
        for _ in range(count):
            # Read appId (4 bytes, int32)
            app_id = struct.unpack('<I', stream.read(4))[0]

            # Read minutesPlayedTotal and minutesPlayedLast2Weeks (4 bytes each, int32)
            minutes_played_total, minutes_played_last_2_weeks = struct.unpack('<II', stream.read(8))

            # Create a MinutesPlayed object and add it to the dictionary
            instance.apps_minutes_played[app_id] = MinutesPlayed(minutes_played_total, minutes_played_last_2_weeks)

        return instance

    def __repr__(self):
        return f"MsgClientAppMinutesPlayedData({self.apps_minutes_played})"


# Example usage:

# Create a MsgClientAppMinutesPlayedData object and add some test data
"""msg = MsgClientAppMinutesPlayedData()
msg.apps_minutes_played[12345] = MinutesPlayed(minutes_played_total=150, minutes_played_last_2_weeks=30)
msg.apps_minutes_played[67890] = MinutesPlayed(minutes_played_total=300, minutes_played_last_2_weeks=60)

# Serialize the data to a byte buffer
serialized_data = msg.serialize()
print(f"Serialized Data: {serialized_data}")"""
packet = b'\x83\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x16\x00\x00\x00\xb8\x01\x00\x00\x15\x06\x00\x00\x00\x00\x00\x00\xf4\x01\x00\x00\x96\x00\x00\x00\x00\x00\x00\x00\x1c\xa2\x00\x00A\x05\x00\x00\x00\x00\x00\x00\xd0\x11\x00\x00\x82\x00\x00\x00\x00\x00\x00\x00\x14#\x00\x00;\x01\x00\x00\x00\x00\x00\x00d2\x00\x00J\x00\x00\x00\x00\x00\x00\x00>D\x00\x00\x12\x03\x00\x00\x00\x00\x00\x00DH\x00\x00}\x00\x00\x00\x00\x00\x00\x00\xb8V\x00\x00B\x01\x00\x00\x00\x00\x00\x00\xb4_\x00\x00 \x00\x00\x00\x00\x00\x00\x00\x84g\x00\x00(\x00\x00\x00\x00\x00\x00\x00\xb0h\x00\x00,\x00\x00\x00\x00\x00\x00\x00\xfcq\x00\x00v\x00\x00\x00\x00\x00\x00\x00h~\x00\x00{\x01\x00\x00\x00\x00\x00\x00L\x81\x00\x00[\x00\x00\x00\x00\x00\x00\x00\x88\x90\x00\x00\xf9\x00\x00\x00\x00\x00\x00\x00\x90\x01\x00\x00\x89\x01\x00\x00\x89\x01\x00\x00,\x92\x00\x00\xc4\x00\x00\x00\x00\x00\x00\x00(\xa0\x00\x00\xbe\x00\x00\x00\x00\x00\x00\x00\x18\x92\x00\x00\xdd\x00\x00\x00\x00\x00\x00\x00\x92\x0e\x00\x00a\x00\x00\x00\x00\x00\x00\x00,\x97\x00\x00R\x00\x00\x00R\x00\x00\x00'

# Deserialize the byte buffer back into an object
deserialized_msg = MsgClientAppMinutesPlayedData.deserialize(packet[36:])
print(f"Deserialized Object: {deserialized_msg}")