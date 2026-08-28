# Copyright 2022-2024 NXP
"""TODO:summary line."""

import logging
from abc import abstractmethod

from memtool.common.config_data import ConfigData
from memtool.common.factories import FactoryClass

logger = logging.getLogger(__name__)


class Scenario(metaclass=FactoryClass.RegistryMeta):
    """Base class for implementing scenarios."""
    NAME = "Scenario"

    def __init__(self):  # type: ignore
        """Constructor."""
        self.column_labels = []
        self.column_values = []
        self.row_labels = []
        self.row_values = []
        self.number_of_cells = 0
        self.number_of_columns = 0
        self.number_of_rows = 0

    @classmethod
    def matches(cls, name) -> bool:  # type: ignore
        """Check if the test name matches the NAME attribute of the test class.

        @param name: test name
        @return: True if match, False otherwise
        """
        return hasattr(cls, 'NAME') and (cls.NAME.lower() == name.lower())

    @abstractmethod
    def has_valid_input(self) -> bool:
        """Checks if input was validated.

        @return: True if scenario parameters were checked and are valid
        """

    @abstractmethod
    def get_input_error(self) -> str:
        """Get input validation error message.

        @return: validation error message
        """

    @abstractmethod
    def reset(self, config_data: ConfigData):  # type: ignore
        """Update scenario based on received parameters.

        @param config_data: configuration data (includes scenario parameters)
        """
        pass

    def get_number_of_cells(self) -> int:
        """Get number of cells."""
        return self.number_of_cells

    def set_column_values(self, values: list, labels: list):  # type: ignore
        """Set column values."""
        if len(values) != len(labels):
            logger.error("For each column value a label should be provided!")
            self.column_values = []
            self.column_labels = []
        else:
            self.column_values = values
            self.column_labels = labels
        self.number_of_columns = len(values)
        self.number_of_cells = self.number_of_columns * self.number_of_rows

    def get_number_of_columns(self) -> int:
        """Get number of columns."""
        return self.number_of_columns

    def get_column_values(self) -> list:
        """Get column values."""
        return self.column_values

    def get_column_labels(self) -> list:
        """Get column labels."""
        return self.column_labels

    def set_row_values(self, values: list, labels: list):  # type: ignore
        """Set row values."""
        if len(values) != len(labels):
            logger.error("For each row value a label should be provided!")
            self.row_values = []
            self.row_labels = []
        else:
            self.row_values = values
            self.row_labels = labels
        self.number_of_rows = len(values)
        self.number_of_cells = self.number_of_rows * self.number_of_columns

    def get_number_of_rows(self) -> int:
        """Get number of rows."""
        return self.number_of_rows

    def get_row_values(self) -> list:
        """Get row values."""
        return self.row_values

    def get_row_labels(self) -> list:
        """Get row labels."""
        return self.row_labels

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Update test parameters."""
        pass

    def update_cell_params(self, config_data: ConfigData, cell_idx):  # type: ignore
        """Update configuration data parameters according to cell index."""
        pass

    @abstractmethod
    def get_test_name(self):  # type: ignore
        """Get scenario test name."""

    @abstractmethod
    def get_test_window_class_name(self):  # type: ignore
        """Get UI class name."""

    @abstractmethod
    def get_scenario_window_class_name(self):  # type: ignore
        """Get UI class name."""

    def get_col_parameter_name(self):  # type: ignore
        """Get name of the parameter for which variation is displayed on column."""
        pass

    def get_col_parameter_values(self):  # type: ignore
        """Get values for parameter displayed on column."""
        pass

    def set_col_parameter_value(self, config_data: ConfigData, value: str):  # type: ignore
        """Set value for parameter displayed on column."""
        pass

    def get_row_parameter_name(self):  # type: ignore
        """Get name of the parameter for which variation is displayed on row."""
        pass

    def get_row_parameter_values(self):  # type: ignore
        """Get values for parameter displayed on row."""
        pass

    def set_row_parameter_value(self, config_data: ConfigData, value: str):  # type: ignore
        """Set value for parameter displayed on row."""
        pass

    def clear_test_result(self):  # type: ignore
        """Clear test results."""
        pass

    def store_test_result(self, test):  # type: ignore
        """Store test results."""
        pass

    @classmethod
    def data_eye_is_generated(cls) -> bool:
        """Data Eye is generated using scenario results."""
        return False

    def process_results(self, config_data: ConfigData):  # type: ignore
        """Process scenario's results."""
        pass
