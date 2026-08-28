# Copyright 2020-2025 NXP
"""Classes implementing Phy Diags tests and eye data parsing."""
import ast
import json
import logging
import math
import os
import re
import struct
import time
import traceback
from copy import deepcopy
from enum import Enum
from typing import Dict, Optional, Tuple, Union

import numpy as np
from bs4 import BeautifulSoup
from matplotlib import font_manager as fm
from matplotlib import pyplot as plt
from matplotlib.colors import ListedColormap, hex2color
from matplotlib.lines import Line2D

from memtool.common.config_data import ConfigData
from memtool.common.workspace import Workspace
from memtool.phyinit.phy_init import PHYInitDriver
from memtool.utils.constants import Const

from ..common.base_test import TestStatus
from ..common.factories import ProcessorFactory
from ..common.options import Options
from ..utils.helper import str_to_int
from .eye_figure import CABusEyeFigure, DiagEyeFigure
from .phy_test import DDRBaseTest
from .snps_phy import SnpsPhy


class PhyTrainingTest(DDRBaseTest):
    """Parent class for implementing Phy Training Tests."""

    logger = logging.getLogger(__name__)

    ID = 200

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        super(PhyTrainingTest, self).__init__(config_data)
        phy_input_basic = config_data.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]
        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            config_data.update_sys_params(Const.PARAM_S_SYS_NUM_DBYTE, phy_input_basic[Const.PARAM_S_PHY_NUM_DBYTE])
        else:
            num_ranks_val0 = num_ranks_val1 = 0
            if Const.PARAM_S_PHY_NUM_RANK_DFI0 in phy_input_basic:
                num_ranks_str = phy_input_basic[Const.PARAM_S_PHY_NUM_RANK_DFI0]
                num_ranks_val0 = int(num_ranks_str, 16)
            if Const.PARAM_S_PHY_NUM_RANK_DFI1 in phy_input_basic:
                num_ranks_str = phy_input_basic[Const.PARAM_S_PHY_NUM_RANK_DFI1]
                num_ranks_val1 = int(num_ranks_str, 16)
            config_data.update_sys_params(Const.PARAM_S_SYS_NUM_DBYTE, str(num_ranks_val0 + num_ranks_val1))

    def use_system_manager(self) -> bool:
        """Check if System Manager (SM) should be used for building PHY Diags test application.

        @return: False because PHY tests are always run without SM.
        """
        return False


class DiagnosticTest(PhyTrainingTest):
    """Parent class for implementing Diagnostic Tests."""

    # Copy of diagnostic parameters at the time of store configuration parameters.
    __diags_params_copy: Dict[str, str] = {}

    def load_app(self, target_ready: bool) -> None:
        """Create and load dcd.bin.

        @param target_ready: target already waiting for input
        """
        # add diags data; this must be executed before calling load_app from parent to ensure that diags data reach dcd
        diags_data_dir = os.path.join(self.config_data.data_dir, 'firmware', self.config_data.snps_phy_info.name,
                                      'diagnostic', self.config_data.mem_type)

        self.config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH] = \
            os.path.join(os.path.abspath(diags_data_dir),
                         SnpsPhy.get_data_file(mem_type=self.config_data.mem_type, op_type="diags", data_type="dmem"))
        self.config_data.sys_params[Const.DIAGS_DMEM_SIZE] = \
            os.path.getsize(self.config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH])

        self.config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH] = \
            os.path.join(os.path.abspath(diags_data_dir),
                         SnpsPhy.get_data_file(mem_type=self.config_data.mem_type, op_type="diags", data_type="imem"))
        self.config_data.sys_params[Const.DIAGS_IMEM_SIZE] = \
            os.path.getsize(self.config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH])

        super(DiagnosticTest, self).load_app(target_ready)

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(DiagnosticTest, cls).update_config_params(config_data)

        # set function to run full training,
        # then config_data.diags_params['diag_test'] will indicate that diagnostic fw must be executed
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT)

    @classmethod
    def store_config_params(cls, config_data: ConfigData) -> None:
        """Store configuration parameters.

        @param config_data: Configuration data.
        """
        # Copy diags parameters to restore then after test run.
        DiagnosticTest.__diags_params_copy = deepcopy(config_data.diags_params)

    @classmethod
    def restore_config_params(cls, config_data: ConfigData) -> None:
        """Restore configuration parameters.

        @param config_data: Configuration data.
        """
        # Restore diags parameters.
        config_data.diags_params = DiagnosticTest.__diags_params_copy

    @classmethod
    def clear_diags_params(cls, config_data: ConfigData) -> None:
        """Clear diagnostic parameters from configuration data.

        @param config_data: Configuration data.
        """
        for key in config_data.diags_params:
            config_data.diags_params[key] = '0'

    def process_results(self) -> None:
        """Process results specific for DiagnosticTest."""
        super(DiagnosticTest, self).process_results()

        self.config_data.fw_bin_info.pop(Const.DIAGS_DMEM_FILE_PATH)
        self.config_data.sys_params[Const.DIAGS_DMEM_SIZE] = 0
        self.config_data.fw_bin_info.pop(Const.DIAGS_IMEM_FILE_PATH)
        self.config_data.sys_params[Const.DIAGS_IMEM_SIZE] = 0


class SendBurstWritesTest(DiagnosticTest):
    """Class implementing Send Burst Writes Test."""
    NAME = 'Send Burst Writes'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from DiagnosticTest."""
        super(SendBurstWritesTest, cls).update_config_params(config_data)

        # Set test number to Send Burst Writes test.
        config_data.diags_params['diag_test'] = Const.SEND_BURST_WRITES_TEST


class SendBurstReadsTest(DiagnosticTest):
    """Class implementing Send Burst Reads Test."""
    NAME = 'Send Burst Reads'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from DiagnosticTest."""
        super(SendBurstReadsTest, cls).update_config_params(config_data)

        # Set test number to Send Burst Reads test.
        config_data.diags_params['diag_test'] = Const.SEND_BURST_READS_TEST


class SimpleWriteReadTest(DiagnosticTest):
    """Class implementing Simple Write Read Test."""
    NAME = 'Simple Write Read'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from DiagnosticTest."""
        super(SimpleWriteReadTest, cls).update_config_params(config_data)

        # Set test number to Simple Write Read test.
        config_data.diags_params['diag_test'] = Const.SIMPLE_WRITE_READ_TEST


class MRWriteTest(DiagnosticTest):
    """Class implementing Mode Register Write Test."""
    NAME = 'Mode Register Write'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from DiagnosticTest."""
        super(MRWriteTest, cls).update_config_params(config_data)

        # Set test number to Mode Register Write test.
        config_data.diags_params['diag_test'] = Const.MR_WRITE_TEST


class MRReadTest(DiagnosticTest):
    """Class implementing Mode Register Read Test."""
    NAME = 'Mode Register Read'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from DiagnosticTest."""
        super(MRReadTest, cls).update_config_params(config_data)

        # Set test number to Mode Register Read test.
        config_data.diags_params['diag_test'] = Const.MR_READ_TEST


class VTSATest(DiagnosticTest):
    """Parent class for implementing VTSA Diagnostic Tests."""

    # For quick boot 2D training should not be executed
    Train2DDisabled = '0'
    initial_train_2d = None

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        super(VTSATest, self).__init__(config_data)
        self.eye_list = []  # type: ignore

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(VTSATest, cls).update_config_params(config_data)

        if Options.get_instance().get_snps_phy_boot_options().quick_boot():
            current_processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
            if current_processor.processor_info.can_run_diags_after_quickboot():
                # set function to quick boot
                config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_QUICK_BOOT)

                # do not execute 2D training; note that this will be passed to the application through dcd.bin
                VTSATest.initial_train_2d = config_data.train_2d
                # this must be set also in overwrite_params because it will be overwritten at import ds
                config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS] \
                    [Const.PARAM_S_SYS_TRAIN_2D] = VTSATest.Train2DDisabled
            else:
                cls.logger.debug("Diagnostic tests can not be executed after Quick Boot on current processor; "
                                 "full PHY initialization will be executed!")

        # set result file for diag output based on image figure file
        figure_file = config_data.figure_file
        if figure_file is not None:
            figure_file_name, figure_file_extension = os.path.splitext(config_data.figure_file)
            config_data.params[Const.PARAM_S_TC][Const.PARAM_S_TC_DIAGS_RESULT_FILE] = figure_file_name + ".txt"

    @classmethod
    def restore_config_params(cls, config_data: ConfigData):  # type: ignore
        """Restore parameters."""
        if Options.get_instance().get_snps_phy_boot_options().quick_boot():
            current_processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
            if current_processor.processor_info.can_run_diags_after_quickboot():
                # restore 2D training status
                config_data.train_2d = VTSATest.initial_train_2d  # type: ignore

    def validate_test_parameters(self) -> TestStatus:
        """Validate test specific parameters.

        @return: test status after parameter validation
        """
        bit_lane = int(self.config_data.diags_params['diag_lane'], 16)
        if not self.config_data.dbi_enabled and bit_lane == 8:
            self.logger.error(f'Error: Bit lane value {bit_lane} is not valid. DBI is disabled!')
            return TestStatus.FAIL

        return TestStatus.PARAMS_VALIDATED

    @classmethod
    def data_eye_is_generated(cls) -> bool:
        """Data Eye is generated using test results."""
        return True

    def read_results(self) -> TestStatus:
        """Override read_results from PhyTrainingTest.

        @return: test status after reading test results
        """
        result = super(VTSATest, self).read_results()

        # If PHY succeeded, diagnostics data can be read
        self._read_diag_result()

        return result

    def _read_diag_result(self) -> None:
        """Collect diagnostics data after running diagnostics firmware."""
        # if self.config_data.sys_params[Const.PARAM_S_SYS_FUNCTION] != str(PhyOperation.OP_RUN_DIAG):
        #     return

        # Read first part of the diagnostics data
        diag_out_addr = (int(self.config_data.diags_params['diag_out_addr_hi'], 16) << 32) | int(
            self.config_data.diags_params['diag_out_addr_lo'], 16)

        swap_data = self.config_data.params.get("swap_data", False)
        global_data = self._read_integer(diag_out_addr, swap=swap_data)
        total_size = self._read_integer(diag_out_addr + 4, swap=not swap_data)
        if global_data is None or total_size is None:
            return

        # Read the diagnostics result
        data = self.channel.read_data(diag_out_addr + 8, 1, total_size)
        self.process_diag_result(global_data, data)

    def process_results(self) -> None:
        """Process results specific for VTSATest."""
        super(VTSATest, self).process_results()

        file_path = self.config_data.params[Const.PARAM_S_TC].get(Const.PARAM_S_TC_DIAGS_RESULT_FILE, None)
        if file_path is not None:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                img_file_path = self.config_data.figure_file
                self.eye_list = EyeData.compute_eye_list(file_path)

                figure = EyeData.show_diag_data_eyes_plots(self.eye_list, self.config_data)
                figure.savefig(img_file_path)
                self.config_data.params[Const.PARAM_S_TC]['diag_image_file'] = img_file_path

                overlay_file_path = self.config_data.params[Const.PARAM_S_TC].get(
                                                                Const.PARAM_DIAG_OVERLAY_FILE, None)
                if overlay_file_path:
                    overlay_data = EyeData.compute_overlay_eyes(self.eye_list)
                    self.save_overlay_data_eyes(overlay_data, overlay_file_path)

    def save_overlay_data_eyes(self, overlay_data: list, overlay_file_path: str) -> None:
        """Generate html containing overlapping eyes."""
        try:
            overlay_html_content = ""
            overlay_template_path = os.path.join(self.config_data.data_dir, Const.TEMPLATES_DIR_NAME,
                                                 Const.TEMPLATE_DIAG_OVERLAY_FILE_NAME)
            with open(overlay_template_path) as template_file:
                template_content = template_file.read().strip()
                template_data = BeautifulSoup(template_content, 'html.parser')

                script_tag = template_data.find_all('script')[0]
                new_script_content = ''
                for script_line in script_tag.string.splitlines():
                    if '$LINECHART_DATA$' in script_line:
                        new_script_content = f'{new_script_content}\nconst linechartExportedData={overlay_data}'
                    else:
                        new_script_content = f'{new_script_content}\n{script_line}'
                new_script_tag = template_data.new_tag('script')
                new_script_tag.string = new_script_content
                script_tag.replace_with(new_script_tag)

                header_tag = template_data.findChild("h1")
                new_header_content = ''
                for header_line in header_tag.string.splitlines():
                    if '$SEL_SCEN_NAME$' in header_line:
                        new_header_content = f'{new_header_content}\n{self.NAME}'
                    else:
                        new_header_content = f'{new_header_content}\n{header_line}'
                new_header_tag = template_data.new_tag('h1')
                new_header_tag.string = new_header_content
                header_tag.replace_with(new_header_tag)

                overlay_html_content = template_data.prettify()
        except Exception as ex:
            self.logger.exception('Failed to generate diagnostic overlay html: %s', str(ex))
        finally:
            with open(overlay_file_path, "wt", encoding="utf-8") as overlay_file:
                overlay_file.write(overlay_html_content)

    @staticmethod
    def save_data_eyes_comparison_overlay(overlay_data: list, data_dir: str) -> str:
        """Generate html containing overlapping eyes for comparison between files in a non ConfigData dependant way."""
        err_msgs = []
        workspace_dir = Workspace.get_instance().get_location()

        def _write_comparison_file(template: str, filename: str) -> None:
            """Generate the html for a specific type of chart."""
            overlay_template_path = os.path.join(data_dir, Const.TEMPLATES_DIR_NAME, template)
            overlay_file_path = os.path.join(workspace_dir, filename)
            overlay_html_content = ''
            try:
                with open(overlay_template_path) as template_file:
                    template_content = template_file.read().strip()
                    template_data = BeautifulSoup(template_content, 'html.parser')

                    script_tag = template_data.find_all('script')[0]
                    new_script_content = ''
                    for script_line in script_tag.string.splitlines():
                        if '$LINECHART_DATA$' in script_line:
                            new_script_content = f'{new_script_content}\nconst linechartExportedData={overlay_data}'
                        else:
                            new_script_content = f'{new_script_content}\n{script_line}'
                    new_script_tag = template_data.new_tag('script')
                    new_script_tag.string = new_script_content
                    script_tag.replace_with(new_script_tag)

                    overlay_html_content = template_data.prettify()
            except Exception as ex:
                err_msgs.append(str(ex))
            finally:
                with open(overlay_file_path, 'wt', encoding='utf-8') as overlay_file:
                    overlay_file.write(overlay_html_content)

        _write_comparison_file(Const.TEMPLATE_EYE_COMPARE_SINGLE_CHART_FILE_NAME,
                               Const.EYE_COMPARE_SINGLE_CHART_FILE_NAME)

        _write_comparison_file(Const.TEMPLATE_EYE_COMPARE_DQ_TO_DQ_FILE_NAME,
                               Const.DIAG_OVERLAY_DQ_TO_DQ_FILE_NAME)

        return '' if len(err_msgs) == 0 else '\n'.join(err_msgs)

    def save_diags_comparison(self, overlay_data: list) -> None:
        """Generate html containing overlapping eyes for comparison between files."""
        err_msg = self.save_data_eyes_comparison_overlay(overlay_data, self.config_data.data_dir)
        if len(err_msg) > 0:
            self.logger.exception('Failed to generate diagnostic comparison html: %s', err_msg)


class DiagTxEye(VTSATest):
    """Class implementing Diag Tx Eye Test."""

    NAME = 'Diag Tx Eye'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from VTSATest."""
        super(DiagTxEye, cls).update_config_params(config_data)

        # set test to TX data eye
        config_data.diags_params['diag_test'] = Const.TX_EYE_TEST


