# Copyright 2025 NXP
"""Implementation of connection tests."""
import io
import logging
import os
import sys
import traceback

import memtool
import memtool.processor
from memtool.common.base_test import BaseTest, TestStatus
from memtool.common.config_data import ConfigData
from memtool.common.factories import ProcessorFactory
from memtool.common.sdp_interface import SDPUtils
from memtool.common.workspace import Workspace
from memtool.utils.constants import Const
from memtool.utils.helper import add_file_to_params

logger = logging.getLogger(__name__)


class ConnectionTest(BaseTest):
    """Special test that checks only that target is responsive."""

    logger = logging.getLogger(__name__)

    ID = 100
    NAME = 'Target-Is-Alive'

    CONNECTION_TEST_PARAMS_FILES = ['connect.json', 'ddrc_config_in.json']
    CONNECTION_TEST_PASS_MESSAGE = "Connection test passed"
    CONNECTION_TEST_FAIL_MESSAGE = "Connection test failed"

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        super(ConnectionTest, self).__init__(config_data)

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from BaseTest."""
        super(ConnectionTest, cls).update_config_params(config_data)
        config_data.params['app']['check_target_is_responsive'] = True

    def get_results(self) -> dict:
        """Getter for the currently collected results."""
        return {}  # no need to return complex results for connection test


def get_devices(log: str, data_dir: str, output_dir: str):  # type: ignore
    """Get HIDs of connected devices."""
    if not os.path.isdir(output_dir):
        logger.error("% directory not found; test parameters can't be found.",
                     os.path.abspath(output_dir))
        return
    Workspace.get_instance().set_location(output_dir)

    params = {}  # type: ignore

    for file_name in ConnectionTest. CONNECTION_TEST_PARAMS_FILES:
        file = os.path.join(output_dir, file_name)
        if not os.path.exists(file):
            logger.error(f"Parameter file {os.path.abspath(file_name)} not found in "
                         f"{os.path.abspath(output_dir)}; "\
                         "test parameters can't be found.")
            return
        params = add_file_to_params(file, params)
    config_data = ConfigData(data_dir, params)
    config_data.log_level = getattr(logging, log)

    try:
        usb_devices = SDPUtils.scan_usb_devices_for_proc(config_data.soc_name)
        if len(usb_devices) > 0:
            for usb_device_index in range(0, len(usb_devices)):
                usb_hid = f'HID{usb_device_index}'
                print(usb_hid)
                # print(usb_devices[usb_device_index].device.path_str)

    except Exception:
        if logger.getEffectiveLevel() == logging.DEBUG:
            logger.exception("Application error:")
            traceback.print_exc()
        else:
            logger.error("An error occurred while searching for connected devices," \
                         "set log level to DEBUG for more details.")


def run_connection_test(log: str, data_dir: str, output_dir: str, com_port: str, hid: str):  # type: ignore
    """Execute test connection."""
    if not os.path.isdir(output_dir):
        logger.error("% directory not found; test parameters can't be found.",
                     os.path.abspath(output_dir))
        return
    Workspace.get_instance().set_location(output_dir)

    params = {}  # type: ignore

    for file_name in ConnectionTest. CONNECTION_TEST_PARAMS_FILES:
        file = os.path.join(output_dir, file_name)
        if not os.path.exists(file):
            logger.error(f"Parameter file {os.path.abspath(file_name)} not found in "
                         f"{os.path.abspath(output_dir)}; "\
                         "test parameters can't be found.")
            return
        params = add_file_to_params(file, params)
    config_data = ConfigData(data_dir, params)
    config_data.log_level = getattr(logging, log)
    config_data.params[Const.PARAM_S_TC]['COM_PORT'] = com_port
    config_data.params[Const.PARAM_S_TC]['usb_sel'] = hid
    config_data.params[Const.PARAM_S_APP] = {Const.PARAM_TEST_PARAMS: {}}

    try:
        # get test to be executed
        test_cls = ConnectionTest
        if test_cls is None:
            return

        # save configuration parameters and apply test specific parameters
        test_cls.update_config_params(config_data)

        # run RPA
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        processor.ddrc_reg_calc(config_data)

        # run test
        test = test_cls(config_data)
        if TestStatus.PASS == BaseTest.run_test(test, config_data):
            print(ConnectionTest.CONNECTION_TEST_PASS_MESSAGE)
        else:
            print(ConnectionTest.CONNECTION_TEST_FAIL_MESSAGE)

    except Exception:
        if logger.getEffectiveLevel() == logging.DEBUG:
            logger.exception("Application error:")
            traceback.print_exc()
        else:
            logger.error("An error occurred while running connection test, set log level to DEBUG for more details.")
        print(ConnectionTest.CONNECTION_TEST_FAIL_MESSAGE)
