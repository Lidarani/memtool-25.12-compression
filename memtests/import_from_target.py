# Copyright 2022-2025 NXP
"""TODO:summary line."""
import argparse
import json
import logging
import os
import sys
import time

from memtool.common.config_data import ConfigData
from memtool.common.factories import BackendFactory, ProcessorFactory
from memtool.common.workspace import Workspace
from memtool.utils.constants import Const
from memtool.utils.helper import add_file_to_params

logger = logging.getLogger(__name__)
CCSR_DDR_PHY1_ADDR = 0x1400000
CCSR_DDR_PHY2_ADDR = 0x1600000
DCFG_CCSR = 0x1E00000
DDRC_BASE_ADDRESS = 0x1080000
CS0_CONFIG_OFFSET = DDRC_BASE_ADDRESS + 0x80
CS1_CONFIG_OFFSET = DDRC_BASE_ADDRESS + 0x84
CS2_CONFIG_OFFSET = DDRC_BASE_ADDRESS + 0x88
CS3_CONFIG_OFFSET = DDRC_BASE_ADDRESS + 0x8C

fw_versions = ['2017.09', '2018.10', '2019.04', '2020.06']
dram_types = ['ddr3', 'ddr4', 'lpddr4']
ODT_IMPEDANCE_MAP = {'0': 0, '1': 480, '2': 240, '3': 160, '8': 120, '9': 96, '10': 80, '11': 68, '24': 60, '25': 53,
                     '26': 48, '27': 43, '56': 40, '57': 36, '58': 34, '59': 32, '62': 30, '63': 28}
ATX_IMPEDANCE_MAP = {'0': 120, '1': 60, '3': 40, '7': 30, '15': 24, '31': 20}


def swap_16(x):  # type: ignore
    """Swaps the bytes of a 16-bit integer number.

    @type x: int
    @param x: 16-bit integer number to swap
    @rtype: int
    @return: the swapped value of the provided integer
    """
    return ((x << 8) & 0xFF00) | ((x >> 8) & 0x00FF)


def map_phy_addr_space(addr):  # type: ignore
    """TODO:summary line."""
    # PState - 22:20 (Which copy of the per PState register is active)
    pstate = (addr & (0x7 << 20)) >> 20

    # Block Type - 19:16 (Which copy of the per PState register is active)
    block_type = (addr & (0xf << 16)) >> 16

    # Instance Number - 15:12 (Which copy of the per PState register is active)
    instance = (addr & (0xf << 12)) >> 12

    # Register - 11:0 (The particular register which is being accessed in an instance)
    reg = addr & 0xfff

    soc_paddr = 0

    if block_type == 0x0:  # ANIB
        soc_paddr = 0xc * pstate + instance
    elif block_type == 0x1:  # DBYTE
        soc_paddr = 0x30 + 0xa * pstate + instance
    elif block_type == 0x2:  # MASTER
        soc_paddr = 0x58 + pstate
    elif block_type == 0x4:  # ACSM
        soc_paddr = 0x5c + pstate
    elif block_type == 0x5:  # uCTL Memory
        soc_paddr = 0x60 + instance
    elif block_type == 0x7:  # PPGC
        soc_paddr = 0x68
    elif block_type == 0x9:  # INITENG
        soc_paddr = 0x69 + pstate
    elif block_type == 0xC:  # DRTUB
        soc_paddr = 0x6d
    elif block_type == 0xD:  # APB Only
        soc_paddr = 0x6e

    return (soc_paddr << 12) + reg


def phy_io_addr(ctrl_id, addr):  # type: ignore
    """TODO:summary line."""
    ddr_phy_ccsr_base = 0
    if ctrl_id == 0:
        ddr_phy_ccsr_base = CCSR_DDR_PHY1_ADDR
    elif ctrl_id == 1:
        ddr_phy_ccsr_base = CCSR_DDR_PHY2_ADDR
    return ddr_phy_ccsr_base + (map_phy_addr_space(addr) << 2)


def my_print(text):  # type: ignore
    """TODO:summary line."""
