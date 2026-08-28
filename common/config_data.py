# Copyright 2021-2025 NXP
"""TODO:summary line."""
import ast
import json
import logging
import os
import re
from copy import deepcopy
from enum import Enum
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Dict, List, Optional

from pycel import AddressCell

from memtool.common.dcd_commands import check_ds_validity
from memtool.common.device import DeviceInfo
from memtool.common.options import Options
from memtool.common.workspace import Workspace
from memtool.phyinit.phy_utils import PhyPhase
from memtool.utils.constants import Const, JsonConfigField
from memtool.utils.helper import merge_dict


class SnpsFirmware(Enum):
    """Synopsys supported firmwares."""

    # Synopsys FW is defined by tuple (id, name, version)
    SnpsFW_Undefined = (-1, "Undefined", 0)
    SnpsFW_2017_09 = (0, "2017.09", 2)
    SnpsFW_2018_10 = (1, "2018.10", 2)
    SnpsFW_2019_04 = (2, "2019.04", 2)
    SnpsFW_2020_06 = (3, "2020.06", 2)
    SnpsFW_2022_01 = (4, "2022.01", 2)
    SnpsFW_2023_06 = (5, "2023.06", 3)
    SnpsFW_2023_11 = (6, "2023.11", 3)
    SnpsFW_2024_09 = (7, "2024.09", 3)
    SnpsFW_2024_09_SP2 = (8, "2024.09-SP2", 3)

    def __init__(self, id: int, name: str, version: int) -> None:
        """Constructor.

        @param id: firmware id
        @param name: firmware display name
        @param version: PHY version
        """
        self._id = id
        self._name = name
        self._version = version

    @property
    def id(self) -> int:
        """FW id."""
        return self._id

    @property
    def name(self) -> str:
        """FW display name."""
        return self._name

    @property
    def version(self) -> str:
        """PHY version."""
        return self._version  # type: ignore

    @staticmethod
    def from_id(id: int) -> 'SnpsFirmware':
        """Converts SnpsFirmware from given id.

        @param id: id to be converted
        @return: corresponding firmware type or SnpsFW_Undefined if the given id is not defined
        """
        for fw in SnpsFirmware:
            if fw._id == id:
                return fw
        return SnpsFirmware.SnpsFW_Undefined

    @staticmethod
    def from_name(name: str) -> 'SnpsFirmware':
        """Converts SnpsFirmware from given name.

        @param name: name to be converted
        @return: corresponding firmware type or SnpsFW_Undefined if the given name is not defined
        """
        for fw in SnpsFirmware:
            if fw._name == name:
                return fw
        return SnpsFirmware.SnpsFW_Undefined

    @staticmethod
    def get_names() -> list:
        """Get the names of supported firmwares."""
        return [fw.name for fw in SnpsFirmware if fw != SnpsFirmware.SnpsFW_Undefined]

    @staticmethod
    def get_values() -> dict:
        """Get the firmware dictionary (id->name)."""
        fws = {}
        for fw in SnpsFirmware:
            fws[fw.id] = fw.name
        return fws

    @staticmethod
    def get_supported_firmwares() -> list:
        """Get the supported firmwares."""
        return [fw for fw in SnpsFirmware if fw != SnpsFirmware.SnpsFW_Undefined]


