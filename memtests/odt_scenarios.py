# Copyright 2022-2023 NXP
"""TODO:summary line."""

from memtool.common.config_data import ConfigData
from memtool.common.scenarios import Scenario
from memtool.memtests.ddr_tests import StressTests
from memtool.utils.constants import Const


class ODTScenario(Scenario):
    """ODT Scenario."""

    NAME = "ODT Scenario"

    def __init__(self):  # type: ignore
        """Constructor."""
        super(ODTScenario, self).__init__()
        self.phy_param_id = None
        self.dram_param_id = None

    def has_valid_input(self) -> bool:
        """Checks if input was validated.

        @return: True if scenario parameters were checked and are valid
        """
        return True  # for now, no need to check ODT scenarios params

    def get_input_error(self) -> str:
        """Get input validation error message.

        @return: validation error message
        """
        return ""  # for now, ODT scenarios params are not validated, so no error message

    def reset(self, config_data: ConfigData):  # type: ignore
        """Reset parameters."""
        _column_values = config_data.params["odt_columns"]
        self.set_column_values(list(_column_values.values()), list(_column_values.keys()))

        _row_values = config_data.params["odt_rows"]
        self.set_row_values(list(_row_values.values()), list(_row_values.keys()))

        self.phy_param_id = config_data.params["phy_param_id"]
        self.dram_param_id = config_data.params["dram_param_id"]

    def get_phy_param_id(self):  # type: ignore
        """Get id of PHY parameter."""
        return self.phy_param_id

    def get_dram_param_id(self):  # type: ignore
        """Get id of DRAM parameter."""
        return self.dram_param_id

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params."""
        StressTests.update_config_params(config_data)

    @staticmethod
    def get_test_name():  # type: ignore
        """Get scenario test name."""
        return StressTests.NAME

    def get_test_window_class_name(self):  # type: ignore
        """Get UI class name."""
        return StressTests.__name__ + 'Window'

    def get_scenario_window_class_name(self):  # type: ignore
        """Get UI class name."""
        return 'ODTScenarioWindow'


class ReadODT(ODTScenario):
    """Read ODT."""
    NAME = "Read ODT and driver"

    def __init__(self):  # type: ignore
        """Constructor."""
        super(ReadODT, self).__init__()

    def update_cell_params(self, config_data: ConfigData, cell_idx):  # type: ignore
        """Update configuration data parameters according to cell index in PHY/DRAM parameters table.

        @param config_data: Configuration data.
        @param cell_idx: Cell index in PHY/DRAM parameters table.
        """
        num_columns = self.get_number_of_columns()
        cell_row = int(cell_idx / num_columns)
        cell_col = cell_idx % num_columns
        row_values = self.get_row_values()  # DRAM parameter actually values.
        column_values = self.get_column_values()  # PHY parameter actually values.
        if cell_row < len(row_values):
            value = row_values[cell_row]
            config_data.params[Const.PARAM_S_ODT][Const.PARAM_S_ODT_RD][self.get_phy_param_id()] = value
            config_data.params[Const.PARAM_S_ODT][Const.PARAM_S_ODT_RD]["soc_odt"] = value
        if cell_col < len(column_values):
            value = column_values[cell_col]
            config_data.params[Const.PARAM_S_ODT][Const.PARAM_S_ODT_RD][self.get_dram_param_id()] = value


class WriteODT(ODTScenario):
    """Write ODT."""

    NAME = "Write ODT and driver"

    def __init__(self):  # type: ignore
        """Constructor."""
        super(WriteODT, self).__init__()

    def update_cell_params(self, config_data: ConfigData, cell_idx):  # type: ignore
        """Update configuration data parameters according to cell index in PHY/DRAM parameters table.

        @param config_data: Configuration data.
        @param cell_idx: Cell index in PHY/DRAM parameters table.
        """
        num_columns = self.get_number_of_columns()
        cell_row = int(cell_idx / num_columns)
        cell_col = cell_idx % num_columns
        row_values = self.get_row_values()  # DRAM parameter actually values.
        column_values = self.get_column_values()  # PHY parameter actually values.
        if cell_row < len(row_values):
            value = row_values[cell_row]
            config_data.params[Const.PARAM_S_ODT][Const.PARAM_S_ODT_WR][self.get_phy_param_id()] = value
        if cell_col < len(column_values):
            value = column_values[cell_col]
            config_data.params[Const.PARAM_S_ODT][Const.PARAM_S_ODT_WR][self.get_dram_param_id()] = value
