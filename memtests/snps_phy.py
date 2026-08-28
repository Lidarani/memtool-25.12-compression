# Copyright 2022-2025 NXP
"""Implementation of SNPS PHY commands.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of NXP nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

This software is provided by NXP "as is" and any
express or implied warranties, including, but not limited to, the implied
warranties of merchantability and fitness for a particular purpose are
disclaimed. In no event shall NXP be liable for any
direct, indirect, incidental, special, exemplary, or consequential damages
(including, but not limited to, procurement of substitute goods or services;
loss of use, data, or profits; or business interruption) however caused and
on any theory of liability, whether in contract, strict liability, or tort
(including negligence or otherwise) arising in any way out of the use of
this software, even if advised of the possibility of such damage.
"""
import logging
import os
import struct
import sys
import time
from typing import Dict, Tuple

from memtool.common.config_data import ConfigData
from memtool.utils.constants import Const
from memtool.utils.helper import aligned_incr, to_int


class PhyException(Exception):
    """Phy-specific exception raised in error cases."""
    pass


class SnpsPhyParam:
    """Phy parameter."""

    def __init__(self, name: str, value: int = 0, size: int = 4):
        """Constructor.

        @param name: parameter's name
        @param size: size of the parameter
        """
        # Name of the parameter
        self.name = name

        # Size of the parameter
        self.size = size

        # Value of the parameter
        self.value = value


class BufferedReader:
    """Utility class to speed-up target reads by using larger chunks."""

    CHUNK_SIZE = 128

    @staticmethod
    def swap32(x: int) -> int:
        """Swap the bytes of a 32-bit integer number.

        @param x: 32-bit big endian integer number to swap
        @return: little endian value of the provided integer
        """
        return struct.unpack("<I", struct.pack(">I", x))[0]

    def __init__(self, read_fct, start_addr, max_addr, read_size=CHUNK_SIZE):  # type: ignore
        """TODO:summary line."""
        self.read = read_fct
        self.buffer = ""
        self.addr_start = start_addr
        self.addr_max = max_addr
        self.addr_crt = start_addr
        self.read_size = read_size

    def __read_more_data(self) -> None:
        """Read the next element."""
        if self.addr_crt >= self.addr_max:
            # Already at the limit, can't read more
            raise PhyException(f"Attempted to read beyond memory limit at address 0x{self.addr_crt:08x}")

        if self.addr_crt + self.read_size >= self.addr_max:
            read_size = self.addr_max - self.addr_crt
        else:
            read_size = self.read_size

        if read_size <= 0:
            raise PhyException(f"No more data to read at address 0x{self.addr_crt:08x}")

        # Read data with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            data = self.read(self.addr_crt, 1, read_size)
            if data:
                self.buffer += data
                self.addr_crt += read_size
                return
            else:
                logging.warning(f"Failed to read data at 0x{self.addr_crt:08x}, attempt {attempt + 1}/{max_retries}")
                time.sleep(0.1)  # Small delay before retry

        raise PhyException(f"Failed to read data at address 0x{self.addr_crt:08x} after {max_retries} attempts")

    def read_integer(self, address: int, size: int = 4, swap: bool = True) -> int:
        """Read an int value from the buffer.

        @param address: address to read from
        @param size: size in bytes of the value to be read
        @param swap: should the value be swapped
        @return: the int value
        """
        # Ensure we have enough data in the buffer
        required_offset = 2 * (address - self.addr_start + size)
        while len(self.buffer) < required_offset:
            if self.addr_crt >= self.addr_max:
                raise PhyException(f"Reached end of readable memory at address 0x{self.addr_crt:08x}")
            self.__read_more_data()

        # Extract the hex string
        start_idx = 2 * (address - self.addr_start)
        end_idx = 2 * (address - self.addr_start + size)
        hex_str = self.buffer[start_idx:end_idx]

        if not hex_str:
            raise PhyException(f"No data available at address 0x{address:08x}")

        try:
            val = int(hex_str, 16)
        except ValueError as e:
            raise PhyException(f"Invalid hex data '{hex_str}' at address 0x{address:08x}: {e}")

        return BufferedReader.swap32(val) if swap else val


