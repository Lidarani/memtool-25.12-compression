# Copyright 2020-2025 NXP
"""Generic engine for handling data in pkl files."""
import logging
import traceback

from pycel import AddressRange, ExcelCompiler
from pycel.excelutil import coerce_to_number

from memtool.common.config_data import ConfigData
from memtool.utils.constants import Const

from .xls_mappings import DSF_CONFIG_SHEET, transform_value

DS_FILE_LINE_NO = 350


class XlsEngine:
    """Loading and working with data from pkl built from excel spreadsheet."""

    logger = logging.getLogger(__name__)

    def __init__(self, config_data: ConfigData):
        """Parent class constructor."""
        try:
            # set pycel log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            self.excel = self.load_excel(config_data)

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('Xls engine creation ended with exception: %s', str(ex))

        finally:
            # restore pycel log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

    def load_excel(self, config_data: ConfigData):  # type: ignore
        """Get the data from the pkl file corresponding to the processor config.

        @param config_data: processor config data
        @return: the spreadsheet from pkl loaded in ExcelCompiler or None if .pkl doesn't exist
        """
        pkl_file_abs_path = config_data.get_target_pkl_file(config_data.soc_name, config_data.mem_type)
        if pkl_file_abs_path is None:
            return None

        self.logger.debug("Using file %s", pkl_file_abs_path)
        return ExcelCompiler.from_file(pkl_file_abs_path)

    def get_ds_file(self, ds_range="A1:E360", sheet=DSF_CONFIG_SHEET) -> str:  # type: ignore
        """Format data from loaded spreadsheet as .ds file content.

        @param ds_range: cell range of interest from the Excel sheet
        @param sheet: name of the sheet of interest from the Excel file
        @return: the content of the ds file as a str
        """
        try:
            # set pycel log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            ds_file = ""
            for cell in AddressRange(ds_range, sheet=sheet).rows:
                row_data = self.excel.evaluate(cell)
                row_str = ''
                for data in row_data:
                    if data is not None:
                        row_str += str(data).strip() + '\t'
                ds_file += row_str.strip() + '\n'

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('Getting .ds file ended with exception: %s', str(ex))
            return ''

        finally:
            # restore pycel log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

        return ds_file

    def is_binary_aligned_density(self, config_data: ConfigData):  # type: ignore
        """Determine if density is aligned or not.

        @param config_data: processor config data
        @return: None if there are no data to determine alignment status, 0 if density is aligned or <> 0 if is not
        aligned
        """
        if Const.PARAM_S_BASIC not in config_data.params:
            return None

        if Const.PARAM_S_BASIC_DENSITY_PER_CHANNEL not in config_data.params[
            Const.PARAM_S_BASIC] or Const.PARAM_S_BASIC_NUM_ROW_ADDRESS not in config_data.params[Const.PARAM_S_BASIC]:
            return None

        density_per_channel = int(config_data.params[Const.PARAM_S_BASIC][Const.PARAM_S_BASIC_DENSITY_PER_CHANNEL])
        if density_per_channel in [3, 6, 12]:
            num_row_address = int(config_data.params[Const.PARAM_S_BASIC][Const.PARAM_S_BASIC_NUM_ROW_ADDRESS])
            return num_row_address - 14

        return 0

    def update_config(self, config_data, config_map):  # type: ignore
        """Update params in config data.

        @param config_data: processor config data
        @param config_map: new params and values
        """
        try:
            # set pycel log level to ERROR
            if Const.HIDE_DETAILED_DEBUG_INFO:
                log_level = logging.root.getEffectiveLevel()
                logging.root.setLevel(logging.ERROR)

            soc_name = config_data.soc_name

            # Basic input config
            assert Const.PARAM_S_BASIC in config_data.params
            for config in config_data.params[Const.PARAM_S_BASIC].keys():
                if config in config_map.keys():
                    if str(config_map[config]) in self.excel.cell_map:
                        value = config_data.params[Const.PARAM_S_BASIC][config]
                        if config == Const.PARAM_S_BASIC_MEM_TYPE:
                            if ConfigData.DEVICES_INFO[soc_name].is_imx9():
                                if value == "2":
                                    value = "LPDDR4"
                                elif value == "3":
                                    value = "LPDDR4x"
                                elif value == "4":
                                    value = "LPDDR5"
                                elif value == "5":
                                    value = "LPDDR5x"
                                self.excel.set_value(config_map[config], value)
                        else:
                            self.excel.set_value(config_map[config], coerce_to_number(value))
                        msg = f'Set {config_map[config]} to %d'
                        self.logger.debug(msg)

            # UART port selection
            if Const.PARAM_S_BOARD_CONFIG_UART_PORTS in config_data.params[Const.PARAM_S_BOARD_CONFIG] \
                    and Const.PARAM_S_BOARD_CONFIG_UART_PORTS in config_map.keys() \
                    and str(config_map[Const.PARAM_S_BOARD_CONFIG_UART_PORTS]) in self.excel.cell_map:
                self.excel.set_value(config_map[Const.PARAM_S_BOARD_CONFIG_UART_PORTS],
                    coerce_to_number(config_data.params[Const.PARAM_S_BOARD_CONFIG]\
                                        [Const.PARAM_S_BOARD_CONFIG_UART_PORTS]))

            # SoC specific values
            if soc_name in config_map:
                # LP mode
                if Const.PARAM_S_BASIC_LP4X_MODE in config_map[soc_name]:
                    lp_mode = config_data.lp_mode
                    cell = str(config_map[soc_name][Const.PARAM_S_BASIC_LP4X_MODE])
                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %d', cell, lp_mode)
                        self.excel.set_value(cell, lp_mode)

                # freq2SetPoint
                if ("freq2SetPoint" in config_map[soc_name]) \
                        and ("freq2SetPoint" in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name]["freq2SetPoint"])
                    if cell in self.excel.cell_map:
                        value = config_data.params[Const.PARAM_S_BASIC]["freq2SetPoint"]
                        self.logger.debug('Set %s to %s', cell, value)
                        self.excel.set_value(cell, coerce_to_number(value))

                # freqSetPointD3
                if ("freqSetPointD3" in config_map[soc_name]) \
                        and ("freqSetPointD3" in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name]["freqSetPointD3"])
                    if cell in self.excel.cell_map:
                        value = config_data.params[Const.PARAM_S_BASIC]["freqSetPointD3"]
                        self.logger.debug('Set %s to %s', cell, value)
                        self.excel.set_value(cell, coerce_to_number(value))

                # Number of pstates
                if Const.PARAM_S_BASIC_NUM_PSTATES in config_map[soc_name]:
                    cell = str(config_map[soc_name][Const.PARAM_S_BASIC_NUM_PSTATES])
                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %d', cell, config_data.num_pstates)
                        self.excel.set_value(cell, config_data.num_pstates)

                # Temperature derating selection
                if Const.PARAM_S_BOARD_CONFIG_TEMP_DERATING in config_map[soc_name]:
                    cell = str(config_map[soc_name][Const.PARAM_S_BOARD_CONFIG_TEMP_DERATING])
                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', cell,
                                config_data.params[Const.PARAM_S_BASIC].get(Const.PARAM_S_BOARD_CONFIG_TEMP_DERATING))
                        self.excel.set_value(cell,
                                config_data.params[Const.PARAM_S_BASIC].get(Const.PARAM_S_BOARD_CONFIG_TEMP_DERATING))

                # DBI selection
                if Const.PARAM_S_BOARD_CONFIG_DBI in config_map[soc_name]:
                    cell = str(config_map[soc_name][Const.PARAM_S_BOARD_CONFIG_DBI])
                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', cell,
                                config_data.params[Const.PARAM_S_BOARD_CONFIG].get(Const.PARAM_S_BOARD_CONFIG_DBI))
                        self.excel.set_value(cell,
                                config_data.params[Const.PARAM_S_BOARD_CONFIG].get(Const.PARAM_S_BOARD_CONFIG_DBI))

                # number of channels
                if ("numberOfChannels" in config_map[soc_name]) and (
                        "numberOfChannels" in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name]["numberOfChannels"])
                    if cell in self.excel.cell_map:
                        value = coerce_to_number(config_data.params[Const.PARAM_S_BASIC]["numberOfChannels"])
                        self.logger.debug('Set %s to %d', cell, value)
                        self.excel.set_value(cell, value)

                # turnarounds options
                if ("turnaroundsOptions" in config_map[soc_name]) and (
                        "turnaroundsOptions" in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name]["turnaroundsOptions"])
                    if cell in self.excel.cell_map:
                        value = coerce_to_number(config_data.params[Const.PARAM_S_BASIC]["turnaroundsOptions"])
                        self.logger.debug('Set %s to %d', cell, value)
                        self.excel.set_value(cell, value)

                # mrr snoop workaround
                if (Const.MRR_SNOOP in config_map[soc_name]) and (
                        Const.MRR_SNOOP in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name][Const.MRR_SNOOP])
                    if cell in self.excel.cell_map:
                        value = coerce_to_number(config_data.params[Const.PARAM_S_BASIC][Const.MRR_SNOOP])
                        self.logger.debug('Set %s to %d', cell, value)
                        self.excel.set_value(cell, value)

                # rx replica workaround
                if (Const.RX_REPLICA in config_map[soc_name]) and (
                        Const.RX_REPLICA in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name][Const.RX_REPLICA])
                    if cell in self.excel.cell_map:
                        value = coerce_to_number(config_data.params[Const.PARAM_S_BASIC][Const.RX_REPLICA])
                        self.logger.debug('Set %s to %d', cell, value)
                        self.excel.set_value(cell, value)

                # spread spectrum
                if (Const.PARAM_S_SS_ENABLE in config_map[soc_name]) and (
                        Const.PARAM_S_SS_ENABLE in config_data.params[Const.PARAM_S_BASIC]):
                    cell = str(config_map[soc_name][Const.PARAM_S_SS_ENABLE])
                    if cell in self.excel.cell_map:
                        value = coerce_to_number(config_data.params[Const.PARAM_S_BASIC][Const.PARAM_S_SS_ENABLE])
                        self.logger.debug('Set %s to %d', cell, value)
                        self.excel.set_value(cell, value)

            # ODT configuration
            if Const.PARAM_S_ODT in config_data.params and soc_name in config_map \
                    and Const.PARAM_S_ODT in config_map[soc_name]:
                for odt_section in config_data.params[Const.PARAM_S_ODT]:  # odtReadConfig, odtWriteConfig
                    if odt_section in config_map[soc_name][Const.PARAM_S_ODT]:
                        for odt_config in config_data.params[Const.PARAM_S_ODT][odt_section]:
                            if odt_config in config_map[soc_name][Const.PARAM_S_ODT][odt_section]:
                                cell = str(config_map[soc_name][Const.PARAM_S_ODT][odt_section].get(odt_config, ''))
                                value = config_data.params[Const.PARAM_S_ODT][odt_section][odt_config]
                                if cell in self.excel.cell_map:
                                    if soc_name not in ("MIMX91", "MIMX93", "MIMX943", "MIMX95", "MIMX95_B0", "MIMX952",
                                                         "LX"):
                                        value = transform_value(odt_config, value)
                                    else:
                                        value = coerce_to_number(value)
                                        self.logger.debug('Set %s to %d')
                                    self.excel.set_value(cell, value)
                                else:
                                    self.logger.warning('Cell %s missing from cell map!')
                            else:
                                self.logger.warning('%s is missing from config_map[%s][%s][%s]!',
                                                    odt_config, soc_name, Const.PARAM_S_ODT, odt_section)
                    else:
                        self.logger.warning('%s is missing from config_map[%s][%s]!',
                                            odt_section, soc_name, Const.PARAM_S_ODT)

            # CA ODT configuration
            if Const.PARAM_S_CA_ODT in config_data.params and soc_name in config_map \
                    and Const.PARAM_S_CA_ODT in config_map[soc_name]:
                for odt_config in config_data.params[Const.PARAM_S_CA_ODT]:
                    if odt_config in config_map[soc_name][Const.PARAM_S_CA_ODT]:
                        cell = str(config_map[soc_name][Const.PARAM_S_CA_ODT].get(odt_config, ''))
                        value = config_data.params[Const.PARAM_S_CA_ODT][odt_config]
                        if cell in self.excel.cell_map:
                            if soc_name not in ("MIMX91", "MIMX93", "LX"):
                                value = transform_value(odt_config, value)
                            else:
                                value = coerce_to_number(value)
                                self.logger.debug('Set %s to %d')
                            self.excel.set_value(cell, value)
                        else:
                            self.logger.warning('Cell %s missing from cell map!')
                    else:
                        self.logger.warning('%s is missing from config_map[%s][%s]!',
                                            odt_config, soc_name, Const.PARAM_S_CA_ODT)

            # CA configuration
            if Const.PARAM_S_CA_VREF in config_data.params and soc_name in config_map \
                    and Const.PARAM_S_CA_VREF in config_map[soc_name]:
                for ca_config in config_data.params[Const.PARAM_S_CA_VREF]:
                    if ca_config in config_map[soc_name][Const.PARAM_S_CA_VREF]:
                        cell = str(config_map[soc_name][Const.PARAM_S_CA_VREF].get(ca_config, ''))
                        value = coerce_to_number(config_data.params[Const.PARAM_S_CA_VREF][ca_config])
                        if cell in self.excel.cell_map:
                            self.logger.debug('Set %s to %s', cell, value)
                            self.excel.set_value(cell, value)
                        else:
                            self.logger.warning('Cell %s missing from cell map', cell)
                    else:
                        self.logger.warning('%s is missing from config_map[%s][%s]!',
                                            ca_config, soc_name, Const.PARAM_S_CA_VREF)

            # DQ configuration
            if Const.PARAM_S_DQ_VREF in config_data.params and soc_name in config_map \
                    and Const.PARAM_S_DQ_VREF in config_map[soc_name]:
                for dq_config in config_data.params[Const.PARAM_S_DQ_VREF]:
                    if dq_config in config_map[soc_name][Const.PARAM_S_DQ_VREF]:
                        cell = str(config_map[soc_name][Const.PARAM_S_DQ_VREF].get(dq_config, ''))
                        value = coerce_to_number(config_data.params[Const.PARAM_S_DQ_VREF][dq_config])
                        if cell in self.excel.cell_map:
                            self.logger.debug('Set %s to %s', cell, value)
                            self.excel.set_value(cell, value)
                        else:
                            self.logger.warning('Cell %s missing from cell map', cell)
                    else:
                        self.logger.warning('%s is missing from config_map[%s][%s]!',
                                            dq_config, soc_name, Const.PARAM_S_DQ_VREF)

            # Address mirroring
            if Const.PARAM_S_ADDR_MIRRORING in config_data.params and soc_name in config_map \
                    and Const.PARAM_S_ADDR_MIRRORING in config_map[soc_name]:
                for am_config in config_data.params[Const.PARAM_S_ADDR_MIRRORING]:
                    if am_config in config_map[soc_name][Const.PARAM_S_ADDR_MIRRORING]:
                        cell = str(config_map[soc_name][Const.PARAM_S_ADDR_MIRRORING].get(am_config, ''))
                        value = coerce_to_number(config_data.params[Const.PARAM_S_ADDR_MIRRORING][am_config])
                        if cell in self.excel.cell_map:
                            self.logger.debug('Set %s to %s', cell, value)
                            self.excel.set_value(cell, value)
                        else:
                            self.logger.warning('Cell %s missing from cell map', cell)
                    else:
                        self.logger.warning('%s is missing from config_map[%s][%s]',
                                            am_config, soc_name, Const.PARAM_S_ADDR_MIRRORING)

            # DQ mappings
            if Const.PARAM_S_BUS in config_data.params:
                for bit in config_data.params[Const.PARAM_S_BUS]:
                    cell = str(config_map[soc_name][Const.PARAM_S_BUS][bit])
                    value = coerce_to_number(config_data.params[Const.PARAM_S_BUS][bit])
                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', cell, value)
                        self.excel.set_value(cell, value)
                    else:
                        self.logger.warning('Cell %s missing from cell map', cell)

            # CA mappings
            if Const.PARAM_S_CA_BUS in config_data.params:
                for bit in config_data.params[Const.PARAM_S_CA_BUS]:
                    cell = str(config_map[soc_name][Const.PARAM_S_CA_BUS][bit])
                    value = coerce_to_number(config_data.params[Const.PARAM_S_CA_BUS][bit])
                    if cell in self.excel.cell_map:
                        self.logger.debug('Set %s to %s', cell, value)
                        self.excel.set_value(cell, value)
                    else:
                        self.logger.warning('Cell %s missing from cell map', cell)

            # Message block
            if Const.PARAM_S_PHY in config_data.params and "messageBlock[0]" in config_data.params[Const.PARAM_S_PHY] \
                    and Const.PARAM_S_PHY in config_map[soc_name] \
                    and "messageBlock[0]" in config_map[soc_name][Const.PARAM_S_PHY]:
                # messageBlock[0]
                for msg_blk_cfg in config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"].keys():
                    if msg_blk_cfg in config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]:
                        cell = str(config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"].get(msg_blk_cfg, ''))
                        value = coerce_to_number(config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"][msg_blk_cfg])
                        if cell in self.excel.cell_map:
                            self.logger.debug('Set %s to %s', cell, value)
                            self.excel.set_value(cell, value)
                        else:
                            self.logger.warning('Cell %s missing from cell map', cell)
                # handle MR14 / MR6; their values are distributed to multiple cells
                # if (not ConfigData.is_phy_v3(config_data.snps_phy_info)) and \
                #     "MR14_A0" in config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]:
                #     mr14_value = int(config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["MR14_A0"], 16)
                #     mr14_value = mr14_value & 0x7F
                #     if not ("MR14_VrefRange" in config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]
                #             and "MR14_VrefValue" in config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]):
                #         self.logger.error('MR14 cells are missing from xls mapping')
                #     else:
                #         cell = str(config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]["MR14_VrefRange"])
                #         if cell in self.excel.cell_map:
                #             mr14_vref_range_value = mr14_value >> 6
                #             self.logger.debug('Set %s to %s', cell, mr14_vref_range_value)
                #             self.excel.set_value(cell, mr14_vref_range_value)
                #         else:
                #             self.logger.warning('Cell %s missing from cell map', cell)

                #         cell = str(config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]["MR14_VrefValue"])
                #         if cell in self.excel.cell_map:
                #             mr14_vref_value = mr14_value & 0x3F
                #             self.logger.debug('Set %s to %s', cell, mr14_vref_value)
                #             self.excel.set_value(cell, mr14_vref_value)
                #         else:
                #             self.logger.warning('Cell %s missing from cell map', cell)
                # elif "MR6" in config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]:
                #     mr6_value = int(config_data.params[Const.PARAM_S_PHY]["messageBlock[0]"]["MR6"], 16)
                #     mr6_value = mr6_value & 0x7F
                #     if not ("MR6_VrefRange" in config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]
                #             and "MR6_VrefValue" in config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]):
                #         self.logger.error('MR6 cells are missing from xls mapping')
                #     else:
                #         cell = str(config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]["MR6_VrefRange"])
                #         if cell in self.excel.cell_map:
                #             mr6_vref_range_value = mr6_value >> 6
                #             self.logger.debug('Set %s to %s', cell, mr6_vref_range_value)
                #             self.excel.set_value(cell, mr6_vref_range_value)
                #         else:
                #             self.logger.warning('Cell %s missing from cell map', cell)

                #         cell = str(config_map[soc_name][Const.PARAM_S_PHY]["messageBlock[0]"]["MR6_VrefValue"])
                #         if cell in self.excel.cell_map:
                #             mr6_vref_value = mr6_value & 0x3F
                #             self.logger.debug('Set %s to %s', cell, mr6_vref_value)
                #             self.excel.set_value(cell, mr6_vref_value)
                #         else:
                #             self.logger.warning('Cell %s missing from cell map', cell)

            # PHY log level
            if Const.PARAM_S_TC in config_data.params and Const.PARAM_S_TC_PHY_LOG in config_data.params[
                Const.PARAM_S_TC] and Const.PARAM_S_TC in config_map[soc_name] and Const.PARAM_S_TC_PHY_LOG in \
                    config_map[soc_name][Const.PARAM_S_TC]:
                self.excel.set_value(config_map[soc_name][Const.PARAM_S_TC][Const.PARAM_S_TC_PHY_LOG],
                                     coerce_to_number(config_data.params[Const.PARAM_S_TC][Const.PARAM_S_TC_PHY_LOG]))

        except Exception as ex:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.debug('Error traceback:')
                traceback.print_exc()
            self.logger.exception('Configuration update ended with exception: %s', str(ex))

        finally:
            # restore pycel log level
            if Const.HIDE_DETAILED_DEBUG_INFO:
                logging.root.setLevel(log_level)

    def collect_ecc_info(self, config_data, config_map):  # type: ignore
        """Dump ECC regions info to .json.

        @param config_data: processor config data
        @param config_map: new params and values
        """
        pass

    def add_device_info(self, value, key, info, update_value: bool = False):  # type: ignore
        """Add device info parameter.

        @param value: value found for key in the RPA dictionary
        @param key: key to be added to the default configuration
        @param info: dictionary that defines the default configuration
        @param update_value: True if the value must be updated before adding it to the default configuration dictionary
        """
        if isinstance(value, dict):
            info[key] = {}
            for child in value:
                child_address = value[child]
                self.add_device_info(child_address, child, info[key], update_value)
        else:
            try:
                # set pycel log level to ERROR
                if Const.HIDE_DETAILED_DEBUG_INFO:
                    log_level = logging.root.getEffectiveLevel()
                    logging.root.setLevel(logging.ERROR)

                cell_address = str(value)
                if cell_address in self.excel.cell_map:
                    cell_value = str(self.excel.evaluate(cell_address))
                    if update_value:
                        cell_value = transform_value(key, cell_value, False)  # type: ignore
                    self.logger.debug('%s cell is %s', cell_address, cell_value)
                    info[key] = str(cell_value)
                else:
                    self.logger.warning('Cell %s missing from cell map', cell_address)

            except Exception as ex:
                if self.logger.getEffectiveLevel() == logging.DEBUG:
                    self.logger.debug('Error traceback:')
                    traceback.print_exc()
                self.logger.exception('Add device info ended with exception: %s', str(ex))

            finally:
                # restore pycel log level
                if Const.HIDE_DETAILED_DEBUG_INFO:
                    logging.root.setLevel(log_level)

    def collect_device_info(self, config_data, config_map) -> dict:  # type: ignore
        """Collect device parameters default values.

        @param config_data: config_data: processor config data
        @param config_map: parameters cell addresses
        @return: dictionary with device parameters or None if they can't be determined
        """
        device_info = {Const.PARAM_S_BASIC: {}}  # type: ignore
        soc_name = config_data.soc_name
        update_value = ((not ConfigData.DEVICES_INFO[soc_name].is_imx9()) and "LX" not in soc_name)

        # get common parameters
        for param in config_map:
            address = config_map[param]
            if not isinstance(address, dict):
                self.add_device_info(address, param, device_info[Const.PARAM_S_BASIC], update_value)

        # get soc specific parameters
        for param in config_map[soc_name]:
            address = config_map[soc_name][param]
            if not isinstance(address, dict):
                self.add_device_info(address, param, device_info[Const.PARAM_S_BASIC])
            else:
                self.add_device_info(address, param, device_info, update_value)

        # for ecc config, we should keep only state and granularity settings
        if Const.PARAM_S_INLINE_ECC_CONFIG in device_info:
            granularity = None
            for ecc_setting in [Const.PARAM_S_INLINE_ECC_ALIGNED_REGIONS, Const.PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS]:
                if ecc_setting in device_info:
                    if granularity is None and Const.PARAM_S_INLINE_ECC_GRANULARITY in device_info[ecc_setting]:
                        granularity = device_info[ecc_setting][Const.PARAM_S_INLINE_ECC_GRANULARITY]
                    del device_info[ecc_setting]
            if granularity is not None:
                device_info[Const.PARAM_S_INLINE_ECC_CONFIG][Const.PARAM_S_INLINE_ECC_GRANULARITY] = granularity

        return device_info
