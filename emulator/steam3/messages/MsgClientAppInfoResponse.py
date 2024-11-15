import struct
import os
import io

from steam3.Types.appinfo import AppInfoParser


class MsgClientAppInfoResponse:
    def __init__(self, app_ids):
        self.app_ids = app_ids
        self.app_infos = []
        self.load_app_infos()

    def load_app_infos(self):
        for app_id in self.app_ids:
            file_path = f"files/appcache/vdf/app_{app_id}.vdf"
            if os.path.exists(file_path):
                parser = AppInfoParser(file_path)
                app_data = parser.get_application_by_id(app_id)
                if app_data:
                    self.app_infos.append(app_data)
                else:
                    print(f"App ID {app_id} not found in {file_path}")
            else:
                print(f"File {file_path} does not exist")

    # the following is for 2010+ i believe, 2008 just has appinfoes one after another with a null byte between
    def serialize(self, out_stream):
        # Write the number of appInfos
        out_stream.write(struct.pack('<I', len(self.app_infos)))
        print(len(self.app_infos))
        # Iterate through each ApplicationData in self.app_infos
        for app_data in self.app_infos:
            # Write appId and changeNumber
            out_stream.write(struct.pack('<I', app_data.app_id))
            # FIXME this is only for single appinfo.vdf files
            out_stream.write(struct.pack('<I', app_data.change_number or 1))

            # Serialize sections
            sections_raw = app_data.sections_raw
            # Sort the section keys by section ID
            sorted_sections = sorted(
                sections_raw.items(),
                key=lambda x: self.get_section_id(x[0])
            )

            for section_name, raw_bytes in sorted_sections:
                # FIXME these are already part of the raw byte output from the appinfoparser class
                # Write section type as a byte
                # section_id = self.get_section_id(section_name)
                # out_stream.write(struct.pack('B', section_id))

                # Write the raw bytes of the section
                out_stream.write(raw_bytes)

            # Write the end of sections marker
            out_stream.write(b'\x00')

    def get_section_id(self, section_name):
        section_ids = {
            "All": 1,
            "Common": 2,
            "Extended": 3,
            "Config": 4,
            "Stats": 5,
            "Install": 6,
            "Depots": 7,
            "VAC": 8,
            "DRM": 9,
            "UFS": 10,
            "OGG": 11,
            "Items": 12,
            "Policies": 13,
            "SystemRequirements": 14,
            "Community": 15,
        }
        return section_ids.get(section_name, 0)