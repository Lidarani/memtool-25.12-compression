# Copyright 2022-2025 NXP
"""TODO:summary line."""
import logging
import traceback
from datetime import datetime

import numpy

from memtool.common.config_data import ConfigData
from memtool.common.scenarios import Scenario
from memtool.memtests.eye_figure import CAEyeFigure
from memtool.memtests.phy_diags_tests import CAEye
from memtool.utils.constants import Const

logger = logging.getLogger(__name__)


class CAEyeScenario(Scenario):
    """CA Eye Scenario."""
    NAME = "CA Eye"

    # VDDQ parameter values - change them only after consulting the manual!!!
    VREF_CA_START_VALUE = {'lpddr4': 10.0,  # 10.0 % VDDQ = index 0
                           'lpddr4x': 15.0,  # 15.0 % VDDQ = index 0
                           'lpddr5': 10.0}
    VREF_CA_END_VALUE = {'lpddr4': 42.0,  # 42.0 % VDD2 = index 80
                         'lpddr4x': 62.9,  # 62.9 % VDD2 = index 80
                         'lpddr5': 73.5}
    VREF_CA_STEP_VALUE = {'lpddr4': 0.4,
                          'lpddr4x': 0.6,
                          'lpddr5': 0.5}
    VREF_CA_RANGE_CHANGE_VALUE = {'lpddr4': 22.0,
                                  'lpddr4x': 32.9,
                                  'lpddr5': 42.0}
    VREF_CA_RANGE_CHANGE_INDEX = {'lpddr4': 30,
                                  'lpddr4x': 30,
                                  'lpddr5': 64}
    VDDQ_VALUE = {'lpddr4': 1.1,  # VDDQ = VDD2 = 1.1V
                  'lpddr4x': 0.6,  # VDDQ = 0.6V, VDD2 = 1.1V
                  'lpddr5': 0.5}
    VDDQ_INTERVALS = {'lpddr4': [(10.0, 42.0, 0.4)],
                      'lpddr4x': [(15.0, 24.0, 0.6), (24.6, 24.6, 0.5), (25.1, 62.90, 0.6)],
                      'lpddr5': [(10.0, 73.5, 0.5)]}  # NOTE: make sure the intervals are ordered

    # Number of signals diagrams drawn on a row
    NO_SIGNALS_PER_ROW = 6

    def __init__(self):  # type: ignore
        """Constructor."""
        super(CAEyeScenario, self).__init__()

        self._has_valid_parameters = True
        self._parameters_error = ''

        self.scenario_results = {}  # {CA range -> {CA VREF -> ([anibs], {CS -> {CA -> [data]}})}}
        self.current_ca_range = None
        self.current_ca_vref = None

    def has_valid_input(self) -> bool:
        """Checks if input was validated.

        @return: True if scenario parameters were checked and are valid
        """
        return self._has_valid_parameters

    def get_input_error(self) -> str:
        """Get input validation error message.

        @return: validation error message
        """
        return self._parameters_error

    def get_vref_ca_value(self, val, memory_type):  # type: ignore
        """Get vref ca value and its index for given value and memory.

        @param val: user input value for ca vref
        """
        # E.g. user sets vref ca start value '24.2' in UI;
        # this will be adjusted to '24.0' and index 15
        index = 0
        value = val * 10
        for interval in CAEyeScenario.VDDQ_INTERVALS[memory_type]:
            start = interval[0] * 10
            end = interval[1] * 10
            step_length = interval[2] * 10
            if (value >= start) and (value <= end):
                offset = int((value - start) / step_length)
                index += offset
                return ((start + (offset * step_length)) / 10), index
            else:  # value > interval end
                index += int((end - start) / step_length) + 1
        return -1, index

    def reset(self, config_data: ConfigData):  # type: ignore
        """Reset parameters and check their validity."""
        self._has_valid_parameters = True
        self._parameters_error = ''

        _row_values = []
        _row_labels = []

        try:
            self.set_column_values([None], ["Status"])  # used just for label

            # NOTE: to avoid problems caused by floating point operations,
            # we'll work with integers (values will be multiplied by 10)
            vdd_min_value = int(CAEyeScenario.VREF_CA_START_VALUE[config_data.mem_type] * 10)
            vdd_max_value = int(CAEyeScenario.VREF_CA_END_VALUE[config_data.mem_type] * 10)
            step_value = int(CAEyeScenario.VREF_CA_STEP_VALUE[config_data.mem_type] * 10)

            if Const.PARAM_S_CA_CONFIG in config_data.params:  # DDR Expert UI
                if Const.PARAM_S_CA_VREF_START_CONFIG not in config_data.params[Const.PARAM_S_CA_CONFIG]:
                    raise Exception('caConfig dictionary is incomplete! CA Vref start is missing.')
                vdd_start_value = int(config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_VREF_START_CONFIG]
                                      * 10)
                if vdd_start_value < vdd_min_value or vdd_start_value > vdd_max_value:
                    raise Exception(
                        f"CA vref start must be set to a float value between "
                        f"{CAEyeScenario.VREF_CA_START_VALUE[config_data.mem_type]} "
                        f"and {CAEyeScenario.VREF_CA_END_VALUE[config_data.mem_type]}!")

                if Const.PARAM_S_CA_VREF_END_CONFIG not in config_data.params[Const.PARAM_S_CA_CONFIG]:
                    raise Exception('caConfig dictionary is incomplete! CA Vref end is missing.')
                vdd_end_value = int(config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_VREF_END_CONFIG] * 10)
                if vdd_end_value < vdd_min_value or vdd_end_value > vdd_max_value:
                    raise Exception(f"CA vref end must be set to a float value between "
                                    f"{CAEyeScenario.VREF_CA_START_VALUE[config_data.mem_type]} "
                                    f"and {CAEyeScenario.VREF_CA_END_VALUE[config_data.mem_type]}!")

                if vdd_start_value >= vdd_end_value:
                    raise Exception("CA vref start must be less than CA vref end!")

                if Const.PARAM_S_CA_VREF_STEP_CONFIG not in config_data.params[Const.PARAM_S_CA_CONFIG]:
                    raise Exception('caConfig dictionary is incomplete! CA Vref step is missing.')
                vdd_step_value = int(config_data.params[Const.PARAM_S_CA_CONFIG][Const.PARAM_S_CA_VREF_STEP_CONFIG]
                                     * 10)
                if vdd_step_value % step_value != 0:
                    raise Exception(f"CA vref step must be set to a float value multiple of {step_value}!")
            else:  # ConfigTools
                vdd_start_value = vdd_min_value
                vdd_end_value = vdd_max_value
                vdd_step_value = step_value * 10

            vdd_crt_value = vdd_start_value
            while vdd_crt_value <= vdd_end_value:
                _value = float(vdd_crt_value) / 10
                vref_ca_value, vref_ca_index = self.get_vref_ca_value(_value, config_data.mem_type)
                if vref_ca_value < 0:
                    raise Exception(f"CA vref steps are incorrectly specified! "
                                    f"Check step definition for interval containing {_value} value!")
                _row_values.append(vref_ca_index)
                _row_labels.append(f'{vref_ca_value}%   ({vref_ca_index})')
                vdd_crt_value = int(vref_ca_value * 10) + vdd_step_value
        except ValueError as ex_value:
            self._has_valid_parameters = False
            self._parameters_error = "Failed to load CA vref parameter: " + str(ex_value)
            logger.error(self._parameters_error)
        except Exception as ex:
            self._has_valid_parameters = False
            self._parameters_error = str(ex)
            logger.error(self._parameters_error)

        self.set_row_values(_row_values, _row_labels)

    def update_cell_params(self, config_data: ConfigData, cell_idx: int):  # type: ignore
        """Update cell specific test parameters.

        @param config_data: target configuration data to be updated with parameter values for current cell
        @param cell_idx: current cell index; for a table cell_idx = 0..(no_columns * no_rows)
        """
        # update params for current cell - for CA eye we have 1 column and multiple rows
        values = self.get_row_values()
        self.set_row_parameter_value(config_data, values[cell_idx])  # apply value to config_data

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Update test specific parameters.

        @param config_data: target configuration data to be updated with test specific parameters
        (those that do not depend on the selected cell)
        """
        CAEye.update_config_params(config_data)

    @classmethod
    def data_eye_is_generated(cls) -> bool:
        """Show data eye window for scenario test."""
        return True

    @staticmethod
    def get_test_name():  # type: ignore
        """Get scenario test name."""
        return CAEye.NAME

    def get_test_window_class_name(self):  # type: ignore
        """Get UI class name."""
        return CAEye.__name__ + 'Window'

    def get_scenario_window_class_name(self):  # type: ignore
        """Get UI class name."""
        return 'CAScenarioWindow'

    def set_row_parameter_value(self, config_data: ConfigData, value):  # type: ignore
        """Set value for parameter displayed on row."""
        self.current_ca_range = 0
        if value >= CAEyeScenario.VREF_CA_RANGE_CHANGE_INDEX[config_data.mem_type]:
            self.current_ca_range = 1
        if self.current_ca_range not in self.scenario_results:
            self.scenario_results[self.current_ca_range] = {}
        current_value = value if value < CAEyeScenario.VREF_CA_RANGE_CHANGE_INDEX[config_data.mem_type] \
            else (value - CAEyeScenario.VREF_CA_RANGE_CHANGE_INDEX[config_data.mem_type])

        if Const.PARAM_S_CA_VREF not in config_data.params:
            config_data.params[Const.PARAM_S_CA_VREF] = {}
        config_data.params[Const.PARAM_S_CA_VREF][Const.PARAM_S_CA_VREF_RANGE] = self.current_ca_range
        config_data.params[Const.PARAM_S_CA_VREF][Const.PARAM_S_CA_VREF_VALUE] = current_value
        self.current_ca_vref = value

    def clear_test_result(self):  # type: ignore
        """Clear test results."""
        self.scenario_results = {}
        self.current_ca_range = None
        self.current_ca_vref = None

    def store_test_result(self, test):  # type: ignore
        """Store test results."""
        anibs_data, signals_data = test.get_data_eye()

        if self.current_ca_range is not None and self.current_ca_vref is not None:
            if self.current_ca_range not in self.scenario_results:
                logger.error("CA range was incorrectly set!")
                return
            if self.current_ca_vref in self.scenario_results[self.current_ca_range]:
                logger.error("CA VREF was incorrectly set!")
                return

            anibs = []
            if len(anibs_data) > 0:
                anibs = [int(a) for a in anibs_data[1:-1].split(',')]
            self.scenario_results[self.current_ca_range][self.current_ca_vref] = (anibs, signals_data)

    def process_results(self, config_data: ConfigData):  # type: ignore
        """Create data eyes based on self.scenario_results."""
        if len(self.scenario_results) == 0:
            logger.error("CA data is missing!")
            return None

        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            self.process_phy_v2_results(config_data)
        else:
            self.process_phy_v3_results(config_data)

    def process_phy_v2_results(self, config_data: ConfigData):  # type: ignore
        """Process CA data for PHY v2."""
        VDDQ = CAEyeScenario.VDDQ_VALUE[config_data.mem_type]

        ca_ranges = list(self.scenario_results.keys())
        ca_ranges.sort()  # sorted list of ranges
        no_tested_vrefs = 0
        for ca_range in ca_ranges:
            no_tested_vrefs += len(self.scenario_results[ca_range])

        # no_ca_ranges = len(ca_ranges)
        first_results = list(self.scenario_results[ca_ranges[0]].values())[0]
        first_anibs = first_results[0]
        first_signals = first_results[1]
        if len(first_anibs) == 0 or len(first_signals) == 0:
            logger.error("CA data is missing!")
            return None

        css = list(first_signals.keys())
        css.sort()  # sorted list of cs
        num_rows = len(css) * (2 if config_data.show_ca_pretrained_data else 1)  # pre & post trained data
        signals = list(first_signals[css[0]].keys())
        signals.sort()  # sorted list of signals
        no_signals = len(signals)

        # when channel A and channel B are present picture will be too wide,
        # so we'll place channel B diagrams on a separate line
        if no_signals > CAEyeScenario.NO_SIGNALS_PER_ROW:
            if (no_signals % 2) != 0:
                logger.warning("CA diagrams are incorrectly displayed because of an odd number of channels found."
                               " Method used to create data eye should be updated!")
            num_columns = int(no_signals / 2)
            num_rows = num_rows * 2
        else:
            num_columns = no_signals

        try:
            # reduce matplotlib log - set log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            fig = CAEyeFigure(num_columns, num_rows)

            # pre trained data
            eye_idx = 1
            if config_data.show_ca_pretrained_data:
                for cs in css:
                    for signal in signals:
                        ax = fig.add_subplot(num_rows, num_columns, eye_idx)
                        line_idx = 1
                        ticks = []
                        labels = []

                        for ca_range in ca_ranges:
                            vrefs = list(self.scenario_results[ca_range].keys())
                            vrefs.sort()  # sorted list of vrefs

                            for vref in vrefs:
                                vref_data = self.scenario_results[ca_range][vref]  # data for a certain vref
                                if len(vref_data[1]) == 0:
                                    logger.error("CA data is missing!")
                                    signal_data = [0, 128]
                                else:
                                    signal_data = vref_data[1][cs][signal]
                                idx = 0
                                while idx < len(signal_data) - 1:
                                    bar_color = Const.COLOR_HEX_BROWN if (idx % 2 == 0) else Const.COLOR_HEX_GREEN
                                    bar_len = signal_data[idx + 1] - signal_data[idx]
                                    ax.barh(line_idx, bar_len, left=signal_data[idx], align='center', color=bar_color)
                                    idx += 1
                                ticks.append(line_idx)

                                vref_range_start = CAEyeScenario.VREF_CA_START_VALUE[config_data.mem_type]
                                vref_step = CAEyeScenario.VREF_CA_STEP_VALUE[config_data.mem_type]
                                vref_value = vref
                                if ca_range == 1:
                                    vref_range_start = CAEyeScenario.VREF_CA_RANGE_CHANGE_VALUE[config_data.mem_type]
                                    vref_value -= CAEyeScenario.VREF_CA_RANGE_CHANGE_INDEX[config_data.mem_type]

                                vref_label = str(round(VDDQ * (vref_range_start + vref_value * vref_step) * 10, 1))
                                labels.append(vref_label + 'mV')

                                line_idx = line_idx + 1

                        ax.set_title(f'CS{cs} {signal} (PreTrain)')
                        ax.set_yticks(ticks, labels)
                        ax.axline((64, 0), (64, 5), linewidth=1.0, color='grey')
                        ax.set_xticks([0, 32, 64, 96, 128], ['-100%(UI)', '-50%(UI)', '0', '50%(UI)', '100%(UI)'])
                        eye_idx = eye_idx + 1

            # post trained data
            soc = config_data.soc_name
            for cs in css:
                for signal in signals:
                    ax = fig.add_subplot(num_rows, num_columns, eye_idx)
                    line_idx = 1
                    ticks = []
                    labels = []

                    for ca_range in ca_ranges:
                        vrefs = list(self.scenario_results[ca_range].keys())
                        vrefs.sort()  # sorted list of vrefs

                        for vref in vrefs:
                            vref_data = self.scenario_results[ca_range][vref]  # data for a certain vref
                            if len(vref_data[0]) == 0 or len(vref_data[1]) == 0:
                                logger.error("CA data is missing!")
                                anibs_data = []
                                signal_data = [0, 128]
                            else:
                                anibs_data = vref_data[0]
                                signal_data = vref_data[1][cs][signal]

                            delay = self.compute_delay(soc, signal, anibs_data)
                            for idx in range(1, len(signal_data) - 1):
                                signal_data[idx] += delay
                                if signal_data[idx] > 128:
                                    signal_data[idx] = 128
                                elif signal_data[idx] < 0:
                                    signal_data[idx] = 0

                            idx = 0
                            while idx < len(signal_data) - 1:
                                bar_color = Const.COLOR_HEX_BROWN if (idx % 2 == 0) else Const.COLOR_HEX_GREEN
                                bar_len = signal_data[idx + 1] - signal_data[idx]
                                ax.barh(line_idx, bar_len, left=signal_data[idx], align='center', color=bar_color)
                                idx += 1
                            ticks.append(line_idx)

                            vref_range_start = CAEyeScenario.VREF_CA_START_VALUE[config_data.mem_type]
                            vref_step = CAEyeScenario.VREF_CA_STEP_VALUE[config_data.mem_type]
                            vref_value = vref
                            if ca_range == 1:
                                vref_range_start = CAEyeScenario.VREF_CA_RANGE_CHANGE_VALUE[config_data.mem_type]
                                vref_value -= CAEyeScenario.VREF_CA_RANGE_CHANGE_INDEX[config_data.mem_type]

                            vref_label = str(round(VDDQ * (vref_range_start + vref_value * vref_step) * 10, 1))
                            labels.append(vref_label + 'mV')

                            line_idx = line_idx + 1

                    ax.set_title(f'CS{cs} {signal} (PostTrain)')
                    ax.set_yticks(ticks, labels)
                    ax.axline((64, 0), (64, 5), linewidth=1.0, color='grey')
                    ax.set_xticks([0, 32, 64, 96, 128], ['-100%(UI)', '-50%(UI)', '0', '50%(UI)', '100%(UI)'])
                    eye_idx = eye_idx + 1

            img_file_path = config_data.figure_file
            fig.savefig(img_file_path)
            config_data.params[Const.PARAM_S_TC]['diag_image_file'] = img_file_path

        except Exception as ex:
            if logger.getEffectiveLevel() == logging.DEBUG:
                logger.debug('Error traceback:')
                traceback.print_exc()
            logger.exception('CA eye data processing ended with exception: %s', str(ex))

        finally:
            # restore log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

    def compute_delay(self, soc, signal, anibs):  # type: ignore
        """Compute delay."""
        if len(anibs) == 0:
            return 0

        is_channel_A = True
        if signal.startswith('CAA'):
            signal_idx = int(signal.replace('CAA', ''))
        else:  # CAB
            is_channel_A = False
            signal_idx = int(signal.replace('CAB', ''))

        delay = 0
        if ConfigData.DEVICES_INFO[soc].is_imx9():
            if is_channel_A:  # CAA
                if signal_idx <= 1:  # CAA0:1
                    if anibs[1] == 64:
                        delay = numpy.fmod((32 - anibs[0]), 32)
                    elif anibs[1] == 0:
                        delay -= numpy.fmod(anibs[0], 32)
                else:  # CAA2:5
                    if anibs[1] == 64:
                        delay = numpy.fmod((32 - anibs[2]), 32)
                    elif anibs[1] == 0:
                        delay -= numpy.fmod(anibs[2], 32)
        else:
            if is_channel_A:  # CAA
                if signal_idx <= 3:  # CAA0:3
                    if anibs[0] == 64:
                        delay = numpy.fmod((anibs[0] - anibs[2]), 32)
                    elif anibs[0] == 0:
                        delay -= numpy.fmod(anibs[2], 32)
                else:  # CAA4:5
                    if anibs[1] == 64:
                        delay = numpy.fmod((anibs[0] - anibs[3]), 32)
                    elif anibs[1] == 0:
                        delay -= numpy.fmod(anibs[3], 32)
            else:  # CAB
                if signal_idx <= 3:  # CAB0:3
                    if anibs[5] == 64:
                        delay = numpy.fmod((anibs[5] - anibs[7]), 32)
                    elif anibs[5] == 0:
                        delay -= numpy.fmod(anibs[7], 32)
                else:  # CAB4:5
                    if anibs[6] == 64:
                        delay = numpy.fmod((anibs[5] - anibs[8]), 32)
                    elif anibs[6] == 0:
                        delay -= numpy.fmod(anibs[8], 32)
        return delay

    def process_phy_v3_results(self, config_data: ConfigData):  # type: ignore
        """Process CA data for PHY v3."""
        VDDQ = CAEyeScenario.VDDQ_VALUE[config_data.mem_type]

        ca_ranges = list(self.scenario_results.keys())
        ca_ranges.sort()  # sorted list of ranges
        no_tested_vrefs = 0
        for ca_range in ca_ranges:
            no_tested_vrefs += len(self.scenario_results[ca_range])

        # no_ca_ranges = len(ca_ranges)
        first_results = list(self.scenario_results[ca_ranges[0]].values())[0]
        first_anibs = first_results[0]
        first_signals = first_results[1]
        if len(first_anibs) == 0 or len(first_signals) == 0:
            logger.error("CA data is missing!")
            return None

        css = list(first_signals.keys())
        css.sort()  # sorted list of cs
        num_rows = len(css)  # pre trained data
        signals = list(first_signals[css[0]].keys())
        signals.sort()  # sorted list of signals
        no_signals = len(signals)
        num_columns = no_signals

        try:
            # reduce matplotlib log - set log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            fig = CAEyeFigure(num_columns, num_rows)

            # pre trained data
            eye_idx = 1
            if config_data.show_ca_pretrained_data:
                for cs in css:
                    signals = list(first_signals[cs].keys())
                    signals.sort()  # sorted list of signals
                    for signal in signals:
                        ax = fig.add_subplot(num_rows, num_columns, eye_idx)
                        line_idx = 1
                        ticks = []
                        labels = []

                        for ca_range in ca_ranges:
                            vrefs = list(self.scenario_results[ca_range].keys())
                            vrefs.sort()  # sorted list of vrefs

                            for vref in vrefs:
                                vref_data = self.scenario_results[ca_range][vref]  # data for a certain vref
                                if len(vref_data[1]) == 0:
                                    logger.error("CA data is missing!")
                                    signal_data = [0, 256]
                                else:
                                    signal_data = vref_data[1][cs][signal]
                                idx = 0
                                while idx < len(signal_data) - 1:
                                    bar_color = Const.COLOR_HEX_BROWN if (idx % 2 == 0) else Const.COLOR_HEX_GREEN
                                    bar_len = signal_data[idx + 1] - signal_data[idx]
                                    ax.barh(line_idx, bar_len, left=signal_data[idx], align='center', color=bar_color)
                                    idx += 1
                                ticks.append(line_idx)

                                vref_range_start = CAEyeScenario.VREF_CA_START_VALUE[config_data.mem_type]
                                vref_step = CAEyeScenario.VREF_CA_STEP_VALUE[config_data.mem_type]
                                vref_value = vref
                                if ca_range == 1:
                                    vref_range_start = CAEyeScenario.VREF_CA_RANGE_CHANGE_VALUE[config_data.mem_type]
                                    vref_value -= CAEyeScenario.VREF_CA_RANGE_CHANGE_INDEX[config_data.mem_type]

                                vref_label = str(round(VDDQ * (vref_range_start + vref_value * vref_step) * 10, 1))
                                labels.append(vref_label + 'mV')

                                line_idx = line_idx + 1

                        ax.set_title(f'{cs} {signal} (PreTrain)')
                        ax.set_yticks(ticks, labels)
                        ax.axline((128, 0), (128, 5), linewidth=1.0, color='grey')
                        ax.set_xticks([0, 64, 128, 192, 256], ['-100%(UI)', '-50%(UI)', '0', '50%(UI)', '100%(UI)'])
                        eye_idx = eye_idx + 1

            img_file_path = config_data.figure_file
            fig.savefig(img_file_path)
            config_data.params[Const.PARAM_S_TC]['diag_image_file'] = img_file_path

        except Exception as ex:
            if logger.getEffectiveLevel() == logging.DEBUG:
                logger.debug('Error traceback:')
                traceback.print_exc()
            logger.exception('CA eye data processing ended with exception: %s', str(ex))

        finally:
            # restore log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)
