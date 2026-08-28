#Copyright 2022-2024 NXP
"""LA1224 processor class."""
import logging
import os
import time
from enum import Enum
from typing import List

from memtool.common.app import ApplicationType
from memtool.common.config_data import ConfigData
from memtool.common.workspace import Workspace
from memtool.processor.ccs_processor import CCSProcessor
from memtool.utils.constants import Const


class LA(CCSProcessor):
    """This class provides an implementation for LA1224 processor."""
    __PC_REG_INDEX = 4106

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], str):
                if arg[0] in ConfigData.DEVICES_INFO:
                    processor_info = ConfigData.DEVICES_INFO[arg[0]]
                    return processor_info.is_la()

        return False

    def __init__(self,  name: str, dram_type: str):
        """__init__ for LA1224 class."""
        super(LA, self).__init__(name, dram_type)

    def get_app_type(self) -> Enum:
        """Get processor application type.

        @return: processor application type
        """
        return ApplicationType.LA

    def init_target(self, ccs_channel):  # type: ignore
        """Override init_target from CCSProcessor.

        @param ccs_channel: CSS channel to communicate with target processor
        @return: was init successful?
        """
        return True

    def get_pc_register(self):  # type: ignore
        """Override get_pc_register from CCSProcessor."""
        return self.__PC_REG_INDEX

    def get_test_bin_file_name(self, config_data: ConfigData):  # type: ignore
        """Find the right binaries for the processor.

        @param config_data: processor config data
        @return: path to DDR test bin file
        """
        binaries_folder = os.path.join(config_data.data_dir, Const.BIN_DIR_NAME)
        bin_file = next(iter(filter(lambda x:
                                    (x.endswith('.syms')),
                                    os.listdir(binaries_folder))))

        bin_file_path = os.path.join(binaries_folder, bin_file).replace('\\', '/').replace('.syms', '.bin')

        return bin_file_path

    def get_app_symbol_names(self, primary_image: bool = True) -> List[str]:
        """Gets the application symbols for primary or secondary image.

        @param primary_image: True if symbols for primary image is needed, False otherwise
        @return: application symbols
        """
        app_symbol_names = ['__START_ADDRESS', '__start', 'TEST_IN', 'TEST_OUT', "g_log_level", 'g_sys_params']
        return app_symbol_names

    def create_dcd_bin(self, config_data: ConfigData):  # type: ignore
        """Override create_dcd_bin from BaseProcessor.

        @param config_data: processor config data
        """
        # dcd is created by javascript - only set it to configData
        workspace_dir = Workspace.get_instance().get_location()
        filename = workspace_dir + os.path.sep + 'dcd.bin'
        # set bin file path
        config_data.target_params['dcd_file'] = filename