class DiagRxEye(VTSATest):
    """Class implementing Diag Rx Eye Test."""

    NAME = 'Diag Rx Eye'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from VTSATest."""
        super(DiagRxEye, cls).update_config_params(config_data)

        # set test to RX data eye
        config_data.diags_params['diag_test'] = Const.RX_EYE_TEST


class VrefDQOptimizer(PhyTrainingTest):
    """Class implementing Vref for DQ Test."""

    NAME = 'Vref for DQ Optimizer'
    ID = 201
    NumPstates = 1

    # VrefDQOptimizer must be executed for a single pstate, so we have to restore it at the end of test
    initial_num_pstates = None

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        super(VrefDQOptimizer, self).__init__(config_data)

        self.is_phy_v2 = ConfigData.is_phy_v2(config_data.snps_phy_info)

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from VTSATest."""
        super(VrefDQOptimizer, cls).update_config_params(config_data)

        # set function to exec firmware
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_EXEC_FIRMWARE)

        # only one pstate needs to be tested
        VrefDQOptimizer.initial_num_pstates = config_data.num_pstates
        config_data.num_pstates = VrefDQOptimizer.NumPstates
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    @classmethod
    def restore_config_params(cls, config_data: ConfigData) -> None:
        """Restore parameters."""
        # restore number of pstates
        config_data.num_pstates = VrefDQOptimizer.initial_num_pstates  # type: ignore
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    def validate_test_parameters(self) -> TestStatus:
        """Validate test specific parameters.

        @return: test status after parameter validation
        """
        if self.is_phy_v2:
            if int(self.config_data.phy_log, 16) > 200:
                err_msg = 'Vref for 1D optimization test requires PHY log to be set to at least ' \
                          '\'Stage completion\' level!'
                self.logger.error(err_msg)
                return TestStatus.FAIL

        return TestStatus.PARAMS_VALIDATED

    def run_check_configuration(self) -> int:
        """TODO:summary line."""
        phy_init_status = -1
        try:
            # execute RPA
            self.processor.ddrc_reg_calc(self.config_data)

            # save generated .ds file
            workspace_dir = Workspace.get_instance().get_location()
            with open(os.path.join(workspace_dir, f"{self.config_data.mem_type}{Const.DS_FILE_SUFFIX}"), 'wt',
                    encoding="utf-8") as f:
                f.write(self.config_data.ds_file_txt)

            self.processor.update_ddrc_config(self.config_data)
            self.processor.update_phy_config(self.config_data)

            # run phyinit
            phy_init_driver = PHYInitDriver.make_unique_instance(self.config_data.data_dir,
                                                                 self.config_data.snps_phy_info.name,
                                                                 self.config_data.mem_type)
            phy_init_driver.run_driver(self.config_data)
            phy_init_driver.process_results(self.config_data)

            # target addresses and binary sizes
            self.processor.init_bin_info(self.config_data)

            # create full dmem config
            self.config_data.generate_firmware_dmem_binaries()

            # load app and DCD if necessary (only on the 1st executed test)
            self.channel.close()
            test_status = self.load_dcd_and_app()

            # execute
            if TestStatus.FAIL != test_status:
                test_status = self.run_app()

            # write board configuration
            if TestStatus.FAIL != test_status:
                self.set_log_level()

            # phy_result = "Phy is up and running"
            while True:
                value = self.channel.read_symbol(self.app.get_result_symbol('phy_status'))
                phy_init_status = int(value) if value is not None else -1
                if phy_init_status > 0:
                    break

                if not self.is_waiting_for_input():
                    time.sleep(3)
                else:
                    break
        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('Vref configuration check ended with exception: %s', str(ex))
        finally:
            return phy_init_status

    def execute_test(self) -> TestStatus:
        """Override write_test_input_params from BaseTest.

        @return: test status after writing test parameters
        """
        if self.is_phy_v2:
            while True:
                value = self.channel.read_symbol(self.app.get_result_symbol('phy_status'))
                phy_init_status = int(value) if value is not None else -1
                if phy_init_status > 0:
                    phy_init_status = self.ddr_phy_vref_searcher()
                    break

                if not self.is_waiting_for_input():
                    time.sleep(3)
                else:
                    break

            if phy_init_status > 0:
                self.read_logged_data()
                self.logger.error(SnpsPhy.get_error_message(phy_init_status))
                return TestStatus.CONFIGURATION_ERROR

        return super(VrefDQOptimizer, self).execute_test()

    def ddr_phy_vref_searcher(self):  # type: ignore
        """Search phy and ddr vrefs."""
        RANGE = {"PHY": [0, 128], "DRAM": {0: [0, 29], 1: [0, 50]}}
        STEP_SIZE = {"PHY": 8, "DRAM": 4}

        test_phy_log_file = self.log_file
        workspace_dir = Workspace.get_instance().get_location()
        self.log_file = os.path.join(workspace_dir, "phy_vref.log")

        vref_dq_range = self.config_data.params[Const.PARAM_S_DQ_VREF][Const.PARAM_S_DQ_VREF_RANGE]
        vref_dq_value = self.config_data.params[Const.PARAM_S_DQ_VREF][Const.PARAM_S_DQ_VREF_VALUE]

        # set starting values for controller vref & dram vref
        phy_vref = RANGE["PHY"][0]
        dram_vref = RANGE["DRAM"][vref_dq_range][0]

        while True:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)

            self.logger.info(f'[VrefDQ Optimizer] check configuration for: phy_vref={hex(phy_vref)},'
                             f' dram_vref={vref_dq_range},{hex(dram_vref)}')
            phy_init_status = self.check_configuration(hex(phy_vref), hex(vref_dq_value), hex(dram_vref))
            if phy_init_status > 0:
                self.read_logged_data()
                if not os.path.isfile(self.log_file):
                    self.logger.error('File %s does not exist!!!', self.log_file)
                    break

                shmoo_phy, shmoo_dram = self.get_shmoo_params(self.log_file)
                if (not shmoo_phy) and (not shmoo_dram):
                    self.logger.error('Could not determine the parameters that must be varied!')
                    break

                if shmoo_phy:
                    phy_vref += STEP_SIZE["PHY"]
                    if phy_vref > RANGE["PHY"][1]:
                        self.logger.error(f'PHY vref exceeded {RANGE["PHY"][1]}!')
                        break

                if shmoo_dram:
                    dram_vref += STEP_SIZE["DRAM"]
                    if dram_vref > RANGE["DRAM"][vref_dq_range][1]:
                        self.logger.error(f'DRAM vref exceeded {RANGE["DRAM"][vref_dq_range][1]}!')
                        break
            else:
                break

        self.log_file = test_phy_log_file
        return phy_init_status

    def check_configuration(self, phy_vref: str, vref_dq_range: str, dram_vref: str) -> int:
        """Update PhyVref & MR and redo the training."""
        self.config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["PhyVref"] = phy_vref
        self.config_data.params[Const.PARAM_S_DQ_VREF][Const.PARAM_S_DQ_VREF_RANGE] = vref_dq_range
        self.config_data.params[Const.PARAM_S_DQ_VREF][Const.PARAM_S_DQ_VREF_VALUE] = dram_vref

        # run test
        return self.run_check_configuration()

    def get_shmoo_params(self, phy_log: str) -> Tuple[bool, bool]:
        """Determine what parameters must be changed."""
        stage_1d_tag = "[1]"
        stages_1d_training = [
            # phase no, description, completion state
            [0, "End of CA training", False],
            [1, "End of initialization", False],
            [2, "End of read enable training", False],
            [3, "End of fine write leveling", False],
            [4, "End of read dq deskew training", False],
            [5, "End of MPR read delay center optimization", False],
            [6, "End of Write leveling coarse delay", False],
            [7, "End of write delay center optimization", False],
            [8, "End of read delay center optimization", False],
            [9, "End of max read latency training", False],
            [10, "Firmware has run successfully (firmware completed)", False]
        ]

        stage_2d_tag = "[2]"
        stages_2d_training = [
            # phase no, description, completion state
            [0, "End of initialization", False],
            [1, "End of 2D write delay/voltage center optimization", False],
            [2, "End of 2D read delay/voltage center optimization", False],
            [3, "Firmware has run successfully (firmware completed)", False]
        ]

        with open(phy_log, "rt") as f:
            line = f.readline()
            while line:
                if stage_1d_tag in line:
                    for stage_msg in stages_1d_training:
                        if stage_msg[1] in line:  # type: ignore
                            stage_msg[2] = True
                elif stage_2d_tag in line:
                    for stage_msg in stages_2d_training:
                        if stage_msg[1] in line:  # type: ignore
                            stage_msg[2] = True
                line = f.readline()

        shmoo_phy = False
        shmoo_dram = False
        if not stages_1d_training[10][2]:  # 1D training failed
            if (self.config_data.dram_type in [2, 4] and not stages_1d_training[0][2]) or not stages_1d_training[2][2] \
                    or not stages_1d_training[4][2]:
                shmoo_phy = True
            elif stages_1d_training[6][2]:
                shmoo_dram = True
        else:
            # 1D training passed
            if not stages_2d_training[3][2]:  # 2D training failed
                if not stages_2d_training[1][2]:
                    shmoo_phy = True
        return shmoo_phy, shmoo_dram

    def phy_init_succeeded(self) -> bool:
        """Check if PHY initialization passed.

        @return: True if PHY init succeeded
        """
        # read PHY log data
        self.get_phy_init_status()
        # in case test is failing force the test to continue searching valid parameters
        return True

    def process_results(self) -> None:
        """Additional processing and output logic that can be performed on the results."""
        super(VrefDQOptimizer, self).process_results()

        if len(self.results['records']) == 0:
            return  # when PHY training fails, records will be empty

        # delete old vref info
        if os.path.exists(self.config_data.vref_info_file):
            os.remove(self.config_data.vref_info_file)

        vref_info = {}
        data = self.results['records'][0]['data']
        if isinstance(data, str):
            data = ast.literal_eval(data)

        phy_vref = hex(data[0])
        vref_info["phyParams.messageBlockCommon.PhyVref"] = phy_vref

        dram_vref = hex(data[1])
        if self.config_data.dram_type == 0:
            vref_info["phyParams.messageBlock[0].MR6"] = dram_vref
        elif self.config_data.dram_type in [2, 4]:
            vref_info["phyParams.messageBlock[0].MR14_A0"] = dram_vref

        # create file with vref info
        with open(self.config_data.vref_info_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(vref_info, indent=4))


