# Copyright 2020-2025 NXP
"""Communication with a target through SDP."""
import logging

from spsdk.sdp.sdp import SDP

from memtool.common.config_data import ConfigData
from memtool.common.sdp_interface import SDPInterface, SDPUtils, UsbId
from memtool.utils.constants import Const


class SDPComm(SDPInterface):
    """Class for SDP protocol communication."""

    logger = logging.getLogger(__name__)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input, so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], dict):
                return arg[0].get('not_sim', True)
        return False

    def __init__(self, connect_params):  # type: ignore
        """TODO:summary line."""
        super(SDPComm, self).__init__()

        soc_name = connect_params[Const.PARAM_S_TC_SOC_NAME]
        usb_id = UsbId.get_usb_id(soc_name)
        if usb_id is None:
            if Const.PARAM_S_TC_USB_ID in connect_params:
                # RT-es have usb id set into connect parameters.
                usb_id = connect_params[Const.PARAM_S_TC_USB_ID]
            else:
                self.sdp = None
                self.logger.error("Missing USB HID device id!")
                return
        if Const.PARAM_S_TC_USB_SEL not in connect_params or connect_params[Const.PARAM_S_TC_USB_SEL] is None:
            self.sdp = None
            self.logger.error("Missing USB HID device selection!")
            return
        try:
            usb_sel = int(connect_params[Const.PARAM_S_TC_USB_SEL])
        except ValueError as val_exp:
            self.sdp = None
            self.logger.error(f"Invalid USB HID device selection type: {val_exp} !")
            return

        if ConfigData.HIDS:
            usb_devices = SDPUtils.scan_usb_devices(ConfigData.HIDS[usb_sel], count=10)
            usb_device = usb_devices[0] if usb_devices else None
        else:
            usb_devices = SDPUtils.scan_usb_devices(usb_id, count=10)
            if usb_sel >= len(usb_devices):
                self.sdp = None
                self.logger.error(f"Invalid USB HID device selection {usb_sel} from list {usb_devices} !")
                return
            usb_device = usb_devices[usb_sel]

        if usb_device is None:
            self.sdp = None
            self.logger.error("No HID device found")
        else:
            self.sdp = SDP(usb_device)
            self.open()
            self.logger.info(' SDP init %s: %s', soc_name, usb_device)

    def load_bin(self, load_address: int, data=None, filename="Binary Image") -> bool:  # type: ignore
        """Override load_bin from SDPInterface.

        @return: True if success else False
        """
        self.logger.info(' SDP write binary 0x%x %s', load_address, filename)

        if data is None:
            with open(filename, 'rb') as f:
                data = f.read()

        status = self.sdp.write_file(load_address, data)

        return status

    def jump(self, jump_address: int) -> bool:
        """Override jump from SDPInterface."""
        self.logger.info(' SDP jump 0x%x', jump_address)
        return self.sdp.jump_and_run(jump_address)

    def is_alive(self) -> bool:
        """Override is_alive from Channel.

        @return: can the backend communicate with channel?
        """
        return self.sdp is not None and self.sdp.is_opened

    def open(self):  # type: ignore
        """Open HID port."""
        if not self.is_alive():
            if self.sdp is None:
                self.logger.error("Please make sure target is in serial downloader mode")
                raise ConnectionError("SDP connection could not be established")
            self.sdp.open()
            if not self.is_alive():
                raise ConnectionError("SDP connection could not be established!")

    def close(self):  # type: ignore
        """Free HID port."""
        self.logger.info(' SDP close HID:')
        if self.sdp is not None:
            self.sdp.close()
