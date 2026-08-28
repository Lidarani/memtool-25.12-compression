# Copyright 2022-2025 NXP
"""TODO:summary line."""
import os

from memtool.common.config_data import ConfigData
from memtool.common.workspace import Workspace
from memtool.processor.imxrt1xxxx.imxrt10xx_processor import MIMXRT10XXProcessor
from memtool.processor.sdp_processor import SDPProcessor


class MIMXRT10XX(MIMXRT10XXProcessor, SDPProcessor):
    """TODO:summary line."""

    def __init__(self, name: str, ddr_type: str):
        """TODO:summary line."""
        super(MIMXRT10XX, self).__init__(name, ddr_type)

    def _load_images(self, config_data: ConfigData):  # type: ignore
        """Load the appropriate firmware bins for the op type and dcd bin.

        @param config_data: processor config data
        """
        # Load dcd block
        if not config_data.skip_download:
            if not self.sdp.load_bin(load_address=int(config_data.target_params['dcd_addr'], 16),  # type: ignore
                    filename=config_data.target_params['dcd_file']):
                return

        insert_fcb_header = ('load_fcb_header' in config_data.params['app']
                             and config_data.params['app']['load_fcb_header'])
        insert_hello_world_app = ('load_fcb' in config_data.params['app']) and config_data.params['app']['load_fcb']

        if insert_fcb_header:
            try:
                binaries_folder = os.path.join(config_data.data_dir, 'binaries')
                bin_file = next(iter(filter(lambda x: (x.endswith('.axf')), os.listdir(binaries_folder))))

                app_path = os.path.join(binaries_folder, bin_file).replace('\\', '/').replace('.axf', '.bin')
                with open(app_path, 'rb') as f:
                    fcb_app = f.read()
                workspace_dir = Workspace.get_instance().get_location()
                fcb_bin_header = os.path.join(workspace_dir, 'fcb.bin').replace('\\', '/')
                with open(fcb_bin_header, 'rb') as fr:
                    fcb_header = fr.read()
            except Exception:
                raise Exception('fcb.bin file was not found at path %s' % (binaries_folder))

        if insert_hello_world_app:
            # ONLY for Write Flash image FCB test : Load fcb header + bootable binary
            self.sdp.load_bin(int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'], 16),  # type: ignore
                fcb_app, filename=app_path)
            config_data.params['app']['test_params']['size'] = len(fcb_app)

        if insert_fcb_header:
            # Overwrite header
            self.sdp.load_bin(int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'], 16),  # type: ignore
                fcb_header, filename=fcb_bin_header)
