# Copyright 2022-2025 NXP

"""TODO:summary line."""
import logging
import os

from spsdk.image.ahab.ahab_image import AHABImage
from spsdk.utils.config import Config
from spsdk.utils.misc import get_abs_path, load_configuration, write_file

from memtool.common.config_data import ConfigData
from memtool.common.factories import MBootFactory, ProcessorFactory
from memtool.common.sdp_interface import SDPUtils
from memtool.common.workspace import Workspace
from memtool.utils.constants import Const
from memtool.utils.helper import align

IVT_HEADER_SIZE_mboot = 0x2000
OFFSET_AHAB = 0x400


class MbootProcessor:
    """This class handles targets that support MBOOT protocol."""

    logger = logging.getLogger(__name__)

    # Analyse MBOOT implementation in python
    def __init__(self, name):  # type: ignore
        """TODO:summary line."""
        self.mcuboot = None

        # super(MbootProcessor, self).__init__(name)

    def load_app(self, config_data: ConfigData, sm_enabled: bool = False):  # type: ignore
        """Override load_app from BaseProcessor.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        """
        self.mcuboot = MBootFactory.make_unique_instance(config_data.connect_params)
        if not self.mcuboot.is_alive():
            self.mcuboot.open()

        if ("container" in config_data.connect_params) and 'AHAB' in config_data.connect_params["container"]:
            image = self._build_ahab_image(config_data)
        else:
            image = self._build_ivt_image(config_data)

        self.mcuboot.load_bin(data=image)

    def _insert_fcb_header(self, config_data: ConfigData, _image: bytearray):  # type: ignore
        """Inserts FCB header.

        @param config_data: processor config data
        """
        fcb_header_size = 0
        try:
            # see if fcb images are there
            workspace_dir = Workspace.get_instance().get_location()
            fcb_bin_header = os.path.join(workspace_dir, 'fcb.bin').replace('\\', '/')
            fcb_header_size = os.path.getsize(fcb_bin_header)
        except Exception:
            raise Exception('fcb.bin file was not found at path %s' % (workspace_dir))

        # Overwrite header
        fcb_offset = 0
        if ('load_fcb' in config_data.params['app']) and (config_data.params['app']['load_fcb']):
            # If hello_world is not loaded, offset = 0, and is added at the end of application binary
            # fcb offset from json makes sense only for check boot test
            fcb_offset = config_data.params['connect']['fcb_offset']
        self._insert_bin_data(
            config_data, image=_image, filename=fcb_bin_header,
            address=(int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'], 16)
                     + fcb_offset),  # offset to boot from
            size=fcb_header_size)

    def _insert_hello_world_app(self, config_data: ConfigData, _image: bytearray):  # type: ignore
        """Inserts hello_world app into the image.

        @param config_data: processor config data
        """
        try:
            # see if fcb images are there
            binaries_folder = os.path.join(config_data.data_dir, 'binaries')
            app_path = self.get_hello_world_app_path(config_data)
            fcb_app_size = os.path.getsize(app_path)
            config_data.params['app']['test_params']['size'] = fcb_app_size
        except Exception:
            raise Exception('hello world app was not found at path %s' % (binaries_folder))

        self._insert_bin_data(config_data, image=_image, filename=app_path,
            address=int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'], 16), size=fcb_app_size)

    def get_hello_world_app_path(self, config_data: ConfigData):  # type: ignore
        """TODO:summary line."""
        try:
            binaries_folder = os.path.join(config_data.data_dir, 'binaries')
            bin_file = next(iter(filter(lambda x: (x.endswith('.axf')), os.listdir(binaries_folder))))
            app_path = os.path.join(binaries_folder, bin_file).replace('\\', '/').replace('.axf', '.bin')
        except Exception:
            raise Exception('hello world app was not found at path %s' % (binaries_folder))
        return app_path

    def _build_ahab_image(self, config_data: ConfigData):  # type: ignore
        """Override Builds AHAB image.

        @param config_data: processor config data
        """
        self.logger.info("Build AHAB image for IMXRT118x")
        binary_file = self.get_test_bin_file_name(config_data)  # type: ignore
        _file_size = os.path.getsize(binary_file)
        __image = bytearray(_file_size)
        _data = bytearray(_file_size)
        with open(binary_file, 'rb') as f:
            _data = f.read()  # type: ignore
        __image[0: _file_size] = _data

        # Insert DCD before creating AHAB container, to correctly calculate CRCR in the header
        self._insert_bin_data(config_data, image=__image, filename=config_data.target_params['dcd_file'],
            address=int(config_data.target_params['dcd_addr'], 16) - IVT_HEADER_SIZE_mboot, size=0)
        ### ONLY for Write Flash image FCB test : Load fcb header + bootable binary
        insert_fcb_header = ('load_fcb_header' in config_data.params['app']) and config_data.params['app'][
            'load_fcb_header']
        insert_hello_world_app = ('load_fcb' in config_data.params['app']) and config_data.params['app']['load_fcb']

        if insert_hello_world_app:
            app_path = self.get_hello_world_app_path(config_data)
            fcb_app_size = os.path.getsize(app_path)
            config_data.params['app']['test_params']['size'] = fcb_app_size
            self._insert_bin_data(config_data, image=__image, filename=app_path,
                address=int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'], 16) - IVT_HEADER_SIZE_mboot,
                size=fcb_app_size)
        if insert_fcb_header:
            workspace_dir = Workspace.get_instance().get_location()
            fcb_bin_header = os.path.join(workspace_dir, 'fcb.bin').replace('\\', '/')
            fcb_header_size = os.path.getsize(fcb_bin_header)
            fcb_offset = 0
            if 'fcb_offset' in config_data.params['connect']:
                # this is the check boot test - fcb offset is needed to be loaded from flash at boot time. offset is
                # set according to manual
                fcb_offset = config_data.params['connect']['fcb_offset']
            if not insert_hello_world_app:
                # this is the case of transaction blocking test - in this case no offset is needed
                fcb_offset = 0
            self._insert_bin_data(config_data, image=__image, filename=fcb_bin_header, address=(
                        int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'],
                            16) + fcb_offset - IVT_HEADER_SIZE_mboot),  # offset to boot from
                size=fcb_header_size)

        write_file(__image, binary_file + "_dcd", mode="wb")

        # Create AHAB image
        ahab_folder = os.path.join(config_data.data_dir, 'templates')  # for RT118x
        config = os.path.join(ahab_folder, 'ahab_config.yaml')
        ahab_cnt = AHABImage.load_from_config(Config.create_from_file(config))
        ahab_cnt.update_fields()
        ahab_data = ahab_cnt.export()

        # SHIFT image by AHAB_OFFSET and fill in load and start address based on syms
        load_address = int(config_data.target_params["workspace_address"], 16)
        self.logger.info("Load address is: 0x%x", int(load_address))
        _image = bytearray(len(ahab_data) + OFFSET_AHAB)
        _image[OFFSET_AHAB:len(ahab_data) + OFFSET_AHAB] = ahab_data

        return _image

    def _build_ivt_image(self, config_data: ConfigData):  # type: ignore
        """Build image to download for m815, m865.

        @param config_data: processor config data
        @return: bytearray containing the image
        """
        self.logger.info("Build IVT header for IMXRT1170")

        start = config_data.target_params['start_addr']
        load_addr = int(config_data.target_params["workspace_address"], 16)
        alg_size = int(config_data.params['config']['Image$$BOOTAPP_START$$RO$$Base'], 16) - load_addr

        fcb_app_size = 0
        fcb_header_size = 0
        if ('load_fcb' in config_data.params['app']) and config_data.params['app']['load_fcb']:
            app_path = self.get_hello_world_app_path(config_data)
            fcb_app_size = os.path.getsize(app_path)
        if ('load_fcb' in config_data.params['app']) and (not config_data.params['app']['load_fcb']):
            # for Enable quad test fcb header is added after the application binary
            fcb_header_size = 512

        _image = bytearray(alg_size + IVT_HEADER_SIZE_mboot + fcb_app_size + fcb_header_size)
        _image[0:IVT_HEADER_SIZE_mboot] = (
            self._build_ivt_hdr(config_data, load_addr, start,
                                alg_size + IVT_HEADER_SIZE_mboot + fcb_app_size + fcb_header_size))

        self._insert_bin_data(config_data, image=_image,
            filename=self.get_test_bin_file_name(config_data), address=load_addr, size=alg_size)  # type: ignore

        self._insert_bin_data(config_data, image=_image, filename=config_data.target_params['dcd_file'],
                              address=int(config_data.target_params['dcd_addr'], 16), size=0)

        # ONLY for Write Flash image FCB test : Load fcb header + bootable binary
        insert_fcb_header = (('load_fcb_header' in config_data.params['app'])
                             and config_data.params['app']['load_fcb_header'])
        insert_hello_world_app = ('load_fcb' in config_data.params['app']) and config_data.params['app']['load_fcb']

        if insert_hello_world_app:
            self._insert_hello_world_app(config_data, _image)
        if insert_fcb_header:
            self._insert_fcb_header(config_data, _image)

        return _image

    def _build_ivt_hdr(self, config_data: ConfigData, load_addr: int, start: int, size: int) -> bytes:
        """Build IVT Header as byte array.

        @param config_data: processor config data
        @return: bytearray containing the image
        """
        start = config_data.target_params['start_addr']
        self.logger.info("Build IVT header for IMXRT1070")
        # ivt_header
        tag = 0x412000D1
        ivt_hdr = tag.to_bytes(4, byteorder='little')

        # entry: Absolute address of the first instruction to execute from the image
        ivt_hdr += start.to_bytes(4, byteorder='little')

        # reserved1: Reserved and should be zero
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # dcd_ptr: Absolute address of the image DCD.
        # The DCD is optional so this field may be set to NULL if no DCD is required
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # boot_data_ptr: Absolute address of the boot data
        ivt_hdr += (load_addr + 0x20 - IVT_HEADER_SIZE_mboot).to_bytes(4, byteorder='little')  # load_addr + 0x20

        # self_ptr: Absolute address of the IVT. Used internally by the ROM.
        ivt_hdr += (load_addr - IVT_HEADER_SIZE_mboot).to_bytes(4, byteorder='little')

        # csf: Absolute address of the Command Sequence File (CSF) used by the HAB library.
        # See High-Assurance Boot (HAB) for
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # reserved2: Reserved and should be zero
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # boot_data: start
        ivt_hdr += (load_addr - IVT_HEADER_SIZE_mboot).to_bytes(4, byteorder='little')
        # boot_data: image_len
        ivt_hdr += size.to_bytes(4, byteorder='little')

        # boot_data: plugin flag
        ivt_hdr += (0).to_bytes(4, byteorder='little')

        # padding to IVT_HEADER_SIZE_mboot
        ivt_hdr += (0).to_bytes(IVT_HEADER_SIZE_mboot - 44, byteorder='little')

        return ivt_hdr

    def _insert_bin_data(self, config_data, image, filename, address, size):  # type: ignore
        """TODO:summary line."""
        # TODO: see if size is needed
        _file_size = os.path.getsize(filename)
        _data = bytearray(_file_size)
        with open(filename, 'rb') as f:
            _data = f.read()

        _offset = address - int(config_data.target_params['workspace_address'], 16) + IVT_HEADER_SIZE_mboot

        self.logger.debug('Address %8x offset %8x size %8x insert file %s', address, _offset, _file_size, filename)

        image[_offset: _offset + _file_size] = _data

        return image

    def execute(self, config_data: ConfigData, resume_from_bkp=False):  # type: ignore
        """Override execute from BaseProcessor."""  # self.mcuboot.close()
