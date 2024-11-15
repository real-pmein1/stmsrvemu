from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING


class ClanAnnoucement_Info(MessageObject):
    """CClanAnnouncementInfo::SetBody(char const*)	.text	00290366	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanAnnouncementInfo::SetClanID(ulong long)	.text	0028FA3C	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CClanAnnouncementInfo::SetGID(ulong long)	.text	0028FA86	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CClanAnnouncementInfo::SetHeadline(char const*)	.text	0029039E	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanAnnouncementInfo::SetPostTime(uint)	.text	0028E4F4	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CClanAnnouncementInfo::SetPosterID(ulong long)	.text	0028F9F2	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CClanAnnouncementInfo::SetUpdateTime(uint)	.text	0028E4BC	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	."""

    def __init__(self, gid, clanid, posttime, posterid, headline, updatetime, body):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for the License using provided parameters
        self.setValue('GID', gid, KVS_TYPE_INT64)
        self.setValue('ClanID', clanid, KVS_TYPE_INT64)
        self.setValue('PostTime', posttime, KVS_TYPE_INT)  # 4 byte int
        self.setValue('PosterID', posterid, KVS_TYPE_INT64)
        self.setValue('Headline', headline, KVS_TYPE_STRING)
        self.setValue('UpdateTime', updatetime, KVS_TYPE_INT)  # 4 byte int
        self.setValue('Body', body, KVS_TYPE_STRING)


    def __repr__(self):
        # Display all data stored in this License for debugging
        return f"<ClanAnnouncement_Info {self.data}>"