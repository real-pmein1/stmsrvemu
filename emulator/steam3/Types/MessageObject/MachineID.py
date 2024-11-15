from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KeyValueClass


class MachineID:
    """BB3: machine guid
       FF2: MAC
       3B3: DiskID
       333: Custom Data
       BBB: Bios Serial
    """
    def __init__(self, data):
        self.message_object = MessageObject(data)
        self.message_object.parse()
        self.BB3 = self.message_object.get('BB3')
        self.FF2 = self.message_object.get('FF2')
        self._3B3 = self.message_object.get('3B3')

    def __str__(self):
        return f"BB3: {self.BB3}, FF2: {self.FF2}, 3B3: {self._3B3}"
# example for parsing
# Assume 'data' is your byte string containing multiple MessageObjects
#machine_id = MachineID(data)
#print(machine_id.BB3, machine_id.FF2, machine_id._3B3)