# Copyright 2019-2025 NXP
"""Classes corresponding to various MCU flash memory tests."""
import logging
import traceback

from memtool.common.base_test import BaseTest, TestStatus
from memtool.common.config_data import ConfigData


class FcbMemoryTest(BaseTest):
    """Base class for memory configuration tests."""


class FlexSpiMemoryTest(FcbMemoryTest):
    """Class implementing FlexSpiMemoryTest Test."""

    def process_results(self):  # type: ignore
        """Parse results records to extract the value read."""
        super().process_results()
        if len(self.results['records']) > 0:
            if '420' in self.results['records'][0]['data']:
                res = self.results['records'][0]['data'].split(',')
                self.logger.error('Sequence number %s does not exist in LUT table', res[1])


class WriteFlashTest(FcbMemoryTest):
    """Class implementing WriteFlashTest Test."""

    ID = 300
    NAME = 'Write Flash Test'


class FcbProgramTest(FcbMemoryTest):
    """Class implementing FcbProgramTest Test."""

    ID = 301
    NAME = 'Write and Test Flash Image'


class CheckBootTest(FcbMemoryTest):
    """Class implementing CheckBootTest Test."""

    ID = 303
    NAME = 'Check Boot Test'

    def read_results(self) -> TestStatus:
        """Override read_results from base_test which is checking that app is in waiting_for_input state.

        Nothing to read.
        """
        return TestStatus.from_state_value(self.results['records'][0]['state'])

    def get_app_state(self) -> int:
        """Override get_app_state for CheckBootTest.

        Reads symbol without printing error in case symbol not found
        @return: app state number
        """
        state_value = self.channel.read_symbol_silent(self.app.get_result_symbol('app_state'))
        app_state = int(state_value) if state_value is not None else int(self.app.APP_STATES['UNKNOWN'])
        return app_state

    def load_dcd_and_app(self) -> TestStatus:
        """Load application and DCD which contains all input parameters.

        @return: test status after load dcd and app
        """
        try:
            # open serial channel and reset buffers before loading app/reset
            self.channel.init_channel()
            app_state = self.app.APP_STATES['UNKNOWN']
            target_ready = self.is_alive(wait_for_response=False)
            if target_ready:
                app_state = self.get_app_state()
            self.results['records'] = []
            self.results['num_records'] = 0
            self.results['app_state'] = 0x11223344
            self.results['err_capt_regs'] = 0
            self.results['debug'] = 0
            self.results['debug_regs'] = 0
            if target_ready and (app_state == self.app.APP_STATES['UNKNOWN']):
                # app_state is UNKNOWN => app is not running, so the board is not in Serial Downloader
                record = {'test_id': 303, 'state': 1}
                self.results['records'].append(record)
                self.logger.info('Target booted successfully. FCB header is correct')
                return TestStatus.PASS
            elif target_ready and (app_state == self.app.APP_STATES['WAIT_FOR_INPUT']):
                # app_state is WAIT_FOR_INPUT => board is in Serial Downloader
                self.logger.error('Make sure the board is in Internal Flash mode')
                self.logger.error('It seems the board is set in Serial Downloader Mode')
                record = {'test_id': 303, 'state': 0}
                self.results['records'].append(record)
                return TestStatus.FAIL
            else:
                # serial channel not present - target did not boot.
                # 2 possible reasons: FCB header not correct, or no image was flashed
                self.logger.error('Make sure the test "Program flash image" is executed before this test')
                self.logger.error('Make sure FCB header is correctly configured'
                                  ' according to flash device existing on the target')
                record = {'test_id': 303, 'state': 0}
                self.results['records'].append(record)
                return TestStatus.FAIL
        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('Load application ended with exception: %s', str(ex))
            return TestStatus.FAIL


class FlexSpiTransactionBlocking(FlexSpiMemoryTest):
    """Class implementing FlexSpi Transaction Blocking Test."""

    ID = 304
    NAME = 'FlexSpi Transaction Blocking'


class UserCustomTest(FlexSpiMemoryTest):
    """Class implementing FlexSpi Transaction Blocking Test."""

    ID = 305
    NAME = 'CustomTest'


class NorFlashInit(FlexSpiMemoryTest):
    """Class implementing NorFlashInit Test."""

    ID = 200
    NAME = 'Nor Flash Init'


class GetVendorId(FlexSpiMemoryTest):
    """Class implementing GetVendorId Test."""

    ID = 201
    NAME = 'Read Vendor ID'

    def read_results(self) -> TestStatus:
        """Parse results records to extract the value read."""
        test_state = super().read_results()
        res = self.results['records'][0]['data'].split(',')
        vendor = res[1]
        self.logger.info('Vendor ID is: %s', vendor)
        if int(vendor) in [0, 1, 255]:
            self.logger.error('Vendor ID is incorrect: %s', vendor)
            record = {'test_id': 201, 'state': 0}
            self.results['records'].append(record)
            test_state = TestStatus.FAIL

        return test_state


class EraseChip(FlexSpiMemoryTest):
    """Class implementing EraseChip Test."""

    ID = 202
    NAME = 'Erase chip'


class EraseSector(FlexSpiMemoryTest):
    """Class implementing EraseSector Test."""

    ID = 203
    NAME = 'Erase Sector'


class NORProgram(FlexSpiMemoryTest):
    """Class implementing NORProgram Test."""

    ID = 204
    NAME = 'Program NOR'


class NORRead(FlexSpiMemoryTest):
    """Class implementing NORRead Test."""

    ID = 205
    NAME = 'Read NOR'

    def read_results(self) -> TestStatus:
        """Parse results records to extract the value read."""
        test_state = super().read_results()
        res = self.results['records'][0]['data'].split(',')
        self.logger.info('Read from NOR address %s data: 0x%x',
                         self.config_data.params['app']['test_params']['start_addr'], int(res[1]))

        return test_state