class CABusSignalsMargin(PhyTrainingTest):
    """Class implementing CA Bus signals margin Test."""

    NAME = 'CA Bus Signals Margin'

    Train2DDisabled = '0'
    NumPstates = 1
    MaximumDebug = '0x04'
    DetailedDebug = '0x05'

    # CABusSignalsMargin updates PHY log level internally, so we have to restore it at the end of test
    initial_phy_log = None
    # For CABusSignalsMargin 2D training should not be executed - configuration value
    initial_train_2d = None
    # CABusSignalsMargin must be executed for a single pstate, so we have to restore it at the end of test
    initial_num_pstates = None

    @classmethod
    def data_eye_is_generated(cls) -> bool:
        """Data Eye is generated using test results."""
        return True

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(CABusSignalsMargin, cls).update_config_params(config_data)

        # set function to exec firmware
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_EXEC_FIRMWARE)

        # do not execute 2D training; note that this will be passed to the application through dcd.bin
        CABusSignalsMargin.initial_train_2d = config_data.train_2d
        # this must be set also in overwrite_params because it will be overwritten at import ds
        config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS][
            Const.PARAM_S_SYS_TRAIN_2D] = CABusSignalsMargin.Train2DDisabled

        # log level should be detailed debug
        CABusSignalsMargin.initial_phy_log = config_data.phy_log
        config_data.phy_log = CABusSignalsMargin.DetailedDebug if \
                ConfigData.is_phy_v2(config_data.snps_phy_info) else CABusSignalsMargin.MaximumDebug

        # only one pstate needs to be tested
        CABusSignalsMargin.initial_num_pstates = config_data.num_pstates
        config_data.num_pstates = CABusSignalsMargin.NumPstates
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    @classmethod
    def restore_config_params(cls, config_data: ConfigData) -> None:
        """Restore parameters."""
        # restore 2D training status
        config_data.train_2d = CABusSignalsMargin.initial_train_2d  # type: ignore

        # restore PHY log level
        config_data.phy_log = CABusSignalsMargin.initial_phy_log  # type: ignore

        # restore number of pstates
        config_data.num_pstates = CABusSignalsMargin.initial_num_pstates  # type: ignore
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    def validate_test_parameters(self) -> TestStatus:
        """Validate test specific parameters.

        @return: test status after parameter validation
        """
        phy_log_level = self.config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["HdtCtrl"]
        if int(phy_log_level, 16) > 5:
            err_msg = 'CA Bus Eye test requires PHY log to be set to at least \'Detailed debug\' level!'
            self.logger.error(err_msg)
            return TestStatus.FAIL

        return TestStatus.PARAMS_VALIDATED

    def process_results(self) -> None:
        """Extract CA data from PHY log."""
        super(CABusSignalsMargin, self).process_results()

        self.create_data_eye()

    def create_data_eye(self) -> None:
        """Create data eye(s) figures and save them to file."""
        file_path = self.config_data.log_file
        if file_path is not None:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                img_file_path = self.config_data.figure_file
                EyeData.clear()
                figure = EyeData.show_ca_bus_eyes_plots(file_path, self, self.config_data.soc_name,
                                            ConfigData.is_phy_v2(self.config_data.snps_phy_info))
                if figure is not None:
                    figure.savefig(img_file_path)
                    self.config_data.params[Const.PARAM_S_TC]['diag_image_file'] = img_file_path
                else:
                    self.config_data.params[Const.PARAM_S_TC]['diag_image_file'] = None


class PhyInit(PhyTrainingTest):
    """Class implementing Phy Init Test."""

    NAME = 'Phy Init'

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(PhyInit, cls).update_config_params(config_data)

        # set function to full init (exec firmware)
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT)


class FirstBoot(DDRBaseTest):
    """Class implementing First Boot Test."""

    NAME = 'First Boot'
    ID = 200

    def validate_test_parameters(self) -> TestStatus:
        """Validate test specific parameters.

        @return: test status after parameter validation
        """
        if self.config_data.quick_boot_registers:
            return TestStatus.PARAMS_VALIDATED

        return TestStatus.FAIL

    @classmethod
    def load_quick_boot_registers(cls, config_data: ConfigData) -> bool:
        """Load registers from the corresponding quick boot fw file."""
        fw_data_dir = os.path.join(config_data.data_dir, 'firmware',
                                   config_data.snps_phy_info.name, f'{config_data.mem_type}_quickboot')
        quick_boot_data_file = os.path.join(os.path.abspath(fw_data_dir),
                                            SnpsPhy.get_data_file(mem_type=config_data.mem_type,
                                                                  data_type='registers', quick_boot=True))
        if os.path.exists(quick_boot_data_file):
            address_start_marker = '\'h'
            len_address_start = len(address_start_marker)
            with open(quick_boot_data_file, 'rt', encoding='utf-8') as f:
                regs_lines = f.read().split()
                for reg_line in regs_lines:
                    reg_addr = reg_line[reg_line.find(address_start_marker) + len_address_start: -1]
                    config_data.quick_boot_registers.append(f"0x{reg_addr}")
                return True

        cls.logger.error(f'Quick boot data is not available for firmware version '
                         f'{config_data.snps_phy_info.name}!')
        return False

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(FirstBoot, cls).update_config_params(config_data)

        # set function to first boot
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FIRST_BOOT)

        if not config_data.quick_boot_registers:
            cls.load_quick_boot_registers(config_data)

        # first boot test should collect new quick boot data
        config_data.quick_boot_data.clear()
        config_data.quick_boot_msgblk.clear()
        config_data.quick_boot_acsm.clear()

    def read_results(self) -> TestStatus:
        """Override read_results from DDRBaseTest.

        @return: test status after reading test results
        """
        result = super(FirstBoot, self).read_results()

        # in first boot mode, qbr values will be saved in the area reserved for diags results
        qbr_out_addr_hi = int(self.config_data.diags_params['diag_out_addr_hi'], 16)
        qbr_out_addr_lo = int(self.config_data.diags_params['diag_out_addr_lo'], 16)
        qbr_out_addr = (qbr_out_addr_hi << 32) | qbr_out_addr_lo
        swap_data = self.config_data.params.get("swap_data", False)

        # read first integer where the number of csr values is saved
        no_qbr = self._read_integer(qbr_out_addr, swap=not swap_data)

        quick_boot_vals = []
        qbr_out_addr += 4  # skip 4 bytes, go to the address of the first value
        if no_qbr > 0:
            # read string that holds all csr values
            # for each value we should extract from the string data 8 chars
            target_data_str = self.channel.read_data(qbr_out_addr, 4, no_qbr)
            data_size = 4 * no_qbr  # 4 bytes/int
            target_data_bytes = bytearray.fromhex(target_data_str)
            data = [val for (val,) in struct.iter_unpack('<I', target_data_bytes[:data_size])]
            if len(data) != no_qbr:
                self.logger.error('CSR read data is incomplete!')
            else:
                current_int_idx = 0
                for idx in range(0, no_qbr):
                    val_int = data[current_int_idx]
                    current_int_idx += 1
                    quick_boot_vals.append(val_int)

        self.config_data.quick_boot_msgblk.clear()
        msgblk_addr = qbr_out_addr + (4 * no_qbr)
        no_msgblk = self._read_integer(msgblk_addr, swap=not swap_data)  # number of (addr, val) pairs
        if no_msgblk > 0:
            msgblk_addr += 4
            target_data_str = self.channel.read_data(msgblk_addr, 4, no_msgblk * 2)
            data_size = 4 * no_msgblk * 2  # 4 bytes/int
            target_data_bytes = bytearray.fromhex(target_data_str)
            data = [val for (val,) in struct.iter_unpack('<I', target_data_bytes[:data_size])]
            if len(data) != (no_msgblk * 2):
                self.logger.error('Message block read data is incomplete!')
            else:
                current_int_idx = 0
                for idx in range(0, no_msgblk):
                    addr = data[current_int_idx]
                    current_int_idx += 1
                    val = data[current_int_idx]
                    current_int_idx += 1
                    self.config_data.quick_boot_msgblk[addr] = val

        self.config_data.quick_boot_acsm.clear()
        no_acsm_sram_addr = msgblk_addr + (4 * no_msgblk * 2)
        no_acsm_sram = self._read_integer(no_acsm_sram_addr, swap=not swap_data)
        if no_acsm_sram > 0:
            acsm_sram_addr = no_acsm_sram_addr + 4
            target_data_str = self.channel.read_data(acsm_sram_addr, 4, no_acsm_sram)
            data_size = 4 * no_acsm_sram  # 4 bytes/int
            target_data_bytes = bytearray.fromhex(target_data_str)
            data = [val for (val,) in struct.iter_unpack('<I', target_data_bytes[:data_size])]
            if len(data) != no_acsm_sram:
                self.logger.error('ACSM SRAM read data is incomplete!')
            else:
                current_int_idx = 0
                for idx in range(0, no_acsm_sram):
                    val = data[current_int_idx]
                    current_int_idx += 1
                    self.config_data.quick_boot_acsm.append(val)

        self.config_data.quick_boot_data.clear()
        if len(quick_boot_vals) != len(self.config_data.quick_boot_registers):
            self.logger.error('Quick boot data is incomplete!')
        else:
            for idx in range(0, len(quick_boot_vals)):
                addr = self.config_data.quick_boot_registers[idx]
                self.config_data.quick_boot_data.append((addr, f"0x{quick_boot_vals[idx]:x}"))

        quick_boot_txt = ''
        for address, value in self.config_data.quick_boot_data:
            quick_boot_txt += f"{address}, {value}\n"

        if quick_boot_txt:
            workspace_dir = Workspace.get_instance().get_location()
            quick_boot_file = os.path.join(workspace_dir, "quick_boot_data.txt")
            with open(quick_boot_file, "wt", encoding="utf-8") as f:
                f.write(quick_boot_txt)

        return result


class CAEye(PhyTrainingTest):
    """Class implementing CA Eye Test."""

    NAME = 'CA Eye'

    anibs_data = []  # type: ignore
    signals_data = {}  # type: ignore  # {CS -> {CA -> [data]}}
    Train2DDisabled = '0'
    NumPstates = 1
    CATrainDisable = '0'
    DetailedDebug = '0x05'
    MaximumDebug = '0x04'

    # CAEye updates PHY log level internally, so we have to restore it at the end of test
    initial_phy_log = None
    # For CAEye 2D training should not be executed - configuration value
    initial_train_2d = None
    # CAEye must be executed for a single pstate, so we have to restore it at the end of test
    initial_num_pstates = None
    # CATrainEnable state
    ca_train_status = None

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(CAEye, cls).update_config_params(config_data)

        # set function to exec firmware
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_EXEC_FIRMWARE)

        # do not execute 2D training; note that this will be passed to the application through dcd.bin
        CAEye.initial_train_2d = config_data.train_2d
        # this must be set also in overwrite_params because it will be overwritten at import ds
        config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS][Const.PARAM_S_SYS_TRAIN_2D] \
            = CAEye.Train2DDisabled

        # log level should be detailed debug
        CAEye.initial_phy_log = config_data.phy_log
        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            config_data.phy_log = CAEye.DetailedDebug
        else:
            config_data.phy_log = CAEye.MaximumDebug

        # only one pstate needs to be tested
        CAEye.initial_num_pstates = config_data.num_pstates
        config_data.num_pstates = CAEye.NumPstates
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

        # CATrainOpt PHY parameter should be set to 0
        if Const.PARAM_S_CA_CONFIG not in config_data.params:
            config_data.params[Const.PARAM_S_CA_CONFIG] = {}
        else:
            if Const.PARAM_S_CA_TRAIN_STATUS in config_data.params[Const.PARAM_S_CA_CONFIG]:
                CAEye.ca_train_status = config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_TRAIN_STATUS]
        config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_TRAIN_STATUS] = CAEye.CATrainDisable

    @classmethod
    def restore_config_params(cls, config_data: ConfigData) -> None:
        """Restore parameters."""
        # restore 2D training status
        config_data.train_2d = CAEye.initial_train_2d  # type: ignore

        # restore PHY log level
        config_data.phy_log = CAEye.initial_phy_log  # type: ignore

        # restore number of pstates
        config_data.num_pstates = CAEye.initial_num_pstates  # type: ignore
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

        # restore CA train enable status
        if CAEye.ca_train_status:
            config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_TRAIN_STATUS] = CAEye.ca_train_status

    @classmethod
    def run_only_as_scenario(cls) -> bool:
        """Test should be run only as scenario test."""
        return True

    def validate_test_parameters(self) -> TestStatus:
        """Validate test specific parameters.

        @return: test status after parameter validation
        """
        phy_log_level = self.config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["HdtCtrl"]
        if int(phy_log_level, 16) > 5:
            err_msg = 'CA Eye test requires PHY log to be set to at least \'Detailed debug\' level!'
            self.logger.error(err_msg)
            return TestStatus.FAIL

        return TestStatus.PARAMS_VALIDATED

    def process_results(self) -> None:
        """Extract CA data from PHY log."""
        super(CAEye, self).process_results()
        if ConfigData.is_phy_v2(self.config_data.snps_phy_info):
            self.store_phy_v2_data_eye()
        else:
            self.store_phy_v3_data_eye()

    def store_phy_v2_data_eye(self):  # type: ignore
        """Create data eye(s) figures and save them to file."""
        if len(self.results['records']) == 0:
            return  # when PHY training fails, records will be empty

        self.anibs_data = self.results['records'][0]['data']
        self.signals_data = {}
        file_path = self.config_data.log_file
        if file_path is not None:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'rt', encoding="utf-8") as f:
                    line = f.readline().strip()
                    cs = None
                    ca = None
                    while line:
                        if "[1] PMU5: CA bitmap dump for cs" in line:
                            line_content = line.split()
                            cs = int(line_content[len(line_content) - 1])
                            if cs not in self.signals_data:
                                self.signals_data[cs] = {}
                        elif "[1] PMU5: CA" in line:
                            line_content = line[line.find(':') + 1:]
                            line_content = line_content.replace("[1]", "").strip()
                            line_content = line_content.split(' ')
                            ca = line_content[0]

                            # unprocessed data
                            # data = []
                            # for val in line_content[2:]:
                            #     data.append(val)

                            # processed data
                            data = [0]
                            ca_data = []
                            for d in line_content[2:]:
                                b = ((bin(int(d, 16)))[2:]).zfill(8)
                                for idx in range(8):
                                    if len(ca_data) > 0 and ca_data[-1] != b[idx]:
                                        data.append(len(ca_data))
                                    ca_data.append(b[idx])
                            data.append(128)

                            if ca in self.signals_data[cs]:
                                self.logger.warning("Data for other frequencies is ignored...")
                                break
                            else:
                                self.signals_data[cs][ca] = data
                        line = f.readline().strip()

    def store_phy_v3_data_eye(self):  # type: ignore
        """Create data eye(s) figures and save them to file."""
        if len(self.results['records']) == 0:
            return  # when PHY training fails, records will be empty

        self.anibs_data = self.results['records'][0]['data']
        self.signals_data = {}
        file_path = self.config_data.log_file
        if file_path is not None:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'rt', encoding="utf-8") as f:
                    line = f.readline().strip()
                    cs = None
                    ca = None
                    while line:
                        if "[1] PMU4: Channel" in line:
                            line_content = line.split(' ')
                            channel = line_content[3]
                            edge = line_content[7]
                            rank = line_content[13]
                            cs = f'Channel {channel} {edge} edge rank {rank}'
                            if cs not in self.signals_data:
                                self.signals_data[cs] = {}
                        elif "[1] PMU4: CA" in line:
                            line_content = line[line.find(':') + 1:]
                            line_content = line_content.replace("[1]", "").strip()
                            line_content = line_content.split(' ')
                            ca = line_content[0]

                            # unprocessed data
                            # data = []
                            # for val in line_content[2:]:
                            #     data.append(val)

                            # processed data
                            data = [0]
                            ca_data = []
                            for d in line_content[2:]:
                                b = ((bin(int(d, 16)))[2:]).zfill(8)
                                for idx in range(8):
                                    if len(ca_data) > 0 and ca_data[-1] != b[idx]:
                                        data.append(len(ca_data))
                                    ca_data.append(b[idx])
                            data.append(256)

                            if ca in self.signals_data[cs]:
                                self.logger.warning("Data for other frequencies is ignored...")
                                break
                            else:
                                self.signals_data[cs][ca] = data
                        line = f.readline().strip()

    def get_data_eye(self):  # type: ignore
        """Get recently processed results."""
        return self.anibs_data, self.signals_data

    def report_phy_error(self) -> bool:
        """Determine if the test should add info about encountered PHY error to the test results."""
        return False  # for CA Eye PHY error should not be logged


