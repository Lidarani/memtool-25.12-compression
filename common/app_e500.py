# Copyright 2023 - 2024 NXP
"""AppInterface for e500 (LA target)."""
import logging
import os
from enum import Enum
from typing import Optional, Tuple

from memtool.common.app import AppInterface, ApplicationType
from memtool.common.config_data import ConfigData


class AppInterfaceE500(AppInterface):
    """AppInterface for e500 (LA target).

    Model mapping between front-end and application-level entities.
    """

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input, so it should be instantiated.

        @param args: list of parameters used to determine if this class should be instantiated
        @return: True if this class can handle the input
        """
        for app_arg in args[0]:
            if isinstance(app_arg, Enum):
                return app_arg == ApplicationType.LA
        return False

    def __init__(self, app_type, app_path, app_timestamp, app_symbol_names, entry_point):  # type: ignore
        """Constructor.Asserts test application executable exists.

        @param app_type: application type
        @param app_path: path of test application
        @param app_timestamp: binary modification date
        @param app_symbol_names: list of symbols that
        @param entry_point: entry point
        """
        super(AppInterfaceE500, self).__init__(app_type, app_path, app_timestamp, app_symbol_names, entry_point)

    def init_sym_table(self, sym_file_path):  # type: ignore
        """Override app method. Initiate symbol dictionary.

        On CW for e500, addresses are on 2d column in the sysms file.
        """
        self.sym_table = {}
        if not os.path.isfile(sym_file_path):
            return

        with open(sym_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if any(s in line for s in self.symbols):
                    cols = line.split()
                    # on LA target, the address is on the 2nd column
                    self.sym_table[cols[-1]] = int(cols[1], 16)

    def update_config_data(self, config_data: ConfigData):  # type: ignore
        """Override app method.

        @param config_data: configuration data
        """
        config_data.target_params['start_addr'] = self.sym_table["__start"]
        config_data.target_params['workspace_address'] = '0x%x' % self.sym_table["__START_ADDRESS"]
        config_data.target_params['dcd_addr'] = '0x%x' % (self.sym_table["g_log_level"] + 16)
        self.sym_table['PEB_offset'] = config_data.connect_params['PEB_offset']

    def get_param_symbol(self, param: str) -> Optional[Tuple[int, int, int]]:
        """Override app method."""
        symb = {
            'test': (self.sym_table['TEST_IN'] + 0x0, 4, 1),
            'pattern': (self.sym_table['TEST_IN'] + 0x4, 1, 1),
            'loopback': (self.sym_table['TEST_IN'] + 0x5, 1, 1),
            'countwindow': (self.sym_table['TEST_IN'] + 0x6, 1, 1),
            'path': (self.sym_table['TEST_IN'] + 0x8, 4, 1),
            'laneNumber': (self.sym_table['TEST_IN'] + 0xC, 1, 1),
            'insertErrorCount': (self.sym_table['TEST_IN'] + 0xD, 1, 1),
            'pllNumber' : (self.sym_table['TEST_IN'] + 0xE, 1, 1),
            'mode' : (self.sym_table['TEST_IN'] + 0xF, 1, 1),
            'pattern_length' : (self.sym_table['TEST_IN'] + 0x10, 4, 1),
            'double_speed' : (self.sym_table['TEST_IN'] + 0x14, 1, 1),
            'params': (self.sym_table['TEST_IN'] + 0x15, 4, 16),
        }.get(param, None)
        if symb is None:
            self.logger.warning('Unknown parameter: %s!', param)
        return symb

    def get_result_symbol(self, result: str) -> Optional[Tuple[int, int, int]]:
        """Override app method."""
        symb = {
            'start': (self.sym_table['__start'], 4, 1),
            'phy_status': (self.sym_table['g_sys_params'] + 4, 4, 1),
            'num_logged_items': (self.sym_table['g_sys_params'] + 8, 4, 1),
            'app_state': (self.sym_table['TEST_OUT'] + 0, 4, 1),
            'num_records': (self.sym_table['TEST_OUT'] + 4, 4, 1),
            'debug': (self.sym_table['TEST_OUT'] + 1160, 4, 8),
            'err_capt_regs': (self.sym_table['TEST_OUT'] + 1192, 4, 10),
            'debug_regs': (self.sym_table['TEST_OUT'] + 1232, 4, 32),
            'app_log_level': (self.sym_table['g_log_level'], 4, 1)
        }.get(result, None)
        if symb is None:
            self.logger.warning('Unknown result: %s!', result)

        return symb
