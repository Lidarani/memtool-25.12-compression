# Copyright 2021-2025 NXP
"""TODO:summary line."""
import logging

from memtool.utils.helper import is_hex

logger = logging.getLogger(__name__)


class DCDCommand:
    """Class for storing DCD commands."""

    def __init__(self, command: int, address: int, value: int, size: int, name: str):
        """TODO:summary line."""
        self.command = command
        self.address = address
        self.value = value
        self.size = size
        self.name = name

    def __str__(self):  # type: ignore
        return f'{self.command}: 0x{self.address:x} -> 0x{self.address:x}'


class DCDCommandIds:
    """Command codes."""

    UNKNOWN = -1
    CMD_WRITE_DATA = 0
    CMD_SET_BIT = 1
    CMD_CLR_BIT = 2
    CMD_CHECK_BIT_SET = 3
    CMD_CHECK_BIT_CLR = 4
    CMD_COPY_BIT = 5
    CMD_DDR_PARAM = 6
    CMD_FREQ0_WRITE_DATA = 7
    CMD_FREQ0_SET_BIT = 8
    CMD_FREQ0_CLR_BIT = 9
    CMD_FREQ0_CHECK_BIT_SET = 10
    CMD_FREQ0_CHECK_BIT_CLR = 11
    CMD_FREQ1_WRITE_DATA = 12
    CMD_FREQ1_SET_BIT = 13
    CMD_FREQ1_CLR_BIT = 14
    CMD_FREQ1_CHECK_BIT_SET = 15
    CMD_FREQ1_CHECK_BIT_CLR = 16
    CMD_FREQ2_WRITE_DATA = 17
    CMD_FREQ2_SET_BIT = 18
    CMD_FREQ2_CLR_BIT = 19
    CMD_FREQ2_CHECK_BIT_SET = 20
    CMD_FREQ2_CHECK_BIT_CLR = 21
    CMD_FREQ3_WRITE_DATA = 22
    CMD_FREQ3_SET_BIT = 23
    CMD_FREQ3_CLR_BIT = 24
    CMD_FREQ3_CHECK_BIT_SET = 25
    CMD_FREQ3_CHECK_BIT_CLR = 26
    CMD_PHY_WRITE_DATA = 0xA0
    CMD_PHY_CLR_BIT = 0xA1
    CMD_PHY_SET_BIT = 0xA2
    CMD_SYS_PARAM_SET = 0xB0
    CMD_FREQ0_SET_TIMING = 0xC0
    CMD_FREQ1_SET_TIMING = 0xC1
    CMD_FREQ2_SET_TIMING = 0xC2
    CMD_FREQ3_SET_TIMING = 0xC3
    CMD_START_SECTION = (ord('H') << 24) + (ord('E') << 16) + (ord('A') << 8) + (ord('D'))
    CMD_END = 0xA5A5A5A5


dcd_command_map = {
    "memory set": DCDCommandIds.CMD_WRITE_DATA,
    "memory setbit": DCDCommandIds.CMD_SET_BIT,
    "memory clrbit": DCDCommandIds.CMD_CLR_BIT,
    "memory chkbit1": DCDCommandIds.CMD_CHECK_BIT_SET,
    "memory chkbit0": DCDCommandIds.CMD_CHECK_BIT_CLR,
    "freq0 set": DCDCommandIds.CMD_FREQ0_WRITE_DATA,
    "freq0 setbit": DCDCommandIds.CMD_FREQ0_SET_BIT,
    "freq0 clrbit": DCDCommandIds.CMD_FREQ0_CLR_BIT,
    "freq0 chkbit1": DCDCommandIds.CMD_FREQ0_CHECK_BIT_SET,
    "freq0 chkbit0": DCDCommandIds.CMD_FREQ0_CHECK_BIT_CLR,
    "freq1 set": DCDCommandIds.CMD_FREQ1_WRITE_DATA,
    "freq1 setbit": DCDCommandIds.CMD_FREQ1_SET_BIT,
    "freq1 clrbit": DCDCommandIds.CMD_FREQ1_CLR_BIT,
    "freq1 chkbit1": DCDCommandIds.CMD_FREQ1_CHECK_BIT_SET,
    "freq1 chkbit0": DCDCommandIds.CMD_FREQ1_CHECK_BIT_CLR,
    "freq2 set": DCDCommandIds.CMD_FREQ2_WRITE_DATA,
    "freq2 setbit": DCDCommandIds.CMD_FREQ2_SET_BIT,
    "freq2 clrbit": DCDCommandIds.CMD_FREQ2_CLR_BIT,
    "freq2 chkbit1": DCDCommandIds.CMD_FREQ2_CHECK_BIT_SET,
    "freq2 chkbit0": DCDCommandIds.CMD_FREQ2_CHECK_BIT_CLR,
    "freq3 set": DCDCommandIds.CMD_FREQ3_WRITE_DATA,
    "freq3 setbit": DCDCommandIds.CMD_FREQ3_SET_BIT,
    "freq3 clrbit": DCDCommandIds.CMD_FREQ3_CLR_BIT,
    "freq3 chkbit1": DCDCommandIds.CMD_FREQ3_CHECK_BIT_SET,
    "freq3 chkbit0": DCDCommandIds.CMD_FREQ3_CHECK_BIT_CLR,
    "phy set": DCDCommandIds.CMD_PHY_WRITE_DATA,
    "phy clrbit": DCDCommandIds.CMD_PHY_CLR_BIT,
    "phy setbit": DCDCommandIds.CMD_PHY_SET_BIT,
    "sysparam set": DCDCommandIds.CMD_SYS_PARAM_SET,
    "freq0 timing": DCDCommandIds.CMD_FREQ0_SET_TIMING,
    "freq1 timing": DCDCommandIds.CMD_FREQ1_SET_TIMING,
    "freq2 timing": DCDCommandIds.CMD_FREQ2_SET_TIMING,
    "freq3 timing": DCDCommandIds.CMD_FREQ3_SET_TIMING,
}

