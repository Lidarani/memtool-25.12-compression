# Copyright 2020-2025 NXP
"""Engine for handling data in pkl files for i.MX8."""
import json
import logging
import os
import traceback

from pycel import AddressRange
from pycel.excelutil import AddressCell

from memtool.common.config_data import ConfigData
from memtool.common.workspace import Workspace
from memtool.utils.constants import Const

from .xls_engine import XlsEngine
from .xls_mappings import CLOCK_FREQ_LABEL, DSF_CONFIG_SHEET, MIMX_DS_RANGE, REG_CONFIG_SHEET

PLL_REG_NAME_1 = 'HW_DRAM_PLL_CFG2_ADDR'
PLL_REG_NAME_2 = 'DRAM_PLL_FDIV_CTL0'
SET_CMD = 'memory set'


class XlsEngineMX8M(XlsEngine):
    """Loading and working with data from pkl for MIMX8 processors."""

    logger = logging.getLogger(__name__)

    def __init__(self, config_data: ConfigData):
        """Child class constructor."""
        super(XlsEngineMX8M, self).__init__(config_data)

    def update_config(self, config_data, config_map):  # type: ignore
        """Override update_config from XlsEngine.

        @param config_data: processor config data
        @param config_map: new params and values
        """
        super(XlsEngineMX8M, self).update_config(config_data, config_map)

        soc_name = config_data.soc_name

        # Inline ECC
        if Const.PARAM_S_INLINE_ECC_CONFIG in config_data.params:
            # set Inline ECC enabled state
            inline_ecc_enabled = False
            if Const.PARAM_S_INLINE_ECC_STATE in config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]:
                cell = str(
                    config_map[soc_name][Const.PARAM_S_INLINE_ECC_CONFIG].get(Const.PARAM_S_INLINE_ECC_STATE, ''))
                value = config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG][Const.PARAM_S_INLINE_ECC_STATE]
                inline_ecc_enabled = value == "ENABLED"
                if cell in self.excel.cell_map:
                    self.logger.debug('Set %s to %s', cell, value)
                    self.excel.set_value(cell, value)
                else:
                    self.logger.warning('Cell %s missing from cell map', cell)

            if inline_ecc_enabled:
                # set Inline ECC binary alignment status - it will be available only if Inline ECC is enabled
                is_ecc_binary_aligned_config = False
                if Const.PARAM_S_INLINE_ECC_BINARY_ALIGNED in config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]:
                    is_ecc_binary_aligned_config = config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG][
                        Const.PARAM_S_INLINE_ECC_BINARY_ALIGNED]
                else:
                    self.logger.warning('Inline ECC binary aligned info is missing!')
                    density_aligned = self.is_binary_aligned_density(config_data)
                    if density_aligned is None:
                        self.logger.error('ECC is enabled, but info needed to compute alignment is missing!')
                    else:
                        is_ecc_binary_aligned_config = density_aligned == 0

                # set Inline ECC granularity
                if Const.PARAM_S_INLINE_ECC_GRANULARITY in config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]:
                    granularity_config_cell = str(config_map[soc_name][Const.PARAM_S_INLINE_ECC_ALIGNED_REGIONS].get(
                        Const.PARAM_S_INLINE_ECC_GRANULARITY, ''))
                    if (not is_ecc_binary_aligned_config) and (
                            Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS in config_map[soc_name]):
                        granularity_config_cell = str(
                            config_map[soc_name][Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS].get(
                                Const.PARAM_S_INLINE_ECC_GRANULARITY, ''))
                    value = int(
                        config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG][Const.PARAM_S_INLINE_ECC_GRANULARITY])
                    if granularity_config_cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', granularity_config_cell, value)
                        self.excel.set_value(granularity_config_cell, value)
                    else:
                        self.logger.warning('Cell %s missing from cell map', granularity_config_cell)
                else:
                    self.logger.warning('Inline ECC granularity info is missing!')

                # set main memory region 0 info
                regions = {}
                if Const.PARAM_S_INLINE_ECC_REGIONS in config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]:
                    regions = config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG][Const.PARAM_S_INLINE_ECC_REGIONS]
                else:
                    self.logger.warning('Inline ECC regions info is missing!')

                ecc_worksheet = config_map[soc_name][Const.PARAM_S_INLINE_ECC_ALIGNED_REGIONS][
                    Const.PARAM_S_INLINE_ECC_CONFIG_SHEET]
                mem_regions_config_map_range = \
                    config_map[soc_name][Const.PARAM_S_INLINE_ECC_ALIGNED_REGIONS][Const.PARAM_S_INLINE_ECC_REGIONS][
                        "0"][Const.PARAM_S_INLINE_ECC_MEMORY_REGIONS]
                if (not is_ecc_binary_aligned_config) and (
                        Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS in config_map[soc_name]):
                    ecc_worksheet = config_map[soc_name][Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS][
                        Const.PARAM_S_INLINE_ECC_CONFIG_SHEET]
                    mem_regions_config_map_range = config_map[soc_name][Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS][
                        Const.PARAM_S_INLINE_ECC_REGIONS]["0"][Const.PARAM_S_INLINE_ECC_MEMORY_REGIONS]

                mem_region_protection = "D"
                mem_region_0 = mem_regions_config_map_range[1]
                for idx in range(0, 8):
                    mem_protection_cell_addr = str(
                        AddressCell(f"{mem_region_protection}{mem_region_0 - idx}", sheet=ecc_worksheet))
                    if str(idx) in regions:
                        value = regions[str(idx)]
                    else:
                        value = 'PROTECTED'

                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', mem_protection_cell_addr, value)
                        self.excel.set_value(mem_protection_cell_addr, value)
                    else:
                        self.logger.warning('Cell %s missing from cell map', mem_protection_cell_addr)

        try:
            # reduce pycel log - set log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            # update PLL reg
            value = self.search_pll_val(config_data)
            if value is not None:
                cell = self.search_pll_reg()
                self.logger.debug('PLL register found in cell %s', cell)
                self.excel.set_value(cell, value)

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('PLL register set ended with exception: %s', str(ex))

        finally:
            # restore pycel log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

    def collect_ecc_info(self, config_data, config_map):  # type: ignore
        """Dump ECC regions info to .json.

        @param config_data: processor config data
        @param config_map: new params and values
        """
        try:
            # set pycel log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            # delete old ECC regions info
            workspace_dir = Workspace.get_instance().get_location()
            ecc_info_file = os.path.join(workspace_dir, Const.ecc_file_name)
            if os.path.exists(ecc_info_file):
                os.remove(ecc_info_file)

            # reset ECC config data
            config_data.inline_ecc_config = []

            soc_name = config_data.soc_name
            if Const.PARAM_S_INLINE_ECC_CONFIG in config_data.params:
                inline_ecc_enabled = False
                if Const.PARAM_S_INLINE_ECC_STATE in config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]:
                    value = config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG][Const.PARAM_S_INLINE_ECC_STATE]
                    inline_ecc_enabled = value == "ENABLED"

                if inline_ecc_enabled:
                    is_binary_aligned = False
                    if Const.PARAM_S_INLINE_ECC_BINARY_ALIGNED in config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]:
                        is_binary_aligned = config_data.params[Const.PARAM_S_INLINE_ECC_CONFIG]\
                                                [Const.PARAM_S_INLINE_ECC_BINARY_ALIGNED]
                    else:
                        density_aligned = self.is_binary_aligned_density(config_data)
                        if density_aligned is None:
                            self.logger.error('ECC is enabled, but info needed to compute alignment is missing!')
                        else:
                            is_binary_aligned = density_aligned == 0

                    ecc_worksheet = config_map[soc_name][Const.PARAM_S_INLINE_ECC_ALIGNED_REGIONS]\
                                        [Const.PARAM_S_INLINE_ECC_CONFIG_SHEET]
                    regions_config_map = config_map[soc_name][Const.PARAM_S_INLINE_ECC_ALIGNED_REGIONS]\
                                        [Const.PARAM_S_INLINE_ECC_REGIONS]
                    if (not is_binary_aligned) and \
                            (Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS in config_map[soc_name]):
                        ecc_worksheet = config_map[soc_name][Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS]\
                                            [Const.PARAM_S_INLINE_ECC_CONFIG_SHEET]
                        regions_config_map = config_map[soc_name][Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS]\
                                            [Const.PARAM_S_INLINE_ECC_REGIONS]

                    regions_info = {}
                    attributes = [("B", Const.PARAM_S_INLINE_ECC_REGION_START),
                                  ("C", Const.PARAM_S_INLINE_ECC_REGION_DENSITY),
                                  ("D", Const.PARAM_S_INLINE_ECC_REGION_ATTRIBUTES)]
                    for reg in regions_config_map.keys():
                        self.logger.debug('Loading region %s...', reg)

                        self.logger.debug('Loading main memory region %s...', reg)
                        mem_region_id = "inlineEccConfig.eccConfigBinaryAligned.mainMemoryRegion"
                        if not is_binary_aligned:
                            mem_region_id = f"inlineEccConfig.eccConfigNonBinaryAligned.eccNonBinaryAligned." \
                                            f"{reg}.mainMemoryRegion{reg}" if reg == "0" else \
                                f"inlineEccConfig.eccConfigNonBinaryAligned.eccNonBinaryAligned.{reg}.mainMemoryRegion"

                        main_memory_regions = []
                        mem_regions_config_map_range = regions_config_map[reg][Const.PARAM_S_INLINE_ECC_MEMORY_REGIONS]
                        line_idx = 0
                        for idx in range(0, mem_regions_config_map_range[1] - mem_regions_config_map_range[0] + 1):
                            self.logger.debug('Loading main memory region xls line idx %d, component table line %d...',
                                              mem_regions_config_map_range[0] + idx, line_idx)
                            memory_region_attributes = {}
                            completed_cells = 0
                            for attr in attributes:
                                # skip ecc attribute for memory region 0
                                if reg == "0" and attr[0] == attributes[2][0]:
                                    completed_cells += 1
                                    continue

                                mem_protection_cell_addr = str(AddressCell(\
                                            f"{attr[0]}{mem_regions_config_map_range[0] + idx}", sheet=ecc_worksheet))
                                value = str(self.excel.evaluate(mem_protection_cell_addr))
                                property = f"{mem_region_id}.{line_idx}.{attr[1]}"
                                self.logger.debug('Read from cell = %s value = %s property = %s', \
                                                    mem_protection_cell_addr, value, property)
                                if value != "":
                                    regions_info[property] = value
                                    memory_region_attributes[attr[1]] = value
                                    completed_cells += 1
                            if len(memory_region_attributes) >= 2:
                                main_memory_regions.append(memory_region_attributes)
                            if completed_cells == len(attributes):
                                line_idx += 1
                        config_data.inline_ecc_config.append(main_memory_regions)

                        self.logger.debug('Loading ecc parity region %s....', reg)
                        ecc_region_id = "inlineEccConfig.eccConfigBinaryAligned.eccParityRegionSelection"
                        if not is_binary_aligned:
                            ecc_region_id = f"inlineEccConfig.eccConfigNonBinaryAligned.eccNonBinaryAligned." \
                                            f"{reg}.eccParityRegion"

                        ecc_regions_config_map_range = regions_config_map[reg][Const.PARAM_S_INLINE_ECC_PARITY_REGIONS]
                        line_idx = 0
                        for idx in range(0, ecc_regions_config_map_range[1] - ecc_regions_config_map_range[0] + 1):
                            self.logger.debug('Loading ecc parity region xls line idx %d, component table line %d...',
                                              ecc_regions_config_map_range[0] + idx, line_idx)
                            completed_cells = 0
                            for attr in attributes:
                                ecc_protection_cell_addr = str(AddressCell(\
                                            f"{attr[0]}{ecc_regions_config_map_range[0] + idx}", sheet=ecc_worksheet))
                                value = str(self.excel.evaluate(ecc_protection_cell_addr))
                                property = f"{ecc_region_id}.{line_idx}.{attr[1]}"
                                self.logger.debug('Read from cell = %s value = %s property = %s', \
                                            ecc_protection_cell_addr, value, property)
                                if value != "":
                                    regions_info[property] = value
                                    completed_cells += 1
                            if completed_cells == len(attributes):
                                line_idx += 1

                    # create file with ECC regions info
                    with open(ecc_info_file, "wt", encoding="utf-8") as f:
                        f.write(json.dumps(regions_info, indent=4))

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('ECC info collection ended with exception: %s', str(ex))

        finally:
            # restore pycel log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

    def search_pll_reg(self):  # type: ignore
        """Search in RPA xls in the DS file sheet for the PLL register cell.

        @return: the cell coordinates
        """
        try:
            # set pycel log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            count = 1
            cell = ''
            for cell_index in AddressRange("A1:E460", sheet=DSF_CONFIG_SHEET).rows:
                row_data = str(self.excel.evaluate(cell_index))
                if (PLL_REG_NAME_1 in row_data or PLL_REG_NAME_2 in row_data) and SET_CMD in row_data:
                    cell = f'{DSF_CONFIG_SHEET}!D{count}'
                    break
                count += 1

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('PLL register search ended with exception: %s', str(ex))
            return ''

        finally:
            # restore pycel log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

        return cell

    @staticmethod
    def search_pll_val(config_data):  # type: ignore
        """Search in PLL table for register the value corresponding to the current frequency.

        @return: register value as hex string
        """
        pll_reg = {
                    '200': '0x19060',
                    '267': '0x59100',
                    '303': '0x65100',
                    '333': '0x6f100',
                    '400': '0x19030',
                    '533': '0x215300',
                    '600': '0x19020',
                    '625': '0x271300',
                    '650': '0x145180',
                    '667': '0x29b300',
                    '700': '0xaf0c0',
                    '733': '0x2dd300',
                    '750': '0x7d080',
                    '800': '0x32030',
                    '900': '0x4b040',
                    '933': '0x137100',
                    '1000': '0x7d060',
                    '1050': '0xaf080',
                    '1066': '0x215180',
                    '1100': '0x1130c0',
                    '1200': '0x19010',
                    '1300': '0x1450c0',
                    '1450': '0x2d5180',
                    '1500': '0x7d040',
                    '1600': '0x64030',
                    '1800': '0x4b020',
                    '2000': '0xFA031'
                    }
        pll_reg_850 = {
                    '200': '0x80',
                    '267': '0x100380',
                    '303': '0x981e00',
                    '333': '0x100480',
                    '400': '0x180',
                    '533': '0x100780',
                    '600': '0x280',
                    '625': '0x180c00',
                    '650': '0x80600',
                    '667': '0x100980',
                    '700': '0x300',
                    '733': '0x100a80',
                    '750': '0x80700',
                    '800': '0x380',
                    '900': '0x400',
                    '933': '0x100d80',
                    '1000': '0x480',
                    '1050': '0x80a00',
                    '1066': '0x100f80',
                    '1100': '0x500',
                    '1200': '0x580',
                    '1300': '0x600',
                    '1450': '0x80e00',
                    '1500': '0x700',
                    '1600': '0x780'
                    }

        if CLOCK_FREQ_LABEL in config_data.params[Const.PARAM_S_BASIC]:
            if config_data.soc_name == 'MIMX8M':
                return pll_reg_850[config_data.params[Const.PARAM_S_BASIC][CLOCK_FREQ_LABEL]]

            return pll_reg[config_data.params[Const.PARAM_S_BASIC][CLOCK_FREQ_LABEL]]

        return None

    def get_ds_file(self, ds_range=MIMX_DS_RANGE, sheet=DSF_CONFIG_SHEET) -> str:  # type: ignore
        """Override get_ds_file fromXlsEngine.

        @param ds_range: cell range of interest from the excel sheet
        @param sheet: name of the sheet of interest from the excel file
        @return: the content of the ds file as a str
        """
        return super(XlsEngineMX8M, self).get_ds_file(ds_range=MIMX_DS_RANGE) # type: ignore
