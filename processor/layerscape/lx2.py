# Copyright 2021-2024 NXP
"""TODO:summary line."""
import logging
import time
from enum import Enum

from memtool.common.app import ApplicationType
from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import get_dcd_command
from memtool.processor.ccs_processor import CCSProcessor
from memtool.processor.errata_library import ErrataLibrary, ErrataType, ErrataUpdatePolicyType
from memtool.rpa.xls_engine_lx2 import XlsEngineLX2
from memtool.utils.constants import Const
from memtool.utils.helper import swap_32


class LX2(CCSProcessor):
    """TODO:summary line."""

    __PC_REG_INDEX = 121385

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], str):
                if arg[0] in ConfigData.DEVICES_INFO:
                    processor_info = ConfigData.DEVICES_INFO[arg[0]]
                    return processor_info.is_lx2()

        return False

    def __init__(self,  name: str, dram_type: str):
        """TODO:summary line."""
        super(LX2, self).__init__(name, dram_type)

    def get_app_type(self) -> Enum:
        """Get processor application type.

        @return: processor application type
        """
        return ApplicationType.LX

    def init_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Load xls data and mappings.

        @param config_data: processor config data
        """
        start = time.time()
        super(LX2, self).init_reg_calc(config_data)
        self.reg_calc_map = config_data.rpa_dict.copy()
        self.reg_calc = XlsEngineLX2(config_data)
        end = time.time()
        logging.getLogger(__name__).info("Xls mapping load time %f", end - start)

    def init_bin_info(self, config_data: ConfigData):  # type: ignore
        """Override init_bin_info from BaseProcessor.

        @param config_data: processor config data
        """
        super(LX2, self).init_bin_info(config_data)
        config_data.connect_params["count_us_app_finish"] = 300
        config_data.sys_params["ctrl_id"] = config_data.ctrl_id
        config_data.params["swap_data"] = True

    def init_target(self, ccs_channel) -> bool:  # type: ignore
        """Override init_target from CCSProcessor.

        @param ccs_channel: CSS channel to communicate with target processor
        @return: was init successful?
        """
        ccs_channel.write_register(20509, (0x0).to_bytes(4, byteorder='big'))
        ccs_channel.write_register(20510, (0x0).to_bytes(4, byteorder='big'))
        ccs_channel.write_register(24576, (0x0).to_bytes(4, byteorder='big'))

        # TrustZone Initialization (mandatory for LX2160A and derivatives)
        ##################################################################
        for idx in range(4):
            # TODO: see if init should fail at first failed operation
            if not ccs_channel.write_data(0x01100004 + idx * 0x10000, 4, (0x00000001).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x01100110 + idx * 0x10000, 4, (0xc0000000).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x01100114 + idx * 0x10000, 4, (0xffffffff).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x01100128 + idx * 0x10000, 4, (0xfffff000).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x0110012C + idx * 0x10000, 4, (0x000000ff).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x01100130 + idx * 0x10000, 4, (0xc0000001).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x01100134 + idx * 0x10000, 4, (0xffffffff).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x01100008 + idx * 0x10000, 4, (0x00000001).to_bytes(4, byteorder='little')):
                return False

        # CCN Initialization
        ####################
        # HN-I sa_aux_ctl
        # Terminate the PoS barriers and serialize Device-nGnRnE writes, clear pos_early_wr_comp_en
        data = ccs_channel.read_data(0x04080500, 4, 1)
        if data is None:
            return False
        val = (swap_32(int(data, 16)) & 0xffffffdf) | 0x210
        if not ccs_channel.write_data(0x04080500, 4, val.to_bytes(4, byteorder='little')):
            return False

        # HN-I - HN-I is not final PoS
        if not ccs_channel.write_data(0x04080000, 4, (0x0).to_bytes(4, byteorder='little')):
            return False

        # Use MN to read the available RN-F, RN-D and HN-F nodes
        data = ccs_channel.read_data(0x04000000 + 0x180, 4, 1)
        if data is None:
            return False
        RNF = swap_32(int(data, 16))
        data = ccs_channel.read_data(0x04000000 + 0x1A0, 4, 1)
        if data is None:
            return False
        RND = swap_32(int(data, 16))
        data = ccs_channel.read_data(0x04000000 + 0x1B0, 4, 1)
        if data is not None:
            return False
        HNF = swap_32(int(data, 16))  # type: ignore

        # Add RNFs to each HNF's snoop domain
        for region in range(bin(HNF).count('1')):
            if not ccs_channel.write_data(0x04200000 + region * 0x10000 + 0x220, 4,
                                          (0xFFFFFFFF).to_bytes(4, byteorder='little')):
                return False
            if not ccs_channel.write_data(0x04200000 + region * 0x10000 + 0x210, 4,
                                          RNF.to_bytes(4, byteorder='little')):
                return False

        # Add RNFs and RNDs to the DVM domain (in MN)
        if not ccs_channel.write_data(0x04000000 + 0x210, 4, (RNF | RND).to_bytes(4, byteorder='little')):
            return False

        # L2 RAM Latency
        ################
        # Initialize the L2 RAM latency
        L2CTLR_EL1 = 118146
        L2CTLR_EL1_value = int.from_bytes(ccs_channel.read_register(L2CTLR_EL1), 'big')
        # Clear L2 Tag RAM latency and L2 Data RAM latency
        L2CTLR_EL1_value &= ~0x000001C7
        # Set L2 data RAM latency bits [2:0]
        L2CTLR_EL1_value |= 0x00000002
        # Set L2 tag RAM latency bits [8:6]
        L2CTLR_EL1_value |= 0x00000080
        ccs_channel.write_register(L2CTLR_EL1, L2CTLR_EL1_value.to_bytes(4, byteorder='big'))

        return True

    def _add_phy(self, config_data: ConfigData):  # type: ignore
        """Override _add_phy from DCDCreator.

        @param config_data: processor config data
        """
        super(LX2, self)._add_phy(config_data)

        erratas = []
        for errata_cmd in ErrataLibrary.get_errata(config_data, ErrataType.PHY_INIT):
            if errata_cmd.mode != ErrataUpdatePolicyType.APPEND_CMD:
                self.logger.warning('Commands can only be appended to dcd PHY section!')
                continue
            erratas.append([errata_cmd.command, int(errata_cmd.address, 16), int(errata_cmd.value, 16)])
        self._add_errata(erratas)

    def update_phy(self, config_data: ConfigData):  # type: ignore
        """Update initPhyConfig with errata.

        @param config_data: processor configuration data
        """
        pass  # for LX2 erratas are not applied to config_data.phy_full_config

    def add_ddrc_after_config_errata(self, config_data):  # type: ignore
        """TODO:summary line."""
        # TODO: add revision info!!!

        # DDR ECC Scrubbing Can Cause Failures - LX2160A Rev 1
        # Description: Disable ECC scrubbing by clearing DDR_SDRAM_CFG_3[ECC_FIX_EN] and DDR_SDRAM_CFG_3[ECC_SCRUB_INT].
        cmd = {'op_code': f'0x{get_dcd_command("memory clrbit"):x}',
               'address': '0x01080260',
               'value': '0x4F000000',
               'size': '0x20'}
        config_data.ddrc_config_full.append(cmd)

        # Address Parity Cannot Be Used with Registered DIMMs - LX2160A Rev 1
        # Description: Disable address parity if using registered DIMMs.
        registered_dimms = int(config_data.params['DDR_SDRAM_CFG'], 16) & 0x10000000
        if registered_dimms != 0:
            cmd = {'op_code': f'0x{get_dcd_command("memory clrbit"):x}',
                   'address': '0x01080114',
                   'value': '0x00000020',
                   'size': '0x20'}
            config_data.ddrc_config_full.append(cmd)

    def add_ddrc_after_enable_errata(self, config_data):  # type: ignore
        """CCN508 Disable CCN interleave.

        Only for LX2xxx
        Disable 2nd ddr controller when the 1st ddr controller is the only one used
        """
        for ID in range(8):
            addr = format(0x04200000 + ID * 0x10000 + 0x8, '#010x')  # pad with 0 so that the string is a 32-bit address
            cmd1 = {'op_code': f'0x{get_dcd_command("memory clrbit"):x}',
                    'address': addr,
                    'value': '0x0000007F',
                    'size': '0x20'}
            cmd2 = {'op_code': f'0x{get_dcd_command("memory setbit"):x}',
                    'address': addr,
                    'value': '0x00000008',
                    'size': '0x20'}
            config_data.ddrc_config_full.append(cmd1)
            config_data.ddrc_config_full.append(cmd2)

    def get_pc_register(self):  # type: ignore
        """Override get_pc_register from CCSProcessor.

        @return: PC reg index
        """
        return self.__PC_REG_INDEX

    def ddrc_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Override ddrc_reg_calc from BaseProcessor.

        @param config_data: processor config data
        """
        self.init_reg_calc(config_data)
        super(LX2, self).ddrc_reg_calc(config_data)
