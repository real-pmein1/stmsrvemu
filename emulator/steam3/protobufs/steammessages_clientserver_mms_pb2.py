# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_clientserver_mms.proto
# Protobuf Python Version: 5.28.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    28,
    2,
    '',
    'steammessages_clientserver_mms.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import steammessages_base_pb2 as steammessages__base__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n$steammessages_clientserver_mms.proto\x1a\x18steammessages_base.proto\"\x98\x01\n\'CMsgClientMMSSetRatelimitPolicyOnClient\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x1a\n\x12\x65nable_rate_limits\x18\x02 \x01(\x08\x12\x1b\n\x13seconds_per_message\x18\x03 \x01(\x05\x12$\n\x1cmilliseconds_per_data_update\x18\x04 \x01(\x05\"\xe8\x01\n\x18\x43MsgClientMMSCreateLobby\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x13\n\x0bmax_members\x18\x02 \x01(\x05\x12\x12\n\nlobby_type\x18\x03 \x01(\x05\x12\x13\n\x0blobby_flags\x18\x04 \x01(\x05\x12\x0f\n\x07\x63\x65ll_id\x18\x05 \x01(\r\x12\x1c\n\x14\x64\x65precated_public_ip\x18\x06 \x01(\r\x12\x10\n\x08metadata\x18\x07 \x01(\x0c\x12\x1a\n\x12persona_name_owner\x18\x08 \x01(\t\x12!\n\tpublic_ip\x18\t \x01(\x0b\x32\x0e.CMsgIPAddress\"^\n CMsgClientMMSCreateLobbyResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x12\n\x07\x65result\x18\x03 \x01(\x05:\x01\x32\"V\n\x16\x43MsgClientMMSJoinLobby\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x14\n\x0cpersona_name\x18\x03 \x01(\t\"\xcf\x02\n\x1e\x43MsgClientMMSJoinLobbyResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12 \n\x18\x63hat_room_enter_response\x18\x03 \x01(\x05\x12\x13\n\x0bmax_members\x18\x04 \x01(\x05\x12\x12\n\nlobby_type\x18\x05 \x01(\x05\x12\x13\n\x0blobby_flags\x18\x06 \x01(\x05\x12\x16\n\x0esteam_id_owner\x18\x07 \x01(\x06\x12\x10\n\x08metadata\x18\x08 \x01(\x0c\x12\x37\n\x07members\x18\t \x03(\x0b\x32&.CMsgClientMMSJoinLobbyResponse.Member\x1a\x42\n\x06Member\x12\x10\n\x08steam_id\x18\x01 \x01(\x06\x12\x14\n\x0cpersona_name\x18\x02 \x01(\t\x12\x10\n\x08metadata\x18\x03 \x01(\x0c\"A\n\x17\x43MsgClientMMSLeaveLobby\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\"]\n\x1f\x43MsgClientMMSLeaveLobbyResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x12\n\x07\x65result\x18\x03 \x01(\x05:\x01\x32\"\xa0\x02\n\x19\x43MsgClientMMSGetLobbyList\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x1d\n\x15num_lobbies_requested\x18\x03 \x01(\x05\x12\x0f\n\x07\x63\x65ll_id\x18\x04 \x01(\r\x12\x1c\n\x14\x64\x65precated_public_ip\x18\x05 \x01(\r\x12\x32\n\x07\x66ilters\x18\x06 \x03(\x0b\x32!.CMsgClientMMSGetLobbyList.Filter\x12!\n\tpublic_ip\x18\x07 \x01(\x0b\x32\x0e.CMsgIPAddress\x1aN\n\x06\x46ilter\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\x12\x13\n\x0b\x63omparision\x18\x03 \x01(\x05\x12\x13\n\x0b\x66ilter_type\x18\x04 \x01(\x05\"\xa5\x02\n!CMsgClientMMSGetLobbyListResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x12\n\x07\x65result\x18\x03 \x01(\x05:\x01\x32\x12\x39\n\x07lobbies\x18\x04 \x03(\x0b\x32(.CMsgClientMMSGetLobbyListResponse.Lobby\x1a\xa0\x01\n\x05Lobby\x12\x10\n\x08steam_id\x18\x01 \x01(\x06\x12\x13\n\x0bmax_members\x18\x02 \x01(\x05\x12\x12\n\nlobby_type\x18\x03 \x01(\x05\x12\x13\n\x0blobby_flags\x18\x04 \x01(\x05\x12\x10\n\x08metadata\x18\x05 \x01(\x0c\x12\x13\n\x0bnum_members\x18\x06 \x01(\x05\x12\x10\n\x08\x64istance\x18\x07 \x01(\x02\x12\x0e\n\x06weight\x18\x08 \x01(\x03\"\xac\x01\n\x19\x43MsgClientMMSSetLobbyData\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x17\n\x0fsteam_id_member\x18\x03 \x01(\x06\x12\x13\n\x0bmax_members\x18\x04 \x01(\x05\x12\x12\n\nlobby_type\x18\x05 \x01(\x05\x12\x13\n\x0blobby_flags\x18\x06 \x01(\x05\x12\x10\n\x08metadata\x18\x07 \x01(\x0c\"_\n!CMsgClientMMSSetLobbyDataResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x12\n\x07\x65result\x18\x03 \x01(\x05:\x01\x32\"C\n\x19\x43MsgClientMMSGetLobbyData\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\"\xed\x02\n\x16\x43MsgClientMMSLobbyData\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x13\n\x0bnum_members\x18\x03 \x01(\x05\x12\x13\n\x0bmax_members\x18\x04 \x01(\x05\x12\x12\n\nlobby_type\x18\x05 \x01(\x05\x12\x13\n\x0blobby_flags\x18\x06 \x01(\x05\x12\x16\n\x0esteam_id_owner\x18\x07 \x01(\x06\x12\x10\n\x08metadata\x18\x08 \x01(\x0c\x12/\n\x07members\x18\t \x03(\x0b\x32\x1e.CMsgClientMMSLobbyData.Member\x12\x14\n\x0clobby_cellid\x18\n \x01(\r\x12#\n\x1bowner_should_accept_changes\x18\x0b \x01(\x08\x1a\x42\n\x06Member\x12\x10\n\x08steam_id\x18\x01 \x01(\x06\x12\x14\n\x0cpersona_name\x18\x02 \x01(\t\x12\x10\n\x08metadata\x18\x03 \x01(\x0c\"w\n\x1d\x43MsgClientMMSSendLobbyChatMsg\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x17\n\x0fsteam_id_target\x18\x03 \x01(\x06\x12\x15\n\rlobby_message\x18\x04 \x01(\x0c\"s\n\x19\x43MsgClientMMSLobbyChatMsg\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x17\n\x0fsteam_id_sender\x18\x03 \x01(\x06\x12\x15\n\rlobby_message\x18\x04 \x01(\x0c\"`\n\x1a\x43MsgClientMMSSetLobbyOwner\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x1a\n\x12steam_id_new_owner\x18\x03 \x01(\x06\"`\n\"CMsgClientMMSSetLobbyOwnerResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x12\n\x07\x65result\x18\x03 \x01(\x05:\x01\x32\"^\n\x1b\x43MsgClientMMSSetLobbyLinked\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x17\n\x0fsteam_id_lobby2\x18\x03 \x01(\x06\"\xcc\x01\n\x1f\x43MsgClientMMSSetLobbyGameServer\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12!\n\x19\x64\x65precated_game_server_ip\x18\x03 \x01(\r\x12\x18\n\x10game_server_port\x18\x04 \x01(\r\x12\x1c\n\x14game_server_steam_id\x18\x05 \x01(\x06\x12&\n\x0egame_server_ip\x18\x06 \x01(\x0b\x32\x0e.CMsgIPAddress\"\xcc\x01\n\x1f\x43MsgClientMMSLobbyGameServerSet\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12!\n\x19\x64\x65precated_game_server_ip\x18\x03 \x01(\r\x12\x18\n\x10game_server_port\x18\x04 \x01(\r\x12\x1c\n\x14game_server_steam_id\x18\x05 \x01(\x06\x12&\n\x0egame_server_ip\x18\x06 \x01(\x0b\x32\x0e.CMsgIPAddress\"s\n\x1c\x43MsgClientMMSUserJoinedLobby\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x15\n\rsteam_id_user\x18\x03 \x01(\x06\x12\x14\n\x0cpersona_name\x18\x04 \x01(\t\"q\n\x1a\x43MsgClientMMSUserLeftLobby\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x15\n\rsteam_id_user\x18\x03 \x01(\x06\x12\x14\n\x0cpersona_name\x18\x04 \x01(\t\"c\n\x1a\x43MsgClientMMSInviteToLobby\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x1d\n\x15steam_id_user_invited\x18\x03 \x01(\x06\"x\n\x1b\x43MsgClientMMSGetLobbyStatus\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12\x18\n\x10\x63laim_membership\x18\x03 \x01(\x08\x12\x17\n\x0f\x63laim_ownership\x18\x04 \x01(\x08\"\x8f\x01\n#CMsgClientMMSGetLobbyStatusResponse\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x16\n\x0esteam_id_lobby\x18\x02 \x01(\x06\x12@\n\x0clobby_status\x18\x03 \x01(\x0e\x32\x10.EMMSLobbyStatus:\x18k_EMMSLobbyStatusInvalid*\x90\x01\n\x0f\x45MMSLobbyStatus\x12\x1c\n\x18k_EMMSLobbyStatusInvalid\x10\x00\x12\x1b\n\x17k_EMMSLobbyStatusExists\x10\x01\x12!\n\x1dk_EMMSLobbyStatusDoesNotExist\x10\x02\x12\x1f\n\x1bk_EMMSLobbyStatusNotAMember\x10\x03\x42\x05H\x01\x90\x01\x00')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_clientserver_mms_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'H\001\220\001\000'
  _globals['_EMMSLOBBYSTATUS']._serialized_start=3982
  _globals['_EMMSLOBBYSTATUS']._serialized_end=4126
  _globals['_CMSGCLIENTMMSSETRATELIMITPOLICYONCLIENT']._serialized_start=67
  _globals['_CMSGCLIENTMMSSETRATELIMITPOLICYONCLIENT']._serialized_end=219
  _globals['_CMSGCLIENTMMSCREATELOBBY']._serialized_start=222
  _globals['_CMSGCLIENTMMSCREATELOBBY']._serialized_end=454
  _globals['_CMSGCLIENTMMSCREATELOBBYRESPONSE']._serialized_start=456
  _globals['_CMSGCLIENTMMSCREATELOBBYRESPONSE']._serialized_end=550
  _globals['_CMSGCLIENTMMSJOINLOBBY']._serialized_start=552
  _globals['_CMSGCLIENTMMSJOINLOBBY']._serialized_end=638
  _globals['_CMSGCLIENTMMSJOINLOBBYRESPONSE']._serialized_start=641
  _globals['_CMSGCLIENTMMSJOINLOBBYRESPONSE']._serialized_end=976
  _globals['_CMSGCLIENTMMSJOINLOBBYRESPONSE_MEMBER']._serialized_start=910
  _globals['_CMSGCLIENTMMSJOINLOBBYRESPONSE_MEMBER']._serialized_end=976
  _globals['_CMSGCLIENTMMSLEAVELOBBY']._serialized_start=978
  _globals['_CMSGCLIENTMMSLEAVELOBBY']._serialized_end=1043
  _globals['_CMSGCLIENTMMSLEAVELOBBYRESPONSE']._serialized_start=1045
  _globals['_CMSGCLIENTMMSLEAVELOBBYRESPONSE']._serialized_end=1138
  _globals['_CMSGCLIENTMMSGETLOBBYLIST']._serialized_start=1141
  _globals['_CMSGCLIENTMMSGETLOBBYLIST']._serialized_end=1429
  _globals['_CMSGCLIENTMMSGETLOBBYLIST_FILTER']._serialized_start=1351
  _globals['_CMSGCLIENTMMSGETLOBBYLIST_FILTER']._serialized_end=1429
  _globals['_CMSGCLIENTMMSGETLOBBYLISTRESPONSE']._serialized_start=1432
  _globals['_CMSGCLIENTMMSGETLOBBYLISTRESPONSE']._serialized_end=1725
  _globals['_CMSGCLIENTMMSGETLOBBYLISTRESPONSE_LOBBY']._serialized_start=1565
  _globals['_CMSGCLIENTMMSGETLOBBYLISTRESPONSE_LOBBY']._serialized_end=1725
  _globals['_CMSGCLIENTMMSSETLOBBYDATA']._serialized_start=1728
  _globals['_CMSGCLIENTMMSSETLOBBYDATA']._serialized_end=1900
  _globals['_CMSGCLIENTMMSSETLOBBYDATARESPONSE']._serialized_start=1902
  _globals['_CMSGCLIENTMMSSETLOBBYDATARESPONSE']._serialized_end=1997
  _globals['_CMSGCLIENTMMSGETLOBBYDATA']._serialized_start=1999
  _globals['_CMSGCLIENTMMSGETLOBBYDATA']._serialized_end=2066
  _globals['_CMSGCLIENTMMSLOBBYDATA']._serialized_start=2069
  _globals['_CMSGCLIENTMMSLOBBYDATA']._serialized_end=2434
  _globals['_CMSGCLIENTMMSLOBBYDATA_MEMBER']._serialized_start=910
  _globals['_CMSGCLIENTMMSLOBBYDATA_MEMBER']._serialized_end=976
  _globals['_CMSGCLIENTMMSSENDLOBBYCHATMSG']._serialized_start=2436
  _globals['_CMSGCLIENTMMSSENDLOBBYCHATMSG']._serialized_end=2555
  _globals['_CMSGCLIENTMMSLOBBYCHATMSG']._serialized_start=2557
  _globals['_CMSGCLIENTMMSLOBBYCHATMSG']._serialized_end=2672
  _globals['_CMSGCLIENTMMSSETLOBBYOWNER']._serialized_start=2674
  _globals['_CMSGCLIENTMMSSETLOBBYOWNER']._serialized_end=2770
  _globals['_CMSGCLIENTMMSSETLOBBYOWNERRESPONSE']._serialized_start=2772
  _globals['_CMSGCLIENTMMSSETLOBBYOWNERRESPONSE']._serialized_end=2868
  _globals['_CMSGCLIENTMMSSETLOBBYLINKED']._serialized_start=2870
  _globals['_CMSGCLIENTMMSSETLOBBYLINKED']._serialized_end=2964
  _globals['_CMSGCLIENTMMSSETLOBBYGAMESERVER']._serialized_start=2967
  _globals['_CMSGCLIENTMMSSETLOBBYGAMESERVER']._serialized_end=3171
  _globals['_CMSGCLIENTMMSLOBBYGAMESERVERSET']._serialized_start=3174
  _globals['_CMSGCLIENTMMSLOBBYGAMESERVERSET']._serialized_end=3378
  _globals['_CMSGCLIENTMMSUSERJOINEDLOBBY']._serialized_start=3380
  _globals['_CMSGCLIENTMMSUSERJOINEDLOBBY']._serialized_end=3495
  _globals['_CMSGCLIENTMMSUSERLEFTLOBBY']._serialized_start=3497
  _globals['_CMSGCLIENTMMSUSERLEFTLOBBY']._serialized_end=3610
  _globals['_CMSGCLIENTMMSINVITETOLOBBY']._serialized_start=3612
  _globals['_CMSGCLIENTMMSINVITETOLOBBY']._serialized_end=3711
  _globals['_CMSGCLIENTMMSGETLOBBYSTATUS']._serialized_start=3713
  _globals['_CMSGCLIENTMMSGETLOBBYSTATUS']._serialized_end=3833
  _globals['_CMSGCLIENTMMSGETLOBBYSTATUSRESPONSE']._serialized_start=3836
  _globals['_CMSGCLIENTMMSGETLOBBYSTATUSRESPONSE']._serialized_end=3979
# @@protoc_insertion_point(module_scope)