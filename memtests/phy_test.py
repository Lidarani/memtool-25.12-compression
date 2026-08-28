# Copyright 2020-2025 NXP
"""TODO:summary line."""
import logging
import time

from memtool.common.app import ApplicationCommand
from memtool.common.base_test import BaseTest
from memtool.common.config_data import ConfigData
from memtool.common.config_data_mcu import ConfigDataMCU

from .snps_phy import BufferedReader, SnpsPhy


class DDRBaseTest(BaseTest, SnpsPhy):
    """Base class for implementing DDR tests."""
    logger = logging.getLogger(__name__)

    def __init__(self, config_data: ConfigData):
        """TODO:summary line."""
        super(DDRBaseTest, self).__init__(config_data)
        self.isMPU = not isinstance(config_data, ConfigDataMCU)
        if self.isMPU:
            self.__init_phy__(config_data)

    def _read_integer(self, address: int, size=4, swap=True) -> int:  # type: ignore
        """Override _read_integer from CwPhy.

        @param address: address to read from
        @param size: size in bytes of the value to be read
        @param swap: should the value be swapped
        @return: the int value or None if read operation failed
        """
        data = self.channel.read_data(address, size, 1)
        if data is None:
            return None  # type: ignore
        val = int(data, 16)
        return BufferedReader.swap32(val) if swap else val

    def read_logged_data(self):  # type: ignore
        """Read logs in BufferedReader and write them to log file."""
        # Read "num_logged_items" - offset hard-coded to 8 (3rd member of the structure)
        value = self.channel.read_symbol(self.app.get_result_symbol('num_logged_items'))
        num_logged_items = int(value) if value is not None else -1

        # Validate num_logged_items
        if num_logged_items < 0:
            logging.warning('Invalid number of logged items: %d', num_logged_items)
            return
        elif num_logged_items == 0:
            logging.info('No logged items to process')
            return
        elif num_logged_items > 10000:  # Adjust based on your system
            logging.warning('Suspiciously large number of logged items: %d', num_logged_items)
            # You might want to cap it or ask for confirmation

        # Use a buffered reader to speed-up reading from target in case of streaming messages
        log_start_address = (int(self.config_data.sys_params['log_addr_hi'], 16) << 32) | int(
            self.config_data.sys_params['log_addr_lo'], 16)

        log_limit_address = (int(self.config_data.sys_params['log_upper_addr_limit_hi'], 16) << 32) | int(
            self.config_data.sys_params['log_upper_addr_limit_lo'], 16)

        # Validate addresses
        if log_limit_address <= log_start_address:
            logging.error('Invalid log address range: start=0x%x, limit=0x%x',
                        log_start_address, log_limit_address)
            return

        br = BufferedReader(self.channel.read_data, log_start_address, log_limit_address)
        self.process_logged_messages(num_logged_items, br)

    def get_phy_init_status(self) -> bool:
        """Get PHY status.

        @return: True if PHY was successfully executed
        """
        response = self.channel.execute_command(cmd=ApplicationCommand.CALIBRATE_TARGET, data=None)
        if not response:
            self.logger.info('PHY initialization failed')

        value = self.channel.read_symbol(self.app.get_result_symbol('phy_status'))
        phy_init_status = int(value) if value is not None else -1

        self.read_logged_data()
        if phy_init_status > 0:
            if self.report_phy_error():
                # for CAEye phy errors should not be saved to results
                self.results['phy_error_state'] = str(phy_init_status)
            return False

        return True

    def phy_init_succeeded(self) -> bool:
        """Check if PHY initialization passed.

        @return: True if PHY init succeeded
        """
        if self.isMPU:
            return self.get_phy_init_status()
        return True

    def report_phy_error(self) -> bool:
        """Determine if the test should add info about encountered PHY error to the test results."""
        return True