class VrefCAOptimizer(PhyTrainingTest):
    """Class implementing Vref for CA Optimizer Test."""

    ID = 202
    NAME = 'Vref for CA Optimizer'

    CAVrefRange = 1
    CAVrefValue = 13
    Train2DDisabled = '0'
    NumPstates = 1

    # For VrefCAOptimizer 2D training should not be executed - configuration value
    initial_train_2d = None
    # VrefCAOptimizer must be executed for a single pstate,
    # so we have to restore it at the end of test - configuration value
    initial_num_pstates = None

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        super(VrefCAOptimizer, self).__init__(config_data)

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from BaseTest."""
        super(VrefCAOptimizer, cls).update_config_params(config_data)

        # set function to exec firmware
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_EXEC_FIRMWARE)

        # set CA vref range
        if Const.PARAM_S_CA_VREF not in config_data.params:
            config_data.params[Const.PARAM_S_CA_VREF] = {}
            config_data.params[Const.PARAM_S_CA_VREF][Const.PARAM_S_CA_VREF_RANGE] = VrefCAOptimizer.CAVrefRange
            config_data.params[Const.PARAM_S_CA_VREF][Const.PARAM_S_CA_VREF_VALUE] = VrefCAOptimizer.CAVrefValue

        # CATrainOpt PHY parameter should be set to 1.
        if Const.PARAM_S_CA_CONFIG not in config_data.params:
            config_data.params[Const.PARAM_S_CA_CONFIG] = {}
        config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_TRAIN_STATUS] = '1'

        # do not execute 2D training; note that this will be passed to the application through dcd.bin
        VrefCAOptimizer.initial_train_2d = config_data.train_2d
        # this must be set also in overwrite_params because it will be overwritten at import ds
        config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS][Const.PARAM_S_SYS_TRAIN_2D]\
            = VrefCAOptimizer.Train2DDisabled

        # test should be executed for 1 pstate
        VrefCAOptimizer.initial_num_pstates = config_data.num_pstates
        config_data.num_pstates = VrefCAOptimizer.NumPstates  # type: ignore
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{VrefCAOptimizer.NumPstates}')

    @classmethod
    def restore_config_params(cls, config_data: ConfigData) -> None:
        """Restore parameters."""
        # restore 2D training status
        config_data.train_2d = VrefCAOptimizer.initial_train_2d  # type: ignore

        # restore number of pstates
        config_data.num_pstates = VrefCAOptimizer.initial_num_pstates  # type: ignore
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    def process_results(self) -> None:
        """Additional processing and output logic that can be performed on the results."""
        super(VrefCAOptimizer, self).process_results()

        if len(self.results['records']) == 0:
            return  # when PHY training fails, records will be empty

        # delete old vref info
        if os.path.exists(self.config_data.vref_info_file):
            os.remove(self.config_data.vref_info_file)

        vref_info = {}
        data = self.results['records'][0]['data']
        if isinstance(data, str):
            data = ast.literal_eval(data)

        ca_vref = data[2] & 0x7F

        if "vrefCAConfig" in self.config_data.params:
            vref_info["vrefCAConfig.vref_ca_range"] = ca_vref >> 6
            vref_info["vrefCAConfig.vref_ca_value"] = ca_vref & 0x3F

        # create file with vref info
        with open(self.config_data.vref_info_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(vref_info, indent=4))


class TrainedDataEye(PhyTrainingTest):
    """Class implementing 2D Data Eye Test."""

    class Protocol(Enum):
        """Protocol type."""
        UNKNOWN = None
        LPDDR4 = 'LPDDR4'
        LPDDR5 = 'LPDDR5'

        @staticmethod
        def from_name(name: str) -> 'TrainedDataEye.Protocol':
            """Converts Protocol from given name.

            @param name: name to be converted
            @return: corresponding protocol type or UNKNOWN if the given name is not defined
            """
            for p in TrainedDataEye.Protocol:
                if p.name == name:
                    return p
            return TrainedDataEye.Protocol.UNKNOWN

    NAME = 'Trained Data Eye'

    DetailedPHYLog = '0x04'
    NumPstates = 1

    # DataEye2D updates PHY log level internally, so we have to restore it at the end of test
    initial_phy_log = None
    # DataEye2D must be executed for a single pstate, so we have to restore it at the end of test
    initial_num_pstates = None

    def __init__(self, config_data: ConfigData):
        """Constructor.

        @param config_data: configuration data
        """
        super(TrainedDataEye, self).__init__(config_data)

        self.is_phy_v3 = ConfigData.is_phy_v3(config_data.snps_phy_info)
        self.protocol: TrainedDataEye.Protocol = TrainedDataEye.Protocol.UNKNOWN

        self.dir = config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][Const.PARAM_TEST_PARAMS_DIRECTION]
        self.rank = config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][Const.PARAM_TEST_PARAMS_CS]
        self.byte = config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][Const.PARAM_TEST_PARAMS_BYTE]
        self.lane = config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][Const.PARAM_TEST_PARAMS_BIT]

        self.nbFineSteps = 64
        self.step = 1
        self.error = 0
        self.minHeightThreshold = False
        self.layoutMode = 'basic'
        self.mergeRuns = False
        self.showAllEyes = False
        self.verbose = True
        self.rxDacOverride = None
        self.d5y11a = False
        self.noLegend = True
        self.noShow = False
        self.superImpose = False
        self.pngFile = config_data.figure_file

        # Fixed center for 2D trained delay, to make debugging and comparing eyes easier for the user
        dir_multiplier = 6 if self.dir == 'RX' else 4
        self.range_delay_2d = self.nbFineSteps + (dir_multiplier * self.nbFineSteps / 32)
        self.center_delay_2d = self.range_delay_2d / 2

    @classmethod
    def data_eye_is_generated(cls) -> bool:
        """Data Eye is generated using test results."""
        return True

    @classmethod
    def update_config_params(cls, config_data: ConfigData) -> None:
        """Override update_config_params from VTSATest.

        @param config_data: configuration data
        """
        super(TrainedDataEye, cls).update_config_params(config_data)

        # set function to full init (exec firmware)
        config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT)

        # log level should be detailed debug
        TrainedDataEye.initial_phy_log = config_data.phy_log
        config_data.phy_log = TrainedDataEye.DetailedPHYLog

        # only one pstate needs to be tested
        TrainedDataEye.initial_num_pstates = config_data.num_pstates
        config_data.num_pstates = TrainedDataEye.NumPstates
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    @classmethod
    def restore_config_params(cls, config_data: ConfigData) -> None:
        """Restore parameters.

        @param config_data: configuration data
        """
        # restore PHY log level
        config_data.phy_log = TrainedDataEye.initial_phy_log  # type: ignore

        # restore number of pstates
        config_data.num_pstates = TrainedDataEye.initial_num_pstates  # type: ignore
        config_data.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{config_data.num_pstates}')

    def process_results(self) -> None:
        """Process results specific for DataEye2D."""
        super(TrainedDataEye, self).process_results()

        # List of all eyes found in input files
        eyes: list[Eye2D] = list()

        # parse FW log file
        isFWLog = False
        try:
            srcFile = open(self.log_file, 'rt')
            isFWLog = True
        except IOError as err:
            self.logger.error(err)
            traceback.print_exc()

        # List of all eyes found in a given 2D training run (only used for RX)
        eyesAcrossRank: list[Eye2D] = list()
        # List of eyes for a specific rank found in a given 2D training run
        eyesInRank: list[Eye2D] = list()
        try:
            if isFWLog:
                self.logger.debug('Scanning firmware training log %s for 2D eyes', self.log_file)
                inEyeRankSection = False
                eyeType = ""
                dacIdx = 0
                while True:
                    line = srcFile.readline()
                    if line == '':
                        break

                    match = re.search('Start (LP)?DDR[0-9]+(X)? Training', line)
                    if match is not None and self.protocol == TrainedDataEye.Protocol.UNKNOWN:
                        self.protocol = TrainedDataEye.Protocol.from_name(match.group(0).split()[1].strip("X"))
                        if self.protocol == TrainedDataEye.Protocol.UNKNOWN:
                            self.logger.error('Only LPDDR4, and LPDDR5 are supported for now!')
                            break
                        if self.verbose:
                            self.logger.debug('Detected protocol: %s', self.protocol.value)
                        continue
                    # DDR5 Rx DFE
                    if 'Start d5_rx_2d dly_incdec' in line:
                        # Detecting which DAC is being configured
                        match = re.search('dac [0-9]+', line)
                        if not match:
                            self.logger.error(
                                'Badly formatted log file: could not extract Rx DFE DAC information from log'
                            )
                            break
                        dacIdx = int(match.group(0).split()[1])
                        if self.verbose:
                            self.logger.debug('Switching to DAC: %s' , dacIdx)
                        continue
                    # LP54 true / complement eyes
                    if 'RX-C EYES' in line:
                        eyeType = "-C"
                    if 'RX-T EYES' in line:
                        eyeType = "-T"
                    if 'TX EYES' in line:
                        eyeType = ""

                    match = re.search("isSecondRun ([0-9])", line)
                    if match is not None:
                        eyeType += " run%s" % match.group(1)

                    # This is how we detect the start of a 2D training run for a specific rank
                    if (((self.dir == 'TX') and ('2D Write Scanning' in line)) or
                        ((self.dir == 'RX') and ('2D Read Scanning' in line)) or
                        ((self.dir == 'RX') and ('2D-DFE Read Scanning' in line))):
                        # Extracting rank of this 2D run
                        match = re.search('TG [0-9]+', line)
                        if not match:
                            self.logger.error('Badly formatted log file: could not extract rank information from log')
                            break
                        rank = int(match.group(0).split()[1])
                        if inEyeRankSection:
                            if self.dir == 'TX':
                                eyes += eyesInRank
                            elif not self.is_phy_v3:
                                eyesAcrossRank += eyesInRank
                            eyesInRank = list()
                        inEyeRankSection = True
                        continue
                    if inEyeRankSection:
                        # Extracting byte and lane (rank was already extracted above)
                        match = re.search('DB[0-9]+ L[0-9]+', line)
                        if match is not None:
                            byte = int(match.group(0).split()[0][2:])
                            lane = int(match.group(0).split()[1][1:])
                            if ((self.rank == -1) or (rank == self.rank)) and (
                                    (self.byte == -1) or (byte == self.byte)) and (
                                    (self.lane == -1) or (lane == self.lane)):
                                # Extracting previously trained center
                                # phy2 / ddr54 format
                                match1 = re.search('delay = ([0-9]+), voltage = ([0-9]+)', line)
                                # lpddr54 format
                                match2 = re.search(
                                    'anchor delay = ([0-9]+), optimal delay offset = ([0-9]+),* voltage = ([0-9]+)',
                                    line)
                                if match1 is not None:
                                    delay = int(match1.group(1))
                                    vref = int(match1.group(2))
                                    delayOffset = None
                                    anchorDelay = None
                                elif match2 is not None:
                                    anchorDelay = int(match2.group(1))
                                    delayOffset = int(match2.group(2))
                                    delay = anchorDelay + delayOffset
                                    vref = int(match2.group(3))
                                else:
                                    self.logger.error(f'Unrecognized line: {line}')
                                    break
                                # Extracting the actual eye (array of min/max VREFs)
                                delays = list()
                                minVrefs = list()
                                maxVrefs = list()
                                for m in range(0, 2):
                                    line = srcFile.readline()
                                    if match1 is not None:
                                        # phy2
                                        line = line.replace('[2] PMU4:', '')
                                    else:
                                        # phy3
                                        line = line.replace('[1] PMU4:', '')
                                    # Find the index of the previously trained center.
                                    if delayOffset is not None:
                                        # in lpddr5, the center is given by the delayOffset
                                        # (divided by 2 since the log messages only print half of the points)
                                        centerIndex = delayOffset / 2
                                    else:
                                        # It corresponds to the value surrounded by '>' '<'.
                                        centerIndex = 0
                                        vrefs = line.split()
                                        for vrefStr in vrefs:
                                            if '>' in vrefStr:
                                                break
                                            else:
                                                centerIndex = centerIndex + 1

                                    offset: float = -1
                                    if anchorDelay is not None:
                                        offset = anchorDelay
                                    else:
                                        # For now, place the trained previous delay (previous center)
                                        # at the fixed coordinate of center_delay_2d.
                                        # We will offset it again later once we know the trained 2D delay.
                                        offset = self.center_delay_2d - (centerIndex * self.nbFineSteps / 32)

                                    line = line.replace('<', '')
                                    line = line.replace('>', '')
                                    vrefs = line.split()
                                    for i in range(0, len(vrefs)):
                                        if m == 0:
                                            d = (i * self.nbFineSteps / 32) + offset
                                            delays.append(d)
                                        elif not len(vrefs) == len(delays):
                                            self.logger.error(
                                                'Min and max vref lines have different number of elements'
                                            )
                                            break
                                        v = int(vrefs[i])
                                        if m == 0:
                                            maxVrefs.append(v)
                                        else:
                                            minVrefs.append(v)
                                eyeDataPoints = list()
                                for i in range(0, len(delays)):
                                    eyeDataPoints.append(Eye2DData(delays[i], minVrefs[i], maxVrefs[i]))
                                    eye = Eye2D(rank, byte, lane, dacIdx, eyeDataPoints, not isFWLog, self.log_file,
                                                eyeType)
                                    if self.is_phy_v3:
                                        eye.trained2DDelay = delay
                                        eye.trained2DVref = vref
                                        if self.verbose:
                                            self.logger.debug('rank %s byte %s lane %s trained 2D delay: %s',
                                                              eye.rank, eye.byte, eye.lane, delay)
                                        if self.dir == 'RX':
                                            eyesAcrossRank.append(eye)
                                        else:
                                            eyesInRank.append(eye)
                                    elif self.protocol == TrainedDataEye.Protocol.LPDDR4:
                                        eye.previousDelay = delay
                                        eye.previousVref = vref
                                        if self.verbose:
                                            self.logger.debug('rank %s byte %s lane %s previous center: %s',
                                                              eye.rank, eye.byte, eye.lane, ({delay} , {vref}))
                                        eyesInRank.append(eye)
                            else:
                                # If we're not interested in that eye, just skip over it
                                srcFile.readline()
                                srcFile.readline()
                        elif (self.dir == 'RX') and ('<<KEY>> 0 RxClkDlyTg' in line):
                            # DDR4 only: extracting RX 2D trained delay (per nibble, per rank)
                            line = srcFile.readline()
                            nib0Delays = srcFile.readline().split()
                            nib1Delays = srcFile.readline().split()
                            if len(nib0Delays) != 12 or len(nib1Delays) != 12:
                                for eye in eyesInRank:
                                    eye.trained2DDelay = eye.previousDelay
                            else:
                                nib0Delays = nib0Delays[2:]
                                nib1Delays = nib1Delays[2:]
                                for eye in eyesInRank:
                                    if eye.lane < 4:
                                        eye.trained2DDelay = str_to_int(nib0Delays[eye.byte], 16, eye.previousDelay)
                                    else:
                                        eye.trained2DDelay = str_to_int(nib1Delays[eye.byte], 16, eye.previousDelay)
                            for eye in eyesInRank:
                                if self.verbose:
                                    self.logger.debug('rank %s byte %s lane %s trained 2D delay: %s',
                                                      eye.rank, eye.byte, eye.lane, eye.trained2DDelay)
                                # DDR4: make sure the trained 2D delay (center)
                                # is set at the fixed coordinate of center_delay_2d
                                for dataPoint in eye.dataPoints:
                                    dataPoint.delay = dataPoint.delay + (eye.previousDelay - eye.trained2DDelay)
                            eyesAcrossRank += eyesInRank
                            eyesInRank = list()
                            inEyeRankSection = False
                            eyeType = ""
                        elif (self.dir == 'TX') and ('<<KEY>> 0 messageBlock VrefDqR' in line):
                            # Extracting TX 2D trained VREF (per device, per rank)
                            line = srcFile.readline()
                            # Note: for x8 and x16, the two or four nibbles connected to a device simply
                            # have the same values, so the following code should work for all modes
                            nib0Vrefs = srcFile.readline().split()
                            nib1Vrefs = srcFile.readline().split()
                            if len(nib0Vrefs) != 12 or len(nib1Vrefs) != 12:
                                for eye in eyesInRank:
                                    eye.trained2DVref = -100
                            else:
                                nib0Vrefs = nib0Vrefs[2:]
                                nib1Vrefs = nib1Vrefs[2:]
                                for eye in eyesInRank:
                                    if eye.lane < 4:
                                        eye.trained2DVref = str_to_int(nib0Vrefs[eye.byte], 16, -100)
                                    else:
                                        eye.trained2DVref = str_to_int(nib1Vrefs[eye.byte], 16, -100)
                                    if eye.trained2DVref != -100:
                                        if self.protocol == TrainedDataEye.Protocol.LPDDR4:
                                            # Convert from LPDDR4 MR14 to linearly increasing VREF
                                            if eye.trained2DVref >= 35:
                                                eye.trained2DVref = (eye.trained2DVref & 0x3F) + 30

                            for eye in eyesInRank:
                                if self.verbose:
                                    self.logger.debug('rank %s byte %s lane %s trained 2D VREF: %s',
                                                      eye.rank, eye.byte, eye.lane, eye.trained2DVref)
                        elif (self.dir == 'TX') and ('<<KEY>> 0 TxDqDlyTg' in line):
                            # Extracting TX 2D trained delay (per lane, per rank)
                            line = srcFile.readline()
                            laneDelays = list()
                            for lane in range(0, 9):
                                laneDelay = srcFile.readline().split()
                                if len(laneDelay) == 12:
                                    laneDelays.append(laneDelay[2:])
                            for eye in eyesInRank:
                                if len(laneDelays) == 9:
                                    eye.trained2DDelay = str_to_int(laneDelays[eye.lane][eye.byte], 16, -100)
                                else:
                                    eye.trained2DDelay = -100
                                if eye.trained2DDelay == -100:
                                    eye.trained2DDelay = eye.previousDelay
                                elif self.nbFineSteps == 32:
                                    # Convert to all fine steps
                                    eye.trained2DDelay = ((eye.trained2DDelay >> 6) << 5) | (eye.trained2DDelay & 0x1F)
                                if self.verbose:
                                    self.logger.debug('rank %s byte %s lane %s trained 2D delay: %s',
                                                      eye.rank, eye.byte, eye.lane, eye.trained2DDelay)
                                # DDR4: make sure the trained 2D delay (center) is set
                                # at the fixed coordinate of center_delay_2d
                                for dataPoint in eye.dataPoints:
                                    dataPoint.delay = dataPoint.delay + (eye.previousDelay - eye.trained2DDelay)
                            eyes += eyesInRank
                            eyesInRank = list()
                            inEyeRankSection = False
                            eyeType = ""
                        elif "pmu_2Dtrain()" in line:
                            # lp54 log files
                            inEyeRankSection = False
                            eyeType = ""
                    if (self.dir == 'RX') and ('<<KEY>> VrefDACs <<KEY>>' in line):
                        # Extracting RX VrefDAC trained VREF (per lane, across rank)
                        if self.rxDacOverride is not None:
                            nbDac = self.rxDacOverride
                        else:
                            nbDac = 1
                        refEyes = list()
                        for eye in eyesAcrossRank:
                            if eye.dac == nbDac:
                                refEyes.append(eye)
                        for dac in range(0, nbDac):
                            line = srcFile.readline()
                            match = re.search('ID=[0-9]+', line)
                            if not match:
                                self.logger.error(f'Badly formatted log file: could not find VrefDACs ID {dac}')
                                break
                            ID = int(match.group(0).split()[0][3:])
                            if ID != dac:
                                self.logger.error('Badly formatted log file: VrefDACs ID mismatch')
                                break
                            laneVrefs = list()
                            for lane in range(0, 9):
                                laneVref = srcFile.readline().split()
                                if len(laneVref) == 12:
                                    laneVrefs.append(laneVref[2:])
                            for eye in eyesAcrossRank:
                                if eye.dac == dac:
                                    if len(laneVrefs) == 9:
                                        eye.trained2DVref = str_to_int(laneVrefs[eye.lane][eye.byte], 16, -100)
                                        for refEye in refEyes:
                                            if dac == 0:
                                                refEye.trained2DVref = eye.trained2DVref
                                            elif dac == 1:
                                                refEye.trained2DVref1 = eye.trained2DVref
                                            elif dac == 2:
                                                refEye.trained2DVref2 = eye.trained2DVref
                                            elif dac == 3:
                                                refEye.trained2DVref3 = eye.trained2DVref
                                    else:
                                        eye.trained2DVref = -100
                                    if self.verbose:
                                        self.logger.debug('rank %s byte %s lane %s VrefDAC %s trained 2D VREF: %s',
                                                          eye.rank, eye.byte, eye.lane, eye.dac, eye.trained2DVref)
                        eyes += eyesAcrossRank
                        eyesAcrossRank = list()
                eyes += eyesAcrossRank + eyesInRank
            else:
                self.logger.error('Scanning Diag binary file is not supported yet!')
        except IOError as err:
            self.logger.error(err)
            traceback.print_exc()

        try:
            srcFile.close()
        except IOError as err:
            self.logger.error(err)
            traceback.print_exc()

        # Filter out intermediate DFE eyes
        if self.dir == 'RX':
            if not self.showAllEyes:
                maxDac = -1
                for eye in eyes:
                    maxDac = max(maxDac, eye.dac)
                filteredEyes = list()
                for eye in eyes:
                    if (eye.dac == maxDac) or (eye.dac == -1):
                        filteredEyes.append(eye)
                eyes = filteredEyes

        # Print all found eyes for debug purposes
        if self.verbose:
            print('Found', len(eyes), 'eyes' if len(eyes) > 1 else 'eye')
            for eye in eyes:
                print('Printing', self.dir, 'eye for rank', eye.rank, ' byte', eye.byte, ' lane', eye.lane, ':')
                for entry in eye.maxVrefs:
                    print('{:4d}'.format(entry), end='')
                print('')
                for entry in eye.minVrefs:
                    print('{:4d}'.format(entry), end='')
                print('\n')

        for eye in eyes:
            sumLnDlyWidth = 0
            sumLnVrefWidth = 0
            sumLnWidth = 0
            for dir in range(0, 2):
                if dir == 0:
                    # Go around the eye: start with bottom (min) part
                    startDelayIndex = 0
                    endDelayIndex = len(eye.dataPoints) - 1
                    incDelay = 1
                else:
                    # And finish with top (max) part
                    startDelayIndex = len(eye.dataPoints) - 1
                    endDelayIndex = 0
                    incDelay = -1
                for i in range(0, len(eye.dataPoints)):
                    delayIndex = (i * incDelay) + startDelayIndex
                    xi = eye.dataPoints[delayIndex].delay
                    if dir == 0:
                        yi = eye.dataPoints[delayIndex].minVref
                    else:
                        yi = eye.dataPoints[delayIndex].maxVref
                    if delayIndex == endDelayIndex:
                        xip = eye.dataPoints[delayIndex].delay
                        if dir == 0:
                            yip = eye.dataPoints[delayIndex].maxVref
                        else:
                            yip = eye.dataPoints[delayIndex].minVref
                    else:
                        xip = eye.dataPoints[delayIndex + incDelay].delay
                        if dir == 0:
                            yip = eye.dataPoints[delayIndex + incDelay].minVref
                        else:
                            yip = eye.dataPoints[delayIndex + incDelay].maxVref
                    diffWidth = (xi * yip) - (xip * yi)
                    sumLnDlyWidth = sumLnDlyWidth + ((xi + xip) * diffWidth)
                    sumLnVrefWidth = sumLnVrefWidth + ((yi + yip) * diffWidth)
                    sumLnWidth = sumLnWidth + (3 * diffWidth)
            if sumLnWidth != 0:
                eye.centroidX = int(sumLnDlyWidth / sumLnWidth)
                eye.centroidY = int(sumLnVrefWidth / sumLnWidth)

        plots: list[list[Eye2D]] = list()
        if self.layoutMode == 'basic':
            for eye in eyes:
                wasAppended = False
                if self.mergeRuns:
                    # Check if eyes already has a plot for this particular lane. If yes,
                    # we add this eye to the plot in order to show a merged view.
                    for plot in plots:
                        for eye2 in plot:
                            if (eye.rank == eye2.rank) and (eye.byte == eye2.byte) and (eye.lane == eye2.lane):
                                plot.append(eye)
                                wasAppended = True
                                break
                if not wasAppended:
                    plots.append([eye])
        elif self.layoutMode == 'byte':
            for rank in range(0, 4):
                for byte in range(0, 10):
                    eyesInPlot: list[Eye2D] = list()
                    for eye in eyes:
                        if (eye.rank == rank) and (eye.byte == byte):
                            if not self.mergeRuns:
                                # Check if eyesInPlot already has an eye for this particular lane. We do this
                                # to support logs with multiple 2D runs, in order to show 1 plot per byte, per run.
                                for eyeInPlot in eyesInPlot:
                                    if eyeInPlot.lane == eye.lane:
                                        plots.append(eyesInPlot)
                                        eyesInPlot = list()
                            eye.legendTitle += '\n    Lane' + str(eye.lane)
                            eyesInPlot.append(eye)
                    if len(eyesInPlot) > 0:
                        plots.append(eyesInPlot)
        elif self.layoutMode == 'nibble':
            for rank in range(0, 4):
                for byte in range(0, 10):
                    for nibble in range(0, 8, 4):
                        eyesInPlot = list()
                        for eye in eyes:
                            if (eye.rank == rank) and (eye.byte == byte) and (eye.lane >= nibble) and (
                                    eye.lane < (nibble + 4)):
                                if not self.mergeRuns:
                                    # Check if eyesInPlot already has an eye for this particular lane.
                                    # We do this to support logs with multiple 2D runs,
                                    # in order to show 1 plot per nibble, per run.
                                    for eyeInPlot in eyesInPlot:
                                        if eyeInPlot.lane == eye.lane:
                                            plots.append(eyesInPlot)
                                            eyesInPlot = list()
                                eye.legendTitle += '\n    Lane' + str(eye.lane)
                                eyesInPlot.append(eye)
                        if len(eyesInPlot) > 0:
                            plots.append(eyesInPlot)
        elif self.layoutMode == 'rank':
            for byte in range(0, 10):
                for lane in range(0, 9):
                    eyesInPlot = list()
                    for eye in eyes:
                        if (eye.byte == byte) and (eye.lane == lane):
                            if not self.mergeRuns:
                                # Check if eyesInPlot already has an eye for this particular rank. We do this
                                # to support logs with multiple 2D runs, in order to show 1 plot per lane, per run.
                                for eyeInPlot in eyesInPlot:
                                    if eyeInPlot.rank == eye.rank:
                                        plots.append(eyesInPlot)
                                        eyesInPlot = list()
                            eye.legendTitle += '\n   Rank' + str(eye.rank)
                            eyesInPlot.append(eye)
                    if len(eyesInPlot) > 0:
                        plots.append(eyesInPlot)

        # Hide matplot log
        if Const.HIDE_DETAILED_DEBUG_INFO:
            matplotlib_logger = logging.getLogger('matplotlib')
            if matplotlib_logger:
                matplotlib_logger.setLevel(logging.ERROR)

        # Create one figure with multiple subplots
        # The subplots will be organized as a NxN grid
        nbRows = math.ceil(math.sqrt(len(plots)))
        nbCols = nbRows
        fig = DiagEyeFigure(nbCols, nbRows)
        fig.subplots_adjust(hspace=0.5)

        plotIdx = 1
        #hasPreviousCenter = False
        for plot in plots:
            ax = fig.add_subplot(nbRows, nbCols, plotIdx)
            plotIdx = plotIdx + 1  # This created N plots
            ax.set_xlabel('delay')
            ax.set_ylabel('voltage')
            ax.set_xlim(0, self.range_delay_2d)
            ax.set_xticks(np.arange(0, self.range_delay_2d + 1, 4), minor=False)
            ax.set_xticks(np.arange(0, self.range_delay_2d + 1, 1), minor=True)
            if self.dir == 'TX':
                ax.set_ylim(0, 128)
            else:
                ax.set_ylim(0, 128)
            ax.grid(True, which='major')

            refEye = plot[0]
            if self.layoutMode == 'basic':
                ax.set_title(
                    self.dir + refEye.eyeType + ' Rank' + str(refEye.rank) + ' DB' + str(refEye.byte) + ' Lane' + str(
                        refEye.lane))
            elif self.layoutMode == 'byte':
                ax.set_title(self.dir + refEye.eyeType + ' Rank' + str(refEye.rank) + ' DB' + str(refEye.byte))
            elif self.layoutMode == 'nibble':
                ax.set_title(
                    self.dir + refEye.eyeType + ' Rank' + str(refEye.rank) + ' DB' + str(refEye.byte) + ' Nibble' + (
                        '0' if refEye.lane < 4 else '1'))
            elif self.layoutMode == 'rank':
                ax.set_title(self.dir + refEye.eyeType + ' DB' + str(refEye.byte) + ' Lane' + str(refEye.lane))
            if anchorDelay is not None:
                # LPDDR54 log
                minX = refEye.trained2DDelay - self.range_delay_2d / 2
                maxX = refEye.trained2DDelay + self.range_delay_2d / 2
                ax.set_xlim(minX, maxX)
                if maxX >= 100:
                    # 3 digit values on the x-axis need more room
                    numMajor = 8
                else:
                    numMajor = 4
                ax.set_xticks(np.arange(minX, maxX + 1, numMajor), minor=False)
                ax.set_xticks(np.arange(minX, maxX + 1, 1), minor=True)

            colorOffset = 1.0
            for eye in plot:
                delays = list()
                minVrefs = list()
                maxVrefs = list()
                for dataPoint in eye.dataPoints:
                    delays.append(dataPoint.delay + (eye.trained2DDelay - refEye.trained2DDelay))
                    minVrefs.append(dataPoint.minVref)
                    maxVrefs.append(dataPoint.maxVref)

                # Upper eye: X: delay ; Y:maxVrefs
                eye.topHandle = ax.plot(delays, maxVrefs, 'o-', color=(colorOffset, 0, 0))
                plt.setp(eye.topHandle, markersize=5)

                # Lower eye: X: delay ; Y:minVrefs
                eye.bottomHandle = ax.plot(delays, minVrefs, 'o-', color=(0, 0, colorOffset))
                plt.setp(eye.bottomHandle, markersize=5)

                if (not self.is_phy_v3) and self.protocol == TrainedDataEye.Protocol.LPDDR4 and (not eye.isDiagEye):
                    (eye.previousCenterHandle,) = ax.plot(
                        self.center_delay_2d + (eye.previousDelay - refEye.trained2DDelay),
                        eye.previousVref, 'x', label='previous center', color=str(1 - colorOffset))
                    plt.setp(eye.previousCenterHandle, markersize=10)
                    #hasPreviousCenter = True
                if self.is_phy_v3:
                    (eye.trained2DCenterHandle,) = ax.plot(eye.trained2DDelay, eye.trained2DVref, '+',
                        label='trained 2D center', color=(colorOffset, 0, 0))
                else:
                    (eye.trained2DCenterHandle,) = ax.plot(
                        self.center_delay_2d + (eye.trained2DDelay - refEye.trained2DDelay),
                        eye.trained2DVref, '+', label='trained 2D center', color=(colorOffset, 0, 0))
                plt.setp(eye.trained2DCenterHandle, markersize=15)
                if eye.trained2DVref1 >= 0:
                    (eye.trained2DCenterHandle1,) = ax.plot(
                        self.center_delay_2d + (eye.trained2DDelay - refEye.trained2DDelay),
                        eye.trained2DVref1, 's', label='trained 2D center (DAC1)', color=(colorOffset, 0, 0))
                    plt.setp(eye.trained2DCenterHandle1, markersize=5)
                if eye.trained2DVref2 >= 0:
                    (eye.trained2DCenterHandle2,) = ax.plot(
                        self.center_delay_2d + (eye.trained2DDelay - refEye.trained2DDelay),
                        eye.trained2DVref2, '*', label='trained 2D center (DAC2)', color=(colorOffset, 0, 0))
                    plt.setp(eye.trained2DCenterHandle2, markersize=10)
                if eye.trained2DVref3 >= 0:
                    (eye.trained2DCenterHandle3,) = ax.plot(
                        self.center_delay_2d + (eye.trained2DDelay - refEye.trained2DDelay), eye.trained2DVref3, 'd',
                        label='trained 2D center (DAC3)', color=(colorOffset, 0, 0))
                    plt.setp(eye.trained2DCenterHandle3, markersize=7)
                (eye.centroidCenterHandle,) = ax.plot(eye.centroidX + (eye.trained2DDelay - refEye.trained2DDelay),
                    eye.centroidY, '.', label='eye centroid', color=(0, colorOffset / 2, 0))
                plt.setp(eye.centroidCenterHandle, markersize=10)
                colorOffset -= 1.0 / len(plot)

        if len(plots) > 0:
            # We assume that all plots have the same number of eyes, therefore we don't need a
            # separate legend for every plot. Instead, we create N legends (one for every eye
            # in a plot) that we draw at the bottom of the figure (if more than one legend) or
            # at the right (if only one legend)
            refPlot = plots[0]
            xOffset = 0.0
            yOffset = 0.0
            for eye in refPlot:
                handles = list()
                if eye.previousCenterHandle is not None:
                    handles.append(eye.previousCenterHandle)
                if eye.trained2DCenterHandle is not None:
                    handles.append(eye.trained2DCenterHandle)
                if eye.trained2DCenterHandle1 is not None:
                    handles.append(eye.trained2DCenterHandle1)
                if eye.trained2DCenterHandle2 is not None:
                    handles.append(eye.trained2DCenterHandle2)
                if eye.trained2DCenterHandle3 is not None:
                    handles.append(eye.trained2DCenterHandle3)
                if eye.centroidCenterHandle is not None:
                    handles.append(eye.centroidCenterHandle)
                if not self.noLegend:
                    if len(refPlot) == 1:
                        # help(fig.legend)
                        legend = fig.legend(handles=handles, labels=["Trained", "Center"], loc='right')
                    else:
                        legend = fig.legend(handles=handles, labels=["Trained", "Center"], loc=(xOffset, yOffset),
                            fontsize='x-small')
                    titleProp = fm.FontProperties(size='x-small')
                    legend.set_title(eye.legendTitle, titleProp)

                if len(refPlot) > 8:
                    xOffset += 0.9 / len(refPlot)
                elif len(refPlot) > 4:
                    xOffset += 0.12
                else:
                    xOffset += 0.20

            if fig is not None:
                fig.savefig(self.pngFile)
                self.config_data.params[Const.PARAM_S_TC]['diag_image_file'] = self.pngFile
            else:
                self.config_data.params[Const.PARAM_S_TC]['diag_image_file'] = None


class EyeData:
    """Class for parsing and saving diags and CA eye data."""

    logger = logging.getLogger(__name__)

    # Minimum value of test result from which a test is considered failed
    PASSED_TEST_VALUE = 1

    parsed_cs = set()  # type: ignore
    current_cs = ''
    num_rows = 0
    num_cols = 0

    def __init__(self):  # type: ignore
        """Constructor."""
        self.data: list[list[str]] = []  # type: ignore
        self.cs = ''
        self.x_axis = []  # type: ignore
        self.y_axis: list[str] = []  # type: ignore
        self.center_x = 0
        self.center_y: int | float = 0  # type: ignore
        self.dq = 0
        self.byte = 0
        self.bit = 0
        self.height: int | float = 0  # type: ignore
        self.width: int | float = 0  # type: ignore
        # Set matplotlib logger level to ERROR because when DEBUG log level is set for tests,
        # output of logger is flooded with matpotlib debug font messages.
        if Const.HIDE_DETAILED_DEBUG_INFO:
            matplotlib_logger = logging.getLogger('matplotlib')
            if matplotlib_logger:
                matplotlib_logger.setLevel(logging.ERROR)

    @classmethod
    def clear(cls) -> None:
        """Reset class members values to avoid data from a previous test being used."""
        cls.parsed_cs = set()
        cls.current_cs = ''
        cls.num_rows = 0
        cls.num_cols = 0

    def is_empty(self) -> bool:
        """Weather or not data for an eye was collected."""
        return len(self.data) == 0

    def add_diag_line(self, new_line: str) -> None:
        """Parse a log line to extract Diag data."""
        if 'CS:' in new_line:
            self.center_x = int(new_line.split()[9])
            self.center_y = float(new_line.split()[5])
        elif 'DQ:' in new_line:
            data_str = new_line.replace('(', '').replace(')', '').split()
            self.dq = int(data_str[2])
            self.byte = int(data_str[4])
            self.bit = int(data_str[7])
        elif 'H:' in new_line:
            self.height = float(new_line.split()[2])
            self.width = float(new_line.split()[6])
        elif 'VREF(V)' in new_line:
            self.x_axis = new_line.split('|')[1:]
        elif '|' in new_line:
            data_str = new_line.replace("XXXXX", '0').split('|')
            self.y_axis.insert(0, data_str[0])
            self.data.insert(0, data_str[1:])

    def get_diag_x_axis(self, delay_precision: int) -> Tuple[list, list]:
        """Get x axis labels for Diags graph.

        @param delay_precision: delay precision (also known as size of unit interval)
        @return: tuple of ticks and associated labels for x axis
        """
        center = 0
        idx = 0
        for step in self.x_axis:
            if int(self.center_x) <= int(step):
                center = idx
                break
            idx = idx + 1
        x_ticks = []
        x_labels = []
        if center - int(delay_precision / 2) >= 0:
            x_ticks.append(int(self.x_axis[center - int(delay_precision / 2)]))
            x_labels.append('-50%')
        if center - int(delay_precision / 4) >= 0:
            x_ticks.append(int(self.x_axis[center - int(delay_precision / 4)]))
            x_labels.append('-25%')
        x_ticks.append(int(self.x_axis[center]))
        x_labels.append('0')
        if center + int(delay_precision / 4) - 1 < len(self.x_axis):
            x_ticks.append(int(self.x_axis[center + int(delay_precision / 4) - 1]))
            x_labels.append('25%')
        if center + int(delay_precision / 2) - 1 < len(self.x_axis):
            x_ticks.append(int(self.x_axis[center + int(delay_precision / 2) - 1]))
            x_labels.append('50%')

        return x_ticks, x_labels

    def get_diag_y_axis(self) -> list:
        """Get y axis labels for Diags graph."""
        center = 0
        idx = 0
        for vref in self.y_axis:
            if float(self.center_y) >= float(vref):
                center = idx
                break
            idx = idx + 1
        y_ticks = []
        if center - int(len(self.y_axis) / 2) >= 0:
            y_ticks.append(float(self.y_axis[center - int(len(self.y_axis) / 2)]))
        if center - int(len(self.y_axis) / 4) >= 0:
            y_ticks.append(float(self.y_axis[center - int(len(self.y_axis) / 4)]))
        y_ticks.append(float(self.y_axis[center]))
        if center + int(len(self.y_axis) / 4) < len(self.y_axis):
            y_ticks.append(float(self.y_axis[center + int(len(self.y_axis) / 4)]))
        if center + int(len(self.y_axis) / 2) < len(self.y_axis):
            y_ticks.append(float(self.y_axis[center + int(len(self.y_axis) / 2)]))

        return y_ticks

    @classmethod
    def get_diag_nb_graphs(cls, size: int, config_data: ConfigData) -> tuple[int, int]:
        """Get number of rows and columns in eye data."""
        if size == 1:
            return 1, 1

        if config_data.dbi_enabled:
            no_bits_per_line = 9
        else:
            no_bits_per_line = 8
        return max(int(size / no_bits_per_line), 1), min(no_bits_per_line, size)

    @staticmethod
    def remove_isolated_passed_tests(eye_data) -> None:  # type: ignore
        """Remove isolated passed tests."""
        # If all neighbors are failed they are not reachable from the center and
        # should not be considered when passed ranges for vref are computed
        max_y = len(eye_data.y_axis)
        for y_idx in range(max_y):
            max_x = len(eye_data.data[y_idx])
            for x_idx in range(max_x):
                if int(eye_data.data[y_idx][x_idx]) in range(EyeData.PASSED_TEST_VALUE):
                    neighbors = ((x_idx, y_idx - 1), (x_idx + 1, y_idx), (x_idx, y_idx + 1), (x_idx - 1, y_idx))
                    max_ck = 4
                    ck = 0
                    for n in neighbors:
                        if 0 <= n[0] < max_x and 0 <= n[1] < max_y:
                            if int(eye_data.data[n[1]][n[0]]) not in range(EyeData.PASSED_TEST_VALUE):
                                ck += 1
                        else:
                            max_ck -= 1
                    if ck == max_ck:
                        eye_data.data[y_idx][x_idx] = '255'  # ignore isolated passed tests

    @staticmethod
    def get_line_passed_range_for_point(line_data: list, center_x: int) -> Tuple[int, int]:
        """Compute the limits of the interval containing passed tests, starting from center_x."""
        lp_x_idx = rp_x_idx = -1
        for x_idx in reversed(range(center_x)):
            if int(line_data[x_idx]) not in range(EyeData.PASSED_TEST_VALUE):
                lp_x_idx = x_idx + 1
                break
        for x_idx in range(center_x + 1, len(line_data)):
            if int(line_data[x_idx]) not in range(EyeData.PASSED_TEST_VALUE):
                rp_x_idx = x_idx - 1
                break
        return lp_x_idx, rp_x_idx

    @staticmethod
    def get_line_passed_ranges_accessible_from_ranges(line_data: list, acs_ranges: list) -> list:
        """Compute all ranges accessible starting from a set of ranges."""
        pass_ranges_x_idx = []
        for acs_range in acs_ranges:
            if int(line_data[acs_range[0]]) in range(EyeData.PASSED_TEST_VALUE):
                l_limit = acs_range[0] - 1
                while l_limit >= 0:
                    if int(line_data[l_limit]) in range(EyeData.PASSED_TEST_VALUE):
                        l_limit -= 1
                    else:
                        break
            else:
                l_limit = acs_range[0]
            l_limit = max(l_limit, 0)

            if int(line_data[acs_range[1]]) in range(EyeData.PASSED_TEST_VALUE):
                r_limit = acs_range[1] + 1
                while r_limit < len(line_data):
                    if int(line_data[r_limit]) in range(EyeData.PASSED_TEST_VALUE):
                        r_limit += 1
                    else:
                        break
            else:
                r_limit = acs_range[1]
            r_limit = min(r_limit, len(line_data) - 1)

            lp_x_idx = rp_x_idx = -1
            for x_idx in range(l_limit, r_limit + 1):
                if int(line_data[x_idx].strip()) in range(EyeData.PASSED_TEST_VALUE):
                    if lp_x_idx < 0:
                        lp_x_idx = x_idx
                    rp_x_idx = x_idx
                else:
                    if lp_x_idx >= 0:
                        pass_ranges_x_idx.append((lp_x_idx, rp_x_idx))
                        lp_x_idx = -1
                        rp_x_idx = -1
        return pass_ranges_x_idx

    @staticmethod
    def compute_overlay_data_eye(eye_data):  # type: ignore
        """Load pre-trained data and compute overlay eye data."""
        max_y = len(eye_data.y_axis)

        center_y_idx = -1
        center_y_value = float(eye_data.center_y)
        for y_idx in range(max_y):  # max vref is at y_idx = 0!
            if float(eye_data.y_axis[y_idx]) <= center_y_value:
                center_y_idx = y_idx
                break

        if center_y_idx < 0:
            EyeData.logger.error(f"[DQ {eye_data.dq}] Eye center not found! Check PHY diagnostic data!")
            return []

        center_line_data = eye_data.data[center_y_idx]
        center_x_idx = eye_data.center_x - int(eye_data.x_axis[0])
        center_range = EyeData.get_line_passed_range_for_point(center_line_data, center_x_idx)
        ranges = [[(center_range[0], center_range[1], center_y_idx, float(eye_data.y_axis[center_y_idx]))]]

        y_idx = center_y_idx + 1
        while y_idx < max_y:
            next_line_data = eye_data.data[y_idx]
            limits = []
            for r in ranges[0]:
                limits.append(r[0])
                limits.append(r[1])
            if len(limits) > 2:
                for limit_index in range(1, len(limits) - 1, 2):
                    for idx in range(limits[limit_index] + 1, limits[limit_index + 1]):
                        if next_line_data[idx].strip() == '0':
                            next_line_data[idx] = '255'

            next_line_ranges = EyeData.get_line_passed_ranges_accessible_from_ranges(next_line_data, ranges[0])
            if len(next_line_ranges) == 0:
                break
            line_ranges = []
            for r in next_line_ranges:
                line_ranges.append((r[0], r[1], y_idx, float(eye_data.y_axis[y_idx])))
            ranges.insert(0, line_ranges)
            y_idx += 1

        y_idx = center_y_idx - 1
        while y_idx >= 0:
            next_line_data = eye_data.data[y_idx]
            limits = []
            for r in ranges[-1]:
                limits.append(r[0])
                limits.append(r[1])
            if len(limits) > 2:
                for limit_index in range(1, len(limits) - 1, 2):
                    for idx in range(limits[limit_index] + 1, limits[limit_index + 1]):
                        if next_line_data[idx].strip() == '0':
                            next_line_data[idx] = '255'

            next_line_ranges = EyeData.get_line_passed_ranges_accessible_from_ranges(next_line_data, ranges[-1])
            if len(next_line_ranges) == 0:
                break
            line_ranges = []
            for r in next_line_ranges:
                line_ranges.append((r[0], r[1], y_idx, float(eye_data.y_axis[y_idx])))
            ranges.append(line_ranges)
            y_idx -= 1

        if not Const.HIDE_DETAILED_DEBUG_INFO:
            print(f'Diags eye {eye_data.dq} range:')
            for r in ranges:
                print(r)

        overlay_eye_data = []  # type: ignore
        tap_delay_margin = len(eye_data.x_axis) / 2
        delay_precision = 32 if tap_delay_margin < 20 else 64
        ui_margin_right = 50
        ui_margin_left = -50
        buffer = 2  # so that the points on the margins aren't exactly on the chart margins

        for line_ranges in ranges:
            y_value_range = line_ranges[0][3]
            lp_range = line_ranges[0][0]
            rp_range = line_ranges[-1][1]
            lp_tap_delay = lp_range - center_x_idx
            rp_tap_delay = rp_range - center_x_idx

            lp_ui_percentage = (lp_tap_delay / delay_precision) * 100.0
            if lp_ui_percentage <= ui_margin_left:
                # keep it even because the html templates have ticks every 2 units
                ui_margin_left = int(lp_ui_percentage - buffer) - int(lp_ui_percentage) % 2

            rp_ui_percentage = (rp_tap_delay / delay_precision) * 100.0
            if rp_ui_percentage >= ui_margin_right:
                # keep it even because the html templates have ticks every 2 units
                ui_margin_right = int(rp_ui_percentage + buffer) + int(rp_ui_percentage) % 2

            lp = {"ps": 0, "td": lp_tap_delay, "ui": lp_ui_percentage, "y": y_value_range}
            overlay_eye_data.insert(0, lp)
            rp = {"ps": 0, "td": rp_tap_delay, "ui": rp_ui_percentage, "y": y_value_range}
            overlay_eye_data.append(rp)

        cp = {"ps": 0, "td": 0, "ui": 0, "y": eye_data.center_y}
        overlay_eye_data.append(cp)

        overlay_eye = {
            "data": overlay_eye_data, "byte": eye_data.byte, "bit": eye_data.bit,
            "tp_margin": tap_delay_margin, "ui_margin": [ui_margin_left, ui_margin_right],
            "label": f"DQ: {eye_data.dq}"
        }
        return overlay_eye

    @staticmethod
    def compute_eye_list(file_name: str) -> list:
        """Parse diagnostic data and create data eyes list."""
        eye_list = []
        with open(file_name, 'rt', encoding="utf-8") as f:
            line = f.readline()
            eye_data = EyeData()
            while line:
                if line[0] == '-' and not eye_data.is_empty():
                    eye_list.append(eye_data)
                    eye_data = EyeData()
                else:
                    eye_data.add_diag_line(line)

                line = f.readline()

            eye_list.append(eye_data)
        return eye_list

    @staticmethod
    def show_diag_data_eyes_plots(eye_list: list, config_data: ConfigData) -> DiagEyeFigure:
        """Create Diag Eye figure."""
        delay_precision = 32 if ConfigData.is_phy_v2(config_data.snps_phy_info) else 64
        n_rows, n_cols = EyeData.get_diag_nb_graphs(len(eye_list), config_data)
        fig = DiagEyeFigure(n_cols, n_rows)

        idx = 1
        for eye_data in eye_list:
            ax = fig.add_subplot(n_rows, n_cols, idx)

            # (r, g, b, a) are floats in range [0, 1].
            r1, g1, b1 = hex2color(Const.COLOR_HEX_GREEN)
            r2, g2, b2 = hex2color(Const.COLOR_HEX_BROWN)
            color_channels_size = 256  # channel size
            color_channels = np.ones((color_channels_size, 4))  # (r, g, b, a) channels
            color_channels[:, 0] = np.linspace(r1, r2, color_channels_size)  # red channel
            color_channels[:, 1] = np.linspace(g1, g2, color_channels_size)  # green channel
            color_channels[:, 2] = np.linspace(b1, b2, color_channels_size)  # blue channel
            # color_channels[:, 3] - alpha channel
            color_map = ListedColormap(color_channels)  # color map that goes from (r1, g1, b1) to (r2, g2, b2)

            ax.imshow(np.array(eye_data.data, 'i'), cmap=color_map,  # interpolation='bilinear',
                      aspect='auto', extent=(float(eye_data.x_axis[0]), float(eye_data.x_axis[-1]),
                                             float(eye_data.y_axis[-1]), float(eye_data.y_axis[0])))

            _x_ticks, _x_labels = eye_data.get_diag_x_axis(delay_precision)
            ax.set_xticks(_x_ticks)
            ax.set_xticklabels(_x_labels)

            _y_ticks = eye_data.get_diag_y_axis()
            ax.set_yticks(_y_ticks)
            ax.set_yticklabels([f'{tick}V' for tick in ax.get_yticks()], rotation=45)

            ax.grid(linestyle='dotted', linewidth=0.5)
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontsize(6)

            title = f"""DQ{eye_data.dq}