# Supported commands and the expected number of parameters for each of them
# Note that the order in this map is important: "memory setbit" should be verified before "memory set"
supported_commands_map = {
    "memory setbit": 3,
    "memory set": 3,
    "memory clrbit": 3,
    "memory chkbit1": 3,
    "memory chkbit0": 3,
    "freq0 setbit": 3,
    "freq0 set": 3,
    "freq0 clrbit": 3,
    "freq0 chkbit1": 3,
    "freq0 chkbit0": 3,
    "freq1 setbit": 3,
    "freq1 set": 3,
    "freq1 clrbit": 3,
    "freq1 chkbit1": 3,
    "freq1 chkbit0": 3,
    "freq2 setbit": 3,
    "freq2 set": 3,
    "freq2 clrbit": 3,
    "freq2 chkbit1": 3,
    "freq2 chkbit0": 3,
    "freq3 set": 3,
    "freq3 setbit": 3,
    "freq3 clrbit": 3,
    "freq3 chkbit1": 3,
    "freq3 chkbit0": 3,
    "sysparam set": 2,
    "ddrparam set": 2,
    "freq0 timing": 3,
    "freq1 timing": 3,
    "freq2 timing": 3,
    "freq3 timing": 3
}


def get_dcd_command(command: str) -> int:
    """Get command code.

    @param command: command name
    @return: int corresponding to the command
    """
    return dcd_command_map.get(command, DCDCommandIds.UNKNOWN)


def get_dcd_command_str(command_id: int) -> str:
    """Get key name from a certain index.

    @param command_id: index in dcd_command_map
    @return: key number command_id
    """
    return list(dcd_command_map.keys())[list(dcd_command_map.values()).index(command_id)]


def check_ds_validity(ds_content: str) -> bool:  # type: ignore
    """Check if the received string could represent a valid ds file.

    @param ds_content: ds file
    @return: True if content is valid
    """
    if len(ds_content) == 0:
        return False  # empty ds is not valid

    supported_commands = list(supported_commands_map.keys())
    for content_line in ds_content.split('\n'):
        line = ' '.join(content_line.split())  # remove multiple spaces
        if len(line) == 0:
            continue  # skip empty lines

        if line.startswith('#'):
            continue  # skip comments

        # check if line contains a supported command
        current_command = ''
        for command in supported_commands:
            line_length = len(line)
            cmd_length = len(command)
            if line.startswith(command) and ((line_length > cmd_length) and (line[len(command)] == ' ')):
                current_command = command
                break
        if len(current_command) == 0:
            logger.error(f'Command from \"{line}\" is not supported!')
            return False

        # check command has the right number of params
        line_params = line[len(current_command):]  # skip command
        comment_idx = line_params.rfind('#')
        if comment_idx > 0:
            line_params = line_params[:comment_idx]
        cmd_params = line_params.split()
        current_command_no_params = supported_commands_map.get(current_command)
        if len(cmd_params) != current_command_no_params:
            logger.error(f'Command from \"{line}\" does not have the right number of parameters!')
            return False

        # check numerical parameters; we expect int and hex, so we could use is_hex method to check their validity
        if current_command_no_params == 3:  # we know that commands with 3 parameters expect 3 numbers
            correct_cmd_params = is_hex(cmd_params[0]) and is_hex(cmd_params[1]) and is_hex(cmd_params[2])
        elif current_command_no_params == 2:  # we know that commands with 2 parameters expect 1 string and 1 number
            correct_cmd_params = is_hex(cmd_params[1])
        else:
            logger.error(f'DS validator expects commands with 2 or 3 parameters. Check command from line \"{line}\"!')
            return False

        if not correct_cmd_params:
            logger.error(f'Command from line \"{line}\" has incorrect parameters!')
            return False

        return True
    return False