#     # TODO: define DEBUG_ENABLED and DEBUG_LOG
#     if not DEBUG_ENABLED:
#         return
#     with open(DEBUG_LOG, 'a') as log:
#         log.write(text)
#         log.write('\n')


def read_rcw_one_reg(ccs_channel) -> int:  # type: ignore
    """TODO:summary line."""
    rcwsr_offset = DCFG_CCSR + 0x100

    try:
        pllRegValue = int(ccs_channel.read_data(rcwsr_offset, 4, 1), 16)
        memPllRate = (pllRegValue >> 10) & 0x3F
        memPllCfgDiv = 1.0 / (((pllRegValue >> 8) & 0x3) + 1)
        pllRate = int(memPllRate * memPllCfgDiv * 4)
        return pllRate
    except Exception as ex:
        print('Import failed: ' + str(ex))
        return -1


def parse_hex(data: str, i: int):  # type: ignore
    """Parse hex format data."""
    return data[(i * 8 + 6):(i * 8 + 6) + 2] \
        + data[(i * 8 + 4):(i * 8 + 4) + 2] \
        + data[(i * 8 + 2):(i * 8 + 2) + 2] \
        + data[i * 8:i * 8 + 2]


def get_int_value(hexStr: str):  # type: ignore
    """TODO:summary line."""
    return int(hexStr.replace('0x', ''), 16)


