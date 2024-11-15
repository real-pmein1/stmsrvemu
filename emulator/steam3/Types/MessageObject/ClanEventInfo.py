from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING, KVS_TYPE_UINT64


class ClanEvent_Info(MessageObject):
    """CClanEventInfo::SetAppID(int)	.text	0028E5DC	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetClanID(ulong long)	.text	0028FAD0	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetEventName(char const*)	.text	00290446	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetEventNotes(char const*)	.text	002903D6	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetEventTime(uint)	.text	0028E52C	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetEventType(EClanEventType)	.text	0028E614	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetGID(ulong long)	.text	0028FB1A	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetServerIP(uint)	.text	0028E5A4	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetServerPassword(char const*)	.text	0029040E	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanEventInfo::SetServerPort(ushort)	.text	0028E564	0000003F	0000001C	00000008	R	.	.	.	.	S	B	T	."""
    def __init__(self, gid, clanid, appid, eventtime, eventname, eventtype, eventnotes, serverip, serverport, serverpassword):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for the License using provided parameters
        self.setValue('GID', gid, KVS_TYPE_UINT64)  # 8 byte int
        self.setValue('ClanID', clanid, KVS_TYPE_UINT64)  # 8 byte int
        self.setValue('AppID', appid, KVS_TYPE_INT)  # 4 byte int
        self.setValue('EventTime', eventtime, KVS_TYPE_INT)  # 4 byte int
        self.setValue('EventName', eventname, KVS_TYPE_STRING)  # string
        self.setValue('EventType', eventtype, KVS_TYPE_INT)  # 4 byte int
        self.setValue('EventNotes', eventnotes, KVS_TYPE_STRING)  # string
        self.setValue('ServerIP', serverip, KVS_TYPE_INT)  # 4 byte int
        self.setValue('ServerPort', serverport, KVS_TYPE_INT)  # 4 byte int
        self.setValue('ServerPassword', serverpassword, KVS_TYPE_STRING)  # string



    def __repr__(self):
        # Display all data stored in this License for debugging
        return f"<ClanEvent_Info {self.data}>"