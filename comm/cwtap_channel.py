# Copyright 2021-2025 NXP
"""Communication with a target through a CCS connection."""
import ast
import ctypes
import logging
import os
import platform
import subprocess
import time
from typing import List, Optional, Tuple, Union

from memtool.common.channel import Channel
from memtool.common.config_data import ConfigData
from memtool.memtests.snps_phy import BufferedReader
from memtool.utils.constants import Const


class CWTapChannel(Channel):
    """Channel for communicating with processor memory and registers through CCS."""
    logger = logging.getLogger(__name__)

    # Supported processors and the necessary info in order to connect to that target:
    # list of devices per target, core chain position, memory space
    PROCESSORS = {'LX2160A': [ctypes.pointer((ctypes.c_int * 2)(302, 232)),
                              21,  # LX2 chain position 21: Cortex - A72
                              4607],
                  'LX2162A': [ctypes.pointer((ctypes.c_int * 2)(302, 232)),
                              21,  # LX2 chain position 21: Cortex - A72
                              4607],
                  'LA1224': [ctypes.pointer((ctypes.c_int * 2)(317, 272)), 2, 0]
                  }

    # Host IP
    __HOST_IP = b"127.0.0.1"

    # CCS default port
    __CCS_PORT = 41475

    # CCS error codes
    __CCS_ERR_OK = 0
    __CCS_ERR_PROCESS_NOT_STARTED = 100
    __CCS_ERR_LIBRARY_NOT_LOADED = 101

    # CCS core status
    __CCS_MODE_UNDEFINED = 4
    __CCS_MODE_DEBUG = 0

    # number of bytes to be read/written in one operation
    CHUNK_SIZE = 4096

    def __init__(self, connect_params: dict):
        """Constructor.

        @param connect_params: connection parameters
        """
        super(CWTapChannel, self).__init__()
        self.channel_is_operational = False
        self.ccs_process = None
        self.ccs = None
        self.ccs_server_handle = -1
        self.connect_params = connect_params
        self.processor = self.connect_params[Const.PARAM_S_TC_SOC_NAME]
        self.log_level = self.connect_params[Const.PARAM_LOG_LEVEL]

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Override matches from Channel."""
        for arg in args:
            if isinstance(arg[0], dict):
                return arg[0].get('not_sim', True) and arg[0][Const.PARAM_S_TC_SOC_NAME] in cls.PROCESSORS

        return False

    def write_data(self, address: int, width: int, data: bytes) -> bool:
        """Override write_data from Channel.

        @param address: application-level address
        @param width: data width (number of bytes to write; access size will be 4)
        @param data: data (hex-encoded byte stream)
        @return: True if write operation was successful, False otherwise
        """
        server_h = ctypes.c_uint(self.ccs_server_handle)
        chain_pos = ctypes.c_uint(self.PROCESSORS[self.processor][1])  # type: ignore

        # if core is running stop it
        status = ctypes.c_uint(self.__CCS_MODE_UNDEFINED)
        result = self.ccs.get_core_status(server_h, chain_pos, ctypes.byref(status))  # type: ignore
        core_stopped = False
        if (self.__CCS_ERR_OK != result) or (self.__CCS_MODE_DEBUG != status.value):
            self.logger.info('CCS: stop core for write')
            result = self.ccs.stop_core(server_h, chain_pos)  # type: ignore
            if self.__CCS_ERR_OK != result:
                self.logger.error('CCS: core could not be stopped for write')
                return False

            result = self.ccs.get_core_status(server_h, chain_pos, ctypes.byref(status))  # type: ignore
            if (self.__CCS_ERR_OK != result) or (self.__CCS_MODE_DEBUG != status.value):
                self.logger.error('CCS: core could not be stopped for write')
                return False

            core_stopped = True

        mem_space = ctypes.c_uint(self.PROCESSORS[self.processor][2])  # type: ignore
        mem_address_hi = ctypes.c_ulong(address >> 32)
        mem_address_lo = ctypes.c_ulong(address & 0xffffffff)
        values = ctypes.c_char_p(data)
        result = self.ccs.write_memory(server_h,  # type: ignore
                                       chain_pos,
                                       mem_space,
                                       width if (width < 4) else 4,
                                       mem_address_hi,
                                       mem_address_lo,
                                       width,
                                       values)
        if self.__CCS_ERR_OK != result:
            self.logger.error('CCS: failed to write data')
            return False

        # if core was stopped for read, start it
        if core_stopped:
            self.logger.info('CCS: resume core after write')
            result = self.ccs.run_core(server_h, chain_pos)  # type: ignore
            if self.__CCS_ERR_OK != result:
                self.logger.error('CCS: core could not be resumed after write')
                return False

        return True

    def read_data(self, address: int, width: int, count: int) -> Optional[str]:
        """Override read_data from Channel.

        @param address: application-level address
        @param width: data width (access size)
        @param count: number of words of size 'width' to read
        @return: read data as hex string or NOne if operation failed
        """
        server_h = ctypes.c_uint(self.ccs_server_handle)
        chain_pos = ctypes.c_uint(self.PROCESSORS[self.processor][1])  # type: ignore

        # if core is running stop it
        status = ctypes.c_uint(self.__CCS_MODE_UNDEFINED)
        result = self.ccs.get_core_status(server_h, chain_pos, ctypes.byref(status))  # type: ignore
        core_stopped = False
        if (self.__CCS_ERR_OK != result) or (self.__CCS_MODE_DEBUG != status.value):
            self.logger.info('CCS: stop core for read')
            result = self.ccs.stop_core(server_h, chain_pos)  # type: ignore
            if self.__CCS_ERR_OK != result:
                self.logger.info('CCS: core could not be stopped for read')
                return None
            result = self.ccs.get_core_status(server_h, chain_pos, ctypes.byref(status))  # type: ignore
            if (self.__CCS_ERR_OK != result) or (self.__CCS_MODE_DEBUG != status.value):
                self.logger.info('CCS: core could not be stopped for read')
                return None
            core_stopped = True

        mem_space = ctypes.c_uint(self.PROCESSORS[self.processor][2])  # type: ignore
        bytes_to_read = count * width
        read_values = b""
        while bytes_to_read > 0:
            mem_address_hi = ctypes.c_ulong(address >> 32)
            mem_address_lo = ctypes.c_ulong(address & 0xffffffff)
            crt_bytes_to_read = self.CHUNK_SIZE if (bytes_to_read > self.CHUNK_SIZE) else bytes_to_read

            crt_values = (ctypes.c_char * crt_bytes_to_read)()
            result = self.ccs.read_memory(server_h,  # type: ignore
                                          chain_pos,
                                          mem_space,
                                          width,
                                          mem_address_hi,
                                          mem_address_lo,
                                          crt_bytes_to_read,
                                          ctypes.pointer(crt_values))
            if self.__CCS_ERR_OK != result:
                self.logger.info('CCS: failed to read data')
                return None
            read_values = b"".join([read_values, crt_values.raw])
            bytes_to_read -= crt_bytes_to_read
            address += crt_bytes_to_read

        # if core was stopped for read, start it
        if core_stopped:
            self.logger.info('CCS: resume core after read')
            result = self.ccs.run_core(server_h, chain_pos)  # type: ignore
            if self.__CCS_ERR_OK != result:
                self.logger.info('CCS: core could not be resumed after read')
                return None

        return bytearray(read_values).hex()

    def write_symbol(self, symbol: Optional[Tuple[int, int, int]], value: int) -> bool:
        """Override write_symbol from Channel.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @param value: value (hex-encoded byte stream)
        @return: True if write operation was successful, False otherwise
        """
        address, width, count = symbol  # type: ignore
        int_val = value
        if isinstance(value, bool):
            if value:
                int_val = 1
            else:
                int_val = 0
        elif isinstance(value, str):
            if value.startswith('[') and value.endswith(']'):
                int_val = ast.literal_eval(value)
            else:
                try:
                    base = 16 if value.lower().startswith('0x') else 10
                    int_val = int(value, base)
                except ValueError:
                    self.logger.error(f'{value} could not be converted to int')
                    return False

        if isinstance(int_val, list):
            int_vals = b''
            for v in int_val:
                int_vals += v.to_bytes(width, byteorder='little')
            return self.write_data(address, width * count, int_vals)

        return self.write_data(address, width * count, int_val.to_bytes(width * count, byteorder='little'))

    def read_symbol(self, symbol: Optional[Tuple[int, int, int]]) -> Union[int, List[int]]:  # type: ignore
        """Override read_symbol from Channel.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @return: symbol value or None if operation failed
        """
        if symbol is None:
            self.logger.error('Read symbol can not be performed without specifying symbol info')
            return None  # type: ignore

        address, width, count = symbol
        if count == 1:
            data = self.read_data(address, width, count)
            if data is None:
                self.logger.error('Read symbol operation failed')
                return None  # type: ignore

            return BufferedReader.swap32(int(data, 16))

        # we have a string of concatenated hex values (2 chars per byte)
        # and we'll create an array of hex values
        values = self.read_data(address, width, count)
        if values is None:
            self.logger.error('Read symbol operation failed')
            return None  # type: ignore
        read_values = []
        idx = 0
        while idx < count:
            start_idx = idx * width * 2
            end_idx = start_idx + width * 2
            value = values[start_idx: end_idx]
            swapped_value = BufferedReader.swap32(int(value, 16))
            read_values.append(swapped_value)
            idx += 1
        return read_values

    def read_register(self, register_index: int) -> bytes:
        """Read the value from a register.

        @param register_index: the target register
        @return: value as array of bytes
        """
        chain_pos = ctypes.c_uint(self.PROCESSORS[self.processor][1])  # type: ignore
        value = (ctypes.c_char * 4)()
        self.ccs.read_registers(self.ccs_server_handle,  # type: ignore
            chain_pos, register_index, 1, 4, ctypes.pointer(value))
        return value  # type: ignore

    def write_register(self, register_index: int, data: bytes):  # type: ignore
        """Write a value to a register.

        @param register_index: the target register
        @param data: array of bytes to be written
        """
        chain_pos = ctypes.c_uint(self.PROCESSORS[self.processor][1])  # type: ignore
        value = ctypes.c_char_p(data)
        self.ccs.write_registers(self.ccs_server_handle, chain_pos, register_index, 1, 4, value)  # type: ignore

    def _start_ccs(self, config_data: ConfigData):  # type: ignore
        """Start CCS process on recognised os.

        @param config_data: processor config data
        """
        operating_system = platform.system()
        if operating_system == "Windows":
            if self.__win_start_ccs(config_data) != self.__CCS_ERR_OK:
                # TODO: check what err can occur and treat them
                return
        elif operating_system == "Linux":
            # TODO
            pass

    def __win_start_ccs(self, config_data: ConfigData) -> int:
        """Start CCS process on Windows.

        NOTE: for debug layout of DDRTool ccs must be found in sdk_mem_data\\memtool\\
        @return: success or error
        """
        self.logger.info(' CCS open')

        root_folder = os.path.join(config_data.data_dir, "..", "..")  # path to mem_validation\ddrc
        ccs_folder = os.path.join(root_folder, "ccs", "win")
        ccs_exe = os.path.join(ccs_folder, "bin", "ccs.exe")

        # start ccs
        if not os.path.exists(ccs_exe):
            self.logger.error('CCS: %s was not found', ccs_exe)
            return self.__CCS_ERR_PROCESS_NOT_STARTED

        self.ccs_process = subprocess.Popen(ccs_exe)  # type: ignore

        # load ccs dll
        ccs_dll = os.path.join(ccs_folder, "CCS_DLL.dll")
        self.ccs = ctypes.cdll.LoadLibrary(ccs_dll)  # type: ignore
        time.sleep(1)

        # TODO: see if the return is needed
        #  always returns the same val
        #  is only called in _start_ccs and _start_ccs doesn't check the return value
        return self.__CCS_ERR_OK

    def open(self, config_data: ConfigData) -> int:
        """Connect to target.

        @return: error code or success
        """
        self.logger.info('Connect to target through CCS')

        if self.channel_is_operational:  # ccs connection already configured
            return self.__CCS_ERR_OK
        self._start_ccs(config_data)

        if self.ccs_process is None:
            return self.__CCS_ERR_PROCESS_NOT_STARTED

        if self.ccs is None:
            return self.__CCS_ERR_LIBRARY_NOT_LOADED

        # open ccs connection
        server_h = ctypes.c_uint(self.ccs_server_handle)
        result = self.ccs.open_connection(ctypes.c_char_p(self.__HOST_IP),
                                          ctypes.c_uint(self.__CCS_PORT), ctypes.byref(server_h))
        time.sleep(1)
        if self.__CCS_ERR_OK != result:
            return result

        # ensure previous configuration was deleted
        self.ccs_server_handle = server_h.value
        self.ccs.delete_command_converter(server_h)

        # configure connection to target
        ccs_config = ctypes.c_char_p(bytes("cwtap:" + self.connect_params['CWTAP_ADDRESS'], 'utf-8'))
        result = self.ccs.connect_to_target(server_h, ccs_config, ctypes.c_long(2), self.PROCESSORS[self.processor][0])
        time.sleep(1)
        if self.__CCS_ERR_OK != result:
            return result

        # reset target
        if self.connect_params['reset']:
            result = self.ccs.reset_to_debug(server_h)
            time.sleep(1)
            if self.__CCS_ERR_OK != result:
                return result

        # check core is in debug
        chain_pos = ctypes.c_uint(self.PROCESSORS[self.processor][1])
        status = ctypes.c_uint(self.__CCS_MODE_UNDEFINED)
        result = self.ccs.get_core_status(server_h, chain_pos, ctypes.byref(status))
        if (self.__CCS_ERR_OK != result) or (self.__CCS_MODE_DEBUG != status.value):
            return result

        self.channel_is_operational = True
        return self.__CCS_ERR_OK

    def run(self):  # type: ignore
        """Run CSS core.

        @return: CSS status
        """
        server_h = ctypes.c_uint(self.ccs_server_handle)
        chain_pos = ctypes.c_uint(self.PROCESSORS[self.processor][1])
        result = self.ccs.run_core(server_h, chain_pos)

        return result
        # TODO: see if a return value is needed as it's not checked when method is called
        #  method only called in CCSProcessor.execute

    def init_channel(self, config_data: ConfigData = None):  # type: ignore
        """Initialize channel.

        @param config_data: processor config data
        """
        if config_data is not None:
            # it performs 'connect to target', so target shouldn't be reset!
            reset = self.connect_params['reset']
            self.connect_params['reset'] = False
            self.open(config_data)
            self.connect_params['reset'] = reset

    def reset(self) -> None:
        """Ask for a self-reset."""
        pass

    def is_alive(self, wait_for_response: bool = True) -> bool:
        """Override is_alive from Channel.

        @param wait_for_response: wait for channel to be responsive
        @return: True if channel is alive and backend can communicate with channel, False otherwise.
        """
        return self.channel_is_operational

    def close(self):  # type: ignore
        """Override close from Channel."""
        self.logger.info('CCS close')

        self.channel_is_operational = False

        # close ccs connection
        self.ccs.close_connection(self.ccs_server_handle)
        self.ccs = None

        # close ccs
        self.ccs_process.terminate()
        self.ccs_process = None
