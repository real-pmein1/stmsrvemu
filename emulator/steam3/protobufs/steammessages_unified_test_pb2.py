# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_unified_test.proto
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
    'steammessages_unified_test.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steam3.protobufs import steammessages_base_pb2 as steammessages__base__pb2
from steam3.protobufs import steammessages_unified_base_pb2 as steammessages__unified__base__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n steammessages_unified_test.proto\x1a\x18steammessages_base.proto\x1a steammessages_unified_base.proto\"G\n CMsgTest_MessageToClient_Request\x12#\n\tsome_text\x18\x01 \x01(\tB\x10\x82\xb5\x18\x0cSome string.\"H\n!CMsgTest_MessageToClient_Response\x12#\n\tsome_text\x18\x01 \x01(\tB\x10\x82\xb5\x18\x0cSome string.\"I\n\"CMsgTest_NotifyClient_Notification\x12#\n\tsome_text\x18\x01 \x01(\tB\x10\x82\xb5\x18\x0cSome string.\"G\n CMsgTest_MessageToServer_Request\x12#\n\tsome_text\x18\x01 \x01(\tB\x10\x82\xb5\x18\x0cSome string.\"H\n!CMsgTest_MessageToServer_Response\x12#\n\tsome_text\x18\x01 \x01(\tB\x10\x82\xb5\x18\x0cSome string.\"I\n\"CMsgTest_NotifyServer_Notification\x12#\n\tsome_text\x18\x01 \x01(\tB\x10\x82\xb5\x18\x0cSome string.2\x83\x02\n\x0fTestSteamClient\x12\x81\x01\n\x0fMessageToClient\x12!.CMsgTest_MessageToClient_Request\x1a\".CMsgTest_MessageToClient_Response\"\'\x82\xb5\x18#Some description - MessageToClient.\x12\x66\n\x0cNotifyClient\x12#.CMsgTest_NotifyClient_Notification\x1a\x0b.NoResponse\"$\x82\xb5\x18 Some description - NotifyClient.\x1a\x04\xc0\xb5\x18\x02\x32\x82\x02\n\x14TestServerFromClient\x12\x81\x01\n\x0fMessageToServer\x12!.CMsgTest_MessageToServer_Request\x1a\".CMsgTest_MessageToServer_Response\"\'\x82\xb5\x18#Some description - MessageToServer.\x12\x66\n\x0cNotifyServer\x12#.CMsgTest_NotifyServer_Notification\x1a\x0b.NoResponse\"$\x82\xb5\x18 Some description - NotifyServer.B\x03\x90\x01\x01')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_unified_test_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'\220\001\001'
  _globals['_CMSGTEST_MESSAGETOCLIENT_REQUEST'].fields_by_name['some_text']._loaded_options = None
  _globals['_CMSGTEST_MESSAGETOCLIENT_REQUEST'].fields_by_name['some_text']._serialized_options = b'\202\265\030\014Some string.'
  _globals['_CMSGTEST_MESSAGETOCLIENT_RESPONSE'].fields_by_name['some_text']._loaded_options = None
  _globals['_CMSGTEST_MESSAGETOCLIENT_RESPONSE'].fields_by_name['some_text']._serialized_options = b'\202\265\030\014Some string.'
  _globals['_CMSGTEST_NOTIFYCLIENT_NOTIFICATION'].fields_by_name['some_text']._loaded_options = None
  _globals['_CMSGTEST_NOTIFYCLIENT_NOTIFICATION'].fields_by_name['some_text']._serialized_options = b'\202\265\030\014Some string.'
  _globals['_CMSGTEST_MESSAGETOSERVER_REQUEST'].fields_by_name['some_text']._loaded_options = None
  _globals['_CMSGTEST_MESSAGETOSERVER_REQUEST'].fields_by_name['some_text']._serialized_options = b'\202\265\030\014Some string.'
  _globals['_CMSGTEST_MESSAGETOSERVER_RESPONSE'].fields_by_name['some_text']._loaded_options = None
  _globals['_CMSGTEST_MESSAGETOSERVER_RESPONSE'].fields_by_name['some_text']._serialized_options = b'\202\265\030\014Some string.'
  _globals['_CMSGTEST_NOTIFYSERVER_NOTIFICATION'].fields_by_name['some_text']._loaded_options = None
  _globals['_CMSGTEST_NOTIFYSERVER_NOTIFICATION'].fields_by_name['some_text']._serialized_options = b'\202\265\030\014Some string.'
  _globals['_TESTSTEAMCLIENT']._loaded_options = None
  _globals['_TESTSTEAMCLIENT']._serialized_options = b'\300\265\030\002'
  _globals['_TESTSTEAMCLIENT'].methods_by_name['MessageToClient']._loaded_options = None
  _globals['_TESTSTEAMCLIENT'].methods_by_name['MessageToClient']._serialized_options = b'\202\265\030#Some description - MessageToClient.'
  _globals['_TESTSTEAMCLIENT'].methods_by_name['NotifyClient']._loaded_options = None
  _globals['_TESTSTEAMCLIENT'].methods_by_name['NotifyClient']._serialized_options = b'\202\265\030 Some description - NotifyClient.'
  _globals['_TESTSERVERFROMCLIENT'].methods_by_name['MessageToServer']._loaded_options = None
  _globals['_TESTSERVERFROMCLIENT'].methods_by_name['MessageToServer']._serialized_options = b'\202\265\030#Some description - MessageToServer.'
  _globals['_TESTSERVERFROMCLIENT'].methods_by_name['NotifyServer']._loaded_options = None
  _globals['_TESTSERVERFROMCLIENT'].methods_by_name['NotifyServer']._serialized_options = b'\202\265\030 Some description - NotifyServer.'
  _globals['_CMSGTEST_MESSAGETOCLIENT_REQUEST']._serialized_start=96
  _globals['_CMSGTEST_MESSAGETOCLIENT_REQUEST']._serialized_end=167
  _globals['_CMSGTEST_MESSAGETOCLIENT_RESPONSE']._serialized_start=169
  _globals['_CMSGTEST_MESSAGETOCLIENT_RESPONSE']._serialized_end=241
  _globals['_CMSGTEST_NOTIFYCLIENT_NOTIFICATION']._serialized_start=243
  _globals['_CMSGTEST_NOTIFYCLIENT_NOTIFICATION']._serialized_end=316
  _globals['_CMSGTEST_MESSAGETOSERVER_REQUEST']._serialized_start=318
  _globals['_CMSGTEST_MESSAGETOSERVER_REQUEST']._serialized_end=389
  _globals['_CMSGTEST_MESSAGETOSERVER_RESPONSE']._serialized_start=391
  _globals['_CMSGTEST_MESSAGETOSERVER_RESPONSE']._serialized_end=463
  _globals['_CMSGTEST_NOTIFYSERVER_NOTIFICATION']._serialized_start=465
  _globals['_CMSGTEST_NOTIFYSERVER_NOTIFICATION']._serialized_end=538
  _globals['_TESTSTEAMCLIENT']._serialized_start=541
  _globals['_TESTSTEAMCLIENT']._serialized_end=800
  _globals['_TESTSERVERFROMCLIENT']._serialized_start=803
  _globals['_TESTSERVERFROMCLIENT']._serialized_end=1061
_builder.BuildServices(DESCRIPTOR, 'steammessages_unified_test_pb2', _globals)
# @@protoc_insertion_point(module_scope)
