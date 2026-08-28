# Copyright 2020-2025 NXP
"""Communication with a target through a serial channel."""
import ast
import logging
import struct
import time
from typing import Optional, Union

import serial

from memtool.common.app import ApplicationCommand
from memtool.common.channel import Channel
from memtool.common.config_data import ConfigData
from memtool.utils.constants import Const


class SerialChannel(Channel):
    """Class implementing serial communication."""

    logger = logging.getLogger(__name__)

    # Supported processors
    PROCESSORS = {'MIMX8M': 'MIMX8MQ6xxxHZ',
                  'MIMX8MM': 'MIMX8MM4xxxKZ',
                  'MIMX8MN': 'MIMX8MN4xxxIZ',
                  'MIMX8MP': 'MIMX8MP4xxxKZ',
                  'MIMX91': 'MIMX91',
                  'MIMX93': 'MIMX93',
                  'MIMX943': 'MIMX943',
                  'MIMX95': 'MIMX95',
                  'MIMX95_B0': 'MIMX95_B0',
                  'MIMXRT10XX': 'MIMXRT10xx',
                  'MIMXRT11XX': 'MIMXRT11xx'}

    PACK_FORMATS = {1: '<B', 2: '<H', 4: '<I', 8: '<Q'}

    def __init__(self, connect_params: dict):
        """Constructor with optimized serial settings."""
        super(SerialChannel, self).__init__()
        self.connect_params = connect_params
        self.app_logger = None
        self.app_logger_file_handler = None
        self.log_level = self.connect_params.get(Const.PARAM_LOG_LEVEL, 'DEBUG')
        if not isinstance(self.log_level, int):
            self.log_level = getattr(logging, self.log_level.upper(), logging.DEBUG)

        self._init_services()

    def _init_services(self) -> None:
        """Perform serial port initialization with optimized settings."""
        com = self.connect_params.get('COM_PORT', None)
        if com is None:
            com = self.connect_params.get('UART', None)

        try:
            # Optimize serial settings for speed
            self.serial = serial.Serial(
                port=com,
                baudrate=115200,  # Consider increasing if hardware supports
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,  # Very short timeout for non-blocking reads
                write_timeout=0.1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False)

            # Set buffer sizes for better performance
            if hasattr(self.serial, 'set_buffer_size'):
                try:
                    # Try larger buffers first (64KB - Windows max)
                    self.serial.set_buffer_size(rx_size=65536, tx_size=65536)
                except (OSError, AttributeError):
                    try:
                        # Fallback to 32KB
                        self.serial.set_buffer_size(rx_size=32768, tx_size=32768)
                        self.logger.debug('Set serial buffers to 32KB each')
                    except (OSError, AttributeError):
                        # Keep current 16KB setting as final fallback
                        self.serial.set_buffer_size(rx_size=16384, tx_size=16384)
                        self.logger.debug('Set serial buffers to 16KB each')

        except Exception as ex:
            self.logger.exception(str(ex))
            self.serial = None

        if self.serial is not None:
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.serial.close()
            self.logger.info('Using serial: %s', self.serial.port)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Override matches from Channel."""
        for arg in args:
            if isinstance(arg[0], dict):
                return arg[0].get('not_sim', True) and (arg[0][Const.PARAM_S_TC_SOC_NAME] in cls.PROCESSORS)
        return False

    def init_channel(self, config_data: ConfigData = None):  # type: ignore
        """Initialize channel.

        @param config_data: processor config data
        """
        if self.serial is None:
            self.logger.error('Serial channel was not created; channel initialization can not be executed')
            return

        # TODO: <check error strings from _command ?!>
        self.serial.open()
        self.serial.timeout = 0.1
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        self.app_logger = logging.getLogger('test_app')  # type: ignore
        if self.app_logger is not None and not self.app_logger.handlers:
            if self.app_logger_file_handler is not None:
                self.app_logger.removeHandler(self.app_logger_file_handler)
                self.app_logger_file_handler = None
            if config_data is not None:
                if config_data.app_log_file:
                    self.app_logger_file_handler = \
                            logging.FileHandler(filename=config_data.app_log_file, mode='a', encoding='utf-8')
                    self.app_logger.addHandler(self.app_logger_file_handler)
                    self.app_logger.propagate = False

    def reset(self) -> None:
        """Override reset from common.Channel."""
        self._command(cmd=ApplicationCommand.RESET_TARGET, data=None)

    def close(self):  # type: ignore
        """Close channel."""
        if self.serial.isOpen():
            self.serial.close()

    def _encode_data(self, symbol: Optional[tuple[int, int, int]],
                     value: int | None, log_error: bool = True) -> bytearray | None:
        """Build bytearray with the value for a certain application parameter.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @param value: application parameter value for write command, None otherwise
        @param log_error: tells the method if the error should be logged or not
        @result: bytearray = address bytes + value bytes for write command,
                            address bytes + count bytes for read command
        """
        if symbol is None:
            if log_error:
                self.logger.error(f'Encode command data: no symbol was received')
            return None

        address, width, count = symbol

        # Use a lookup table for pack formats to avoid if-elif chains
        pack = self.PACK_FORMATS.get(width)
        if pack is None:
            if log_error:
                self.logger.error(f'Encode command data: unsupported parameter size {width}')
            return None

        # Pre-calculate the total size for better memory allocation
        if value is None:
            # Read command: address (4) + count (4)
            binary = bytearray(8)
            struct.pack_into('<II', binary, 0, address, count * width)
        else:
            # Write command: address (4) + data (width * count)
            total_size = 4 + (width * count)
            binary = bytearray(total_size)
            struct.pack_into('<I', binary, 0, address)

            if count == 1:
                # Single value - optimize for the common case
                if isinstance(value, int):
                    struct.pack_into(pack, binary, 4, value)
                elif isinstance(value, str):
                    value_str = value.strip()
                    if value_str:  # Check for empty string
                        try:
                            # Use a single int() call with automatic base detection
                            value_int = int(value_str, 0) if value_str.startswith('0x') else int(value_str)
                            struct.pack_into(pack, binary, 4, value_int)
                        except ValueError:
                            if log_error:
                                self.logger.error(f'Encode command data: invalid value "{value_str}"')
                            return None
                else:
                    if log_error:
                        self.logger.error(f'Encode command data: unsupported parameter type {type(value)}')
                    return None
            else:
                # Multiple values - optimize array handling
                offset = 4
                if isinstance(value, str):
                    # Pre-process the string once
                    value_str = value.strip()
                    if value_str.startswith('[') and value_str.endswith(']'):
                        value_str = value_str[1:-1]  # Remove brackets

                    # Split and convert all values at once
                    try:
                        values = []
                        for v in value_str.split(','):
                            v = v.strip()
                            if v:
                                # Automatic base detection
                                values.append(int(v, 0) if v.startswith('0x') else int(v))
                        if len(values) != count:
                            if log_error:
                                self.logger.error(f'Encode command data: expected {count} values, got {len(values)}')
                            return None

                        # Pack all values efficiently
                        for val in values:
                            struct.pack_into(pack, binary, offset, val)
                            offset += width
                    except ValueError as e:
                        if log_error:
                            self.logger.error(f'Encode command data: invalid value in array - {e}')
                        return None
                elif isinstance(value, (list, tuple)):
                    # Handle list/tuple of values
                    if len(value) != count:
                        if log_error:
                            self.logger.error(f'Encode command data: expected {count} values, got {len(value)}')
                        return None

                    try:
                        for val in value:
                            if isinstance(val, str):
                                val = int(val.strip(), 0) if val.strip().startswith('0x') else int(val.strip())
                            struct.pack_into(pack, binary, offset, val)
                            offset += width
                    except (ValueError, struct.error) as e:
                        if log_error:
                            self.logger.error(f'Encode command data: error packing values - {e}')
                        return None
                else:
                    if log_error:
                        self.logger.error(f'Encode command data: unsupported parameter type {type(value)}')
                    return None

        return binary

    def _decode_data(self, symbol: Optional[tuple[int, int, int]], data: bytearray,
                     log_error: bool = True) -> list[int] | None:
        """Decode parameter value from bytearray.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @param data: bytearray containing parameter value
        @param log_error: tells the method if the error should be logged or not
        @result: list of int if decode is successful, None otherwise
        """
        if symbol is None:
            if log_error:
                self.logger.error(f'Encode command data: no symbol was received')
            return None

        _, width, count = symbol

        # Use class-level lookup table for unpack formats
        unpack = self.PACK_FORMATS.get(width)
        if unpack is None:
            if log_error:
                self.logger.error(f'Decode data: unsupported parameter size {width}')
            return None

        # Validate data size
        expected_size = width * count
        if len(data) < expected_size:
            if log_error:
                self.logger.error(f'Decode data: insufficient data - expected {expected_size} bytes, got {len(data)}')
            return None

        # Optimize for single value (common case)
        if count == 1:
            try:
                return [struct.unpack_from(unpack, data, 0)[0]]
            except struct.error as e:
                if log_error:
                    self.logger.error(f'Decode data: unpack error - {e}')
                return None

        # For multiple values, use different strategies based on count
        try:
            if count < 10:
                # For small arrays, use list comprehension with unpack_from
                return [struct.unpack_from(unpack, data, i * width)[0] for i in range(count)]
            else:
                # For larger arrays, use struct.iter_unpack for better performance
                # Create format string for all values at once
                if width == 1:
                    # Special optimization for byte arrays
                    return list(data[:count])
                else:
                    # Use iter_unpack for efficient unpacking of multiple values
                    return [val for (val,) in struct.iter_unpack(unpack, data[:expected_size])]
        except struct.error as e:
            if log_error:
                self.logger.error(f'Decode data: unpack error - {e}')
            return None

    def _send_command(self, cmd: ApplicationCommand, data: None | bytearray,
                      timeout: float, log_error: bool = True) -> bool:
        """Write command on serial.

        @param cmd: application command
        @param data: command parameters
        @param timeout: wait time after a command is sent in s
        @param log_error: tells the method if the error should be logged or not
        @return: True is command was sent successfully, False otherwise
        """
        if cmd.id is None:
            return True  # nothing to be send to the target

        # Clear input buffer more efficiently
        if self.serial.in_waiting > 0:
            # Read all available data at once instead of line by line
            pending_data = self.serial.read(self.serial.in_waiting)
            if log_error and pending_data:
                # Decode and log in one operation
                try:
                    lines = pending_data.decode(errors='ignore').strip()
                    if self.app_logger is not None and len(lines) > 0:
                        self.app_logger.log(level=self.log_level, msg=lines)
                except (UnicodeDecodeError, AttributeError, OSError):
                    # Explicitly ignore only expected decode/logging errors for pending data
                    # UnicodeDecodeError: malformed bytes in pending data
                    # AttributeError: app_logger method issues
                    # OSError: logging system errors
                    pass

        # prepare command data
        cmd_data = bytearray()
        cmd_data.extend(struct.pack('<B', cmd.id))
        num_params = len(data) if data is not None else 0
        cmd_data.extend(struct.pack('<B', num_params))
        if num_params > 0 and data is not None:
            cmd_data.extend(data)

        try:
            # Write and flush immediately
            bytes_written = self.serial.write(cmd_data)
            self.serial.flush()  # Ensure data is sent immediately

            # Only sleep if timeout > 0 and verify all bytes were written
            if bytes_written != len(cmd_data):
                if log_error:
                    self.logger.error(f'Failed to write all bytes: {bytes_written}/{len(cmd_data)}')
                return False

            # Use timeout only if specified and > 0
            if timeout > 0:
                time.sleep(timeout)

        except Exception as ex:
            if log_error:
                self.logger.exception('Send command ended with exception: %s', str(ex))
            return False
        return True

    def _read_response(self, cmd: ApplicationCommand,
                  timeout: float, log_error: bool = True) -> tuple[bool, str | None]:
        """Optimized read with better buffer management."""
        if cmd.response is None:
            return True, None

        response = False
        response_data = None
        start_time = time.time()
        is_infinite = timeout < 0

        # Use a local buffer to accumulate partial data
        read_buffer = bytearray()

        while not response:
            # Read all available data at once (non-blocking)
            if self.serial.in_waiting > 0:
                try:
                    # Read up to 4KB at once
                    chunk = self.serial.read(min(self.serial.in_waiting, 4096))
                    read_buffer.extend(chunk)

                    # Process complete lines from buffer
                    while b'\n' in read_buffer:
                        line_end = read_buffer.index(b'\n')
                        line = read_buffer[:line_end].decode(errors='ignore').strip()
                        read_buffer = read_buffer[line_end + 1:]

                        if cmd.response in line:
                            response = True
                            response_data = line.replace(cmd.response, '').strip()
                            break

                        if self.app_logger is not None and len(line) > 0:
                            self.app_logger.log(level=self.log_level, msg=line)

                except Exception as ex:
                    if log_error:
                        self.logger.exception('Failed to read response: %s', str(ex))

            # Check timeout
            if not is_infinite and (time.time() - start_time) > timeout:
                if log_error:
                    self.logger.warning(f'Timeout waiting for response "{cmd.response}"')
                break

            # Minimal sleep only if no data available
            if self.serial.in_waiting == 0:
                time.sleep(0.001)

        return response, response_data

    def _command(self, cmd: ApplicationCommand, data: None | bytearray = None,
                 read_timeout: None | float = None, log_error: bool = True) -> tuple[bool, str | None]:
        """Execute a command and return its output.

        @param cmd: application command
        @param data: command parameters
        @param read_timeout: wait time for command response in s
        @param log_error: tells the method if the error should be logged or not
        @return: True if command expected result was found, False otherwise &
                response data as string if applicable (at read from target) or None otherwise
        """
        if self.serial is None:
            if log_error:
                self.logger.error('Serial channel was not created; command can not be executed')
            return False, None

        if not self.serial.isOpen():
            if log_error:
                self.logger.error('Serial channel was closed; command can not be executed')
            return False, None

        if not self._send_command(cmd=cmd, data=data, timeout=cmd.send_timeout, log_error=log_error):
            return False, None

        actual_read_timeout = read_timeout if read_timeout is not None else cmd.read_timeout
        return self._read_response(cmd=cmd, timeout=actual_read_timeout, log_error=log_error)

    def is_alive(self, wait_for_response=True) -> bool:  # type: ignore
        """Override is_alive from common.Channel."""
        if not wait_for_response:
            response, _ = self._command(cmd=ApplicationCommand.SERIAL_CHANNEL_OPENED)
            return response
        # Use minimal timeouts for is_alive check
        response, _ = self._command(cmd=ApplicationCommand.IS_ALIVE_TARGET)
        return response

    def _read_symbol(self, symbol: Optional[tuple[int, int, int]],
                     log_error:bool = True) -> None | int | str:
        """Read symbol from target.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @param log_error: tells the method if the error should be logged or not
        @return: value as int if the operation was successfull, None otherwise
        """
        if symbol is None:
            return None

        cmd_data = self._encode_data(symbol=symbol, value=None, log_error=log_error)
        if cmd_data is None:
            if log_error:
                self.logger.error(f'Read command: no data to be read')
            return None

        response, response_data = self._command(cmd=ApplicationCommand.READ_FROM_TARGET,
                                                data=cmd_data, log_error=log_error)
        if not response or not response_data:
            return None

        data = bytearray.fromhex(response_data)
        decoded_data = self._decode_data(symbol=symbol, data=data, log_error=log_error)
        if decoded_data is None:
            return None

        _, _, count = symbol
        if count == 1:
            return decoded_data[0]

        return str(decoded_data)

    @staticmethod
    def parse_val(value, width, count) -> str:  # type: ignore
        """Parse a string or integer (simple or array) value into a hex-encoded byte-stream representation.

        @return: hex value as str
        """
        if isinstance(value, list):
            if len(value) != count:
                SerialChannel.logger.error(f'Failed to parse value: found {len(value)} values, expected {count}')
                return ''

            result = ''
            for e in value:
                result += SerialChannel.parse_val(e, width, 1)
            return result

        if isinstance(value, str):
            val = value.strip()
            if val.startswith('[') and val.endswith(']'):
                return SerialChannel.parse_val(ast.literal_eval(val), width, count)

            if count != 1:
                SerialChannel.logger.error(f'Failed to parse value: found 1 value, expected {count}')
                return ''
            base = 16 if val.startswith('0x') else 10
            return '{n:0{w}x}'.format(n=int(val, base), w=2 * width)[:2 * width]

        if count != 1:
            SerialChannel.logger.error(f'Failed to parse value: found 1 value, expected {count}')
            return ''

        return '{n:0{w}x}'.format(n=value, w=2 * width)[:2 * width]

    def read_data(self, address: int, width: int, count: int) -> Optional[str]:
        """Override read_data from Channel.

        @param address: application-level address
        @param width: data width (access size)
        @param count: number of words of size 'width' to read
        @return: read data as string
        """
        if count <= 0 or width <= 0:
            self.logger.error(f'Invalid read parameters: count={count}, width={width}')
            return ''

        cmd_data = self._encode_data(symbol=(address, width, count), value=None)
        if cmd_data is None:
            self.logger.error(f'Read command: no data to be read')
            return None

        # Use optimized timeouts for read operations
        # Write timeout can be minimal since we're just sending the command
        # Read timeout should be proportional to the amount of data expected
        read_timeout = max(0.1, (count * width) / 1024.0)  # Scale timeout based on data size
        response, response_data = self._command(
            cmd=ApplicationCommand.READ_FROM_TARGET,
            data=cmd_data,
            read_timeout=read_timeout)

        return response_data if response and response_data else ''

    def write_symbol(self, symbol: Optional[tuple[int, int, int]], value: int | None) -> bool:
        """Override write_symbol from common.Channel.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @param value: value to be written
        @return: True if operation was successful, False otherwise
        """
        if symbol is None:
            return False

        cmd_data = self._encode_data(symbol=symbol, value=value)
        if cmd_data is None:
            self.logger.error(f'Write command: no data to be written')
            return False

        if len(cmd_data) > 255:
            self.logger.error(f'Write command: maximum number of bytes were exceeded')
            return False

        # Use minimal timeouts for write operations
        response, _ = self._command(cmd=ApplicationCommand.WRITE_TO_TARGET, data=cmd_data)
        return response

    def read_symbol(self, symbol: Optional[tuple[int, int, int]]) -> Union[None, int, str]:  # type: ignore
        """Override read_symbol from common.Channel.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @return: symbol value if the operation succeeded or None if the read symbol operation failed
        """
        count = 3
        while count > 0:
            result = self._read_symbol(symbol=symbol)
            if result is not None:
                return result

            count -= 1
            self.logger.debug('Retry read symbol')

        self.logger.error('Read symbol failed after 3 tries')
        return None

    def read_symbol_silent(self, symbol: Optional[tuple[int, int, int]]) -> int | str | None:  # type: ignore
        """Read symbol only once. Doesn't print error in case symbol is not found.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @return: symbol value if the operation succeeded or None if the read symbol operation failed
        """
        value = self._read_symbol(symbol=symbol, log_error=False)
        if value is None:
            return None
        if isinstance(value, str):
            value = '0x' + value.strip()
            try:
                int_value = int(value, 16)
                return str(int_value)
            except ValueError:
                return None
        return value  # value is int

    def execute_command(self, cmd: ApplicationCommand,
                        data: None | bytearray,
                        timeout: None | float = None) -> bool:  # type: ignore
        """Override execute_command from common.Channel.

        @param data: command parameters
        @param timeout: wait time for command response in s
        @return: True if command expected result was found, False otherwise
        """
        response, _ = self._command(cmd=cmd, data=data, read_timeout=timeout)
        return response
