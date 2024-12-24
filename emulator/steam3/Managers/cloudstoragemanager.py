import os
import hashlib
import shutil
from typing import List, Dict
from steam3.Types.remotefile import RemoteFile


class CloudStorageManager:
    def __init__(self, cloud_root: str):
        self.cloud_root = cloud_root

    def _format_hexa(self, steam_global_id: int) -> str:
        return f"{steam_global_id:016x}"

    def _get_app_folder(self, steam_global_id: int, app_id: int) -> str:
        return os.path.join(self.cloud_root, self._format_hexa(steam_global_id), str(app_id))

    def _get_file_path(self, steam_global_id: int, app_id: int, filename: str) -> str:
        return os.path.join(self._get_app_folder(steam_global_id, app_id), filename.lstrip("./"))

    def _calculate_sha1(self, file_path: str) -> bytes:
        sha1 = hashlib.sha1()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        return sha1.digest()

    def list_files(self, steam_global_id: int, app_id: int):
        app_folder = self._get_app_folder(steam_global_id, app_id)
        if not os.path.exists(app_folder):
            os.makedirs(app_folder)
            return []

        files = []
        for root, _, filenames in os.walk(app_folder):
            for file in filenames:
                file_path = os.path.join(root, file)
                relative_path = f"./{os.path.relpath(file_path, app_folder).replace(os.sep, '/')}"
                files.append({
                    "app_id": app_id,
                    "file_name": relative_path,
                    "sha_file": self._calculate_sha1(file_path),
                    "time_stamp": int(os.path.getmtime(file_path)),
                    "raw_file_size": os.path.getsize(file_path),
                })
        return files

    def upload_file(self, steam_global_id: int, app_id: int, local_file_path: str, target_filename: str):
        target_path = self._get_file_path(steam_global_id, app_id, target_filename)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy(local_file_path, target_path)

    def download_file(self, steam_global_id: int, app_id: int, filename: str, local_destination: str):
        source_path = self._get_file_path(steam_global_id, app_id, filename)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"File {filename} does not exist.")
        shutil.copy(source_path, local_destination)

    def delete_file(self, steam_global_id: int, app_id: int, filename: str):
        file_path = self._get_file_path(steam_global_id, app_id, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            raise FileNotFoundError(f"File {filename} does not exist.")