# Copyright 2023-2025 NXP
"""TODO:summary line."""
import logging
import math
import os
from copy import deepcopy
from enum import Enum
from json import JSONDecodeError
from typing import List

import commentjson

from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import DCDCommandIds, get_dcd_command
from memtool.phyinit.phy_utils import PhyPhase
from memtool.utils.constants import Const


class ErrataUpdatePolicyType(Enum):
    """Errata update policy."""

    UPDATE_CMD = 'update'
    APPEND_CMD = 'append'


class ErrataType(Enum):
    """Errata type."""

    PHY_INIT = PhyPhase.PHY_INIT_CONFIG.name
    LOAD_PIE = PhyPhase.LOAD_PIE.name


class ErrataCommand:
    """Class for storing errata command."""

    def __init__(self, mode: ErrataUpdatePolicyType, command: int, address: str, value: str):
        """TODO:summary line."""
        self.mode = mode
        self.command = command
        self.address = address
        self.value = value


class ErrataLibrary:
    """Base class for loading errata."""

    logger = logging.getLogger(__name__)

    ERRATA_COMMANDS = 'commands'
    # number of arguments for errata specified by PHY commands
    # (e.g. ["update", "phy set", "0x20021", "0x0", ["lpddr4"]])
    ERRATA_BY_CMD_NO_ARGS = 5
    # number of arguments for errata specified by PHY commands per pstate
    # (e.g. ["update", "phy set", "0x20021", "0x0", ["lpddr4"], [0, 1]])
    ERRATA_PER_FSP_BY_CMD_NO_ARGS = 6

    ERRATA_FUNCTIONS = 'functions'
    # number of arguments for errata specified by functions name
    # (e.g. ["update", "err3256585", ["lpddr4"]])
    ERRATA_BY_NAME_NO_ARGS = 3
    # number of arguments for errata specified by functions name per pstate
    # (e.g. ["update", "err3256585", ["lpddr4"], [2, 5]])
    ERRATA_PER_FSP_BY_NAME_NO_ARGS = 4

    ERRATA_MODE_IDX = 0
    ERRATA_BY_NAME_NAME_IDX = 1
    ERRATA_BY_NAME_DRAM_IDX = 2
    ERRATA_BY_NAME_FSP_IDX = 3
    ERRATA_BY_CMD_CMD_IDX = 1
    ERRATA_BY_CMD_ADDR_IDX = 2
    ERRATA_BY_CMD_VAL_IDX = 3
    ERRATA_BY_CMD_DRAM = 4
    ERRATA_BY_CMD_FSP_IDX = 5

    @staticmethod
    def load_erratas(config_data: ConfigData):  # type: ignore
        """Load erratas for the specified processor; loaded data will be cached in config_data.erratas[processor name].

        @param config_data: configuration data
        """
        # At the end, loaded errata info it will contain commands and functions;
        # when errata info is needed, commands will be applied as they are,
        # functions will be executed for the current configuration
        # and the corresponding commands will be applied to the PHY init configuration.
        # For example, the loaded data for MIMX93 will be like this:
        # 'MIMX93' = {
        #    ErrataType.PHY_INIT: {
        #       'lpddr4': {
        #          'commands': [ErrataCommand object, ErrataCommand object],
        #          'functions': [('err4101789', ErrataUpdatePolicyType.UPDATE_CMD)],
        #          '0' { # per pstate
        #              'commands': [ErrataCommand object, ErrataCommand object],
        #              'functions': [('err4101789', ErrataUpdatePolicyType.UPDATE_CMD)],
        #          }
        #       }
        #    },
        #    ErrataType.LOAD_PIE = {
        #       lpddr4' = {
        #          'commands' = [],
        #          'functions' = {list: 1}[('err3256585', ErrataUpdatePolicyType.UPDATE_CMD)]
        #       }
        #    }
        # }

        config_data.erratas[config_data.soc_name] = {}

        erratas_folder = os.path.join(config_data.data_dir, Const.ERRATAS_DIR_NAME)
        errata_file_name = f'{config_data.soc_name}_errata.json'
        errata_file = os.path.join(erratas_folder, errata_file_name)

        if not os.path.exists(errata_file):
            ErrataLibrary.logger.info('No erratas to be applied for %s', config_data.soc_name)
            return

        errata_dict = {}
        with open(errata_file, 'r', encoding='utf-8') as erratas:
            try:
                errata_dict = commentjson.loads(erratas.read())
            except JSONDecodeError as e:
                ErrataLibrary.logger.error('Error while importing erratas for %s', str(e))
                return

        for errata_type_str in errata_dict:
            if errata_type_str not in [m.value for m in ErrataType]:
                ErrataLibrary.logger.error('Error while parsing errata dictionary; invalid type was found (%s).',
                    errata_type_str)
                return
            errata_type = ErrataType(errata_type_str)

            config_data.erratas[config_data.soc_name][errata_type] = {}
            for errata in errata_dict[errata_type_str]:
                # get number of parameters and validate it
                errata_no_params = len(errata)
                if errata_no_params != ErrataLibrary.ERRATA_BY_NAME_NO_ARGS and \
                   errata_no_params != ErrataLibrary.ERRATA_PER_FSP_BY_NAME_NO_ARGS and \
                   errata_no_params != ErrataLibrary.ERRATA_BY_CMD_NO_ARGS and \
                   errata_no_params != ErrataLibrary.ERRATA_PER_FSP_BY_CMD_NO_ARGS:
                    ErrataLibrary.logger.error('Error while parsing errata command: %s (%s);'
                                               ' invalid number of parameters.', errata, errata_type)
                    return

                # get mode and validate it
                mode_str = errata[ErrataLibrary.ERRATA_MODE_IDX].lower()
                if mode_str not in [m.value for m in ErrataUpdatePolicyType]:
                    ErrataLibrary.logger.error('Error while parsing errata command: %s (%s);'
                                               ' invalid mode was found (%s).', errata, errata_type, mode_str)
                    return
                mode = ErrataUpdatePolicyType(mode_str)

                fsps = []
                errata_commands = []
                errata_functions = []
                if errata_no_params == ErrataLibrary.ERRATA_BY_CMD_NO_ARGS or \
                   errata_no_params == ErrataLibrary.ERRATA_PER_FSP_BY_CMD_NO_ARGS:
                    cmd = get_dcd_command(errata[ErrataLibrary.ERRATA_BY_CMD_CMD_IDX].lower())
                    if cmd == DCDCommandIds.UNKNOWN:
                        ErrataLibrary.logger.error('Error while parsing errata command: %s (%s);'
                                                   ' invalid command was found (%s).', errata, errata_type, errata[1])
                        return
                    errata_commands.append(ErrataCommand(mode, cmd, errata[ErrataLibrary.ERRATA_BY_CMD_ADDR_IDX],
                        errata[ErrataLibrary.ERRATA_BY_CMD_VAL_IDX]))
                    dram_types = [dram.lower() for dram in errata[ErrataLibrary.ERRATA_BY_CMD_DRAM]]
                    if errata_no_params == ErrataLibrary.ERRATA_PER_FSP_BY_CMD_NO_ARGS:
                        fsps = [str(fsp) for fsp in errata[ErrataLibrary.ERRATA_BY_CMD_FSP_IDX]]
                else:  # for erratas specified by errata function name
                    errata_functions.append((errata[ErrataLibrary.ERRATA_BY_NAME_NAME_IDX], mode))
                    dram_types = [dram.lower() for dram in errata[ErrataLibrary.ERRATA_BY_NAME_DRAM_IDX]]
                    if errata_no_params == ErrataLibrary.ERRATA_PER_FSP_BY_NAME_NO_ARGS:
                        fsps = [str(fsp) for fsp in errata[ErrataLibrary.ERRATA_BY_NAME_FSP_IDX]]

                for dram in dram_types:
                    if dram not in ConfigData.DRAM_TYPES.values():
                        ErrataLibrary.logger.error('Error while parsing errata command: %s (%s);'
                                                   ' unsupported dram type.', errata, errata_type)
                        return

                    if dram not in config_data.erratas[config_data.soc_name][errata_type]:
                        config_data.erratas[config_data.soc_name][errata_type][dram] = {}
                        config_data.erratas[config_data.soc_name][errata_type][dram][ErrataLibrary.ERRATA_COMMANDS] = []
                        config_data.erratas[config_data.soc_name][errata_type][dram][
                            ErrataLibrary.ERRATA_FUNCTIONS] = []

                    for fsp in fsps:
                        if fsp not in config_data.erratas[config_data.soc_name][errata_type][dram]:
                            config_data.erratas[config_data.soc_name][errata_type][dram][fsp] = {}
                            config_data.erratas[config_data.soc_name][errata_type][dram][fsp][
                                ErrataLibrary.ERRATA_COMMANDS] = []
                            config_data.erratas[config_data.soc_name][errata_type][dram][fsp][
                                ErrataLibrary.ERRATA_FUNCTIONS] = []

                    for e in errata_commands:  # type: ignore
                        if fsps:
                            for fsp in fsps:
                                config_data.erratas[config_data.soc_name][errata_type][dram][fsp][
                                    ErrataLibrary.ERRATA_COMMANDS].append(e)
                        else:
                            config_data.erratas[config_data.soc_name][errata_type][dram][
                                ErrataLibrary.ERRATA_COMMANDS].append(e)

                    for e in errata_functions:  # type: ignore
                        if fsps:
                            for fsp in fsps:
                                config_data.erratas[config_data.soc_name][errata_type][dram][fsp][
                                    ErrataLibrary.ERRATA_FUNCTIONS].append(e)
                        else:
                            config_data.erratas[config_data.soc_name][errata_type][dram][
                                ErrataLibrary.ERRATA_FUNCTIONS].append(e)

    @staticmethod
    def get_errata(config_data: ConfigData, errata_type: ErrataType, fsp: str = '') -> List[ErrataCommand]:
        """Get erratas of specified type for the specified processor.

        if erratas are loaded yet, first they will be loaded and be cached in config_data.erratas[processor name]
        Erratas will be appended to the corresponding sections from config_data.phy_full_config, so errata_type
        should match PHY output sections

        @param config_data: configuration data
        @param errata_type: errata type
        @param fsp: frequency point
        @return: the list of errata commands that implements specified errata_type
        """
        if config_data.soc_name not in config_data.erratas:
            ErrataLibrary.load_erratas(config_data)

        if errata_type in config_data.erratas[config_data.soc_name]:
            dram = ConfigData.DRAM_TYPES[config_data.dram_type]
            if dram in config_data.erratas[config_data.soc_name][errata_type]:
                if fsp and fsp in config_data.erratas[config_data.soc_name][errata_type][dram]:
                    erratas = deepcopy(
                        config_data.erratas[config_data.soc_name][errata_type][dram][fsp][ErrataLibrary.ERRATA_COMMANDS]
                    )
                    for errata in config_data.erratas[config_data.soc_name][errata_type][dram][fsp][
                        ErrataLibrary.ERRATA_FUNCTIONS]:
                        erratas.extend(get_errata_by_name(errata[0], errata[1], config_data))
                else:
                    erratas = deepcopy(
                        config_data.erratas[config_data.soc_name][errata_type][dram][ErrataLibrary.ERRATA_COMMANDS])
                    for errata in config_data.erratas[config_data.soc_name][errata_type][dram][
                        ErrataLibrary.ERRATA_FUNCTIONS]:
                        erratas.extend(get_errata_by_name(errata[0], errata[1], config_data))
                return erratas
        return []


