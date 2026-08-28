# Copyright 2020-2025 NXP
"""Communication with a target through SDPS."""
import logging
import traceback

from spsdk.exceptions import SPSDKConnectionError
from spsdk.sdp.sdps import SDPS
from spsdk.utils.database import DatabaseManager, SPSDKErrorMissingDevice
from spsdk.utils.family import FamilyRevision

from memtool.common.config_data import ConfigData
from memtool.common.sdp_interface import SDPSInterface, SDPUtils, UsbId
from memtool.utils.constants import Const


class SDPSComm(SDPSInterface):
    """Class for SDPS protocol communication."""

    logger = logging.getLogger(__name__)

    # TODO: remove self.spsdk_device_map when DDR soc name and SPSDK device name will match!!!
    spsdk_device_map = {'MIMX8MN': 'mx8mn',
                        'MIMX8MP': 'mx8mp',
                        'MIMX91': 'mx91',
                        'MIMX93': 'mx93',
                        'MIMX943': 'mx943',
                        'MIMX95': 'mx95',
                        'MIMX95_B0': 'mx95'}

    @classmethod
    def get_spsdk_device(cls, soc_name: str) -> str:
        """Get SPSDK device name for the given processor.

        @return: SPSDK device name
        """
        if soc_name in ConfigData.DEVICES_INFO:
            spsdk_device = ConfigData.DEVICES_INFO[soc_name].get_spsdk_id()
            try:
                if DatabaseManager().db.devices.get(spsdk_device):
                    return spsdk_device
            except SPSDKErrorMissingDevice:
                if soc_name in cls.spsdk_device_map:
                    return cls.spsdk_device_map[soc_name]

        return soc_name

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input, so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], dict):
                return arg[0].get('not_sim', True)
        return False

    def __init__(self, params):  # type: ignore
        """TODO:summary line."""
        super(SDPSComm, self).__init__()

        self.connect_params = params
        self.sdps = None
        self.usb_device = None
        self.init()

    def init(self):  # type: ignore
        """Initiate sdps communication channel."""
        soc_name = self.connect_params[Const.PARAM_S_TC_SOC_NAME]
        usb_id = UsbId.get_usb_id(soc_name)
        if usb_id is None:
            self.sdps = None
            self.logger.error("Missing USB HID device id!")
            return
        if Const.PARAM_S_TC_USB_SEL not in self.connect_params or self.connect_params[Const.PARAM_S_TC_USB_SEL] is None:
            self.sdps = None
            self.logger.error("Missing USB HID device selection!")
            return
        try:
            usb_sel = int(self.connect_params[Const.PARAM_S_TC_USB_SEL])
        except ValueError as val_exp:
            self.sdps = None
            self.logger.error(f"Invalid USB HID device selection type: {val_exp} !")
            return

        if ConfigData.HIDS:
            usb_devices = SDPUtils.scan_usb_devices(ConfigData.HIDS[usb_sel], count=10)
            self.usb_device = usb_devices[0] if usb_devices else None
        else:
            usb_devices = SDPUtils.scan_usb_devices(usb_id, count=10)
            if usb_sel >= len(usb_devices):
                self.sdps = None
                self.logger.error(f"Invalid USB HID device selection {usb_sel} from list {usb_devices} !")
                return
            self.usb_device = usb_devices[usb_sel]

        if self.usb_device is None:
            self.sdps = None
            self.logger.error("No HID device found!")
        else:
            self.sdps = SDPS(self.usb_device, FamilyRevision(self.get_spsdk_device(soc_name)))
            self.logger.debug("Create %s with device %s", self.connect_params[Const.PARAM_S_TC_SOC_NAME],
                self.usb_device)

    def load_bin(self, data=None, filename='Binary image'):  # type: ignore
        """Override load_bin from SDPSInterface."""
        self.logger.debug("Load binary %s", filename)

        if data is None:
            with open(filename, 'rb') as f:
                data = f.read()

        self.usb_device.configure({"hid_ep1": True, "pack_size": 1020, })
        try:
            self.usb_device.write_data(data)
        except SPSDKConnectionError as exc:
            self.logger.error("SDPS download failed: %s", exc)
            raise SPSDKConnectionError(f"SDPS download incomplete: {exc}") from exc

    def is_alive(self) -> bool:
        """Override is_alive from Channel.

        @return: can the backend communicate with channel?
        """
        return self.sdps is not None and self.sdps.is_opened

    def open(self):  # type: ignore
        """Connect to i.MX device."""
        if not self.is_alive():
            self.init()
            self.sdps.open()
            if not self.is_alive():
                raise ConnectionError("SDPS connection could not be established!")

    def close(self):  # type: ignore
        """Disconnect i.MX device."""
        if self.sdps is not None:
            self.sdps.close()
            self.usb_device = None
