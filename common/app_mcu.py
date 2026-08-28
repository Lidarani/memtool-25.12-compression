# Copyright 2022-2025 NXP
"""TODO:summary line."""
import json
import os
import struct
from enum import Enum
from typing import List, Optional, Tuple

from memtool.common.app import AppInterface, ApplicationType
from memtool.common.config_data import ConfigData
from memtool.common.workspace import Workspace


class AppMCU(AppInterface):
    """Model mapping between front-end and application-level entities.

    Entities used by the front-end: magic numbers, names of parameters / results
    Application-level entities: symbol names / constants
    """

    MAX_NB_OF_FLEXSPI_TRANSACTIONS = 6
    TRANSACTION_SIZE = 12  # bytes

    def __init__(self, app_type, app_path, app_timestamp, app_symbol_names, entry_point):  # type: ignore
        """Constructor.Asserts test application executable exists.

        @param app_type: application type
        @param app_path: path of test application
        @param app_timestamp: binary modification date
        @param app_symbol_names: list of symbols that
        @param entry_point: entry point
        """
        self.image = None
        self.dcd = None
        self.start = None
        self.bootapp_start = None
        self.bootapp_end = None
        self.image_end = None
        self.SIZE_PARAMS = self.MAX_NB_OF_FLEXSPI_TRANSACTIONS * self.TRANSACTION_SIZE + 1  # end of transactions marker
        super(AppMCU, self).__init__(app_type, app_path, app_timestamp, app_symbol_names, entry_point)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for app_arg in args[0]:
            if isinstance(app_arg, Enum):
                return app_arg == ApplicationType.MCU
        return False

    def init_sym_table(self, sym_file_path):  # type: ignore
        """Initiate symbol dictionary."""
        self.sym_table = {}
        with open(sym_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if any(s in line for s in self.symbols):
                    cols = line.split()
                    self.sym_table[cols[-1]] = int(cols[1], 16)
                if any(s in line for s in ['ResetISR']):
                    cols = line.split()
                    self.start = int('0x' + cols[1], 16)
                if any(s in line for s in ['Image$$DCD_START']):
                    cols = line.split()
                    self.dcd = '0x' + cols[1]
                if any(s in line for s in ['_image_end']):
                    cols = line.split()
                    self.image_end = '0x' + cols[1]
                if any(s in line for s in ['_image_start']):
                    cols = line.split()
                    self.image = '0x' + cols[1]
                if any(s in line for s in ['_end_noinit']):
                    cols = line.split()
                    self.bootapp_start = '0x' + cols[1]
                if any(s in line for s in ['Image$$BOOTAPP_E']):
                    cols = line.split()
                    self.bootapp_end = '0x' + cols[1]

    def get_command_type_opcode(self, command: str):  # type: ignore
        """Flexspi command opcode."""
        cmd = {'Read': 2, 'Write': 3, 'Config': 1, 'Command': 0}
        return cmd[command]

    def parse_custom_user_file(self, config_data: ConfigData):  # type: ignore
        """TODO:summary line."""
        """Parse user custom file and transform it in a list of bytes that will be sent to target as parameters for
        flexspi_transaction_blocking with multiple transactions"""
        workspace_dir = Workspace.get_instance().get_location()
        file = workspace_dir + os.path.sep + config_data.params["app"]["custom_file_name"]

        if not os.path.isfile(file):
            self.logger.error('File %s does not exist!!!', file)
            return

        with open(file, 'r', encoding='utf-8') as cust_file:
            try:
                json_dict = json.loads(cust_file.read())
            except Exception as e:
                self.logger.error('Exception while parsing the user custom json file: %s', str(e))

        if len(json_dict.keys()) > self.MAX_NB_OF_FLEXSPI_TRANSACTIONS:
            self.logger.error('Test supports a maximum number of %d flexspi transactions'
                              % self.MAX_NB_OF_FLEXSPI_TRANSACTIONS)

        pList = []
        for param in json_dict.keys():
            m1 = (json_dict[param]['flexspiPort'] << 24)\
                 | (self.get_command_type_opcode(json_dict[param]['commandType']) << 16)\
                 | (json_dict[param]['lutSeqTransactionNumber'] << 8) | json_dict[param]['lutSeqIndex']
            p = struct.pack("<IIII", m1, int(json_dict[param]['deviceAddress'], 16), int(json_dict[param]['data'], 16),
                (json_dict[param]['transferSize'] << 24))
            for d in list(p):
                pList.append(d)

        pList.append(0xFE)  # end of transactions marker
        for i in range(len(pList) - 1, self.SIZE_PARAMS - 1):
            pList.append(0)

        config_data.params['app']['test_params']['params'] = pList

    def update_config_data(self, config_data: ConfigData):  # type: ignore
        """Update config and target params in config data."""
        if "CustomTest" in config_data.params["app"]["name"]:
            self.parse_custom_user_file(config_data)

        config_data.params['config']['start_address'] = self.start
        if ('container' in config_data.params['connect']) and ('AHAB' in config_data.params['connect']['container']):
            config_data.params['config']['Image$$DCD_START'] = self.image_end
            config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'] = "0x%8x" % (4 + int(self.image_end, 16))
        else:
            config_data.params['config']['Image$$DCD_START'] = self.dcd
            config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'] = self.bootapp_start

        config_data.params['config']['_image_start'] = self.image
        config_data.target_params['workspace_address'] = config_data.params["config"]["_image_start"]
        config_data.target_params['dcd_addr'] = config_data.params["config"]["Image$$DCD_START"]
        config_data.target_params['start_addr'] = config_data.params['config']['start_address']
        config_data.params['config']['Image$$BOOTAPP_END$$RO$$Base'] = self.bootapp_end

    def get_param_symbol(self, param: str) -> Optional[Tuple[int, int, int]]:
        """Map python-level param dictionary keys to application-level parameter block accessor.

        @param param: (python-level) parameter name (key)
        @return: a tuple (address, width, count) or None if param name was not found
        """
        symb = {'test': (self.sym_table['TEST_IN'] + 0x0, 4, 1),
                'cmd_type': (self.sym_table['TEST_IN'] + 0x4, 4, 1),
                'start_addr': (self.sym_table['TEST_IN'] + 0x8, 8, 1),
                'size': (self.sym_table['TEST_IN'] + 0x10, 8, 1),
                'flags': (self.sym_table['TEST_IN'] + 0x18, 4, 1),
                'data': (self.sym_table['TEST_IN'] + 0x1C, 4, 1),
                'pattern': (self.sym_table['TEST_IN'] + 0x20, 1, 16),  # 6 transactions of 12 bytes + 1 end byte
                'params': (self.sym_table['TEST_IN'] + 0x60, 1, self.SIZE_PARAMS),
                # 6 transactions of 12 bytes + 1 end byte
                }.get(param, None)
        if symb is None:
            self.logger.warning('Unknown parameter: %s!', param)
        return symb

    def get_result_symbol(self, result: str) -> Optional[Tuple[int, int, int]]:
        """Map python-level result dictionary keys to application-level output block symbol names.

        @param result: (python-level) result name (key)
        @return: symbol as tuple of (address, width, count)
        """
        symb = {'app_state': (self.sym_table['TEST_OUT'] + 0, 4, 1),
                'num_records': (self.sym_table['TEST_OUT'] + 4, 4, 1),
                'debug': (self.sym_table['TEST_OUT'] + 1160, 4, 8),
                'err_capt_regs': (self.sym_table['TEST_OUT'] + 1192, 4, 10),
                'debug_regs': (self.sym_table['TEST_OUT'] + 1232, 4, 32), }.get(result, None)
        if symb is None:
            self.logger.warning('Unknown result: %s!', result)

        return symb

    @staticmethod
    def get_app_symbol_names() -> List[str]:
        """Get the names of the app symbols for test params.

        @return: list of symbol names
        """
        app_symbol_names = ['start64', 'g_sys_params', 'TEST_IN', 'TEST_OUT', "g_log_level"]
        return app_symbol_names
