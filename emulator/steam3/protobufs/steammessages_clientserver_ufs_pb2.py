# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_clientserver_ufs.proto
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
    'steammessages_clientserver_ufs.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steam3.protobufs import steammessages_base_pb2 as steammessages__base__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n$steammessages_clientserver_ufs.proto\x1a\x18steammessages_base.proto\"\x86\x02\n\x1e\x43MsgClientUFSUploadFileRequest\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x11\n\tfile_size\x18\x02 \x01(\r\x12\x15\n\rraw_file_size\x18\x03 \x01(\r\x12\x10\n\x08sha_file\x18\x04 \x01(\x0c\x12\x12\n\ntime_stamp\x18\x05 \x01(\x04\x12\x11\n\tfile_name\x18\x06 \x01(\t\x12$\n\x1cplatforms_to_sync_deprecated\x18\x07 \x01(\r\x12%\n\x11platforms_to_sync\x18\x08 \x01(\r:\n4294967295\x12\x0f\n\x07\x63\x65ll_id\x18\t \x01(\r\x12\x13\n\x0b\x63\x61n_encrypt\x18\n \x01(\x08\"\xbb\x01\n\x1f\x43MsgClientUFSUploadFileResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x10\n\x08sha_file\x18\x02 \x01(\x0c\x12\x10\n\x08use_http\x18\x03 \x01(\x08\x12\x11\n\thttp_host\x18\x04 \x01(\t\x12\x10\n\x08http_url\x18\x05 \x01(\t\x12\x12\n\nkv_headers\x18\x06 \x01(\x0c\x12\x11\n\tuse_https\x18\x07 \x01(\x08\x12\x14\n\x0c\x65ncrypt_file\x18\x08 \x01(\x08\"\xae\x01\n\x19\x43MsgClientUFSUploadCommit\x12.\n\x05\x66iles\x18\x01 \x03(\x0b\x32\x1f.CMsgClientUFSUploadCommit.File\x1a\x61\n\x04\x46ile\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x0e\n\x06\x61pp_id\x18\x02 \x01(\r\x12\x10\n\x08sha_file\x18\x03 \x01(\x0c\x12\x10\n\x08\x63ub_file\x18\x04 \x01(\r\x12\x11\n\tfile_name\x18\x05 \x01(\t\"\x99\x01\n!CMsgClientUFSUploadCommitResponse\x12\x36\n\x05\x66iles\x18\x01 \x03(\x0b\x32\'.CMsgClientUFSUploadCommitResponse.File\x1a<\n\x04\x46ile\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x0e\n\x06\x61pp_id\x18\x02 \x01(\r\x12\x10\n\x08sha_file\x18\x03 \x01(\x0c\"L\n\x16\x43MsgClientUFSFileChunk\x12\x10\n\x08sha_file\x18\x01 \x01(\x0c\x12\x12\n\nfile_start\x18\x02 \x01(\r\x12\x0c\n\x04\x64\x61ta\x18\x03 \x01(\x0c\" \n\x1e\x43MsgClientUFSTransferHeartbeat\"G\n\x1f\x43MsgClientUFSUploadFileFinished\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x10\n\x08sha_file\x18\x02 \x01(\x0c\"_\n\x1e\x43MsgClientUFSDeleteFileRequest\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x11\n\tfile_name\x18\x02 \x01(\t\x12\x1a\n\x12is_explicit_delete\x18\x03 \x01(\x08\"H\n\x1f\x43MsgClientUFSDeleteFileResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x11\n\tfile_name\x18\x02 \x01(\t\"S\n\x1e\x43MsgClientUFSGetFileListForApp\x12\x15\n\rapps_to_query\x18\x01 \x03(\r\x12\x1a\n\x12send_path_prefixes\x18\x02 \x01(\x08\"\xc1\x02\n&CMsgClientUFSGetFileListForAppResponse\x12;\n\x05\x66iles\x18\x01 \x03(\x0b\x32,.CMsgClientUFSGetFileListForAppResponse.File\x12\x15\n\rpath_prefixes\x18\x02 \x03(\t\x1a\xb8\x01\n\x04\x46ile\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x11\n\tfile_name\x18\x02 \x01(\t\x12\x10\n\x08sha_file\x18\x03 \x01(\x0c\x12\x12\n\ntime_stamp\x18\x04 \x01(\x04\x12\x15\n\rraw_file_size\x18\x05 \x01(\r\x12\x1a\n\x12is_explicit_delete\x18\x06 \x01(\x08\x12\x19\n\x11platforms_to_sync\x18\x07 \x01(\r\x12\x19\n\x11path_prefix_index\x18\x08 \x01(\r:\x08\x80\xb5\x18\x08\x88\xb5\x18\x10\"Z\n\x1c\x43MsgClientUFSDownloadRequest\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x11\n\tfile_name\x18\x02 \x01(\t\x12\x17\n\x0f\x63\x61n_handle_http\x18\x03 \x01(\x08\"\xa0\x02\n\x1d\x43MsgClientUFSDownloadResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x0e\n\x06\x61pp_id\x18\x02 \x01(\r\x12\x11\n\tfile_size\x18\x03 \x01(\r\x12\x15\n\rraw_file_size\x18\x04 \x01(\r\x12\x10\n\x08sha_file\x18\x05 \x01(\x0c\x12\x12\n\ntime_stamp\x18\x06 \x01(\x04\x12\x1a\n\x12is_explicit_delete\x18\x07 \x01(\x08\x12\x10\n\x08use_http\x18\x08 \x01(\x08\x12\x11\n\thttp_host\x18\t \x01(\t\x12\x10\n\x08http_url\x18\n \x01(\t\x12\x12\n\nkv_headers\x18\x0b \x01(\x0c\x12\x11\n\tuse_https\x18\x0c \x01(\x08\x12\x11\n\tencrypted\x18\r \x01(\x08\"]\n\x19\x43MsgClientUFSLoginRequest\x12\x18\n\x10protocol_version\x18\x01 \x01(\r\x12\x18\n\x10\x61m_session_token\x18\x02 \x01(\x04\x12\x0c\n\x04\x61pps\x18\x03 \x03(\r\"0\n\x1a\x43MsgClientUFSLoginResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\"D\n\x1a\x43MsgClientUFSGetUGCDetails\x12&\n\x08hcontent\x18\x01 \x01(\x06:\x14\x31\x38\x34\x34\x36\x37\x34\x34\x30\x37\x33\x37\x30\x39\x35\x35\x31\x36\x31\x35\"\xe5\x01\n\"CMsgClientUFSGetUGCDetailsResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x0b\n\x03url\x18\x02 \x01(\t\x12\x0e\n\x06\x61pp_id\x18\x03 \x01(\r\x12\x10\n\x08\x66ilename\x18\x04 \x01(\t\x12\x17\n\x0fsteamid_creator\x18\x05 \x01(\x06\x12\x11\n\tfile_size\x18\x06 \x01(\r\x12\x1c\n\x14\x63ompressed_file_size\x18\x07 \x01(\r\x12\x17\n\x0frangecheck_host\x18\x08 \x01(\t\x12\x19\n\x11\x66ile_encoded_sha1\x18\t \x01(\t\"C\n\x1e\x43MsgClientUFSGetSingleFileInfo\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x11\n\tfile_name\x18\x02 \x01(\t\"\xb8\x01\n&CMsgClientUFSGetSingleFileInfoResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12\x0e\n\x06\x61pp_id\x18\x02 \x01(\r\x12\x11\n\tfile_name\x18\x03 \x01(\t\x12\x10\n\x08sha_file\x18\x04 \x01(\x0c\x12\x12\n\ntime_stamp\x18\x05 \x01(\x04\x12\x15\n\rraw_file_size\x18\x06 \x01(\r\x12\x1a\n\x12is_explicit_delete\x18\x07 \x01(\x08\";\n\x16\x43MsgClientUFSShareFile\x12\x0e\n\x06\x61pp_id\x18\x01 \x01(\r\x12\x11\n\tfile_name\x18\x02 \x01(\t\"\\\n\x1e\x43MsgClientUFSShareFileResponse\x12\x12\n\x07\x65result\x18\x01 \x01(\x05:\x01\x32\x12&\n\x08hcontent\x18\x02 \x01(\x06:\x14\x31\x38\x34\x34\x36\x37\x34\x34\x30\x37\x33\x37\x30\x39\x35\x35\x31\x36\x31\x35\x42\x05H\x01\x90\x01\x00')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_clientserver_ufs_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'H\001\220\001\000'
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPPRESPONSE']._loaded_options = None
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPPRESPONSE']._serialized_options = b'\200\265\030\010\210\265\030\020'
  _globals['_CMSGCLIENTUFSUPLOADFILEREQUEST']._serialized_start=67
  _globals['_CMSGCLIENTUFSUPLOADFILEREQUEST']._serialized_end=329
  _globals['_CMSGCLIENTUFSUPLOADFILERESPONSE']._serialized_start=332
  _globals['_CMSGCLIENTUFSUPLOADFILERESPONSE']._serialized_end=519
  _globals['_CMSGCLIENTUFSUPLOADCOMMIT']._serialized_start=522
  _globals['_CMSGCLIENTUFSUPLOADCOMMIT']._serialized_end=696
  _globals['_CMSGCLIENTUFSUPLOADCOMMIT_FILE']._serialized_start=599
  _globals['_CMSGCLIENTUFSUPLOADCOMMIT_FILE']._serialized_end=696
  _globals['_CMSGCLIENTUFSUPLOADCOMMITRESPONSE']._serialized_start=699
  _globals['_CMSGCLIENTUFSUPLOADCOMMITRESPONSE']._serialized_end=852
  _globals['_CMSGCLIENTUFSUPLOADCOMMITRESPONSE_FILE']._serialized_start=599
  _globals['_CMSGCLIENTUFSUPLOADCOMMITRESPONSE_FILE']._serialized_end=659
  _globals['_CMSGCLIENTUFSFILECHUNK']._serialized_start=854
  _globals['_CMSGCLIENTUFSFILECHUNK']._serialized_end=930
  _globals['_CMSGCLIENTUFSTRANSFERHEARTBEAT']._serialized_start=932
  _globals['_CMSGCLIENTUFSTRANSFERHEARTBEAT']._serialized_end=964
  _globals['_CMSGCLIENTUFSUPLOADFILEFINISHED']._serialized_start=966
  _globals['_CMSGCLIENTUFSUPLOADFILEFINISHED']._serialized_end=1037
  _globals['_CMSGCLIENTUFSDELETEFILEREQUEST']._serialized_start=1039
  _globals['_CMSGCLIENTUFSDELETEFILEREQUEST']._serialized_end=1134
  _globals['_CMSGCLIENTUFSDELETEFILERESPONSE']._serialized_start=1136
  _globals['_CMSGCLIENTUFSDELETEFILERESPONSE']._serialized_end=1208
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPP']._serialized_start=1210
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPP']._serialized_end=1293
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPPRESPONSE']._serialized_start=1296
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPPRESPONSE']._serialized_end=1617
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPPRESPONSE_FILE']._serialized_start=1423
  _globals['_CMSGCLIENTUFSGETFILELISTFORAPPRESPONSE_FILE']._serialized_end=1607
  _globals['_CMSGCLIENTUFSDOWNLOADREQUEST']._serialized_start=1619
  _globals['_CMSGCLIENTUFSDOWNLOADREQUEST']._serialized_end=1709
  _globals['_CMSGCLIENTUFSDOWNLOADRESPONSE']._serialized_start=1712
  _globals['_CMSGCLIENTUFSDOWNLOADRESPONSE']._serialized_end=2000
  _globals['_CMSGCLIENTUFSLOGINREQUEST']._serialized_start=2002
  _globals['_CMSGCLIENTUFSLOGINREQUEST']._serialized_end=2095
  _globals['_CMSGCLIENTUFSLOGINRESPONSE']._serialized_start=2097
  _globals['_CMSGCLIENTUFSLOGINRESPONSE']._serialized_end=2145
  _globals['_CMSGCLIENTUFSGETUGCDETAILS']._serialized_start=2147
  _globals['_CMSGCLIENTUFSGETUGCDETAILS']._serialized_end=2215
  _globals['_CMSGCLIENTUFSGETUGCDETAILSRESPONSE']._serialized_start=2218
  _globals['_CMSGCLIENTUFSGETUGCDETAILSRESPONSE']._serialized_end=2447
  _globals['_CMSGCLIENTUFSGETSINGLEFILEINFO']._serialized_start=2449
  _globals['_CMSGCLIENTUFSGETSINGLEFILEINFO']._serialized_end=2516
  _globals['_CMSGCLIENTUFSGETSINGLEFILEINFORESPONSE']._serialized_start=2519
  _globals['_CMSGCLIENTUFSGETSINGLEFILEINFORESPONSE']._serialized_end=2703
  _globals['_CMSGCLIENTUFSSHAREFILE']._serialized_start=2705
  _globals['_CMSGCLIENTUFSSHAREFILE']._serialized_end=2764
  _globals['_CMSGCLIENTUFSSHAREFILERESPONSE']._serialized_start=2766
  _globals['_CMSGCLIENTUFSSHAREFILERESPONSE']._serialized_end=2858
# @@protoc_insertion_point(module_scope)