def err3256585(mode: ErrataUpdatePolicyType, config_data: ConfigData) -> List[ErrataCommand]:
    """DFT0578472A	When using multiple PSTATEs, PLL Lock Time may not be sufficient.

    @param mode: command update policy
    @param config_data: processor configuration data
    @return: the list of errata commands
    """
    if config_data.num_pstates == 1:
        return []

    erratas = []
    for pstate in range(config_data.num_pstates):
        Seq0BDLY0_ADDR = hex(0x20000 | (pstate << 20) | 0x0B)

        dfi_freq = -1.0
        dfi_key = f'Frequency[{pstate}]'
        if Const.PARAM_S_PHY in config_data.params:
            if Const.PARAM_S_PHY_INPUT_BASIC in config_data.params[Const.PARAM_S_PHY]:
                if dfi_key in config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]:
                    dfi_freq = float(
                        config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][dfi_key]) * 0.5
        if dfi_freq < 0:
            ErrataLibrary.logger.error('err3256585 errata could not be applied; %s was not found!', dfi_key)

        value = hex(math.ceil(4.5 * 0.25 * dfi_freq))
        erratas.append(ErrataCommand(mode, DCDCommandIds.CMD_PHY_WRITE_DATA, Seq0BDLY0_ADDR, value))
    return erratas


