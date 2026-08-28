# Copyright 2023-2024 NXP
"""TODO:summary line."""
import logging

from memtool.common.config_data import ConfigData, SnpsFirmware
from memtool.common.factories import Singleton


class TargetConfiguration(metaclass=Singleton):
    """Workspace singleton class that handles current target configuration."""

    logger = logging.getLogger(__name__)

    # default processor
    DEFAULT_PROCESSOR = 0  # MIMX8M

    def __init__(self):  # type: ignore
        """Constructor."""
        self.__supported_processors = list(ConfigData.DEVICES_INFO.keys())
        self.__processor_index = TargetConfiguration.DEFAULT_PROCESSOR
        self.__processor_name = self.__supported_processors[self.__processor_index]
        self.__firmware = None  # firmware id (SnpsFirmware.id)
        self.__memory_type = None  # memory type (index in ConfigData.MEMORY_TYPES)

    @staticmethod
    def get_instance():  # type: ignore
        """Get singleton instance of settings."""
        return TargetConfiguration()

    def set_processor(self, _processor_index: int):  # type: ignore
        """Set current processor.

        @param _processor_index: processor index in supported devices
        """
        if _processor_index < 0 or _processor_index >= len(self.__supported_processors):
            self.logger.error(f'Invalid processor index {_processor_index}; '
                              f'it should be in range [0, {len(self.__supported_processors)}]! '
                              f'Current processor will be set to'
                              f' {self.__supported_processors[TargetConfiguration.DEFAULT_PROCESSOR]}.')
            self.__processor_index = TargetConfiguration.DEFAULT_PROCESSOR
        else:
            self.__processor_index = _processor_index
        self.__processor_name = self.__supported_processors[self.__processor_index]

    def get_processor_index(self) -> int:
        """Get current processor index."""
        return self.__processor_index

    def get_processor(self) -> str:
        """Get current processor."""
        return self.__processor_name

    def set_firmware(self, _firmware: int, _config_data: ConfigData):  # type: ignore
        """Set current firmware.

        @param _firmware: firmware id
        @param _config_data: configuration data
        """
        fw = SnpsFirmware.from_id(_firmware)
        fw_name = f'FW{fw.name}'
        proc_supported_firmwares = _config_data.get_loaded_firmware_versions(self.__processor_name)
        if fw_name not in proc_supported_firmwares:
            self.logger.error(f'Firmware with id {_firmware} not supported for current processor! '
                              f'Current firmware id will be set to the first supported firmware.')

            fw = SnpsFirmware.from_name(proc_supported_firmwares[0][2:])
            self.__firmware = fw.id  # type: ignore
        else:
            self.__firmware = _firmware  # type: ignore

    def get_firmware(self) -> int:
        """Get current firmware id."""
        if self.__firmware is None:
            self.logger.error('Firmware not set!')
        return self.__firmware  # type: ignore

    def set_memory_type(self, _memory_type: int, _config_data: ConfigData):  # type: ignore
        """Set memory type.

        @param _memory_type: memory type (index in ConfigData.MEMORY_TYPES)
        @param _config_data: configuration data
        """
        mem_name = "unknown_memory"
        if _memory_type in ConfigData.MEMORY_TYPES.keys():
            mem_name = ConfigData.MEMORY_TYPES[_memory_type].upper()
        proc_supported_memories = _config_data.get_loaded_memory_types(self.__processor_name)
        if mem_name not in proc_supported_memories:
            self.logger.error(f'Memory with id {_memory_type} not supported for current processor! '
                              f'Current memory id will be set to the first supported memory.')
            mem_name = proc_supported_memories[0]
            self.__memory_type = ConfigData.get_memory_id(mem_name)  # type: ignore
        else:
            self.__memory_type = _memory_type  # type: ignore

    def get_memory_type(self) -> int:
        """Get memory type."""
        if self.__memory_type is None:
            self.logger.error('Memory type not set!')
        return self.__memory_type  # type: ignore
