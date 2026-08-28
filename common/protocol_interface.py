# Copyright 2022-2025 NXP
"""TODO:summary line."""
from abc import abstractmethod

from memtool.common.config_data import ConfigData


class CommProtocolInterface:
    """Interface for implementing communication protocol."""

    @abstractmethod
    def load_app(self, config_data: ConfigData, sm_enabled: bool = False) -> None:
        """Load application.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        """
        pass

    @abstractmethod
    def execute(self, config_data: ConfigData, resume_from_bkp: bool = False) -> None:
        """Execute application.

        @param config_data: processor config data
        @param resume_from_bkp: resume from breakpoint
        """
        pass
