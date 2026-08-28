# Copyright 2020-2025 NXP
"""TODO:summary line."""
import logging
import time
import traceback
from enum import Enum
from typing import Optional

import libusbsio
from spsdk.sdp.interfaces.usb import SdpUSBInterface
from spsdk.utils.database import DatabaseManager, SPSDKErrorMissingDevice

from ..utils.constants import Const
from .config_data import ConfigData
from .factories import SDPFactory, SDPSFactory


class UsbId:
    """Class for usb id."""

    # TODO: use USB_DEVICES list from spsdk usb.py once updated!
    USB_DEVICES = {
        "MIMX8M": (0x1FC9, 0x012B),
        "MIMX8MM": (0x1FC9, 0x0134),
        "MIMX8MN": (0x1FC9, 0x013E),
        "MIMX8MP": (0x1FC9, 0x0146),
        "MIMX91": (0x1FC9, 0x0159),
        "MIMX93": (0x1FC9, 0x014E),
        "MIMX943": (0x1FC9, 0x0027),
        "MIMX95": (0x1FC9, 0x015D),  # USB port 1 PID: 0x015D, USB port 2 PID: 0x015C
        "MIMX95_B0": (0x1FC9, 0x015D)
    }

    @staticmethod
    def get_usb_id(soc_name: str) -> Optional[str]:
        """Get usb id for given soc name.

        @param soc_name: Soc name for usb id.
        @return: Usb id for given soc name in format "vid:pid" or None if not found in USB_DEVICES map.
        """
        usb_id = UsbId.get_vid_pid(soc_name)
        if usb_id is None:
            return None
        (vid, pid) = usb_id
        return f'{vid}:{pid}'

    @staticmethod
    def get_vid_pid(soc_name: str) -> Optional[tuple]:
        """Get (vid, pid) tuple for given soc name.

        @param soc_name: Soc name for usb id.
        @return: (vid, pid) tuple for given soc name or None if not found in USB_DEVICES map.
        """
        if soc_name is None:
            return None

        usb_id = None
        if soc_name in ConfigData.DEVICES_INFO:
            try:
                spsdk_device_info = DatabaseManager().db.devices.get(ConfigData.DEVICES_INFO[soc_name].get_spsdk_id())
                usb_id = (spsdk_device_info.info.isp.rom.usb_id.vid, spsdk_device_info.info.isp.rom.usb_id.pid)
            except SPSDKErrorMissingDevice:
                usb_id = None
        if usb_id is None:
            if soc_name in UsbId.USB_DEVICES:
                usb_id = UsbId.USB_DEVICES[soc_name]
        return usb_id


class UsbDevScanOption(Enum):
    """Options for how to perform usb device scan."""
    SPSDK = 0  # Use spsdk usb scan.
    DEVICE_MANAGER = 1  # Use device manager scan.
    LIBUSBSIO = 2  # Use libusbsio scan.


class SDPInterface(SDPFactory):
    """Interface for implementing SDP communication channels."""

    logger = logging.getLogger(__name__)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Determine if the class can be instantiated.

        Each class tells the factory if it can handle the input
        """
        return False

    def load_bin(self, load_address: int, data=None, filename="Binary Image") -> bool:  # type: ignore
        """Load binary to specified address.

        @return: success?
        """
        pass

    def jump(self, jump_address: int) -> bool:  # type: ignore
        """Jump to specified address.

        @return: success?
        """
        pass

    def close(self):  # type: ignore
        """Free HID port."""
        pass


class SDPSInterface(SDPSFactory):
    """Interface for implementing SDPS communication channels."""

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Determine if the class can be instantiated.

        Each class tells the factory if it can handle the input
        """
        return False

    def open(self):  # type: ignore
        """Open USB HID device."""
        pass

    def close(self):  # type: ignore
        """Close USB HID device."""
        pass

    def load_bin(self, data, filename):  # type: ignore
        """Load image binary and boot.

        @param data: binary data
        @param filename: binary image, when data is None data from file is loaded
        """
        pass


