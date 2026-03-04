import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientGetGiftTargetListResponse:
    """Represents a gift target list entry for ClientGetGiftTargetListResponse.

    Attributes:
        client_obj: The :class:`steam3.ClientManager.client.Client` receiving the response.
        package_id (int): The package ID queried by the client.
        steamid_friend (int): SteamID of the friend.
        potential_gift_target (int): Index of this friend in the response list.
        total_potential_targets (int): Total friends included in the response.
        valid_gift_target (int): 1 if the friend can receive the gift, otherwise 0.
    """

    def __init__(self, client_obj, package_id: int = 0, steamid_friend: int = 0,
                 potential_gift_target: int = 0, total_potential_targets: int = 0,
                 valid_gift_target: int = 0) -> None:
        self.client_obj = client_obj
        self.package_id = package_id
        self.steamid_friend = steamid_friend
        self.potential_gift_target = potential_gift_target
        self.total_potential_targets = total_potential_targets
        self.valid_gift_target = valid_gift_target

    def to_clientmsg(self) -> CMResponse:
        """Serialize the response into a :class:`CMResponse` packet."""
        packet = CMResponse(eMsgID=EMsg.ClientGetGiftTargetListResponse,
                            client_obj=self.client_obj)
        packet.data = struct.pack(
            '<IQiiB',
            self.package_id,
            self.steamid_friend,
            self.potential_gift_target,
            self.total_potential_targets,
            self.valid_gift_target,
        )
        packet.length = len(packet.data)
        return packet
