# Copyright 2020-2025 NXP
"""Generate code for targets with PHY v2 firmware."""
import logging

from memtool import __version__
from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import DCDCommand, DCDCommandIds
from memtool.phyinit.phy_utils import PhyPhase
from memtool.processor.base_processor import BaseProcessor
from memtool.utils.constants import Const
from memtool.utils.helper import get_current_year

from .addr_decoder import PhyAddrIMX8Decoder, PhyAddrIMX93Decoder
from .codegenerator import CodeGenerator, indent_block

logger = logging.getLogger(__name__)


class CodeGeneratorPHYv2(CodeGenerator):
    """Generate timing data for targets with PHY v2 firmware."""

    def __init__(self, _config_data: ConfigData, _processor: BaseProcessor):
        """Constructor.

        @param _config_data: processor config data
        @param _processor: processor
        """
        super(CodeGeneratorPHYv2, self).__init__(_config_data, _processor)

    def generate_timing(self) -> str:
        """Prepare timing file contents.

        @return: timing file contents as a string
        """
        logger.debug("Generate timing file")
        is_imx9 = self.processor.processor_info.is_imx9()

        num_pstates = self.config_data.num_pstates
        message_block_1d = ''
        fsp_msg_1d = ''
        message_block_2d = self.config_data.message_block_tmg_2d

        dram_rate = []
        dram_rate_list = ''

        struct = "struct"
        if is_imx9:
            struct = "static struct"

        for pstate in range(0, num_pstates):
            freq = self.config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC].get(
                        f"Frequency[{pstate}]", 0)
            if self.config_data.mem_type in ['ddr3'] and pstate != 0:
                dram_rate.append(int(float(freq) * 2) - 1)
            else:
                dram_rate.append(int(float(freq) * 2))
            dram_rate_list += str(dram_rate[pstate]) + ', '

            if pstate >= len(self.config_data.message_block_tmg_1d):
                logger.error('message_block_tmg_1d for pstate %d does not exist!', pstate)
                continue

            message_block_1d += f"""
/* P{pstate} message block parameter for training firmware */
{struct} dram_cfg_param ddr_fsp{pstate}_cfg[] = {{
{indent_block(f'''{{0xd0000, 0x0}},
{self.config_data.message_block_tmg_1d[pstate]}{{0xd0000, 0x1}}''', 1, False)}}};
"""

            fsp_msg_1d += f"""{{
{indent_block(f'''/* P{pstate} {dram_rate[pstate]}mts 1D */
.drate = {dram_rate[pstate]},
.fw_type = FW_1D_IMAGE,
.fsp_cfg = ddr_fsp{pstate}_cfg,
.fsp_cfg_num = ARRAY_SIZE(ddr_fsp{pstate}_cfg),''', 1)}
}},
"""
        # DDRC timings
        ddrc_timings = ""
        # for now, only for IMX93 & IMX95(lpddr4, lpddr4x, lpddr5, lpddr5x) we have support for timing in RPA
        if self.config_data.mem_type in ['lpddr4', 'lpddr4x']:
            if self.config_data.ddrc_timings:
                for pstate in range(0, num_pstates):
                    ddrc_timings += "{\n"

                    ddrc_timings += indent_block("{\n", 1, False)
                    for command in self.config_data.ddrc_timings[pstate]:
                        ddrc_timings += indent_block(f"{{{command['address']}, {command['value']}}},\n", 2, False)
                    ddrc_timings += indent_block("},\n", 1, False)

                    ddrc_timings += indent_block("{\n", 1, False)
                    msg_blk_key = f"messageBlock[{pstate}]"
                    for mr_idx in ["0x01", "0x02", "0x03", "0x0b", "0x0c", "0x0e", "0x16"]:
                        mr_key = f"MR{int(mr_idx, 16)}_A0"
                        ddrc_timings += indent_block(
                            f"{{{mr_idx}, {self.config_data.params[Const.PARAM_S_PHY][msg_blk_key][mr_key]}}},\n",
                            2, False)
                    ddrc_timings += indent_block("},\n", 1, False)

                    pll_bypass_key = f"PllBypass[{pstate}]"
                    ddrc_timings += indent_block(
                        f"{self.config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][pll_bypass_key]},",
                        1, False)

                    ddrc_timings += "},\n"

        # DDRC registers
        commands = self.processor.get_ddrc_registers(self.config_data)
        ddrc_config = ""
        for command in commands:
            if len(ddrc_config) > 0:
                ddrc_config += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_WRITE_DATA]:
                ddrc_config += f"{{0x{command.address:x}, 0x{command.value:x}}},"

        # PHY init sequence
        phy_config = ""
        if is_imx9:
            phy_addr_decoder = PhyAddrIMX93Decoder()
        else:
            phy_addr_decoder = PhyAddrIMX8Decoder()  # type: ignore

        commands = self.processor.get_phy_dq_mapping(self.config_data)
        for command in commands:
            if len(phy_config) > 0:
                phy_config += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_WRITE_DATA]:
                phy_addr = phy_addr_decoder.revert_ddr_space(command.address)
                phy_config += f"{{0x{phy_addr:x}, 0x{command.value:x}}},"

        commands = self.processor.get_phy_init_commands(self.config_data, pstate=None,
                                                   add_phy_init=True, add_phy_init_skip_train=False)
        for command in commands:
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                if len(phy_config) > 0:
                    phy_config += "\n"
                phy_config += f"{{0x{command.address:x}, 0x{command.value:x}}},"

        phy_config_per_pstate = []
        for pstate in range(self.config_data.num_pstates):
            config = ""
            commands = self.processor.get_phy_init_commands(self.config_data, pstate,
                                                       add_phy_init=True, add_phy_init_skip_train=False)
            for command in commands:
                if len(config) > 0:
                    config += "\n"
                if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                    config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
            phy_config_per_pstate.append(config)

        # PHY init skip train section
        # phy_skip_train = ""
        # commands = self.processor.get_phy_init_commands(self.config_data, pstate=None,
        #                                            add_phy_init=False, add_phy_init_skip_train=True)
        # for command in commands:
        #     if len(phy_skip_train) > 0:
        #         phy_skip_train += "\n"
        #     if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
        #         phy_skip_train += f"{{0x{command.address:x}, 0x{command.value:x}}},"

        # phy_skip_train_per_pstate = []
        # for pstate in range(self.config_data.num_pstates):
        #     config = ""
        #     commands = self.processor.get_phy_init_commands(self.config_data, pstate,
        #                                                add_phy_init=False, add_phy_init_skip_train=True)
        #     for command in commands:
        #         if len(config) > 0:
        #             config += "\n"
        #         if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
        #             config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
        #     phy_skip_train_per_pstate.append(config)

        # PIE config
        commands = self.processor.get_pie_init_commands(self.config_data)
        pie_config = ""
        for command in commands:
            if len(pie_config) > 0:
                pie_config += "\n"
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                pie_config += f"{{0x{command.address:x}, 0x{command.value:x}}},"

        pie_config_per_pstate = []
        for pstate in range(self.config_data.num_pstates):
            config = ""
            commands = self.processor.get_pie_init_commands(self.config_data, pstate)
            for command in commands:
                if len(config) > 0:
                    config += "\n"
                if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_PHY_WRITE_DATA]:
                    config += f"{{0x{command.address:x}, 0x{command.value:x}}},"
            pie_config_per_pstate.append(config)

        # DDR PHY train CSR sequence.
        ddr_phy_train_csr = ""
        if self.config_data.retention_registers:
            for addr in self.config_data.retention_registers:
                if len(ddr_phy_train_csr) > 0:
                    ddr_phy_train_csr += "\n"
                ddr_phy_train_csr += f"{{{addr}, 0x0}},"

        # DDR ECC scrub config
        ecc_scrub_config = ""
        ecc_scrub_regions = self.processor.get_ecc_scrub_regions(self.config_data)
        if ecc_scrub_regions is not None:
            for region in ecc_scrub_regions[0]:
                ecc_scrub_config += f"ddrc_inline_ecc_scrub({region[0]}, {region[1]});\n"
            ecc_scrub_config += f"ddrc_inline_ecc_scrub_end({ecc_scrub_regions[1][0]}, {ecc_scrub_regions[1][1]});"

        # Set copyright year
        current_year = get_current_year()

        # Set DDR part number
        ddr_part_number = self.config_data.params.get('ddrPartNumber', '').strip() or "Unknown"
        ddr_part_number_str = f'Part number: {ddr_part_number}'

        header_file_gpl2 = f"""/*
 * Copyright {current_year} NXP
 *
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Code generated with DDR Tool v{__version__.__version__}_{self.config_data.rpa_version}-{__version__.__commit_id__}.
 * DDR PHY FW{self.config_data.snps_phy_info.name} 
 * {ddr_part_number_str}
 */
"""
        file = f"""{header_file_gpl2}
#include <linux/kernel.h>
#include <asm/arch/ddr.h>
"""

        file += f"""
/* Initialize DDRC registers */
{struct} dram_cfg_param ddr_ddrc_cfg[] = {{
{indent_block(ddrc_config, 1)}}};
"""

        if len(ddrc_timings) > 0:
            file += f"""
/* dram fsp cfg */
{struct} dram_fsp_cfg ddr_dram_fsp_cfg[] = {{
{indent_block(ddrc_timings, 1)}}};
"""

        file += f"""
/* PHY Initialize Configuration */
{struct} dram_cfg_param ddr_ddrphy_cfg[] = {{
{indent_block(phy_config, 1)}}};
"""
        for pstate in range(self.config_data.num_pstates):
            if len(phy_config_per_pstate[pstate])> 0:
                file += f"""
/* PHY Initialize Configuration for Pstate {pstate} */
{struct} dram_cfg_param ddr_ddrphy_fps{pstate}_cfg[] = {{
{indent_block(phy_config_per_pstate[pstate], 1)}}};
"""
            else:
                logger.info(f"No Phy Init configuration found for Pstate {pstate}")

        file += f"""
/* PHY trained csr */
{struct} dram_cfg_param ddr_ddrphy_trained_csr[] = {{
{indent_block(ddr_phy_train_csr, 1)}}};
{message_block_1d}
"""

        if len(message_block_2d) > 0:
            file += f"""
/* P0 2D message block parameter for training firmware */
{struct} dram_cfg_param ddr_fsp0_2d_cfg[] = {{
{indent_block(f'''{{0xd0000, 0x0}},
{message_block_2d}{{0xd0000, 0x1}}''', 1)}}};
"""

        file += f"""
/* DRAM PHY init engine image */
{struct} dram_cfg_param ddr_phy_pie[] = {{
{indent_block(pie_config, 1)}}};
"""

        for pstate in range(self.config_data.num_pstates):
            if len(pie_config_per_pstate[pstate]) > 0:
                file += f"""
/* DRAM PHY init engine image for Pstate {pstate} */
{struct} dram_cfg_param ddr_phy_pie_fps{pstate}[] = {{
{indent_block(pie_config_per_pstate[pstate], 1)}}};
"""
            else:
                logger.info(f"No PIE configuration found for Pstate {pstate}")

        if len(message_block_2d) > 0:
            file += f"""
{struct} dram_fsp_msg ddr_dram_fsp_msg[] = {{
{indent_block(fsp_msg_1d, 1, False)}{indent_block(f'''{{
    /* P0 {dram_rate[0]}mts 2D */
    .drate = {dram_rate[0]},
    .fw_type = FW_2D_IMAGE,
    .fsp_cfg = ddr_fsp0_2d_cfg,
    .fsp_cfg_num = ARRAY_SIZE(ddr_fsp0_2d_cfg),
}},''', 1, False)}}};
"""
        else:
            file += f"""
{struct} dram_fsp_msg ddr_dram_fsp_msg[] = {{
{indent_block(fsp_msg_1d, 1, False)}}};
"""

        file += f"""
/* ddr timing config params */
struct dram_timing_info dram_timing = {{
    .ddrc_cfg = ddr_ddrc_cfg,
    .ddrc_cfg_num = ARRAY_SIZE(ddr_ddrc_cfg),
    .ddrphy_cfg = ddr_ddrphy_cfg,
    .ddrphy_cfg_num = ARRAY_SIZE(ddr_ddrphy_cfg),
    .fsp_msg = ddr_dram_fsp_msg,
    .fsp_msg_num = ARRAY_SIZE(ddr_dram_fsp_msg),
    .ddrphy_trained_csr = ddr_ddrphy_trained_csr,
    .ddrphy_trained_csr_num = ARRAY_SIZE(ddr_ddrphy_trained_csr),
    .ddrphy_pie = ddr_phy_pie,
    .ddrphy_pie_num = ARRAY_SIZE(ddr_phy_pie),
    .fsp_table = {{ {dram_rate_list}}},"""

        if len(ddrc_timings) > 0:
            file += """
    .fsp_cfg = ddr_dram_fsp_cfg,
    .fsp_cfg_num = ARRAY_SIZE(ddr_dram_fsp_cfg),
};
"""
        else:
            file += """
};
"""

        if len(ecc_scrub_config) > 0:
            file += f"""
void board_dram_ecc_scrub(void)
{{
{indent_block(ecc_scrub_config, 1, False)}}}
"""
        return file