def err4101789(mode: ErrataUpdatePolicyType, config_data: ConfigData) -> List[ErrataCommand]:
    """DFT0604469A	Potential PLL issue when using Fbk div. ratio of 16 (DfiClk from 166-312.5 MHz).

    @param mode: command update policy
    @param config_data: processor configuration data
    @return: the list of errata commands
    """
    erratas = []  # type: ignore
    for pstate in range(config_data.num_pstates):
        pll_bypass_key = f'PllBypass[{pstate}]'
        if int(config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][pll_bypass_key]):
            return erratas

        PllCtrl1_ADDR = hex(0x20000 | (pstate << 20) | 0xC7)
        PllCtrl2_ADDR = hex(0x20000 | (pstate << 20) | 0xC5)

        dfi_freq = -1.0
        dfi_key = f'Frequency[{pstate}]'

        if Const.PARAM_S_PHY in config_data.params:
            if Const.PARAM_S_PHY_INPUT_BASIC in config_data.params[Const.PARAM_S_PHY]:
                if dfi_key in config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]:
                    dfi_freq = float(
                        config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][dfi_key]) * 0.5
                    if 235 < dfi_freq < 313:
                        erratas.append(ErrataCommand(mode, DCDCommandIds.CMD_PHY_WRITE_DATA, PllCtrl2_ADDR, '0x2'))
                        erratas.append(ErrataCommand(mode, DCDCommandIds.CMD_PHY_WRITE_DATA, PllCtrl1_ADDR,
                            '0x41'))  # err4101789 merged with err3975199 marker (0x40 + 0x1)
                    elif dfi_freq < 235:
                        erratas.append(ErrataCommand(mode, DCDCommandIds.CMD_PHY_WRITE_DATA, PllCtrl2_ADDR, '0x3'))
                        erratas.append(ErrataCommand(mode, DCDCommandIds.CMD_PHY_WRITE_DATA, PllCtrl1_ADDR,
                            '0x41'))  # err4101789 merged with err3975199 marker (0x40 + 0x1)

        if dfi_freq < 0:
            ErrataLibrary.logger.error('err4101789 errata could not be applied; %s was not found!', dfi_key)
    return erratas

