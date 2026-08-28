# Copyright 2020-2025 NXP
"""Generate code for LX2 targets."""
import logging

from memtool.codegen.codegenerator import CodeGenerator
from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import DCDCommand
from memtool.common.dcd_commands import DCDCommandIds
from memtool.processor.base_processor import BaseProcessor
from memtool.utils.constants import Const
from memtool.utils.helper import get_current_year, to_int
from memtool import __version__


class CodeGeneratorLX(CodeGenerator):
    """Generate timing data for LX targets."""

    def __init__(self, _config_data: ConfigData, _processor: BaseProcessor):
        """Constructor.

        @param _config_data: processor config data
        @param _processor: processor
        """
        super(CodeGeneratorLX, self).__init__(_config_data, _processor)

    @staticmethod
    def calc_ps_time(timing: str, bus_clock: int) -> float:
        """Transforms timing from clocks to picoseconds.

        @param timing: timing to be transformed
        @param bus_clock: selected bus clock
        @return: picoseconds timing
        """
        try:
            return 1000 * round(1000 * int(timing) / bus_clock)
        except ArithmeticError:
            return -1

    @staticmethod
    def get_reg_hexvalue(name: str, ddrc_registers: {}) -> str:  # type: ignore
        """Gets register value in hex, or #NA if register was not found in the .DS file.

        @param name: register's name
        @param ddrc_registers: dict of found registers
        """
        try:
            return f"0x{ddrc_registers[name]:02X}"
        except ValueError:
            return "NA#"

    @staticmethod
    def get_reg_value(name: str, ddrc_registers: {}) -> int:  # type: ignore
        """Gets register value in hex, or #NA if register was not found in the .DS file.

        @param name: register's name
        @param ddrc_registers: dict of found registers
        """
        try:
            return ddrc_registers[name]
        except KeyError:
            return -1

    def generate_timing(self) -> str:
        """Prepare timing file contents.

        @return: timing file contents as a string
        """
        logging.getLogger(__name__).debug("Generate timing file")

        freq = self.config_data.freq
        dram_rate = []
        dram_rate_list = ''

        for pstate in range(0, self.config_data.num_pstates):
            dram_rate.append(freq[pstate] * 2)
            dram_rate_list += str(dram_rate[pstate]) + ', '

        # DDRC registers
        commands = self.processor.get_ddrc_registers(self.config_data)
        ddrc_registers = {}
        for command in commands:
            if isinstance(command, DCDCommand) and command.command in [DCDCommandIds.CMD_WRITE_DATA]:
                ddrc_registers[command.name] = command.value

        # Some calculations for the generated file
        rdimm = 0 if ('udimm' in ConfigData.DIMM_TYPES[self.config_data.dimm_type]) else 1

        number_of_ranks = int(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("numberOfRanks", 1))
        data_bus_width = 64 if (
                (CodeGeneratorLX.get_reg_value("DDR_SDRAM_CFG", ddrc_registers) & 0x180000) >> 19 == 0) else 32
        dram_density = int(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("dramDensity", 1))
        device_width = int(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("deviceWidth", 1))
        enable_ecc = (CodeGeneratorLX.get_reg_value("DDR_SDRAM_CFG", ddrc_registers) & 0x20000000) >> 29
        number_of_controllers = self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("numberOfControllersEnabled", 1)
        ec_sdram_width = 8 if (enable_ecc == 1) else 0
        dimm_on_ctlr = 1 if (number_of_ranks < 3) else 2
        cs_on_dimm = 1 if (number_of_ranks == 1) else (3 if (number_of_ranks == 2) else 15)
        edc_config = 2 if (enable_ecc == 1) else 0
        mirrored_dimm = CodeGeneratorLX.get_reg_value("DDR_SDRAM_CFG_2", ddrc_registers) & 0x1
        dram_density = 4 if (dram_density == 1) else (8 if (dram_density == 2) else 16)
        die_density = 4 if (dram_density == 1) else (5 if (dram_density == 2) else 6)
        device_width = 4 if (device_width == 2) else (8 if (device_width == 0) else 16)
        bus_clock = dram_rate[0] / 2
        total_size = ((1 + CodeGeneratorLX.get_reg_value("CS0_BNDS", ddrc_registers)) << 24)
        trwt = ((CodeGeneratorLX.get_reg_value("TIMING_CFG_4", ddrc_registers) & 0xC000) >> 12) \
               | ((CodeGeneratorLX.get_reg_value("TIMING_CFG_0", ddrc_registers) & 0xC0000000) >> 30)
        twrt = ((CodeGeneratorLX.get_reg_value("TIMING_CFG_4", ddrc_registers) & 0x1000) >> 10) \
               | ((CodeGeneratorLX.get_reg_value("TIMING_CFG_0", ddrc_registers) & 0x30000000) >> 28)
        trrt = ((CodeGeneratorLX.get_reg_value("TIMING_CFG_4", ddrc_registers) & 0x400) >> 8) \
               | ((CodeGeneratorLX.get_reg_value("TIMING_CFG_0", ddrc_registers) & 0xC000000) >> 26)
        twwt = ((CodeGeneratorLX.get_reg_value("TIMING_CFG_4", ddrc_registers) & 0x100) >> 6) \
               | ((CodeGeneratorLX.get_reg_value("TIMING_CFG_0", ddrc_registers) & 0x3000000) >> 24)
        burst = (CodeGeneratorLX.get_reg_value("DDR_SDRAM_CFG", ddrc_registers) & 0x40000) >> 18

        valid_mask = 0
        # Valid masks: b0101 (1 dimm , 2 controllers), b1111(2 dimms, 2 controllers), b01 (1 controller, 1 dimm), b11 (1 controller, 2 dimms)
        for i in range(0, int(number_of_controllers)):
            for j in range(0, dimm_on_ctlr):
                valid_mask |= (1 << j) << i * 2

        current_year = get_current_year()
        header_file_bsd3 = f"""/*
 * Copyright {current_year} NXP
 *
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Code generated with DDR Tool v{__version__.__version__}_{self.config_data.rpa_version}-{__version__.__commit_id__}.
 * DDR PHY FW{self.config_data.snps_phy_info.name}
 */
"""
        file = f"""{header_file_bsd3}
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <common/debug.h>
#include <lib/utils.h>
#include <plat_common.h>
#include <ddr.h>
#include <platform_def.h>

#ifdef CONFIG_STATIC_DDR
const struct ddr_cfg_regs static_{dram_rate[0]} = {{
    .cs[0].bnds = {CodeGeneratorLX.get_reg_hexvalue("CS0_BNDS", ddrc_registers)},
    .cs[0].config = {CodeGeneratorLX.get_reg_hexvalue("CS0_CONFIG", ddrc_registers)},
    .cs[1].bnds = {CodeGeneratorLX.get_reg_hexvalue("CS1_BNDS", ddrc_registers)},
    .cs[1].config = {CodeGeneratorLX.get_reg_hexvalue("CS1_CONFIG", ddrc_registers)},
    .cs[2].bnds = {CodeGeneratorLX.get_reg_hexvalue("CS2_BNDS", ddrc_registers)},
    .cs[2].config = {CodeGeneratorLX.get_reg_hexvalue("CS2_CONFIG", ddrc_registers)},
    .cs[3].bnds = {CodeGeneratorLX.get_reg_hexvalue("CS3_BNDS", ddrc_registers)},
    .cs[3].config = {CodeGeneratorLX.get_reg_hexvalue("CS3_CONFIG", ddrc_registers)},
    .timing_cfg[0] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_0", ddrc_registers)},
    .timing_cfg[1] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_1", ddrc_registers)},
    .timing_cfg[2] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_2", ddrc_registers)},
    .timing_cfg[3] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_3", ddrc_registers)},
    .timing_cfg[4] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_4", ddrc_registers)},
    .timing_cfg[5] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_5", ddrc_registers)},
    .timing_cfg[7] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_7", ddrc_registers)},
    .timing_cfg[8] = {CodeGeneratorLX.get_reg_hexvalue("TIMING_CFG_8", ddrc_registers)},
    .sdram_cfg[0] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_CFG", ddrc_registers)},
    .sdram_cfg[1] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_CFG_2", ddrc_registers)},
    .sdram_mode[0] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE", ddrc_registers)},
    .sdram_mode[1] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_2", ddrc_registers)},
    .sdram_mode[2] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_3", ddrc_registers)},
    .sdram_mode[3] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_4", ddrc_registers)},
    .sdram_mode[4] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_5", ddrc_registers)},
    .sdram_mode[5] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_6", ddrc_registers)},
    .sdram_mode[6] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_7", ddrc_registers)},
    .sdram_mode[7] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_8", ddrc_registers)},
    .sdram_mode[8] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_9", ddrc_registers)},
    .sdram_mode[9] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_10", ddrc_registers)},
    .sdram_mode[10] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_11", ddrc_registers)},
    .sdram_mode[11] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_12", ddrc_registers)},
    .sdram_mode[12] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_13", ddrc_registers)},
    .sdram_mode[13] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_14", ddrc_registers)},
    .sdram_mode[14] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_15", ddrc_registers)},
    .sdram_mode[15] = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_MODE_16", ddrc_registers)},
    .md_cntl = 0x00,
    .interval = {CodeGeneratorLX.get_reg_hexvalue("DDR_SDRAM_INTERVAL", ddrc_registers)},
    .data_init = {CodeGeneratorLX.get_reg_hexvalue("DDR_DATA_INIT", ddrc_registers)},
    .init_addr = 0x00,
    .zq_cntl = {CodeGeneratorLX.get_reg_hexvalue("DDR_ZQ_CNTL", ddrc_registers)},
    .sdram_rcw[0] = {CodeGeneratorLX.get_reg_hexvalue("RCW_1", ddrc_registers)},
    .sdram_rcw[1] = {CodeGeneratorLX.get_reg_hexvalue("RCW_2", ddrc_registers)},
    .sdram_rcw[2] = {CodeGeneratorLX.get_reg_hexvalue("RCW_3", ddrc_registers)},
    .sdram_rcw[3] = {CodeGeneratorLX.get_reg_hexvalue("RCW_4", ddrc_registers)},
    .sdram_rcw[4] = {CodeGeneratorLX.get_reg_hexvalue("RCW_5", ddrc_registers)},
    .sdram_rcw[5] = {CodeGeneratorLX.get_reg_hexvalue("RCW_6", ddrc_registers)},
    .err_disable = 0x00,
    .err_int_en = 0x00
}};


const struct dimm_params static_dimm = {{
    .rdimm = {rdimm},
    .primary_sdram_width = {data_bus_width},
    .ec_sdram_width = {ec_sdram_width},
    .n_ranks = {number_of_ranks},
    .device_width = {device_width},
    .mirrored_dimm = {mirrored_dimm}
}};


/* Sample code using two UDIMM /**TODO */, on each DDR controller */
long long board_static_ddr(struct ddr_info *priv)
{{
    int valid_spd_mask __unused;
    int ret = 0x0;

    valid_spd_mask = 0x{valid_mask:X};
#if defined(NXP_HAS_CCN504) || defined(NXP_HAS_CCN508)
    if (priv->num_ctlrs == 2 || priv->num_ctlrs == 1) {{
        ret = disable_unused_ddrc(priv, valid_spd_mask,
                NXP_CCN_HN_F_0_ADDR);
        if (ret)
            return ret;
    }}
#endif
        memcpy(&priv->ddr_reg, &static_{dram_rate[0]}, sizeof(static_{dram_rate[0]}));
        memcpy(&priv->dimm, &static_dimm, sizeof(static_dimm));
        priv->conf.cs_on_dimm[0] = 0x{cs_on_dimm:X};
        ddr_board_options(priv);
        compute_ddr_phy(priv);
        return ULL(0x{total_size:X});
}}

#elif defined(CONFIG_DDR_NODIMM)

/*
* Below structure is generated for DIMM part number: N/A
* Sample code to bypass reading SPD. 
* This is a sample, not recommended  for boards with slots. 
*/
struct dimm_params ddr_raw_timing = {{
        .n_ranks = {number_of_ranks},
        .rank_density = 0x{(dram_density * 1073741824) :X},
        .capacity = 0x{(dram_density * 1073741824 * number_of_ranks) :X},
        .primary_sdram_width = {data_bus_width},
        .ec_sdram_width = {ec_sdram_width},
        .device_width = {device_width},
        .die_density = 0x{die_density:X},
        .rdimm = {rdimm},
        .mirrored_dimm = {mirrored_dimm},
        .n_row_addr = {((CodeGeneratorLX.get_reg_value("CS0_CONFIG", ddrc_registers) & 0x700) >> 8) + 12},
        .n_col_addr = {(CodeGeneratorLX.get_reg_value("CS0_CONFIG", ddrc_registers) & 0x7) + 8},
        .bank_addr_bits = 0,
        .bank_group_bits = {1 if (device_width == 16) else 2},
        .edc_config = {edc_config},
        .burst_lengths_bitmask = 0x0c,
        .tckmin_x_ps = 625,
        .tckmax_ps = 1600,
        .caslat_x = 0x00FFFC00,
        .taa_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("taa", "24"), bus_clock)}, 
        .trcd_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trcd", "22"), bus_clock)},
        .trp_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trp", "22"), bus_clock)},
        .tras_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("tras", "52"), bus_clock)},
        .trc_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trp", "22"), bus_clock)
                   + CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trcd", "22"), bus_clock)},
        .twr_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("twr", "24"), bus_clock)},
        .trfc1_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trfc1", "560"), bus_clock)},
        .trfc2_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trfc2", "416"), bus_clock)},
        .trfc4_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trfc4", "256"), bus_clock)},
        .tfaw_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("tfaw", "34"), bus_clock)},
        .trrds_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trrds", "6"), bus_clock)},
        .trrdl_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trrdl", "8"), bus_clock)},
        .tccdl_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("tccdl", "8"), bus_clock)},
        .refresh_rate_ps = {CodeGeneratorLX.calc_ps_time(self.config_data.params.get(Const.PARAM_S_BASIC, {}).get("trefi", "12480"), bus_clock)}
}};

int ddr_get_ddr_params(struct dimm_params *pdimm,
                            struct ddr_conf *conf)
{{
    static const char dimm_model[] = "Fixed DDR on board";
        conf->dimm_in_use[0] = {dimm_on_ctlr};       /* Modify accordingly */
        memcpy(pdimm, &ddr_raw_timing, sizeof(struct dimm_params));
        memcpy(pdimm->mpart, dimm_model, sizeof(dimm_model) - 1);

        /* valid DIMM mask, change accordingly, together with dimm_on_ctlr. */
        return 0x{valid_mask:X};
}}
#endif /* CONFIG_DDR_NODIMM */

int ddr_board_options(struct ddr_info *priv)
{{
    struct memctl_opt *popts = &priv->opt;
    const struct ddr_conf *conf = &priv->conf;

    /* vref_dimm: value of this this field is reflected in sdram_mode[9]
    * in upper 16 bits. This value is also the part of phy register MR6
    * This is used for range selection and its corresponding value.
    */

    popts->vref_dimm = {hex(to_int(self.config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["MR6"]) & 0xFF)}; /* range 1, 83.4% */ /**TODO*/

    /* rtt_override: allows to override the cs.odt_rtt_norm, cs.odt_rtt_wr
     * 
     * cs.odt_rtt_norm is reflected in sdram_mode 0[24..26] and the same
     * value is reflected as phy MR1 value also. This is 3 bit value.
     * Overriden value must be given as popts->rtt_override_value.
     * Valid set of values:
     * DDR4_RTT_OFF            0
     * DDR4_RTT_60_OHM         1
     * DDR4_RTT_120_OHM        2
     * DR4_RTT_40_OHM         3
     * DDR4_RTT_240_OHM        4
     * DDR4_RTT_48_OHM         5
     * DDR4_RTT_80_OHM         6
     * DDR4_RTT_34_OHM         7
     */

    popts->rtt_override = 1;
    popts->rtt_override_value = 0x5;    /* RTT being used as 60 ohm */
    /* Dram driver strength: Is defined in the MR1 phy register bit[1..2]
     * and sdram_mode 0[17..18]. This is a 2 bit value meaning as below:
     *
     * 00 (full 34 ohm)
     * 01 (half 48 ohm)
     *
     * Default value is set to 0. To change it to 1 use below two options
     * (whichever is true.)
     * Set quad_rank_present or output_driver_impedance to 1
     * popts->quad_rank_present = 1 or popts->output_driver_impedance = 1
     */
     popts->output_driver_impedance = 0;

    /* rtt_park: the value of rtt_park is set in sdram_mode 8[6..8]. And the
    * same value is used in MR5[A8:A6]. Below are valid values (in ohm):
    * 0x0 -disable
    * 0x1 -60
    * 0x2 -120
    * 0x3 -40
    * 0x4 -240
    * 0x5 -48
    * 0x6 -80
    * 0x7 -34
    * Note: If the value is not defined then the default 0x4 is considered
    * by SW.
    */

    popts->rtt_park = {Const.RTT_PARK[(CodeGeneratorLX.get_reg_value("DDR_SDRAM_MODE_9", ddrc_registers) & 0x1C0) >> 6]};
    popts->otf_burst_chop_en = {(CodeGeneratorLX.get_reg_value("DDR_SDRAM_CFG_2", ddrc_registers) & 0x40) >> 6};
    popts->burst_length = {4 if (burst == 0) else 8};
    popts->trwt_override = 1;
    popts->bstopre = 0;     /* auto precharge */
    popts->addr_hash = 1;
    /* trwt_override is used to override the turnaround timing values.
     * It overrides following timing parameters
     * trwt - read - write turnaround timing
     * twrt - write - read turnaround timing
     * trrt - read - read turnaround timing
     * twwt - write - write turnaround timing
     *
     * Values are progrmamed using respective parameters:
     * popts->trwt, popts->twrt, popts->trrt, popts->twwt
     * These values are programmed in below switch case.
     */
    popts->trwt_override = 1;

    /* 
     * Various other phy parameters are also defined in this file
     * such as:
     * PHY Data Bus driver impedance: value is defined in popts->tx_impedance
     * If not defined default is 28 ohm
     *  Valid values (in ohm): 000001 - 480.0, 240.0, 160.0, 120.0,
     *  96.0, 80.0, 68.6, 60.0, 53.3, 48.0, 43.6, 40.0, 36.9, 34.3,
     *  32.0, 30.0, 28.2
     * PHY C/A Bus driver impedance: value is defined in popts->atx_impedance
     *  If not defined default is 30 ohm
     *  Valid values (in ohm): 120.0, 60.0, 40.0, 30.0, 24.0, 20.0 Ohm 
     * PHY ODT: value is defined in popts->odt
     *  If not defined default is 60 ohm
     *  Valid values (in ohm): 000001 - 480.0, 240.0, 160.0, 120.0,
     *  96.0, 80.0, 68.6, 60.0, 53.3, 48.0, 43.6, 40.0, 36.9, 34.3,
     *  32.0, 30.0, 28.2
     * PHY Vref: value is defined in popts->vref_phy
     * if not defined default value is 0x61
     * Value programmed in register is calculated as:
     * (input_value * 1000 - 345 * 128 + 320) / (5 * 128);
     *
     * Above mentioned settings are set in the below code, user can change
     * according to their board/DRAM configuration needs.
     */ 

/*
#if DDRC_NUM_DIMM != 2
#error /"This board has two DIMM slots per controller./"
#endif
*/
    /* Set ODT impedance on PHY side */
    switch (conf->cs_on_dimm[1]) {{
    case 0xc:   /* Two slots dual rank */
    case 0x4:   /* Two slots single rank, not valid for interleaving */
        popts->trwt = 0x{trwt:02X};
        popts->twrt = 0x{twrt:02X};
        popts->trrt = 0x{trrt:02X};
        popts->twwt = 0x{twwt:02X};
        popts->vref_phy = {self.config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyVref"]};
        popts->odt = {self.config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[0]"]};
        popts->phy_tx_impedance = {self.config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[0]"]};
        break;
    case 0:     /* One slot used */
    default:
        popts->trwt = 0x{trwt:02X};
        popts->twrt = 0x{twrt:02X};
        popts->trrt = 0x{trrt:02X};
        popts->twwt = 0x{twwt:02X};
        popts->vref_phy = {self.config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyVref"]};
        popts->odt = {self.config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["ODTImpedance[0]"]};
        popts->phy_tx_impedance = {self.config_data.params[Const.PARAM_S_PHY]["userInputAdvanced"]["TxImpedance[0]"]};
        break;
    }}

    return 0;
}}

#ifdef NXP_WARM_BOOT
long long _init_ddr(uint32_t wrm_bt_flg)
#else
long long _init_ddr(void)
#endif
{{
        int spd_addr[] = {{ 0x51, 0x52, 0x53, 0x54 }};
        struct ddr_info info;
        struct sysinfo sys;
        long long dram_size;

        zeromem(&sys, sizeof(sys));
        if (get_clocks(&sys, NXP_DCFG_ADDR, NXP_SYSCLK_FREQ,
                NXP_DDRCLK_FREQ, NXP_PLATFORM_CLK_DIVIDER)) {{
            ERROR("System clocks are not set");
            assert(0);
        }}

        zeromem(&info, sizeof(info));

        /* Set two DDRC. Unused DDRC will be removed automatically. */
        info.num_ctlrs = {number_of_controllers};
        info.spd_addr = spd_addr;
        info.ddr[0] = (void *)NXP_DDR_ADDR;
        info.ddr[1] = (void *)NXP_DDR2_ADDR;
        info.phy[0] = (void *)NXP_DDR_PHY1_ADDR;
        info.phy[1] = (void *)NXP_DDR_PHY2_ADDR;
        info.clk = get_ddr_freq(&sys, 0, NXP_DCFG_ADDR, NXP_SYSCLK_FREQ,
                    NXP_DDRCLK_FREQ, NXP_PLATFORM_CLK_DIVIDER);
        if (!info.clk)
            info.clk = get_ddr_freq(&sys, 1, NXP_DCFG_ADDR, NXP_SYSCLK_FREQ,
                        NXP_DDRCLK_FREQ,
                        NXP_PLATFORM_CLK_DIVIDER);
        info.dimm_on_ctlr = {dimm_on_ctlr};

        info.warm_boot_flag = DDR_WRM_BOOT_NT_SUPPORTED;
        dram_size = dram_init(&info
    #if defined(NXP_HAS_CCN504) || defined(NXP_HAS_CCN508)
            , NXP_CCN_HN_F_0_ADDR
    #endif
    #ifndef CONFIG_STATIC_DDR
            , NXP_I2C_ADDR
    #endif
            );

    if (dram_size < 0)
        ERROR("DDR init failed.");

    return dram_size;
}}

"""
        return file
