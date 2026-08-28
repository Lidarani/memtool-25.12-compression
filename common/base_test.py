# Copyright 2019-2025 NXP
"""TODO:summary line."""
import logging
import os
import re
import shutil
import sys
import time
import traceback
from datetime import datetime
from enum import Enum
from typing import Optional

from memtool.common.app import ApplicationCommand
from memtool.utils.constants import Const

from .config_data import ConfigData
from .config_data_mcu import ConfigDataMCU
from .factories import AppInterfaceFactory, BackendFactory, FactoryClass, ProcessorFactory
from .preferences import Preferences
from .scenarios import Scenario
from .workspace import Workspace


class TestStatus(Enum):
    """Test status."""
    FAIL = 0
    PASS = 1
    UNKNOWN = 2
    DS_INVALID = 3
    PARAMS_VALIDATED = 4
    APP_LOADED = 5
    APP_STARTED = 6
    CONFIG_RECEIVED = 7
    INPUT_RECEIVED = 8
    CONFIGURATION_ERROR = 9  # DDR configuration was not accepted by the DDR controller.
    TARGET_ERROR = 10  # Any kind of target access error.

    def __init__(self, state: int) -> None:
        """Constructor.

        @param state: state value
        """
        self._state = state

    @staticmethod
    def from_state_value(state_value: int) -> 'TestStatus':
        """Converts a state value into a TestStatus.

        @param state_value: state value to be converted
        @return: corresponding TestStatus element
        """
        for ts in TestStatus:
            if ts._state == state_value:
                return ts
        return TestStatus.UNKNOWN


class TestResults:
    """Test results class."""

    @staticmethod
    def save(save_results_dir_label: str) -> None:
        """It saves current test results from workspace.

        @param save_results_dir_label: Label used for naming save results directory,
        timestamp is appended to ensure unique save results directory name.
        """
        save_results = True
        logger = logging.getLogger(__name__)
        if save_results:
            workspace_dir = Workspace.get_instance().get_location()
            timestamp = re.sub(r':', '_', f'{datetime.now()}')
            save_results_dir_name = f'{timestamp}_{save_results_dir_label}'
            save_results_dir = os.path.join(workspace_dir, save_results_dir_name)
            if not os.path.exists(save_results_dir):
                os.mkdir(save_results_dir)
            else:
                logger.error(f'Save results failed because save directory {save_results_dir} already exists!')
                return
            for filename in os.listdir(workspace_dir):
                src_file = os.path.join(workspace_dir, filename)
                dst_file = os.path.join(save_results_dir, filename)
                if os.path.isfile(src_file):
                    shutil.copy(src_file, dst_file)

    @staticmethod
    def clear() -> None:
        """It clears current test results from workspace."""
        workspace_dir = Workspace.get_instance().get_location()
        workspace_specific_files = [Preferences.PREFERENCES_FILE_NAME]
        for filename in os.listdir(workspace_dir):
            src_file = os.path.join(workspace_dir, filename)
            if os.path.isfile(src_file) and filename not in workspace_specific_files:
                try:
                    os.remove(src_file)
                except PermissionError:
                    # Clear file that can not be deleted.
                    clear_file = open(src_file, 'w')
                    clear_file.close()


