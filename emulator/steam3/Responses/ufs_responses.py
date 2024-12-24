from steam3.messages.MsgClientUFSGetFileListForApp import MsgClientUFSGetFileListForAppResponse
from steam3.Types.remotefile import RemoteFile
from steam3.Managers.cloudstoragemanager import CloudStorageManager


def build_UFSGetFileListForApp_response(client_obj, account_id, app_id, protobuf=False):
    cloud_manager = CloudStorageManager("files/webroot/cloud")
    files_metadata = cloud_manager.list_files(account_id, app_id)

    response = MsgClientUFSGetFileListForAppResponse(client_obj)
    for file_metadata in files_metadata:
        response.files.append(RemoteFile(
            app_id=file_metadata["app_id"],
            name=file_metadata["file_name"],
            sha=file_metadata["sha_file"],
            time=file_metadata["time_stamp"],
            size=file_metadata["raw_file_size"]
        ))

    # Serialize based on format
    if protobuf:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()