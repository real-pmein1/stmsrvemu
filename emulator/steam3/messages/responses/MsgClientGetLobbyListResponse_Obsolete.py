# get_lobby_list_response.py

import struct
import globalvars

from steam3.cm_packet_utils import CMProtoResponse, CMResponse

# from steam3.protobufs.steammessages_clientserver_lobby_pb2 import CMsgClientGetLobbyListResponse
import io
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.keyvaluesystem import KeyValuesSystem


class GetLobbyListResponse_obsolete:
    """
    MsgClientGetLobbyListResponse, with per-lobby metadata via KeyValuesSystem.

    Based on 2008 client analysis (UpdateLobbyMetadataFromLobbyListMsg), format is:
      - game_id (8 bytes) - CRITICAL: must be included for client parsing
      - lobby_count (4 bytes)
      - lobby steamIDs (8 bytes each)
      - metadata_remaining_bytes (4 bytes)
      - For each lobby: steamID (8), members (4), max_members (4), metadata_len (4), KeyValues blob

    Fields:
      - game_id: int - The game/app ID for this lobby search
      - lobby_ids: List[int]
      - metadata: Dict[int, {'members': int, 'max_members': int, 'kv': Optional[KeyValuesSystem]}]
      - client_obj:  opaque back-pointer for CMResponse
    """
    def __init__(self, client_obj):
        self.game_id = 0  # Added: game_id is required by client
        self.lobby_ids = []
        self.metadata = {}
        self.client_obj = client_obj

    @classmethod
    def deserialize(cls, client_obj, raw_data: bytes):
        inst = cls(client_obj)
        stream = io.BytesIO(raw_data)

        # 1) Read lobby count
        header = stream.read(4)
        if len(header) < 4:
            raise ValueError("Incomplete GetLobbyListResponse_obsolete header")
        (count,) = struct.unpack('<I', header)

        # 2) Read each lobby ID
        for _ in range(count):
            chunk = stream.read(8)
            if len(chunk) < 8:
                raise ValueError("Incomplete lobby ID")
            (lobby_id,) = struct.unpack('<Q', chunk)
            inst.lobby_ids.append(lobby_id)

        # 3) Parse optional metadata block
        #    First 4 bytes = total metadata bytes to follow
        remaining = len(raw_data) - stream.tell()
        if remaining >= 4:
            (cub_metadata_remaining,) = struct.unpack('<i', stream.read(4))
            remaining -= 4

            while cub_metadata_remaining > 0:
                # a) lobby ID
                lid_data = stream.read(8)
                (lobby_id,) = struct.unpack('<Q', lid_data)
                cub_metadata_remaining -= 8

                # b) current members
                m_data = stream.read(4)
                (c_members,) = struct.unpack('<i', m_data)
                cub_metadata_remaining -= 4

                # c) max members
                mm_data = stream.read(4)
                (c_members_max,) = struct.unpack('<i', mm_data)
                cub_metadata_remaining -= 4

                # d) length of this lobby's metadata blob
                len_data = stream.read(4)
                (cub_lobby_meta,) = struct.unpack('<i', len_data)
                cub_metadata_remaining -= 4

                kv_obj = None
                # e) read & deserialize the binary KeyValues blob
                if cub_lobby_meta > 0:
                    blob = stream.read(cub_lobby_meta)
                    if len(blob) < cub_lobby_meta:
                        raise ValueError(f"Incomplete metadata blob for lobby {lobby_id}")
                    cub_metadata_remaining -= cub_lobby_meta

                    buf = io.BytesIO(blob)
                    kvs = KeyValuesSystem()
                    kvs.deserialize(buf)
                    kv_obj = kvs

                inst.metadata[lobby_id] = {
                    'members': c_members,
                    'max_members': c_members_max,
                    'kv': kv_obj
                }

            # (optional) sanity check:
            if cub_metadata_remaining != 0:
                # you could log or raise here
                pass

        return inst

    def to_clientmsg(self):
        packet = CMResponse(
            eMsgID=EMsg.ClientGetLobbyListResponse,
            client_obj=self.client_obj
        )

        # 1) game_id (8 bytes) + lobby count (4 bytes) - required for 2008 client
        data = struct.pack('<QI', self.game_id, len(self.lobby_ids))
        for lid in self.lobby_ids:
            data += struct.pack('<Q', lid)

        # 2) serialize metadata block (always include size field, even if 0)
        meta_bytes = b''
        if self.metadata:
            for lid in self.lobby_ids:
                info = self.metadata.get(lid)
                if not info:
                    continue

                # a) lobby ID
                meta_bytes += struct.pack('<Q', lid)
                # b) members & max
                meta_bytes += struct.pack('<i', info['members'])
                meta_bytes += struct.pack('<i', info['max_members'])

                # c) serialize KV blob
                buf = io.BytesIO()
                if info['kv']:
                    info['kv'].serialize(buf)
                blob = buf.getvalue()
                meta_bytes += struct.pack('<i', len(blob))
                meta_bytes += blob

        # Always write metadata size field (even if 0) for client compatibility
        data += struct.pack('<i', len(meta_bytes))
        data += meta_bytes

        packet.data = data
        packet.length = len(data)
        return packet

    def __str__(self):
        lines = [f"GetLobbyListResponse_obsolete: {len(self.lobby_ids)} lobbies"]
        for lid in self.lobby_ids:
            meta = self.metadata.get(lid)
            if meta:
                lines.append(
                    f"  Lobby {lid}: {meta['members']}/{meta['max_members']} members, "
                    f"KV keys = {meta['kv'].root.get_elements()}"
                )
            else:
                lines.append(f"  Lobby {lid}: no metadata")
        return "\n".join(lines)


