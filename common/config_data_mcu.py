# Copyright 2022-2024 NXP
"""TODO:summary line."""
from copy import deepcopy
from typing import Dict

from memtool.common.config_data import ConfigData
from memtool.phyinit.phy_utils import PhyPhase
from memtool.utils.constants import Const


class ConfigDataMCU(ConfigData):
    """Hold configuration data for target and tests."""

    def __init__(self, data_dir_path: str, params=None):  # type: ignore
        """Config data constructor.

        @param data_dir_path: path to data dir
        @param params: params to be updated
        """
        super(ConfigDataMCU, self).__init__(data_dir_path, params)

    def data_reset(self, params: Dict[str, dict]):  # type: ignore
        """Reset config and update params.

        @param params: params to be updated
        """
        if params is not None:
            self.soc_name = params[Const.PARAM_S_TC][Const.PARAM_S_TC_SOC_NAME]
            self.params = deepcopy(params)
            self.connect_params = self.params[Const.PARAM_S_TC]

        self.data_width = 0
        self.fw_bin_info = {}
        self.misc_sys_params = {}

        self.target_params = {}