def rx_replica(mode: ErrataUpdatePolicyType, config_data: ConfigData) -> List[ErrataCommand]:
    """DFT0604469A	Potential PLL issue when using Fbk div. ratio of 16 (DfiClk from 166-312.5 MHz).

    @param mode: command update policy
    @param config_data: processor configuration data
    @return: the list of errata commands
    """
    Rx_replica = 'rx_replica'
    if int(config_data.misc_sys_params[Rx_replica]) == 0:
        return []

    erratas = []  # type: ignore

    freq_factor = 0.25 if config_data.mem_type in ["lpddr4", "lpddr4x"] else 1
    dram_pll = -1.0
    dfi_key = 'Frequency[0]'

    if dfi_key in config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]:
        dram_pll = float(
            config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][dfi_key]) * freq_factor

    freq = int(dram_pll * 2 / 100)
    rxReplicaCtl04_VAL = (freq << 8) | 0x87

    Num_dbyte_per_ch = 'NumDbytesPerCh'
    Num_ch = 'NumCh'
    numDbyte = int(config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][Num_dbyte_per_ch]) * \
        int(config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][Num_ch])

    for byte in range(numDbyte):
        rxReplicaCtl04_ADDR = hex(0x10000 | (byte << 12) | 0xF)
        erratas.append(ErrataCommand(mode, DCDCommandIds.CMD_PHY_WRITE_DATA, rxReplicaCtl04_ADDR,
                                     hex(rxReplicaCtl04_VAL)))

    return erratas


FUNCTION_DICTIONARY = {'err3256585': err3256585, 'err4101789': err4101789, 'rx_replica': rx_replica}


def get_errata_by_name(errata_name: str, mode: ErrataUpdatePolicyType, config_data: ConfigData) -> List[ErrataCommand]:
    """Get commands that implements requested errata.

    @param errata_name: name of errata
    @param mode: command update policy
    @param config_data: processor configuration data
    @return: the list of errata commands
    """
    if errata_name not in FUNCTION_DICTIONARY:
        ErrataLibrary.logger.error('Error while parsing errata command; unsupported errata %s.', errata_name)
        return []

    return FUNCTION_DICTIONARY.get(errata_name)(mode, config_data)  # type: ignore
