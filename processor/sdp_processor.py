# Copyright 2020-2025 NXP
"""TODO:summary line."""
import logging
import os

from memtool.common.config_data import ConfigData
from memtool.common.factories import SDPFactory
from memtool.common.protocol_interface import CommProtocolInterface
from memtool.common.sdp_interface import SDPUtils
from memtool.utils.constants import Const


class SDPProcessor(CommProtocolInterface):
    """SDPProcessor uses SDP as communication protocol with target."""

    logger = logging.getLogger(__name__)

    # SDP protocol ID
    PROTOCOL = "sdp"

    def __init__(self, soc_name, dram_type):  # type: ignore
        """Constructor."""
        self.usb_id = None
        self.soc_name = soc_name
        self.sdp = None

    def load_app(self, config_data: ConfigData, sm_enabled: bool = False) -> None:
        """Load application. Implements load_app from CommProtocolInterface.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        """
        self.sdp = SDPFactory.make_unique_instance_without_caching(config_data.connect_params)

        if self.sdp.is_alive():
            self.sdp.close()
        self.sdp.open()

        load_addr = int(config_data.target_params["workspace_address"], 16) - SDPUtils.IVT_HEADER_SIZE
        app_path = self.get_test_bin_file_name(config_data)  # type: ignore

        with open(app_path, 'rb') as f:
            data = f.read()
            alg_size = os.path.getsize(app_path)
            ivt = self._build_ivt_hdr(config_data, load_addr, config_data.target_params['start_addr'], alg_size)

            if not self.sdp.load_bin(load_addr, ivt + data, filename=app_path):
                return  # TODO: treat err
        self._load_images(config_data)

    def _build_ivt_hdr(self, config_data: ConfigData, load_addr: int, start: int, size: int) -> bytes:
        return SDPUtils.build_ivt_hdr(load_addr, start, size)

    def execute(self, config_data: ConfigData, resume_from_bkp: bool = False) -> None:
        """Override execute from CommProtocolInterface."""
        self.logger.info(" Execute image")  # type: ignore

        if not self.sdp.jump(jump_address=int(config_data.target_params['workspace_address'], 16)
                                          - SDPUtils.IVT_HEADER_SIZE):
            return  # TODO: treat err
        self.sdp.close()

    def _load_images(self, config_data: ConfigData):  # type: ignore
        """Load the appropriate firmware bins for the op type and dcd bin.

        @param config_data: processor config data
        """
        # Will need to load 1D/2D firmware depending on 'train_2d' param value
        self._load_firmware(config_data, firmware_2d=False)
        if config_data.train_2d:
            self._load_firmware(config_data, firmware_2d=True)
            if config_data.diags_params['diag_test'] != Const.NO_DIAG_TEST:
                self._load_diag_firmware(config_data)

        # Load dcd block
        if not config_data.skip_download:
            if not self.sdp.load_bin(load_address=int(config_data.target_params['dcd_addr'], 16),
                    filename=config_data.target_params['dcd_file']):
                self.logger.error("Error loading dcd binary.")
                return

    def _load_firmware(self, config_data: ConfigData, firmware_2d: bool = False):  # type: ignore
        """Load firmware.

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
        if not self.sdp.load_bin(filename=dmem_path, load_address=dmem_address):
            self.logger.error("Error loading dmem firmware binary.")
            return

        # Load firmware instruction binary
        if not config_data.skip_download:
            if not self.sdp.load_bin(filename=imem_path, load_address=imem_address):
                self.logger.error("Error loading imem firmware binary.")
                return

    def _load_diag_firmware(self, config_data: ConfigData) -> None:
        """Load diagnostics firmware.

        @param config_data: processor config data
        """
        if not config_data.train_2d:
            self.logger.error("Error loading diagnostics firmware, train 2D is required.")
            return

        if Const.DIAGS_DMEM_FILE_PATH not in config_data.fw_bin_info or Const.DIAGS_IMEM_FILE_PATH not in \
                config_data.fw_bin_info:
            self.logger.error("Error loading diagnostics firmware, missing firmware path.")
            return

        dmem_diags_path = config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH]
        dmem_diags_source = int(config_data.sys_params[Const.DIAGS_DMEM_SOURCE], 16)
        imem_diags_path = config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH]
        imem_diags_source = int(config_data.sys_params[Const.DIAGS_IMEM_SOURCE], 16)

        # Load DMEM diag firmware binary
        if not self.sdp.load_bin(filename=dmem_diags_path, load_address=dmem_diags_source):
            self.logger.error("Error loading dmem diagnostics firmware binary.")
            return

        # Load IMEM diag firmware binary
        if not config_data.skip_download:
            if not self.sdp.load_bin(filename=imem_diags_path, load_address=imem_diags_source):
                self.logger.error("Error loading imem diagnostics firmware binary.")
                return

    def close_communication_channel(self):  # type: ignore
        """Close processor communication channel."""
        if self.sdp is not None:
            self.sdp.close()
