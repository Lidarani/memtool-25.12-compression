# Copyright 2021-2025 NXP
"""i.MX8 processor classes."""
import logging
import time
from enum import Enum
from typing import List, Tuple, Union

from memtool.common.app import ApplicationType
from memtool.common.config_data import ConfigData
from memtool.processor.base_processor import BaseProcessor
from memtool.processor.sdp_processor import SDPProcessor
from memtool.processor.sdps_processor import SDPSProcessor
from memtool.rpa.xls_engine_mx8m import XlsEngineMX8M
from memtool.utils.constants import Const


class MIMX8MProcessor(BaseProcessor):
    """i.MX8 processor base class."""

    def __init__(self, name, dram_type):  # type: ignore
        """Constructor."""
        super(MIMX8MProcessor, self).__init__(name, dram_type)

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
        super(MIMX8MProcessor, self).init_reg_calc(config_data)
        self.reg_calc_map = config_data.rpa_dict.copy()
        self.reg_calc = XlsEngineMX8M(config_data)
        end = time.time()
        logging.getLogger(__name__).info("Xls mapping load time %f", end - start)

    def ddrc_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Override ddrc_reg_calc from BaseProcessor.

        @param config_data: processor config data
        """
        self.init_reg_calc(config_data)
        super(MIMX8MProcessor, self).ddrc_reg_calc(config_data)

    def update_phy_config(self, config_data: ConfigData):  # type: ignore
        """TODO:summary line."""
        super(MIMX8MProcessor, self).update_phy_config(config_data)

        if config_data.mem_type != 'ddr3':
            config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyOdtImpedance"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[1]"]["PhyOdtImpedance"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[2]"]["PhyOdtImpedance"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[0]"]
            config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyDrvImpedance"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[1]"]["PhyDrvImpedance"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[2]"]["PhyDrvImpedance"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[0]"]
        else:
            if config_data.soc_name in ['MIMX8M', 'MIMX8MM']:
                # ddr3 8m and 8mm have only messageBlock 0
                config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyOdtImpedance"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[0]"]
                config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyDrvImpedance"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[0]"]
            else:
                # other ddr3 has only messageBlock 0 and 1
                config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyOdtImpedance"] = \
                    config_data.params[Const.PARAM_S_PHY]["messageBlock[1]"]["PhyOdtImpedance"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[0]"]
                config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyDrvImpedance"] = \
                    config_data.params[Const.PARAM_S_PHY]["messageBlock[1]"]["PhyDrvImpedance"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[0]"]

    def get_ecc_scrub_regions(self, config_data: ConfigData) -> \
            Union[None, Tuple[List[Tuple[str, str]], Tuple[str, str]]]:
        """Get ECC scrub regions.

        @param config_data: processor config data
        """
        no_ecc_block = len(config_data.inline_ecc_config)
        if no_ecc_block == 0:
            return None

        no_regions = len(config_data.inline_ecc_config[0])
        for ecc_block_idx in range(1, no_ecc_block):
            crt_no_regions = len(config_data.inline_ecc_config[ecc_block_idx])
            if no_regions != crt_no_regions:
                logging.getLogger(__name__).error("ECC memory block %d has %d regions instead of expected %d regions",
                                                  ecc_block_idx, crt_no_regions, no_regions)
                # retain the minimum
                no_regions = crt_no_regions if crt_no_regions < no_regions else no_regions
                continue

        scrub_regions = []
        for region_idx in range(no_regions - 1, -1, -1):
            for ecc_block_idx in range(0, no_ecc_block):
                region_attributes = config_data.inline_ecc_config[ecc_block_idx][region_idx]
                if Const.PARAM_S_INLINE_ECC_REGION_START in region_attributes and \
                        Const.PARAM_S_INLINE_ECC_REGION_DENSITY in region_attributes:
                    region_start_axi_address = region_attributes[Const.PARAM_S_INLINE_ECC_REGIONS_START_MX9]
                    region_start_hif_address = int((int(region_start_axi_address, 16) - 0x40000000) / 4)
                    region_density = int(int(
                        region_attributes[Const.PARAM_S_INLINE_ECC_REGION_DENSITY].replace("MB", "")) * 0x100000 / 4)
                    region_end_hif_address = region_start_hif_address + region_density - 1
                    scrub_regions.append((hex(region_start_hif_address), hex(region_end_hif_address)))
        scrub_end_region = ("0x0", "0x0")
        if Const.PARAM_S_BASIC in config_data.params:
            num_channels = 2 if int(config_data.params[Const.PARAM_S_BASIC].get('busWidth', '0')) == 32 else 1
            num_chips = int(config_data.params[Const.PARAM_S_BASIC].get('numChipSelects', '0'))
            if config_data.mem_type in ['lpddr4']:
                density_per_channel = int(config_data.params[Const.PARAM_S_BASIC].get('densityPerChannel', '0'))
            else:
                density_per_channel = int(config_data.params[Const.PARAM_S_BASIC].get('densityPerDevice', '0'))
            total_size = int(density_per_channel * num_chips * num_channels / 8) * 0x40000000
            scrub_end_region = ("0x0", hex(int(total_size / 4) - 1))
        return scrub_regions, scrub_end_region


class MIMX8MSDP(MIMX8MProcessor, SDPProcessor):
    """i.MX8 with SDP connection processor class."""

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], str):
                if arg[0] in ConfigData.DEVICES_INFO:
                    processor_info = ConfigData.DEVICES_INFO[arg[0]]
                    return processor_info.is_imx8() and (processor_info.get_protocol() == SDPProcessor.PROTOCOL)

        return False


class MIMX8MSDPS(MIMX8MProcessor, SDPSProcessor):
    """i.MX8 with SDPS connection processor class."""

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], str):
                if arg[0] in ConfigData.DEVICES_INFO:
                    processor_info = ConfigData.DEVICES_INFO[arg[0]]
                    return processor_info.is_imx8() and (processor_info.get_protocol() == SDPSProcessor.PROTOCOL)

        return False
