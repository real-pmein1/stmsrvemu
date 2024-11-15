from typing import Any, Dict
from io import BytesIO

from steam3.Types.keyvaluesystem import KeyValuesSystem, RegistryKey


class WizardData:
    def __init__(self, byte_data: bytes = None):
        # Dictionary to store the parsed data
        self.data: Dict[str, Any] = {}
        if byte_data:
            self.parse(byte_data)

    def parse(self, byte_data: bytes):
        # Use the KeyValuesSystem to parse the byte_data
        kvs = KeyValuesSystem()
        input_stream = BytesIO(byte_data)
        kvs.deserialize(input_stream)

        # Convert the parsed data into a dictionary
        self.data = self._registry_key_to_dict(kvs.root)

    def _registry_key_to_dict(self, registry_key: RegistryKey) -> Dict[str, Any]:
        result = {}
        for element in registry_key.get_elements():
            if element.is_value():
                result[element.name] = element.value
            elif element.is_key():
                # Handle subkeys (if any)
                result[element.name] = self._registry_key_to_dict(element)
        return result

    def __str__(self):
        # String representation of the data
        return str(self.data)

    def __repr__(self):
        # Debugging representation of the object
        return f"WizardData(data={self.data})"

    def get_value(self, key: str) -> Any:
        # Get a value by its key
        return self.data.get(key, None)

    def set_value(self, key: str, value: Any):
        # Set a value for a given key
        self.data[key] = value

    # Getter and Setter methods for each field
    def get_net_speed(self) -> int:
        return self.get_value("NetSpeed")

    def set_net_speed(self, value: int):
        self.set_value("NetSpeed", value)

    def get_net_speed_label(self) -> str:
        return self.get_value("NetSpeedLabel")

    def set_net_speed_label(self, value: str):
        self.set_value("NetSpeedLabel", value)

    def get_microphone(self) -> int:
        return self.get_value("Microphone")

    def set_microphone(self, value: int):
        self.set_value("Microphone", value)

    def get_microphone_label(self) -> str:
        return self.get_value("MicrophoneLabel")

    def set_microphone_label(self, value: str):
        self.set_value("MicrophoneLabel", value)

    def get_cpu_vendor(self) -> str:
        return self.get_value("CPUVendor")

    def set_cpu_vendor(self, value: str):
        self.set_value("CPUVendor", value)

    def get_cpu_speed(self) -> int:
        return self.get_value("CPUSpeed")

    def set_cpu_speed(self, value: int):
        self.set_value("CPUSpeed", value)

    def get_logical_processors(self) -> int:
        return self.get_value("LogicalProcessors")

    def set_logical_processors(self, value: int):
        self.set_value("LogicalProcessors", value)

    def get_physical_processors(self) -> int:
        return self.get_value("PhysicalProcessors")

    def set_physical_processors(self, value: int):
        self.set_value("PhysicalProcessors", value)

    def get_hyper_threading(self) -> int:
        return self.get_value("HyperThreading")

    def set_hyper_threading(self, value: int):
        self.set_value("HyperThreading", value)

    def get_fcmov(self) -> int:
        return self.get_value("FCMOV")

    def set_fcmov(self, value: int):
        self.set_value("FCMOV", value)

    def get_sse2(self) -> int:
        return self.get_value("SSE2")

    def set_sse2(self, value: int):
        self.set_value("SSE2", value)

    def get_sse3(self) -> int:
        return self.get_value("SSE3")

    def set_sse3(self, value: int):
        self.set_value("SSE3", value)

    def get_sse4(self) -> int:
        return self.get_value("SSE4")

    def set_sse4(self, value: int):
        self.set_value("SSE4", value)

    def get_sse4a(self) -> int:
        return self.get_value("SSE4a")

    def set_sse4a(self, value: int):
        self.set_value("SSE4a", value)

    def get_sse41(self) -> int:
        return self.get_value("SSE41")

    def set_sse41(self, value: int):
        self.set_value("SSE41", value)

    def get_sse42(self) -> int:
        return self.get_value("SSE42")

    def set_sse42(self, value: int):
        self.set_value("SSE42", value)

    def get_os_version(self) -> str:
        return self.get_value("OSVersion")

    def set_os_version(self, value: str):
        self.set_value("OSVersion", value)

    def get_is_64bit_os(self) -> int:
        return self.get_value("Is64BitOS")

    def set_is_64bit_os(self, value: int):
        self.set_value("Is64BitOS", value)

    def get_os_type(self) -> int:
        return self.get_value("OSType")

    def set_os_type(self, value: int):
        self.set_value("OSType", value)

    def get_ntfs(self) -> int:
        return self.get_value("NTFS")

    def set_ntfs(self, value: int):
        self.set_value("NTFS", value)

    def get_adapter_description(self) -> str:
        return self.get_value("AdapterDescription")

    def set_adapter_description(self, value: str):
        self.set_value("AdapterDescription", value)

    def get_driver_version(self) -> str:
        return self.get_value("DriverVersion")

    def set_driver_version(self, value: str):
        self.set_value("DriverVersion", value)

    def get_driver_date(self) -> str:
        return self.get_value("DriverDate")

    def set_driver_date(self, value: str):
        self.set_value("DriverDate", value)

    def get_vram_size(self) -> int:
        return self.get_value("VRAMSize")

    def set_vram_size(self, value: int):
        self.set_value("VRAMSize", value)

    def get_bit_depth(self) -> int:
        return self.get_value("BitDepth")

    def set_bit_depth(self, value: int):
        self.set_value("BitDepth", value)

    def get_refresh_rate(self) -> int:
        return self.get_value("RefreshRate")

    def set_refresh_rate(self, value: int):
        self.set_value("RefreshRate", value)

    def get_num_monitors(self) -> int:
        return self.get_value("NumMonitors")

    def set_num_monitors(self, value: int):
        self.set_value("NumMonitors", value)

    def get_num_display_devices(self) -> int:
        return self.get_value("NumDisplayDevices")

    def set_num_display_devices(self, value: int):
        self.set_value("NumDisplayDevices", value)

    def get_monitor_width_in_pixels(self) -> int:
        return self.get_value("MonitorWidthInPixels")

    def set_monitor_width_in_pixels(self, value: int):
        self.set_value("MonitorWidthInPixels", value)

    def get_monitor_height_in_pixels(self) -> int:
        return self.get_value("MonitorHeightInPixels")

    def set_monitor_height_in_pixels(self, value: int):
        self.set_value("MonitorHeightInPixels", value)

    def get_desktop_width_in_pixels(self) -> int:
        return self.get_value("DesktopWidthInPixels")

    def set_desktop_width_in_pixels(self, value: int):
        self.set_value("DesktopWidthInPixels", value)

    def get_desktop_height_in_pixels(self) -> int:
        return self.get_value("DesktopHeightInPixels")

    def set_desktop_height_in_pixels(self, value: int):
        self.set_value("DesktopHeightInPixels", value)

    def get_monitor_width_in_millimeters(self) -> int:
        return self.get_value("MonitorWidthInMillimeters")

    def set_monitor_width_in_millimeters(self, value: int):
        self.set_value("MonitorWidthInMillimeters", value)

    def get_monitor_height_in_millimeters(self) -> int:
        return self.get_value("MonitorHeightInMillimeters")

    def set_monitor_height_in_millimeters(self, value: int):
        self.set_value("MonitorHeightInMillimeters", value)

    def get_monitor_diagonal_in_millimeters(self) -> int:
        return self.get_value("MonitorDiagonalInMillimeters")

    def set_monitor_diagonal_in_millimeters(self, value: int):
        self.set_value("MonitorDiagonalInMillimeters", value)

    def get_video_card(self) -> str:
        return self.get_value("VideoCard")

    def set_video_card(self, value: str):
        self.set_value("VideoCard", value)

    def get_dx_video_card_driver(self) -> str:
        return self.get_value("DXVideoCardDriver")

    def set_dx_video_card_driver(self, value: str):
        self.set_value("DXVideoCardDriver", value)

    def get_dx_video_card_version(self) -> str:
        return self.get_value("DXVideoCardVersion")

    def set_dx_video_card_version(self, value: str):
        self.set_value("DXVideoCardVersion", value)

    def get_dx_vendor_id(self) -> int:
        return self.get_value("DXVendorID")

    def set_dx_vendor_id(self, value: int):
        self.set_value("DXVendorID", value)

    def get_dx_device_id(self) -> int:
        return self.get_value("DXDeviceID")

    def set_dx_device_id(self, value: int):
        self.set_value("DXDeviceID", value)

    def get_msaa_modes(self) -> str:
        return self.get_value("MSAAModes")

    def set_msaa_modes(self, value: str):
        self.set_value("MSAAModes", value)

    def get_multi_gpu(self) -> int:
        return self.get_value("MultiGPU")

    def set_multi_gpu(self, value: int):
        self.set_value("MultiGPU", value)

    def get_num_sli_gpus(self) -> int:
        return self.get_value("NumSLIGPUs")

    def set_num_sli_gpus(self, value: int):
        self.set_value("NumSLIGPUs", value)

    def get_display_type(self) -> int:
        return self.get_value("DisplayType")

    def set_display_type(self, value: int):
        self.set_value("DisplayType", value)

    def get_bus_type(self) -> int:
        return self.get_value("BusType")

    def set_bus_type(self, value: int):
        self.set_value("BusType", value)

    def get_bus_rate(self) -> int:
        return self.get_value("BusRate")

    def set_bus_rate(self, value: int):
        self.set_value("BusRate", value)

    def get_dell_oem(self) -> int:
        return self.get_value("dell_oem")

    def set_dell_oem(self, value: int):
        self.set_value("dell_oem", value)

    def get_audio_device_description(self) -> str:
        return self.get_value("AudioDeviceDescription")

    def set_audio_device_description(self, value: str):
        self.set_value("AudioDeviceDescription", value)

    def get_ram(self) -> int:
        return self.get_value("RAM")

    def set_ram(self, value: int):
        self.set_value("RAM", value)

    def get_language_id(self) -> int:
        return self.get_value("LanguageId")

    def set_language_id(self, value: int):
        self.set_value("LanguageId", value)

    def get_drive_type(self) -> int:
        return self.get_value("DriveType")

    def set_drive_type(self, value: int):
        self.set_value("DriveType", value)

    def get_total_hd(self) -> int:
        return self.get_value("TotalHD")

    def set_total_hd(self, value: int):
        self.set_value("TotalHD", value)

    def get_free_hd(self) -> int:
        return self.get_value("FreeHD")

    def set_free_hd(self, value: int):
        self.set_value("FreeHD", value)

    def get_steam_hd_usage(self) -> int:
        return self.get_value("SteamHDUsage")

    def set_steam_hd_usage(self, value: int):
        self.set_value("SteamHDUsage", value)

    def get_os_install_date(self) -> str:
        return self.get_value("OSInstallDate")

    def set_os_install_date(self, value: str):
        self.set_value("OSInstallDate", value)

    def get_game_controller(self) -> str:
        return self.get_value("GameController")

    def set_game_controller(self, value: str):
        self.set_value("GameController", value)

    def get_non_steam_app_firefox(self) -> int:
        return self.get_value("NonSteamApp_firefox")

    def set_non_steam_app_firefox(self, value: int):
        self.set_value("NonSteamApp_firefox", value)

    def get_non_steam_app_openoffice(self) -> int:
        return self.get_value("NonSteamApp_openoffice")

    def set_non_steam_app_openoffice(self, value: int):
        self.set_value("NonSteamApp_openoffice", value)

    def get_non_steam_app_wfw(self) -> int:
        return self.get_value("NonSteamApp_wfw")

    def set_non_steam_app_wfw(self, value: int):
        self.set_value("NonSteamApp_wfw", value)

    def get_non_steam_app_za(self) -> int:
        return self.get_value("NonSteamApp_za")

    def set_non_steam_app_za(self, value: int):
        self.set_value("NonSteamApp_za", value)

    def get_non_steam_app_f4m(self) -> int:
        return self.get_value("NonSteamApp_f4m")

    def set_non_steam_app_f4m(self, value: int):
        self.set_value("NonSteamApp_f4m", value)

    def get_non_steam_app_cog(self) -> int:
        return self.get_value("NonSteamApp_cog")

    def set_non_steam_app_cog(self, value: int):
        self.set_value("NonSteamApp_cog", value)

    def get_non_steam_app_pd(self) -> int:
        return self.get_value("NonSteamApp_pd")

    def set_non_steam_app_pd(self, value: int):
        self.set_value("NonSteamApp_pd", value)

    def get_non_steam_app_vmf(self) -> int:
        return self.get_value("NonSteamApp_vmf")

    def set_non_steam_app_vmf(self, value: int):
        self.set_value("NonSteamApp_vmf", value)

    def get_non_steam_app_grl(self) -> int:
        return self.get_value("NonSteamApp_grl")

    def set_non_steam_app_grl(self, value: int):
        self.set_value("NonSteamApp_grl", value)

    def get_non_steam_app_fv(self) -> int:
        return self.get_value("NonSteamApp_fv")

    def set_non_steam_app_fv(self, value: int):
        self.set_value("NonSteamApp_fv", value)

    def get_machine_id(self) -> int:
        return self.get_value("machineid")

    def set_machine_id(self, value: int):
        self.set_value("machineid", value)

    def get_version(self) -> int:
        return self.get_value("version")

    def set_version(self, value: int):
        self.set_value("version", value)

    def get_country(self) -> int:
        return self.get_value("country")

    def set_country(self, value: int):
        self.set_value("country", value)

    def get_ownership(self) -> dict:
        return self.get_value("ownership")

    def set_ownership(self, value: dict):
        self.set_value("ownership", value)

    def __repr__(self):
        # Debugging representation of the object with key-value pairs
        return f"WizardData(data={self.data})"

    def __str__(self):
        # User-friendly string representation of the data
        return '\n'.join(f"{key}: {value}" for key, value in self.data.items())