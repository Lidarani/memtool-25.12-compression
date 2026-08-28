# Copyright 2022-2024 NXP
"""TODO:summary line."""
import os
from enum import Enum
from typing import List

from memtool.common.app import ApplicationType
from memtool.common.app_mcu import AppMCU
from memtool.common.base_test import TestStatus
from memtool.common.config_data import ConfigData
from memtool.common.workspace import Workspace
from memtool.processor.base_processor import BaseProcessor
from memtool.utils.constants import Const


class MIMXRT11XXProcessor(BaseProcessor):
    """TODO:summary line."""

    def __init__(self, name, ddr_type):  # type: ignore
        """TODO:summary line."""
        super(MIMXRT11XXProcessor, self).__init__(name, ddr_type)

    def get_app_type(self) -> Enum:
        """Get processor application type.

        @return: processor application type
        """
        return ApplicationType.MCU

    def init_bin_info(self, config_data: ConfigData):  # type: ignore
        """Override init_bin_info from BaseProcessor.

        @param config_data: processor config data
        """

    def create_dcd_bin(self, config_data: ConfigData):  # type: ignore
        """Override create_dcd_bin from BaseProcessor."""
        # dcd is created by javascript - only set it to configData
        workspace_dir = Workspace.get_instance().get_location()
        filename = workspace_dir + os.path.sep + 'dcd.bin'
        # set bin file path
        config_data.target_params['dcd_file'] = filename

    def get_test_bin_file_name(self, config_data: ConfigData):  # type: ignore
        """Find the right binaries for the processor.

        @param config_data: processor config data
        @return: path to DDR test bin file
        """
        binaries_folder = os.path.join(config_data.data_dir, Const.BIN_DIR_NAME)
        bin_file = next(iter(filter(lambda x: (x[-5:] in ('.syms',)), os.listdir(binaries_folder))))

        bin_file_path = os.path.join(binaries_folder, bin_file).replace('\\', '/').replace('.syms', '.bin')

        return bin_file_path

    def get_app_symbol_names(self, primary_image: bool = True) -> List[str]:
        """Gets the application symbols for primary or secondary image.

        @param primary_image: True if symbols for primary image is needed, False otherwise
        @return: application symbols
        """
        return AppMCU.get_app_symbol_names()

    def pre_test_updates(self, config_data):  # type: ignore
        """Override pre_test_updates from BaseProcessor.

        @param config_data: processor config data
        """
        params = config_data.params
        if 'configured_test_size' in params["app"]:
            if params["app"]["configured_test_size"] < int(params["app"]["test_params"]["size"]):
                sizeKb = params["app"]["configured_test_size"] / 1024
                unit = 'KB'
                if sizeKb > 1024:
                    sizeKb = sizeKb / 1024
                    unit = 'MB'
                raise Exception(
                    'SEMC component error: configured size is %d %s. Increase BR0 value to test bigger size' % (
                    sizeKb, unit))

            if params["app"]["comp_base_address"] != params["app"]["test_params"]["start_addr"]:
                raise Exception(
                    'SEMC component error: SDRAM base address is not correct. SEMC component setting: %s. Test '
                    'setting: %s' % (
                    params["app"]["comp_base_address"], params["app"]["test_params"]["start_addr"]))

            if params["app"]["comp_validity"] != 1:
                raise Exception('SEMC component error: validity for the BR registers not set.')

        return TestStatus.PARAMS_VALIDATED
