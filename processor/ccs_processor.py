# Copyright 2021-2024 NXP
"""TODO:summary line."""
import logging
import os

from memtool.comm.cwtap_channel import CWTapChannel
from memtool.common.config_data import ConfigData
from memtool.common.factories import BackendFactory
from memtool.common.protocol_interface import CommProtocolInterface
from memtool.processor.base_processor import BaseProcessor
from memtool.utils.constants import Const


class CCSProcessor(BaseProcessor, CommProtocolInterface):
    """This class provides an implementation for target communication using CSS channel."""

    logger = logging.getLogger(__name__)

    # CCS protocol ID
    PROTOCOL = "ccs"

    def __init__(self, name: str, dram_type: str):
        """TODO:summary line."""
        super(CCSProcessor, self).__init__(name, dram_type)
        self.ccs_channel = None

    def init_target(self, ccs_channel):  # type: ignore
        """Initialise communication with target processor.

        @param ccs_channel: CSS channel to communicate with target processor
        """
        # TODO: see if it shouldn't be @abstractmethod
        # nothing to do by default; if needed, each processor should override this
        pass

    def load_app(self, config_data: ConfigData, sm_enabled: bool = False):  # type: ignore
        """Load application. Implements load_app from CommProtocolInterface.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        """
        channel = BackendFactory.make_unique_instance(config_data.connect_params)
        self._load_app_using_channel(channel, config_data)

    def _load_app_using_channel(self, channel, config_data: ConfigData):  # type: ignore
        """Open channel and load bin files.

        @param channel: communication channel with target processor
        @param config_data: processor config data
        """
        self.ccs_channel = channel
        if not self.ccs_channel.is_alive():  # type: ignore
            self.ccs_channel.open(config_data)  # type: ignore
            assert self.ccs_channel.is_alive()  # type: ignore
            # TODO: what if it isn't?
            self.init_target(self.ccs_channel)

        self._load_image(load_addr=int(config_data.target_params["workspace_address"], 16),
            file_path=self.get_test_bin_file_name(config_data))
        self._load_images(config_data)

    def _load_diag_firmware(self, config_data: ConfigData) -> None:
        """Load diagnostics firmware.

        @param config_data: processor config data
        """
        if Const.DIAGS_DMEM_FILE_PATH not in config_data.fw_bin_info or Const.DIAGS_IMEM_FILE_PATH not in \
                config_data.fw_bin_info:
            self.logger.error("Error loading diagnostics firmware, missing firmware path.")
            return

        dmem_diags_path = config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH]
        dmem_diags_source = int(config_data.sys_params[Const.DIAGS_DMEM_SOURCE], 16)
        imem_diags_path = config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH]
        imem_diags_source = int(config_data.sys_params[Const.DIAGS_IMEM_SOURCE], 16)

        # Load DMEM diag firmware binary
        self._load_image(load_addr=dmem_diags_source, file_path=dmem_diags_path)

        # Load IMEM diag firmware binary
        if not config_data.skip_download:
            self._load_image(load_addr=imem_diags_source, file_path=imem_diags_path)

    def execute(self, config_data: ConfigData, resume_from_bkp=False):  # type: ignore
        """Override execute from CommProtocolInterface."""
        start_pc_value = config_data.target_params['start_addr']
        pc_reg_index = self.get_pc_register()
        self.ccs_channel.write_register(pc_reg_index, start_pc_value.to_bytes(4, byteorder='big'))  # type: ignore

        # check PC was correctly set
        pc_value = int.from_bytes(self.ccs_channel.read_register(pc_reg_index), 'big')  # type: ignore
        assert start_pc_value == pc_value

        self.ccs_channel.run()  # type: ignore

    def _load_image(self, load_addr: int, file_path: str):  # type: ignore
        """Read from file and write to channel.

        @param load_addr: first address to write to
        @param file_path: bin file to read from
        """
        with open(file_path, 'rb') as f:
            bytes_read = f.read(CWTapChannel.CHUNK_SIZE)
            no_bytes_read = len(bytes_read)
            while no_bytes_read > 0:
                if not self.ccs_channel.write_data(load_addr, len(bytes_read), bytes_read):  # type: ignore
                    return  # TODO: treat err

                load_addr += no_bytes_read
                bytes_read = f.read(CWTapChannel.CHUNK_SIZE)
                no_bytes_read = len(bytes_read)

    def _load_images(self, config_data: ConfigData):  # type: ignore
        """Load the appropriate firmware bins for the op type and dcd bin.

        @param config_data: processor config data
        """
        # Will need to load 1D/2D firmware depending on 'train_2d' param value
        if Const.PARAM_SERDES_SKIP_DDR_PHY not in config_data.params[Const.PARAM_S_BASIC]:
            self._load_firmware(config_data, False)
            self._load_firmware(config_data, True)
            if config_data.diags_params['diag_test'] != Const.NO_DIAG_TEST:
                self._load_diag_firmware(config_data)

        # Load dcd block
        if not config_data.skip_download:
            self._load_image(load_addr=int(config_data.target_params['dcd_addr'], 16),
                file_path=config_data.target_params['dcd_file'])

    def _load_firmware(self, config_data: ConfigData, firmware_2d=False):  # type: ignore
        """Load firmware binaries.

        @param config_data: processor config data
        @param firmware_2d: True if 2D firmware images are requested, false otherwise
        """
        # Suffix for variables used
        stage = "2d" if firmware_2d else "1d"

        dmem_address = int(config_data.sys_params['dmem_fw_source_' + stage], 16)
        imem_address = int(config_data.sys_params['imem_fw_source_' + stage], 16)
        dmem_path = config_data.fw_bin_info['dmem_fw_path_' + stage]
        imem_path = config_data.fw_bin_info['imem_fw_path_' + stage]

        # Load firmware data binary
        self._load_image(load_addr=dmem_address, file_path=dmem_path)

        # Load firmware instruction binary
        if not config_data.skip_download:
            self._load_image(load_addr=imem_address, file_path=imem_path)

    def get_pc_register(self):  # type: ignore
        """Getter for PC reg index.

        @return: PC reg index
        """
        # TODO: see if it shouldn't be @abstractmethod
        # must be overwritten by each child processor
        return -1
