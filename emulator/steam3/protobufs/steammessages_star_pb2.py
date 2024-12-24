# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: steammessages_star.proto
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
    'steammessages_star.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steam3.protobufs import steammessages_base_pb2 as steammessages__base__pb2
from steam3.protobufs import steammessages_unified_base_pb2 as steammessages__unified__base__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x18steammessages_star.proto\x1a\x18steammessages_base.proto\x1a steammessages_unified_base.proto\"\xc6\x01\n\x13\x43STAR_KeyValueQuery\x12\x43\n\x03key\x18\x01 \x01(\tB6\x82\xb5\x18\x32key to search for in JSON path format (SQL subset)\x12j\n\x05value\x18\x02 \x01(\tB[\x82\xb5\x18Wthe value to compare against (the JSON value will be compared for equality as a string)\"\xcb\x01\n\x16\x43STAR_GlyphQueryParams\x12s\n\tbundle_id\x18\x01 \x01(\x04\x42`\x82\xb5\x18\\if provided, Bundle ID is used instead of the other query parameters (much faster SQL query)\x12<\n\x07queries\x18\x02 \x03(\x0b\x32\x14.CSTAR_KeyValueQueryB\x15\x82\xb5\x18\x11key value queries\"\x94\x02\n\x1b\x43STAR_ReadGlyphData_Request\x12\x65\n\x0cquery_params\x18\x01 \x01(\x0b\x32\x17.CSTAR_GlyphQueryParamsB6\x82\xb5\x18\x32parameters to identify the glyphs to read from SQL\x12\x8d\x01\n\x1elast_modified_time_lower_limit\x18\x02 \x01(\tBe\x82\xb5\x18\x61if provided, only return glyphs modified more recently than this timestamp  (RFC 3339 UTC format)\"\xef\x01\n\x0f\x43STAR_GlyphData\x12<\n\nglyph_guid\x18\x01 \x01(\x0c\x42(\x82\xb5\x18$GUID uniquely identifying this glyph\x12\x65\n\x13glyph_last_modified\x18\x02 \x01(\tBH\x82\xb5\x18\x44timestamp of when this glyph was last modified (RFC 3339 UTC format)\x12\x37\n\x0fglyph_json_data\x18\x03 \x01(\tB\x1e\x82\xb5\x18\x1aJSON encoded glyph message\"\xb7\x01\n\x1c\x43STAR_WriteGlyphData_Request\x12@\n\tbundle_id\x18\x01 \x01(\x04\x42-\x82\xb5\x18)the Bundle ID of the glyphs to be written\x12U\n\nglyph_data\x18\x02 \x03(\x0b\x32\x10.CSTAR_GlyphDataB/\x82\xb5\x18+one or more items of glyph message to write\"\x7f\n\rCSTAR_Request\x12\x35\n\x0fread_glyph_data\x18\x01 \x01(\x0b\x32\x1c.CSTAR_ReadGlyphData_Request\x12\x37\n\x10write_glyph_data\x18\x02 \x01(\x0b\x32\x1d.CSTAR_WriteGlyphData_Request\"\xf4\x01\n\x1c\x43STAR_ReadGlyphData_Response\x12|\n\tbundle_id\x18\x01 \x01(\x04\x42i\x82\xb5\x18\x65the Bundle ID of the returned glyphs; the client should send this back to optimize subsequent queries\x12V\n\nglyph_data\x18\x02 \x03(\x0b\x32\x10.CSTAR_GlyphDataB0\x82\xb5\x18,zero or more items of returned glyph message\"z\n\x1d\x43STAR_WriteGlyphData_Response\x12Y\n\x06result\x18\x01 \x03(\x0e\x32\x18.E_STAR_GlyphWriteResultB/\x82\xb5\x18+write result for each item of glyph message\"\x82\x01\n\x0e\x43STAR_Response\x12\x36\n\x0fread_glyph_data\x18\x01 \x01(\x0b\x32\x1d.CSTAR_ReadGlyphData_Response\x12\x38\n\x10write_glyph_data\x18\x02 \x01(\x0b\x32\x1e.CSTAR_WriteGlyphData_Response*\xc1\x01\n\x17\x45_STAR_GlyphWriteResult\x12%\n!k_E_STAR_GlyphWriteResult_Success\x10\x00\x12,\n(k_E_STAR_GlyphWriteResult_InvalidMessage\x10\x01\x12)\n%k_E_STAR_GlyphWriteResult_InvalidJSON\x10\x02\x12&\n\"k_E_STAR_GlyphWriteResult_SQLError\x10\x03\x32\x88\x01\n\x04STAR\x12R\n\x0eProcessMessage\x12\x0e.CSTAR_Request\x1a\x0f.CSTAR_Response\"\x1f\x82\xb5\x18\x1bprocesses a generic message\x1a,\x82\xb5\x18(service for reading/writing STAR messageB\x03\x90\x01\x01')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steammessages_star_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'\220\001\001'
  _globals['_CSTAR_KEYVALUEQUERY'].fields_by_name['key']._loaded_options = None
  _globals['_CSTAR_KEYVALUEQUERY'].fields_by_name['key']._serialized_options = b'\202\265\0302key to search for in JSON path format (SQL subset)'
  _globals['_CSTAR_KEYVALUEQUERY'].fields_by_name['value']._loaded_options = None
  _globals['_CSTAR_KEYVALUEQUERY'].fields_by_name['value']._serialized_options = b'\202\265\030Wthe value to compare against (the JSON value will be compared for equality as a string)'
  _globals['_CSTAR_GLYPHQUERYPARAMS'].fields_by_name['bundle_id']._loaded_options = None
  _globals['_CSTAR_GLYPHQUERYPARAMS'].fields_by_name['bundle_id']._serialized_options = b'\202\265\030\\if provided, Bundle ID is used instead of the other query parameters (much faster SQL query)'
  _globals['_CSTAR_GLYPHQUERYPARAMS'].fields_by_name['queries']._loaded_options = None
  _globals['_CSTAR_GLYPHQUERYPARAMS'].fields_by_name['queries']._serialized_options = b'\202\265\030\021key value queries'
  _globals['_CSTAR_READGLYPHDATA_REQUEST'].fields_by_name['query_params']._loaded_options = None
  _globals['_CSTAR_READGLYPHDATA_REQUEST'].fields_by_name['query_params']._serialized_options = b'\202\265\0302parameters to identify the glyphs to read from SQL'
  _globals['_CSTAR_READGLYPHDATA_REQUEST'].fields_by_name['last_modified_time_lower_limit']._loaded_options = None
  _globals['_CSTAR_READGLYPHDATA_REQUEST'].fields_by_name['last_modified_time_lower_limit']._serialized_options = b'\202\265\030aif provided, only return glyphs modified more recently than this timestamp  (RFC 3339 UTC format)'
  _globals['_CSTAR_GLYPHDATA'].fields_by_name['glyph_guid']._loaded_options = None
  _globals['_CSTAR_GLYPHDATA'].fields_by_name['glyph_guid']._serialized_options = b'\202\265\030$GUID uniquely identifying this glyph'
  _globals['_CSTAR_GLYPHDATA'].fields_by_name['glyph_last_modified']._loaded_options = None
  _globals['_CSTAR_GLYPHDATA'].fields_by_name['glyph_last_modified']._serialized_options = b'\202\265\030Dtimestamp of when this glyph was last modified (RFC 3339 UTC format)'
  _globals['_CSTAR_GLYPHDATA'].fields_by_name['glyph_json_data']._loaded_options = None
  _globals['_CSTAR_GLYPHDATA'].fields_by_name['glyph_json_data']._serialized_options = b'\202\265\030\032JSON encoded glyph message'
  _globals['_CSTAR_WRITEGLYPHDATA_REQUEST'].fields_by_name['bundle_id']._loaded_options = None
  _globals['_CSTAR_WRITEGLYPHDATA_REQUEST'].fields_by_name['bundle_id']._serialized_options = b'\202\265\030)the Bundle ID of the glyphs to be written'
  _globals['_CSTAR_WRITEGLYPHDATA_REQUEST'].fields_by_name['glyph_data']._loaded_options = None
  _globals['_CSTAR_WRITEGLYPHDATA_REQUEST'].fields_by_name['glyph_data']._serialized_options = b'\202\265\030+one or more items of glyph message to write'
  _globals['_CSTAR_READGLYPHDATA_RESPONSE'].fields_by_name['bundle_id']._loaded_options = None
  _globals['_CSTAR_READGLYPHDATA_RESPONSE'].fields_by_name['bundle_id']._serialized_options = b'\202\265\030ethe Bundle ID of the returned glyphs; the client should send this back to optimize subsequent queries'
  _globals['_CSTAR_READGLYPHDATA_RESPONSE'].fields_by_name['glyph_data']._loaded_options = None
  _globals['_CSTAR_READGLYPHDATA_RESPONSE'].fields_by_name['glyph_data']._serialized_options = b'\202\265\030,zero or more items of returned glyph message'
  _globals['_CSTAR_WRITEGLYPHDATA_RESPONSE'].fields_by_name['result']._loaded_options = None
  _globals['_CSTAR_WRITEGLYPHDATA_RESPONSE'].fields_by_name['result']._serialized_options = b'\202\265\030+write result for each item of glyph message'
  _globals['_STAR']._loaded_options = None
  _globals['_STAR']._serialized_options = b'\202\265\030(service for reading/writing STAR message'
  _globals['_STAR'].methods_by_name['ProcessMessage']._loaded_options = None
  _globals['_STAR'].methods_by_name['ProcessMessage']._serialized_options = b'\202\265\030\033processes a generic message'
  _globals['_E_STAR_GLYPHWRITERESULT']._serialized_start=1836
  _globals['_E_STAR_GLYPHWRITERESULT']._serialized_end=2029
  _globals['_CSTAR_KEYVALUEQUERY']._serialized_start=89
  _globals['_CSTAR_KEYVALUEQUERY']._serialized_end=287
  _globals['_CSTAR_GLYPHQUERYPARAMS']._serialized_start=290
  _globals['_CSTAR_GLYPHQUERYPARAMS']._serialized_end=493
  _globals['_CSTAR_READGLYPHDATA_REQUEST']._serialized_start=496
  _globals['_CSTAR_READGLYPHDATA_REQUEST']._serialized_end=772
  _globals['_CSTAR_GLYPHDATA']._serialized_start=775
  _globals['_CSTAR_GLYPHDATA']._serialized_end=1014
  _globals['_CSTAR_WRITEGLYPHDATA_REQUEST']._serialized_start=1017
  _globals['_CSTAR_WRITEGLYPHDATA_REQUEST']._serialized_end=1200
  _globals['_CSTAR_REQUEST']._serialized_start=1202
  _globals['_CSTAR_REQUEST']._serialized_end=1329
  _globals['_CSTAR_READGLYPHDATA_RESPONSE']._serialized_start=1332
  _globals['_CSTAR_READGLYPHDATA_RESPONSE']._serialized_end=1576
  _globals['_CSTAR_WRITEGLYPHDATA_RESPONSE']._serialized_start=1578
  _globals['_CSTAR_WRITEGLYPHDATA_RESPONSE']._serialized_end=1700
  _globals['_CSTAR_RESPONSE']._serialized_start=1703
  _globals['_CSTAR_RESPONSE']._serialized_end=1833
  _globals['_STAR']._serialized_start=2032
  _globals['_STAR']._serialized_end=2168
_builder.BuildServices(DESCRIPTOR, 'steammessages_star_pb2', _globals)
# @@protoc_insertion_point(module_scope)
