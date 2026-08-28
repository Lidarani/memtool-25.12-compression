# Copyright 2024-2025 NXP
"""Device info class."""
import logging
import os
from typing import List, Tuple, Union

import yaml


class DeviceInfo:
    """Device info container."""

    logger = logging.getLogger(__name__)

    DIR_NAME = "devices"
    FAMILY = "family"
    PROTOCOL = "protocol"
    SPSDK_ID = "spsdk_device"
    REVISION = "revision"
    PRIMARY_IMAGE = "primary_image"
    SECONDARY_IMAGE = "secondary_image"
    IMAGE_NAME = "name"
    IMAGE_ENTRY_POINT = "entry_point"
    IMAGE_SYMBOLS = "symbols"
    HAS_SM = "has_sm"
    AHAB_IMAGE_NAME = "ahab_img_file_name"
    SM_IMAGE_NAME = "sm_file_name"
    V2X_IMAGE_NAME = "v2x_file_name"
    DS_MAP = "ds_map"
    CAN_EXECUTE_DIAGS_AFTER_QUICKBOOT = "can_execute_diags_after_quickboot"

    FAMILY_MX8 = "mx8"  # i.MX8 family ID
    FAMILY_MX9 = "mx9"  # i.MX9 family ID
    FAMILY_LX2 = "lx2"  # Layerscape family ID
    FAMILY_LA = "la"  # LA family ID

    def __init__(self, device: str, device_dir_path: str):
        """Constructor.

        @param device: device name
        @param device_dir_path: path to device directory info
        """
        self.name = device
        self.device_info = {}

        device_info_path = os.path.join(device_dir_path, f"{device}.yaml")
        if not os.path.isfile(device_info_path):
            self.logger.error(f"Unable to find info for {device} processor. {device_info_path} is missing!")
        else:
            try:
                with open(device_info_path) as stream:
                    self.device_info = yaml.safe_load(stream)
            except IOError as exc1:
                self.logger.error(exc1)
            except yaml.YAMLError as exc2:
                self.logger.error(exc2)

    def get_family(self) -> str:
        """Get device family."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to identify info for {self.name}. Device info dictionary is empty!")
            return ''

        if DeviceInfo.FAMILY not in self.device_info:
            self.logger.error(f"Unable to identify family for {self.name}. "
                              f"{DeviceInfo.FAMILY} section is missing from device info dictionary!")
            return ''

        return self.device_info[DeviceInfo.FAMILY]

    def get_protocol(self) -> str:
        """Get device protocol."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to identify info for {self.name}. Device info dictionary is empty!")
            return ''

        if DeviceInfo.PROTOCOL not in self.device_info:
            self.logger.error(f"Unable to identify protocol for {self.name}. "
                              f"{DeviceInfo.PROTOCOL} section is missing from device info dictionary!")
            return ''

        return self.device_info[DeviceInfo.PROTOCOL]

    def get_ds_map(self) -> dict:
        """Get DS_MAP for current device."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to identify the DS mapping for {self.name}. Device info dictionary is empty!")
            return {}

        if DeviceInfo.DS_MAP not in self.device_info.keys():
            self.logger.error(f"Unable to identify the DS mapping for {self.name}. "
                              f"{DeviceInfo.DS_MAP} section is missing from device info dictionary!")
            return {}

        return self.device_info[DeviceInfo.DS_MAP]

    def get_bin_file_name(self) -> str:
        """Get name of test binary for current device."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to find image name for {self.name}. Device info dictionary is empty!")
            return ''

        if DeviceInfo.PRIMARY_IMAGE not in self.device_info:
            self.logger.error(f"Unable to find image name for {self.name}. "
                              f"{DeviceInfo.PRIMARY_IMAGE} section is missing from device info dictionary!")
            return ''

        if DeviceInfo.IMAGE_NAME not in self.device_info[DeviceInfo.PRIMARY_IMAGE]:
            self.logger.error(f"Unable to find image name for {self.name}. "
                              f"{DeviceInfo.IMAGE_NAME} section is missing from device info dictionary!")
            return ''

        return self.device_info[DeviceInfo.PRIMARY_IMAGE][DeviceInfo.IMAGE_NAME]

    def get_second_bin_file_name(self) -> str:
        """Get name of test second binary for current device."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to find second image name for {self.name}. Device info dictionary is empty!")
            return ''

        if DeviceInfo.SECONDARY_IMAGE not in self.device_info:
            self.logger.error(f"Unable to find second image name for {self.name}. "
                              f"{DeviceInfo.SECONDARY_IMAGE} section is missing from device info dictionary!")
            return ''

        if DeviceInfo.IMAGE_NAME not in self.device_info[DeviceInfo.SECONDARY_IMAGE]:
            self.logger.error(f"Unable to find image name for {self.name}. "
                              f"{DeviceInfo.IMAGE_NAME} section is missing from device info dictionary!")
            return ''

        return self.device_info[DeviceInfo.SECONDARY_IMAGE][DeviceInfo.IMAGE_NAME]

    def get_ahab_image_name(self) -> str:
        """Get AHAB image file name for current device."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to find AHAB image name for {self.name}. Device info dictionary is empty!")
            return ''

        if DeviceInfo.AHAB_IMAGE_NAME not in self.device_info:
            self.logger.error(f"Unable to find AHAB image name for {self.name}. "
                              f"{DeviceInfo.AHAB_IMAGE_NAME} section is missing from device info dictionary!")
            return ''

        return self.device_info[DeviceInfo.AHAB_IMAGE_NAME]

    def get_sm_image_name(self) -> str:
        """Get system manager image file name for current device."""
        if len(self.device_info) == 0:
            self.logger.error(f"Unable to find SM image name for {self.name}. Processor info dictionary is empty!")
            return ''

        if DeviceInfo.SM_IMAGE_NAME not in self.device_info:
            self.logger.error(f"Unable to find SM image name for {self.name}. "
                              f"{DeviceInfo.SM_IMAGE_NAME} section is missing from device info dictionary!")
            return ''

        return self.device_info[DeviceInfo.SM_IMAGE_NAME]

    def get_v2x_image_name(self) -> str:
        """Get V2X image file name for current device."""
        if len(self.device_info) == 0:
            return ''

        if DeviceInfo.V2X_IMAGE_NAME not in self.device_info:
            return ''

        return self.device_info[DeviceInfo.V2X_IMAGE_NAME]

    def has_sm(self) -> bool:
        """Check if device supports system manager."""
        if not self.device_info:
            self.logger.error(f"Unable to find info for SM on {self.name}. Device info dictionary is empty!")
            return False

        return self.device_info.get(DeviceInfo.HAS_SM, False)

    def get_app_symbols(self, primary_image: bool = True) -> List[str]:
        """Gets the application symbols for primary or secondary image.

        @param primary_image: True if symbols for primary image is needed, False otherwise
        @return: application symbols
        """
        if not self.device_info:
            self.logger.info(f"Unable to find application symbols for {self.name}. Device info dictionary is empty!")
            return []

        if primary_image:
            if DeviceInfo.PRIMARY_IMAGE not in self.device_info:
                self.logger.info(f"Unable to find primary application symbols for {self.name}. "
                                 f"{DeviceInfo.PRIMARY_IMAGE} section is missing from device info dictionary!")
                return []
            image_info = self.device_info[DeviceInfo.PRIMARY_IMAGE]
        else:
            if DeviceInfo.SECONDARY_IMAGE not in self.device_info:
                self.logger.info(f"Unable to find secondary application symbols for {self.name}. "
                                 f"{DeviceInfo.SECONDARY_IMAGE} section is missing from device info dictionary!")
                return []
            image_info = self.device_info[DeviceInfo.SECONDARY_IMAGE]

        if DeviceInfo.IMAGE_SYMBOLS not in image_info:
            self.logger.info(f"Unable to find application symbols for {self.name}. "
                             f"{DeviceInfo.IMAGE_SYMBOLS} section is missing from device info dictionary!")
            return []

        return image_info[DeviceInfo.IMAGE_SYMBOLS]

    def get_app_entry_point(self, primary_image: bool = True) -> Union[str, None]:
        """Gets the application entry point symbol for primary or secondary image.

        @param primary_image: True if symbols for primary image is needed, False otherwise
        @return: application entry point symbol
        """
        if not self.device_info:
            self.logger.info(f"Unable to find application entry point for {self.name}. "
                             f"Device info dictionary is empty!")
            return None

        if primary_image:
            if DeviceInfo.PRIMARY_IMAGE not in self.device_info:
                self.logger.info(f"Unable to find primary application entry point for {self.name}. "
                                 f"{DeviceInfo.PRIMARY_IMAGE} section is missing from device info dictionary!")
                return None
            image_info = self.device_info[DeviceInfo.PRIMARY_IMAGE]
        else:
            if DeviceInfo.SECONDARY_IMAGE not in self.device_info:
                self.logger.info(f"Unable to find secondary application entry point for {self.name}. "
                                 f"{DeviceInfo.SECONDARY_IMAGE} section is missing from device info dictionary!")
                return None
            image_info = self.device_info[DeviceInfo.SECONDARY_IMAGE]

        if DeviceInfo.IMAGE_ENTRY_POINT not in image_info:
            self.logger.info(f"Unable to find application entry point for {self.name}. "
                             f"{DeviceInfo.IMAGE_ENTRY_POINT} section is missing from device info dictionary!")
            return None

        return image_info[DeviceInfo.IMAGE_ENTRY_POINT]

    def can_run_diags_after_quickboot(self) -> bool:
        """Getter for whether device can run diagnostic tests with QuickBoot.

        @return: True if diagnostics can be executed after QuickBoot, False otherwise
        """
        if not self.device_info:
            self.logger.error(f"Unable to find info for {self.name}. Device info dictionary is empty!")
            return False

        return self.device_info.get(DeviceInfo.CAN_EXECUTE_DIAGS_AFTER_QUICKBOOT, False)

    def get_spsdk_id(self) -> Union[str, None]:
        """Get processor SPSDK device id."""
        if not self.device_info:
            self.logger.error(f"Unable to find USB info for {self.name} device. Device info dictionary is empty!")
            return None

        if DeviceInfo.SPSDK_ID not in self.device_info:
            self.logger.info(f"Unable to find SPSDK device ID info for {self.name}. "
                             f"{DeviceInfo.SPSDK_ID} section is missing from device info dictionary!")
            return None

        return self.device_info[DeviceInfo.SPSDK_ID]

    def get_revision(self) -> Union[str, None]:
        """Get processor revision."""
        if not self.device_info:
            self.logger.error(f"Unable to find USB info for {self.name} device. Device info dictionary is empty!")
            return None

        if DeviceInfo.REVISION not in self.device_info:
            self.logger.info(f"Unable to find revision info for {self.name}. "
                             f"{DeviceInfo.REVISION} section is missing from device info dictionary!")
            return None

        return self.device_info[DeviceInfo.REVISION]

    def is_imx8(self) -> bool:
        """Check if it's i.MX8."""
        return self.get_family() == DeviceInfo.FAMILY_MX8

    def is_imx9(self) -> bool:
        """Check if it's i.MX9."""
        return self.get_family() == DeviceInfo.FAMILY_MX9

    def is_lx2(self) -> bool:
        """Check if it's LX2."""
        return self.get_family() == DeviceInfo.FAMILY_LX2

    def is_la(self) -> bool:
        """Check if it's LA."""
        return self.get_family() == DeviceInfo.FAMILY_LA
