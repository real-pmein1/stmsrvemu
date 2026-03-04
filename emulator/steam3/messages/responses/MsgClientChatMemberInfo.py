import struct
from enum import IntEnum
from typing import Optional, Tuple
from steam3.Types.chat_types import ChatInfoType, ChatMemberStateChange

from steam3.Types.emsg import EMsg  # Assumes EMsg.ClientChatMemberInfo is defined
from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo  # Must implement to_bytes() and from_bytes()


class MsgClientChatMemberInfo:

    __slots__ = (
        "chatGlobalId",
        "type",
        # stateChange fields
        "stateChange_memberGlobalId",
        "stateChange_change",
        "stateChange_actorGlobalId",
        # infoUpdate / stateChange-entered payload
        "memberInfo",
        # memberLimitChange fields
        "memberLimitChange_memberGlobalId",
        "memberLimitChange_memberLimit",
    )

    def __init__(self):
        # Defaults (match C++ constructor)
        self.chatGlobalId: int = 0
        self.type: ChatInfoType = ChatInfoType.stateChange

        # For ChatInfoType.stateChange
        self.stateChange_memberGlobalId: int = 0
        self.stateChange_change: ChatMemberStateChange = ChatMemberStateChange.entered
        self.stateChange_actorGlobalId: int = 0

        # Only present if change == entered or type == infoUpdate
        self.memberInfo: Optional[ChatMemberInfo] = None

        # For ChatInfoType.memberLimitChange
        self.memberLimitChange_memberGlobalId: int = 0
        self.memberLimitChange_memberLimit: int = 0

    def pack(self) -> bytes:
        """
        Serialize this message into bytes via struct.pack. No header is included here?
        only the body fields in the exact order the C++ code writes them.
        """
        # Pack chatGlobalId (uint64) and type (int32)
        buf = struct.pack("<Qi", self.chatGlobalId, int(self.type))

        if self.type == ChatInfoType.stateChange:
            # Pack stateChange.memberGlobalId (uint64), change (int32), actorGlobalId (uint64)
            buf += struct.pack(
                "<QiQ",
                self.stateChange_memberGlobalId,
                int(self.stateChange_change),
                self.stateChange_actorGlobalId,
            )
            # If ?entered?, we must have a ChatMemberInfo to serialize next
            if self.stateChange_change == ChatMemberStateChange.entered:
                if self.memberInfo is None:
                    raise ValueError("memberInfo is required when stateChange == entered")
                buf += self.memberInfo.serialize()

        elif self.type == ChatInfoType.infoUpdate:
            # For infoUpdate, we serialize a ChatMemberInfo next
            if self.memberInfo is None:
                raise ValueError("memberInfo is required when type == infoUpdate")
            buf += self.memberInfo.serialize()

        elif self.type == ChatInfoType.memberLimitChange:
            # Pack memberLimitChange.memberGlobalId (uint64), memberLimit (int32)
            buf += struct.pack(
                "<Qi",
                self.memberLimitChange_memberGlobalId,
                self.memberLimitChange_memberLimit,
            )

        else:
            raise ValueError(f"Unknown ChatInfoType: {self.type}")

        return buf

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> Tuple["MsgClientChatMemberInfo", int]:
        """
        Deserialize from `data[offset:]`, returning (instance, new_offset).
        Raises if the buffer is too short or fields are invalid.
        """
        inst = cls()
        # Minimum: 8 bytes (chatGlobalId) + 4 bytes (type) = 12 bytes
        if len(data) - offset < 12:
            raise ValueError("Buffer too short to contain MsgClientChatMemberInfo header")

        # Unpack chatGlobalId (uint64) and type (int32)
        inst.chatGlobalId, raw_type = struct.unpack_from("<Qi", data, offset)
        try:
            inst.type = ChatInfoType(raw_type)
        except ValueError:
            raise ValueError(f"Invalid ChatInfoType value: {raw_type}")
        offset += struct.calcsize("<Qi")  # = 12

        if inst.type == ChatInfoType.stateChange:
            # Next: uint64 + int32 + uint64 = 8 + 4 + 8 = 20 bytes
            if len(data) - offset < 20:
                raise ValueError("Buffer too short for stateChange fields")
            (inst.stateChange_memberGlobalId,
             raw_change,
             inst.stateChange_actorGlobalId) = struct.unpack_from("<QiQ", data, offset)
            try:
                inst.stateChange_change = ChatMemberStateChange(raw_change)
            except ValueError:
                raise ValueError(f"Invalid ChatMemberStateChange: {raw_change}")
            offset += struct.calcsize("<QiQ")  # = 20

            # If ?entered?, the next bytes encode a ChatMemberInfo
            if inst.stateChange_change == ChatMemberStateChange.entered:
                # Delegate to ChatMemberInfo.from_bytes(); it returns (obj, new_offset)
                inst.memberInfo, offset = ChatMemberInfo(False, data)

        elif inst.type == ChatInfoType.infoUpdate:
            # Entire ChatMemberInfo follows
            inst.memberInfo, offset = ChatMemberInfo(False, data)

        elif inst.type == ChatInfoType.memberLimitChange:
            # Next: uint64 + int32 = 8 + 4 = 12 bytes
            if len(data) - offset < 12:
                raise ValueError("Buffer too short for memberLimitChange fields")
            (inst.memberLimitChange_memberGlobalId,
             inst.memberLimitChange_memberLimit) = struct.unpack_from("<Qi", data, offset)
            offset += struct.calcsize("<Qi")  # = 12

        else:
            raise ValueError(f"Unknown ChatInfoType: {inst.type}")

        return inst, offset

    def to_clientmsg(self) -> bytes:
        """
        Prepend the 4-byte EMsg ID (little-endian uint32) to the packed body.
        This yields a full ?response-type? message buffer you can send directly.
        """
        # EMsg.ClientChatMemberInfo is presumed to be an int;
        # pack it as a little-endian uint32, then append the body bytes.
        header = struct.pack("<I", EMsg.ClientChatMemberInfo)
        body = self.pack()
        return header + body

    def __str__(self) -> str:
        lines = [f"<MsgClientChatMemberInfo chatGlobalId={self.chatGlobalId} type={self.type.name}>"]
        if self.type == ChatInfoType.stateChange:
            lines.append(
                f"  [StateChange] memberGlobalId={self.stateChange_memberGlobalId} "
                f"change={self.stateChange_change.name} actorGlobalId={self.stateChange_actorGlobalId}"
            )
            if self.stateChange_change == ChatMemberStateChange.entered:
                lines.append(f"    memberInfo={self.memberInfo}")
        elif self.type == ChatInfoType.infoUpdate:
            lines.append(f"  [InfoUpdate] memberInfo={self.memberInfo}")
        elif self.type == ChatInfoType.memberLimitChange:
            lines.append(
                f"  [MemberLimitChange] memberGlobalId={self.memberLimitChange_memberGlobalId} "
                f"memberLimit={self.memberLimitChange_memberLimit}"
            )
        lines.append("</MsgClientChatMemberInfo>")
        return "\n".join(lines)
