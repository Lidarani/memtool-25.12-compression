# Copyright 2019-2025 NXP
"""TODO:summary line."""
import logging
import os
from enum import Enum
from typing import List, Optional, Tuple

from memtool.common.config_data import ConfigData
from memtool.common.factories import AppInterfaceFactory
from memtool.utils.constants import Const
from memtool.utils.helper import get_syms_file_path


class ApplicationType(Enum):
    """Memtool application types."""
    MPU = "mpu"
    MCU = "mcu"
    LX = "lx"
    LA = "la"
    UNKNOWN = "unknown"


class AppInterface(AppInterfaceFactory):
    """Model mapping between front-end and application-level entities.

    Entities used by the front-end: magic numbers, names of parameters / results
    Application-level entities: symbol names / constants
    """

    APP_STATES = {
        'INIT': 0x00000000,
        'WAIT_FOR_INPUT': 0x5588DCFE,
        'INPUT_RECEIVED': 0x77665544,
        'CONFIG_RECEIVED': 0x55AA55AA,
        'RUNNING': 0x1234FEDC,
        'FINISHED': 0x11223344,
        'INTERRUPTED': 0x0D0E0A0D,
        'UNKNOWN': 0xFFFFFFFF
    }

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input, so it should be instantiated.

        @param args: list of parameters used to determine if this class should be instantiated
        @return: True if this class can handle the input
        """
        for app_arg in args[0]:
            if isinstance(app_arg, Enum):
                return app_arg in [ApplicationType.MPU, ApplicationType.LX]
        return False

    def __init__(self, app_type, app_path, app_timestamp, app_symbol_names, entry_point):  # type: ignore
        """Constructor.Asserts test application executable exists.

        @param app_type: application type
        @param app_path: path of test application
        @param app_timestamp: binary modification date
        @param app_symbol_names: list of symbols that
        @param entry_point: entry point
        """
        self.logger = logging.getLogger(__name__)

        self.sym_table = None
        self.symbols = app_symbol_names
        if entry_point is not None:
            self.symbols += [entry_point]
        self.start = entry_point
        sym_file_path = get_syms_file_path(app_path)
        self.init_sym_table(sym_file_path)

    def init_sym_table(self, sym_file_path):  # type: ignore
        """Initiate symbol dictionary.

        @param sym_file_path: symbolics file
        """
        self.sym_table = {}
        if not os.path.isfile(sym_file_path):
            return

        is_using_arm_ds = False
        with open(sym_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if 'ARM Linker' in line:
                    is_using_arm_ds = True
                if any(s in line for s in self.symbols):
                    cols = line.split()
                    if is_using_arm_ds:
                        self.sym_table[cols[-1]] = int(cols[0], 16)
                    else:
                        self.sym_table[cols[-1]] = int('0x' + cols[1], 16)

    def update_config_data(self, config_data: ConfigData):  # type: ignore
        """Update target params in config data.

        @param config_data: configuration data
        """
        config_data.target_params['start_addr'] = self.get_symbol(self.start)[0]  # type: ignore
        config_data.target_params['g_diags_params'] = self.get_symbol("g_diags_params")[0]  # type: ignore
        config_data.target_params['g_sys_params'] = self.get_symbol("g_sys_params")[0]  # type: ignore
        if Const.PARAM_SERDES_SKIP_DDR_PHY in config_data.params[Const.PARAM_S_BASIC]:
            # serdes app
            config_data.target_params['workspace_address'] = '0x%x' % config_data.target_params['start_addr']
            config_data.target_params['dcd_addr'] = '0x%x' % (self.get_symbol("g_log_level")[0] + 16)  # type: ignore
            self.sym_table['PEB_offset'] = config_data.connect_params['PEB_offset']

    def get_symbol(self, symbol: str) -> Optional[Tuple[int, int, int]]:
        """Map python-level param dictionary keys to application-level accessor.

        @param symbol: (python-level) symbol name (key)
        @return: a tuple (address, width, count) or None if symbol was not found
        """
        # check if any symbols are available
        if not isinstance(self.symbols, list):
            self.logger.warning('No app symbols registered!')
            return None

        # load symbols in dictionary
        symb = {}
        for s in self.symbols:
            symb[s] = (self.sym_table[s], 4, 1)

        # search key
        result = symb.get(symbol, None)
        if result is None:
            self.logger.warning('Unknown symbol: %s!', symbol)
        return result

    def get_param_symbol(self, param: str) -> Optional[Tuple[int, int, int]]:
        """Map python-level param dictionary keys to application-level parameter block accessor.

        @param param: (python-level) parameter name (key)
        @return: a tuple (address, width, count) or None if param name was not found
        """
        symb = {
            'test': (self.sym_table['TEST_IN'] + 0x0, 4, 1),
            'cache': (self.sym_table['TEST_IN'] + 0x4, 4, 1),
            'start_addr': (self.sym_table['TEST_IN'] + 0x8, 8, 1),
            'size': (self.sym_table['TEST_IN'] + 0x10, 8, 1),
            'flags': (self.sym_table['TEST_IN'] + 0x30, 4, 1),
            'forever': (self.sym_table['TEST_IN'] + 0x34, 4, 1),
            'cores': (self.sym_table['TEST_IN'] + 0x38, 4, 1),
            'params': (self.sym_table['TEST_IN'] + 0x38, 4, 16),
            'perf_mon_enable': (self.sym_table['TEST_IN'] + 0x78, 4, 1),
            'perf_mon_events': (self.sym_table['TEST_IN'] + 0x7c, 4, 11)
        }.get(param, None)
        if symb is None:
            self.logger.warning('Unknown parameter: %s!', param)
        return symb

    def get_result_symbol(self, result: str) -> Optional[Tuple[int, int, int]]:
        """Map python-level result dictionary keys to application-level output block symbol names.

        @param result: (python-level) result name (key)
        @return: symbol as tuple of (address, width, count) or None if result param name was not found
        """
        result_base_symb = {
            'start': self.start,
            'phy_status': 'g_sys_params',
            'num_logged_items': 'g_sys_params',
            'app_state': 'TEST_OUT',
            'num_records': 'TEST_OUT',
            'debug': 'TEST_OUT',
            'err_capt_regs': 'TEST_OUT',
            'debug_regs': 'TEST_OUT',
            'app_log_level': 'g_log_level'
        }
        base_symb = result_base_symb.get(result, None)
        if base_symb is None:
            self.logger.warning('Unknown result: %s!', result)
            return None
        if base_symb not in self.sym_table:
            self.logger.warning('Unknown symbol: %s!', base_symb)
            return None

        symb = {
            'start': (self.sym_table[base_symb], 4, 1),
            'phy_status': (self.sym_table[base_symb] + 4, 4, 1),
            'num_logged_items': (self.sym_table[base_symb] + 8, 4, 1),
            'app_state': (self.sym_table[base_symb] + 0, 4, 1),
            'num_records': (self.sym_table[base_symb] + 4, 4, 1),
            'debug': (self.sym_table[base_symb] + 1160, 4, 8),
            'err_capt_regs': (self.sym_table[base_symb] + 1192, 4, 10),
            'debug_regs': (self.sym_table[base_symb] + 1232, 4, 32),
            'app_log_level': (self.sym_table[base_symb], 4, 1)
        }.get(result, None)
        if symb is None:
            self.logger.warning('Unknown result: %s!', result)

        return symb

    def get_test_result_symbol(self, index: int, field: str) -> Optional[Tuple[int, int, int]]:
        """Map python-level test result dictionary keys to application-level test record symbol names.

        @param index: test record index
        @param field: (python-level) test record field name (key)
        @return: field symbol as tuple of (address, width, count)
        """
        field_symbol = {
            'state': (self.sym_table['TEST_OUT'] + 8 + 72 * index + 0, 4, 1),
            'test_id': (self.sym_table['TEST_OUT'] + 8 + 72 * index + 4, 4, 1),
            'data': (self.sym_table['TEST_OUT'] + 8 + 72 * index + 8, 4, 16),
            'jitter_step': (self.sym_table.get('PEB_offset', 0) + 0x400 * index, 4, 256)
        }.get(field, None)
        if field_symbol is None:
            self.logger.warning('Unknown result field: %s!!!', field)
        return field_symbol

    def get_app_state_name(self, app_state_no: int) -> str:
        """Get the application state name from the application state number encoding.

        @param app_state_no: application state number
        @return: application state name
        """
        for name, value in self.APP_STATES.items():
            if app_state_no == value:
                return name

        self.logger.warning('Unknown application state number %d', app_state_no)
        return 'UNKNOWN'

    @staticmethod
    def state_name(state_code: int) -> str:
        """Decode the application state into human-readable string.

        @param state_code: application state code
        @return: application state string
        """
        if state_code == 0x00000000:
            return 'INIT'
        if state_code == 0x5588DCFE:
            return 'WAIT_FOR_INPUT'
        if state_code == 0x77665544:
            return 'INPUT_RECEIVED'
        if state_code == 0x55AA55AA:
            return 'CONFIG_RECEIVED'
        if state_code == 0x1234FEDC:
            return 'RUNNING'
        if state_code == 0x11223344:
            return 'FINISHED'
        if state_code == 0x0D0E0A0D:
            return 'INTERRUPTED'
        return 'UNKNOWN'

    @staticmethod
    def get_app_symbol_names() -> List[str]:
        """Get the names of the app symbols for test params.

        @return: list of symbol names
        """
        app_symbol_names = ['g_sys_params', 'g_diags_params', 'TEST_IN', 'TEST_OUT', "g_log_level"]
        return app_symbol_names


class ApplicationCommand(Enum):
    """Supported application commands."""

    SERIAL_CHANNEL_OPENED = ('CHANNEL_OPENED', None, None, 0.1, 0.1)
    IS_ALIVE_TARGET = ('IS_ALIVE_TARGET', 0x01, '[TARGET IS ALIVE]', 0, 10)
    RESET_TARGET = ('TARGET_RESET', 0x02, None, 1, 0)
    WRITE_TO_TARGET = ('WRITE_TO_TARGET', 0x03, '[WRITE FINISHED]', 0, 0.05)
    READ_FROM_TARGET = ('READ_FROM_TARGET', 0x04, '[READ FINISHED]', 0, 0.05)
    CALIBRATE_TARGET = ('CALIBRATION', 0x05, '[PHY FINISHED]', 1, 900)
    EXECUTE_TEST = ('EXECUTE_TEST', 0x06, '[TEST FINISHED]', 1, 1200)

    def __init__(self, name: str, id: None | int, response: None | str,
                 send_timeout: float, read_timeout: float) -> None:  # type: ignore
        """Constructor.

        @param name: command name
        @param data: command data to be send to target
        @param response: command expected response
        @param send_timeout: send command timeout
        @param read_timeout: read result timeout
        """
        self._name = name
        self._id = id
        self._response = response
        self._send_timeout = send_timeout
        self._read_timeout = read_timeout

    @property
    def name(self) -> str:
        """Command name."""
        return self._name

    @property
    def id(self) -> None | int:
        """Command id."""
        return self._id

    @property
    def response(self) -> None | str:
        """Command response."""
        return self._response

    @property
    def send_timeout(self) -> float:
        """Get send command timeout."""
        return self._send_timeout

    @property
    def read_timeout(self) -> float:
        """Get read result timeout."""
        return self._read_timeout
