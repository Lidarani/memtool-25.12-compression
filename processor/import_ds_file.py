# Copyright 2020-2025 NXP
"""TODO:summary line."""
import logging
import re
from enum import Enum

from memtool.common.config_data import ConfigData, SnpsFirmware
from memtool.common.dcd_commands import DCDCommandIds, get_dcd_command
from memtool.common.factories import ProcessorFactory
from memtool.utils.constants import Const


class DSImporter:
    """Class for handling updating parameters based on data from ds file."""

    logger = logging.getLogger(__name__)

    @staticmethod
    def set_read_write_odt(params, dram_wrodt, dram_rdodt):  # type: ignore
        """Update ODT in params message blocks."""
        for rank in range(0, 4):
            value = 0
            value = value | dram_wrodt[rank]

            value = value | dram_rdodt[rank] << 4
            params[Const.PARAM_S_PHY]['messageBlock[0]'][f'AcsmOdtCtrl{str(rank)}'] = f'0x{value:x}'
            params[Const.PARAM_S_PHY]['messageBlock[1]'][f'AcsmOdtCtrl{str(rank)}'] = f'0x{value:x}'
            params[Const.PARAM_S_PHY]['messageBlock[2]'][f'AcsmOdtCtrl{str(rank)}'] = f'0x{value:x}'
            params[Const.PARAM_S_PHY]['messageBlock[3]'][f'AcsmOdtCtrl{str(rank)}'] = f'0x{value:x}'

    def update_phy_cs_parameters(self, config_data: ConfigData, dram_type, cs_present=None):  # type: ignore
        """TODO:summary line."""
        # Calculate DDR component number of bytes and number of bytes per DF based on data_width Synopsys parameter
        params = config_data.params

        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            ddr_data_width = int(params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['DramDataWidth'])
            if ddr_data_width is None or ddr_data_width not in (16, 32, 64, 72):
                self.logger.error("[RPADescriptor] Unable to find bus width parameter!")
                return

            num_bytes = int(ddr_data_width / 8)

            params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]["NumDbyte"] = str(num_bytes)

            num_channels = 2 if (dram_type == "lpddr4" and ddr_data_width == 32) else 1

            num_active_bytes_dfi = int(num_bytes / num_channels)
            params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['NumActiveDbyteDfi0'] = str(num_active_bytes_dfi)
            if num_channels == 2:
                params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['NumActiveDbyteDfi1']\
                    = str(num_active_bytes_dfi)
                params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['Dfi1Exists'] = '1'
            else:
                params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['NumActiveDbyteDfi1'] = '0'
                if dram_type == "lpddr4":
                    params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['Dfi1Exists'] = '0'

            # Calculate DDR component number of ranks in the DFI0, 1 based on csPresent
            # and data_width Synopsys parameters
            if cs_present is None:
                self.logger.error("[RPADescriptor] Unable to find csPresent parameter!")
                return

            # in case no CS is populated we have 1 rank per DFI
            num_ranks_dfi0 = bin(cs_present).count('1')
            params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['NumRank_dfi0'] = str(num_ranks_dfi0)
            if num_channels == 2:
                num_ranks_dfi1 = num_ranks_dfi0
                params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['NumRank_dfi1'] = str(num_ranks_dfi1)
            else:
                params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['NumRank_dfi1'] = '0'

        if dram_type == "ddr4":
            # set CsPresentD0 equal to CsPresent
            params[Const.PARAM_S_PHY]["messageBlock[0]"]['CsPresentD0'] = \
                params[Const.PARAM_S_PHY]["messageBlock[1]"]['CsPresentD0'] = \
                params[Const.PARAM_S_PHY]["messageBlock[2]"]['CsPresentD0'] = \
                params[Const.PARAM_S_PHY]["messageBlock[3]"]['CsPresentD0'] = str(cs_present)

    @staticmethod
    def update_connection_parameters(config_data: ConfigData):  # type: ignore
        """Update ddr type and firmware with data from the imported .ds file."""
        # start regexes with \n to avoid matches on commented lines
        re1 = re.search(r"\nddrparam\s+set\s+dram_type\s+[0-9]+", config_data.ds_file_txt)
        config_data.dram_type = int(re1.group(0).split()[3])  # type: ignore
        re1 = re.search(r"\nddrparam\s+set\s+lp[4-5]+x_mode\s+[0x|0X]*[0-9]+", config_data.ds_file_txt)
        if re1 is not None:
            value = re1.group(0).split()[3]
            base = 16 if value.lower().startswith('0x') else 10
            config_data.lp_mode = int(value, base)
        else:
            config_data.lp_mode = 0
        # based on dram type and lp mode compute memory type
        config_data.set_memory_type()

        # if:
        #     config_data.dram_type = int(re1.group(0).split()[3])
        #     config_data.mem_type = config_data.DDR_TYPES[config_data.dram_type]
        # else:
        #     raise RuntimeError("\'dram_type\' parameter could not be found in the imported .ds file!")

        if ConfigData.is_phy_v2(config_data.snps_phy_info) or \
            (config_data.snps_phy_info == SnpsFirmware.SnpsFW_Undefined):
            re1 = re.search(r"\nsysparam\s+set\s+fw_version\s+[0-9]+", config_data.ds_file_txt)
            if re1 is not None:
                config_data.snps_phy_info = SnpsFirmware.from_id(int(re1.group(0).split()[3]))

        re1 = re.search(r"\nddrparam\s+set\s+data_width\s+[0-9]+", config_data.ds_file_txt)
        if re1 is not None:
            config_data.data_width = int(re1.group(0).split()[3])

        re1 = re.search(r"\nddrparam\s+set\s+ssc\s+[0-9]+", config_data.ds_file_txt)
        if re1 is not None:
            config_data.ssc = int(re1.group(0).split()[3])
            config_data.sys_params['ss_enable'] = f'{config_data.ssc}'


    def update_ddrc_config(self, config_data: ConfigData):  # type: ignore
        """Update DDR controller configuration in params from DS file.

        @param config_data: processor config data
        """
        re1 = re.search(r"#\s+Version\s+[0-9][.]?[0-9]?", config_data.ds_file_txt)
        config_data.rpa_version = re1.group(0).split()[2]  # type: ignore

        re1 = re.search(r"\nddrparam\s+set\s+num_pstat\s+[0-9]", config_data.ds_file_txt)
        config_data.num_pstates = int(re1.group(0).split()[3])  # type: ignore
        config_data.sys_params['num_pstates'] = f'{config_data.num_pstates}'

        # TODO need to understand the relation between NumPstates and CfgPStates and FirstPState
        if config_data.is_phy_v3(config_data.snps_phy_info):
            cfg_pstates = 0  # CfgPStates should contain a number of '1' equal with the number of pstates
            idx = config_data.num_pstates - 1
            while idx >= 0:
                cfg_pstates = cfg_pstates | (1 << idx)
                idx -= 1
            config_data.params[Const.PARAM_S_PHY]["userInputBasic"]['CfgPStates'] = f'{cfg_pstates}'

        # train_2d not available for DDR3 but should be present for the other DDR types
        if config_data.dram_type != 1 and config_data.is_phy_v2(config_data.snps_phy_info):
            re1 = re.search(r"\nddrparam\s+set\s+train_2d\s+[0-9]", config_data.ds_file_txt)
            train2d_str = re1.group(0).split()[3]  # type: ignore
            config_data.train_2d = train2d_str  # type: ignore
        else:
            config_data.train_2d = "0"  # type: ignore
        dram_type = config_data.DRAM_TYPES[config_data.dram_type]

        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        is_imx8 = processor.processor_info.is_imx8()

        is_ddr5 = config_data.is_ddr5(config_data.mem_type)
        freq_multiplier = 1 if is_imx8 else (8 if is_ddr5 else 2)
        for i in range(4):
            # look for frequencies 0 to 3 and parse them whether they are expressed af ints or floats
            re1 = re.search(rf"\nddrparam\s+set\s+frequency{i}\s+\d+(\.)?\d+", config_data.ds_file_txt)
            if re1 is not None:
                config_data.freq[i] = float(re1.group(0).split()[3])
                config_data.sys_params[f'freq_{i}'] = int(config_data.freq[i] * freq_multiplier)
                self.logger.debug(f'freq_{i} set to {int(config_data.freq[i] * freq_multiplier)}')

        # reset configuration in params
        config_data.ddrc_config_full = []
        config_data.ddrc_registers = []
        config_data.dq_mapping = []
        config_data.pmic_cmds = []
        config_data.ddrc_timings = {}

        # Sensitive regions from ds file for data configuration.
        class DS_REGION(Enum):
            """TODO:summary line."""

            NONE = 0
            DDRC_CONFIG = 1
            RESET_DDRC = 2
            DDR_PHY_DQ_LANE = 3
            DDR_PARAM_SETTINGS = 4
            UART_IOMUX_CONFIG = 5
            PMIC_IOMUX_CONFIG = 6
            PMIC_CONFIG = 7
            GENERIC_IOMUX_CONFIG = 8
            DDRC_CUSTOM_CONFIG = 9

        ds_region = DS_REGION.NONE
        ds_map = processor.processor_info.get_ds_map()

        def _is_ddrc_config_start(_line: str) -> bool:
            return (ds_region is not DS_REGION.DDRC_CONFIG) and _line.startswith('#') and 'DDRC configuration' in _line

        def _is_reset_ddrc_start(_line: str) -> bool:
            return (ds_region is not DS_REGION.RESET_DDRC) and '#RESET DDRC' in _line

        def _is_dq_mapping_start(_line: str) -> bool:
            return (ds_region is not DS_REGION.DDR_PHY_DQ_LANE) and _line.startswith('#') and 'PHY DQ lane' in _line

        def _is_ddr_param_settings_start(_line: str) -> bool:
            return ((ds_region is not DS_REGION.DDR_PARAM_SETTINGS)
                    and _line.startswith('#') and 'DDR parameter settings' in _line)

        def _is_ddrc_config_enable(_line: str) -> bool:
            return _line.startswith('#') and 'enable memory controller' in _line

        def _is_ddrc_sdram_cfg_set(_line: str) -> bool:
            return _line.startswith('memory set') and 'DDR_SDRAM_CFG' in _line and 'DDR_SDRAM_CFG_' not in _line

        def _is_uart_iomux_config_start(_line: str) -> bool:
            return _line.startswith(Const.PARAM_S_BOARD_CONFIG_UART_IOMUX_SECTION)

        def _is_pmic_iomux_config_start(_line: str) -> bool:
            return _line.startswith(Const.PARAM_S_BOARD_CONFIG_PMIC_IOMUX_SECTION)

        def _is_pmic_config_start(_line: str) -> bool:
            return _line.startswith(Const.PARAM_S_BOARD_CONFIG_PMIC_COMMANDS_SECTION)

        def _is_generic_iomux_config_start(_line: str) -> bool:
            return _line.startswith(Const.PARAM_S_BOARD_CONFIG_GENERIC_IOMUX_SECTION)

        def _is_ddrc_custom_config_start(_line: str) -> bool:
            return _line.startswith(Const.PARAM_S_DDRC_CUSTOM_CONFIG_SECTION)

        def _is_dram_param_set(_line: str) -> bool:
            return _line.startswith('dramparam set')

        for line in config_data.ds_file_txt.split('\n'):
            if not line.strip():
                continue  # skip empty line

            # update DDR controller configuration sequence.
            if line.startswith('memory') or line.startswith("freq"):
                cmd_line = line.split()
                command = f"{cmd_line[0]} {cmd_line[1]}"
                try:
                    reg_name = cmd_line[5].replace("#", "")
                except Exception:
                    reg_name = "#NA"
                cmd = {
                    'op_code': f'0x{get_dcd_command(command):x}',
                    'address': cmd_line[2],
                    'value': cmd_line[4],
                    'size': hex(int(cmd_line[3], 10)),
                    'name': reg_name
                }

                if ds_region is DS_REGION.UART_IOMUX_CONFIG:
                    config_data.uart_iomux_config.append(cmd)
                elif ds_region is DS_REGION.PMIC_IOMUX_CONFIG:
                    config_data.pmic_iomux_config.append(cmd)
                elif ds_region is DS_REGION.GENERIC_IOMUX_CONFIG:
                    config_data.generic_iomux_config.append(cmd)
                else:
                    config_data.ddrc_config_full.append(cmd)
                    if ds_region in [DS_REGION.DDRC_CONFIG, DS_REGION.DDRC_CUSTOM_CONFIG]:
                        config_data.ddrc_registers.append(cmd)
                        if _is_ddrc_sdram_cfg_set(line):
                            config_data.params['DDR_SDRAM_CFG'] = cmd_line[4]
                    elif ds_region is DS_REGION.DDR_PHY_DQ_LANE:
                        config_data.dq_mapping.append(cmd)
                    elif ds_region is DS_REGION.DDR_PARAM_SETTINGS:
                        cmd_opcode = int(cmd['op_code'], 16)
                        if (cmd_opcode >= DCDCommandIds.CMD_FREQ0_SET_TIMING)\
                                and (cmd_opcode <= DCDCommandIds.CMD_FREQ3_SET_TIMING):
                            re_fp_idx = re.search(r"freq[0-9]+", cmd_line[0])
                            if re_fp_idx is not None:
                                fp_idx = int(re_fp_idx.group(0).replace("freq", ""), 10)
                                if fp_idx not in config_data.ddrc_timings:
                                    config_data.ddrc_timings[fp_idx] = []
                                config_data.ddrc_timings[fp_idx].append(cmd)

            elif line.startswith('sysparam'):
                cmd = line.split()  # type: ignore
                if ds_region is DS_REGION.PMIC_CONFIG:
                    if cmd[2] in ['pmic_cfg', 'pmic_set']:  # type: ignore
                        config_data.pmic_cmds.append((f'{cmd[2]}', f'{cmd[3]}'))  # type: ignore
                else:
                    if cmd[2] in ds_map[dram_type].keys():  # type: ignore
                        config_data.misc_sys_params[cmd[2]] = cmd[3]  # type: ignore

            elif _is_ddrc_config_start(line):
                ds_region = DS_REGION.DDRC_CONFIG
                processor.add_ddrc_before_config_errata(config_data)

            elif _is_reset_ddrc_start(line):
                ds_region = DS_REGION.RESET_DDRC

            elif _is_dq_mapping_start(line):
                ds_region = DS_REGION.DDR_PHY_DQ_LANE

            elif _is_ddr_param_settings_start(line):
                ds_region = DS_REGION.DDR_PARAM_SETTINGS

            elif _is_ddrc_config_enable(line):
                processor.add_ddrc_after_config_errata(config_data)

            elif _is_uart_iomux_config_start(line):
                ds_region = DS_REGION.UART_IOMUX_CONFIG

            elif _is_pmic_iomux_config_start(line):
                ds_region = DS_REGION.PMIC_IOMUX_CONFIG

            elif _is_pmic_config_start(line):
                ds_region = DS_REGION.PMIC_CONFIG

            elif _is_generic_iomux_config_start(line):
                ds_region = DS_REGION.GENERIC_IOMUX_CONFIG

            elif _is_ddrc_custom_config_start(line):
                ds_region = DS_REGION.DDRC_CUSTOM_CONFIG

            elif _is_dram_param_set(line):
                cmd = line.split()  # type: ignore
                config_data.params[Const.PARAM_S_BASIC][cmd[2]] = cmd[3].split('.')[0]  # type: ignore

        # make sure that correct pmic commands are applied
        config_data.update_apply_pmic_policy()

        # apply errata
        processor.add_ddrc_after_enable_errata(config_data)

    def update_phy_config(self, config_data: ConfigData):  # type: ignore
        """Update config data based on ds file data."""
        dram_type = config_data.DRAM_TYPES[config_data.dram_type]

        cs_present = None
        wr_odt = [0, 0, 0, 0]
        rd_odt = [0, 0, 0, 0]

        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        ds_map = processor.processor_info.get_ds_map()

        for line in config_data.ds_file_txt.split('\n'):
            # update phy_config
            if line.startswith('ddrparam set'):
                cmd = line.split()
                if cmd[2] in ds_map[dram_type].keys():
                    cat, param = ds_map[dram_type][cmd[2]].split('.')

                    # only update settings that already exist in configuration
                    if cat in config_data.params[Const.PARAM_S_PHY]\
                            and param in config_data.params[Const.PARAM_S_PHY][cat]:
                        config_data.params[Const.PARAM_S_PHY][cat][param] = cmd[3]

                if cmd[2].startswith('wrODT'):
                    wr_odt[int(cmd[2][-1:])] = int(cmd[3])
                elif cmd[2].startswith('rdODT'):
                    rd_odt[int(cmd[2][-1:])] = int(cmd[3])
                elif cmd[2] == 'csPresent':
                    cs_present = int(cmd[3], 16)

        # test param has the highest priority, they should not be overwritten with the values read from ds file
        if Const.PARAM_S_APP in config_data.params:
            if Const.OVERWRITE_TEST_PARAMS in config_data.params[Const.PARAM_S_APP]:
                # update train 2D params
                if Const.PARAM_S_SYS_TRAIN_2D in config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS]:
                    train2d\
                        = config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS][Const.PARAM_S_SYS_TRAIN_2D]
                    config_data.train_2d = train2d

        self.update_phy_cs_parameters(config_data, dram_type, cs_present=cs_present)

        if dram_type == "ddr4":
            self.set_read_write_odt(config_data.params, dram_wrodt=wr_odt, dram_rdodt=rd_odt)
            config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["EnabledDQs"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[1]"]["EnabledDQs"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[2]"]["EnabledDQs"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[3]"]["EnabledDQs"] = \
                config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]["DramDataWidth"]

        if dram_type in ["lpddr4", "lpddr5"]:
            no_mr = 24 if dram_type == "lpddr4" else 41
            no_mb = config_data.num_pstates
            for mr in range(0, no_mr + 1):
                mr_a0_key = f"MR{mr}_A0"
                mr_a1_key = f"MR{mr}_A1"
                mr_b0_key = f"MR{mr}_B0"
                mr_b1_key = f"MR{mr}_B1"
                for mb in range(0, no_mb):
                    mb_dictionary = config_data.params[Const.PARAM_S_PHY][f"messageBlock[{mb}]"]
                    rank0_configured = mr_a0_key in mb_dictionary
                    if rank0_configured:
                        mr_a0_value = mb_dictionary[mr_a0_key]
                        mb_dictionary[mr_b0_key] = mr_a0_value

                        mr_a1_value = mr_a0_value
                        rank1_configured_in_rpa = f"messageBlock[{mb}].{mr_a1_key}" in ds_map[dram_type].values()
                        if rank1_configured_in_rpa:
                            if mr_a1_key not in mb_dictionary:
                                self.logger.error(f"Expected value for {mr_a1_key} could not be found!")
                            else:
                                mr_a1_value = mb_dictionary[mr_a1_key]
                        mb_dictionary[mr_a1_key] = mr_a1_value
                        mb_dictionary[mr_b1_key] = mr_a1_value

        if ConfigData.is_phy_v3(config_data.snps_phy_info):
            # update MsgMisc (= "userInputBasic.NumRank_dfi0")
            num_ranks_val = -1
            if Const.PARAM_S_PHY in config_data.params:
                if Const.PARAM_S_PHY_INPUT_BASIC in config_data.params[Const.PARAM_S_PHY]:
                    if "NumRank_dfi0" in config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]:
                        num_ranks_str = \
                            config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]["NumRank_dfi0"]
                        num_ranks_val = int(num_ranks_str, 16)
            if num_ranks_val < 0:
                self.logger.error("Expected value for userInputBasic.NumRank could not be found!")
            else:
                msg_misc_value = "0x40" if (num_ranks_val == 2) else "0x0"
                for mb in range(0, config_data.num_pstates):
                    config_data.params[Const.PARAM_S_PHY][f"messageBlock[{mb}]"]["MsgMisc"] = msg_misc_value

        if Const.PARAM_S_PHY_MB_X8MODE in ds_map[dram_type].keys():
            config_data.params[Const.PARAM_S_PHY]["messageBlock[1]"]["X8Mode"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["X8Mode"]
            config_data.params[Const.PARAM_S_PHY]["messageBlock[2]"]["X8Mode"] = \
                config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["X8Mode"]

        # not all ddr types have all 4 message blocks; find the actual number
        max_msgblk = 0
        for i in (3, 2, 1, 0):  # iterate all possible max messageBlock IDs
            if config_data.params[Const.PARAM_S_PHY].get(f'messageBlock[{i}]', None):
                max_msgblk = i
                break
        if max_msgblk > 0:
            max_msgblk += 1  # will be used in range() function

        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            base_val = config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyVref"]
            for i in range(1, max_msgblk):
                config_data.params[Const.PARAM_S_PHY][f'messageBlock[{i}]']["PhyVref"] = base_val

            for i in range(1, max_msgblk):
                config_data.params[Const.PARAM_S_PHY][f'messageBlock[{i}]']["PhyOdtImpedance"] = "0x0"

            for i in range(1, max_msgblk):
                config_data.params[Const.PARAM_S_PHY][f'messageBlock[{i}]']["PhyDrvImpedance"] = "0x0"

            config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[1]"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[2]"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[3]"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[0]"]
            config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[1]"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[2]"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[3]"] = \
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[0]"]
        elif ConfigData.is_phy_v3(config_data.snps_phy_info):
            if dram_type == "lpddr4":
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceAc[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceAc[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceAc[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCk[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCk[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCk[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDTO[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDTO[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDTO[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCKE[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCKE[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCKE[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCs[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCs[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCs[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDq[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDq[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDq[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDqs[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDqs[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDqs[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCa[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCa[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCa[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCk[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCk[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCk[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDq[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDq[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDq[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDqs[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDqs[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDqs[0]"]
            elif dram_type == "lpddr5":
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceAc[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceAc[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceAc[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCk[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCk[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceCk[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDq[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDq[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDq[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDqs[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDqs[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceDqs[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCa[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCa[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCa[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCk[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCk[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["OdtImpedanceCk[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDq[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDq[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDq[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDqs[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDqs[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceDqs[0]"]
                config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceWCK[1]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceWCK[2]"] = \
                    config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedanceWCK[0]"]

        ds_log_level = config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["HdtCtrl"]
        # TODO: sometimes config_data.phy_log is str, other times it is int, see if this is ok
        if isinstance(config_data.phy_log, str):
            phy_log = int(config_data.phy_log, 16)
        else:
            phy_log = config_data.phy_log
        if int(ds_log_level, 16) > phy_log:
            config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["HdtCtrl"] = config_data.phy_log
        else:
            config_data.phy_log = config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["HdtCtrl"]

        base_val = config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["HdtCtrl"]
        for i in range(1, max_msgblk):
            config_data.params[Const.PARAM_S_PHY][f'messageBlock[{i}]']["HdtCtrl"] = base_val

    def update_ds_file_ddrc_config(self, config_data: ConfigData, regs):  # type: ignore
        """Update DDR controller configuration in params from DS file.

        @param config_data: processor config data
        """
        for line in config_data.ds_file_txt.split('\n'):
            # update DDR controller configuration sequence.
            if line.startswith('memory'):
                cmd_line = line.split()
                if cmd_line[2] in regs.keys():
                    cmd_mask = regs[cmd_line[2]]
                    if cmd_line[5] == '#DDR_SDRAM_CFG':
                        cmd = (regs[cmd_line[2]]).replace('0x', '')
                        cmd_mask = '0x%08X' % (int(cmd, 16) & 0x7FFFFFFF)
                    elif cmd_line[5] in {'#CS0_CONFIG', '#CS1_CONFIG', '#CS2_CONFIG', '#CS3_CONFIG'}:
                        cmd = (regs[cmd_line[2]]).replace('0x', '')
                        cmd_mask = '0x%08X' % (int(cmd, 16) & 0x7FFFFFFF)
                    newline = line.replace(cmd_line[4], cmd_mask)
                    config_data.ds_file_txt = config_data.ds_file_txt.replace(line, newline)
            elif line.startswith('ddrparam'):
                cmd_line = line.split()
                if cmd_line[2] in regs.keys():
                    newline = line.replace(cmd_line[3], regs[cmd_line[2]])
                    config_data.ds_file_txt = config_data.ds_file_txt.replace(line, newline)
