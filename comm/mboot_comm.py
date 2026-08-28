# Copyright 2022-2025 NXP
"""Communication with a target through MBoot."""
import logging
import time

from spsdk.mboot.interfaces.usb import MbootUSBInterface
from spsdk.mboot.mcuboot import McuBoot

from memtool.common.mboot_interface import MBootInterface
from memtool.utils.constants import Const


class MBootComm(MBootInterface):
    """Class for MBoot protocol communication."""

    logger = logging.getLogger(__name__)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], dict):
                return arg[0].get('not_sim', True)
        return False

    def __init__(self, connect_params):  # type: ignore
        """TODO:summary line."""
        super(MBootComm, self).__init__()
        device = self.get_usb_device(connect_params['usb_id'])

        if device is None:
            self.mcuBoot = None
            self.logger.error("No HID device found on USB port")
        else:
            self.mcuBoot = McuBoot(device)
            self.open()
            self.logger.info(' MBoot init %s: %s', connect_params[Const.PARAM_S_TC_SOC_NAME], device)

    def load_bin(self, data=None, filename="Binary Image") -> bool:  # type: ignore
        """Override load_bin from MbootInterface.

        @return: True if success else False
        """
        self.logger.info(' mcuBoot write binary')

        if data is None:
            with open(filename, 'rb') as f:
                flash_loader_data = f.read()
                status = self.mcuBoot.load_image(flash_loader_data)
        else:
            status = self.mcuBoot.load_image(data)

        return status

    def is_alive(self) -> bool:
        """Override is_alive from Channel.

        @return: can the backend communicate with channel?
        """
        return self.mcuBoot is not None and self.mcuBoot.is_opened

    def open(self):  # type: ignore
        """Open HID port."""
        if not self.is_alive():
            if self.mcuBoot is None:
                self.logger.error("Please make sure target is in serial downloader mode")
                raise ConnectionError("Mboot connection could not be established")
            self.mcuBoot.open()
            if not self.is_alive():
                raise ConnectionError("mboot connection could not be established!")

    def close(self):  # type: ignore
        """Free HID port."""
        self.logger.info(' mboot close HID:')
        if self.mcuBoot is not None:
            self.mcuBoot.close()

    def get_usb_device(self, usb_id: str):  # type: ignore
        """Scan for USB device for mboot communication."""
        start = time.time()
        count = 10

        while True:
            devices = MbootUSBInterface.scan(usb_id)
            if devices:
                break

            if count > 0:
                self.logger.info("Retry USB scan")
                time.sleep(1)
                count -= 1
            else:
                break

        end = time.time()
        self.logger.info("USB scan time %f\n", end - start)

        if devices is None or len(devices) == 0:
            return None

        return devices[0]