class MMSGetLobbyListResponse:
    """
    Mirrors the C++ MsgClientGetLobbyListResponse, with:
      - to_protobuf(): for Steam ?protobuf? transport
      - to_clientmsg(): for raw ClientMsg transport
    """

    def __init__(self, client_obj):
        self.gameId = 0                     # ULONGLONG
        self.lobbies = []                   # List[ULONGLONG]
        self.metadata = {}                  # Dict[ULONGLONG, Lobby]
        self.client_obj = client_obj

    def to_protobuf(self):
        """
        Build a CMProtoResponse carrying a CMsgClientGetLobbyListResponse.
        """
        pass
        """packet = CMProtoResponse(
            eMsgID=EMsg.ClientGetLobbyListResponse,
            client_obj=self.client_obj
        )
        msg = CMsgClientGetLobbyListResponse()
        msg.game_id = self.gameId
        msg.lobbies.extend(self.lobbies)

        for lid, lob in self.metadata.items():
            entry = msg.metadata.add()
            entry.lobby_global_id = lob.lobbyGlobalId
            entry.members_count    = lob.membersCount
            entry.members_max      = lob.membersMax
            if lob.metadata:
                # ChatRoomMetadata.populate_protobuf fills in the nested fields
                lob.metadata.populate_protobuf(entry.metadata)

        packet.set_response_message(msg)
        serialized = msg.SerializeToString()
        packet.data   = serialized
        packet.length = len(serialized)
        return packet"""

    def to_clientmsg(self):
        """
        Build a CMResponse carrying the raw ClientMsg format:
          [ gameId (Q) ][ lobbyCount (I) ][ each lobbyId (Q)... ]
          [ metadataBlockLength (I) ][ per-entry: Q, I, I, [ChatRoomMetadata bytes]... ]
        """
        packet = CMResponse(
            eMsgID=EMsg.ClientGetLobbyListResponse,
            client_obj=self.client_obj
        )

        # 1) gameId
        data = struct.pack('<Q', self.gameId)

        # 2) lobbies array
        data += struct.pack('<I', len(self.lobbies))
        for lid in self.lobbies:
            data += struct.pack('<Q', lid)

        # 3) metadata block
        meta_buf = b''
        for lid, lob in self.metadata.items():
            # lobbyGlobalId, membersCount, membersMax
            meta_buf += struct.pack('<QII',
                lob.lobbyGlobalId,
                lob.membersCount,
                lob.membersMax
            )
            if lob.metadata:
                # ChatRoomMetadata.to_bytes() should return its binary form
                meta_buf += lob.metadata.to_bytes()

        # 4) prefix and append
        data += struct.pack('<I', len(meta_buf))
        data += meta_buf

        packet.data   = data
        packet.length = len(data)
        return packet
