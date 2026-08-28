# Copyright 2020-2023 NXP
"""TODO:summary line."""
from memtool.common.config_data import ConfigData

from .xls_engine import XlsEngine
from .xls_mappings import DSF_CONFIG_SHEET, LX2_DS_RANGE, REG_CONFIG_SHEET


class XlsEngineLX2(XlsEngine):
    """TODO:summary line."""

    def __init__(self, config_data: ConfigData):
        """TODO:summary line."""
        super(XlsEngineLX2, self).__init__(config_data)

    def get_ds_file(self, ds_range=LX2_DS_RANGE, sheet=DSF_CONFIG_SHEET) -> str:  # type: ignore
        """Override get_ds_file from XlsEngine.

        @param ds_range: cell range of interest from the excel sheet
        @param sheet: name of the sheet of interest from the excel file
        @return: the content of the ds file as a str
        """
        return super(XlsEngineLX2, self).get_ds_file(ds_range=ds_range,
                                                     sheet=DSF_CONFIG_SHEET)