class ConfigData:
    """Hold configuration data for target and tests."""

    logger = logging.getLogger(__name__)

    # device info cache
    DEVICES_INFO = {}  # type: ignore

    # Supported memory types (it's given by ddr type and lp mode).
    MEMORY_TYPES = {0: 'ddr4', 1: 'ddr3', 2: 'lpddr4', 3: 'lpddr4x', 4: 'lpddr5', 5: 'lpddr5x'}

    # Supported DRAM types (values in sync with RPA values)
    DRAM_TYPES = {0: 'ddr4', 1: 'ddr3', 2: 'lpddr4', 4: 'lpddr5'}

    # Supported DDR DIMM types.
    DIMM_TYPES = {0: 'udimm', 1: 'sodimm', 2: 'rdimm', 3: 'lrdimm', 4: 'nodimm'}

    # Hardware Identification System (HIDS) dictionary for tracking hardware configurations
    # This dictionary is used only by DDR Expert
    HIDS = {}  # type: ignore

    @staticmethod
    def is_ddr5(mem_type: str) -> bool:
        """Check if given mem_type is DDR5."""
        return mem_type in ['lpddr5', 'lpddr5x']

    @staticmethod
    def is_phy_v2(fw: SnpsFirmware) -> bool:
        """Check if given firmware is version 2."""
        return fw.version == 2

    @staticmethod
    def is_phy_v3(fw: SnpsFirmware) -> bool:
        """Check if given firmware is version 3."""
        return fw.version == 3

    @staticmethod
    def get_memory_id(memory_name: str) -> int:
        """Get memory id from MEMORY_TYPES for given memory name.

        @memory_name: name for which we need to determine the id
        @return: memory id or -1 if the memory name was not found in the list of supported memories
        """
        for key, name in ConfigData.MEMORY_TYPES.items():
            if name == memory_name.lower():
                return key
        return -1

    def __init__(self, data_dir_path: str, params=None, use_default_rpa=False):  # type: ignore
        """Config data constructor.

        @param data_dir_path: path to data dir
        @param params: params to be updated
        @param use_default_rpa: flag that signals usage of default RPA configuration
        """
        ConfigData.DEVICES_INFO = {}  # type: ignore
        self.__supported_devices = []  # type: ignore
        self.__data_dir = None
        self.data_dir = data_dir_path

        self.__soc_name = None
        self.__use_default_rpa_config = use_default_rpa
        self.__fw_bin_info = None
        self.__skip_download = None
        self.__snps_phy_info = SnpsFirmware.SnpsFW_Undefined
        self.__ds_file_txt = ''
        self.__ds_is_valid = False
        self.__train_2d = 1

        self.params = params
        self.misc_sys_params = {}  # type: ignore
        self.sys_params = {}  # type: ignore
        self.connect_params = {}  # type: ignore
        self.rpa_dict = {}  # type: ignore

        self.log_level = getattr(logging, 'INFO')
        self.phy_log = '0xFF'

        self.ds_file_name = ''
        self.ds_file_txt = ''
        self.phy_json_name = ''
        self.log_file = ''  # PHY log file
        self.app_log_file = ''  # application log file
        self.vref_info_file = ''
        self.figure_file = ''
        self.sm_file = ''

        self.pmic_opt = Const.PMIC_INIT_UNKNOWN
        self.apply_pmic = True  # it will reflect 'Initialize PMIC' check; for Config Tools it will always be True

        self.ctrl_id = 1
        self.mem_type = 'ddr4'  # default memory type ddr4
        self.dram_type = 0  # dram type; default is ddr4
        self.dimm_type = 4  # dimm type nodimm
        self.lp_mode = 0  # lp mode; if set to 1 indicates lpddr4x/5x memory is used depending on the dram_type
        self.num_pstates = 0
        self.freq = []  # type: ignore
        self.data_width = 0
        self.ssc = 0

        self.rpa_version = 'unknown'  # default rpa version

        self.diags_params = {}  # type: ignore
        self.target_params = {}  # type: ignore
        self.uart_iomux_config = []  # type: ignore
        self.pmic_iomux_config = []  # type: ignore
        self.pmic_cmds = []  # type: ignore
        self.generic_iomux_config = []  # type: ignore
        self.ddrc_config_full = []  # type: ignore
        self.ddrc_registers = []  # type: ignore
        self.ddrc_timings = {}  # type: ignore
        self.dq_mapping = []  # type: ignore
        self.message_block_1d = []  # type: ignore
        self.message_block_tmg_1d = []  # type: ignore
        self.message_block_2d = ''  # type: ignore
        self.message_block_tmg_2d = ''  # type: ignore
        self.phy_full_config = {}  # type: ignore

        # Retention registers (PHY output)
        self.retention_registers = []  # type: ignore

        # Quick mode data (registers are received with firmware)
        self.quick_boot_registers = []  # type: ignore
        self.quick_boot_data = []  # type: ignore
        self.quick_boot_msgblk = {}  # type: ignore
        self.quick_boot_acsm = []  # type: ignore

        # Only used for DDR Tool Expert GUI for now, it loads data
        # from memtool_data configuration data files.
        self.loaded_data = []  # type: ignore

        # Erratas cache per processor; errata is loaded and cached first time when it is requested
        self.erratas = {}  # type: ignore

        # Hashes with registers' names per firmware loaded from registers' names hash files.
        self.regs_name_hashes = {}  # type: ignore

        # ECC configuration; needed for generating the ddrc_inline_ecc_scrub() calls in timing.c file
        self.inline_ecc_config = []  # type: ignore

        self.show_ca_pretrained_data = False

        self.data_reset(params)

    def data_reset(self, params: Dict[str, dict]):  # type: ignore
        """Reset config and update params.

        @param params: params to be updated
        """
        if params is not None:
            self.soc_name = params[Const.PARAM_S_TC][Const.PARAM_S_TC_SOC_NAME]
            if Const.PARAM_S_TC_FW in params[Const.PARAM_S_TC]:
                self.snps_phy_info = SnpsFirmware.from_id(
                    int(params[Const.PARAM_S_TC].get(Const.PARAM_S_TC_FW)))  # type: ignore
            self.phy_log = params[Const.PARAM_S_TC].get(Const.PARAM_S_TC_PHY_LOG, '0xFF')
            self.ctrl_id = int(params[Const.PARAM_S_BASIC].get('numberOfControllersEnabled', 1))
            self.skip_download = params[Const.PARAM_S_TC].get('skip_download', False)
            self.params = params.copy()
            self.params[Const.PARAM_S_TC][Const.PARAM_LOG_LEVEL] = self.log_level
            self.connect_params = self.params[Const.PARAM_S_TC]

            if Const.PARAM_S_TARGET_PARAMS in self.params:
                self.target_params = self.params[Const.PARAM_S_TARGET_PARAMS]
            else:
                # For Expert Mode load from memtool_data configuration data files.
                self.target_params = self.get_loaded_target_parameters(self.soc_name)

            if Const.PARAM_S_DCD_FW_PARAMS in self.params:
                self.sys_params = self.params[Const.PARAM_S_DCD_FW_PARAMS]
            else:
                # For Expert Mode load from memtool_data configuration data files.
                self.sys_params = self.get_loaded_sys_parameters(self.soc_name)

            if Const.PARAM_S_DCD_DIAG_PARAMS in self.params:
                self.diags_params = self.params[Const.PARAM_S_DCD_DIAG_PARAMS]
            else:
                # For Expert Mode load from memtool_data configuration data files.
                self.diags_params = self.get_loaded_diag_test_parameters(self.soc_name)

            if Const.PARAM_S_SYS_TRAIN_2D in self.sys_params:
                self.train_2d = self.sys_params[Const.PARAM_S_SYS_TRAIN_2D]

            # To investigated if is really needed: for Config Tools 'function' is being set in .js file
            # and for Expert Mode 'function' is being set by test in update_config_params method.
            # self.update_sys_params(Const.PARAM_S_SYS_FUNCTION, f'{self.op_type}')

            if Const.PARAM_S_BOARD_CONFIG in params:
                if Const.PARAM_S_BOARD_CONFIG_PMIC in params[Const.PARAM_S_BOARD_CONFIG]:
                    self.pmic_opt = int(params[Const.PARAM_S_BOARD_CONFIG][Const.PARAM_S_BOARD_CONFIG_PMIC].get(
                        Const.PARAM_S_BOARD_CONFIG_PMIC_OPTIONS, str(Const.PMIC_INIT_UNKNOWN)))
                    self.update_sys_params(Const.PARAM_S_SYS_PMIC_OPT, f'{self.pmic_opt}')

            if Const.PARAM_S_BASIC in params:
                if Const.PARAM_S_BOARD_CONFIG_DATA_RATE in params[Const.PARAM_S_BASIC]:
                    self.update_sys_params(Const.PARAM_S_SYS_FREQ_0,
                        params[Const.PARAM_S_BASIC][Const.PARAM_S_BOARD_CONFIG_DATA_RATE])
                if Const.PARAM_S_BOARD_CONFIG_FREQ_SETPOINT_1 in params[Const.PARAM_S_BASIC]:
                    self.update_sys_params(Const.PARAM_S_SYS_FREQ_1,
                        params[Const.PARAM_S_BASIC][Const.PARAM_S_BOARD_CONFIG_FREQ_SETPOINT_1])
                if Const.PARAM_S_BOARD_CONFIG_FREQ_SETPOINT_2 in params[Const.PARAM_S_BASIC]:
                    self.update_sys_params(Const.PARAM_S_SYS_FREQ_2,
                        params[Const.PARAM_S_BASIC][Const.PARAM_S_BOARD_CONFIG_FREQ_SETPOINT_2])
                if Const.PARAM_S_SS_ENABLE in params[Const.PARAM_S_BASIC]:
                    self.update_sys_params(Const.PARAM_S_SYS_SS_ENABLE, '0'
                        if params[Const.PARAM_S_BASIC][Const.PARAM_S_SS_ENABLE] == 'Disable' else '1')
                if Const.PARAM_S_SS_PERCENTAGE in params[Const.PARAM_S_BASIC]:
                    self.update_sys_params(Const.PARAM_S_SYS_SS_PERCENTAGE,
                        params[Const.PARAM_S_BASIC][Const.PARAM_S_SS_PERCENTAGE])
                if Const.PARAM_S_SS_MODULATION in params[Const.PARAM_S_BASIC]:
                    self.update_sys_params(Const.PARAM_S_SYS_SS_MODULATION,
                        params[Const.PARAM_S_BASIC][Const.PARAM_S_SS_MODULATION])

            phy_params_dram_type = None
            user_input_basic = None
            if Const.PARAM_S_PHY in params:  # phy may not be present during DDR Expert main window initialisation
                user_input_basic = params[Const.PARAM_S_PHY].get(Const.PARAM_S_PHY_INPUT_BASIC, None)
                if user_input_basic is not None:
                    phy_params_dram_type = user_input_basic.get('DramType', None)

            if Const.PARAM_S_BASIC_MEM_TYPE in params[Const.PARAM_S_BASIC]:
                mem_type = params[Const.PARAM_S_BASIC][Const.PARAM_S_BASIC_MEM_TYPE]
            else:
                # On import .ds from ConfigTool, we read mem_type from phy.json
                if phy_params_dram_type is not None:
                    mem_type = phy_params_dram_type
                    if mem_type == '2' and user_input_basic is not None:
                        lpddr4Mode = user_input_basic.get('Lp4xMode', '0')
                        if lpddr4Mode == '1':
                            mem_type = '3'
                else:
                    mem_type = '0'
                    self.logger.error('Memory type is UNKNOWN!')

            if str.isdigit(mem_type):
                self.mem_type = ConfigData.MEMORY_TYPES[int(mem_type)]
            else:
                self.mem_type = mem_type.lower()

            # check if dram type in userInputBasic corresponds to mem type in deviceInformation
            if phy_params_dram_type is not None and int(phy_params_dram_type) != self.dram_type:
                self.logger.error('Inconsistent dram type and memory type!')

            self.dimm_type = int(params[Const.PARAM_S_BASIC].get(Const.PARAM_S_BASIC_DIMM_TYPE, '4'))
            self.num_pstates = int(params[Const.PARAM_S_BASIC].get(Const.PARAM_S_BASIC_NUM_PSTATES, '1'))
            self.update_sys_params(Const.PARAM_S_SYS_NUM_STATES, f'{self.num_pstates}')

            freq1_set_point_str = 'freqSetPointLP4' if self.mem_type in ('lpddr4', 'lpddr4x') else 'freqSetPoint'
            freq2_set_point_str = params[Const.PARAM_S_BASIC].get('freq2SetPoint', '0')
            if freq2_set_point_str == 'None':
                freq2_set_point_str = '0'
            self.freq = [int(params[Const.PARAM_S_BASIC].get('clockFreqMHz', '0')) * 2,
                         int(params[Const.PARAM_S_BASIC].get(freq1_set_point_str, '0')) * 2,
                         int(freq2_set_point_str) * 2, 0]

            if Const.PARAM_S_CA_CONFIG in self.params:
                for ca_cfg in self.params[Const.PARAM_S_CA_CONFIG]:
                    if ca_cfg in self.params[Const.PARAM_S_PHY]["messageBlock[0]"]:
                        self.params[Const.PARAM_S_PHY]["messageBlock[0]"][ca_cfg] = \
                            self.params[Const.PARAM_S_CA_CONFIG][ca_cfg]

        self.data_width = 0
        self.fw_bin_info = {}
        self.misc_sys_params = {}

        self.uart_iomux_config = []
        self.pmic_iomux_config = []
        self.pmic_cmds = []
        self.generic_iomux_config = []
        self.ddrc_config_full = []
        self.ddrc_registers = []
        self.ddrc_timings = {}
        self.dq_mapping = []
        self.phy_full_config = {}
        self.message_block_1d = []
        self.message_block_tmg_1d = []
        self.message_block_2d = ''
        self.message_block_tmg_2d = ''

        # make sure data_reset is called only when is necessary, otherwise ds data is lost!
        self.ds_file_name = ''
        self.ds_file_txt = ''

        self.phy_json_name = ''

        # reset ECC config data
        self.inline_ecc_config = []

    def clear_phy_config_data(self):  # type: ignore
        """Clear config data."""
        # Clear PHY dictionaries to trigger running PHY driver.
        if (self.params is not None) and (Const.PARAM_S_PHY in self.params):
            self.params.pop(Const.PARAM_S_PHY)
        if (self.params is not None) and (Const.PARAM_S_PHY_INIT in self.params):
            self.params.pop(Const.PARAM_S_PHY_INIT)
        self.phy_full_config = {}
        # Clear dictionary holding absolute paths towards firmware binaries.
        # TODO: refactor to eliminate caching absolute paths into config data.
        self.fw_bin_info = {}

    @property
    def data_dir(self):  # type: ignore
        """Getter for data dir name."""
        return self.__data_dir

    @data_dir.setter
    def data_dir(self, value):  # type: ignore
        """Setter for data dir name."""
        self.__data_dir = value

        # load supported devices
        self.__load_supported_devices(self.__data_dir)

    def __load_supported_devices(self, data_dir_path: str):  # type: ignore
        """Load devices.

        @param data_dir_path: path to data dir
        """
        if data_dir_path is None:
            return

        device_dir_path = os.path.join(data_dir_path, DeviceInfo.DIR_NAME)
        if not os.path.isdir(device_dir_path):
            logging.getLogger(__name__).info(f"Device data folder {device_dir_path} does not exist.")
            self.__devices: List[str] = []
            return

        tool_supported_devices = []
        devices = os.listdir(device_dir_path)
        for device in devices:
            device_path = os.path.join(device_dir_path, device)
            if os.path.isdir(device_path):
                tool_supported_devices.append(device)
                self.DEVICES_INFO[device] = DeviceInfo(device, device_path)
            else:
                self.logger.warning(f"Device data folder contains invalid data file {device_path}; "
                                    f"it must contain only folders with processor data.")
        self.supported_devices = tool_supported_devices

    @property
    def supported_devices(self):  # type: ignore
        """Getter for supported devices."""
        return self.__supported_devices

    @supported_devices.setter
    def supported_devices(self, value):  # type: ignore
        """Setter for supported devices."""
        self.__supported_devices = value

    @property
    def soc_name(self):  # type: ignore
        """Getter for socket name."""
        return self.__soc_name

    @soc_name.setter
    def soc_name(self, value):  # type: ignore
        """Setter for socket name."""
        self.__soc_name = value

    @property
    def use_default_rpa_config(self) -> bool:
        """Getter for use RPA default config."""
        return self.__use_default_rpa_config

    @use_default_rpa_config.setter
    def use_default_rpa_config(self, use_default_rpa: bool):  # type: ignore
        """Setter for use RPA default config."""
        if self.get_target_pkl_file(self.soc_name,
                self.mem_type):  # default config can be used only if RPA is available
            self.__use_default_rpa_config = use_default_rpa
        else:
            self.__use_default_rpa_config = False

    @property
    def skip_download(self):  # type: ignore
        """Getter for skip_download."""
        return self.__skip_download

    @skip_download.setter
    def skip_download(self, value):  # type: ignore
        """Setter for skip_download."""
        self.__skip_download = value

    @property
    def mem_type(self):  # type: ignore
        """Getter for memory type."""
        return self.__mem_type

    @mem_type.setter
    def mem_type(self, mem_type):  # type: ignore
        """Setter for memory type."""
        self.__mem_type = mem_type
        self.set_ddr_type_and_lp_mode()
        # TODO: 'dram_type' in sys params is in fact 'mem_type'; change the sys parameter key!
        self.update_sys_params('dram_type', f'{ConfigData.get_memory_id(self.mem_type)}')

    @property
    def snps_phy_info(self):  # type: ignore
        """Getter for firmware version."""
        return self.__snps_phy_info

    @snps_phy_info.setter
    def snps_phy_info(self, snps_phy_info):  # type: ignore
        """Setter for firmware version."""
        self.__snps_phy_info = snps_phy_info

    @property
    def fw_bin_info(self):  # type: ignore
        """Getter for temp dir for generated files."""
        return self.__fw_bin_info

    @fw_bin_info.setter
    def fw_bin_info(self, dictionary):  # type: ignore
        """Setter for temp dir for generated files."""
        self.__fw_bin_info = dictionary

    @property
    def ds_file_txt(self) -> str:
        """Getter for ds file content."""
        return self.__ds_file_txt

    @ds_file_txt.setter
    def ds_file_txt(self, content: str):  # type: ignore
        """Setter for ds file content and its validity status.

        @param content: ds content
        """
        if self.__ds_file_txt == content:
            return

        self.__ds_file_txt = content
        self.__ds_is_valid = check_ds_validity(self.__ds_file_txt)

    @property
    def ds_is_valid(self) -> bool:
        """Getter for ds validity status."""
        return self.__ds_is_valid

    @property
    def train_2d(self) -> bool:
        """Getter for train 2D."""
        if self.__train_2d == 0:
            return False
        return True

    @train_2d.setter
    def train_2d(self, train: str | int | bool) -> None:
        """Setter for train 2D."""
        if isinstance(train, str):
            self.__train_2d = int(train)
        elif isinstance(train, int):
            self.__train_2d = train
        else:
            self.__train_2d = 0 if not train else 1
        self.update_sys_params(Const.PARAM_S_SYS_TRAIN_2D, str(self.__train_2d))
        self.update_phy_params(Const.PARAM_S_PHY_TRAIN_2D, str(self.__train_2d))

    def is_empty(self) -> bool:
        """Check if any params were set.

        @return: if params is empty
        """
        return self.params is None or len(self.params) == 0

    @classmethod
    def default(cls, data_dir_path=None, params=None, use_default_rpa=False):  # type: ignore
        """Instantiate config data with default config.

        @param data_dir_path: path to data dir
        @param params: params to be updated
        @param use_default_rpa: flag that signals usage of default RPA configuration
        """
        return cls(data_dir_path, params, use_default_rpa)

    @classmethod
    def update_detected_hids(cls, usb_devices: list) -> None:
        """Update detected HID devices."""
        cls.HIDS.clear()
        for usb_device_index, usb_device in enumerate(usb_devices):
            cls.HIDS[usb_device_index] = usb_device.device.path_str

    def set_memory_type(self):  # type: ignore
        """Compute and set memory type knowing ddr type and lp mode."""
        if self.lp_mode == 1:
            if self.dram_type == 2:
                self.mem_type = ConfigData.MEMORY_TYPES[3]
            elif self.dram_type == 4:
                self.mem_type = ConfigData.MEMORY_TYPES[5]
        else:
            self.mem_type = ConfigData.MEMORY_TYPES[self.dram_type]

    def set_ddr_type_and_lp_mode(self):  # type: ignore
        """Compute and set ddr type and lp mode knowing memory type."""
        if self.mem_type == ConfigData.MEMORY_TYPES[3]:
            self.dram_type = 2
            self.lp_mode = 1
        elif self.mem_type == ConfigData.MEMORY_TYPES[5]:
            self.dram_type = 4
            self.lp_mode = 1
        else:
            keys = [k for k, v in ConfigData.DRAM_TYPES.items() if v == self.mem_type]
            if keys:
                self.dram_type = keys[0]
            else:
                self.logger.error(f'Memory type {self.mem_type}'
                                  f' can not be converted to supported ddr type and lp mode!')
            self.lp_mode = 0

    def get_phy_dmem_addr(self):  # type: ignore
        """Get PHY DMEM base address."""
        if self.is_phy_v2(self.snps_phy_info):
            return Const.phy_v2_dmem_addr
        elif self.is_phy_v3(self.snps_phy_info):
            return Const.phy_v3_dmem_addr

        self.logger.error('Could not determine the base address for unsupported PHY version!')
        return -1

    def generate_firmware_dmem_binaries(self):  # type: ignore
        """Prepare 1D/2D firmware binaries."""
        quick_boot = (self.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        phy_init_options = Options.get_instance().get_snps_phy_init_options()
        if phy_init_options.skip_training() or quick_boot:
            return  # no training binaries to be considered

        dmem_info = {'1d': PhyPhase.LOAD_DMEM_1D.name + str(0)}
        if self.train_2d and phy_init_options.execute_full_training():
            dmem_info['2d'] = PhyPhase.LOAD_DMEM_2D.name

        for stage, msgs in dmem_info.items():
            binary = bytearray()

            # add dmem data from file
            dmem_file_key = 'dmem_fw_path_' + stage
            if dmem_file_key not in self.fw_bin_info:
                self.logger.error(f'Path to {dmem_file_key} could not be found!')
                return

            dmem_file_path = self.fw_bin_info.get(dmem_file_key)
            with open(dmem_file_path, 'rb') as dmem_file:
                binary.extend(bytearray(dmem_file.read()))

            # add dmem message block data
            phy_dmem_addr = self.get_phy_dmem_addr()
            if phy_dmem_addr < 0:
                return
            for addr, val in self.phy_full_config[msgs]:
                address = int(addr, 16)
                value = int(val, 16)
                offset = address - phy_dmem_addr
                binary[2 * offset: 2 * offset + 2] = bytes([value & 0xFF, (value >> 8) & 0xFF])

            # override dmem bin file with the complete data set
            with open(dmem_file_path, 'wb') as dmem_file:
                dmem_file.write(binary)

            self.sys_params["dmem_fw_size_" + stage] = os.path.getsize(dmem_file_path)

    def update_from_phy_full_config(self):  # type: ignore
        """Update PHY init params from phy full config."""
        if Const.PARAM_S_PHY_INIT in self.params:
            self.params.pop(Const.PARAM_S_PHY_INIT)
        self.params = merge_dict(self.params, {Const.PARAM_S_PHY_INIT: self.phy_full_config})

    @property
    def log_level(self):  # type: ignore
        """Getter for log level."""
        return self.__log_level

    @log_level.setter
    def log_level(self, log_level):  # type: ignore
        """Setter for log level."""
        self.__log_level = log_level
        self.connect_params[Const.PARAM_LOG_LEVEL] = log_level

    @property
    def dbi_enabled(self):  # type: ignore
        """Getter for DBI enabled status."""
        dbi_enable_str = 'disable'
        if Const.PARAM_S_BASIC in self.params:
            dbi_enable_str = self.params[Const.PARAM_S_BASIC].get(Const.PARAM_S_BASIC_ENABLE_DBI, 'disable')
        return dbi_enable_str.lower().startswith('enable')

    def update_sys_params(self, entry: str, value: str):  # type: ignore
        """It updates an entry from sys parameter block with given value.

        Entry must exist in sys parameter block because block must match
        precisely with PHY DDR algorithm, otherwise update is not performed
        and error/warning is being logged as a red flag.
        @param entry: Entry from sys parameter block to be updated.
        @param value: Value for entry to be updated.
        """
        if len(self.sys_params) > 0:
            if entry in self.sys_params:
                self.sys_params[entry] = value  # type: ignore
            else:
                # Sys parameter block must match precisely with PHY DDR algorithm.
                self.logger.warning(f'Can not update {entry} entry because it does not exist in sys parameter block!')

    def update_phy_params(self, entry: str, value: str):  # type: ignore
        """It updates an entry from phy parameter block with given value.

        @param entry: Entry from phy parameter block to be updated.
        @param value: Value for entry to be updated.
        """
        if self.params is None or len(self.params) == 0:
            self.logger.info('Parameter block is empty!')
        else:
            if Const.PARAM_S_PHY not in self.params:
                self.logger.info('phy section is missing from parameter block!')
            else:
                if Const.PARAM_S_PHY_INPUT_BASIC not in self.params[Const.PARAM_S_PHY]:
                    self.logger.info('userInputBasic section is missing from phy parameter block!')
                else:
                    if entry in self.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC]:
                        self.params[Const.PARAM_S_PHY][Const.PARAM_S_PHY_INPUT_BASIC][entry] = value

    def initialize_pmic_cmds(self, apply_pmic: bool):  # type: ignore
        """Store 'Initialize PMIC' button check state and trigger update of PMIC commands options parameter.

        This method is to be used only from UI

        @param apply_pmic: 'Initialize PMIC' button check state
        """
        self.apply_pmic = apply_pmic
        self.update_apply_pmic_policy()

    def update_apply_pmic_policy(self):  # type: ignore
        """TODO:summary line.

        Update PMIC commands options parameter based on 'Initialize PMIC' button state and PMIC commands
        availability.
        """
        if not self.apply_pmic:
            self.update_sys_params(Const.PARAM_S_SYS_PMIC_OPT, f'{Const.PMIC_INIT_DISABLED}')
        else:
            if self.pmic_opt == Const.PMIC_INIT_UNKNOWN:
                if self.pmic_cmds:
                    self.update_sys_params(Const.PARAM_S_SYS_PMIC_OPT, f'{Const.PMIC_INIT_CUSTOM}')
                else:
                    self.update_sys_params(Const.PARAM_S_SYS_PMIC_OPT, f'{Const.PMIC_INIT_DEFAULT}')

    def get_target_pkl_file(self, processor, memory):  # type: ignore
        """Get the .pkl file for current target.

        @param processor: target processor
        @param memory: target memory
        @return: path to .pkl if file exists or None if the .pkl doesn't exist
        """
        pkl_dir = os.path.join(self.data_dir, Const.PKL_DIR_NAME)
        pkl_file_name = f'{Const.PICKLE_ALIASES[processor].lower()}_{memory.lower()}_rpa'
        try:
            pkl_file = next(iter(filter(lambda x: ((Path(x).suffix in Const.PICKLE_EXTENSIONS)
                                                   and x.lower().startswith(pkl_file_name)),
                                 os.listdir(pkl_dir))))
        except Exception:
            self.logger.error(f".pkl file for {processor} {memory} doesn't exist!")
            return None

        return os.path.join(pkl_dir, pkl_file)

    def load_rpa_from_file(self):  # type: ignore
        """Load rpa from .ds file."""
        workspace_dir = Workspace.get_instance().get_location()
        ds_file_name = workspace_dir + os.path.sep + f"{self.mem_type}{Const.DS_FILE_SUFFIX}"
        if not os.path.isfile(ds_file_name):
            self.logger.error('File %s does not exist!!!', ds_file_name)
            return

        with open(ds_file_name, 'r', encoding='ascii', errors='ignore') as f:
            self.ds_file_txt = f.read()

    def load_rpa_mapping(self, _param, _json_dict, _rpa_dict):  # type: ignore
        """Load rpa mapping."""
        value = _json_dict[_param]
        if isinstance(value, dict):
            _rpa_dict[_param] = {}
            for param_child in value.keys():
                self.load_rpa_mapping(param_child, value, _rpa_dict[_param])
        else:
            if isinstance(value, str):  # e.g. ECC 'sheet' parameter
                _rpa_dict[_param] = value
            elif isinstance(value, list):
                if len(value) == 2:  # e.g. ECC 'ecc_region', 'mem_region' parameters
                    if isinstance(value[0], int):
                        _rpa_dict[_param] = (value[0], value[1])
                    else:
                        cell = value[0]
                        sheet = value[1]
                        _rpa_dict[_param] = AddressCell(cell, sheet=sheet)
                else:
                    self.logger.error('Error parsing mapping')

    def load_rpa_mappings(self):  # type: ignore
        """Load rpa mappings."""
        dictionaries_folder = os.path.join(self.data_dir, Const.MAPPING_DIR_NAME)
        rpa_mapping_name = f'{self.soc_name}_{self.mem_type}.json'.lower()
        rpa_mapping_file = os.path.join(dictionaries_folder, rpa_mapping_name)

        if not os.path.exists(rpa_mapping_file):
            raise Exception(f'RPA mappings file not found for {self.soc_name} {self.mem_type}')

        self.rpa_dict = {}
        json_dict = {}
        with open(rpa_mapping_file, 'r', encoding='utf-8') as rpa:
            try:
                json_dict = json.loads(rpa.read())
            except JSONDecodeError as e:
                self.logger.error('Error importing RPA dictionary: %s', str(e))

        for param in json_dict.keys():
            self.load_rpa_mapping(param, json_dict, self.rpa_dict)

    def load_from_data_dir(self):  # type: ignore
        """It loads config data from json configuration data files found in data directory.

        @note Only used by DDR Tool Expert GUI for now.
        """
        config_data_dir = os.path.join(self.data_dir, 'config_data')
        if not os.path.exists(config_data_dir):
            self.logger.error(f'Config data directory {config_data_dir} does not exist!')
            return

        for processor_name in self.supported_devices:
            # Load configuration data only for processors for which there is support.
            config_data_file_name = f'{processor_name}_CONFIG.json'
            config_data_file_path = os.path.join(config_data_dir, config_data_file_name)
            config_data_dic = {}
            if os.path.exists(config_data_file_path):
                with open(config_data_file_path, "rt", encoding="utf-8") as file:
                    try:
                        config_data_dic = json.load(file)
                    except JSONDecodeError as ex:
                        self.logger.error(f'Error while decoding {config_data_file_path} file: {str(ex)}')
            else:
                self.logger.error(f'Config data file {config_data_file_path} for {processor_name} does not exist!')
            # Load expert defined configuration data only for processors for which there is support.
            config_data_expert_file_name = f'{processor_name}_CONFIG_EXPERT.json'
            config_data_expert_file_path = os.path.join(config_data_dir, config_data_expert_file_name)
            config_data_expert_dic = {}
            # Expert defined configuration data is not mandatory.
            if os.path.exists(config_data_expert_file_path):
                with open(config_data_expert_file_path, "rt", encoding="utf-8") as file:
                    try:
                        config_data_expert_dic = json.load(file)
                    except JSONDecodeError as err:
                        self.logger.error(f'Error while decoding {config_data_expert_file_path} file! \n{str(err)}')
            # Merge configuration data with append option.
            config_data_merge_dic = merge_dict(config_data_dic, config_data_expert_dic, True)
            self.loaded_data.append(config_data_merge_dic)

    def get_loaded_processors(self) -> list:
        """It gets list of processors from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @return: List of processors from loaded configuration data.
        """
        processors = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                processors.append(proc_config_data_dic[JsonConfigField.PROCESSOR])
        return processors

    def get_loaded_firmware_versions(self, processor: str) -> list:
        """It gets list of firmware version for a specific processor  from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @return: List of memory types from loaded configuration data.
        """
        firmware_versions = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    firmware_versions = proc_config_data_dic[JsonConfigField.FIRMWARE_VERSIONS]
        return firmware_versions

    def get_loaded_memory_types(self, processor: str) -> list:
        """It gets list of memory types for a specific processor from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @return: List of memory types from loaded configuration data.
        """
        memory_types = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    memory_types = proc_config_data_dic[JsonConfigField.MEMORY_TYPES]
        return memory_types

    def get_loaded_target_parameters(self, processor: str) -> dict:
        """It gets target parameters for a specific processor from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @return: Target parameters for a specific processor from loaded configuration data.
        """
        target_params = {}
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    if JsonConfigField.TARGET_PARAMETERS in proc_config_data_dic:
                        # Provide deep copy to avoid change of actually loaded data.
                        target_params = deepcopy(proc_config_data_dic[JsonConfigField.TARGET_PARAMETERS])
        return target_params

    def get_loaded_sys_parameters(self, processor: str) -> dict:
        """It gets system parameters for DDR PHY algorithm for a specific processor from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @return: System parameters for DDR PHY algorithm for a specific processor from loaded configuration data.
        """
        sys_params = {}
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    if JsonConfigField.SYS_PARAMETERS in proc_config_data_dic:
                        # Provide deep copy to avoid change of actually loaded data.
                        sys_params = deepcopy(proc_config_data_dic[JsonConfigField.SYS_PARAMETERS])
        return sys_params

    def get_loaded_diag_test_parameters(self, processor: str) -> dict:
        """TODO:summary line.

        It gets diagnostics test parameters for DDR PHY algorithm for a specific processor from loaded
        configuration data.
        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @return: Diagnostics test parameters for DDR PHY algorithm for a specific processor from loaded configuration
        data.
        """
        diag_test_params = {}
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    if JsonConfigField.DIAG_TEST_PARAMETERS in proc_config_data_dic:
                        # Provide copy to avoid change of actually loaded data.
                        diag_test_params = proc_config_data_dic[JsonConfigField.DIAG_TEST_PARAMETERS].copy()
        return diag_test_params

    def get_loaded_phy_parameters(self, processor: str, memory_type: str) -> dict:
        """It gets phy parameters for a specific processor and memory type from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @param memory_type: Memory type.
        @return: Phy parameters for a specific processor and memory type from loaded configuration data.
        """
        phy_params = {}
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    if JsonConfigField.PHY_PARAMETERS in proc_config_data_dic:
                        for key in proc_config_data_dic[JsonConfigField.PHY_PARAMETERS]:
                            if key.lower() == memory_type.lower():
                                # Provide deepcopy to avoid change of actually loaded data
                                # because copied dictionary contains data references.
                                phy_params = deepcopy(proc_config_data_dic[JsonConfigField.PHY_PARAMETERS][key])
                                break
        return phy_params

    def get_loaded_tests_names(self, processor: str, memory_type: str) -> list:
        """It gets list of names of tests for a specific processor from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @param memory_type: Memory type.
        @return: List of names of tests from loaded configuration data.
        """
        tests = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    tests_dic_list = proc_config_data_dic[JsonConfigField.TESTS]
                    for test_dic in tests_dic_list:
                        if JsonConfigField.MEMORY_TYPES in test_dic:
                            test_mem_types = test_dic[JsonConfigField.MEMORY_TYPES]
                            test_mem_types_lower = list(test_mem_type.lower() for test_mem_type in test_mem_types)
                            if memory_type.lower() in test_mem_types_lower:
                                if JsonConfigField.TEST_NAME in test_dic:
                                    tests.append(test_dic[JsonConfigField.TEST_NAME])
        return tests

    def get_loaded_scenarios_names(self, processor: str, memory_type: str) -> list:
        """It gets list of names of scenarios for a specific processor and memory type from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @param memory_type: Memory type.
        @return: List of names of scenarios from loaded configuration data.
        """
        scenarios = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    if JsonConfigField.SCENARIOS in proc_config_data_dic:
                        scenarios_dic_list = proc_config_data_dic[JsonConfigField.SCENARIOS]
                        for scenario_dic in scenarios_dic_list:
                            if JsonConfigField.SCENARIO_MEMORY_TYPES in scenario_dic:
                                scenario_mem_types = scenario_dic[JsonConfigField.SCENARIO_MEMORY_TYPES]
                                scenario_mem_types_lower = list(
                                    scenario_mem_type.lower() for scenario_mem_type in scenario_mem_types)
                                if memory_type.lower() in scenario_mem_types_lower:
                                    if JsonConfigField.SCENARIO_NAME in scenario_dic:
                                        scenarios.append(scenario_dic[JsonConfigField.SCENARIO_NAME])
        return scenarios

    class TestParameter:
        """TODO:summary line.

        Wrapper for test parameter data loaded from json configuration files
        to ease test parameter data consumption after being loaded.
        """

        def __init__(self, _id=None, _name=None, _default_value=None, _options=None):  # type: ignore
            """TODO:summary line."""
            self.param_id = _id
            self.name = _name
            self.default_value = _default_value
            self.options = _options

    class ScenarioParameter:
        """TODO:summary line.

        Wrapper for scenario parameter data loaded from json configuration files
        to ease scenario parameter data consumption after being loaded.
        """

        def __init__(self, _id: str, name: Optional[str] = None,  # type: ignore
            default_values: Optional[dict[str, str]] = None, options: Optional[dict[str, str]] = None):  # type: ignore
            """TODO:summary line."""
            self.param_id = _id
            self.name = name
            self.default_values = default_values
            self.options = options

    def get_loaded_test_parameters(self, processor: str, test: str) -> list[TestParameter]:  # type: ignore
        """It gets list of parameters of a test for a specific processor from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @param test: Name of test.
        @return: List of parameters of test as TestParameter objects.
        """
        parameters = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    tests_dic_list = proc_config_data_dic[JsonConfigField.TESTS]
                    for test_dic in tests_dic_list:
                        if test_dic[JsonConfigField.TEST_NAME] == test:
                            if JsonConfigField.TEST_PARAMETERS in test_dic:
                                test_parameters = test_dic[JsonConfigField.TEST_PARAMETERS]
                                for parameter in test_parameters:
                                    parameter_id = ''
                                    parameter_name = ''
                                    parameter_default_value = ''
                                    parameter_options = []
                                    if JsonConfigField.TEST_PARAM_ID in parameter:
                                        parameter_id = parameter[JsonConfigField.TEST_PARAM_ID]
                                    else:
                                        self.logger.warning(f'Parameter from {test} has no id!')
                                    if JsonConfigField.TEST_PARAM_NAME in parameter:
                                        parameter_name = parameter[JsonConfigField.TEST_PARAM_NAME]
                                    else:
                                        self.logger.error(f'Parameter from {test} has no name!')
                                    if JsonConfigField.TEST_PARAM_DEFAULT_VAL in parameter:
                                        parameter_default_value = parameter[JsonConfigField.TEST_PARAM_DEFAULT_VAL]
                                        # Only if parameter is 'True' or 'False' evaluate to boolean.
                                        if parameter_default_value in ('True', 'False'):
                                            parameter_default_value = ast.literal_eval(parameter_default_value)
                                    else:
                                        self.logger.error(f'Parameter from {test} has no default-value value!')
                                    if JsonConfigField.TEST_PARAM_OPTIONS in parameter:
                                        parameter_options = parameter[JsonConfigField.TEST_PARAM_OPTIONS]
                                    parameters.append(
                                        ConfigData.TestParameter(parameter_id, parameter_name, parameter_default_value,
                                                                 parameter_options))

        return parameters

    def get_loaded_scenario_parameters(self, processor: str, memory_type: str, scenario: str) -> list[
        ScenarioParameter]:
        """It gets list of parameters of a scenario for a specific processor from loaded configuration data.

        Loaded configuration data is a list of dictionaries,
        each dictionary contains configuration data for a specific processor.
        @param processor: Name of processor.
        @param memory_type: Memory type.
        @param scenario: Name of scenario.
        @return: List of parameters of test as ScenarioParameter objects.
        """
        parameters = []
        for proc_config_data_dic in self.loaded_data:
            if JsonConfigField.PROCESSOR in proc_config_data_dic:
                if proc_config_data_dic[JsonConfigField.PROCESSOR] == processor:
                    if JsonConfigField.SCENARIOS in proc_config_data_dic:
                        scenarios_dic_list = proc_config_data_dic[JsonConfigField.SCENARIOS]
                        for scenario_dic in scenarios_dic_list:
                            if JsonConfigField.SCENARIO_NAME in scenario_dic:
                                if scenario_dic[JsonConfigField.SCENARIO_NAME] == scenario:
                                    if JsonConfigField.SCENARIO_MEMORY_TYPES in scenario_dic:
                                        scenario_mem_types = scenario_dic[JsonConfigField.SCENARIO_MEMORY_TYPES]
                                        scenario_mem_types_lower = list(
                                            scenario_mem_type.lower() for scenario_mem_type in scenario_mem_types)
                                        if memory_type.lower() in scenario_mem_types_lower:
                                            if JsonConfigField.SCENARIO_PARAMETERS in scenario_dic:
                                                scenario_parameters = scenario_dic[JsonConfigField.SCENARIO_PARAMETERS]
                                                for parameter in scenario_parameters:
                                                    param_name = ''
                                                    param_id = ''
                                                    param_default_vals = {}
                                                    param_options = {}
                                                    if JsonConfigField.SCENARIO_PARAMETER_NAME in parameter:
                                                        param_name = parameter[JsonConfigField.SCENARIO_PARAMETER_NAME]
                                                    else:
                                                        self.logger.error(f'Parameter from {scenario} has no name!')
                                                    if JsonConfigField.SCENARIO_PARAMETER_ID in parameter:
                                                        param_id = parameter[JsonConfigField.SCENARIO_PARAMETER_ID]
                                                    else:
                                                        self.logger.error(f'Parameter from {scenario} has no id!')
                                                    if JsonConfigField.SCENARIO_PARAMETER_DEFAULT_VALUES in parameter:
                                                        param_default_vals = parameter[
                                                            JsonConfigField.SCENARIO_PARAMETER_DEFAULT_VALUES]
                                                    if JsonConfigField.SCENARIO_PARAMETER_OPTIONS in parameter:
                                                        param_options = parameter[
                                                            JsonConfigField.SCENARIO_PARAMETER_OPTIONS]
                                                    parameters.append(ConfigData.ScenarioParameter(param_id, param_name,
                                                        param_default_vals, param_options))

        return parameters

    def get_phy_init_reg_names_hash(self) -> dict[str, str]:
        """TODO:summary line.

        It loads PHY init registers' names dictionary from registers' names hash file
        for current firmware version of config data.
        @return: Dictionary of PHY init registers' names.
        @note Only used by DDR Tool Expert GUI for now.
        """
        reg_names_hash = {}
        if self.snps_phy_info.name in self.regs_name_hashes:
            reg_names_hash = self.regs_name_hashes[self.snps_phy_info.name]
        else:
            reg_names_hash_file = os.path.join(self.data_dir,
                f'{Const.REGS_HASH_DIR_NAME}/reg_names_{self.snps_phy_info.name}.hash')
            if not os.path.exists(reg_names_hash_file):
                self.logger.error(f'Phy init registers names hash file {reg_names_hash_file} does not exist!')
            else:
                REG_TUPLE_LEN = 2
                with open(reg_names_hash_file, "rt", encoding="utf-8") as file:
                    line = file.readline().rstrip()  # Remove EOL.
                    while line:
                        reg_tuple = tuple(line.split())
                        if len(reg_tuple) == REG_TUPLE_LEN:
                            reg_addr, reg_name = reg_tuple
                            # Eliminate hexa 0 padding and use lower case for registers' addresses.
                            reg_addr = re.sub(r'0x0+', '0x', reg_addr.lower())
                            reg_names_hash[reg_addr] = reg_name
                        else:
                            self.logger.error(f'Invalid format of line \"{line}\" from'
                                              f' phy init registers names hash file {reg_names_hash_file}!')
                        line = file.readline().rstrip()  # Remove EOL.
                self.regs_name_hashes[self.snps_phy_info.name] = reg_names_hash
        return reg_names_hash

    # TODO: check if from_file should be implemented; called in finish_import from ImportFrame  # from_file(
    #  file_name, self.dev_type.get(), self.fw_version.get())