class BaseTest(metaclass=FactoryClass.RegistryMeta):
    """Base class for implementing memtests.

    Derived classes can customize behavior.
    The implementation uses generic backend and application interfaces to isolate test logic from
    underlying target connection choice and application specifics respectively.
    """

    logger = logging.getLogger(__name__)
    NAME = "BaseTest"

    @classmethod
    def matches(cls, name: str) -> bool:
        """Check if the test name matches the NAME attribute of the test class.

        @param name: test name
        @return: True if match, False otherwise
        """
        return hasattr(cls, 'NAME') and cls.NAME.lower() == name.lower()

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        self.logger = logging.getLogger(__name__)

        # Pre-process params - make sure relevant parameters are set
        self.config_data = config_data
        config_data.params['app']['test_params']['test'] = self.get_id()

        # instantiate and backend objects
        self.channel = BackendFactory.make_unique_instance(config_data.connect_params)

        # instantiate processor
        self.processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)

        # instantiate application
        self.opaque_custom_oei = bool(config_data.compress) and config_data.soc_name == 'MIMX95_B0'
        if self.opaque_custom_oei:
            self.app = None
            self.logger.info('Using opaque custom OEI mode; skipping the memtool test-application interface.')
        else:
            binary_file_path = self.processor.get_test_bin_file_name(config_data)
            binary_mdate = os.path.getmtime(binary_file_path)
            if self.processor.processor_info is not None:
                entry_point = self.processor.processor_info.get_app_entry_point(primary_image=True)
            else:
                entry_point = None
            self.app = AppInterfaceFactory.make_unique_instance(self.processor.get_app_type(),
                            binary_file_path, binary_mdate,
                            self.processor.get_app_symbol_names(primary_image=True),
                            entry_point)
            self.app.update_config_data(config_data)
            # update channel application member; for now, this is needed for simulator
            self.channel.set_application(self.app)

        # gather application results in a dictionary
        sys.stdout.flush()
        self.results = {}  # type: ignore

        # various flags for controlling test execution behavior
        self.run_to_completion = config_data.params['app'].get('single_result', True)
        self.timeout = config_data.params['app'].get('max_timeout', 0)
        self.ID: Optional[int] = None

    def switch_application(self, config_data: ConfigData):  # type: ignore
        """Switch application.

        @param config_data: configuration data
        """
        second_binary_file_path = self.processor.get_test_second_bin_file_name(config_data)
        if second_binary_file_path:
            binary_mdate = os.path.getmtime(second_binary_file_path)
            self.app = AppInterfaceFactory.make_unique_instance(self.processor.get_app_type(),
                            second_binary_file_path, binary_mdate,
                            self.processor.get_app_symbol_names(primary_image=False),
                            self.processor.processor_info.get_app_entry_point(primary_image=False))

            # update channel application member; for now, this is needed for simulator
            self.channel.set_application(self.app)

    @staticmethod
    def validate_parameters(config_data: ConfigData) -> TestStatus:
        """Check test parameters.

        @param config_data: target configuration data
        @return: test status after parameter validation
        """
        # Sanity check
        test_params = config_data.params
        required_keys = {'app', Const.PARAM_S_TC}
        missing_keys = required_keys - set(test_params.keys())
        if missing_keys:
            err_mgs = f'Incomplete parameters: missing {list(missing_keys)}!'
            BaseTest.logger.error(err_mgs)
            return TestStatus.FAIL

        # Identify the appropriate test class matching the name parameter against all registered test subclasses
        test_name = test_params['app']['name']

        test_cls = next(iter([cls for cls in BaseTest.registry.values() if cls.matches(test_name)]), None)
        if test_cls is None:
            err_mgs = f'No matching test class found for {test_name}!'
            BaseTest.logger.error(err_mgs)
            return TestStatus.FAIL

        return test_cls(config_data).validate_test_parameters()

    def validate_test_parameters(self) -> TestStatus:
        """Validate test specific parameters; nothing to do by default; if needed, each test should override this.

        @return: test status after parameter validation
        """
        return TestStatus.PARAMS_VALIDATED

    @staticmethod
    def get_scenario_cls(config_data: ConfigData):  # type: ignore
        """Identify scenario class; for now only CA scenario is available.

        @param config_data: configuration data
        @return: scenario class or None if scenario class could not be found
        """
        scenario_cls = None
        scenario_name = ''

        # scenario will be executed?
        if Const.PARAM_S_SCENARIO in config_data.params[Const.PARAM_S_APP]:
            scenario_name = config_data.params[Const.PARAM_S_APP][Const.PARAM_S_SCENARIO]
        if scenario_name:
            scenario_cls = next(iter([cls for cls in Scenario.registry.values() if cls.matches(scenario_name)]), None)
            if scenario_cls is None:
                BaseTest.logger.error('No matching scenario class found for %s!', scenario_name)
        return scenario_cls

    @staticmethod
    def get_test_cls_by_name(test_name: str):  # type: ignore
        """Identify test class.

        @param test_name: test name
        @return: test class or None if test class could not be found
        """
        test_cls = next(iter([cls for cls in BaseTest.registry.values() if cls.matches(test_name)]), None)
        if test_cls is None:
            BaseTest.logger.error('No matching test class found for %s!', test_name)
        return test_cls

    @staticmethod
    def get_test_cls(config_data: ConfigData):  # type: ignore
        """Identify test class.

        @param config_data: configuration data
        @return: test class or None if test class could not be found
        """
        test_params = config_data.params

        # Identify the appropriate test class matching the name parameter against all registered test subclasses
        test_name = test_params['app']['name']
        return BaseTest.get_test_cls_by_name(test_name)

    @staticmethod
    def run_test(test, config_data: ConfigData) -> TestStatus:  # type: ignore
        """Test runner method.

        @param test: test class to be executed
        @param config_data: target configuration data
        @return: test status
        """
        if test is None:
            BaseTest.logger.error("Uninitialized test can't be executed!")
            return TestStatus.FAIL

        # clear temp .json files containing results from previous test execution (e.g. ecc, vref)
        BaseTest.clear_temp_files(config_data)

        # Invoke the test
        return test.run()

    @classmethod
    def clear_temp_files(cls, config_data: ConfigData) -> None:
        """Clear files from old test execution.

        @param config_data: target configuration data
        """
        workspace_dir = Workspace.get_instance().get_location()
        # delete old ECC regions info
        if os.path.exists(Const.ecc_file_name):
            ecc_info_file = os.path.join(workspace_dir, Const.ecc_file_name)
            if os.path.exists(ecc_info_file):
                os.remove(ecc_info_file)

        # delete old vref info
        if (config_data.vref_info_file is not None) and os.path.exists(config_data.vref_info_file):
            os.remove(config_data.vref_info_file)

    def get_test_window_class_name(self) -> str:
        """Get UI class name."""
        return self.__name__ + 'Window'  # type: ignore

    def get_id(self) -> Optional[int]:
        """Getter for ID.

        @return: test ID
        """
        return self.ID

    def get_app_state(self) -> int:
        """Read the state of the application from target.

        @return: app state number
        """
        state_value = self.channel.read_symbol(self.app.get_result_symbol('app_state'))
        app_state = int(state_value) if state_value is not None else int(self.app.APP_STATES['UNKNOWN'])
        self.logger.info('Read app state %s', self.app.state_name(app_state))

        return app_state

    def is_waiting_for_input(self, wait_for_response: bool = True) -> bool:
        """Utility method to determine if application is waiting for parameters.

        @return: True if channel is alive and application is waiting for input
        """
        return self.channel.is_alive(wait_for_response)

    def is_alive(self, wait_for_response: bool = True) -> bool:
        """Utility method to determine if application is alive.

        @param wait_for_response: wait for prompt
        @return: True if channel is alive
        """
        return self.channel.is_alive(wait_for_response)

    def load_app(self, target_ready: bool) -> None:
        """Create and load dcd.bin.

        @param target_ready: target already waiting for input
        """
        if not target_ready:
            if not self.config_data.soc_name.startswith('MIMX9'):
                self.processor.create_dcd_bin(self.config_data)
            self.processor.load_app(self.config_data, self.use_system_manager())

    def load_dcd_and_app(self) -> TestStatus:
        """Load application and DCD which contains all input parameters.

        @return: test status after load dcd and app
        """
        try:
            # open serial channel and reset buffers before loading app/reset
            self.channel.init_channel(self.config_data)

            target_ready = self.is_alive(wait_for_response=False)
            if target_ready:
                self.channel.reset()
                target_ready = False

            # reduce SPSDK log - set log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            self.load_app(target_ready)
        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.error('Application load ended with exception: %s', str(ex))
            return TestStatus.FAIL
        finally:
            # restore log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

        return TestStatus.APP_LOADED

    def set_log_level(self) -> bool:
        """Set application log level."""
        app_log_level_symb = self.app.get_result_symbol('app_log_level')
        if app_log_level_symb is not None:
            return self.channel.write_symbol(app_log_level_symb, self.config_data.log_level)
        return True

    def execute_test(self) -> TestStatus:
        """Utility method to write test parameters to target and execute test.

        @return: test status
        """
        #Todo: find a place to load params that shouldn't be loaded in app[test_params] as they aren't delivered to the
        #board. E.g. trained data eye params that are only filters for the phy init result (direction, byte, bit, cs).
        excluded_params = ["direction", "byte", "bit", "cs"]
        for (k, v) in self.config_data.params['app']['test_params'].items():
            if k in excluded_params:
                continue
            if v is not None:
                symbol = self.app.get_param_symbol(k)
                if symbol is not None:
                    if not self.channel.write_symbol(symbol, v):
                        self.logger.error('Input parameter %s could not be set to %s', k, v)
                        return TestStatus.FAIL

                    # make sure current parameter was written before writing the next one
                    time.sleep(0.1)
                else:
                    self.logger.warning('Symbol for input parameter %s is not available', k)
            else:
                self.logger.warning('Parameter %s value is None', k)

        # In case of run 'forever' timeout will be set to -1
        if self.config_data.params['app'].get('test_params', {}).get('forever', False):
            result = self.channel.execute_command(cmd=ApplicationCommand.EXECUTE_TEST,
                                                  data=None, timeout=-1)
        else:
            result = self.channel.execute_command(cmd=ApplicationCommand.EXECUTE_TEST, data=None)
        return TestStatus.PASS if result else TestStatus.FAIL

    def wait_app_finish(self, count) -> bool:  # type: ignore
        """Wait for app to finish.

        @param count: number of seconds we'll wait for the application to reach WAIT_FOR_INPUT state
        @return: True if application is in WAIT_FOR_INPUT state
        """
        cnt = int(count)
        if cnt == 0:
            return True

        while cnt > 0:
            if self.is_waiting_for_input():
                return True
            time.sleep(1)
            cnt = cnt - 1

        return False

    @staticmethod
    def test_state(test_state: int = 0) -> TestStatus:
        """Translate test result to the corresponding TestStatus.

        @param test_state: test state code
        @return: test state
        """
        if test_state == 1:
            return TestStatus.PASS
        if test_state == 0:
            return TestStatus.FAIL
        return TestStatus.UNKNOWN

    def read_results(self) -> TestStatus:
        """Utility method to gather results from target into internal state.

        Use get_results to retrieve the results

        @return: test status after reading test results
        """
        self.results['app_state'] = -1
        self.results['num_records'] = -1
        self.results['records'] = []
        self.results['debug'] = ''
        self.results['err_capt_regs'] = ''
        self.results['debug_regs'] = ''

        # needed for LX2
        if not self.wait_app_finish(self.config_data.connect_params.get('count_us_app_finish', 1)):
            self.logger.error('Application is not waiting for input state.')
            return TestStatus.FAIL

        # simple values
        for s in ('app_state', 'num_records'):
            value = self.channel.read_symbol(self.app.get_result_symbol(s))
            self.results[s] = int(value) if value is not None else -1
            # self.logger.info('Read symbol %s = 0x%x', s, self.results[s])

        # lists
        for s in ('debug', 'err_capt_regs', 'debug_regs'):
            value = self.channel.read_symbol(self.app.get_result_symbol(s))
            self.results[s] = value if value is not None else -1

        # test_results
        num_tests = self.results['num_records']
        self.results['records'] = []
        num_passed_tests = 0
        for r in range(num_tests):
            record = {}
            for f in ('state', 'test_id'):
                value = self.channel.read_symbol(self.app.get_test_result_symbol(r, f))
                record[f] = value if value is not None else -1

            value = self.channel.read_symbol(self.app.get_test_result_symbol(r, 'data'))
            record['data'] = value if value is not None else -1

            self.results['records'].append(record)
            test_state = self.test_state(int(record['state']))
            num_passed_tests += 1 if test_state == TestStatus.PASS else 0

        return TestStatus.PASS if (num_tests == num_passed_tests and num_passed_tests != 0) else TestStatus.FAIL

    def get_results(self) -> dict:
        """Getter for the currently collected results."""
        return self.results

    def process_results(self) -> None:
        """Additional processing and output logic that can be performed on the results."""
        records = self.results['records']

        # Flush std.in to avoid mixed output from logger and stdin
        sys.stdout.flush()
        self.logger.debug('Err_caption_registers: %s', self.results['err_capt_regs'])
        self.logger.debug('Debug: %s', self.results['debug'])
        self.logger.debug('Debug registers: %s', self.results['debug_regs'])
        self.logger.debug('Results: %s', records)
        self.logger.debug('Number of records: %d', self.results['num_records'])

        results = self.get_results()
        if results:
            print(results)

    def use_system_manager(self) -> bool:
        """Check if System Manager is used.

        If processor is SM controlled, SM image should be imported in the final image.
        Tests that need SM to enable access to target resources should override this method.

        @return: False  #  by default, tests will not use SM
        """
        return False

    def phy_init_succeeded(self) -> bool:
        """Check if PHY initialization passed.

        @return: True if PHY init succeeded
        """
        return True

    def run_app(self) -> TestStatus:
        """Execute test application based on configuration (strategy, timeouts).

        Can accommodate run-to-completion or continuous-monitoring

        @return: test status after executing the test
        """
        self.processor.execute(self.config_data)
        # TODO: wait notification from target
        time.sleep(7)

        if not self.opaque_custom_oei and not self.is_waiting_for_input():
                self.logger.error('Applicationsp is not waiting for input state.')
                return TestStatus.FAIL

        return TestStatus.APP_STARTED

    def run(self) -> TestStatus:
        """Main test execution routine.

        The implementation dispatches to specific methods for each stage to allow customization in derived classes

        @return: test result
        """
        if self.opaque_custom_oei:
            # The custom OEI has no memtool test-application interface (self.app is None),
            # so none of the symbol-based steps below (set_log_level, execute_test,
            # read_results) can run. Just load and start the image; the DDR initialization
            # progress can only be observed on the OEI UART console.
            try:
                test_status = self.load_dcd_and_app()
                if test_status != TestStatus.APP_LOADED:
                    return test_status

                test_status = self.run_app()
                if test_status == TestStatus.APP_STARTED:
                    self.logger.info('Custom OEI started; check the OEI UART console for the DDR initialization result.')
                    return TestStatus.PASS

                self.logger.error('Custom OEI could not be started on target.')
                return TestStatus.TARGET_ERROR
            except Exception as ex:
                if self.logger.getEffectiveLevel() == logging.DEBUG:
                    self.logger.debug('Error traceback:')
                    traceback.print_exc()
                self.logger.exception('Run test ended with exception: %s', str(ex))
                return TestStatus.FAIL
            finally:
                self.close_channel()

        is_mpu = not isinstance(self.config_data, ConfigDataMCU)
        test_status = TestStatus.UNKNOWN
        try:
            # load app and DCD if necessary (only on the 1st executed test)
            test_status = self.load_dcd_and_app()

            # execute
            if is_mpu and TestStatus.APP_LOADED == test_status:
                test_status = self.run_app()

            if is_mpu:
                app_started = TestStatus.APP_STARTED == test_status

                if self.config_data.params['app'].get('check_target_is_responsive', False):
                    return TestStatus.PASS if app_started else TestStatus.FAIL

                if not app_started and not self.use_system_manager():
                    return TestStatus.TARGET_ERROR

            # set log level
            if is_mpu and not self.set_log_level():
                if not self.use_system_manager():
                    return TestStatus.TARGET_ERROR

            # check if PHY passed
            if is_mpu and not self.phy_init_succeeded():
                return TestStatus.CONFIGURATION_ERROR

            # Switch to the next application if needed and second application is found
            if self.use_system_manager():
                self.switch_application(self.config_data)

            # write test parameters from test.json
            test_status = self.execute_test()

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('Run test ended with exception: %s', str(ex))
            return TestStatus.FAIL

        finally:
            # read and process results (should be done even if the test failed;
            # printed results are used by Config Tool to determine the failure type)
            test_status = self.read_results()
            self.process_results()

            self.close_channel()

        return test_status

    def close_channel(self):  # type: ignore
        """Close communication channels(s) used by the test."""
        logging.shutdown()
        self.channel.close()

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Clear test params, set test name and set reset.

        @param config_data: processor config data
        """
        config_data.connect_params['reset'] = True
        config_data.params[Const.PARAM_S_APP]['name'] = cls.NAME
        config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS] = {}

        # Set test number to 0 to inform application that no diagnostic test should be executed.
        # Diagnostic tests should set this parameter to the right value.
        config_data.diags_params['diag_test'] = Const.NO_DIAG_TEST

    @classmethod
    def restore_config_params(cls, config_data: ConfigData):  # type: ignore
        """In case test needs to update PHY/DDR configuration parameters, they must be restored when the test ends.

        This is not needed from Config Tools
        because each test is executed individually and starts with the user configuration
        @param config_data: processor config data
        """
        pass

    @classmethod
    def available(cls, processor: str = '') -> bool:
        """Overwritten by specific test implementations if needed.

        @param processor: processor type
        @return: if processor is of the required type for the test to be run on it
        """
        return True

    @classmethod
    def run_only_as_scenario(cls) -> bool:
        """Test should be run only as scenario test."""
        return False

    @classmethod
    def data_eye_is_generated(cls) -> bool:
        """Data Eye is generated using test results."""
        return False
