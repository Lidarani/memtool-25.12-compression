# Copyright 2021-2025 NXP
"""TODO:summary line."""
import json
import logging
import os
import sys
import traceback
from ctypes import CDLL

from memtool.common.config_data import ConfigData
from memtool.common.factories import FactoryClass, ProcessorFactory
from memtool.common.options import Options, SnpsPhyInitEnum
from memtool.common.workspace import Workspace
from memtool.phyinit.out_parser import PhyInitParser
from memtool.utils.constants import Const


class PHYInitFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """Using a factory superclass because the framework won't instantiate direct Descendants of factory class."""
    pass


class PHYInitDriver(PHYInitFactory):
    """Class for running PhyInit."""

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """This is the only class of this type, so it should match."""
        return True

    def __init__(self, data_dir, fw_version, mem_type):  # type: ignore
        """TODO:summary line."""
        logger = logging.getLogger(__name__)

        self.data_dir = data_dir
        logger.info("Run phyinit for %s%s%s", fw_version, os.path.sep, mem_type)

        if sys.platform == "win32":
            dll_name = f'phyinit_{fw_version}_{mem_type}.dll'
        else:
            dll_name = f'phyinit_{fw_version}_{mem_type}.so'

        dll_path = os.path.join(data_dir, Const.LIB_DIR_NAME, dll_name)
        logger.debug("Shared library %s", os.path.abspath(dll_path))

        # load the shared object file
        if os.path.isfile(dll_path) and os.path.isfile(dll_path):
            self.phyinit_lib = CDLL(dll_path)
        else:
            logger.error("Cannot find %s", os.path.abspath(dll_path))
            self.phyinit_lib = None
            raise ResourceWarning(f"Cannot find {os.path.abspath(dll_path)}")
        self.mem_type = mem_type
        self.phyinit_out_file = f'{Const.phyinit_out_file_name}'
        self.retention_out_file = f'{Const.retention_out_file_name}'

    def run_driver(self, config_data: ConfigData):  # type: ignore
        """Init PHY config through cdll lib call.

        @param config_data: processor config data
        """
        logger = logging.getLogger(__name__)

        # ensure that the phy parameters are in the format needed by the firmware version - temporary solution
        # TODO: devise a better way to ensure firmware version compliance
        if config_data.snps_phy_info.name in ('2024.09', '2024.09-SP2') and \
            'PhyVrefCode' in config_data.params[Const.PARAM_S_PHY]['userInputAdvanced']:
            config_data.params[Const.PARAM_S_PHY]['userInputAdvanced']['PhyVrefCode[0]'] = \
                config_data.params[Const.PARAM_S_PHY]['userInputAdvanced']['PhyVrefCode']
            config_data.params[Const.PARAM_S_PHY]['userInputAdvanced'].pop('PhyVrefCode')

        workspace_dir = Workspace.get_instance().get_location()
        phy_config_file = os.path.join(workspace_dir, "phy_config_final.json")
        with open(phy_config_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(config_data.params[Const.PARAM_S_PHY], indent=4))

        if workspace_dir != '':
            self.phyinit_out_file = f'{workspace_dir}/{Const.phyinit_out_file_name}'
            self.retention_out_file = f'{workspace_dir}/{Const.retention_out_file_name}'

        logger.debug("PHY config file %s", os.path.abspath(phy_config_file))
        logger.debug("Phyinit output file %s", os.path.abspath(self.phyinit_out_file))
        logger.debug("Retention output file %s", os.path.abspath(self.retention_out_file))

        if self.phyinit_lib is not None and os.path.isfile(phy_config_file):
            # for quick boot, we need to run phy training for computing message blocks
            quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                          Const.PHY_QUICK_BOOT)
            train2d = 0 if (self.mem_type in ['ddr3']) or ConfigData.is_phy_v3(
                config_data.snps_phy_info) or quick_boot else 1
            skip_train = SnpsPhyInitEnum.FULL_TRAINING.value if quick_boot else \
                            Options.get_instance().get_snps_phy_init_options().get_phy_init_option()

            run_dir = os.getcwd()
            os.chdir(self.data_dir)
            try:
                self.phyinit_lib.phy_init_config(phy_config_file.encode('utf-8'), self.phyinit_out_file.encode('utf-8'),
                    self.retention_out_file.encode('utf-8'), train2d, skip_train)
            except Exception:
                traceback.print_exc()

            os.chdir(run_dir)
        else:
            logger.error("Cannot find %s", os.path.abspath(phy_config_file))

    def process_results(self, config_data: ConfigData):
        """Parse config data and instantiate a processor.

        @param config_data: processor config data
        """
        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            PhyInitParser.parse_phy_v2(config_data, self.phyinit_out_file, self.retention_out_file)
        elif ConfigData.is_phy_v3(config_data.snps_phy_info):
            PhyInitParser.parse_phy_v3(config_data, self.phyinit_out_file, self.retention_out_file)
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        processor.update_phy(config_data)
