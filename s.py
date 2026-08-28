# Copyright 2019-2025 NXP

"""TODO:summary line."""
import logging
import os
import traceback

import memtool
import memtool.processor
from memtool.common.base_test import BaseTest, TestStatus
from memtool.common.config_data import ConfigData
from memtool.common.config_data_mcu import ConfigDataMCU
from memtool.common.factories import ProcessorFactory
from memtool.common.workspace import Workspace
from memtool.phyinit.phy_init import PHYInitDriver
from memtool.utils.constants import Const
from memtool.utils.helper import add_file_to_params


def run_test(_log: str, _files: list, _app_log_file, _phy_log_file: str,  # type: ignore
             _figure_file: str, _vref_info_file: str,
             _data_dir: str, _sm_bin_file: str, _compress: bool = False):
    """Execute test (script called from Config Tools).

    @param _log: log level
    @param _files: list of json files containing configuration parameters
    @param _app_log_file: path to application log
    @param _phy_log_file: path to PHY log
    @param _figure_file: path to figure file
    @param _vref_info_file: path to vref info file
    @param _data_dir: processor data folder
    @param _sm_bin_file: path to the system manager binary
    @return: TestStatus
    """
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(format="%(levelname)-8s %(name)s %(message)s", level=getattr(logging, _log))

    logger = logging.getLogger(__name__)

    params = {}  # type: ignore
    fw_dir = ""
    for file in _files:
        fw_dir = os.path.dirname(os.path.abspath(file.name))
        params = add_file_to_params(file.name, params)

    if ("processor_type" in params["connect"]) and (params["connect"]["processor_type"] == "MCU"):
        config_data = ConfigDataMCU(_data_dir, params)
    else:
        config_data = ConfigData(_data_dir, params)  # type: ignore

    config_data.app_log_file = _app_log_file
    config_data.log_level = getattr(logging, _log)
    config_data.log_file = _phy_log_file
    config_data.figure_file = _figure_file
    config_data.vref_info_file = _vref_info_file
    config_data.sm_file = _sm_bin_file
    config_data.compress = _compress
    logger.debug("Compression flag from CLI: %s", config_data.compress)

    Workspace.get_instance().set_location(fw_dir)
    if not Workspace.get_instance().is_valid_location():
        logger.error(f"Invalid workspace location: {fw_dir}")
        return

    # Call Synopsys phy init
    old_dir = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        # get test to be executed
        test_cls = BaseTest.get_test_cls(config_data)
        if test_cls is None:
            return TestStatus.FAIL

        # verify if a scenario needs to be executed
        scenario_log_file = None
        scenario = None
        scenario_cls = BaseTest.get_scenario_cls(config_data)
        if scenario_cls is not None:
            if scenario_cls.get_test_name() != test_cls.NAME:
                return TestStatus.FAIL

            scenario_log_file = config_data.log_file
            scenario = scenario_cls()
            scenario.reset(config_data)

        test_status = TestStatus.PASS
        crt_iteration = 0
        no_iterations = scenario.get_number_of_cells() if scenario is not None else 1
        while crt_iteration < no_iterations:
            if scenario is not None:
                workspace_dir = Workspace.get_instance().get_location()
                config_data.log_file = os.path.join(
                    workspace_dir, f"{crt_iteration}_phy_training.log"
                )  # log for current iteration
                if os.path.exists(config_data.log_file):  # each test has to start with clean phy log
                    open(config_data.log_file, "w").close()
                scenario.update_cell_params(config_data, crt_iteration)

            # save configuration parameters and apply test specific parameters
            test_cls.update_config_params(config_data)

            # run RPA
            processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
            # skip pre_test_updates for serdes
            if Const.PARAM_SERDES_SKIP_DDR_PHY in config_data.params[Const.PARAM_S_BASIC]:
                test_status = TestStatus.PARAMS_VALIDATED
            else:
                test_status = processor.pre_test_updates(config_data)

            # run test
            if TestStatus.PARAMS_VALIDATED == test_status:
                test = test_cls(config_data)
                test_status = BaseTest.run_test(test, config_data)
                if scenario is not None:
                    scenario.store_test_result(test)

            # go to the next iteration
            crt_iteration += 1

            # keep log from current iteration
            if scenario_log_file is not None:
                with open(scenario_log_file, "at", encoding="utf-8") as s:
                    with open(config_data.log_file, "rt", encoding="utf-8") as t:
                        s.write(
                            f"\nScenario {scenario_cls.NAME} - Test {test_cls.NAME}" f" - Iteration {crt_iteration}\n\n"
                        )
                        s.write(t.read())
                    os.remove(config_data.log_file)

            # restore previously saved parameters
            test_cls.restore_config_params(config_data)

        if scenario is not None:
            scenario.process_results(config_data)
    except Exception:
        if logger.getEffectiveLevel() == logging.DEBUG:
            logger.exception("Application error:")
            traceback.print_exc()
        else:
            logger.error("An error occurred while running tests, set log level to DEBUG for more details.")
    finally:
        print(Const.DONE_MARKER)  # Notify Eclipse plugin that test was done
        os.chdir(old_dir)
