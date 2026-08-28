# Copyright 2023-2025 NXP
"""Memtool entry point from Config Tools."""
import argparse
import os
import sys
from enum import Enum

from memtool.common.config_data import ConfigData, SnpsFirmware

MEMTOOL_HOTFIX_PATH = "MEMTOOL_HOTFIX_PATH"


class OperationType(Enum):
    """Memtool operations available from Config Tools."""

    CODEGEN = "codegen"
    RUNTEST = "runtest"
    TESTCONNECTION = "testconn"
    GETDEVICES = "getdevices"

    @staticmethod
    def get_values() -> list[str]:
        """Get the operation types."""
        ops = []
        for op in OperationType:
            ops.append(op.value)
        return ops


# Presence of the MEMTOOL_HOTFIX_PATH environment variable indicates the memtool module that must be used,
# so sys.path will be updated to use this version:
if MEMTOOL_HOTFIX_PATH in os.environ:
    memtool_update_path = os.environ[MEMTOOL_HOTFIX_PATH]
    if os.path.exists(os.path.abspath(memtool_update_path)):
        sys.path.insert(0, memtool_update_path)


parser = argparse.ArgumentParser(description="Execute memtool operation")
parser.add_argument(
    "-t",
    "--op-type",
    required=True,
    choices=OperationType.get_values(),
    help="Specifies operation type",
)
parser.add_argument(
    "files",
    nargs="*",
    type=argparse.FileType("r"),
    help="JSON format files containing test parameters",
)
parser.add_argument(
    "-m",
    "--mem-type",
    required=False,
    choices=[name for name in ConfigData.MEMORY_TYPES.values()],
    help="MEMORY type",
)
parser.add_argument(
    "-f",
    "--firmware-version",
    required=False,
    choices=SnpsFirmware.get_names(),
    help="Firmware version",
)
parser.add_argument("-d", "--data-dir", required=False, default=os.getcwd(), help="Data path")
parser.add_argument(
    "-o",
    "--output-dir",
    required=False,
    default=os.getcwd(),
    help="Output directory path",
)
parser.add_argument(
    "-l",
    "--log",
    required=False,
    choices=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
    default="ERROR",
    help="Specifies logging level",
)
parser.add_argument(
    "-x",
    "--compress",
    required=False,
    action="store_true",
    help="Enable compression for firmware binaries",
)
parser.add_argument("-p", "--phy-log-file", required=False, help="specifies PHY log file")
parser.add_argument("-i", "--figure-file", required=False, help="specifies figure result file")
parser.add_argument("-v", "--vref-info-file", required=False, help="specifies vref info result file")
parser.add_argument("-s", "--sm-bin-file", required=False, help="specifies system manager binary file")
parser.add_argument("-a", "--app-log-file", required=False, help="specifies application log file")
parser.add_argument("-c", "--com-port", required=False, help="specifies COM port used for connection test")
parser.add_argument(
    "-b",
    "--board-hid",
    required=False,
    default="0",
    help="specifies board HID used for connection test")

# call code generation or test execution depending on the specified op_type
args = parser.parse_args()
operation = OperationType(args.op_type)
if operation == OperationType.CODEGEN:
    from memtool.codegen.code_gen import run_code_gen

    run_code_gen(
        args.log,
        args.files,
        args.firmware_version,
        args.mem_type,
        args.output_dir,
        args.data_dir,
    )
elif operation == OperationType.GETDEVICES:
    from memtool.memtests.connection_test import get_devices
    get_devices(args.log, args.data_dir, args.output_dir)
elif operation == OperationType.TESTCONNECTION:
    from memtool.memtests.connection_test import run_connection_test
    run_connection_test(args.log, args.data_dir, args.output_dir, args.com_port, args.board_hid)
else:
    from memtool.s import run_test
    run_test(
        args.log,
        args.files,
        args.app_log_file,
        args.phy_log_file,
        args.figure_file,
        args.vref_info_file,
        args.data_dir,
        args.sm_bin_file,
        args.compress,
    )
