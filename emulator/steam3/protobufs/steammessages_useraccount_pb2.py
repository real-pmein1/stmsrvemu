# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_useraccount.proto
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
    'steammessages_useraccount.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steam3.protobufs import steammessages_base_pb2 as steammessages__base__pb2
from steam3.protobufs import steammessages_unified_base_pb2 as steammessages__unified__base__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1fsteammessages_useraccount.proto\x1a\x18steammessages_base.proto\x1a steammessages_unified_base.proto\"P\n8CUserAccount_GetAvailableValveDiscountPromotions_Request\x12\x14\n\x0c\x63ountry_code\x18\x01 \x01(\t\"\x85\x04\n9CUserAccount_GetAvailableValveDiscountPromotions_Response\x12l\n\npromotions\x18\x01 \x03(\x0b\x32X.CUserAccount_GetAvailableValveDiscountPromotions_Response.ValveDiscountPromotionDetails\x1a\xd9\x02\n\x1dValveDiscountPromotionDetails\x12\x13\n\x0bpromotionid\x18\x01 \x01(\r\x12\x1d\n\x15promotion_description\x18\x02 \x01(\t\x12\x1b\n\x13minimum_cart_amount\x18\x03 \x01(\x03\x12\'\n\x1fminimum_cart_amount_for_display\x18\x04 \x01(\x03\x12\x17\n\x0f\x64iscount_amount\x18\x05 \x01(\x03\x12\x15\n\rcurrency_code\x18\x06 \x01(\x05\x12\x1b\n\x13\x61vailable_use_count\x18\x07 \x01(\x05\x12!\n\x19promotional_discount_type\x18\x08 \x01(\x05\x12\x19\n\x11loyalty_reward_id\x18\t \x01(\x05\x12\x1c\n\x14localized_name_token\x18\n \x01(\t\x12\x15\n\rmax_use_count\x18\x0b \x01(\x05\"\x8a\x01\n+CUserAccount_GetClientWalletDetails_Request\x12\x1e\n\x16include_balance_in_usd\x18\x01 \x01(\x08\x12\x18\n\rwallet_region\x18\x02 \x01(\x05:\x01\x31\x12!\n\x19include_formatted_balance\x18\x03 \x01(\x08\"\x93\x03\n&CUserAccount_GetWalletDetails_Response\x12\x12\n\nhas_wallet\x18\x01 \x01(\x08\x12\x19\n\x11user_country_code\x18\x02 \x01(\t\x12\x1b\n\x13wallet_country_code\x18\x03 \x01(\t\x12\x14\n\x0cwallet_state\x18\x04 \x01(\t\x12\x0f\n\x07\x62\x61lance\x18\x05 \x01(\x03\x12\x17\n\x0f\x64\x65layed_balance\x18\x06 \x01(\x03\x12\x15\n\rcurrency_code\x18\x07 \x01(\x05\x12\x1c\n\x14time_most_recent_txn\x18\x08 \x01(\r\x12\x19\n\x11most_recent_txnid\x18\t \x01(\x04\x12\x16\n\x0e\x62\x61lance_in_usd\x18\n \x01(\x03\x12\x1e\n\x16\x64\x65layed_balance_in_usd\x18\x0b \x01(\x03\x12#\n\x1bhas_wallet_in_other_regions\x18\x0c \x01(\x08\x12\x15\n\rother_regions\x18\r \x03(\x05\x12\x19\n\x11\x66ormatted_balance\x18\x0e \x01(\t\"+\n)CUserAccount_GetAccountLinkStatus_Request\"}\n*CUserAccount_GetAccountLinkStatus_Response\x12\x0c\n\x04pwid\x18\x01 \x01(\r\x12\x1d\n\x15identity_verification\x18\x02 \x01(\r\x12\"\n\x1aperformed_age_verification\x18\x03 \x01(\x08\"9\n(CUserAccount_CancelLicenseForApp_Request\x12\r\n\x05\x61ppid\x18\x01 \x01(\r\"+\n)CUserAccount_CancelLicenseForApp_Response\"6\n#CUserAccount_GetUserCountry_Request\x12\x0f\n\x07steamid\x18\x01 \x01(\x06\"7\n$CUserAccount_GetUserCountry_Response\x12\x0f\n\x07\x63ountry\x18\x01 \x01(\t\"r\n,CUserAccount_CreateFriendInviteToken_Request\x12\x14\n\x0cinvite_limit\x18\x01 \x01(\r\x12\x17\n\x0finvite_duration\x18\x02 \x01(\r\x12\x13\n\x0binvite_note\x18\x03 \x01(\t\"\x99\x01\n-CUserAccount_CreateFriendInviteToken_Response\x12\x14\n\x0cinvite_token\x18\x01 \x01(\t\x12\x14\n\x0cinvite_limit\x18\x02 \x01(\x04\x12\x17\n\x0finvite_duration\x18\x03 \x01(\x04\x12\x14\n\x0ctime_created\x18\x04 \x01(\x07\x12\r\n\x05valid\x18\x05 \x01(\x08\",\n*CUserAccount_GetFriendInviteTokens_Request\"m\n+CUserAccount_GetFriendInviteTokens_Response\x12>\n\x06tokens\x18\x01 \x03(\x0b\x32..CUserAccount_CreateFriendInviteToken_Response\"S\n*CUserAccount_ViewFriendInviteToken_Request\x12\x0f\n\x07steamid\x18\x01 \x01(\x06\x12\x14\n\x0cinvite_token\x18\x02 \x01(\t\"f\n+CUserAccount_ViewFriendInviteToken_Response\x12\r\n\x05valid\x18\x01 \x01(\x08\x12\x0f\n\x07steamid\x18\x02 \x01(\x04\x12\x17\n\x0finvite_duration\x18\x03 \x01(\x04\"U\n,CUserAccount_RedeemFriendInviteToken_Request\x12\x0f\n\x07steamid\x18\x01 \x01(\x06\x12\x14\n\x0cinvite_token\x18\x02 \x01(\t\"/\n-CUserAccount_RedeemFriendInviteToken_Response\"D\n,CUserAccount_RevokeFriendInviteToken_Request\x12\x14\n\x0cinvite_token\x18\x01 \x01(\t\"/\n-CUserAccount_RevokeFriendInviteToken_Response\">\n\'CUserAccount_RegisterCompatTool_Request\x12\x13\n\x0b\x63ompat_tool\x18\x01 \x01(\r\"*\n(CUserAccount_RegisterCompatTool_Response\"\x9c\x03\n,CAccountLinking_GetLinkedAccountInfo_Request\x12H\n\x0c\x61\x63\x63ount_type\x18\x01 \x01(\x0e\x32\x15.EInternalAccountType:\x1bk_EInternalSteamAccountType\x12+\n\naccount_id\x18\x02 \x01(\x04\x42\x17\x82\xb5\x18\x13Internal account ID\x12t\n\x06\x66ilter\x18\x03 \x01(\x0e\x32\x15.EExternalAccountType:\x0fk_EExternalNoneB<\x82\xb5\x18\x38if specified then only return this external account type\x12\x7f\n\x13return_access_token\x18\x04 \x01(\x08\x42\x62\x82\xb5\x18^if provided and true, then returns valid access token if available. It may refresh the token. \"\x8b\x06\n-CAccountLinking_GetLinkedAccountInfo_Response\x12h\n\x11\x65xternal_accounts\x18\x01 \x03(\x0b\x32M.CAccountLinking_GetLinkedAccountInfo_Response.CExternalAccountTuple_Response\x1a\xef\x04\n\x1e\x43\x45xternalAccountTuple_Response\x12=\n\rexternal_type\x18\x01 \x01(\x0e\x32\x15.EExternalAccountType:\x0fk_EExternalNone\x12;\n\x0b\x65xternal_id\x18\x02 \x01(\tB&\x82\xb5\x18\"unique external account identifier\x12:\n\x12\x65xternal_user_name\x18\x03 \x01(\tB\x1e\x82\xb5\x18\x1auser readable; best effort\x12S\n\x0c\x65xternal_url\x18\x04 \x01(\tB=\x82\xb5\x18\x39required for all, can be a sentinal to verify correctness\x12@\n\x0c\x61\x63\x63\x65ss_token\x18\x05 \x01(\tB*\x82\xb5\x18&provided if requeest and it was valid.\x12k\n\x13\x61\x63\x63\x65ss_token_secret\x18\x06 \x01(\tBN\x82\xb5\x18Jrequired for OAuth v1 and signing the message, provided with access token.\x12\x90\x01\n\x08is_valid\x18\x07 \x01(\x08\x42~\x82\xb5\x18zIf false, it means access token no longer work (expired, disconnected) and the link is now broken. Inform user to refresh.\"w\n.CEmbeddedClient_AuthorizeCurrentDevice_Request\x12\x0f\n\x07steamid\x18\x01 \x01(\x06\x12\r\n\x05\x61ppid\x18\x02 \x01(\r\x12\x13\n\x0b\x64\x65vice_info\x18\x03 \x01(\t\x12\x10\n\x08\x64\x65viceid\x18\x04 \x01(\r\"`\n\x15\x43\x45mbeddedClient_Token\x12\x0f\n\x07steamid\x18\x01 \x01(\x06\x12\x14\n\x0c\x63lient_token\x18\x02 \x01(\x0c\x12\x0e\n\x06\x65xpiry\x18\x03 \x01(\r\x12\x10\n\x08\x64\x65viceid\x18\x04 \x01(\r\"a\n(CEmbeddedClient_AuthorizeDevice_Response\x12\x0e\n\x06result\x18\x01 \x01(\r\x12%\n\x05token\x18\x02 \x01(\x0b\x32\x16.CEmbeddedClient_Token*\x8d\x01\n\x14\x45InternalAccountType\x12\x1f\n\x1bk_EInternalSteamAccountType\x10\x01\x12\x17\n\x13k_EInternalClanType\x10\x02\x12\x16\n\x12k_EInternalAppType\x10\x03\x12#\n\x1fk_EInternalBroadcastChannelType\x10\x04*\x86\x02\n\x14\x45\x45xternalAccountType\x12\x13\n\x0fk_EExternalNone\x10\x00\x12\x1b\n\x17k_EExternalSteamAccount\x10\x01\x12\x1c\n\x18k_EExternalGoogleAccount\x10\x02\x12\x1e\n\x1ak_EExternalFacebookAccount\x10\x03\x12\x1d\n\x19k_EExternalTwitterAccount\x10\x04\x12\x1c\n\x18k_EExternalTwitchAccount\x10\x05\x12$\n k_EExternalYouTubeChannelAccount\x10\x06\x12\x1b\n\x17k_EExternalFacebookPage\x10\x07\x32\xc4\x0f\n\x0bUserAccount\x12\xe0\x01\n#GetAvailableValveDiscountPromotions\x12\x39.CUserAccount_GetAvailableValveDiscountPromotions_Request\x1a:.CUserAccount_GetAvailableValveDiscountPromotions_Response\"B\x82\xb5\x18>Gets the available promotional discounts available to the user\x12\xa7\x01\n\x16GetClientWalletDetails\x12,.CUserAccount_GetClientWalletDetails_Request\x1a\'.CUserAccount_GetWalletDetails_Response\"6\x82\xb5\x18\x32Returns balance and details about any users wallet\x12\x90\x01\n\x14GetAccountLinkStatus\x12*.CUserAccount_GetAccountLinkStatus_Request\x1a+.CUserAccount_GetAccountLinkStatus_Response\"\x1f\x82\xb5\x18\x1b\x46\x65tches account link status\x12\x93\x01\n\x13\x43\x61ncelLicenseForApp\x12).CUserAccount_CancelLicenseForApp_Request\x1a*.CUserAccount_CancelLicenseForApp_Response\"%\x82\xb5\x18!Cancels a free license for a user\x12\xc9\x01\n\x0eGetUserCountry\x12$.CUserAccount_GetUserCountry_Request\x1a%.CUserAccount_GetUserCountry_Response\"j\x82\xb5\x18\x66Get the country code associated with the passed steamid (only available for logged-in user or support)\x12\xc7\x01\n\x17\x43reateFriendInviteToken\x12-.CUserAccount_CreateFriendInviteToken_Request\x1a..CUserAccount_CreateFriendInviteToken_Response\"M\x82\xb5\x18ICreate a limited-use token that can be used to create a friend request_id\x12\xa1\x01\n\x15GetFriendInviteTokens\x12+.CUserAccount_GetFriendInviteTokens_Request\x1a,.CUserAccount_GetFriendInviteTokens_Response\"-\x82\xb5\x18)Get the set of active tokens for the user\x12\x9b\x01\n\x15ViewFriendInviteToken\x12+.CUserAccount_ViewFriendInviteToken_Request\x1a,.CUserAccount_ViewFriendInviteToken_Response\"\'\x82\xb5\x18#View details about an invite token \x12\xb7\x01\n\x17RedeemFriendInviteToken\x12-.CUserAccount_RedeemFriendInviteToken_Request\x1a..CUserAccount_RedeemFriendInviteToken_Response\"=\x82\xb5\x18\x39\x43reate a friend relationship using the given invite token\x12\xa2\x01\n\x17RevokeFriendInviteToken\x12-.CUserAccount_RevokeFriendInviteToken_Request\x1a..CUserAccount_RevokeFriendInviteToken_Response\"(\x82\xb5\x18$Revoke an active friend invite token\x12\x98\x01\n\x12RegisterCompatTool\x12(.CUserAccount_RegisterCompatTool_Request\x1a).CUserAccount_RegisterCompatTool_Response\"-\x82\xb5\x18)Register intended account usage of a tool\x1a-\x82\xb5\x18)A service to get user account information2\x9d\x02\n\x0e\x41\x63\x63ountLinking\x12\xd3\x01\n\x14GetLinkedAccountInfo\x12-.CAccountLinking_GetLinkedAccountInfo_Request\x1a..CAccountLinking_GetLinkedAccountInfo_Response\"\\\x82\xb5\x18XList all my active linked external accounts; may be requested to return the access token\x1a\x35\x82\xb5\x18\x31\x41 service to manage and link to external accounts2\xa4\x02\n\x0e\x45mbeddedClient\x12\xc1\x01\n\x16\x41uthorizeCurrentDevice\x12/.CEmbeddedClient_AuthorizeCurrentDevice_Request\x1a).CEmbeddedClient_AuthorizeDevice_Response\"K\x82\xb5\x18GUse a logged-in (password/etc) session to create a durable access token\x1aN\x82\xb5\x18JService to authorize and manage Steam functions directly embedded in gamesB\x03\x90\x01\x01')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_useraccount_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'\220\001\001'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST'].fields_by_name['account_id']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST'].fields_by_name['account_id']._serialized_options = b'\202\265\030\023Internal account ID'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST'].fields_by_name['filter']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST'].fields_by_name['filter']._serialized_options = b'\202\265\0308if specified then only return this external account type'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST'].fields_by_name['return_access_token']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST'].fields_by_name['return_access_token']._serialized_options = b'\202\265\030^if provided and true, then returns valid access token if available. It may refresh the token. '
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['external_id']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['external_id']._serialized_options = b'\202\265\030\"unique external account identifier'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['external_user_name']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['external_user_name']._serialized_options = b'\202\265\030\032user readable; best effort'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['external_url']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['external_url']._serialized_options = b'\202\265\0309required for all, can be a sentinal to verify correctness'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['access_token']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['access_token']._serialized_options = b'\202\265\030&provided if requeest and it was valid.'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['access_token_secret']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['access_token_secret']._serialized_options = b'\202\265\030Jrequired for OAuth v1 and signing the message, provided with access token.'
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['is_valid']._loaded_options = None
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE'].fields_by_name['is_valid']._serialized_options = b'\202\265\030zIf false, it means access token no longer work (expired, disconnected) and the link is now broken. Inform user to refresh.'
  _globals['_USERACCOUNT']._loaded_options = None
  _globals['_USERACCOUNT']._serialized_options = b'\202\265\030)A service to get user account information'
  _globals['_USERACCOUNT'].methods_by_name['GetAvailableValveDiscountPromotions']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['GetAvailableValveDiscountPromotions']._serialized_options = b'\202\265\030>Gets the available promotional discounts available to the user'
  _globals['_USERACCOUNT'].methods_by_name['GetClientWalletDetails']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['GetClientWalletDetails']._serialized_options = b'\202\265\0302Returns balance and details about any users wallet'
  _globals['_USERACCOUNT'].methods_by_name['GetAccountLinkStatus']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['GetAccountLinkStatus']._serialized_options = b'\202\265\030\033Fetches account link status'
  _globals['_USERACCOUNT'].methods_by_name['CancelLicenseForApp']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['CancelLicenseForApp']._serialized_options = b'\202\265\030!Cancels a free license for a user'
  _globals['_USERACCOUNT'].methods_by_name['GetUserCountry']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['GetUserCountry']._serialized_options = b'\202\265\030fGet the country code associated with the passed steamid (only available for logged-in user or support)'
  _globals['_USERACCOUNT'].methods_by_name['CreateFriendInviteToken']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['CreateFriendInviteToken']._serialized_options = b'\202\265\030ICreate a limited-use token that can be used to create a friend request_id'
  _globals['_USERACCOUNT'].methods_by_name['GetFriendInviteTokens']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['GetFriendInviteTokens']._serialized_options = b'\202\265\030)Get the set of active tokens for the user'
  _globals['_USERACCOUNT'].methods_by_name['ViewFriendInviteToken']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['ViewFriendInviteToken']._serialized_options = b'\202\265\030#View details about an invite token '
  _globals['_USERACCOUNT'].methods_by_name['RedeemFriendInviteToken']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['RedeemFriendInviteToken']._serialized_options = b'\202\265\0309Create a friend relationship using the given invite token'
  _globals['_USERACCOUNT'].methods_by_name['RevokeFriendInviteToken']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['RevokeFriendInviteToken']._serialized_options = b'\202\265\030$Revoke an active friend invite token'
  _globals['_USERACCOUNT'].methods_by_name['RegisterCompatTool']._loaded_options = None
  _globals['_USERACCOUNT'].methods_by_name['RegisterCompatTool']._serialized_options = b'\202\265\030)Register intended account usage of a tool'
  _globals['_ACCOUNTLINKING']._loaded_options = None
  _globals['_ACCOUNTLINKING']._serialized_options = b'\202\265\0301A service to manage and link to external accounts'
  _globals['_ACCOUNTLINKING'].methods_by_name['GetLinkedAccountInfo']._loaded_options = None
  _globals['_ACCOUNTLINKING'].methods_by_name['GetLinkedAccountInfo']._serialized_options = b'\202\265\030XList all my active linked external accounts; may be requested to return the access token'
  _globals['_EMBEDDEDCLIENT']._loaded_options = None
  _globals['_EMBEDDEDCLIENT']._serialized_options = b'\202\265\030JService to authorize and manage Steam functions directly embedded in games'
  _globals['_EMBEDDEDCLIENT'].methods_by_name['AuthorizeCurrentDevice']._loaded_options = None
  _globals['_EMBEDDEDCLIENT'].methods_by_name['AuthorizeCurrentDevice']._serialized_options = b'\202\265\030GUse a logged-in (password/etc) session to create a durable access token'
  _globals['_EINTERNALACCOUNTTYPE']._serialized_start=4130
  _globals['_EINTERNALACCOUNTTYPE']._serialized_end=4271
  _globals['_EEXTERNALACCOUNTTYPE']._serialized_start=4274
  _globals['_EEXTERNALACCOUNTTYPE']._serialized_end=4536
  _globals['_CUSERACCOUNT_GETAVAILABLEVALVEDISCOUNTPROMOTIONS_REQUEST']._serialized_start=95
  _globals['_CUSERACCOUNT_GETAVAILABLEVALVEDISCOUNTPROMOTIONS_REQUEST']._serialized_end=175
  _globals['_CUSERACCOUNT_GETAVAILABLEVALVEDISCOUNTPROMOTIONS_RESPONSE']._serialized_start=178
  _globals['_CUSERACCOUNT_GETAVAILABLEVALVEDISCOUNTPROMOTIONS_RESPONSE']._serialized_end=695
  _globals['_CUSERACCOUNT_GETAVAILABLEVALVEDISCOUNTPROMOTIONS_RESPONSE_VALVEDISCOUNTPROMOTIONDETAILS']._serialized_start=350
  _globals['_CUSERACCOUNT_GETAVAILABLEVALVEDISCOUNTPROMOTIONS_RESPONSE_VALVEDISCOUNTPROMOTIONDETAILS']._serialized_end=695
  _globals['_CUSERACCOUNT_GETCLIENTWALLETDETAILS_REQUEST']._serialized_start=698
  _globals['_CUSERACCOUNT_GETCLIENTWALLETDETAILS_REQUEST']._serialized_end=836
  _globals['_CUSERACCOUNT_GETWALLETDETAILS_RESPONSE']._serialized_start=839
  _globals['_CUSERACCOUNT_GETWALLETDETAILS_RESPONSE']._serialized_end=1242
  _globals['_CUSERACCOUNT_GETACCOUNTLINKSTATUS_REQUEST']._serialized_start=1244
  _globals['_CUSERACCOUNT_GETACCOUNTLINKSTATUS_REQUEST']._serialized_end=1287
  _globals['_CUSERACCOUNT_GETACCOUNTLINKSTATUS_RESPONSE']._serialized_start=1289
  _globals['_CUSERACCOUNT_GETACCOUNTLINKSTATUS_RESPONSE']._serialized_end=1414
  _globals['_CUSERACCOUNT_CANCELLICENSEFORAPP_REQUEST']._serialized_start=1416
  _globals['_CUSERACCOUNT_CANCELLICENSEFORAPP_REQUEST']._serialized_end=1473
  _globals['_CUSERACCOUNT_CANCELLICENSEFORAPP_RESPONSE']._serialized_start=1475
  _globals['_CUSERACCOUNT_CANCELLICENSEFORAPP_RESPONSE']._serialized_end=1518
  _globals['_CUSERACCOUNT_GETUSERCOUNTRY_REQUEST']._serialized_start=1520
  _globals['_CUSERACCOUNT_GETUSERCOUNTRY_REQUEST']._serialized_end=1574
  _globals['_CUSERACCOUNT_GETUSERCOUNTRY_RESPONSE']._serialized_start=1576
  _globals['_CUSERACCOUNT_GETUSERCOUNTRY_RESPONSE']._serialized_end=1631
  _globals['_CUSERACCOUNT_CREATEFRIENDINVITETOKEN_REQUEST']._serialized_start=1633
  _globals['_CUSERACCOUNT_CREATEFRIENDINVITETOKEN_REQUEST']._serialized_end=1747
  _globals['_CUSERACCOUNT_CREATEFRIENDINVITETOKEN_RESPONSE']._serialized_start=1750
  _globals['_CUSERACCOUNT_CREATEFRIENDINVITETOKEN_RESPONSE']._serialized_end=1903
  _globals['_CUSERACCOUNT_GETFRIENDINVITETOKENS_REQUEST']._serialized_start=1905
  _globals['_CUSERACCOUNT_GETFRIENDINVITETOKENS_REQUEST']._serialized_end=1949
  _globals['_CUSERACCOUNT_GETFRIENDINVITETOKENS_RESPONSE']._serialized_start=1951
  _globals['_CUSERACCOUNT_GETFRIENDINVITETOKENS_RESPONSE']._serialized_end=2060
  _globals['_CUSERACCOUNT_VIEWFRIENDINVITETOKEN_REQUEST']._serialized_start=2062
  _globals['_CUSERACCOUNT_VIEWFRIENDINVITETOKEN_REQUEST']._serialized_end=2145
  _globals['_CUSERACCOUNT_VIEWFRIENDINVITETOKEN_RESPONSE']._serialized_start=2147
  _globals['_CUSERACCOUNT_VIEWFRIENDINVITETOKEN_RESPONSE']._serialized_end=2249
  _globals['_CUSERACCOUNT_REDEEMFRIENDINVITETOKEN_REQUEST']._serialized_start=2251
  _globals['_CUSERACCOUNT_REDEEMFRIENDINVITETOKEN_REQUEST']._serialized_end=2336
  _globals['_CUSERACCOUNT_REDEEMFRIENDINVITETOKEN_RESPONSE']._serialized_start=2338
  _globals['_CUSERACCOUNT_REDEEMFRIENDINVITETOKEN_RESPONSE']._serialized_end=2385
  _globals['_CUSERACCOUNT_REVOKEFRIENDINVITETOKEN_REQUEST']._serialized_start=2387
  _globals['_CUSERACCOUNT_REVOKEFRIENDINVITETOKEN_REQUEST']._serialized_end=2455
  _globals['_CUSERACCOUNT_REVOKEFRIENDINVITETOKEN_RESPONSE']._serialized_start=2457
  _globals['_CUSERACCOUNT_REVOKEFRIENDINVITETOKEN_RESPONSE']._serialized_end=2504
  _globals['_CUSERACCOUNT_REGISTERCOMPATTOOL_REQUEST']._serialized_start=2506
  _globals['_CUSERACCOUNT_REGISTERCOMPATTOOL_REQUEST']._serialized_end=2568
  _globals['_CUSERACCOUNT_REGISTERCOMPATTOOL_RESPONSE']._serialized_start=2570
  _globals['_CUSERACCOUNT_REGISTERCOMPATTOOL_RESPONSE']._serialized_end=2612
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST']._serialized_start=2615
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_REQUEST']._serialized_end=3027
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE']._serialized_start=3030
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE']._serialized_end=3809
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE']._serialized_start=3186
  _globals['_CACCOUNTLINKING_GETLINKEDACCOUNTINFO_RESPONSE_CEXTERNALACCOUNTTUPLE_RESPONSE']._serialized_end=3809
  _globals['_CEMBEDDEDCLIENT_AUTHORIZECURRENTDEVICE_REQUEST']._serialized_start=3811
  _globals['_CEMBEDDEDCLIENT_AUTHORIZECURRENTDEVICE_REQUEST']._serialized_end=3930
  _globals['_CEMBEDDEDCLIENT_TOKEN']._serialized_start=3932
  _globals['_CEMBEDDEDCLIENT_TOKEN']._serialized_end=4028
  _globals['_CEMBEDDEDCLIENT_AUTHORIZEDEVICE_RESPONSE']._serialized_start=4030
  _globals['_CEMBEDDEDCLIENT_AUTHORIZEDEVICE_RESPONSE']._serialized_end=4127
  _globals['_USERACCOUNT']._serialized_start=4539
  _globals['_USERACCOUNT']._serialized_end=6527
  _globals['_ACCOUNTLINKING']._serialized_start=6530
  _globals['_ACCOUNTLINKING']._serialized_end=6815
  _globals['_EMBEDDEDCLIENT']._serialized_start=6818
  _globals['_EMBEDDEDCLIENT']._serialized_end=7110
_builder.BuildServices(DESCRIPTOR, 'steammessages_useraccount_pb2', _globals)
# @@protoc_insertion_point(module_scope)
