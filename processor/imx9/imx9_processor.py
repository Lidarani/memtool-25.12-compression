# Copyright 2020-2025 NXP
"""i.MX9 processor classes."""
import logging
import time
from enum import Enum

from memtool.common.app import ApplicationType
from memtool.common.config_data import ConfigData
from memtool.processor.base_processor import BaseProcessor
from memtool.processor.sdps_processor import SDPSProcessor
from memtool.rpa.xls_engine_mx9 import XlsEngineMX9


class MIMX9Processor(BaseProcessor):
    """i.MX9 processor base class."""

    logger = logging.getLogger(__name__)

    def __init__(self, name, dram_type):  # type: ignore
        """Constructor."""
        super(MIMX9Processor, self).__init__(name, dram_type)

    def get_app_type(self) -> Enum:
        """Get processor application type.

        @return: processor application type
        """
        return ApplicationType.MPU

    def init_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Load xls data and mappings.

        @param config_data: processor config data
        """
        start = time.time()
        super(MIMX9Processor, self).init_reg_calc(config_data)
        self.reg_calc_map = config_data.rpa_dict.copy()
        self.reg_calc = XlsEngineMX9(config_data)
        end = time.time()
        logging.getLogger(__name__).info("Xls mapping load time %f", end - start)

    def ddrc_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Override ddrc_reg_calc from BaseProcessor.

        @param config_data: processor config data
        """
        self.init_reg_calc(config_data)
        super(MIMX9Processor, self).ddrc_reg_calc(config_data)


class MIMX9MSDPS(MIMX9Processor, SDPSProcessor):
    """i.MX9 with SDPS connection processor class."""

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], str):
                if arg[0] in ConfigData.DEVICES_INFO:
                    processor_info = ConfigData.DEVICES_INFO[arg[0]]
                    return processor_info.is_imx9() and (processor_info.get_protocol() == SDPSProcessor.PROTOCOL)

        return False
