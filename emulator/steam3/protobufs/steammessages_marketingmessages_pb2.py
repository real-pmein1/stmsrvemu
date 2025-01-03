# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_marketingmessages.proto
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
    'steammessages_marketingmessages.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steam3.protobufs import steammessages_base_pb2 as steammessages__base__pb2
from steam3.protobufs import steammessages_unified_base_pb2 as steammessages__unified__base__pb2
from steam3.protobufs import steammessages_storebrowse_pb2 as steammessages__storebrowse__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n%steammessages_marketingmessages.proto\x1a\x18steammessages_base.proto\x1a steammessages_unified_base.proto\x1a\x1fsteammessages_storebrowse.proto\"H\n5CMarketingMessages_GetActiveMarketingMessages_Request\x12\x0f\n\x07\x63ountry\x18\x01 \x01(\t\"\xed\x05\n\x16\x43MarketingMessageProto\x12\x0b\n\x03gid\x18\x01 \x01(\x06\x12\r\n\x05title\x18\x02 \x01(\t\x12@\n\x04type\x18\x03 \x01(\x0e\x32\x16.EMarketingMessageType:\x1ak_EMarketingMessageInvalid\x12P\n\nvisibility\x18\x04 \x01(\x0e\x32\x1c.EMarketingMessageVisibility:\x1ek_EMarketingMessageVisibleBeta\x12\x10\n\x08priority\x18\x05 \x01(\r\x12]\n\x10\x61ssociation_type\x18\x06 \x01(\x0e\x32!.EMarketingMessageAssociationType: k_EMarketingMessageNoAssociation\x12\x15\n\rassociated_id\x18\x07 \x01(\r\x12\x17\n\x0f\x61ssociated_name\x18\x08 \x01(\t\x12\x12\n\nstart_date\x18\t \x01(\r\x12\x10\n\x08\x65nd_date\x18\n \x01(\r\x12\x15\n\rcountry_allow\x18\x0b \x01(\t\x12\x14\n\x0c\x63ountry_deny\x18\x0c \x01(\t\x12)\n!ownership_restrictions_overridden\x18\r \x01(\x08\x12\x16\n\x0emust_own_appid\x18\x0e \x01(\r\x12\x1a\n\x12must_not_own_appid\x18\x0f \x01(\r\x12\x1a\n\x12must_own_packageid\x18\x10 \x01(\r\x12\x1e\n\x16must_not_own_packageid\x18\x11 \x01(\r\x12 \n\x18must_have_launched_appid\x18\x12 \x01(\r\x12\x1f\n\x17\x61\x64\x64itional_restrictions\x18\x13 \x01(\t\x12\x15\n\rtemplate_type\x18\x14 \x01(\t\x12\x15\n\rtemplate_vars\x18\x15 \x01(\t\x12\r\n\x05\x66lags\x18\x16 \x01(\r\x12\x14\n\x0c\x63reator_name\x18\x17 \x01(\t\"\x82\x01\n6CMarketingMessages_GetActiveMarketingMessages_Response\x12)\n\x08messages\x18\x01 \x03(\x0b\x32\x17.CMarketingMessageProto\x12\x1d\n\x15time_next_message_age\x18\x02 \x01(\r\"\xa2\x03\n6CMarketingMessages_GetMarketingMessagesForUser_Request\x12\x1d\n\x15include_seen_messages\x18\x01 \x01(\x08\x12\x14\n\x0c\x63ountry_code\x18\x02 \x01(\t\x12\x11\n\telanguage\x18\x03 \x01(\x05\x12\x31\n\x10operating_system\x18\x04 \x01(\x05\x42\x17\x82\xb5\x18\x13\x45OSType from client\x12\x1e\n\x16\x63lient_package_version\x18\x05 \x01(\x05\x12l\n\x07\x63ontext\x18\x06 \x01(\x0b\x32\x13.StoreBrowseContextBF\x82\xb5\x18\x42Optional, server can fill in from country code/language if not set\x12_\n\x0c\x64\x61ta_request\x18\x07 \x01(\x0b\x32\x1b.StoreBrowseItemDataRequestB,\x82\xb5\x18(If passed, item message will be returned\"\x93\x02\n\x18\x43\x44isplayMarketingMessage\x12\x0b\n\x03gid\x18\x01 \x01(\x06\x12\r\n\x05title\x18\x02 \x01(\t\x12@\n\x04type\x18\x03 \x01(\x0e\x32\x16.EMarketingMessageType:\x1ak_EMarketingMessageInvalid\x12(\n\x12\x61ssociated_item_id\x18\x04 \x01(\x0b\x32\x0c.StoreItemID\x12#\n\x0f\x61ssociated_item\x18\x05 \x01(\x0b\x32\n.StoreItem\x12\x17\n\x0f\x61ssociated_name\x18\x06 \x01(\t\x12\x15\n\rtemplate_type\x18\n \x01(\t\x12\x1a\n\x12template_vars_json\x18\x0b \x01(\t\"\xfa\x01\n7CMarketingMessages_GetMarketingMessagesForUser_Response\x12\x62\n\x08messages\x18\x01 \x03(\x0b\x32P.CMarketingMessages_GetMarketingMessagesForUser_Response.MarketingMessageForUser\x1a[\n\x17MarketingMessageForUser\x12\x14\n\x0c\x61lready_seen\x18\x01 \x01(\x08\x12*\n\x07message\x18\x02 \x01(\x0b\x32\x19.CDisplayMarketingMessage\"\xcb\x01\n5CMarketingMessages_GetDisplayMarketingMessage_Request\x12\x0b\n\x03gid\x18\x01 \x01(\x06\x12$\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x13.StoreBrowseContext\x12_\n\x0c\x64\x61ta_request\x18\x03 \x01(\x0b\x32\x1b.StoreBrowseItemDataRequestB,\x82\xb5\x18(If passed, item message will be returned\"d\n6CMarketingMessages_GetDisplayMarketingMessage_Response\x12*\n\x07message\x18\x01 \x01(\x0b\x32\x19.CDisplayMarketingMessage\">\n/CMarketingMessages_MarkMessageSeen_Notification\x12\x0b\n\x03gid\x18\x01 \x01(\x06\"=\n.CMarketingMessages_GetMarketingMessage_Request\x12\x0b\n\x03gid\x18\x01 \x01(\x06\"[\n/CMarketingMessages_GetMarketingMessage_Response\x12(\n\x07message\x18\x01 \x01(\x0b\x32\x17.CMarketingMessageProto\"]\n1CMarketingMessages_CreateMarketingMessage_Request\x12(\n\x07message\x18\x01 \x01(\x0b\x32\x17.CMarketingMessageProto\"A\n2CMarketingMessages_CreateMarketingMessage_Response\x12\x0b\n\x03gid\x18\x01 \x01(\x06\"j\n1CMarketingMessages_UpdateMarketingMessage_Request\x12\x0b\n\x03gid\x18\x01 \x01(\x06\x12(\n\x07message\x18\x02 \x01(\x0b\x32\x17.CMarketingMessageProto\"4\n2CMarketingMessages_UpdateMarketingMessage_Response\"@\n1CMarketingMessages_DeleteMarketingMessage_Request\x12\x0b\n\x03gid\x18\x01 \x01(\x06\"4\n2CMarketingMessages_DeleteMarketingMessage_Response\"\xfe\x01\n0CMarketingMessages_FindMarketingMessages_Request\x12S\n\x0blookup_type\x18\x01 \x01(\x0e\x32\x1c.EMarketingMessageLookupType: k_EMarketingMessageLookupInvalid\x12\x0b\n\x03gid\x18\x02 \x01(\x06\x12H\n\x0cmessage_type\x18\x03 \x01(\x0e\x32\x16.EMarketingMessageType:\x1ak_EMarketingMessageInvalid\x12\x0f\n\x07gidlist\x18\x04 \x03(\x06\x12\r\n\x05title\x18\x05 \x01(\t\"^\n1CMarketingMessages_FindMarketingMessages_Response\x12)\n\x08messages\x18\x01 \x03(\x0b\x32\x17.CMarketingMessageProto*\xea\x02\n\x15\x45MarketingMessageType\x12\x1e\n\x1ak_EMarketingMessageInvalid\x10\x00\x12#\n\x1fk_EMarketingMessageNowAvailable\x10\x01\x12\"\n\x1ek_EMarketingMessageWeekendDeal\x10\x02\x12\"\n\x1ek_EMarketingMessagePrePurchase\x10\x03\x12\x1e\n\x1ak_EMarketingMessagePlayNow\x10\x04\x12!\n\x1dk_EMarketingMessagePreloadNow\x10\x05\x12\x1e\n\x1ak_EMarketingMessageGeneral\x10\x06\x12\x1f\n\x1bk_EMarketingMessageDemoQuit\x10\x07\x12\x1e\n\x1ak_EMarketingMessageGifting\x10\x08\x12 \n\x1ck_EMarketingMessageEJsKorner\x10\t*g\n\x1b\x45MarketingMessageVisibility\x12\"\n\x1ek_EMarketingMessageVisibleBeta\x10\x01\x12$\n k_EMarketingMessageVisiblePublic\x10\x02*\x9f\x02\n EMarketingMessageAssociationType\x12$\n k_EMarketingMessageNoAssociation\x10\x00\x12%\n!k_EMarketingMessageAppAssociation\x10\x01\x12.\n*k_EMarketingMessageSubscriptionAssociation\x10\x02\x12+\n\'k_EMarketingMessagePublisherAssociation\x10\x03\x12\'\n#k_EMarketingMessageGenreAssociation\x10\x04\x12(\n$k_EMarketingMessageBundleAssociation\x10\x05*\xe2\x01\n\x1b\x45MarketingMessageLookupType\x12$\n k_EMarketingMessageLookupInvalid\x10\x00\x12\"\n\x1ek_EMarketingMessageLookupByGID\x10\x01\x12#\n\x1fk_EMarketingMessageLookupActive\x10\x02\x12,\n(k_EMarketingMessageLookupByTitleWithType\x10\x03\x12&\n\"k_EMarketingMessageLookupByGIDList\x10\x04\x32\xcd\r\n\x11MarketingMessages\x12\xbb\x01\n\x1aGetActiveMarketingMessages\x12\x36.CMarketingMessages_GetActiveMarketingMessages_Request\x1a\x37.CMarketingMessages_GetActiveMarketingMessages_Response\",\x82\xb5\x18(Get a list of active marketing messages.\x12\xdb\x01\n\x1bGetMarketingMessagesForUser\x12\x37.CMarketingMessages_GetMarketingMessagesForUser_Request\x1a\x38.CMarketingMessages_GetMarketingMessagesForUser_Response\"I\x82\xb5\x18\x45Get a list of active marketing messages filtered for a specific user.\x12\xbd\x01\n\x1aGetDisplayMarketingMessage\x12\x36.CMarketingMessages_GetDisplayMarketingMessage_Request\x1a\x37.CMarketingMessages_GetDisplayMarketingMessage_Response\".\x82\xb5\x18*Get a single marketing message, cacheable.\x12\x99\x01\n\x0fMarkMessageSeen\x12\x30.CMarketingMessages_MarkMessageSeen_Notification\x1a\x0b.NoResponse\"G\x82\xb5\x18\x43Mark that a user has viewed a message (so we won\'t show it again)\'.\x12\xcb\x01\n\x13GetMarketingMessage\x12/.CMarketingMessages_GetMarketingMessage_Request\x1a\x30.CMarketingMessages_GetMarketingMessage_Response\"Q\x82\xb5\x18MGet a single marketing message.  Admin account needed for non-active messages\x12\xa6\x01\n\x16\x43reateMarketingMessage\x12\x32.CMarketingMessages_CreateMarketingMessage_Request\x1a\x33.CMarketingMessages_CreateMarketingMessage_Response\"#\x82\xb5\x18\x1f\x43reate a new marketing message.\x12\xa2\x01\n\x16UpdateMarketingMessage\x12\x32.CMarketingMessages_UpdateMarketingMessage_Request\x1a\x33.CMarketingMessages_UpdateMarketingMessage_Response\"\x1f\x82\xb5\x18\x1bModify a marketing message.\x12\xa2\x01\n\x16\x44\x65leteMarketingMessage\x12\x32.CMarketingMessages_DeleteMarketingMessage_Request\x1a\x33.CMarketingMessages_DeleteMarketingMessage_Response\"\x1f\x82\xb5\x18\x1b\x44\x65lete a marketing message.\x12\xb5\x01\n\x15\x46indMarketingMessages\x12\x31.CMarketingMessages_FindMarketingMessages_Request\x1a\x32.CMarketingMessages_FindMarketingMessages_Response\"5\x82\xb5\x18\x31Search for marketing messages by name, type, etc.\x1aG\x82\xb5\x18\x43Marketing message message (\"Steam News\" updates at client startup).B\x03\x90\x01\x01')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_marketingmessages_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'\220\001\001'
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST'].fields_by_name['operating_system']._loaded_options = None
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST'].fields_by_name['operating_system']._serialized_options = b'\202\265\030\023EOSType from client'
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST'].fields_by_name['context']._loaded_options = None
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST'].fields_by_name['context']._serialized_options = b'\202\265\030BOptional, server can fill in from country code/language if not set'
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST'].fields_by_name['data_request']._loaded_options = None
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST'].fields_by_name['data_request']._serialized_options = b'\202\265\030(If passed, item message will be returned'
  _globals['_CMARKETINGMESSAGES_GETDISPLAYMARKETINGMESSAGE_REQUEST'].fields_by_name['data_request']._loaded_options = None
  _globals['_CMARKETINGMESSAGES_GETDISPLAYMARKETINGMESSAGE_REQUEST'].fields_by_name['data_request']._serialized_options = b'\202\265\030(If passed, item message will be returned'
  _globals['_MARKETINGMESSAGES']._loaded_options = None
  _globals['_MARKETINGMESSAGES']._serialized_options = b'\202\265\030CMarketing message message (\"Steam News\" updates at client startup).'
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetActiveMarketingMessages']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetActiveMarketingMessages']._serialized_options = b'\202\265\030(Get a list of active marketing messages.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetMarketingMessagesForUser']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetMarketingMessagesForUser']._serialized_options = b'\202\265\030EGet a list of active marketing messages filtered for a specific user.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetDisplayMarketingMessage']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetDisplayMarketingMessage']._serialized_options = b'\202\265\030*Get a single marketing message, cacheable.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['MarkMessageSeen']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['MarkMessageSeen']._serialized_options = b'\202\265\030CMark that a user has viewed a message (so we won\'t show it again)\'.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetMarketingMessage']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['GetMarketingMessage']._serialized_options = b'\202\265\030MGet a single marketing message.  Admin account needed for non-active messages'
  _globals['_MARKETINGMESSAGES'].methods_by_name['CreateMarketingMessage']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['CreateMarketingMessage']._serialized_options = b'\202\265\030\037Create a new marketing message.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['UpdateMarketingMessage']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['UpdateMarketingMessage']._serialized_options = b'\202\265\030\033Modify a marketing message.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['DeleteMarketingMessage']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['DeleteMarketingMessage']._serialized_options = b'\202\265\030\033Delete a marketing message.'
  _globals['_MARKETINGMESSAGES'].methods_by_name['FindMarketingMessages']._loaded_options = None
  _globals['_MARKETINGMESSAGES'].methods_by_name['FindMarketingMessages']._serialized_options = b'\202\265\0301Search for marketing messages by name, type, etc.'
  _globals['_EMARKETINGMESSAGETYPE']._serialized_start=3371
  _globals['_EMARKETINGMESSAGETYPE']._serialized_end=3733
  _globals['_EMARKETINGMESSAGEVISIBILITY']._serialized_start=3735
  _globals['_EMARKETINGMESSAGEVISIBILITY']._serialized_end=3838
  _globals['_EMARKETINGMESSAGEASSOCIATIONTYPE']._serialized_start=3841
  _globals['_EMARKETINGMESSAGEASSOCIATIONTYPE']._serialized_end=4128
  _globals['_EMARKETINGMESSAGELOOKUPTYPE']._serialized_start=4131
  _globals['_EMARKETINGMESSAGELOOKUPTYPE']._serialized_end=4357
  _globals['_CMARKETINGMESSAGES_GETACTIVEMARKETINGMESSAGES_REQUEST']._serialized_start=134
  _globals['_CMARKETINGMESSAGES_GETACTIVEMARKETINGMESSAGES_REQUEST']._serialized_end=206
  _globals['_CMARKETINGMESSAGEPROTO']._serialized_start=209
  _globals['_CMARKETINGMESSAGEPROTO']._serialized_end=958
  _globals['_CMARKETINGMESSAGES_GETACTIVEMARKETINGMESSAGES_RESPONSE']._serialized_start=961
  _globals['_CMARKETINGMESSAGES_GETACTIVEMARKETINGMESSAGES_RESPONSE']._serialized_end=1091
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST']._serialized_start=1094
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_REQUEST']._serialized_end=1512
  _globals['_CDISPLAYMARKETINGMESSAGE']._serialized_start=1515
  _globals['_CDISPLAYMARKETINGMESSAGE']._serialized_end=1790
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_RESPONSE']._serialized_start=1793
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_RESPONSE']._serialized_end=2043
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_RESPONSE_MARKETINGMESSAGEFORUSER']._serialized_start=1952
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGESFORUSER_RESPONSE_MARKETINGMESSAGEFORUSER']._serialized_end=2043
  _globals['_CMARKETINGMESSAGES_GETDISPLAYMARKETINGMESSAGE_REQUEST']._serialized_start=2046
  _globals['_CMARKETINGMESSAGES_GETDISPLAYMARKETINGMESSAGE_REQUEST']._serialized_end=2249
  _globals['_CMARKETINGMESSAGES_GETDISPLAYMARKETINGMESSAGE_RESPONSE']._serialized_start=2251
  _globals['_CMARKETINGMESSAGES_GETDISPLAYMARKETINGMESSAGE_RESPONSE']._serialized_end=2351
  _globals['_CMARKETINGMESSAGES_MARKMESSAGESEEN_NOTIFICATION']._serialized_start=2353
  _globals['_CMARKETINGMESSAGES_MARKMESSAGESEEN_NOTIFICATION']._serialized_end=2415
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGE_REQUEST']._serialized_start=2417
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGE_REQUEST']._serialized_end=2478
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGE_RESPONSE']._serialized_start=2480
  _globals['_CMARKETINGMESSAGES_GETMARKETINGMESSAGE_RESPONSE']._serialized_end=2571
  _globals['_CMARKETINGMESSAGES_CREATEMARKETINGMESSAGE_REQUEST']._serialized_start=2573
  _globals['_CMARKETINGMESSAGES_CREATEMARKETINGMESSAGE_REQUEST']._serialized_end=2666
  _globals['_CMARKETINGMESSAGES_CREATEMARKETINGMESSAGE_RESPONSE']._serialized_start=2668
  _globals['_CMARKETINGMESSAGES_CREATEMARKETINGMESSAGE_RESPONSE']._serialized_end=2733
  _globals['_CMARKETINGMESSAGES_UPDATEMARKETINGMESSAGE_REQUEST']._serialized_start=2735
  _globals['_CMARKETINGMESSAGES_UPDATEMARKETINGMESSAGE_REQUEST']._serialized_end=2841
  _globals['_CMARKETINGMESSAGES_UPDATEMARKETINGMESSAGE_RESPONSE']._serialized_start=2843
  _globals['_CMARKETINGMESSAGES_UPDATEMARKETINGMESSAGE_RESPONSE']._serialized_end=2895
  _globals['_CMARKETINGMESSAGES_DELETEMARKETINGMESSAGE_REQUEST']._serialized_start=2897
  _globals['_CMARKETINGMESSAGES_DELETEMARKETINGMESSAGE_REQUEST']._serialized_end=2961
  _globals['_CMARKETINGMESSAGES_DELETEMARKETINGMESSAGE_RESPONSE']._serialized_start=2963
  _globals['_CMARKETINGMESSAGES_DELETEMARKETINGMESSAGE_RESPONSE']._serialized_end=3015
  _globals['_CMARKETINGMESSAGES_FINDMARKETINGMESSAGES_REQUEST']._serialized_start=3018
  _globals['_CMARKETINGMESSAGES_FINDMARKETINGMESSAGES_REQUEST']._serialized_end=3272
  _globals['_CMARKETINGMESSAGES_FINDMARKETINGMESSAGES_RESPONSE']._serialized_start=3274
  _globals['_CMARKETINGMESSAGES_FINDMARKETINGMESSAGES_RESPONSE']._serialized_end=3368
  _globals['_MARKETINGMESSAGES']._serialized_start=4360
  _globals['_MARKETINGMESSAGES']._serialized_end=6101
_builder.BuildServices(DESCRIPTOR, 'steammessages_marketingmessages_pb2', _globals)
# @@protoc_insertion_point(module_scope)