Center(Dly={eye_data.center_x - int(eye_data.x_axis[0])}\\{delay_precision}UI,Vref={eye_data.center_y}V)
"""
            # subplot title
            ax.set_title(title, size=10)

            # subplot labels
            ax.set_xlabel(f'Eye width={eye_data.width}%UI', fontsize=8)

            y_label = f"""Eye height={eye_data.height}V
(min={eye_data.y_axis[-1].strip()}V,max={eye_data.y_axis[0].strip()}V)
"""
            ax.set_ylabel(y_label, fontsize=8)

            ax.scatter(eye_data.center_x, eye_data.center_y, s=100, c='white', marker='+')

            idx = idx + 1

        return fig

    @staticmethod
    def compute_overlay_eyes(eye_list: list) -> list:
        """Generate overlay data eyes data."""
        overlay_data = []
        for eye_data in eye_list:
            overlay_data.append(EyeData.compute_overlay_data_eye(eye_data))
        return overlay_data

    @staticmethod
    def add_phy_v2_ca_bus_line(new_line: str) -> Optional['EyeData']:
        """Parse a log line to extract CA data."""
        new_line = new_line.strip()
        if "[1] PMU5: CA bitmap dump for cs" in new_line:
            data_str: str | list[str] = new_line.split(' ')
            EyeData.current_cs = f'{data_str[-2]}{data_str[-1]}'.upper()
            EyeData.parsed_cs.add(EyeData.current_cs)
        elif "[1] PMU5: CA" in new_line:
            eye_data = EyeData()
            eye_data.cs = EyeData.current_cs
            data_str = new_line[new_line.find(':') + 1:]
            data_str = data_str.replace("[1]", "").strip()
            data_str = data_str.split(' ')
            eye_data.y_axis.append(f'{data_str[0]}')

            ca_data: list[str] = []
            for d in data_str[2:]:
                b = ((bin(int(d, 16)))[2:]).zfill(8)
                for idx in range(8):
                    if len(ca_data) > 0 and ca_data[-1] != b[idx]:
                        eye_data.x_axis.append(len(ca_data))
                    ca_data.append(b[idx])

            eye_data.data.append(ca_data)
            return eye_data

        return None

    @staticmethod
    def add_phy_v3_ca_bus_line(new_line: str) -> Optional['EyeData']:
        """Parse a log line to extract CA data."""
        new_line = new_line.strip()
        if "[1] PMU4: Channel" in new_line:
            data_str: str | list[str] = new_line.split(' ')
            EyeData.current_cs = f'{data_str[3]}'
            EyeData.parsed_cs.add(EyeData.current_cs)
            # WA: for now, in current CS we'll store eye label until we'll clarify
            # if both rising/falling edge eyes are needed
            EyeData.current_cs = f'Channel {data_str[3]} {data_str[7]} edge of rank {data_str[13]}'
        elif ("[1] PMU4: CAA" in new_line) or ("[1] PMU4: CAB" in new_line):
            eye_data = EyeData()
            eye_data.cs = EyeData.current_cs
            data_str = new_line[new_line.find(':') + 1:]
            data_str = data_str.replace("[1]", "").strip()
            data_str = data_str.split(' ')
            eye_data.y_axis.append(f'{data_str[0]}')

            ca_data: list[str] = []
            for d in data_str[2:]:
                b = ((bin(int(d, 16)))[2:]).zfill(8)
                for idx in range(8):
                    if len(ca_data) > 0 and ca_data[-1] != b[idx]:
                        eye_data.x_axis.append(len(ca_data))
                    ca_data.append(b[idx])

            eye_data.data.append(ca_data)
            return eye_data

        return None

    @staticmethod
    def load_phy_v2_pretrained_data(file_name: str, ui: int):  # type: ignore
        """Load pre-trained data."""
        eye_list = []
        with open(file_name, 'rt', encoding="utf-8") as f:

            eye_lines = []
            line = f.readline()
            while line:
                if line.startswith("[1] End of CA training"):
                    break
                eye_line = EyeData.add_phy_v2_ca_bus_line(line)
                if eye_line is not None:
                    eye_line.x_axis.insert(0, 0)
                    eye_line.x_axis.append(4 * ui)
                    eye_lines.append(eye_line)
                elif len(eye_lines) != 0:
                    eye_list.append(eye_lines)
                    eye_lines = []
                line = f.readline()
            if len(eye_lines) != 0:
                eye_list.append(eye_lines)
        return eye_list

    @staticmethod
    def load_phy_v3_pretrained_data(file_name: str, ui: int):  # type: ignore
        """Load pre-trained data."""
        eye_list = []
        with open(file_name, 'rt', encoding="utf-8") as f:
            eye_lines = []
            line = f.readline()
            while line:
                if line.startswith("[1] End of CA training"):
                    break
                eye_line = EyeData.add_phy_v3_ca_bus_line(line)
                if eye_line is not None:
                    eye_line.x_axis.insert(0, 0)
                    eye_line.x_axis.append(4 * ui)
                    eye_lines.append(eye_line)
                elif len(eye_lines) != 0:
                    eye_list.append(eye_lines)
                    eye_lines = []
                line = f.readline()
            if len(eye_lines) != 0:
                eye_list.append(eye_lines)
        return eye_list

    @staticmethod
    def show_ca_bus_eyes_plots(file_name: str, test: CABusSignalsMargin, soc: Optional[str] = None,
                               is_phy_v2: Optional[bool] = True) -> Optional[CABusEyeFigure]:
        """Parse log file and create CA Eye figure."""
        anibs = [int(a) for a in test.get_results().get("records")[0].get("data")[1:-1].split(',')]  # type: ignore

        # load pre-trained data
        if is_phy_v2:
            ui = 32
            eye_list = EyeData.load_phy_v2_pretrained_data(file_name, ui)
        else:
            ui = 64
            eye_list = EyeData.load_phy_v3_pretrained_data(file_name, ui)

        EyeData.num_cols = len(EyeData.parsed_cs)
        if EyeData.num_cols == 0:
            PhyTrainingTest.logger.error("CA data is missing!")
            return None

        EyeData.num_rows = int(len(eye_list) / EyeData.num_cols) * (
            2 if test.config_data.show_ca_pretrained_data else 1)
        fig = CABusEyeFigure(EyeData.num_cols, EyeData.num_rows)

        # display pre training data
        if test.config_data.show_ca_pretrained_data:
            eye_idx = 1
            for eye_data in eye_list:
                ax = fig.add_subplot(EyeData.num_rows, EyeData.num_cols, eye_idx)

                eye_line_idx = 1
                cs = ''
                ticks = []
                labels = []
                for eye_line in eye_data:
                    cs = eye_line.cs
                    x_idx = 0
                    while x_idx < len(eye_line.x_axis) - 1:
                        bar_color = Const.COLOR_HEX_BROWN if (x_idx % 2 == 0) else Const.COLOR_HEX_GREEN
                        bar_len = eye_line.x_axis[x_idx + 1] - eye_line.x_axis[x_idx]
                        ax.barh(eye_line_idx, bar_len, left=eye_line.x_axis[x_idx], align='center', color=bar_color)
                        x_idx += 1

                    ticks.append(eye_line_idx)
                    labels.append(eye_line.y_axis[0])
                    eye_line_idx = eye_line_idx + 1

                if is_phy_v2:
                    ch = chr(ord('A') + int((eye_idx - 1) / EyeData.num_cols))
                    ax.set_title('Channel ' + ch + ' - ' + cs + ' (PreTrain)')
                else:
                    ax.set_title(cs + ' (PreTrain)')

                ax.set_yticks(ticks, labels)
                ax.invert_yaxis()

                ax.axline((2 * ui, 0), (2 * ui, 5), linewidth=1.0, color='grey')
                ax.set_xticks([0, ui, 2 * ui, 3 * ui, 4 * ui], ['-100%(UI)', '-50%(UI)', '0', '50%(UI)', '100%(UI)'])
                eye_idx = eye_idx + 1

        if is_phy_v2:
            if soc is not None and ConfigData.DEVICES_INFO[soc].is_imx9():
                EyeData.compute_post_trained_mx93(eye_list, anibs)
            else:
                EyeData.compute_post_trained_mx8(eye_list, anibs)
        else:
            EyeData.compute_post_trained_mx95(eye_list, anibs)

        # display post training data
        if is_phy_v2:
            eye_idx = 1
            start_idx = len(eye_list) if test.config_data.show_ca_pretrained_data else 0
            for eye_data in eye_list:
                ax = fig.add_subplot(EyeData.num_rows, EyeData.num_cols, start_idx + eye_idx)

                eye_line_idx = 1
                cs = ''
                ticks = []
                labels = []
                for eye_line in eye_data:
                    cs = eye_line.cs

                    eye_line.x_axis[0] = 0
                    eye_line.x_axis[-1] = 4 * ui

                    x_idx = 0
                    while x_idx < len(eye_line.x_axis) - 1:
                        bar_color = Const.COLOR_HEX_BROWN if (x_idx % 2 == 0) else Const.COLOR_HEX_GREEN
                        bar_len = eye_line.x_axis[x_idx + 1] - eye_line.x_axis[x_idx]
                        ax.barh(eye_line_idx, bar_len, left=eye_line.x_axis[x_idx], align='center', color=bar_color)
                        x_idx += 1

                    ticks.append(eye_line_idx)
                    labels.append(eye_line.y_axis[0])
                    eye_line_idx = eye_line_idx + 1

                ch = chr(ord('A') + int((eye_idx - 1) / EyeData.num_cols))
                ax.set_title('Channel ' + ch + ' - ' + cs + ' (PostTrain)')
                ax.set_yticks(ticks, labels)
                ax.invert_yaxis()

                ax.axline((2 * ui, 0), (2 * ui, 5), linewidth=1.0, color='grey')
                ax.set_xticks([0, ui, 2 * ui, 3 * ui, 4 * ui], ['-100%(UI)', '-50%(UI)', '0', '50%(UI)', '100%(UI)'])
                eye_idx = eye_idx + 1

        return fig

    @staticmethod
    def compute_post_trained_mx8(eye_list, anibs):  # type: ignore
        """ANIB decode for mscale.

        anibs[0] - CKE/CS, channel A
        anibs[1] - CLK, channel A
        anibs[2] - CA0:3, channel A
        anibs[3] - CA4:5, channel A
        anibs[4] - NA
        anibs[5] - CKE/CS, channel B
        anibs[6] - CLK, channel B
        anibs[7] - CA0:3, channel B
        anibs[8] - CA4:5, channel B
        """
        eye_idx = 0
        for eye_data in eye_list:
            line_idx = 0
            for eye_line in eye_data:
                delay = 0
                if eye_idx in [0, 1]:  # CA
                    if line_idx in [0, 1, 2, 3]:
                        if anibs[0] == 64:
                            delay = np.fmod((anibs[0] - anibs[2]), 32)
                        elif anibs[0] == 0:
                            delay -= np.fmod(anibs[2], 32)
                    else:
                        if anibs[1] == 64:
                            delay = np.fmod((anibs[0] - anibs[3]), 32)
                        elif anibs[1] == 0:
                            delay -= np.fmod(anibs[3], 32)
                elif eye_idx in [2, 3]:  # CB
                    if line_idx in [0, 1, 2, 3]:
                        if anibs[5] == 64:
                            delay = np.fmod((anibs[5] - anibs[7]), 32)
                        elif anibs[5] == 0:
                            delay -= np.fmod(anibs[7], 32)
                    else:
                        if anibs[6] == 64:
                            delay = np.fmod((anibs[5] - anibs[8]), 32)
                        elif anibs[6] == 0:
                            delay -= np.fmod(anibs[8], 32)

                if delay != 0:
                    for idx in range(len(eye_line.x_axis)):
                        eye_line.x_axis[idx] += delay
                        if eye_line.x_axis[idx] > 128:
                            eye_line.x_axis[idx] = 128
                        elif eye_line.x_axis[idx] < 0:
                            eye_line.x_axis[idx] = 0

                line_idx = line_idx + 1
            eye_idx = eye_idx + 1

    @staticmethod
    def compute_post_trained_mx93(eye_list, anibs):  # type: ignore
        """ANIB decode for MX93.

        anibs[0] - CKE/CA0:1, channel A
        anibs[1] - CS/CLK, channel A
        anibs[2] - CA2:5, channel A
        """
        eye_idx = 0
        for eye_data in eye_list:
            line_idx = 0
            for eye_line in eye_data:
                delay = 0
                if eye_idx in [0, 1]:  # CA
                    if line_idx in [0, 1]:
                        if anibs[1] == 64:
                            delay = np.fmod((32 - anibs[0]), 32)
                        elif anibs[1] == 0:
                            delay -= np.fmod(anibs[0], 32)
                    else:
                        if anibs[1] == 64:
                            delay = np.fmod((32 - anibs[2]), 32)
                        elif anibs[1] == 0:
                            delay -= np.fmod(anibs[2], 32)

                if delay != 0:
                    for idx in range(len(eye_line.x_axis)):
                        eye_line.x_axis[idx] += delay
                        if eye_line.x_axis[idx] > 128:
                            eye_line.x_axis[idx] = 128
                        elif eye_line.x_axis[idx] < 0:
                            eye_line.x_axis[idx] = 0

                line_idx = line_idx + 1
            eye_idx = eye_idx + 1

    @staticmethod
    def compute_post_trained_mx95(eye_list, anibs):  # type: ignore
        """ANIB decode for MX95."""
        pass


class Eye2DData:
    """Class used to store data eye point."""

    def __init__(self, delay: Union[int, float], min_vref: int, max_vref: int):
        """Constructor.

        @param delay: delay info
        @param min_vref: minimum vref
        @param minVref: maximum vref
        """
        self.delay = delay
        self.minVref = min_vref
        self.maxVref = max_vref


class Eye2D:
    """Class used to store data eye."""

    @staticmethod
    def __cleanup_data_points(data: Eye2DData) -> bool:
        """Filter function to remove sections of the eyes that are fully closed.

        @param data: data eye point
        @return: False if eye was filtered True otherwise
        """
        if data.minVref >= data.maxVref:
            return False
        return True

    def __init__(self, rank: int, byte: int, lane: int, dac: int, dataPoints: list,
                    isDiagEye: bool, fileName: str, eyeType: str=""):
        """Constructor.

        @param rank: rank info
        @param byte: byte info
        @param lane: lane info
        @param dac: dac info
        @param dataPoints: eys data points
        @param isDiagEye: True if it is data eye, False otherwise
        @param fileName: data file name
        @param eyeType: eye type
        """
        self.rank = rank
        self.byte = byte
        self.lane = lane
        self.dac = dac
        self.isDiagEye = isDiagEye
        self.eyeType = eyeType
        self.previousDelay = -1
        self.previousVref = -1
        self.trained2DDelay = -1
        self.trained2DVref = -100
        self.trained2DVref1 = -100
        self.trained2DVref2 = -100
        self.trained2DVref3 = -100
        self.centroidX = -1
        self.centroidY = -1
        self.minVrefs = list()
        self.maxVrefs = list()
        for dataPoint in dataPoints:
            self.minVrefs.append(dataPoint.minVref)
            self.maxVrefs.append(dataPoint.maxVref)
        # Construct new "clean" min/max lists by removing invalid data points
        self.dataPoints = list(filter(self.__cleanup_data_points, dataPoints))
        self.topHandle: list[Line2D] = list()
        self.bottomHandle: list[Line2D] = list()
        self.previousCenterHandle: Union[Line2D, None] = None
        self.trained2DCenterHandle: Union[Line2D, None] = None
        self.trained2DCenterHandle1: Union[Line2D, None] = None
        self.trained2DCenterHandle2: Union[Line2D, None] = None
        self.trained2DCenterHandle3: Union[Line2D, None] = None
        self.centroidCenterHandle: Union[Line2D, None] = None
        self.legendTitle = fileName
