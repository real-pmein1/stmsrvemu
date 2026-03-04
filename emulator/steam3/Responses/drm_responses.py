from steam3.messages.responses.MsgClientDRMDownload_Response import MsgClientDRMDownloadResponse
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


def build_DRMDownload_response(client_obj, eresult, app_id, blob_type,
                               merge_guid: bytes, ip: int, port: int, url: str,
                               module_path: str = ""):
    msg = MsgClientDRMDownloadResponse(client_obj)
    msg.result = eresult
    msg.app_id = app_id
    msg.blob_download_type = blob_type
    msg.merge_guid = merge_guid[:16].ljust(16, b"\x00")
    msg.file.ip_dfs = ip
    msg.file.port_dfs = port
    msg.file.url = url
    # module_path is ignored by our simplified class
    return msg.to_clientmsg()