class SDPUtils:
    """Helpers for SDP."""

    logger = logging.getLogger(__name__)

    IVT_HEADER_SIZE = 0xC0

    @staticmethod
    def build_ivt_hdr(load_addr: int, start: int, size: int) -> bytes:
        """Build IVT Header as byte array.

        @param load_addr: workspace address
        @param start: address of first instruction in image
        @param size: workspace size (or size of bin file + IVT header size)
        @return: IVT Header in little endian
                    ivt_header;
                    entry;
                    reserved1;
                    dcd_ptr;
                    boot_data_ptr;
                    self_ptr;
                    csf;
                    reserved2;
                    boot_data;
                    image_len;
                    plugin;
                    dcd_cmd[37];
        """
        # ivt_header
        tag = 0x412000D1
        ivt_hdr = tag.to_bytes(4, byteorder='little')

        # entry: Absolute address of the first instruction to execute from the image
        ivt_hdr += start.to_bytes(4, byteorder='little')

        # reserved1: Reserved and should be zero
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # dcd_ptr: Absolute address of the image DCD.
        # The DCD is optional so this field may be set to NULL if no DCD is required
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # boot_data_ptr: Absolute address of the boot data
        ivt_hdr += (start - SDPUtils.IVT_HEADER_SIZE + 0x20).to_bytes(4, byteorder='little')

        # self_ptr: Absolute address of the IVT. Used internally by the ROM.
        ivt_hdr += (start - SDPUtils.IVT_HEADER_SIZE).to_bytes(4, byteorder='little')

        # csf: Absolute address of the Command Sequence File (CSF) used by the HAB library.
        # See High-Assurance Boot (HAB) for
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # reserved2: Reserved and should be zero
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # boot_data: start
        ivt_hdr += (start - SDPUtils.IVT_HEADER_SIZE).to_bytes(4, byteorder='little')

        # boot_data: image_len
        ivt_hdr += (size + SDPUtils.IVT_HEADER_SIZE).to_bytes(4, byteorder='little')

        # boot_data: plugin flag
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # padding to IVT_HEADER_SIZE
        ivt_hdr += (0).to_bytes(SDPUtils.IVT_HEADER_SIZE - 44, byteorder='little')

        return ivt_hdr

    @staticmethod
    def scan_usb_devices(usb_id: str, count: int = 0) -> list:
        """Scan for USB device for SDP communication.

        @param usb_id: "VID:PID" string id.
        @param count: Number of times/timeout to retry scan.
        @return: List of USB devices.
        """
        def safe_sort_key(device):  # type: ignore
            """HID sort method."""
            if hasattr(device, 'device'):
                if hasattr(device.device, 'path_str') and device.device.path_str:
                    return device.device.path_str
            return str(device)

        devices = []
        try:
            # reduce SDPS log - set log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            start = time.time()
            crt_iteration = count

            while True:
                devices = SdpUSBInterface.scan(usb_id, Const.USB_DEVICE_TIMEOUT)
                devices.sort(key=safe_sort_key)
                if devices is not None and len(devices) > 0:
                    break

                if crt_iteration > 0:
                    SDPUtils.logger.info("Retry USB scan")
                    time.sleep(1)
                    crt_iteration -= 1
                else:
                    break

            end = time.time()
            SDPUtils.logger.info("USB scan time %f\n", end - start)

        except Exception as ex:
            if SDPUtils.logger.getEffectiveLevel() == logging.DEBUG:
                SDPUtils.logger.debug('Error traceback:')
                traceback.print_exc()
            SDPUtils.logger.exception('Scan for USB device ended with exception: %s', str(ex))

        finally:
            # restore log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

        return devices

    @staticmethod
    def scan_usb_devices_device_manager(vid: int, pid: int):  # type: ignore
        """Scan for USB devices using device manager.

        @param vid: Vid of USB device.
        @param pid: Pid of USB device.
        @return: List of USB devices.
        """
        class DeviceManager:
            """Dummy class for device manager."""
            def __init__(self):  # type: ignore
                """Use import to exercise device manager from infi package."""
                # from infi.devicemanager import DeviceManager
                pass
        vid = format(vid, '04x').upper()  # type: ignore
        pid = format(pid, '04x').upper()  # type: ignore
        usb_devices = []
        device_manager = DeviceManager()
        device_manager.root.rescan()  # type: ignore
        devices = device_manager.all_devices  # type: ignore
        if devices is not None:
            HID_COMPL_VENDOR_DEF_DEVICE = 'HID-compliant vendor-defined device'
            for device in devices:
                if HID_COMPL_VENDOR_DEF_DEVICE in device.description:
                    if f'VID_{vid}' in device.instance_id and f'PID_{pid}' in device.instance_id:
                        usb_devices.append(device)
        return usb_devices

    @staticmethod
    def scan_usb_devices_for_proc(proc_name: str,  # type: ignore
                                  scan_option: UsbDevScanOption = UsbDevScanOption.SPSDK):
        """Scan usb devices for given processor name.

        @param proc_name: Name of the processor.
        @param scan_option: Scan option.
        @return: List of usb devices connected to given processor.
        """
        usb_devices = []
        if proc_name is not None:
            if scan_option is UsbDevScanOption.SPSDK:
                # Use spsdk usb scan.
                usb_id = UsbId.get_usb_id(proc_name)
                if usb_id is not None:
                    usb_devices = SDPUtils.scan_usb_devices(usb_id)
            elif scan_option is UsbDevScanOption.DEVICE_MANAGER:
                # Use device manager scan.
                vid_pid = UsbId.get_vid_pid(proc_name)
                if vid_pid is not None:
                    (vid, pid) = vid_pid
                    usb_devices = SDPUtils.scan_usb_devices_device_manager(vid, pid)
            elif scan_option is UsbDevScanOption.LIBUSBSIO:
                # Use libusbsio scan.
                vid_pid = UsbId.get_vid_pid(proc_name)
                libusbsio_logger = logging.getLogger("libusbsio")
                sio = libusbsio.usbsio(loglevel=libusbsio_logger.getEffectiveLevel())
                usb_devices = list(sio.HIDAPI_Enumerate(vidpid=vid_pid))

        return usb_devices
