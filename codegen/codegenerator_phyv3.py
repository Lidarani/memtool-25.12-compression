# Copyright 2023-2025 NXP
"""Generate code for targets with PHY v3 firmware."""
import json
import logging
import os

from memtool import __version__
from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import DCDCommand, DCDCommandIds
from memtool.common.options import Options
from memtool.processor.base_processor import BaseProcessor
from memtool.utils.constants import Const
from memtool.utils.helper import get_current_year

from .addr_decoder import PhyAddrIMX95Decoder
from .codegenerator import CodeGenerator, indent_block

logger = logging.getLogger(__name__)


def add_phy_init_reg_names(config: str, phy_init_reg_names: dict) -> str:
    """Add phy init register names to the given configuration.

    @param config: configuration without register info
    @param phy_init_reg_names: phy init registers map
    @return: configuration with register info
    """
    updated_config = ''
    config_list = config.split('\n')
    for cfg in config_list:
        cmd = cfg.replace('{', '').replace('}', '').split(',')
        updated_config += cfg
        if cmd[0] in phy_init_reg_names:
            updated_config += f'{Const.indent}// {phy_init_reg_names[cmd[0]]}'
        updated_config += '\n'
    return updated_config


class CodeGeneratorPHYv3(CodeGenerator):
    """Generate timing data for targets with PHY v3 firmware."""

    MR_LPDDR4 = ["0x01", "0x02", "0x03", "0x0b", "0x0c", "0x0e", "0x16"]
    MR_LPDDR5 = ["0x01", "0x02", "0x03", "0x0a", "0x0b", "0x0c", "0x0d", "0x0e", "0x0f",
                 "0x10", "0x11", "0x12", "0x13", "0x14", "0x15", "0x16", "0x18", "0x1C", "0x29"]

    MR_LIST = {'lpddr4': MR_LPDDR4, 'lpddr4x': MR_LPDDR4, 'lpddr5': MR_LPDDR5, 'lpddr5x': MR_LPDDR5}

    def __init__(self, _config_data: ConfigData, _processor: BaseProcessor):
        """Constructor.

        @param _config_data: processor config data
        @param _processor: processor
        """
        super(CodeGeneratorPHYv3, self).__init__(_config_data, _processor)

    def generate_timing(self) -> str:
        """Prepare timing file contents.

        @return: timing file contents as a string
        """
        logger.debug("Generate timing file")

        skip_train = Options.get_instance().get_snps_phy_init_options().get_phy_init_option()

        phy_init_reg_names = {}
        emu_folder = os.path.join(self.config_data.data_dir, Const.EMU_MASK_DIR_NAME)
        if os.path.exists(emu_folder):  # just to determine if an emulator is used
            phy_init_reg_names = self.config_data.get_phy_init_reg_names_hash()

        num_pstates = self.config_data.num_pstates
        message_block_1d = ''
        fsp_msg_1d = ''
        dram_fsp_cfg = ''

        dram_rate = []
        dram_rate_list = ''

        struct = "static struct"

        for pstate in range(0, num_pstates):
            freq = self.config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC].get(
                        f"Frequency[{pstate}]", 0)
            if self.config_data.mem_type in ['lpddr5', 'lpddr5x']:
                dram_rate.append(int(float(freq) * 8))
            else:
                dram_rate.append(int(float(freq) * 2))
            dram_rate_list += str(dram_rate[pstate]) + ', '

            if pstate >= len(self.config_data.message_block_tmg_1d):
                logger.error('message_block_tmg_1d for pstate %d does not exist!', pstate)
                continue

            if phy_init_reg_names:
                pstate_message_block_tmg_1d = add_phy_init_reg_names(
                                                self.config_data.message_block_tmg_1d[pstate],
                                                phy_init_reg_names)
            else:
                pstate_message_block_tmg_1d = self.config_data.message_block_tmg_1d[pstate]

            message_block_1d += f"""
/* P{pstate} message block parameter for training firmware */
{struct} ddrphy_cfg_param ddr_phy_msgh_fsp{pstate}_cfg[] = {{
{indent_block(f'''{pstate_message_block_tmg_1d}''', 1, False)}}};
"""

        # PLL bypass
        pll_bypass = self.config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]['PllBypass[0]']

        # Spread spectrum
        ss_enable = str(self.config_data.ssc == 1).lower()

        # Set copyright year
        INITIAL_COPYRIGHT_YEAR = Const.INITIAL_COPYRIGHT_YEAR.get(self.config_data.soc_name, None)
        current_year = get_current_year()

        copyright_year = (f"{INITIAL_COPYRIGHT_YEAR}-{current_year}" if INITIAL_COPYRIGHT_YEAR != str(current_year)
                          else f"{current_year}")
        
        # Set DDR part number
        ddr_part_number = self.config_data.params.get('ddrPartNumber', '').strip() or "Unknown"
        ddr_part_number_str = f'Part number: {ddr_part_number}'

        if num_pstates > 1:
            for pstate in range(1, num_pstates):
                fsp_msg_1d += f"""{{
{indent_block(f'''/* P{pstate} {dram_rate[pstate]}mts */
.drate = {dram_rate[pstate]},
.ssc = {ss_enable},
.fsp_phy_cfg = ddr_phy_fsp{pstate}_cfg,
.fsp_phy_cfg_num = ARRAY_SIZE(ddr_phy_fsp{pstate}_cfg),
.fw_type = FW_1D_IMAGE,
{f".fsp_phy_prog_csr_ps_cfg = ddr_phy_prog_csr_ps_fsp{pstate}_cfg," if skip_train != 0 else ""}
{f".fsp_phy_prog_csr_ps_cfg_num = ARRAY_SIZE(ddr_phy_prog_csr_ps_fsp{pstate}_cfg)," if skip_train != 0 else ""}
.fsp_phy_msgh_cfg = ddr_phy_msgh_fsp{pstate}_cfg,
.fsp_phy_msgh_cfg_num = ARRAY_SIZE(ddr_phy_msgh_fsp{pstate}_cfg),
.fsp_phy_pie_cfg = ddr_phy_pie_fsp{pstate}_cfg,
.fsp_phy_pie_cfg_num = ARRAY_SIZE(ddr_phy_pie_fsp{pstate}_cfg),''', 1, False)}
"""
        fsp_msg_1d += f"""{{
{indent_block(f'''/* P{0} {dram_rate[0]}mts */
.drate = {dram_rate[0]},
.ssc = {ss_enable},
.fsp_phy_cfg = ddr_phy_fsp{0}_cfg,
.fsp_phy_cfg_num = ARRAY_SIZE(ddr_phy_fsp{0}_cfg),
.fw_type = FW_1D_IMAGE,
{f".fsp_phy_prog_csr_ps_cfg = ddr_phy_prog_csr_ps_fsp{0}_cfg," if skip_train != 0 else ""}
{f".fsp_phy_prog_csr_ps_cfg_num = ARRAY_SIZE(ddr_phy_prog_csr_ps_fsp{0}_cfg)," if skip_train != 0 else ""}
.fsp_phy_msgh_cfg = ddr_phy_msgh_fsp{0}_cfg,
.fsp_phy_msgh_cfg_num = ARRAY_SIZE(ddr_phy_msgh_fsp{0}_cfg),
.fsp_phy_pie_cfg = ddr_phy_pie_fsp{0}_cfg,
.fsp_phy_pie_cfg_num = ARRAY_SIZE(ddr_phy_pie_fsp{0}_cfg),''', 1, False)}

}},
"""
        dram_fsp_cfg += f"""{{
{indent_block(f'''.ddrc_cfg = ddr_dram_fsp_ddrc_cfg,
.ddrc_cfg_num = ARRAY_SIZE(ddr_dram_fsp_ddrc_cfg),
.mr_cfg = ddr_dram_fsp_mr_cfg,
.mr_cfg_num = ARRAY_SIZE(ddr_dram_fsp_mr_cfg),
.bypass = {pll_bypass},''', 1, False)}
}},
"""
        # DDRC timings
        ddrc_timings_per_pstate = []
        # for now, only for IMX93 & IMX95(lpddr4, lpddr4x, lpddr5, lpddr5x) we have support for timing in RPA
        if (self.config_data.mem_type in ['lpddr4', 'lpddr4x', 'lpddr5', 'lpddr5x']
                and len(self.config_data.ddrc_timings) > 0):
            for pstate in range(0, num_pstates):
                ddrc_timings = ""
                for command in self.config_data.ddrc_timings[pstate]:
                    ddrc_timings += indent_block(f"{{{command['address']}, {command['value']}{Const.U_SUFFIX}}},\n",
                        0, False)
                ddrc_timings_per_pstate.append(ddrc_timings)

        # DDRC registers
        commands = self.processor.get_ddrc_registers(self.config_data)
        ddrc_config = ""
        for command in commands:
            if ddrc_config:
                ddrc_config += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_WRITE_DATA]:
                ddrc_config += f"{{0x{command.address:x}, 0x{command.value:x}{Const.U_SUFFIX}}},"

        # PHY init sequence
        phy_config = ""
        phy_addr_decoder = PhyAddrIMX95Decoder()

        commands = self.processor.get_phy_dq_mapping(self.config_data)
        for command in commands:
            if phy_config:
                phy_config += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_WRITE_DATA]:
                phy_addr = phy_addr_decoder.revert_ddr_space(command.address)
                phy_config += f"{{0x{phy_addr:x}, 0x{command.value:x}}},"

        commands = self.processor.get_phy_init_commands(self.config_data, pstate=None,
                                                   add_phy_init=True, add_phy_init_skip_train=False)
        for command in commands:
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                if phy_config:
                    phy_config += "\n"
                phy_config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
                if phy_init_reg_names:
                    reg_key = f"0x{command.address:x}"
                    if reg_key in phy_init_reg_names:
                        phy_config += f'{Const.indent}// {phy_init_reg_names[reg_key]}'

        phy_config_per_pstate = []
        for pstate in range(self.config_data.num_pstates):
            config = ""
            commands = self.processor.get_phy_init_commands(self.config_data, pstate,
                                                       add_phy_init=True, add_phy_init_skip_train=False)
            for command in commands:
                if config:
                    config += "\n"
                if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                    config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
                    if phy_init_reg_names:
                        reg_key = f"0x{command.address:x}"
                        if reg_key in phy_init_reg_names:
                            config += f'{Const.indent}// {phy_init_reg_names[reg_key]}'
            phy_config_per_pstate.append(config)

        # PHY init skip train section
        phy_skip_train = ""
        commands = self.processor.get_phy_init_commands(self.config_data, pstate=None,
                                                   add_phy_init=False, add_phy_init_skip_train=True)
        for command in commands:
            if phy_skip_train:
                phy_skip_train += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                phy_skip_train += f"{{0x{command.address:x}, 0x{command.value:x}}},"
                if phy_init_reg_names:
                    reg_key = f"0x{command.address:x}"
                    if reg_key in phy_init_reg_names:
                        phy_skip_train += f'{Const.indent}// {phy_init_reg_names[reg_key]}'

        phy_skip_train_per_pstate = []
        for pstate in range(self.config_data.num_pstates):
            config = ""
            commands = self.processor.get_phy_init_commands(self.config_data, pstate,
                                                       add_phy_init=False, add_phy_init_skip_train=True)
            for command in commands:
                if config:
                    config += "\n"
                if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                    config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
                    if phy_init_reg_names:
                        reg_key = f"0x{command.address:x}"
                        if reg_key in phy_init_reg_names:
                            config += f'{Const.indent}// {phy_init_reg_names[reg_key]}'
            phy_skip_train_per_pstate.append(config)

        # PIE config
        commands = self.processor.get_pie_init_commands(self.config_data)
        pie_config = ""
        for command in commands:
            if pie_config:
                pie_config += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                pie_config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
                if phy_init_reg_names:
                    reg_key = f"0x{command.address:x}"
                    if reg_key in phy_init_reg_names:
                        pie_config += f'{Const.indent}// {phy_init_reg_names[reg_key]}'

        pie_config_per_pstate = []
        for pstate in range(self.config_data.num_pstates):
            config = ""
            commands = self.processor.get_pie_init_commands(self.config_data, pstate)
            for command in commands:
                if config:
                    config += "\n"
                if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                    config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
                    if phy_init_reg_names:
                        reg_key = f"0x{command.address:x}"
                        if reg_key in phy_init_reg_names:
                            config += f'{Const.indent}// {phy_init_reg_names[reg_key]}'
            pie_config_per_pstate.append(config)

        # DDR PHY train CSR sequence.
        ddr_phy_train_csr = ""
        if self.config_data.retention_registers:
            for addr in self.config_data.retention_registers:
                if ddr_phy_train_csr:
                    ddr_phy_train_csr += "\n"
                ddr_phy_train_csr += f"{{{addr}, 0x0}},"
                if addr in phy_init_reg_names:
                    ddr_phy_train_csr += f'{Const.indent}// {phy_init_reg_names[addr]}'

        # TODO: get revision from processor data
        revision = None
        if '_' in self.config_data.soc_name:
            revision = self.config_data.soc_name.split('_')[1]
        revision_str = f'Chip revision: {revision}' if revision else ''

        header_file_gpl2 = f"""/*
 * Copyright {copyright_year} NXP
 *
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Code generated with DDR Tool v{__version__.__version__}_{self.config_data.rpa_version}-{__version__.__commit_id__}.
 * DDR PHY FW{self.config_data.snps_phy_info.name}
 * {revision_str}
 * {ddr_part_number_str}
 */
"""
        file = f"""{header_file_gpl2}
#include "ddr.h"
"""
        file += f"""
/* Initialize DDRC registers */
{struct} ddrc_cfg_param ddr_ddrc_cfg[] = {{
{indent_block(ddrc_config, 1, False)}}};
"""
        if len(ddrc_timings_per_pstate) == num_pstates:
            for pstate in range(0, num_pstates):
                ddrc_timings = ddrc_timings_per_pstate[pstate]
                file += f"""
/* DRAM fsp configurations */
{struct} ddrc_cfg_param ddr_dram_fsp{pstate}_ddrc_cfg[] = {{
{indent_block(ddrc_timings, 1, False)}}};
"""
        file += f"""
/* PHY Initialize Configuration */
{struct} ddrphy_cfg_param ddr_ddrphy_cfg[] = {{
{indent_block(phy_config, 1, False)}}};
"""
        file += f"""
/* PHY trained csr */
{struct} ddrphy_cfg_param ddr_ddrphy_trained_csr[] = {{
{indent_block(ddr_phy_train_csr, 1, False)}}};
"""
        for pstate in range(self.config_data.num_pstates):
            if phy_config_per_pstate[pstate]:
                file += f"""
/* PHY Initialize Configuration for Pstate {pstate} */
{struct} ddrphy_cfg_param ddr_phy_fsp{pstate}_cfg[] = {{
{indent_block(phy_config_per_pstate[pstate], 1, False)}}};"""

        if skip_train != 0:
            file += f"""
    /* PHY skip train csr  */
    {struct} ddrphy_cfg_param ddr_phy_prog_csr_cfg[] = {{
    {indent_block(phy_skip_train, 1, False)}}};
    """
        for pstate in range(self.config_data.num_pstates):
            if phy_skip_train_per_pstate[pstate]:
                file += f"""
/* PHY skip train csr for Pstate {pstate} */
{struct} ddrphy_cfg_param ddr_phy_prog_csr_ps_fsp{pstate}_cfg[] = {{
{indent_block(phy_skip_train_per_pstate[pstate], 1, False)}}};"""

            file += f"""
{message_block_1d}"""

        for pstate in range(self.config_data.num_pstates):
            if pstate < len(pie_config_per_pstate) and len(pie_config_per_pstate[pstate]) > 0:
                file += f"""
/* DRAM PHY init engine image for Pstate {pstate} */
{struct} ddrphy_cfg_param ddr_phy_pie_fsp{pstate}_cfg[] = {{
{indent_block(pie_config_per_pstate[pstate], 1, False)}}};
"""

        file += f"""
/* DRAM PHY init engine image */
{struct} ddrphy_cfg_param ddr_phy_pie[] = {{
{indent_block(pie_config, 1, False)}}};
"""

        file += f"""
{struct} dram_fsp_msg ddr_dram_fsp_msg[] = {{
{indent_block(fsp_msg_1d, 1, False)}}};
"""

        fsp_config = ""
        for pstate in range(self.config_data.num_pstates):
            fsp_config += f"""{{
{indent_block(f'''
.ddrc_cfg = ddr_dram_fsp{pstate}_ddrc_cfg,
.ddrc_cfg_num = ARRAY_SIZE(ddr_dram_fsp{pstate}_ddrc_cfg),
.bypass = 0,
''', 1, False)}}},
"""
        file += f"""
/* dram fsp cfg */
{struct} dram_fsp_cfg ddr_dram_fsp_cfg[] = {{
{indent_block(fsp_config, 1, False)}}};
"""

        file += f"""
/* ddr timing config params */
struct dram_timing_info dram_timing = {{
{indent_block(f'''.ddrc_cfg = ddr_ddrc_cfg,
.ddrc_cfg_num = ARRAY_SIZE(ddr_ddrc_cfg),
.ddrphy_cfg = ddr_ddrphy_cfg,
.ddrphy_cfg_num = ARRAY_SIZE(ddr_ddrphy_cfg),
.fsp_msg = ddr_dram_fsp_msg,
.fsp_msg_num = ARRAY_SIZE(ddr_dram_fsp_msg),
.ddrphy_trained_csr = ddr_ddrphy_trained_csr,
.ddrphy_trained_csr_num = ARRAY_SIZE(ddr_ddrphy_trained_csr),
.ddrphy_pie = ddr_phy_pie,
.ddrphy_pie_num = ARRAY_SIZE(ddr_phy_pie),
.fsp_table = {{ {dram_rate_list}}},
{".ddrphy_prog_csr = ddr_phy_prog_csr_cfg," if skip_train != 0 else ""}
{".ddrphy_prog_csr_num = ARRAY_SIZE(ddr_phy_prog_csr_cfg)," if skip_train != 0 else ""}
.fsp_cfg = ddr_dram_fsp_cfg,
.fsp_cfg_num = ARRAY_SIZE(ddr_dram_fsp_cfg),''', 1, False)}}};
"""
        return file
