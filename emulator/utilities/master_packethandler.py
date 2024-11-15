class PacketHandler:
    def __init__(self, packet_data):
        self.packet_data = packet_data
        self.packet_length = len(packet_data)
        self.msg_readcount = 0

    def read_string(self):
        start = self.msg_readcount
        while self.msg_readcount < self.packet_length and self.packet_data[self.msg_readcount] not in (b'\r', b'\n', b'\0'):
            self.msg_readcount += 1

        # Extract the string
        result = self.packet_data[start:self.msg_readcount]

        # Advance readcount past the string terminator if within bounds
        if self.msg_readcount < self.packet_length:
            self.msg_readcount += 1

        # Skip any additional newline characters
        while self.msg_readcount < self.packet_length and self.packet_data[self.msg_readcount] in (b'\r', b'\n'):
            self.msg_readcount += 1

        return result.decode('iso-8859-1')  # or the appropriate encoding

    def read_byte(self):
        if self.msg_readcount >= self.packet_length:
            print("Overflow reading byte")
            return -1

        value = self.packet_data[self.msg_readcount]
        self.msg_readcount += 1
        return value

    def read_short(self):
        if self.msg_readcount + 2 > self.packet_length:
            print("Overflow reading short")
            return -1

        value = int.from_bytes(self.packet_data[self.msg_readcount:self.msg_readcount + 2], 'little')
        self.msg_readcount += 2
        return value

    def read_long(self):
        if self.msg_readcount + 4 > self.packet_length:
            print("Overflow reading int")
            return -1

        value = int.from_bytes(self.packet_data[self.msg_readcount:self.msg_readcount + 4], 'little')
        self.msg_readcount += 4
        return value

    def info_value_for_key(info, key): # THIS CANNOT HAVE SELF *BUT* AT LEAST 2003 SOMETIMES DOESNT COMPLETE WHEN NO SERVERS RUNNING
        pairs = info.split('\\')
        key_index = pairs.index(key) if key in pairs else -1
        if key_index != -1 and key_index + 1 < len(pairs):
            return pairs[key_index + 1]
        return 0