class SnpsPhy:
    """Phy implementation."""

    logger = logging.getLogger(__name__)

    # Type of debugging logs (as used by the algorithm)
    LOG_INIT_MAILBOX = 1
    LOG_INIT_CONFIG = 2
    LOG_IMEM_1D = 4
    LOG_DMEM_1D = 8
    LOG_IMEM_2D = 16
    LOG_DMEM_2D = 32
    LOG_EXEC_FIRMWARE = 64
    LOG_READ_MSG_BLOCK = 128
    LOG_LOAD_PIE = 256
    LOG_MESSAGES = 512
    LOG_TRAINING_MESSAGES = 512  # Just an "alias" for LOG_MESSAGES
    LOG_CODE_GEN = LOG_INIT_CONFIG + LOG_DMEM_1D + LOG_DMEM_2D + LOG_LOAD_PIE

    # Type of debugging logs (as used by the command)
    _LOG_TYPES = {
        'init_mailbox': LOG_INIT_MAILBOX,
        'init_config': LOG_INIT_CONFIG,
        'imem_1d': LOG_IMEM_1D,
        'dmem_1d': LOG_DMEM_1D,
        'imem_2d': LOG_IMEM_2D,
        'dmem_2d': LOG_DMEM_2D,
        'exec_firmware': LOG_EXEC_FIRMWARE,
        'read_msg_block': LOG_READ_MSG_BLOCK,
        'load_pie': LOG_LOAD_PIE,
        'training_messages': LOG_TRAINING_MESSAGES,
        'messages': LOG_MESSAGES,
        'code_gen': LOG_CODE_GEN
        # This kind of log is a merge of multiple log type necessary for code generation: init_config, dmem_1d, dmem_2d
    }

    # Types of reg map compression implementations
    REG_MAP_COMPRESSION_LX = 1
    REG_MAP_COMPRESSION_IMX8 = 2

    # Phy algorithm possible results
    PHY_ERR_OK = 0
    PHY_ERR_UNSUPPORTED = 1
    PHY_ERR_TIMEOUT = 2
    PHY_ERR_TRAINING_1D_FAILED = 3
    PHY_ERR_TRAINING_2D_FAILED = 4
    PHY_ERR_INVALID_DIAG_TEST = 5
    PHY_ERR_DIAG_FAILED = 6
    PHY_ERR_HARDWARE_FAILED = 7
    DDR_ERR_INITIALIZATION_FAILED = 10

    # Major messages reported by the PHY.
    _MAJOR_MESSAGES = {
        0x00: 'End of initialization\n',
        0x01: 'End of fine write leveling\n',
        0x02: 'End of read enable training\n',
        0x03: 'End of read delay center optimization\n',
        0x04: 'End of write delay center optimization\n',
        0x05: 'End of 2D read delay/voltage center optimization\n',
        0x06: 'End of 2D write delay/voltage center optimization\n',
        0x07: 'Firmware has run successfully (firmware completed)\n',
        0x08: 'Start of streaming message\n',
        0x09: 'End of max read latency training\n',
        0x0A: 'End of read dq deskew training\n',
        0x0B: 'End of LCDL offset calibration\n',
        0x0C: 'End of LRDIMM Specific training (DWL, MREP, MRD and MWD)\n',
        0x0D: 'End of CA training\n',
        0xFD: 'End of MPR read delay center optimization\n',
        0xFE: 'End of Write leveling coarse delay\n',
        0xFF: 'Firmware has failed (firmware completed)\n'
    }

    # Algorithm entry point and parameters
    _ALG_ENTRY_POINT = 0x300

    # Indexes of diagnostic result 'target' array
    TARGET_CS_IDX = 0
    TARGET_BYTE_IDX = 1
    TARGET_BIT_IDX = 2
    TARGET_VREF_IDX = 3
    TARGET_DELAY_IDX = 5

    def __init_phy__(self, config_data: ConfigData):  # type: ignore
        """Constructor - Initialize static parameters.

        Dynamic parameters will be initialized later in configure() method
        """
        # cw_phy_params (dict) : a dictionary containing the static DDR PHY parameters
        #                              - soc (string): SoC name
        #                              - dram_type (string): type of DDR to be configured
        #                              - dimm_type (string): type of DIMM to be configured
        #                              - diag_out_addr_hi (int): hi address of diag results
        #                              - diag_out_addr_lo (int): low address of diag results
        #                              - dcd_file (string): path to file containing dcd parameter block
        #                              - dcd_addr (int): address where dcd block is loaded
        #                              - log_file (string): path to file used for logging all
        #                                                   DDR PHY accesses
        #                              - result_file (string): path to file used for diagnostics result
        #                              - log_types (array of strings): what types of logging are
        #                                                   activated for DDR PHY accesses
        #                              - skip_download (bool): whether algorithm and IMEM firmware
        #                                                   download will be skipped
        #                              - op_type (int): whether diagnostics needs to be executed
        #                              - phy_param_file (string): path to file containing phy parameters
        #                              - data_dir (string): the current working directory

        # Type of DDR; default to DDR4
        self.dram_type = config_data.dram_type
        self.memory_type = config_data.mem_type

        # DCD block
        self.firmware_version = config_data.snps_phy_info.name

        # File where to log all DDR PHY accesses
        self.log_file = config_data.log_file
        self.result_file = config_data.params[Const.PARAM_S_TC].get(Const.PARAM_S_TC_DIAGS_RESULT_FILE, None)

        # Whether download of algorithm and IMEM firmware can be skipped
        self.skip_download = config_data.skip_download

        self.log_addr = (int(config_data.sys_params["log_addr_hi"], 16) << 32) \
            | int(config_data.sys_params["log_addr_lo"], 16)

        self.data_dir = config_data.data_dir

        self.phy_version_2 = ConfigData.is_phy_v2(config_data.snps_phy_info)

        self.quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                           Const.PHY_QUICK_BOOT)

        self.dbi_enabled = config_data.dbi_enabled

    @staticmethod
    def cmp_log_types(log_types_list: list) -> int:
        """Determine the type of messages that were logged.

        @param log_types_list: names of log types
        @return: map of log types
        @raise PhyException: conflicting log types
        """
        if "code_gen" in log_types_list:
            log_types = SnpsPhy._LOG_TYPES['code_gen']
        else:  # training_messages
            log_types = SnpsPhy._LOG_TYPES['training_messages']

        # Logging requested. Build the 'map' of logging types to be sent to the algorithm
        for log in log_types_list:
            log_types |= SnpsPhy._LOG_TYPES[log]

        # Not able to log items having different data types behind them
        # (LOG_MESSAGES is one of the special cases)
        if (log_types & SnpsPhy.LOG_MESSAGES) and (log_types & ~SnpsPhy.LOG_MESSAGES):
            raise PhyException("DDR PHY: cannot log messages at the same time with other types of logs")

        return log_types

    @staticmethod
    def get_data_file(mem_type: str = "ddr4", op_type: str = "pmu_train",
                      data_type: str = "imem", data_2d: bool = False,
                      quick_boot: bool = False) -> str:
        """Get filename for the instruction/data firmware binary or for the training messages file.

        @param mem_type: code for memory type
        @param op_type: whether training or diagnostics file is requested
        @param data_type: imem/dmem/messages/registers file to obtain
        @param data_2d: flag indicating whether files associated with 2D training are needed
        @param quick_boot: quick boot data file is needed
        @return: string representing the filename
        """
        # Get the appropriate 1D/2D firmware/messages (makes sense only for training FW)
        if data_2d:
            mem_type += '_'
            mem_type += "2d"

        op_type = ('_' + 'quickboot') if quick_boot else ('_' + op_type)

        # Strings or binary firmware?
        extension = 'strings' if data_type == 'messages' else ('txt' if data_type == 'registers' else 'bin')
        data_type = '' if data_type == 'messages' or quick_boot else ('_' + data_type)

        # Build the actual filename
        return mem_type + op_type + data_type + "." + extension

    @staticmethod
    def get_error_message(err_id: int) -> str:
        """Get corresponding error message.

        @param err_id: error identifier returned by the algorithm
        @return: string representing the error message for the specified error id.
        @raise PhyException: unknown err_id
        """
        try:
            return {
                SnpsPhy.PHY_ERR_OK: '',
                SnpsPhy.PHY_ERR_UNSUPPORTED: 'DDR PHY: unsupported operation',
                SnpsPhy.PHY_ERR_TIMEOUT: 'DDR PHY: timeout error',
                SnpsPhy.PHY_ERR_TRAINING_1D_FAILED: 'DDR PHY: 1D training failed',
                SnpsPhy.PHY_ERR_TRAINING_2D_FAILED: 'DDR PHY: 2D training failed',
                SnpsPhy.PHY_ERR_INVALID_DIAG_TEST: 'DDR PHY: invalid diagnostics test',
                SnpsPhy.PHY_ERR_DIAG_FAILED: 'DDR PHY: diagnostics failed',
                SnpsPhy.PHY_ERR_HARDWARE_FAILED: 'DDR PHY: hardware initialization failed',
                SnpsPhy.DDR_ERR_INITIALIZATION_FAILED: 'DDR: initialization failed'
            }[err_id]
        except KeyError:
            raise PhyException("DDR PHY: unknown error code: " + str(err_id))

    @staticmethod
    def _read_messages_file(messages_filename: str) -> Dict[int, str]:
        """Read a generic messages file.

        @param messages_filename: path to messages file
        @return: messages as dict
        @raise PhyException: messages_filename is unavailable
        """
        messages_dict = {}
        if not os.path.isfile(messages_filename):
            raise PhyException(f"DDR PHY: cannot find messages file {messages_filename}")
        with open(messages_filename, encoding='utf-8') as messages_handle:
            messages = messages_handle.readlines()

        # Strip trailing/leading whitespaces
        messages = [message.strip() for message in messages]

        # Obtain ID and the actual message
        for message in messages:
            separator = message.find(' ')
            if separator < 0:
                logging.getLogger(__name__).error("DDR PHY: cannot parse message (%s)", message)
            else:
                msg_id = to_int(message[:separator])
                msg = message[separator + 1:].strip('"').replace('\\n', '\n')
                messages_dict[msg_id] = msg

        # Return the messages read from file
        return messages_dict

    def _read_training_messages_file(self, stage_2d: bool, quick_boot: bool) -> Dict[int, str]:
        """Read and parse the training messages file.

        @param stage_2d: reading 2d messages or not
        @param quick_boot: reading quick boot messages or not
        @return: messages as dict
        """
        # Obtain filename and read it
        # Get the appropriate 1D/2D firmware/messages (makes sense only for training FW)
        if quick_boot and stage_2d:
            logging.getLogger(__name__).error("Training messages for QuickBoot stage 2D are not available!")
            return {}

        messages_file = os.path.abspath(
            os.path.join(self.data_dir, "firmware", self.firmware_version, self.memory_type)
        )
        if quick_boot:
            messages_file += '_quickboot'
        elif stage_2d:
            messages_file += '_2d'

        messages_file = os.path.join(
            messages_file,
            self.get_data_file(mem_type=self.memory_type, data_type="messages", data_2d=stage_2d, quick_boot=quick_boot)
        )

        # Simply read the messages now
        return self._read_messages_file(messages_file)

    def _get_log_messages(self) -> Tuple[Dict[int, str], Dict[int, str]]:
        """If training messages have been requested, read the possible messages from file.

        @return: messages for 1d and 2d as dicts
        """
        training_messages_1d = self._read_training_messages_file(stage_2d=False, quick_boot=self.quick_boot)
        training_messages_2d = {}
        if (not self.quick_boot) and self.phy_version_2 and (self.memory_type != 'ddr3'):
            training_messages_2d = self._read_training_messages_file(stage_2d=True, quick_boot=self.quick_boot)

        return training_messages_1d, training_messages_2d  # type: ignore

    def process_logged_messages(self, num_logged_items: int, br: BufferedReader):  # type: ignore
        """Analyse all messages reported by the PHY and write them to log file.

        @param num_logged_items: number of logged messages
        @param br: BufferedReader
        @raise PhyException: error while reading logged messages
        """
        # We'll have to read items that look like:
        #   { uint32_t major_message, uint32_t streaming_messages[] }

        training_messages_1d, training_messages_2d = self._get_log_messages()

        log_addr = self.log_addr
        log_handle = None

        # Sanity check for num_logged_items
        if num_logged_items < 0 or num_logged_items > 10000:  # Adjust max value as needed
            self.logger.warning(f"Suspicious number of logged items: {num_logged_items}")
            if num_logged_items < 0:
                return  # Exit early for negative values

        try:
            # Write to stdout or to file
            log_handle = open(self.log_file, 'a', encoding='utf-8') if self.log_file else sys.stdout

            # Read items one by one
            for item_idx in range(num_logged_items):
                # Check if we have enough space for at least a major message
                if log_addr + 4 > br.addr_max:
                    self.logger.warning(f"Reached memory limit at item {item_idx}/{num_logged_items}, \
                                        addr 0x{log_addr:08x}")
                    break

                try:
                    # Read major message first
                    major_message = br.read_integer(log_addr)
                except PhyException as e:
                    self.logger.warning(f"Failed to read major message at item {item_idx}: {e}")
                    break

                # Extract current stage (1D/2D)
                current_stage = (major_message >> 16) & 0xFFFF
                major_message = major_message & 0xFFFF
                tokens = []
                log_addr += 4

                # Log major message
                if major_message in SnpsPhy._MAJOR_MESSAGES:
                    # Don't print 'start of streaming message'
                    if major_message != 0x0008:
                        log_handle.write("[1] " if (current_stage == 0)
                                        else "[2] " if (current_stage == 1)
                                        else "[D] ")
                        log_handle.write(SnpsPhy._MAJOR_MESSAGES[major_message])
                else:
                    log_handle.write("DDR PHY: unknown major message (0x%x)\n" % major_message)

                # If it's a streaming message, then we need to read all the tokens
                if major_message == 0x0008:
                    # Check if we can read streaming message header
                    if log_addr + 4 > br.addr_max:
                        self.logger.warning(f"Reached memory limit reading streaming message at addr 0x{log_addr:08x}")
                        break

                    try:
                        streaming_message = br.read_integer(log_addr)
                    except PhyException as e:
                        self.logger.warning(f"Failed to read streaming message: {e}")
                        break

                    log_addr += 4

                    # The first streaming message represents the index of the message and contains
                    # the number of tokens used to build the training message.
                    num_tokens = streaming_message & 0xFFFF

                    # Sanity check for num_tokens
                    if num_tokens > 100:  # Adjust based on expected max tokens
                        self.logger.warning(f"Suspicious number of tokens: {num_tokens} \
                                            for message 0x{streaming_message:04x}")
                        continue

                    # Check if we have enough space for all tokens
                    if log_addr + (num_tokens * 4) > br.addr_max:
                        self.logger.warning(f"Not enough space for {num_tokens} tokens at addr 0x{log_addr:08x}")
                        break

                    for token in range(num_tokens):
                        try:
                            tokens.append(br.read_integer(log_addr))
                            log_addr += 4
                        except PhyException as e:
                            self.logger.warning(f"Failed to read token {token}/{num_tokens}: {e}")
                            break

                    # Obtain the message
                    if (current_stage == 1) and (streaming_message in training_messages_2d):
                        message = "[2] " + training_messages_2d[streaming_message] % tuple(tokens)
                    elif (current_stage == 0) and (streaming_message in training_messages_1d):
                        message = "[1] " + training_messages_1d[streaming_message] % tuple(tokens)
                    else:
                        message = "DDR PHY: unknown streaming message (0x%x)\n" % streaming_message
                    log_handle.write(message)

        except Exception as e:
            self.logger.exception(f'DDR PHY: an error occurred while reading training messages: {e}')
            raise PhyException('DDR PHY: an error occurred while reading training messages')
        finally:
            if log_handle and log_handle is not sys.stdout:
                log_handle.close()

    @staticmethod
    def _find_max_nz_seq(seq) -> Tuple[int, int, int]:  # type: ignore
        """Find the longest sequence of zeros in the given array.

        @param seq: array of int to look for zeros in
        @return: zeros sequence start, end and length
        """
        count = z_count = 0
        start = z_start = -1
        end = z_end = -1
        for i, elem in enumerate(seq):
            # All memtests passed?
            if elem == 0:
                # Start of a new sequence?
                if z_start == -1:
                    z_start = i
                # Move the end as well
                z_end = i
                # Increase sequence size
                z_count += 1
            else:
                # At least one test fail. Is the sequence longer than the previous one?
                if z_count > count:
                    count = z_count
                    start = z_start
                    end = z_end
                # Start with a new sequence
                z_start = -1
                z_end = -1
                z_count = 0
        # Maybe sequence ended with a zero?
        if z_count > count:
            count = z_count
            start = z_start
            end = z_end
        return start, end, count

    def process_diag_result(self, global_data=None, data=None):  # type: ignore
        """Collect diagnostics data after running diagnostics firmware.

        item struct:
        {
            uint8_t max_v, max_t;
            uint8_t num_bytes, num_bits;
            {
                float target[6];
                uint16_t delay_range[max_t];
                float vref_range[max_v];
                uint8_t eye_dat[max_v][max_t]
            }[num_bytes][num_bits]
        }[1]
        """
        if global_data is None or data is None:
            return

        log_handle = open(self.result_file, 'w', encoding='utf-8') if self.result_file else sys.stdout

        # Read first part of the diagnostics data
        max_v = global_data >> 24
        max_t = (global_data >> 16) & 0xFF
        num_bytes = (global_data >> 8) & 0xFF
        num_bits = global_data & 0xFF
        no_bits_per_line = num_bits
        if num_bits == 1:
            if self.dbi_enabled:
                no_bits_per_line = 9
            else:
                no_bits_per_line = 8

        # Process diagnostics result
        delay_precision = 32 if self.phy_version_2 else 64
        current_loc = 0
        for byte_n in range(num_bytes):
            for bit_n in range(num_bits):
                # Decode 'target' array
                target = struct.unpack('<ffffff', bytes.fromhex(data[current_loc: current_loc + 8 * 6]))
                current_loc = aligned_incr(current_loc, 8 * 6, 8)

                # Decode delay_range array
                delay_range = []
                for _ in range(max_t):
                    delay_range.append(struct.unpack('<h', bytes.fromhex(data[current_loc: current_loc + 4]))[0])
                    current_loc += 4
                current_loc = aligned_incr(current_loc, 0, 8)

                # Decode vref_range array
                vref_range = []
                for _ in range(max_v):
                    vref_range.append(struct.unpack('<f', bytes.fromhex(data[current_loc: current_loc + 8]))[0])
                    current_loc += 8
                current_loc = aligned_incr(current_loc, 0, 8)

                # Decode RLE data
                dec_data = ''
                cnt = 0
                while cnt < max_v * max_t:
                    byte = data[current_loc: current_loc + 2].lower()
                    current_loc += 2
                    if byte in ('00', 'ff'):
                        reps = int('0x' + data[current_loc: current_loc + 2], 16)
                        current_loc += 2
                    else:
                        reps = 0
                    dec_byte = '' + (reps + 1) * byte
                    dec_data += dec_byte
                    cnt += reps + 1
                current_loc = aligned_incr(current_loc, 0, 8)

                # Decode eye
                dec_crt_loc = 0
                eye = []
                for _ in range(max_v):
                    delay = []
                    for _ in range(max_t):
                        delay.append(int(dec_data[dec_crt_loc: dec_crt_loc + 2], 16))
                        dec_crt_loc += 2
                    eye.append(delay)

                # Determine optimal Vref position in the table (line where eye center is located)
                min_vref_diff = 230.0
                optimal_vref_pos = -1  # eye line index
                for vref_idx, vref_elem in enumerate(vref_range):
                    if abs(target[SnpsPhy.TARGET_VREF_IDX] - vref_elem) <= min_vref_diff:
                        min_vref_diff = abs(target[SnpsPhy.TARGET_VREF_IDX] - vref_elem)
                        optimal_vref_pos = vref_idx
                if optimal_vref_pos not in range(0, len(eye)):
                    self.logger.error("Optimal Vref position could not be determined!\n")
                    return

                # Find width of the eye (computed on the line where eye center is located)
                (_, _, eye_width) = self._find_max_nz_seq(eye[optimal_vref_pos])
                self.logger.info(f"Eye center line {optimal_vref_pos}, eye width {eye_width}\n")

                # Find height of Vref
                delay_pos = int(target[SnpsPhy.TARGET_DELAY_IDX] - delay_range[0])

                # Create a new list containing all Vref elements on current column
                vrefs = []
                for v in range(len(vref_range)):
                    if v >= len(eye):
                        self.logger.error(f"Eye line {v} is missing!\n")
                        return
                    if delay_pos not in range(0, len(eye[v])):
                        self.logger.error(f"Eye line {v} is incomplete; info for delay index {delay_pos} is missing\n")
                        return
                    vrefs.append(eye[v][delay_pos])
                # Find the longest passing sequence
                (start, end, _) = self._find_max_nz_seq(vrefs)
                if (end not in range(0, len(vref_range))) or (start not in range(0, end + 1)):
                    self.logger.warning(f"Unable to determine a passing sequence for delay index {delay_pos}\n")
                    eye_height = 0
                else:
                    eye_height = vref_range[end] - vref_range[start]
                self.logger.info(f"Eye center column {delay_pos}, start {start}, end {end} eye height {eye_height}\n")

                # Get byte and bit info from target data
                _byte_n = target[SnpsPhy.TARGET_BYTE_IDX]
                _bit_n = target[SnpsPhy.TARGET_BIT_IDX]

                # Start printing results
                log_handle.write("-----------------------------------------------------\n")
                log_handle.write("|  CS: %1d  |  Vref: %f V  |  TapDelay: %3d UI  |\n" % (
                    target[SnpsPhy.TARGET_CS_IDX], target[SnpsPhy.TARGET_VREF_IDX], target[SnpsPhy.TARGET_DELAY_IDX]))
                log_handle.write("-----------------------------------------------------\n")
                log_handle.write("|   DQ: %2d    (Byte: %2d | Bit: %2d)   |\n" % (
                    _byte_n * no_bits_per_line + _bit_n, _byte_n, _bit_n))
                log_handle.write("--------------------------------------\n")
                log_handle.write("|   H: %f V  | W: %6.2f %%UI   |\n" % (eye_height,
                                                                         (eye_width / float(delay_precision)) * 100))
                log_handle.write("--------------------------------------\n")
                log_handle.write(" VREF(V)  \\  Strobe delay (UI)  ")
                for dly in delay_range:
                    log_handle.write("| %4i  " % dly)
                log_handle.write("\n--------------------------------")
                for _ in delay_range:
                    log_handle.write("--------")
                log_handle.write("\n")

                # Print the Vref/UI table
                n = 0
                for dly_range in eye:
                    log_handle.write("            %5.3f               " % vref_range[n])
                    for dly_range_idx, current_dly in enumerate(dly_range):
                        val = current_dly

                        # Highlight optimal tap delay and optimal Vref
                        if (val == 0) and (target[SnpsPhy.TARGET_DELAY_IDX] - delay_range[0] == dly_range_idx) and \
                                (n == optimal_vref_pos):
                            log_handle.write("| XXXXX ")
                        else:
                            log_handle.write("| %4i  " % val)
                    log_handle.write("\n")
                    n += 1
                log_handle.write("\n\n")

        if log_handle and log_handle is not sys.stdout:
            log_handle.close()
        else:
            sys.stdout.flush()