def import_from_target():  # type: ignore
    """Imports a ddr configuration from the target."""
    # Info : DDR Phy Mode Registers

    # MR0    Byte offset 0x5e, CSR Addr 0x5402f, Direction=In
    # Value of DDR mode register MR0 for all ranks for current pstate
    # MR1    Byte offset 0x60, CSR Addr 0x54030, Direction=In
    # Value of DDR mode register MR1 for all ranks for current pstate
    # MR2    Byte offset 0x62, CSR Addr 0x54031, Direction=In
    # Value of DDR mode register MR2 for all ranks for current pstate
    # MR3    Byte offset 0x64, CSR Addr 0x54032, Direction=In
    # Value of DDR mode register MR3 for all ranks for current pstate
    # MR4    Byte offset 0x66, CSR Addr 0x54033, Direction=In
    # Value of DDR mode register MR4 for all ranks for current pstate
    # MR5    Byte offset 0x68, CSR Addr 0x54034, Direction=In
    # Value of DDR mode register MR5 for all ranks for current pstate
    # MR6    Byte offset 0x6a, CSR Addr 0x54035, Direction=In
    # Value of DDR mode register MR6 for all ranks for current pstate. Note: The initial VrefDq value and range must
    # be set in A6:A0.

    # uint8_t  AcsmOdtCtrl0;     Byte offset 0x7e, CSR Addr 0x5403f, Direction=In
    # Odt pattern for accesses targeting rank 0. [3:0] is used for write ODT [7:4] is used for read ODT
    # uint8_t  AcsmOdtCtrl1;     Byte offset 0x7f, CSR Addr 0x5403f, Direction=In
    # Odt pattern for accesses targeting rank 1. [3:0] is used for write ODT [7:4] is used for read ODT
    # uint8_t  AcsmOdtCtrl2;     Byte offset 0x80, CSR Addr 0x54040, Direction=In
    # Odt pattern for accesses targeting rank 2. [3:0] is used for write ODT [7:4] is used for read ODT
    # uint8_t  AcsmOdtCtrl3;     Byte offset 0x81, CSR Addr 0x54040, Direction=In
    # Odt pattern for accesses targeting rank 3. [3:0] is used for write ODT [7:4] is used for read ODT

    # DqDqsRcvCntrl              Byte offset 0x43, Addr 0x010043, Direction=In
    # Connected to the rxdqs and rxdq Mode selects and trim controls, per nibble. [3:2] is used for DfeCtrl
    # TxImpedanceCtrl0           Byte offset 0x041, Addr 0x010041, Direction=In
    # Tx impedance of DQ driver cells when equalization is disabled. [5:0] is used for  DrvStrenFSDqP (TX_IMPEDANCE)
    # TxImpedanceCtrl1           Byte offset 0x049, Addr 0x010049, Direction=In
    # Tx impedance of DQ driver cells when equalization is disabled. [5:0] is used for  DrvStrenFSDqP (TX_IMPEDANCE)
    # TxOdtDRVStren              Byte offset 0x04D, Addr 0x01004D, Direction=In
    # Selects desired impedance value for Host ODT (ODT_IMPEDANCE)
    # VrefDAC0                   Byte offset 0x40, Addr 0x010040, Direction=In
    # Controls DQ Receiver. [6:0] is used for Phy Vref
    # VrefDAC1                   Byte offset 0x30, Addr 0x54043, Direction=In
    # control for DQ Receiver (used only when DFE is enabled in DDR4).[6:0] is used for Dram Vref

    parser = argparse.ArgumentParser(description='Generate PHY configuration using SNPS driver and firmware',
        epilog=f'Supported firmware versions = {fw_versions}.<br>Supported DRAM types = {dram_types}')
    parser.add_argument('file', nargs='+', type=argparse.FileType('r'),
        help='JSON format files containing test parameters')
    parser.add_argument('-d', '--dram-type', choices=dram_types, help="DRAM type")
    parser.add_argument('-f', '--firmware-version', choices=fw_versions, help='Firmware version')
    parser.add_argument('-t', '--data-dir', default=os.getcwd(), help='Data path')
    parser.add_argument('-o', '--output-dir', default=os.getcwd(), help='Output directory path')
    parser.add_argument('-l', '--log', choices=['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'], default='CRITICAL',
        help='Specifies logging level')

    start = time.time()

    args = parser.parse_args()
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(name)s %(message)s', level=getattr(logging, args.log))

    # TODO: see if phy_config_file is needed
    phy_config_file = ''
    _params = {}
    for file in args.file:
        _params = add_file_to_params(file.name, _params)
        if file.name.endswith('phy.json'):
            phy_config_file = file.name
    _params[Const.PARAM_S_TC][Const.PARAM_S_TC_FW] = fw_versions.index(args.firmware_version)

    config_data = ConfigData(args.data_dir, _params)
    config_data.mem_type = args.dram_type

    # create destination folder if it does not exist
    if not os.path.isdir(args.output_dir):
        logger.info('Create directory %s', os.path.abspath(args.output_dir))
        os.mkdir(args.output_dir)
    Workspace.get_instance().set_location(args.output_dir)

    # call synopsys phy init
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir))
    logger.debug("chdir %s", os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir))

    processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)

    ccs_channel = BackendFactory.make_unique_instance(config_data.connect_params)
    if not ccs_channel.is_alive():
        ccs_channel.open(config_data)  # assert ccs_channel.is_alive()

    try:
        # Read RCW to extract PLL RATE
        pllRate = read_rcw_one_reg(ccs_channel) * 100
        processor.init_reg_calc(config_data)
        # Check if second controller is enabled
        secondCtrlAddress = DDRC_BASE_ADDRESS + 0x10000
        raw_data = ccs_channel.read_data(secondCtrlAddress, 4, 1)
        NUMBER_OF_CONTROLLERS = 1 if (int(parse_hex(raw_data, 0), 16) == 0) else 2

        # update DATA RATE in reg_calc.xls
        config_data.params[Const.PARAM_S_BASIC]['ddrDataRateMbps'] = str(pllRate)
        config_data.params[Const.PARAM_S_BASIC]['numberOfControllersEnabled'] = NUMBER_OF_CONTROLLERS

        # Run RPA tool
        processor.ddrc_reg_calc(config_data)

        end = time.time()
        logger.info("Start reading DDR controller and PHY registers %f", end - start)

        # Read DDR controller and PHY registers
        regs = {}
        for i in range(NUMBER_OF_CONTROLLERS):
            ctrl_id = i
            base_addr = DDRC_BASE_ADDRESS + ctrl_id * 0x10000
            access = 4
            size = int(0xF00 / access)  # 960
            raw_data = ccs_channel.read_data(base_addr, access, size)

            # Read DDR controller registers
            for j in range(size):
                regs['0x%08X' % (base_addr + j * 4)] = '0x' + parse_hex(raw_data, j)

        access = 2
        ctrl_id = 0
        size = 1
        ccs_channel.write_data(phy_io_addr(ctrl_id, 0x0d0000), access, (0x0000).to_bytes(4, byteorder='little'))
        ccs_channel.write_data(phy_io_addr(ctrl_id, 0x0c0080), access, (0x0003).to_bytes(4, byteorder='little'))

        # Read MR registers - Addresses from 0x5402f to 0x54035 belong to DDR Phy Mode Registers
        for k in range(0x5402f, 0x54036):
            mrk = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, k), 2, size)), 16))
            regs['MR%s' % (k - 0x5402f)] = '0x%04x' % mrk

        # Read AcsmOdtCtrl0, AcsmOdtCtrl1, AcsmOdtCtrl2, AcsmOdtCtrl3 from 0x5403f and 0x54040
        reg_id = 0x5403f
        acsmOdtCtrl_0_1 = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
        regs['rdODT0'] = str((acsmOdtCtrl_0_1 >> 4) & 0xF)
        regs['rdODT1'] = str(acsmOdtCtrl_0_1 >> 12)
        regs['wrODT0'] = str(acsmOdtCtrl_0_1 & 0xF)
        regs['wrODT1'] = str((acsmOdtCtrl_0_1 >> 8) & 0xF)

        reg_id = 0x54040
        acsmOdtCtrl_2_3 = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
        regs['rdODT2'] = str((acsmOdtCtrl_2_3 >> 4) & 0xF)
        regs['rdODT3'] = str(acsmOdtCtrl_2_3 >> 12)
        regs['wrODT2'] = str(acsmOdtCtrl_2_3 & 0xF)
        regs['wrODT3'] = str((acsmOdtCtrl_2_3 >> 8) & 0xF)

        # Read DFE
        reg_id = 0x010043
        dfe = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
        dfe_3_2 = (dfe >> 2) & 0x3
        if dfe_3_2 == 0:
            # Read TxImpedanceCtrl1 - TX_IMPEDANCE
            reg_id = 0x010049
            TxImpCtrl1 = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
            TxImpedance = str(TxImpCtrl1 & 0x3F)
        else:
            # Read TxImpedanceCtrl0 - TX_IMPEDANCE
            reg_id = 0x010041
            TxImpCtrl0 = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
            TxImpedance = str(TxImpCtrl0 & 0x3F)

        if str(TxImpedance) in ODT_IMPEDANCE_MAP:
            idx = ODT_IMPEDANCE_MAP[str(TxImpedance)]
            regs['TxImpedance'] = str(idx)

        # Read TxOdtDRVStren - ODT_IMPEDANCE
        reg_id = 0x01004D
        ODTImpedance = 0x3F & (swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16)))
        if str(ODTImpedance) in ODT_IMPEDANCE_MAP:
            idx = ODT_IMPEDANCE_MAP[str(ODTImpedance)]
            regs['ODTImpedance'] = str(idx)

        # Read ATxImpedance 0x000043
        reg_id = 0x000043
        ATxImpedance = 0x1F & (swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16)))
        if str(ATxImpedance) in ATX_IMPEDANCE_MAP:
            idx = ATX_IMPEDANCE_MAP[str(ATxImpedance)]
            regs['ATxImpedance'] = str(idx)

        # Read RX2D_trainOpt # 0
        register = 0x5400c
        value = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, register), 1, size)), 16)) & 0xFF
        # regs['RX2D_trainOpt'] = str(value)

        # Read TX2D_trainOpt    # 0
        register = 0x5400d
        value = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, register), 2, size)), 16))
        # regs['TX2D_trainOpt'] = str('0x%x'% ((value & 0xFF00) >> 8))
        # regs['Share_2dVref'] = str('0x%x'% (value & 0xFF))

        # Read Delay_weight2d # 0x7f
        # Read Volt_weight2d    #0x1f
        register = 0x5400e
        value = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, register), 2, size)), 16))
        # regs['Delay_weight2d'] = str('0x%x'% ((value & 0xFF00) >> 8))
        # regs['Volt_weight2d'] = str('0x%x'% (value & 0xFF))

        # Read Dram Vref
        register = 0x54043
        dram_vref = 0
        for lane in range(0, 10):
            reg_id = register + lane
            value = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
            dram_vref += (value & 0xFF) + (value >> 8)
        dram_vref /= 20

        # Read PHY Vref
        register = 0x010040
        register_values = 0
        for lane in range(0, 8):
            reg_id = (lane << 8) | register
            value = swap_16(int(str(ccs_channel.read_data(phy_io_addr(ctrl_id, reg_id), 2, size)), 16))
            register_values += value
        register_values /= 8
        # calculate trained vref controller value
        phy_vref = int(((register_values * 0.00345) + 0.510) * 128)
        regs['PhyVref'] = '0x%X' % phy_vref

        ccs_channel.write_data(phy_io_addr(ctrl_id, 0x0c0080), access, (0x0).to_bytes(4, byteorder='little'))
        ccs_channel.write_data(phy_io_addr(ctrl_id, 0x0d0000), access, (0x1).to_bytes(4, byteorder='little'))

        # terminate validation session by disconnecting
        end = time.time()
        logger.info("Import from target time %f", end - start)

        # Flush the output stream regularly
        sys.stdout.flush()

        # Update .DS fields based on DDRc registers values (that were read above)
        dbw = (get_int_value(regs['0x01080110']) & 0x180000) >> 19
        eccEnabled = (get_int_value(regs['0x01080110']) & 0x20000000) >> 29
        regDimmEnabledEnabled = (get_int_value(regs['0x01080110']) & 0x10000000) >> 28
        cs0Enabled = 0 if (get_int_value(regs[str('0x%08X' % CS0_CONFIG_OFFSET)]) == 0) else 1
        cs1Enabled = 0 if (get_int_value(regs[str('0x%08X' % CS1_CONFIG_OFFSET)]) == 0) else 1
        cs2Enabled = 0 if (get_int_value(regs[str('0x%08X' % CS2_CONFIG_OFFSET)]) == 0) else 1
        cs3Enabled = 0 if (get_int_value(regs[str('0x%08X' % CS3_CONFIG_OFFSET)]) == 0) else 1
        number_of_ranks = cs0Enabled + cs1Enabled + cs2Enabled + cs3Enabled
        cs_on_dimm = 0x1 if (number_of_ranks == 1) else (0x3 if (number_of_ranks == 2) else 0xF)
        regs['data_width'] = str((64 if (dbw == 0) else 32) + (8 if (eccEnabled == 1) else 0))
        regs['dimm_type'] = str(2 if (regDimmEnabledEnabled == 1) else 0)  # UDIMM=0,SODIMM=1,RDIMM=2,LRDIMM=3,No DIMM=4
        regs['csPresent'] = str(cs_on_dimm)
        regs['numberOfRanks'] = str(number_of_ranks)

        workspace_dir = Workspace.get_instance().get_location()
        # Generate DS file
        processor.update_ds_file_ddrc_config(config_data, regs)
        with open(os.path.join(workspace_dir,
            f"{config_data.mem_type}{Const.DS_FILE_SUFFIX}"), 'w', encoding='utf-8') as f:
            f.write(config_data.ds_file_txt)

        if not config_data.ds_is_valid:
            raise Exception('DS file generation ended with errors!')

        # Update configData based on .ds file content
        processor.update_diags_params(config_data)
        # update PHY input and DDRC config using DS file
        processor.update_connection_parameters(config_data)
        # Parses ds file and updates config_data with DDRc registers
        processor.update_ddrc_config(config_data)
        processor.update_phy_config(config_data)

        # create DDR controller configuration file
        ddrc_config_file = os.path.join(workspace_dir, "ddrc_config_final.json")
        with open(ddrc_config_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(config_data.ddrc_config_full, indent=4))

        # create file with updated PHY config
        phy_config_file = os.path.join(workspace_dir, "phy_config_final.json")
        with open(phy_config_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(config_data.params[Const.PARAM_S_PHY], indent=4))

    except Exception as ex:
        print(f'Exception: Connection issue.{ex}')

    finally:
        ccs_channel.close()


import_from_target()
