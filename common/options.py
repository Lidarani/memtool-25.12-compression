# Copyright 2023-2024 NXP
"""TODO:summary line."""
import logging
from enum import Enum

from memtool.common.factories import Singleton


class SnpsPhyInitEnum(Enum):
    """Synopsys PHY Initialization options."""

    FULL_TRAINING = 0
    SKIP_TRAINING = 1
    DRAM_INIT_ONLY = 2
    UNDEFINED = -1

    @staticmethod
    def from_value(value: int) -> 'SnpsPhyInitEnum':
        """Converts SnpsPhyInitOption from given value.

        @param value: value to be converted
        @return: corresponding SnpsPhyInitOption for the given value or UNDEFINED for an invalid value
        """
        for opt in SnpsPhyInitEnum:
            if opt.value == value:
                return opt
        return SnpsPhyInitEnum.UNDEFINED


class SnpsPhyInitOptions:
    """SNPS Phy Initialization settings."""

    def __init__(self, _phy_init_option: SnpsPhyInitEnum):
        """Constructor."""
        self.__phy_init_option = _phy_init_option

    def set_phy_init_option(self, _phy_init_option: int):  # type: ignore
        """Set PHY initialization option.

        @param _phy_init_option: PHY initialization option
        """
        self.__phy_init_option = SnpsPhyInitEnum.from_value(_phy_init_option)

    def get_phy_init_option(self) -> int:
        """Get PHY initialization option."""
        return self.__phy_init_option.value

    def execute_full_training(self) -> bool:
        """Check if full training should be executed."""
        return self.__phy_init_option == SnpsPhyInitEnum.FULL_TRAINING

    def skip_training(self) -> bool:
        """Check if training should be skipped."""
        return self.__phy_init_option == SnpsPhyInitEnum.SKIP_TRAINING

    def dram_init_only(self) -> bool:
        """Check if only DRAM initialization should be executed."""
        return self.__phy_init_option == SnpsPhyInitEnum.DRAM_INIT_ONLY


class SnpsPhyBootEnum(Enum):
    """Synopsys PHY Boot Mode options."""
    NORMAL_BOOT = 0
    QUICK_BOOT = 1
    UNDEFINED = -1

    @staticmethod
    def from_value(value: int) -> 'SnpsPhyBootEnum':
        """Converts SnpsPhyBootEnum from given value.

        @param value: value to be converted
        @return: corresponding SnpsPhyBootOptions for the given value or UNDEFINED for an invalid value
        """
        for opt in SnpsPhyBootEnum:
            if opt.value == value:
                return opt
        return SnpsPhyBootEnum.UNDEFINED


class SnpsPhyBootOptions:
    """SNPS Phy Boot Mode settings."""

    def __init__(self, _phy_boot_option: SnpsPhyBootEnum):
        """Constructor."""
        self.__phy_boot_option = _phy_boot_option

    def set_phy_boot_option(self, _phy_boot_option: SnpsPhyBootEnum):  # type: ignore
        """Set PHY boot mode option.

        @param _phy_boot_option: PHY boot mode option
        """
        self.__phy_boot_option = _phy_boot_option

    def get_phy_boot_option(self) -> int:
        """Get PHY boot mode option."""
        return self.__phy_boot_option.value

    def normal_boot(self) -> bool:
        """Check if normal boot mode will be performed."""
        return self.__phy_boot_option == SnpsPhyBootEnum.NORMAL_BOOT

    def quick_boot(self) -> bool:
        """Check if quick boot will be performed."""
        return self.__phy_boot_option == SnpsPhyBootEnum.QUICK_BOOT


class BootableImageOptions:
    """Bootable image options."""

    def __init__(self, use_custom_bootable_image: bool, sign_bootable_image: bool):
        """Constructor."""
        self.__use_custom_bootable_image = use_custom_bootable_image
        self.__sign_bootable_image = sign_bootable_image

    def set_use_custom_bootable_image(self, use_custom_bootable_image: bool) -> None:
        """Set use custom bootable image option.

        @param use_custom_bootable_image: Value for use custom bootable image option.
        """
        self.__use_custom_bootable_image = use_custom_bootable_image

    def get_use_custom_bootable_image(self) -> int:
        """Get use custom bootable image option."""
        return self.__use_custom_bootable_image

    def set_sign_bootable_image(self, sign_bootable_image: bool) -> None:
        """Set sign bootable image option.

        @param sign_bootable_image: Value for sign bootable image option.
        """
        self.__sign_bootable_image = sign_bootable_image

    def get_sign_bootable_image(self) -> int:
        """Get sign bootable image option."""
        return self.__sign_bootable_image


class Options(metaclass=Singleton):
    """Workspace singleton class that handles Options."""

    logger = logging.getLogger(__name__)

    # phy init options
    __snps_phy_init_options = SnpsPhyInitOptions(SnpsPhyInitEnum.FULL_TRAINING)

    # phy boot mode options
    __snps_phy_boot_options = SnpsPhyBootOptions(SnpsPhyBootEnum.NORMAL_BOOT)

    # bootable image options
    __bootable_image_options = BootableImageOptions(use_custom_bootable_image=False, sign_bootable_image=False)

    @staticmethod
    def get_instance():  # type: ignore
        """Get singleton instance of options."""
        return Options()

    def get_snps_phy_init_options(self) -> SnpsPhyInitOptions:
        """Get Synopsys PHY init options."""
        return self.__snps_phy_init_options

    def get_snps_phy_boot_options(self) -> SnpsPhyBootOptions:
        """Get Synopsys PHY boot options."""
        return self.__snps_phy_boot_options

    def get_bootable_image_options(self) -> BootableImageOptions:
        """Get Bootable image options."""
        return self.__bootable_image_options
