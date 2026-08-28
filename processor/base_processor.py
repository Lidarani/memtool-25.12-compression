# Copyright 2019-2025 NXP
"""TODO:summary line."""
import json
import logging
import os
import shutil
import time
from enum import Enum
from typing import List, Tuple, Union

import yaml

from memtool.common.app import AppInterface, ApplicationType
from memtool.common.base_test import BaseTest, TestStatus
from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import get_dcd_command_str
from memtool.common.factories import ProcessorFactory
from memtool.common.options import Options
from memtool.common.workspace import Workspace
from memtool.memtests.snps_phy import SnpsPhy
from memtool.phyinit.out_parser import PhyInitParser
from memtool.phyinit.phy_init import PHYInitDriver
from memtool.processor.dcd_creator import DCDCreator
from memtool.processor.errata import Errata
from memtool.processor.import_ds_file import DSImporter
from memtool.utils.constants import Const


class BaseProcessor(ProcessorFactory, DCDCreator, DSImporter, Errata):
    """This class provides an implementation for target communication using SDP & UART."""

    logger = logging.getLogger(__name__)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Let the factory know that this class can handle the input so it should be instantiated.

        @return: can this class handle the input?
        """
        for arg in args:
            if isinstance(arg[0], str):
                return arg[0] == cls.__name__
        return False

    def __init__(self, name, dram_type):  # type: ignore
        """TODO:summary line."""
        super(BaseProcessor, self).__init__()

        self.processor_info = ConfigData.DEVICES_INFO[name] if name in ConfigData.DEVICES_INFO else None

        self.system_manager_on = self.processor_info.has_sm() if self.processor_info is not None else False
        self.name = name
        self.firmware_path = ''

        self.reg_calc = None
        self.reg_calc_map = {}

    def get_app_type(self) -> Enum:
        """Get processor application type.

        @return: processor application type
        """
        return ApplicationType.UNKNOWN

    def is_system_manager_on(self) -> bool:
        """Getter for whether processor is controlled by System Manager.

        @return: True if processor is controlled by System Manager, False otherwise
        """
        return self.system_manager_on

    def init_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Load xls data and mappings.

        @param config_data: processor config data
        """
        config_data.load_rpa_mappings()

    @staticmethod
    def add_command(cmd) -> str:  # type: ignore
        """Format command as str.

        @param cmd: command
        @return: command as str
        """
        command_id = cmd.get(Const.PARAM_S_BOARD_CONFIG_CMD)
        address = cmd.get(Const.PARAM_S_BOARD_CONFIG_ADR)
        size = cmd.get(Const.PARAM_S_BOARD_CONFIG_SZE)
        value = cmd.get(Const.PARAM_S_BOARD_CONFIG_VAL)
        return f'{get_dcd_command_str(int(command_id))}\t{address}\t{size}\t{value}\n'

    def insert_after_rpa(self, config_data: ConfigData):  # type: ignore
        """Override insert_after_rpa from ErrataAPI.

        @param config_data: processor config data
        """
        if Const.PARAM_S_BOARD_CONFIG in config_data.params:
            uart_iomux_cmd_list = config_data.params[Const.PARAM_S_BOARD_CONFIG].\
                                            get(Const.PARAM_S_BOARD_CONFIG_UART_IOMUX, [])
            if len(uart_iomux_cmd_list) > 0:
                config_data.ds_file_txt += f'\n{Const.PARAM_S_BOARD_CONFIG_UART_IOMUX_SECTION}\n'
                for cmd in uart_iomux_cmd_list:
                    config_data.ds_file_txt += self.add_command(cmd)

            if Const.PARAM_S_BOARD_CONFIG_PMIC in config_data.params[Const.PARAM_S_BOARD_CONFIG]:
                pmic_iomux_cmd_list = config_data.params[Const.PARAM_S_BOARD_CONFIG].\
                                            get(Const.PARAM_S_BOARD_CONFIG_PMIC).\
                                            get(Const.PARAM_S_BOARD_CONFIG_PMIC_IOMUX, [])
                if len(pmic_iomux_cmd_list) > 0:
                    config_data.ds_file_txt += f'\n{Const.PARAM_S_BOARD_CONFIG_PMIC_IOMUX_SECTION}\n'
                    for cmd in pmic_iomux_cmd_list:
                        config_data.ds_file_txt += self.add_command(cmd)

                pmic_cmd_list = config_data.params[Const.PARAM_S_BOARD_CONFIG][Const.PARAM_S_BOARD_CONFIG_PMIC].\
                                                get(Const.PARAM_S_BOARD_CONFIG_PMIC_COMMANDS, [])
                if len(pmic_cmd_list) > 0:
                    config_data.ds_file_txt += f'\n{Const.PARAM_S_BOARD_CONFIG_PMIC_COMMANDS_SECTION}\n'
                    for cmd in pmic_cmd_list:
                        if cmd:
                            command_id = int(cmd.get(Const.PARAM_S_BOARD_CONFIG_CMD))
                            value = cmd.get(Const.PARAM_S_BOARD_CONFIG_VAL)
                            config_data.ds_file_txt += f'sysparam set {"pmic_set" if command_id == 0 else "pmic_cfg"} '\
                                                       f'{value}\n'

            generic_iomux_cmd_list = config_data.params[Const.PARAM_S_BOARD_CONFIG].\
                                                    get(Const.PARAM_S_BOARD_CONFIG_GENERIC_IOMUX, [])
            if len(generic_iomux_cmd_list) > 0:
                config_data.ds_file_txt += f'\n{Const.PARAM_S_BOARD_CONFIG_GENERIC_IOMUX_SECTION}\n'
                for cmd in generic_iomux_cmd_list:
                    config_data.ds_file_txt += self.add_command(cmd)

        ddrc_custom_cmd_list = config_data.params.get(Const.PARAM_S_DDRC_CUSTOM_CONFIG, [])
        if len(ddrc_custom_cmd_list) > 0:
            config_data.ds_file_txt += f'\n{Const.PARAM_S_DDRC_CUSTOM_CONFIG_SECTION}\n'
            for cmd in ddrc_custom_cmd_list:
                config_data.ds_file_txt += self.add_command(cmd)

    def get_ecc_scrub_regions(self, config_data: ConfigData) -> \
            Union[None, Tuple[List[Tuple[str, str]], Tuple[str, str]]]:
        """Get ECC scrub regions.

        @param config_data: processor config data
        """
        return None

    def ddrc_reg_calc(self, config_data: ConfigData):  # type: ignore
        """Update config, create DS file contents and insert errata.

        @param config_data: processor config data
        """
        start = time.time()
        self.reg_calc.update_config(config_data, self.reg_calc_map)

        end = time.time()
        self.logger.info("Config time %f", end - start)

        config_data.ds_file_txt = self.reg_calc.get_ds_file()
        self.insert_after_rpa(config_data)

        end = time.time()
        self.logger.info("DS file time %f", end - start)

        # extract ECC regions info
        self.reg_calc.collect_ecc_info(config_data, self.reg_calc_map)

    def __int_val_to_bytes(self, int_val: int, byte_idx: int = -1) -> Union[None, bytes]:
        """Get byte array that corresponds to the given short int value.

        @param int_val: int value to be converted to byte array
        @param byte_idx: index of the byte; if index is -1 both bytes will be returned
        @return: array of requested bytes, or None if invalid parameters were received
        """
        if byte_idx > 1:
            return None

        if byte_idx < 0:
            return bytes([int_val & 0xFF, (int_val >> 8) & 0xFF])
        else:
            return bytes([int_val & 0xFF]) if byte_idx == 0 else bytes([(int_val >> 8) & 0xFF])

    def get_updated_quick_boot_dmem_file(self, src_file: str, dst_file: str, config_data: ConfigData):  # type: ignore
        """Compute dmem file for quick boot.

        @param src_file: path to quick boot fw dmem file
        @param dst_file: path to quick boot dmem file used for initialization
        @param config_data: processor config data
        """
        data = bytearray()
        with open(src_file, 'rb') as f:
            data.extend(bytearray(f.read()))

        # apply message block updates
        phy_dmem_addr = config_data.get_phy_dmem_addr()
        if phy_dmem_addr < 0:
            return
        for k, v in config_data.message_block_1d[0]:
            addr = int(k, 16)
            val = int(v, 16)
            offset = addr - phy_dmem_addr
            bytes_val = self.__int_val_to_bytes(val)
            if bytes_val is None:
                self.logger.error("QuickBoot message block updates could not be applied!")
                return
            data[2 * offset: 2 * offset + 2] = bytes_val

        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            # adjust MR14
            PhyV2QuickBootMsgMR14 = {
                (0x54026, 1): 0x39,  # MR14_A0
                (0x54027, 0): 0x45,  # MR14_A1
                (0x54040, 0): 0x6c,  # MR14_B0
                (0x54040, 1): 0x78   # MR14_B1
            }
            for (src_addr, src_byte), dst in PhyV2QuickBootMsgMR14.items():
                if src_addr not in config_data.quick_boot_msgblk:
                    continue
                src_val = config_data.quick_boot_msgblk[src_addr]
                bytes_val = self.__int_val_to_bytes(src_val, src_byte)
                if bytes_val is None:
                    self.logger.error("QuickBoot MR14 updates could not be applied!")
                    return
                data[dst: dst + 1] = bytes_val

        elif ConfigData.is_phy_v3(config_data.snps_phy_info):
            # adjust message block
            PhyV3QuickBootMsgBlk1 = {
                (0x58019, 1): 0x6e,  # TrainedVREFCA_A0 -> MR12_A0
                (0x5801a, 0): 0x6f,  # TrainedVREFCA_A1 -> MR12_A1
                (0x58027, 0): 0x70,  # TrainedVREFCA_B0 -> MR12_B0
                (0x58027, 1): 0x71,  # TrainedVREFCA_B1 -> MR12_B1
                (0x5801a, 1): 0x76,  # TrainedVREFDQ_A0 -> MR14_A0
                (0x5801b, 0): 0x77,  # TrainedVREFDQ_A1 -> MR14_A1
                (0x58028, 0): 0x78,  # TrainedVREFDQ_B0 -> MR14_B0
                (0x58028, 1): 0x79,  # TrainedVREFDQ_B1 -> MR14_B1
                (0x58068, 0): 0x7a,  # TrainedVREFDQU_A0 -> MR15_A0
                (0x5806a, 1): 0x7b,  # TrainedVREFDQU_A1 -> MR15_A1
                (0x5806d, 0): 0x7c,  # TrainedVREFDQU_B0 -> MR15_B0
                (0x5806f, 1): 0x7d,  # TrainedVREFDQU_B1 -> MR15_B1
                (0x58068, 1): 0x9a,  # TrainedDRAMDFE_A0 -> MR24_A0
                (0x5806b, 0): 0x9b,  # TrainedDRAMDFE_A1 -> MR24_A1
                (0x5806d, 1): 0x9c,  # TrainedDRAMDFE_B0 -> MR24_B0
                (0x58070, 0): 0x9d,  # TrainedDRAMDFE_B1 -> MR24_B1
                (0x58069, 0): 0xae,  # TrainedDRAMDCA_A0 -> MR30_A0
                (0x5806b, 1): 0xaf,  # TrainedDRAMDCA_A1 -> MR30_A1
                (0x5806e, 0): 0xb0,  # TrainedDRAMDCA_B0 -> MR30_B0
                (0x58070, 1): 0xb1   # TrainedDRAMDCA_B1 -> MR30_B1
            }
            # for src, dst in PhyV3QuickBootMsgBlk1.items():
            for (src_addr, src_byte), dst in PhyV3QuickBootMsgBlk1.items():
                if src_addr not in config_data.quick_boot_msgblk:
                    continue
                src_val = config_data.quick_boot_msgblk[src_addr]
                bytes_val = self.__int_val_to_bytes(src_val, src_byte)
                if bytes_val is None:
                    self.logger.error("QuickBoot MR updates could not be applied!")
                    return
                data[dst: dst + 1] = bytes_val

            PhyV3QuickBootMsgBlk2 = {
                0x58098: 0x130,  # QBPllUPllProg0
                0x58099: 0x132,  # QBPllUPllProg1
                0x5809a: 0x134,  # QBPllUPllProg2
                0x5809b: 0x136,  # QBPllUPllProg3
                0x5809c: 0x138,  # QBPllCtrl1
                0x5809d: 0x13a,  # QBPllCtrl4
                0x5809e: 0x13c  # QBPllCtrl5
            }
            for src_addr, dst in PhyV3QuickBootMsgBlk2.items():
                if src_addr not in config_data.quick_boot_msgblk:
                    continue
                src_val = config_data.quick_boot_msgblk[src_addr]
                bytes_val = self.__int_val_to_bytes(src_val)
                if bytes_val is None:
                    self.logger.error("QuickBoot PLL updates could not be applied!")
                    return
                data[dst: dst + 2] = bytes_val

            csr_offset = Const.phy_v3_csr_offset
            for _, str_value in config_data.quick_boot_data:
                int_value = int(str_value, 16)
                bytes_val = self.__int_val_to_bytes(int_value)
                if bytes_val is None:
                    self.logger.error("QuickBoot CSR updates could not be applied!")
                    return
                data[csr_offset: csr_offset + 2] = bytes_val
                csr_offset += 2

        # update SequenceCtrl
        SequenceCtrlOffset = 0x10
        data[SequenceCtrlOffset: SequenceCtrlOffset + 2] = bytes([0x01, 0x00])

        # update QuickBoot
        QuickBoot = 0x19
        data[QuickBoot: QuickBoot + 1] = bytes([0x01])

        with open(dst_file, 'wb') as f:
            f.write(data)

    def init_bin_info(self, config_data: ConfigData):  # type: ignore
        """Load file paths sizes and addresses in config_data.

        @param config_data: processor config data
        """
        fw_bin_info = {}
        config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = 0
        config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = 0
        config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = 0
        config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = 0
        workspace_dir = Workspace.get_instance().get_location()
        quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        if quick_boot:
            fw_data_dir = os.path.join(config_data.data_dir, 'firmware',
                                       config_data.snps_phy_info.name, f'{config_data.mem_type}_quickboot')
            imem_file_name = SnpsPhy.get_data_file(mem_type=config_data.mem_type, op_type="quickboot", data_type="imem")
            tmp_imem_file = os.path.join(workspace_dir, imem_file_name)
            if not os.path.exists(tmp_imem_file):  # AHAB needs imem file in workspace
                shutil.copy(os.path.join(fw_data_dir, imem_file_name), tmp_imem_file)
            fw_bin_info[Const.FW_IMEM_1D_FILE_PATH] = tmp_imem_file
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = os.path.getsize(tmp_imem_file)

            dmem_file_name = SnpsPhy.get_data_file(mem_type=config_data.mem_type, op_type="quickboot", data_type="dmem")
            tmp_dmem_file = os.path.join(workspace_dir, dmem_file_name)
            if not os.path.exists(tmp_dmem_file):  # AHAB needs dmem file in workspace
                self.get_updated_quick_boot_dmem_file(
                        os.path.join(fw_data_dir, dmem_file_name), tmp_dmem_file, config_data)
            fw_bin_info[Const.FW_DMEM_1D_FILE_PATH] = tmp_dmem_file
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = os.path.getsize(tmp_dmem_file)
        else:
            phy_init_options = Options.get_instance().get_snps_phy_init_options()
            if not phy_init_options.skip_training():
                fw_bin_info[Const.FW_IMEM_1D_FILE_PATH] = os.path.normpath(
                        workspace_dir + os.path.sep + Const.imem_1d_bin)
                config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = os.path.getsize(
                    fw_bin_info[Const.FW_IMEM_1D_FILE_PATH])
                fw_bin_info[Const.FW_DMEM_1D_FILE_PATH] = os.path.normpath(workspace_dir
                                                                           + os.path.sep + Const.dmem_1d_bin[0])
                config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = os.path.getsize(
                    fw_bin_info[Const.FW_DMEM_1D_FILE_PATH])

                if config_data.train_2d and phy_init_options.execute_full_training():
                    fw_bin_info[Const.FW_IMEM_2D_FILE_PATH] = os.path.normpath(workspace_dir
                                                                               + os.path.sep + Const.imem_2d_bin)
                    if os.path.exists(fw_bin_info[Const.FW_IMEM_2D_FILE_PATH]):
                        config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = os.path.getsize(
                            fw_bin_info[Const.FW_IMEM_2D_FILE_PATH])
                    fw_bin_info[Const.FW_DMEM_2D_FILE_PATH] = os.path.normpath(workspace_dir
                                                                               + os.path.sep + Const.dmem_2d_bin)
                    if os.path.exists(fw_bin_info[Const.FW_DMEM_2D_FILE_PATH]):
                        config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = os.path.getsize(
                            fw_bin_info[Const.FW_DMEM_2D_FILE_PATH])

        config_data.fw_bin_info = fw_bin_info

    def get_test_bin_file_name(self, config_data: ConfigData) -> str:
        """Assemble path to DDR test bin file.

        @param config_data: processor config data
        @return: path to DDR test bin file
        """
        return self.find_test_bin_file(config_data, self.processor_info.get_bin_file_name())

    def get_test_second_bin_file_name(self, config_data: ConfigData) -> str:
        """Get second image in case of SM controlled processors.

        @param config_data: processor config data
        @return: path to bin file
        """
        return self.find_test_bin_file(config_data, self.processor_info.get_second_bin_file_name(),
                                       primary_image=False)

    def get_ahab_img_file_name(self, config_data: ConfigData) -> str:
        """Get path to processor ahab container image; applicable for SM controlled processors.

        @param config_data: processor config data
        @return: path to processor ahab container image
        """
        binaries_folder = os.path.join(config_data.data_dir, Const.BIN_DIR_NAME)
        return os.path.join(binaries_folder, self.name, self.processor_info.get_ahab_image_name()).replace('\\', '/')

    def get_sm_file_name(self, config_data: ConfigData) -> str:
        """Get path to processor SM image; applicable for SM controlled processors.

        @param config_data: processor config data
        @return: path to processor SM image
        """
        if config_data.sm_file:
            if not os.path.exists(config_data.sm_file):
                self.logger.warning(f"{config_data.sm_file} could not be found! "
                                    f"Default system manager will be used!")
            else:
                return config_data.sm_file  # if a custom SM binary was specified, then this binary should be used

        binaries_folder = os.path.join(config_data.data_dir, Const.BIN_DIR_NAME)
        return os.path.join(binaries_folder, self.name, self.processor_info.get_sm_image_name()).replace('\\', '/')

    def get_v2x_file_name(self, config_data: ConfigData) -> str:
        """Get path to processor V2X image; applicable for SM controlled processors.

        @param config_data: processor config data
        @return: path to processor V2X image
        """
        v2x_image_name = self.processor_info.get_v2x_image_name()
        if not v2x_image_name:
            return ''
        binaries_folder = os.path.join(config_data.data_dir, Const.BIN_DIR_NAME)
        return os.path.join(binaries_folder, self.name, v2x_image_name).replace('\\', '/')

    def find_test_bin_file(self, config_data: ConfigData, bin_name: str, primary_image: bool = True) -> str:
        """Find the right binaries for the processor.

        @param config_data: processor config data
        @param bin_name: binary file name
        @param primary_image: True if is primary image
        @return: path to bin file
        """
        binaries_folder = os.path.join(config_data.data_dir, Const.BIN_DIR_NAME)
        test_name = config_data.params[Const.PARAM_S_APP]['name'].lower()
        if (self.processor_info.has_sm() and primary_image) or test_name != 'memtester':
            return os.path.join(binaries_folder, bin_name).replace('\\', '/')

        memtester_bin = bin_name.replace('ddr_test_', 'ddr_test_memtester_')
        return os.path.join(binaries_folder, memtester_bin).replace('\\', '/')

    def collect_device_info(self, config_data: ConfigData):  # type: ignore
        """Collect device parameters default values.

        @param config_data: processor config data
        @return: dictionary with device parameters or None if they can't be determined
        """
        return self.reg_calc.collect_device_info(config_data, self.reg_calc_map)

    @staticmethod
    def update_sys_params(config_data: ConfigData):  # type: ignore
        """Update sys_params with dcd_fw_params.

        @param config_data: processor config data
        """
        _sys_params = config_data.params.get(Const.PARAM_S_SYS, config_data.sys_params)
        for key in _sys_params.keys():
            _sys_params[key] = config_data.params[Const.PARAM_S_DCD_FW_PARAMS].get(key, _sys_params[key])
        config_data.params[Const.PARAM_S_SYS] = _sys_params

    @staticmethod
    def update_diags_params(config_data: ConfigData):  # type: ignore
        """Update diag_params with dcd_diag_params.

        @param config_data: processor config data
        """
        for key in config_data.diags_params.keys():
            config_data.diags_params[key] = config_data.params['dcd_diag_params'].get(key,
                                                                                      config_data.diags_params[key])
        config_data.params[Const.PARAM_S_DIAGS] = config_data.diags_params

    def add_ddrc_before_config_errata(self, config_data):  # type: ignore
        """TODO:summary line."""
        # nothing to do by default; if needed, each processor should override this
        pass

    def add_ddrc_after_config_errata(self, config_data):  # type: ignore
        """TODO:summary line."""
        # nothing to do by default; if needed, each processor should override this
        pass

    def add_ddrc_after_enable_errata(self, config_data):  # type: ignore
        """TODO:summary line."""
        # nothing to do by default; if needed, each processor should override this
        pass

    def close_communication_channel(self):  # type: ignore
        """Close processor communication channel if needed (e.g. USB)."""
        pass

    def get_app_symbol_names(self, primary_image: bool = True) -> List[str]:
        """Gets the application symbols for primary or secondary image.

        @param primary_image: True if symbols for primary image is needed, False otherwise
        @return: application symbols
        """
        app_syms = self.processor_info.get_app_symbols(primary_image)
        if not app_syms:
            return AppInterface.get_app_symbol_names()
        return app_syms

    def pre_test_updates(self, config_data) -> TestStatus:  # type: ignore
        """Check test parameters.

        @param config_data: target configuration data
        @return: test status after parameter validation
        """
        self.update_sys_params(config_data)

        if Const.PARAM_S_BASIC_MEM_TYPE in config_data.params[Const.PARAM_S_BASIC]:
            # Run RPA tool
            self.ddrc_reg_calc(config_data)
        else:
            # Import RPA script
            config_data.load_rpa_from_file()

        self.update_diags_params(config_data)

        workspace_dir = Workspace.get_instance().get_location()
        with open(os.path.join(workspace_dir, f"{config_data.mem_type}{Const.DS_FILE_SUFFIX}"),
                  'wt', encoding="utf-8") as f:
            f.write(config_data.ds_file_txt)

        if not config_data.ds_is_valid:
            return TestStatus.DS_INVALID

        # update PHY input and DDRC config using DS file
        self.update_connection_parameters(config_data)
        self.update_ddrc_config(config_data)
        self.update_phy_config(config_data)

        # create DDR controller configuration file
        ddrc_config_file = os.path.join(workspace_dir, "ddrc_config_final.json")
        with open(ddrc_config_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(config_data.ddrc_config_full, indent=4))

        # run phyinit
        phy_init_driver = PHYInitDriver.make_unique_instance(config_data.data_dir, config_data.snps_phy_info.name,
                                                             config_data.mem_type)
        phy_init_driver.run_driver(config_data)
        phy_init_driver.process_results(config_data)

        # target addresses and binary sizes
        self.init_bin_info(config_data)

        # create full dmem config
        config_data.generate_firmware_dmem_binaries()

        # check test parameters; it will throw an exception in case of an error
        return BaseTest.validate_parameters(config_data)
