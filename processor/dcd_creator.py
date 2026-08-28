# Copyright 2020-2025 NXP

"""TODO:summary line."""
import logging
import math
import os
import struct
from typing import Optional

from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import DCDCommand, DCDCommandIds
from memtool.common.options import Options
from memtool.common.workspace import Workspace
from memtool.memtests.snps_phy import SnpsPhy
from memtool.phyinit.phy_utils import PhyPhase, PhyV3Utils
from memtool.utils import helper
from memtool.utils.constants import Const


class DCDCreator:
    """Class used for creating commands for dcd.bin."""

    logger = logging.getLogger(__name__)

    _SIZE_PHY_PARAM_BITS = 32

    def __init__(self):  # type: ignore
        """TODO:summary line."""
        self.commands = bytearray()
        self.commands_list = []
        self.create_list = False

    def _add_command(self, command: int, address: int, value: int, size: int,  # type: ignore
        name: Optional[str] = None):
        """Store command as bytes object or DCDCommand.

        @param command: command code
        @param address, value, size: command params
        """
        if self.create_list:
            # store command as DCDCommand
            self.commands_list.append(DCDCommand(command, address, value, size, name))  # type: ignore
        else:
            # pack command as bytes object
            self.commands += struct.pack("<IIII", int(command), address, value, size)

    def _add_value(self, value: int):  # type: ignore
        """Store int value to dcd.

        @param value: address to be stored in dcd
        """
        self.commands += struct.pack("<I", value)

    def create_dcd_bin(self, config_data: ConfigData):  # type: ignore
        """Create dcd.bin in temp dir.

        @param config_data: processor config data
        """
        self.commands = bytearray()
        self.commands_list = []
        self.create_list = False
        workspace_dir = Workspace.get_instance().get_location()
        filename = workspace_dir + os.path.sep + 'dcd.bin'

        if Const.PARAM_SERDES_SKIP_DDR_PHY not in config_data.params[Const.PARAM_S_BASIC]:
            # gather all commands
            self._add_target_init(config_data)
            opaque_custom_oei = bool(config_data.compress) and config_data.soc_name == 'MIMX95_B0'
            if not opaque_custom_oei:
                self._add_sys_params(config_data)
            self._add_pmic_init(config_data)
            self._add_generic_iomux_init(config_data)
            if not config_data.params['app'].get('check_target_is_responsive', False):
                self._add_ddrc(config_data)
                if not opaque_custom_oei:
                    self._add_diags_params(config_data)
                if not config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) == Const.PHY_QUICK_BOOT:
                    self._add_phy(config_data)
                    for pstate in range(config_data.num_pstates):
                        self._add_phy_per_pstate(config_data, pstate)
                    self._add_pie(config_data)
                    for pstate in range(config_data.num_pstates):
                        self._add_pie_per_pstate(config_data, pstate)

                self._add_extra_msb(config_data)
                self._add_quick_boot_registers(config_data)
                self._add_quick_boot_data(config_data)

            # Mandatory END command
            self._add_command(DCDCommandIds.CMD_END, ord('E'), ord('N'), ord('D'))
            # write commands in file
            # for serdes tests, dcd is created in js
            with open(filename, 'w') as f:
                # TODO: see if implementation is needed
                pass
            with open(filename, 'wb') as f:
                f.write(self.commands)

        # set bin file path
        config_data.target_params['dcd_file'] = filename

    def get_ddrc_registers(self, config_data: ConfigData) -> list:
        """Get list of DDRC register configuration. Used in code generation.

        @param config_data: processor config data
        @return: list of write commands for DDRC registers
        """
        self.create_list = True
        self.commands_list = []
        self.add_ddrc_registers(config_data)
        return self.commands_list

    def get_phy_dq_mapping(self, config_data: ConfigData) -> list:
        """Get list of PHY DQ mappings. Used in code generation.

        @param config_data: processor config data
        @return: PHY DQ mappings as list of commands
        """
        self.create_list = True
        self.commands_list = []
        for dq_mapping in config_data.dq_mapping:
            address = dq_mapping.get('address', '0')
            value = dq_mapping.get('value', '0')
            if address != 0:
                self._add_command(DCDCommandIds.CMD_WRITE_DATA, int(address, 16), int(value, 16), 32)

        return self.commands_list

    def get_phy_init_commands(self, config_data: ConfigData, pstate: Optional[int] = None,
                              add_phy_init: bool = True,
                              add_phy_init_skip_train: bool = True) -> list:
        """Get PHY init commands as list. Used for code generation.

        @param config_data: processor config data
        @param pstate: frequency point index; if None common PHY init commands will be returned
        @param add_phy_init: add phy init commands
        @param add_phy_init_skip_train: add phy init skip train commands
        @return: PHY commands as list of commands
        """
        self.create_list = True
        self.commands_list = []
        if pstate is not None:
            self._add_phy_per_pstate(config_data, pstate, add_phy_init, add_phy_init_skip_train)
        else:
            self._add_phy(config_data, add_phy_init, add_phy_init_skip_train)
        return self.commands_list

    def get_pie_init_commands(self, config_data: ConfigData, pstate: Optional[int] = None) -> list:
        """Get PIE init commands as list. Used for code generation.

        @param config_data: processor config data
        @param pstate: frequency point index; if None common PIE init commands will be returned
        @return: PIE commands as list of commands
        """
        self.create_list = True
        self.commands_list = []
        if pstate is not None:
            self._add_pie_per_pstate(config_data, pstate)
        else:
            self._add_pie(config_data)
        return self.commands_list

    def _add_target_init(self, config_data: ConfigData) -> None:
        """Add commands for target initialization params to command list.

        @param config_data: processor config data
        """
        sys_params_list = {
            Const.PARAM_S_SYS_UART: 0x10,
            Const.PARAM_S_SYS_FW_VERSION: 0x11,
            Const.PARAM_S_SYS_SM_ENABLED: 0x15
        }

        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('T'), ord('G'), ord('I'))

        # add extra system params like uart
        for key in config_data.misc_sys_params.keys():
            if key in sys_params_list:
                self._add_command(DCDCommandIds.CMD_SYS_PARAM_SET,
                                sys_params_list[key], int(config_data.misc_sys_params[key]), 32)

        # add iomux configurations
        for iomux_config in config_data.uart_iomux_config:
            address = iomux_config.get('address', '0')
            value = iomux_config.get('value', '0')
            self._add_command(DCDCommandIds.CMD_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_pmic_init(self, config_data: ConfigData) -> None:
        """Add commands for PMIC initialization params to command list.

        @param config_data: processor config data
        """
        pmic_params_list = {
            Const.PARAM_S_SYS_PMIC_CFG: 0x13,
            Const.PARAM_S_SYS_PMIC_SET: 0x14
        }

        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('P'), ord('M'), ord('I'))

        # add pmic commands
        for cmd, val in config_data.pmic_cmds:
            self._add_command(DCDCommandIds.CMD_SYS_PARAM_SET, pmic_params_list[cmd], int(val, 16), 32)

        # add pmic iomux configurations
        for iomux_config in config_data.pmic_iomux_config:
            address = iomux_config.get('address', '0')
            value = iomux_config.get('value', '0')
            self._add_command(DCDCommandIds.CMD_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_generic_iomux_init(self, config_data: ConfigData) -> None:
        """Add commands for generic IOMUX initialization params to command list.

        @param config_data: processor config data
        """
        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('G'), ord('P'), ord('C'))

        # add generic iomux configurations
        for iomux_config in config_data.generic_iomux_config:
            address = iomux_config.get('address', '0')
            value = iomux_config.get('value', '0')
            self._add_command(DCDCommandIds.CMD_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_ddrc(self, config_data: ConfigData) -> None:
        """Add DDRC commands to command list.

        @param config_data: processor config data
        """
        if not config_data.ddrc_config_full:
            return

        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('D'), ord('D'), ord('R'))
        self._add_ddrc_generic_config(config_data)
        self._add_ddrc_generic_dfi(config_data)

        if config_data.is_phy_v2(config_data.snps_phy_info):
            # timing data added to DDR section
            self._add_ddrc_timing_config(config_data)
        elif config_data.is_phy_v3(config_data.snps_phy_info):
            # timing data added to separate DT[pstate] section, for each pstate
            self._add_ddrc_timing_config_per_pstate(config_data)

    def add_ddrc_registers(self, config_data: ConfigData) -> None:
        """Add write in registers commands.

        @param config_data: processor config data
        """
        for register in config_data.ddrc_registers:
            address = register.get('address', '0')
            value = register.get('value', '0')
            name = register.get('name', '0')
            if address != 0:
                self._add_command(DCDCommandIds.CMD_WRITE_DATA, int(address, 16), int(value, 16), 32, name)

    def _add_pie(self, config_data: ConfigData) -> None:
        """Add PIE commands to command list.

        @param config_data: processor config data
        """
        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('P'), ord('I'), ord('E'))
        for address, value in config_data.phy_full_config[PhyPhase.LOAD_PIE.name]:
            self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_pie_per_pstate(self, config_data: ConfigData, pstate: int) -> None:
        """Add PIE commands to command list.

        @param config_data: processor config data
        @param pstate: frequency point index
        """
        # add PIE pstate specific section
        pstate_pie_cfg = PhyPhase.LOAD_PIE.name + str(pstate)
        if pstate_pie_cfg in config_data.phy_full_config:
            self._add_command(DCDCommandIds.CMD_START_SECTION, ord('P'), ord('I'), ord(str(pstate)))
            for address, value in config_data.phy_full_config[pstate_pie_cfg]:
                self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_diags_params(self, config_data: ConfigData) -> None:
        """Add DGS commands to command list.

        @param config_data: processor config data
        """
        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('D'), ord('G'), ord('S'))
        address = config_data.target_params['g_diags_params']
        for _param in config_data.diags_params.keys():
            if not _param.startswith("vddq_"):
                self._add_command(DCDCommandIds.CMD_WRITE_DATA, address, int(config_data.diags_params[_param], 16), 32)
            else:
                vddq_int = math.trunc(float(config_data.diags_params[_param]) * Const.VDDQ_PRECISION)
                self._add_command(DCDCommandIds.CMD_WRITE_DATA, address, vddq_int, 32)
            address += 4

    def _add_sys_params(self, config_data: ConfigData) -> None:
        """Add write commands for system configuration to command list.

        @param config_data: processor config data
        """
        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('S'), ord('Y'), ord('S'))

        # add system params from config_data
        address = config_data.target_params['g_sys_params']
        for _param in config_data.sys_params.keys():
            _param_val = config_data.sys_params[_param]
            value = 0
            if isinstance(_param_val, int):
                value = _param_val
            elif isinstance(_param_val, str):
                try:
                    value = int(_param_val, 16 if helper.has_hex_prefix(_param_val) else 10)
                except ValueError:
                    self.logger.error(f'Invalid value {_param_val} for param {_param}!')

            self._add_command(DCDCommandIds.CMD_WRITE_DATA, address, value, 32)
            address += 4

    def _add_phy(self, config_data: ConfigData,
                add_phy_init: bool = True, add_phy_init_skip_train: bool = True) -> None:
        """Add PHY commands to command list.

        @param config_data: processor config data
        @param add_phy_init: add phy init commands
        @param add_phy_init_skip_train: add phy init skip train commands
        """
        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('P'), ord('H'), ord('Y'))
        if add_phy_init:
            for address, value in config_data.phy_full_config[PhyPhase.PHY_INIT_CONFIG.name]:
                self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, int(address, 16), int(value, 16), 32)

        # skip train section will be added to the PHY dcd section
        if add_phy_init_skip_train and PhyPhase.SKIP_TRAIN_MODE.name in config_data.phy_full_config:
            for address, value in config_data.phy_full_config[PhyPhase.SKIP_TRAIN_MODE.name]:
                self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_phy_per_pstate(self, config_data: ConfigData, pstate: int,
                            add_phy_init: bool = True, add_phy_init_skip_train: bool = True) -> None:
        """Add pstate PHY commands to command list.

        @param config_data: processor config data
        @param pstate: frequency point index
        @param add_phy_init: add phy init commands
        @param add_phy_init_skip_train: add phy init skip train commands
        """
        # add PHY pstate specific section
        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('P'), ord('H'), ord(str(pstate)))
        if add_phy_init:
            pstate_phy_init_cfg = PhyPhase.PHY_INIT_CONFIG.name + str(pstate)
            if pstate_phy_init_cfg in config_data.phy_full_config:
                for address, value in config_data.phy_full_config[pstate_phy_init_cfg]:
                    self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, int(address, 16), int(value, 16), 32)

        if add_phy_init_skip_train:
            pstate_phy_init_skip_train_cfg = PhyPhase.SKIP_TRAIN_MODE.name + str(pstate)
            if pstate_phy_init_skip_train_cfg in config_data.phy_full_config:
                for address, value in config_data.phy_full_config[pstate_phy_init_skip_train_cfg]:
                    self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, int(address, 16), int(value, 16), 32)

    def _add_ddrc_generic_config(self, config_data: ConfigData) -> None:
        """Add DDRC config commands to command list.

        @param config_data: processor config data
        """
        for command in config_data.ddrc_config_full:
            if int(command["op_code"], 16) < DCDCommandIds.CMD_FREQ0_WRITE_DATA:
                try:
                    self._add_command(int(command["op_code"], 16),
                                      int(command["address"], 16),
                                      int(command["value"], 16),
                                      int(command["size"], 16))
                except ValueError:
                    self.logger.error('Unable to process config command %s', command)

    def _add_ddrc_generic_dfi(self, config_data: ConfigData) -> None:
        """Add DDRC DFI commands to command list.

        @param config_data: processor config data
        """
        for command in config_data.ddrc_config_full:
            cmd_opcode = int(command["op_code"], 16)
            if (cmd_opcode >= DCDCommandIds.CMD_FREQ0_WRITE_DATA) and (cmd_opcode < DCDCommandIds.CMD_FREQ0_SET_TIMING):
                try:
                    self._add_command(int(command["op_code"], 16),
                                      int(command["address"], 16),
                                      int(command["value"], 16),
                                      int(command["size"], 16))
                except ValueError:
                    self.logger.error('Unable to process config command %s', command)

    def _add_ddrc_timing_config(self, config_data: ConfigData) -> None:
        """Add DDRC timing config commands to command list.

        @param config_data: processor config data
        """
        for command in config_data.ddrc_config_full:
            if int(command["op_code"], 16) >= DCDCommandIds.CMD_FREQ0_SET_TIMING:
                try:
                    self._add_command(int(command["op_code"], 16),
                                      int(command["address"], 16),
                                      int(command["value"], 16),
                                      int(command["size"], 16))
                except ValueError:
                    self.logger.error('Unable to process config command %s', command)

    def _add_ddrc_timing_config_per_pstate(self, config_data: ConfigData) -> None:
        """Add DDRC timing config commands for each initialized frequency point to command list.

        @param config_data: processor config data
        """
        for pstate in range(config_data.num_pstates):
            if pstate not in config_data.ddrc_timings:
                continue
            if not config_data.ddrc_timings[pstate]:
                continue

            self._add_command(DCDCommandIds.CMD_START_SECTION, ord('D'), ord('T'), ord(str(pstate)))
            for command in config_data.ddrc_timings[pstate]:
                try:
                    self._add_command(int(command["op_code"], 16), int(command["address"], 16),
                        int(command["value"], 16), int(command["size"], 16))
                except ValueError:
                    self.logger.error('Unable to process config command %s', command)

    def _add_errata(self, errata, name=None):  # type: ignore
        """Add DCD commands to self.

        Command structure is [command, address, value].
        'command' is from DCDCommands.
        @param errata: Array of DCD write commands
        """
        if self.create_list and name is not None:
            self.commands_list.append(name)
        for command in errata:
            self._add_command(command[0], command[1], command[2], self._SIZE_PHY_PARAM_BITS)

    def _add_extra_msb(self, config_data: ConfigData) -> None:
        """Add extra write commands for each pstate.

        @param config_data: processor config data
        """
        num_pstates = int(config_data.num_pstates)
        for pstate in range(1, num_pstates):
            self._add_command(DCDCommandIds.CMD_START_SECTION, ord('M'), ord('B'), ord('0') + pstate)
            dmem_info = f'{PhyPhase.LOAD_DMEM_1D.name}{pstate}'
            if dmem_info in config_data.phy_full_config:
                for addr, val in config_data.phy_full_config[dmem_info]:
                    address = int(addr, 16)
                    value = int(val, 16)
                    self._add_command(DCDCommandIds.CMD_PHY_WRITE_DATA, address, value, self._SIZE_PHY_PARAM_BITS)

    def _add_quick_boot_registers(self, config_data: ConfigData) -> None:
        """Add Quick Boot registers section (address of registers used to collect QuickBoot data).

        @param config_data: processor config data
        """
        if config_data.sys_params[Const.PARAM_S_SYS_FUNCTION] != Const.PHY_FIRST_BOOT:
            return

        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('Q'), ord('B'), ord('R'))
        for address in config_data.quick_boot_registers:
            self._add_value(int(address, 16))

        # align section to command size
        self._add_padding_to_align(len(config_data.quick_boot_registers))

    def _add_quick_boot_data(self, config_data: ConfigData) -> None:
        """Add Quick Boot data section.

        @param config_data: processor config data
        """
        if config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) != Const.PHY_QUICK_BOOT:
            return

        self._add_command(DCDCommandIds.CMD_START_SECTION, ord('Q'), ord('B'), ord('D'))
        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            for address, value in config_data.quick_boot_data:
                self._add_value(int(value, 16))

            # align section to command size
            self._add_padding_to_align(len(config_data.quick_boot_data))
        elif ConfigData.is_phy_v3(config_data.snps_phy_info):
            for value in config_data.quick_boot_acsm:
                self._add_value(value)

            # align section to command size
            self._add_padding_to_align(len(config_data.quick_boot_acsm))

    def _add_padding_to_align(self, size: int, size_to_align: int = 4) -> None:
        """Add padding bytes to align to command size (for now, a command is stored on 4 ints).

        @param size: size of the section to be align
        @param size_to_align: align size
        """
        remainder = size % size_to_align
        if remainder != 0:
            no_padding_ints = size_to_align - remainder
            for idx in range(0, no_padding_ints):
                self.commands += struct.pack("<I", int('0x0', 16))
