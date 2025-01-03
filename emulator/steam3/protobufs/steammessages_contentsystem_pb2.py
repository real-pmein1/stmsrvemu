# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_contentsystem.proto
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
    'steammessages_contentsystem.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steam3.protobufs import steammessages_base_pb2 as steammessages__base__pb2
from steam3.protobufs import steammessages_unified_base_pb2 as steammessages__unified__base__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!steammessages_contentsystem.proto\x1a\x18steammessages_base.proto\x1a steammessages_unified_base.proto\"\xb5\x02\n6CContentServerDirectory_GetServersForSteamPipe_Request\x12#\n\x07\x63\x65ll_id\x18\x01 \x01(\rB\x12\x82\xb5\x18\x0e\x63lient Cell ID\x12\x39\n\x0bmax_servers\x18\x02 \x01(\r:\x02\x32\x30\x42 \x82\xb5\x18\x1cmax servers in response list\x12*\n\x0bip_override\x18\x03 \x01(\tB\x15\x82\xb5\x18\x11\x63lient IP address\x12+\n\rlauncher_type\x18\x04 \x01(\x05:\x01\x30\x42\x11\x82\xb5\x18\rlauncher type\x12\x42\n\x0bipv6_public\x18\x05 \x01(\tB-\x82\xb5\x18)client public ipv6 address if it knows it\"\xdb\x02\n\"CContentServerDirectory_ServerInfo\x12\x0c\n\x04type\x18\x01 \x01(\t\x12\x11\n\tsource_id\x18\x02 \x01(\x05\x12\x0f\n\x07\x63\x65ll_id\x18\x03 \x01(\x05\x12\x0c\n\x04load\x18\x04 \x01(\x05\x12\x15\n\rweighted_load\x18\x05 \x01(\x02\x12\"\n\x1anum_entries_in_client_list\x18\x06 \x01(\x05\x12\x18\n\x10steam_china_only\x18\x07 \x01(\x08\x12\x0c\n\x04host\x18\x08 \x01(\t\x12\r\n\x05vhost\x18\t \x01(\t\x12\x14\n\x0cuse_as_proxy\x18\n \x01(\x08\x12#\n\x1bproxy_request_path_template\x18\x0b \x01(\t\x12\x15\n\rhttps_support\x18\x0c \x01(\t\x12\x17\n\x0f\x61llowed_app_ids\x18\r \x03(\r\x12\x18\n\x10preferred_server\x18\x0e \x01(\x08\"o\n7CContentServerDirectory_GetServersForSteamPipe_Response\x12\x34\n\x07servers\x18\x01 \x03(\x0b\x32#.CContentServerDirectory_ServerInfo\"\x89\x01\n1CContentServerDirectory_GetDepotPatchInfo_Request\x12\r\n\x05\x61ppid\x18\x01 \x01(\r\x12\x0f\n\x07\x64\x65potid\x18\x02 \x01(\r\x12\x19\n\x11source_manifestid\x18\x03 \x01(\x04\x12\x19\n\x11target_manifestid\x18\x04 \x01(\x04\"{\n2CContentServerDirectory_GetDepotPatchInfo_Response\x12\x14\n\x0cis_available\x18\x01 \x01(\x08\x12\x12\n\npatch_size\x18\x02 \x01(\x04\x12\x1b\n\x13patched_chunks_size\x18\x03 \x01(\x04\"P\n4CContentServerDirectory_GetClientUpdateHosts_Request\x12\x18\n\x10\x63\x61\x63hed_signature\x18\x01 \x01(\t\"w\n5CContentServerDirectory_GetClientUpdateHosts_Response\x12\x10\n\x08hosts_kv\x18\x01 \x01(\t\x12\x18\n\x10valid_until_time\x18\x02 \x01(\x04\x12\x12\n\nip_country\x18\x03 \x01(\t\"\xa1\x01\n6CContentServerDirectory_GetManifestRequestCode_Request\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x10\n\x08\x64\x65pot_id\x18\x02 \x01(\r\x12\x13\n\x0bmanifest_id\x18\x03 \x01(\x04\x12\x12\n\napp_branch\x18\x04 \x01(\t\x12\x1c\n\x14\x62ranch_password_hash\x18\x05 \x01(\t\"X\n7CContentServerDirectory_GetManifestRequestCode_Response\x12\x1d\n\x15manifest_request_code\x18\x01 \x01(\x04\x32\xe0\x04\n\x16\x43ontentServerDirectory\x12\x8b\x01\n\x16GetServersForSteamPipe\x12\x37.CContentServerDirectory_GetServersForSteamPipe_Request\x1a\x38.CContentServerDirectory_GetServersForSteamPipe_Response\x12|\n\x11GetDepotPatchInfo\x12\x32.CContentServerDirectory_GetDepotPatchInfo_Request\x1a\x33.CContentServerDirectory_GetDepotPatchInfo_Response\x12\x85\x01\n\x14GetClientUpdateHosts\x12\x35.CContentServerDirectory_GetClientUpdateHosts_Request\x1a\x36.CContentServerDirectory_GetClientUpdateHosts_Response\x12\x8b\x01\n\x16GetManifestRequestCode\x12\x37.CContentServerDirectory_GetManifestRequestCode_Request\x1a\x38.CContentServerDirectory_GetManifestRequestCode_Response\x1a$\x82\xb5\x18 Content Server and CDN directoryB\x03\x90\x01\x01')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_contentsystem_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'\220\001\001'
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['cell_id']._loaded_options = None
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['cell_id']._serialized_options = b'\202\265\030\016client Cell ID'
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['max_servers']._loaded_options = None
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['max_servers']._serialized_options = b'\202\265\030\034max servers in response list'
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['ip_override']._loaded_options = None
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['ip_override']._serialized_options = b'\202\265\030\021client IP address'
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['launcher_type']._loaded_options = None
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['launcher_type']._serialized_options = b'\202\265\030\rlauncher type'
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['ipv6_public']._loaded_options = None
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST'].fields_by_name['ipv6_public']._serialized_options = b'\202\265\030)client public ipv6 address if it knows it'
  _globals['_CONTENTSERVERDIRECTORY']._loaded_options = None
  _globals['_CONTENTSERVERDIRECTORY']._serialized_options = b'\202\265\030 Content Server and CDN directory'
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST']._serialized_start=98
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_REQUEST']._serialized_end=407
  _globals['_CCONTENTSERVERDIRECTORY_SERVERINFO']._serialized_start=410
  _globals['_CCONTENTSERVERDIRECTORY_SERVERINFO']._serialized_end=757
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_RESPONSE']._serialized_start=759
  _globals['_CCONTENTSERVERDIRECTORY_GETSERVERSFORSTEAMPIPE_RESPONSE']._serialized_end=870
  _globals['_CCONTENTSERVERDIRECTORY_GETDEPOTPATCHINFO_REQUEST']._serialized_start=873
  _globals['_CCONTENTSERVERDIRECTORY_GETDEPOTPATCHINFO_REQUEST']._serialized_end=1010
  _globals['_CCONTENTSERVERDIRECTORY_GETDEPOTPATCHINFO_RESPONSE']._serialized_start=1012
  _globals['_CCONTENTSERVERDIRECTORY_GETDEPOTPATCHINFO_RESPONSE']._serialized_end=1135
  _globals['_CCONTENTSERVERDIRECTORY_GETCLIENTUPDATEHOSTS_REQUEST']._serialized_start=1137
  _globals['_CCONTENTSERVERDIRECTORY_GETCLIENTUPDATEHOSTS_REQUEST']._serialized_end=1217
  _globals['_CCONTENTSERVERDIRECTORY_GETCLIENTUPDATEHOSTS_RESPONSE']._serialized_start=1219
  _globals['_CCONTENTSERVERDIRECTORY_GETCLIENTUPDATEHOSTS_RESPONSE']._serialized_end=1338
  _globals['_CCONTENTSERVERDIRECTORY_GETMANIFESTREQUESTCODE_REQUEST']._serialized_start=1341
  _globals['_CCONTENTSERVERDIRECTORY_GETMANIFESTREQUESTCODE_REQUEST']._serialized_end=1502
  _globals['_CCONTENTSERVERDIRECTORY_GETMANIFESTREQUESTCODE_RESPONSE']._serialized_start=1504
  _globals['_CCONTENTSERVERDIRECTORY_GETMANIFESTREQUESTCODE_RESPONSE']._serialized_end=1592
  _globals['_CONTENTSERVERDIRECTORY']._serialized_start=1595
  _globals['_CONTENTSERVERDIRECTORY']._serialized_end=2203
_builder.BuildServices(DESCRIPTOR, 'steammessages_contentsystem_pb2', _globals)
# @@protoc_insertion_point(module_scope)
