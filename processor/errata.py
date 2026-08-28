# Copyright 2021-2023, 2025 NXP
"""TODO:summary line."""
import logging

from memtool.common.config_data import ConfigData
from memtool.common.dcd_commands import DCDCommandIds
from memtool.processor.errata_library import ErrataLibrary, ErrataType, ErrataUpdatePolicyType


class Errata:
    """Base class for handling errata."""

    logger = logging.getLogger(__name__)

    def __init__(self):  # type: ignore
        """TODO:summary line."""
        pass

    def insert_after_rpa(self, config_data: ConfigData):  # type: ignore
        """Insert errata after DS file was created.

        @param config_data: processor config data
        """
        pass

    def __update_phy_commands(self, config_data: ConfigData, errata: ErrataType, fsp: str = ''):  # type: ignore
        """Update phy config commands list for the given errata type and frequency point.

        @param config_data: processor configuration data
        @param errata: errata type <=> phy section
        @param fsp: frequency point id or '' for common section
        """
        section = f'{errata.value}{fsp}'
        if section not in config_data.phy_full_config:
            self.logger.info('\'%s\' section is missing from config_data.phy_full_config!', section)
            return

        phy_init_cmds = config_data.phy_full_config[section]
        for errata_cmd in ErrataLibrary.get_errata(config_data, errata, fsp):
            if errata_cmd.command != DCDCommandIds.CMD_PHY_WRITE_DATA:
                self.logger.warning('Only \'phy set\' commands can be applied to config_data.phy_full_config!')
                continue

            append_command = True
            if errata_cmd.mode == ErrataUpdatePolicyType.UPDATE_CMD:
                for cmd_idx in range(len(phy_init_cmds)):
                    cmd = phy_init_cmds[cmd_idx]
                    if len(cmd) < 0:
                        self.logger.error('Invalid command \'%s\' found in section \'%s\''
                                          ' from config_data.phy_full_config!', str(cmd), section)
                        return
                    if errata_cmd.address == cmd[0]:
                        phy_init_cmds[cmd_idx] = (errata_cmd.address, errata_cmd.value)
                        append_command = False
                        break

            if append_command:
                phy_init_cmds.append((errata_cmd.address, errata_cmd.value))

    def update_phy(self, config_data: ConfigData):  # type: ignore
        """Update phy config sections (initPhyConfig, loadPIEImage) from config_data.phy_full_config with erratas.

        @param config_data: processor configuration data
        """
        sections_to_update = [ErrataType.PHY_INIT, ErrataType.LOAD_PIE]
        for section in sections_to_update:
            self.__update_phy_commands(config_data, section)

            if config_data.is_phy_v3(config_data.snps_phy_info):
                for fsp in list(range(config_data.num_pstates)):
                    self.__update_phy_commands(config_data, section, str(fsp))
