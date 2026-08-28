# Copyright 2020-2023 NXP
"""Engine for handling data in pkl files for i.MX9."""
import logging

from memtool.common.config_data import ConfigData
from memtool.utils.constants import Const

from .xls_engine import XlsEngine
from .xls_mappings import DSF_CONFIG_SHEET, MIMX9_DS_RANGE


class XlsEngineMX9(XlsEngine):
    """Loading and working with data from pkl for MIMX9 processors."""

    logger = logging.getLogger(__name__)

    def __init__(self, config_data: ConfigData):
        """Child class constructor."""
        super(XlsEngineMX9, self).__init__(config_data)

    def update_config(self, config_data, config_map):  # type: ignore
        """Override update_config from XlsEngine.

        @param config_data: processor config data
        @param config_map: new params and values
        """
        super(XlsEngineMX9, self).update_config(config_data, config_map)

        soc_name = config_data.soc_name

        # Inline ECC
        if Const.PARAM_S_INLINE_ECC_CONFIG_MX9 in config_data.params[Const.PARAM_S_BASIC]:
            # set Inline ECC enabled state
            inline_ecc_enabled = False
            cell = str(
                config_map.get(Const.PARAM_S_INLINE_ECC_CONFIG_MX9, ''))
            value = config_data.params[Const.PARAM_S_BASIC][Const.PARAM_S_INLINE_ECC_CONFIG_MX9]
            inline_ecc_enabled = value == "Enable"
            if cell in self.excel.cell_map:
                self.logger.debug('Set %s to %s', cell, value)
                self.excel.set_value(cell, value)
            else:
                self.logger.warning('Cell %s missing from cell map', cell)

            if inline_ecc_enabled:
                # set ecc start and end addresses
                start_regions = {}
                end_regions = {}
                if (Const.PARAM_S_INLINE_ECC_REGIONS_START_MX9 and Const.PARAM_S_INLINE_ECC_REGIONS_END_MX9
                        in config_data.params[Const.PARAM_S_INLINE_ECC_REGIONS_MX9]):
                    start_regions = config_data.params[Const.PARAM_S_INLINE_ECC_REGIONS_MX9][
                        Const.PARAM_S_INLINE_ECC_REGIONS_START_MX9]
                    end_regions = config_data.params[Const.PARAM_S_INLINE_ECC_REGIONS_MX9][
                        Const.PARAM_S_INLINE_ECC_REGIONS_END_MX9]
                else:
                    self.logger.warning('Inline ECC regions info is missing!')

                for idx in range(0, 8):
                    ecc_start_cell = str(config_map[soc_name][Const.PARAM_S_INLINE_ECC_REGIONS_MX9][
                        Const.PARAM_S_INLINE_ECC_REGIONS_START_MX9][str(idx)])
                    ecc_end_cell = str(config_map[soc_name][Const.PARAM_S_INLINE_ECC_REGIONS_MX9][
                        Const.PARAM_S_INLINE_ECC_REGIONS_END_MX9][str(idx)])

                    ecc_start_val = start_regions[str(idx)]
                    ecc_end_val = end_regions[str(idx)]

                    if ecc_start_cell and ecc_end_cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', ecc_start_cell, ecc_start_val)
                        self.excel.set_value(ecc_start_cell, ecc_start_val)
                        self.logger.debug('Set %s to %s', ecc_end_cell, ecc_end_val)
                        self.excel.set_value(ecc_end_cell, ecc_end_val)
                    else:
                        self.logger.warning('Cell missing from cell map')

    def get_ds_file(self, ds_range=MIMX9_DS_RANGE, sheet=DSF_CONFIG_SHEET):  # type: ignore
        """Override get_ds_file fromXlsEngine.

        @param ds_range: cell range of interest from the excel sheet
        @param sheet: name of the sheet of interest from the excel file
        @return: the content of the ds file as a str
        """
        return super(XlsEngineMX9, self).get_ds_file(ds_range=MIMX9_DS_RANGE)  # type: ignore
