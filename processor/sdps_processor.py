# Copyright 2019-2025 NXP
"""TODO:summary line."""
import datetime
import filecmp
import logging
import os
import struct
import shutil
from typing import List, Optional

from ruamel.yaml import CommentedMap, CommentedSeq
from ruamel.yaml.main import YAML
from spsdk.crypto.hash import EnumHashAlgorithm, get_hash
from spsdk.crypto.keys import PublicKey
from spsdk.crypto.signature_provider import PlainFileSP
from spsdk.crypto.utils import get_matching_key_id
from spsdk.exceptions import SPSDKError
from spsdk.image.ahab.ahab_image import AHABImage
from spsdk.utils.binary_image import BinaryImage
from spsdk.utils.config import Config
from spsdk.utils.family import FamilyRevision
from spsdk.utils.misc import load_configuration, write_file
from spsdk.utils.schema_validator import CommentedConfig, check_config

from memtool.comm.sdps_comm import SDPSComm
from memtool.lz4_utils import build_chunked_ddr_firmware
from memtool.common.config_data import ConfigData
from memtool.common.factories import ProcessorFactory, SDPSFactory
from memtool.common.options import Options
from memtool.common.protocol_interface import CommProtocolInterface
from memtool.common.sdp_interface import SDPUtils
from memtool.common.workspace import Workspace
from memtool.utils.constants import Const, SpsdkYamlField
from memtool.utils.helper import align, get_bin_data


class SDPSProcessor(CommProtocolInterface):
    """This class handles targets that support SDPS protocol."""

    logger = logging.getLogger(__name__)

    # SDPS protocol ID
    PROTOCOL = "sdps"

    # Analyse SDP/SDPS implementation in python
    def __init__(self, name, dram_type):  # type: ignore
        """Constructor."""
        self.sdps = None

        # super(SDPSProcessor, self).__init__(name, dram_type)

    def _init_services(self):  # type: ignore
        # TODO: see if implementation is needed
        pass

    def load_app(self, config_data: ConfigData, sm_enabled: bool = False) -> None:
        """Load application. Implements load_app from CommProtocolInterface.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        """
        self.sdps = SDPSFactory.make_unique_instance(config_data.connect_params)

        if self.sdps.is_alive():
            self.sdps.close()
        self.sdps.open()

        image = self.build_image(config_data, sm_enabled)
        if image is not None:
            self.sdps.load_bin(data=image)

    def build_image(self, config_data: ConfigData, sm_enabled: bool):  # type: ignore
        """Build image to download.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        @return: bytearray containing the image
        """
        # create imx9 image
        if ConfigData.DEVICES_INFO[config_data.soc_name].is_imx9():
            bootable_image_options = Options.get_instance().get_bootable_image_options()
            use_custom_bootable_image = bootable_image_options.get_use_custom_bootable_image()
            if use_custom_bootable_image:
                return self.custom_bootable_image()
            else:
                return self.build_ahab_image(config_data, sm_enabled)

        # create non imx9 image
        return self.build_image_v1(config_data)

    def build_ahab_image(self, config_data: ConfigData, sm_enabled: bool):  # type: ignore
        """Build AHAB image.

        @param config_data: processor config data
        @param sm_enabled: system manager enabled
        @return: bytearray containing the image
        """
        if sm_enabled:
            config_data.misc_sys_params[Const.PARAM_S_SYS_SM_ENABLED] = '1'
        use_ahab_file_copy = True

        # generate ahab config file
        if sm_enabled:  # for now, only MIMX95 can be controlled by System Manager
            ahab_file_path = self.generate_ahab_config_file_for_system_manager(config_data)
        else:
            ahab_file_path = self.generate_ahab_config_file(config_data)

        # Create AHAB image
        return self.__generate_ahab_image(config_data, ahab_file_path, use_ahab_file_copy)

    def custom_bootable_image(self) -> Optional[bytearray]:
        """Custom bootable image as binary array.

        @return: Byte array of custom bootable image or None if custom bootable image is not found.
        """
        custom_bootable_image_file = None
        workspace_temp_dir = Workspace.get_instance().get_temp_location()
        workspace_dir = Workspace.get_instance().get_location()
        if os.path.exists(workspace_temp_dir):
            src_bootable_image_file = os.path.join(workspace_temp_dir, Const.CUSTOM_BOOTABLE_IMAGE_NAME)
            dst_bootable_image_file = os.path.join(workspace_dir, Const.CUSTOM_BOOTABLE_IMAGE_NAME)
            if os.path.exists(src_bootable_image_file):
                shutil.copy(src_bootable_image_file, dst_bootable_image_file)
                custom_bootable_image_file = dst_bootable_image_file
                with open(custom_bootable_image_file, 'rb') as custom_bootable_image:
                    return bytearray(custom_bootable_image.read())
            else:
                self.logger.error("No custom bootable image found in workspace!")
                return None
        else:
            self.logger.error("No custom bootable image found in workspace!")
            return None

    @staticmethod
    def _uses_opaque_custom_oei(config_data: ConfigData) -> bool:
        """Return whether this run loads the standalone compressed DDR OEI."""
        return bool(config_data.compress) and config_data.soc_name == 'MIMX95_B0'

    def _get_opaque_custom_oei_path(self, config_data: ConfigData) -> str:
        """Locate the custom OEI binary, allowing an explicit application setting override."""
        custom_path = config_data.params['app'].get('custom_oei_path')
        if custom_path:
            oei_path = os.path.abspath(custom_path)
        else:
            memtool_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            oei_path = os.path.join(
                memtool_dir, 'imx-oei', 'build', 'mx95lp4x-15', 'ddr', 'oei-m33-ddr.bin')
        if not os.path.isfile(oei_path):
            raise SPSDKError(f'Custom OEI image not found: {oei_path}')
        return oei_path

    def build_image_v1(self, config_data: ConfigData):  # type: ignore
        """Build image to download for m815, m865.

        @param config_data: processor config data
        @return: bytearray containing the image
        """
        start = config_data.target_params['start_addr']
        _image = bytearray(int(config_data.target_params['workspace_size'], 16))
        _image[0: SDPUtils.IVT_HEADER_SIZE] = SDPUtils.build_ivt_hdr(
            int(config_data.target_params['workspace_address'], 16), start,
            int(config_data.target_params['workspace_size'], 16))

        alg_size = os.path.getsize(self.get_test_bin_file_name(config_data))  # type: ignore
        self._insert_bin_data(config_data, image=_image,
            filename=self.get_test_bin_file_name(config_data),  # type: ignore
            address=int(config_data.target_params['workspace_address'], 16), size=alg_size)

        self._insert_bin_data(config_data, image=_image, filename=config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH],
            address=int(config_data.sys_params[Const.FW_IMEM_1D_SOURCE], 16),
            size=config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE])
        if config_data.train_2d:
            self._insert_bin_data(config_data, image=_image,
                filename=config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH],
                address=int(config_data.sys_params[Const.FW_IMEM_2D_SOURCE], 16),
                size=config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE])

        self._insert_bin_data(config_data, image=_image, filename=config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH],
            address=int(config_data.sys_params[Const.FW_DMEM_1D_SOURCE], 16),
            size=config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE])
        if config_data.train_2d:
            self._insert_bin_data(config_data, image=_image,
                filename=config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH],
                address=int(config_data.sys_params[Const.FW_DMEM_2D_SOURCE], 16),
                size=config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE])

            if Const.DIAGS_IMEM_FILE_PATH in config_data.fw_bin_info and Const.DIAGS_DMEM_FILE_PATH in \
                    config_data.fw_bin_info:
                self._insert_bin_data(config_data, image=_image,
                    filename=config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH],
                    address=int(config_data.sys_params[Const.DIAGS_IMEM_SOURCE], 16),
                    size=config_data.sys_params[Const.DIAGS_IMEM_SIZE])
                self._insert_bin_data(config_data, image=_image,
                    filename=config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH],
                    address=int(config_data.sys_params[Const.DIAGS_DMEM_SOURCE], 16),
                    size=config_data.sys_params[Const.DIAGS_DMEM_SIZE])

        self._insert_bin_data(config_data, image=_image, filename=config_data.target_params['dcd_file'],
            address=int(config_data.target_params['dcd_addr'], 16), size=0)
        return _image

    def build_image_v2(self, config_data: ConfigData):  # type: ignore
        """Build image to download for mx93 (without using ahab container spsdk capability).

        @param config_data: processor config data
        @return: bytearray containing the image
        """
        # constants
        IVT_OFFSET = 0x0  # ivt header starts at 0
        NUM_IMAGES = 0x01
        HEADER_IMG_ARRAY_OFFSET = 0x10
        IMG_ARRAY_ENTRY_SIZE = 128

        IVT_VERSION_B0 = 0x00
        IVT_HEADER_TAG_B0 = 0x87
        IVT_HEADER_SW_VERSION_B0 = 0x00
        CONTAINER_FUSE_DEFAULT = 0x00
        CONTAINER_FLAGS_DEFAULT = 0x10
        IMG_FLAG_HASH_SHA256 = 0x000
        CORE_ULP_CA35 = 2
        BOOT_IMG_FLAGS_CORE_SHIFT = 0x04
        IMG_TYPE_EXEC = 0x03
        IMG_META = 0

        SIG_HEADER_SIZE = 16
        SIG_HEADER_TAG = 0x90

        HEADER_SIZE = Const.IMX9_APP_OFFSET
        HEADER_OFFSET = 0
        MX93_DDR_BINARY_LEN = 0x20000

        # (offset, size) of ivt header fields
        ivt_header = {'version': (0, 1), 'length': (1, 2), 'tag': (3, 1), 'flags': (4, 4), 'sw_version': (8, 2),
                      'fuse_version': (10, 1), 'num_images': (11, 1), 'sig_blk_offset': (12, 2), 'img': (16, -1)}
        # we use a single image; we'll not use the size info from this dictionary

        sig_header = {'length': (1, 2), 'tag': (3, 1)}

        img_header = {'offset': (0, 4), 'size': (4, 4), 'dst': (8, 8), 'entry': (16, 8), 'hab_flags': (24, 4),
            'meta': (28, 4), 'hash': (32, 32)}

        _image = bytearray(0x100000)  # initialize image

        # ivt header
        (ivt_ver_off, ivt_ver_sz) = ivt_header['version']
        ivt_ver_off += IVT_OFFSET
        _image[ivt_ver_off: ivt_ver_off + ivt_ver_sz] = IVT_VERSION_B0.to_bytes(ivt_ver_sz, byteorder='little')

        (ivt_tag_off, ivt_tag_sz) = ivt_header['tag']
        ivt_tag_off += IVT_OFFSET
        _image[ivt_tag_off: ivt_tag_off + ivt_tag_sz] = IVT_HEADER_TAG_B0.to_bytes(ivt_tag_sz, byteorder='little')

        (ivt_sw_ver_off, ivt_sw_ver_sz) = ivt_header['sw_version']
        ivt_sw_ver_off += IVT_OFFSET
        _image[ivt_sw_ver_off: ivt_sw_ver_off + ivt_sw_ver_sz] = IVT_HEADER_SW_VERSION_B0.to_bytes(ivt_sw_ver_sz,
            byteorder='little')

        (ivt_fuse_ver_off, ivt_fuse_ver_sz) = ivt_header['fuse_version']
        ivt_fuse_ver_off += IVT_OFFSET
        _image[ivt_fuse_ver_off: ivt_fuse_ver_off + ivt_fuse_ver_sz] = CONTAINER_FUSE_DEFAULT.to_bytes(ivt_fuse_ver_sz,
            byteorder='little')

        (ivt_num_img_off, ivt_num_img_sz) = ivt_header['num_images']
        ivt_num_img_off += IVT_OFFSET
        _image[ivt_num_img_off: ivt_num_img_off + ivt_num_img_sz] = NUM_IMAGES.to_bytes(ivt_num_img_sz,
            byteorder='little')

        (ivt_sig_blk_off, ivt_sig_blk_sz) = ivt_header['sig_blk_offset']
        ivt_sig_blk_off += IVT_OFFSET
        _image[ivt_sig_blk_off: ivt_sig_blk_off + ivt_sig_blk_sz] = (
                    HEADER_IMG_ARRAY_OFFSET + NUM_IMAGES * IMG_ARRAY_ENTRY_SIZE).to_bytes(ivt_sig_blk_sz,
            byteorder='little')

        (ivt_flags_off, ivt_flags_sz) = ivt_header['flags']
        ivt_flags_off += IVT_OFFSET
        _image[ivt_flags_off: ivt_flags_off + ivt_flags_sz] = CONTAINER_FLAGS_DEFAULT.to_bytes(ivt_flags_sz,
            byteorder='little')

        (ivt_length_off, ivt_length_sz) = ivt_header['length']
        ivt_length_off += IVT_OFFSET
        ivt_header_length = HEADER_IMG_ARRAY_OFFSET + NUM_IMAGES * IMG_ARRAY_ENTRY_SIZE + SIG_HEADER_SIZE
        _image[ivt_length_off: ivt_length_off + ivt_length_sz] = ivt_header_length.to_bytes(ivt_length_sz,
            byteorder='little')

        # sig block header
        sig_header_offset = IVT_OFFSET + ivt_header_length - HEADER_IMG_ARRAY_OFFSET

        (sig_tag_off, sig_tag_sz) = sig_header['tag']
        sig_tag_off += sig_header_offset
        _image[sig_tag_off: sig_tag_off + sig_tag_sz] = SIG_HEADER_TAG.to_bytes(sig_tag_sz, byteorder='little')

        (sig_len_off, sig_len_sz) = sig_header['length']
        sig_len_off += sig_header_offset
        _image[sig_len_off: sig_len_off + sig_len_sz] = SIG_HEADER_SIZE.to_bytes(sig_len_sz, byteorder='little')

        # app
        bin_offset = Const.IMX9_APP_OFFSET
        bin_data, bin_size = get_bin_data(self.get_test_bin_file_name(config_data))  # type: ignore
        _image[bin_offset: bin_offset + bin_size] = bin_data
        config_data.target_params['workspace_address'] = hex(Const.IMX9_OCRAM_START_ADDRESS + bin_offset)
        config_data.target_params['workspace_size'] = hex(bin_size)

        # fw
        ext_bin_offset = crt_ext_bin_offset = bin_offset + MX93_DDR_BINARY_LEN
        ext_bin_size = 0

        quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        phy_init_options = Options.get_instance().get_snps_phy_init_options()
        skip_training = phy_init_options.skip_training() and (not quick_boot)
        if not skip_training:
            # imem
            imem_1d_data, imem_1d_size = get_bin_data(config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH])
            _image[crt_ext_bin_offset: crt_ext_bin_offset + imem_1d_size] = imem_1d_data
            config_data.sys_params[Const.FW_IMEM_1D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS
                                                                  + crt_ext_bin_offset - HEADER_SIZE)
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            ext_bin_size += imem_1d_size
            crt_ext_bin_offset += imem_1d_size

            train_2d = config_data.train_2d and phy_init_options.execute_full_training() and (not quick_boot)
            if train_2d:
                imem_2d_data, imem_2d_size = get_bin_data(config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH])
                _image[crt_ext_bin_offset: crt_ext_bin_offset + imem_2d_size] = imem_2d_data
                config_data.sys_params[Const.FW_IMEM_2D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS
                                                                      + crt_ext_bin_offset - HEADER_SIZE)
                config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
                ext_bin_size += imem_2d_size
                crt_ext_bin_offset += imem_2d_size
            # dmem
            dmem_1d_data, dmem_1d_size = get_bin_data(config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH])
            _image[crt_ext_bin_offset: crt_ext_bin_offset + dmem_1d_size] = dmem_1d_data
            config_data.sys_params[Const.FW_DMEM_1D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS
                                                                  + crt_ext_bin_offset - HEADER_SIZE)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            ext_bin_size += dmem_1d_size
            crt_ext_bin_offset += dmem_1d_size

            if train_2d:
                dmem_2d_data, dmem_2d_size = get_bin_data(config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH])
                _image[crt_ext_bin_offset: crt_ext_bin_offset + dmem_2d_size] = dmem_2d_data
                config_data.sys_params[Const.FW_DMEM_2D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS
                                                                      + crt_ext_bin_offset - HEADER_SIZE)
                config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
                ext_bin_size += dmem_2d_size
                crt_ext_bin_offset += dmem_2d_size

                # diag
                if Const.DIAGS_IMEM_FILE_PATH in config_data.fw_bin_info and Const.DIAGS_DMEM_FILE_PATH in \
                        config_data.fw_bin_info:
                    diag_imem_data, diag_imem_size = get_bin_data(config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH])
                    _image[crt_ext_bin_offset: crt_ext_bin_offset + diag_imem_size] = diag_imem_data
                    config_data.sys_params[Const.DIAGS_IMEM_SOURCE] = hex(
                        Const.IMX9_APP_START_ADDRESS + crt_ext_bin_offset - HEADER_SIZE)
                    config_data.sys_params[Const.DIAGS_IMEM_SIZE] = hex(diag_imem_size)
                    ext_bin_size += diag_imem_size
                    crt_ext_bin_offset += diag_imem_size

                    diag_dmem_data, diag_dmem_size = get_bin_data(config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH])
                    _image[crt_ext_bin_offset: crt_ext_bin_offset + diag_dmem_size] = diag_dmem_data
                    config_data.sys_params[Const.DIAGS_DMEM_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS
                                                                          + crt_ext_bin_offset - HEADER_SIZE)
                    config_data.sys_params[Const.DIAGS_DMEM_SIZE] = hex(diag_dmem_size)
                    ext_bin_size += diag_dmem_size
                    crt_ext_bin_offset += diag_dmem_size

        # dcd creation should be delayed until all config_data.sys_params are correctly set
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        processor.create_dcd_bin(config_data)

        ext_bin_size = align(ext_bin_size, Const.ALIGN_TO_1K)
        dcd_offset = ext_bin_offset + ext_bin_size
        dcd_data, dcd_size = get_bin_data(config_data.target_params['dcd_file'])
        _image[dcd_offset: dcd_offset + dcd_size] = dcd_data
        config_data.target_params['dcd_addr'] = hex(Const.IMX9_APP_START_ADDRESS + dcd_offset - HEADER_SIZE)

        # img info
        (ivt_img_off, ivt_img_sz) = ivt_header['img']  # only one image is used
        ivt_img_off += IVT_OFFSET

        (img_off_off, img_off_sz) = img_header['offset']
        img_off_off += ivt_img_off
        _image[img_off_off: img_off_off + img_off_sz] = (bin_offset - HEADER_OFFSET).to_bytes(img_off_sz,
            byteorder='little')

        (img_sz_off, img_sz_sz) = img_header['size']
        img_sz_off += ivt_img_off
        image_size = MX93_DDR_BINARY_LEN + ext_bin_size + dcd_size
        _image[img_sz_off: img_sz_off + img_sz_sz] = image_size.to_bytes(img_sz_sz, byteorder='little')

        (img_flags_off, img_flags_sz) = img_header['hab_flags']
        img_flags_off += ivt_img_off
        _image[img_flags_off: img_flags_off + img_flags_sz] = (IMG_FLAG_HASH_SHA256 |
                (CORE_ULP_CA35 << BOOT_IMG_FLAGS_CORE_SHIFT) | IMG_TYPE_EXEC).to_bytes(img_flags_sz, byteorder='little')

        (img_meta_off, img_meta_sz) = img_header['meta']
        img_meta_off += ivt_img_off
        _image[img_meta_off: img_meta_off + img_meta_sz] = IMG_META.to_bytes(img_meta_sz, byteorder='little')

        _image_hash = get_hash(_image[bin_offset: bin_offset + image_size], algorithm=EnumHashAlgorithm["sha256"])

        (img_hash_off, img_hash_sz) = img_header['hash']
        img_hash_off += ivt_img_off
        _image[img_hash_off: img_hash_off + img_hash_sz] = _image_hash

        (img_dst_off, img_dst_sz) = img_header['dst']
        img_dst_off += ivt_img_off
        _image[img_dst_off: img_dst_off + img_dst_sz] = Const.IMX9_APP_START_ADDRESS.to_bytes(img_dst_sz,
                                                                                              byteorder='little')

        (img_entry_off, img_entry_sz) = img_header['entry']
        img_entry_off += ivt_img_off
        _image[img_entry_off: img_entry_off + img_entry_sz] = Const.IMX9_APP_START_ADDRESS.to_bytes(img_entry_sz,
                                                                                                    byteorder='little')

        # dump image
        if Const.DUMP_IMAGE:
            workspace_dir = Workspace.get_instance().get_location()
            ahab_image_file = os.path.join(workspace_dir, 'non_ahab_final_binary_file.bin')
            write_file(_image[0: HEADER_SIZE + image_size], ahab_image_file, mode="wb")

        return _image[0: HEADER_SIZE + image_size]

    def __generate_ahab_input_image_from_bytearray(self, config_data: ConfigData):  # type: ignore
        """Create image without header ([workspace]\final_binary_file.bin) = input for ahab.

        @param config_data: processor config data
        """
        self.logger.info(f"Build AHAB image for {config_data.soc_name}")

        workspace_dir = Workspace.get_instance().get_location()

        image_size = Const.IMX9_DCD_START_ADDRESS - Const.IMX9_APP_START_ADDRESS  # image size without dcd
        image = bytearray(image_size)

        bin_data, bin_size = get_bin_data(self.get_test_bin_file_name(config_data))  # type: ignore
        image[0: bin_size] = bin_data
        config_data.target_params['workspace_address'] = hex(Const.IMX9_OCRAM_START_ADDRESS + Const.IMX9_APP_OFFSET)
        config_data.target_params['workspace_size'] = hex(bin_size)
        offset = bin_size + (4 * Const.ALIGN_TO_1K)  # determined experimentally that we need a gap between bin and imem

        quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        phy_init_options = Options.get_instance().get_snps_phy_init_options()
        skip_training = phy_init_options.skip_training() and (not quick_boot)
        if not skip_training:
            imem_1d_data, imem_1d_size = get_bin_data(config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH])
            image[offset: offset + imem_1d_size] = imem_1d_data
            config_data.sys_params[Const.FW_IMEM_1D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            offset += imem_1d_size

            train_2d = config_data.train_2d and phy_init_options.execute_full_training() and (not quick_boot)
            if train_2d:
                imem_2d_data, imem_2d_size = get_bin_data(config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH])
                image[offset: offset + imem_2d_size] = imem_2d_data
                config_data.sys_params[Const.FW_IMEM_2D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
                offset += imem_2d_size

            dmem_1d_data, dmem_1d_size = get_bin_data(config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH])
            image[offset: offset + dmem_1d_size] = dmem_1d_data
            config_data.sys_params[Const.FW_DMEM_1D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            offset += dmem_1d_size

            if train_2d:
                dmem_2d_data, dmem_2d_size = get_bin_data(config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH])
                image[offset: offset + dmem_2d_size] = dmem_2d_data
                config_data.sys_params[Const.FW_DMEM_2D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
                offset += dmem_2d_size

                if Const.DIAGS_IMEM_FILE_PATH in config_data.fw_bin_info and Const.DIAGS_DMEM_FILE_PATH in \
                        config_data.fw_bin_info:
                    diag_imem_data, diag_imem_size = get_bin_data(config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH])
                    image[offset: offset + diag_imem_size] = diag_imem_data
                    config_data.sys_params[Const.DIAGS_IMEM_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                    config_data.sys_params[Const.DIAGS_IMEM_SIZE] = hex(diag_imem_size)
                    offset += diag_imem_size

                    diag_dmem_data, diag_dmem_size = get_bin_data(config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH])
                    image[offset: offset + diag_dmem_size] = diag_dmem_data
                    config_data.sys_params[Const.DIAGS_DMEM_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                    config_data.sys_params[Const.DIAGS_DMEM_SIZE] = hex(diag_dmem_size)
                    offset += diag_dmem_size

        # dcd creation should be delayed until all config_data.sys_params are correctly set
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        processor.create_dcd_bin(config_data)

        dcd_data, dcd_size = get_bin_data(config_data.target_params['dcd_file'])
        image.extend(dcd_data)
        config_data.target_params['dcd_addr'] = hex(Const.IMX9_DCD_START_ADDRESS)

        # dump image without header; it's input for AHABImage
        bin_file = os.path.join(workspace_dir, Const.AHAB_BIN_INPUT_NAME)
        write_file(image, bin_file, mode="wb")

    def __create_ahab_region_container(self, name: str, file_path: str, offset: int) -> CommentedMap:
        """Create ahab merge region container.

        @param name: region name
        @param file_path: file path to be merged
        @param offset: offset where the file data will be merged
        @return: commented map that corresponds to the region to be merged
        """
        workspace_dir = Workspace.get_instance().get_location()
        tmp_file = os.path.join(workspace_dir, os.path.basename(file_path))
        copy_file = True
        if os.path.exists(tmp_file):
            # if a different file is already present in workspace it must be deleted
            # to make sure the image generator will use updated data
            if not filecmp.cmp(file_path, tmp_file):
                os.remove(tmp_file)
            else:
                copy_file = False
        if copy_file:
            shutil.copy(file_path, tmp_file)

        region = CommentedMap()
        region_map = CommentedMap()
        region_map["name"] = name
        region_map["path"] = os.path.basename(tmp_file)
        region_map["offset"] = offset
        region["binary_file"] = region_map
        return region

    def __generate_ahab_input_image_using_ahab_merge_config(self, config_data: ConfigData):  # type: ignore
        """Create image without header ([workspace]\final_binary_file.bin) = input for ahab.

        @param config_data: processor config data
        """
        merge_config_map = CommentedMap()
        merge_config_map.yaml_set_start_comment(f"AHAB merge config from "
                                                f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}.")
        merge_config_map["family"] = SDPSComm.get_spsdk_device(config_data.soc_name)
        merge_config_map["pattern"] = 0
        merge_config_regions = CommentedSeq()

        bin_file_path = self.get_test_bin_file_name(config_data)  # type: ignore
        bin_data, bin_size = get_bin_data(bin_file_path)
        config_data.target_params['workspace_address'] = hex(Const.IMX9_OCRAM_START_ADDRESS + Const.IMX9_APP_OFFSET)
        config_data.target_params['workspace_size'] = hex(bin_size)
        offset = 0x0
        merge_config_regions.append(self.__create_ahab_region_container("Application", bin_file_path, offset))
        offset += bin_size + (4 * Const.ALIGN_TO_1K)

        quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        phy_init_options = Options.get_instance().get_snps_phy_init_options()
        skip_training = phy_init_options.skip_training() and (not quick_boot)
        if not skip_training:
            imem_1d_file_path = config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH]
            imem_1d_data, imem_1d_size = get_bin_data(imem_1d_file_path)
            config_data.sys_params[Const.FW_IMEM_1D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            merge_config_regions.append(self.__create_ahab_region_container("Imem1D", imem_1d_file_path, offset))
            offset += align(imem_1d_size, 16 * Const.ALIGN_TO_1K)

            train_2d = config_data.train_2d and phy_init_options.execute_full_training() and (not quick_boot)
            if train_2d:
                imem_2d_file_path = config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH]
                imem_2d_data, imem_2d_size = get_bin_data(imem_2d_file_path)
                config_data.sys_params[Const.FW_IMEM_2D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
                merge_config_regions.append(self.__create_ahab_region_container("Imem2D", imem_2d_file_path, offset))
                offset += imem_2d_size

            dmem_1d_file_path = config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH]
            dmem_1d_data, dmem_1d_size = get_bin_data(dmem_1d_file_path)
            config_data.sys_params[Const.FW_DMEM_1D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            merge_config_regions.append(self.__create_ahab_region_container("Dmem1D", dmem_1d_file_path, offset))
            offset += align(dmem_1d_size, 16 * Const.ALIGN_TO_1K)

            if train_2d:
                dmem_2d_file_path = config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH]
                dmem_2d_data, dmem_2d_size = get_bin_data(dmem_2d_file_path)
                config_data.sys_params[Const.FW_DMEM_2D_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
                merge_config_regions.append(self.__create_ahab_region_container("Dmem2D", dmem_2d_file_path, offset))
                offset += dmem_2d_size

                if Const.DIAGS_IMEM_FILE_PATH in config_data.fw_bin_info and Const.DIAGS_DMEM_FILE_PATH in \
                        config_data.fw_bin_info:
                    diag_imem_file_path = config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH]
                    diag_imem_data, diag_imem_size = get_bin_data(diag_imem_file_path)
                    config_data.sys_params[Const.DIAGS_IMEM_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                    config_data.sys_params[Const.DIAGS_IMEM_SIZE] = hex(diag_imem_size)
                    merge_config_regions.append(self.__create_ahab_region_container("DiagImem",
                                                                                    diag_imem_file_path, offset))
                    offset += diag_imem_size

                    diag_dmem_file_path = config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH]
                    diag_dmem_data, diag_dmem_size = get_bin_data(diag_dmem_file_path)
                    config_data.sys_params[Const.DIAGS_DMEM_SOURCE] = hex(Const.IMX9_APP_START_ADDRESS + offset)
                    config_data.sys_params[Const.DIAGS_DMEM_SIZE] = hex(diag_dmem_size)
                    merge_config_regions.append(self.__create_ahab_region_container("DiagDmem",
                                                                                    diag_dmem_file_path, offset))
                    offset += diag_dmem_size

        # dcd creation should be delayed until all config_data.sys_params are correctly set
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        processor.create_dcd_bin(config_data)

        offset = Const.IMX9_DCD_START_ADDRESS - Const.IMX9_APP_START_ADDRESS
        config_data.target_params['dcd_addr'] = hex(Const.IMX9_DCD_START_ADDRESS)
        merge_config_regions.append(self.__create_ahab_region_container("Dcd",
                                                                        config_data.target_params['dcd_file'], offset))

        merge_config_map["regions"] = merge_config_regions

        # generate merge yaml
        workspace_dir = Workspace.get_instance().get_location()
        merge_config_file = os.path.join(workspace_dir, Const.AHAB_MERGE_CONFIG_NAME)
        with open(merge_config_file, 'wt') as f:
            yaml = YAML()
            yaml.dump(merge_config_map, f)
        image = BinaryImage.load_from_config(Config.create_from_file(merge_config_file))
        try:
            image.validate()
        except SPSDKError as exc:
            raise SPSDKError("Image validation failed") from exc
        image_data = image.export()
        final_bin_file = os.path.join(workspace_dir, Const.AHAB_BIN_INPUT_NAME)
        write_file(image_data, final_bin_file, mode="wb")

    def __generate_ahab_image(self, config_data: ConfigData, ahab_file_path: str,  # type: ignore
                              use_ahab_file_copy: bool = True):
        """Generate AHAB image.

        @param config_data: processor config data
        @param ahab_file_path: absolute path to the ahab config file
        @param use_ahab_file_copy: copy the ahab config file to workspace
        @return: bytearray containing the image with header
        """
        workspace_dir = Workspace.get_instance().get_location()
        if use_ahab_file_copy:
            tmp_ahab_file = os.path.join(workspace_dir, os.path.basename(ahab_file_path))
            if not os.path.exists(tmp_ahab_file):
                shutil.copy(ahab_file_path, tmp_ahab_file)
            # make sure that temp config file is used
            ahab_file_path = tmp_ahab_file

        # Update AHAB configuration data according to processor configuration data and Options if needed.
        self.update_ahab_configuration_from_file(config_data, ahab_file_path)

        # Load updated AHAB configuration data.
        ahab_cnt = AHABImage.load_from_config(Config.create_from_file(ahab_file_path))
        ahab_cnt.update_fields()
        ahab_data = ahab_cnt.export()

        # Generate ahab image; total image size should be aligned to 16K
        img_size = len(ahab_data)
        ahab_image = bytearray(img_size)
        ahab_image[0:len(ahab_data)] = ahab_data
        if Const.DUMP_IMAGE:
            ahab_image_file = os.path.join(workspace_dir, Const.AHAB_BIN_OUTPUT_NAME)
            write_file(ahab_image, ahab_image_file, mode="wb")

        return ahab_image

    def __create_ahab_image_container(self, file_path: str, load_addr: str,
                            entry_addr: str, core: str, type: str,
                            hash: str, cpu_id: int) -> CommentedMap:
        """Create ahab image container.

        @param file_path: file path to be added
        @param load_addr: image load address
        @param entry_addr: image entry point
        @param core: boot_core
        @param type: image type
        @param hash: hash type
        @param cpu_id: start cpu id
        @return: commented map that corresponds to the image
        """
        workspace_dir = Workspace.get_instance().get_location()
        tmp_file = os.path.join(workspace_dir, os.path.basename(file_path))
        if not os.path.exists(tmp_file):
            shutil.copy(file_path, tmp_file)

        image_map = CommentedMap()
        image_map["image_path"] = os.path.basename(file_path)
        image_map["load_address"] = load_addr
        image_map["entry_point"] = entry_addr
        image_map["image_type"] = type
        image_map["core_id"] = core
        image_map["is_encrypted"] = False
        image_map["boot_flags"] = 0
        image_map["meta_data_start_cpu_id"] = cpu_id
        image_map["meta_data_mu_cpu_id"] = 0
        image_map["meta_data_start_partition_id"] = 0
        image_map["hash_type"] = hash
        return image_map

    @staticmethod
    def update_ahab_configuration_from_file(config_data: ConfigData, ahab_config_file_path: str) -> None:
        """Update AHAB configuration data from file according to processor configuration data and Options.

        @param config_data: Configuration data.
        @param ahab_config_file_path: Absolute path of AHAB configuration data file.
        """
        if ConfigData.DEVICES_INFO[config_data.soc_name].is_imx9():
            workspace_dir = Workspace.get_instance().get_location()
            # Get sign DDR bootable image options.
            sign_image_options = Options.get_instance().get_bootable_image_options()
            sign_bootable_image = sign_image_options.get_sign_bootable_image()
            if sign_bootable_image:
                # Get private SRK key.
                private_srk_key = ''
                private_keys_dir_path = Workspace.get_instance().get_private_key_location()
                for file in os.listdir(private_keys_dir_path):
                    private_srk_key = file
                    src_srk_file = os.path.join(private_keys_dir_path, file)
                    dst_srk_file = os.path.join(workspace_dir, file)
                    shutil.copy(src_srk_file, dst_srk_file)
                    break
                if len(os.listdir(private_keys_dir_path)) > 1:
                    SDPSProcessor.logger.warning(f"Found more than 1 private SRK key, {private_srk_key} is used!")

                # Get public SRK keys.
                public_srk_keys = []
                public_keys: List[PublicKey] = []
                public_keys_dir_path = Workspace.get_instance().get_public_keys_location()
                for file in os.listdir(public_keys_dir_path):
                    public_srk_keys.append(file)
                    public_keys.append(PublicKey.load(os.path.join(public_keys_dir_path, file)))
                    src_srk_file = os.path.join(public_keys_dir_path, file)
                    dst_srk_file = os.path.join(workspace_dir, file)
                    shutil.copy(src_srk_file, dst_srk_file)

                # Find id of SRK public key matching private SRK key.
                # Throws SPSDKError and did not catch because it has useful verbose error message.
                signature_provider = PlainFileSP(os.path.join(private_keys_dir_path, private_srk_key))
                # Throws SPSDKValueError and did not catch because it has useful verbose error message.
                used_srk_id = get_matching_key_id(public_keys, signature_provider)

                # Load default AHAB configuration data and update it.
                ahab_config_data = load_configuration(ahab_config_file_path)
                if SpsdkYamlField.CONTAINERS in ahab_config_data:
                    containers = ahab_config_data[SpsdkYamlField.CONTAINERS]
                    for container in containers:
                        if SpsdkYamlField.CONTAINER in container:
                            sign_container = container[SpsdkYamlField.CONTAINER]
                            sign_container[SpsdkYamlField.CONTAINER_SRK_SET] = SpsdkYamlField.CONTAINER_SRK_SET_OEM_VAL
                            sign_container[SpsdkYamlField.CONTAINER_USED_SRK_ID] = used_srk_id
                            sign_container[SpsdkYamlField.CONTAINER_SRK_REVOKE_MSK] = 0
                            sign_container[SpsdkYamlField.CONTAINER_SIGNING_KEY] = private_srk_key
                            sign_container[SpsdkYamlField.CONTAINER_SRK_TABLE] = \
                                {SpsdkYamlField.CONTAINER_SRK_TABLE_ARRAY: public_srk_keys}

                # Save updated AHAB configuration data and overwrite AHAB initial configuration data file.
                commented_ahab_config_data = CommentedConfig(
                                main_title=(f"AHAB recreated configuration from "
                                            f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}."),
                                schemas=AHABImage.get_validation_schemas(
                                            FamilyRevision(SDPSComm.get_spsdk_device(config_data.soc_name)))).\
                                            get_config(ahab_config_data)
                write_file(commented_ahab_config_data, ahab_config_file_path)

    def generate_ahab_config_file(self, config_data: ConfigData) -> str:
        """Create AHAB configuration file.

        @param config_data: processor config data
        @return: path to ahab configuration file
        """
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        workspace_dir = Workspace.get_instance().get_location()

        ahab_config_map = CommentedMap()
        ahab_config_map["family"] = SDPSComm.get_spsdk_device(config_data.soc_name)
        revision = processor.processor_info.get_revision()
        ahab_config_map["revision"] = revision if revision is not None else "a0"
        ahab_config_map["target_memory"] = "serial_downloader"
        ahab_config_map["output"] = Const.AHAB_BIN_OUTPUT_NAME
        ahab_config_containers = CommentedSeq()

        if config_data.soc_name in ['MIMX943', 'MIMX95_B0']:
            ahab_image_map = CommentedMap()
            ahab_image_file_path = processor.get_ahab_img_file_name(config_data)
            tmp_ahab_image_file = os.path.join(workspace_dir, os.path.basename(ahab_image_file_path))
            shutil.copy(ahab_image_file_path, tmp_ahab_image_file)  # copy ahab image to workspace
            image_map = CommentedMap()
            image_map["path"] = os.path.basename(ahab_image_file_path)
            ahab_image_map["binary_container"] = image_map
            ahab_config_containers.append(ahab_image_map)

        compress = config_data.compress if config_data.compress is not None else False
        opaque_custom_oei = self._uses_opaque_custom_oei(config_data)
        self.logger.debug("Compression flag in SDPS image builder: %s", compress)

        ahab_container_map = CommentedMap()
        container_map = CommentedMap()
        container_map["srk_set"] = "none"
        container_map["fuse_version"] = 0
        container_map["sw_version"] = 0
        container_map["decompression"] = False
        container_images = CommentedSeq()
        hash = "sha384" if config_data.soc_name in ['MIMX943', 'MIMX95', 'MIMX95_B0'] else "sha256"

        quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        phy_init_options = Options.get_instance().get_snps_phy_init_options()
        skip_training = (phy_init_options.skip_training() and (not quick_boot)) or \
                        (Const.PARAM_SERDES_SKIP_DDR_PHY in config_data.params[Const.PARAM_S_BASIC])
        train_2d = config_data.train_2d and phy_init_options.execute_full_training() and (not quick_boot)

        # utils
        align_data_sections = True
        boot_core_CM33 = is_mx95 = processor.processor_info.has_sm()
        align_to_value = Const.ALIGN_TO_1K if is_mx95 else (16 * Const.ALIGN_TO_1K)
        boot_core = "cortex-m33" if boot_core_CM33 else "cortex-a55"

        # create aligned bin for final image
        bin_file_path = self._get_opaque_custom_oei_path(config_data) if opaque_custom_oei else \
            self.get_test_bin_file_name(config_data)  # type: ignore
        # bin_file_path = self.get_test_bin_file_name(config_data)  # type: ignore
        bin_data, bin_size = get_bin_data(bin_file_path)
        aligned_bin_size = align(bin_size, align_to_value)
        bin_data_with_padding = bytearray(aligned_bin_size)
        bin_data_with_padding[0:bin_size] = bin_data
        application_file_path = os.path.join(workspace_dir, os.path.basename(bin_file_path))
        write_file(bin_data_with_padding, application_file_path, mode="wb")

        # add data sections
        imem_1d_size = 0
        imem_2d_size = 0
        dmem_1d_size = 0
        dmem_2d_size = 0
        fw_size = 0

        diag_imem_size = 0
        diag_dmem_size = 0
        diags_fw_size = 0

        compressed_imem_1d_size = 0
        compressed_imem_2d_size = 0
        compressed_dmem_1d_size = 0
        compressed_dmem_2d_size = 0

        skip_training = skip_training or config_data.params['app'].get('check_target_is_responsive', False)
        if not skip_training and not compress:
            f = open("fw_debug.txt", "w", encoding='utf+8')
            f.write(f'IMEM: {fw_size}\n')
    
            imem_1d_file_path = config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH]
            imem_1d_data, imem_1d_size = get_bin_data(imem_1d_file_path)
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            aligned_imem_1d_size = align(imem_1d_size, align_to_value)
            fw_size += aligned_imem_1d_size if align_data_sections else imem_1d_size

            if train_2d:
                f.write(f'IMEM2D: {fw_size}\n')
                imem_2d_file_path = config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH]
                imem_2d_data, imem_2d_size = get_bin_data(imem_2d_file_path)
                config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
                aligned_imem_2d_size = align(imem_2d_size, align_to_value)
                fw_size += aligned_imem_2d_size if align_data_sections else imem_2d_size

            f.write(f'DMEM: {fw_size}\n')
            dmem_1d_file_path = config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH]
            dmem_1d_data, dmem_1d_size = get_bin_data(dmem_1d_file_path)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            aligned_dmem_1d_size = align(dmem_1d_size, align_to_value)
            fw_size += aligned_dmem_1d_size if align_data_sections else dmem_1d_size

            if train_2d:
                f.write(f'DMEM2D: {fw_size}\n')
                dmem_2d_file_path = config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH]
                dmem_2d_data, dmem_2d_size = get_bin_data(dmem_2d_file_path)
                config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
                aligned_dmem_2d_size = align(dmem_2d_size, align_to_value)
                fw_size += aligned_dmem_2d_size if align_data_sections else dmem_2d_size

            if (train_2d or config_data.is_phy_v3(config_data.snps_phy_info)) and \
                    Const.DIAGS_IMEM_FILE_PATH in config_data.fw_bin_info and \
                    Const.DIAGS_DMEM_FILE_PATH in config_data.fw_bin_info:
                diag_imem_file_path = config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH]
                diag_imem_data, diag_imem_size = get_bin_data(diag_imem_file_path)
                aligned_diag_imem_size = align(diag_imem_size, align_to_value)
                if config_data.soc_name in ['MIMX943']:
                    diags_fw_size += aligned_diag_imem_size if align_data_sections else diag_imem_size
                else:
                    f.write(f'DIAGS_IMEM: {fw_size}\n')
                    fw_size += aligned_diag_imem_size if align_data_sections else diag_imem_size

                diag_dmem_file_path = config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH]
                diag_dmem_data, diag_dmem_size = get_bin_data(diag_dmem_file_path)
                aligned_diag_dmem_size = align(diag_dmem_size, align_to_value)
                if config_data.soc_name in ['MIMX943']:
                    diags_fw_size += aligned_diag_dmem_size if align_data_sections else diag_dmem_size
                else:
                    f.write(f'DIAGS_DMEM: {fw_size}\n')
                    fw_size += aligned_diag_dmem_size if align_data_sections else diag_dmem_size

        if not skip_training and compress:
            imem_1d_data, imem_1d_size = get_bin_data(
                config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH])
            imem_2d_data, imem_2d_size = (b'', 0)
            if train_2d:
                imem_2d_data, imem_2d_size = get_bin_data(
                    config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH])
            dmem_1d_data, dmem_1d_size = get_bin_data(
                config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH])
            dmem_2d_data, dmem_2d_size = (b'', 0)
            if train_2d:
                dmem_2d_data, dmem_2d_size = get_bin_data(
                    config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH])

            imem_data = imem_1d_data + imem_2d_data
            dmem_data = dmem_1d_data + dmem_2d_data
            compressed_firmware = build_chunked_ddr_firmware(imem_data, dmem_data)
            fw_data = compressed_firmware.data
            fw_file_path = os.path.join(workspace_dir, "fw.bin")
            write_file(fw_data, fw_file_path, mode="wb")
            config_data.sys_params[Const.FW_IMEM_1D_SOURCE] = hex(Const.IMX95_FW_START_ADDRESS_NS_NSRAM)
            config_data.sys_params[Const.FW_DMEM_1D_SOURCE] = hex(Const.IMX95_FW_START_ADDRESS_NS_NSRAM)

            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
            config_data.sys_params[Const.COMPRESS_FW_IMEM_1D_SIZE] = hex(compressed_firmware.imem_compressed_size)
            config_data.sys_params[Const.COMPRESS_FW_IMEM_2D_SIZE] = hex(0)
            config_data.sys_params[Const.COMPRESS_FW_DMEM_1D_SIZE] = hex(compressed_firmware.dmem_compressed_size)
            config_data.sys_params[Const.COMPRESS_FW_DMEM_2D_SIZE] = hex(0)
            container_images.append(
                self.__create_ahab_image_container(fw_file_path, hex(Const.IMX95_FW_START_ADDRESS_NS_NSRAM),
                    hex(Const.IMX95_FW_START_ADDRESS_NS_NSRAM), boot_core, "data", hash, 0))

        # compute fw address
        if is_mx95:
            # IMX95
            if boot_core_CM33:
                fw_load_addr = Const.IMX95_FW_START_ADDRESS_NS_NSRAM
            else:  # A55
                fw_load_addr = Const.IMX95_FW_START_ADDRESS_NS_TCMC
        else:
            # IMX91, IMX93
            fw_load_addr = Const.IMX9_APP_START_ADDRESS + aligned_bin_size

        if fw_size > 0 and not compress:
            fw_data = bytearray(fw_size)
            offset = 0

            config_data.sys_params[Const.FW_IMEM_1D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            if imem_1d_size > 0:
                fw_data[offset: offset + imem_1d_size] = imem_1d_data
                offset += aligned_imem_1d_size if align_data_sections else imem_1d_size

            config_data.sys_params[Const.FW_IMEM_2D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
            if imem_2d_size > 0:
                fw_data[offset: offset + imem_2d_size] = imem_2d_data
                offset += aligned_imem_2d_size if align_data_sections else imem_2d_size

            config_data.sys_params[Const.FW_DMEM_1D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            if dmem_1d_size > 0:
                fw_data[offset: offset + dmem_1d_size] = dmem_1d_data
                offset += aligned_dmem_1d_size if align_data_sections else dmem_1d_size

            config_data.sys_params[Const.FW_DMEM_2D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
            if dmem_2d_size > 0:
                fw_data[offset: offset + dmem_2d_size] = dmem_2d_data
                offset += aligned_dmem_2d_size if align_data_sections else dmem_2d_size

            if config_data.soc_name not in ['MIMX943']:
                config_data.sys_params[Const.DIAGS_IMEM_SOURCE] = hex(fw_load_addr + offset)
                config_data.sys_params[Const.DIAGS_IMEM_SIZE] = hex(diag_imem_size)
                if diag_imem_size > 0:
                    fw_data[offset: offset + diag_imem_size] = diag_imem_data
                    offset += aligned_diag_imem_size if align_data_sections else diag_imem_size

                config_data.sys_params[Const.DIAGS_DMEM_SOURCE] = hex(fw_load_addr + offset)
                config_data.sys_params[Const.DIAGS_DMEM_SIZE] = hex(diag_dmem_size)
                if diag_dmem_size > 0:
                    fw_data[offset: offset + diag_dmem_size] = diag_dmem_data
                    offset += aligned_diag_dmem_size if align_data_sections else diag_dmem_size

            fw_file_name = "fw.bin"
            fw_file_path = os.path.join(workspace_dir, fw_file_name)
            write_file(fw_data, fw_file_path, mode="wb")

            # add fw data to AHAB container
            container_images.append(
                self.__create_ahab_image_container(fw_file_path, hex(fw_load_addr),
                    hex(fw_load_addr), boot_core, "data", hash, 0))

        if diags_fw_size > 0:
            fw_data = bytearray(diags_fw_size)
            offset = 0

            diags_fw_load_addr = Const.IMX943_DIAGS_FW_START_ADDRESS_NS_OCRAM

            config_data.sys_params[Const.DIAGS_IMEM_SOURCE] = hex(diags_fw_load_addr + offset)
            config_data.sys_params[Const.DIAGS_IMEM_SIZE] = hex(diag_imem_size)
            if diag_imem_size > 0:
                fw_data[offset: offset + diag_imem_size] = diag_imem_data
                offset += aligned_diag_imem_size if align_data_sections else diag_imem_size

            config_data.sys_params[Const.DIAGS_DMEM_SOURCE] = hex(diags_fw_load_addr + offset)
            config_data.sys_params[Const.DIAGS_DMEM_SIZE] = hex(diag_dmem_size)
            if diag_dmem_size > 0:
                fw_data[offset: offset + diag_dmem_size] = diag_dmem_data
                offset += aligned_diag_dmem_size if align_data_sections else diag_dmem_size

            diags_fw_file_name = "diags_fw.bin"
            diags_fw_file_path = os.path.join(workspace_dir, diags_fw_file_name)
            write_file(fw_data, diags_fw_file_path, mode="wb")

            # add fw data to AHAB container
            container_images.append(
                self.__create_ahab_image_container(diags_fw_file_path, hex(diags_fw_load_addr),
                    hex(diags_fw_load_addr), boot_core, "data", hash, 0))

        # dcd creation should be delayed until all config_data.sys_params are correctly set
        processor.create_dcd_bin(config_data)
        # compute dcd address
        if is_mx95:
            # IMX95
            if boot_core_CM33:
                if config_data.soc_name == 'MIMX943':
                    dcd_load_address = hex(Const.IMX943_DCD_START_ADDRESS_NS_NSRAM)
                else:
                    dcd_load_address = hex(Const.IMX95_DCD_START_ADDRESS_NS_NSRAM)
            else:  # A55
                dcd_load_address = hex(Const.IMX95_DCD_START_ADDRESS_NS_TCMS)
        else:
            # IMX91, IMX93
            dcd_load_address = hex(Const.IMX9_DCD_START_ADDRESS)
        config_data.target_params['dcd_addr'] = dcd_load_address

        # add dcd to AHAB container
        container_images.append(
            self.__create_ahab_image_container(config_data.target_params['dcd_file'],
                dcd_load_address, dcd_load_address, boot_core, "data", hash, 0))

        # add executable to AHAB container
        app_load_addr = hex(Const.IMX95_APP_START_ADDRESS_S_TCMC) if boot_core_CM33 else \
                            hex(Const.IMX9_APP_START_ADDRESS)
        app_entry_addr = hex(Const.IMX95_APP_START_ADDRESS_S_TCMC + 1) if opaque_custom_oei else \
            (hex(config_data.target_params['start_addr']) if boot_core_CM33 else app_load_addr)
        container_images.append(self.__create_ahab_image_container(application_file_path,
             app_load_addr, app_entry_addr, boot_core, "oei" if boot_core_CM33 else "executable", hash, 0))

        # finalize AHAB container initialization
        container_map["images"] = container_images
        ahab_container_map["container"] = container_map
        ahab_config_containers.append(ahab_container_map)
        ahab_config_map["containers"] = ahab_config_containers

        # generate AHAB config yaml
        workspace_dir = Workspace.get_instance().get_location()
        ahab_config_file = os.path.join(workspace_dir, Const.AHAB_CONFIG_NAME)
        commented_ahab_config_data = CommentedConfig(main_title=(f"AHAB created configuration from "
            f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}."),
            schemas=AHABImage.get_validation_schemas(
                FamilyRevision(SDPSComm.get_spsdk_device(config_data.soc_name)))).get_config(ahab_config_map)
        write_file(commented_ahab_config_data, ahab_config_file)

        return ahab_config_file

    def generate_ahab_config_file_for_system_manager(self, config_data: ConfigData) -> str:
        """Create AHAB configuration file.

        @param config_data: processor config data
        @return: path to ahab configuration file
        """
        # utils
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        workspace_dir = Workspace.get_instance().get_location()
        align_data_sections = True
        is_mx95 = processor.processor_info.has_sm()
        align_to_value = Const.ALIGN_TO_1K if is_mx95 else (16 * Const.ALIGN_TO_1K)

        ahab_config_map = CommentedMap()
        ahab_config_map["family"] = SDPSComm.get_spsdk_device(config_data.soc_name)
        revision = processor.processor_info.get_revision()
        ahab_config_map["revision"] = revision if revision is not None else "a0"
        ahab_config_map["target_memory"] = "serial_downloader"
        ahab_config_map["output"] = Const.AHAB_BIN_OUTPUT_NAME
        ahab_config_containers = CommentedSeq()

        ahab_image_map = CommentedMap()
        ahab_image_file_path = processor.get_ahab_img_file_name(config_data)
        tmp_ahab_image_file = os.path.join(workspace_dir, os.path.basename(ahab_image_file_path))
        shutil.copy(ahab_image_file_path, tmp_ahab_image_file)  # copy ahab image to workspace
        image_map = CommentedMap()
        image_map["path"] = os.path.basename(ahab_image_file_path)
        ahab_image_map["binary_container"] = image_map
        ahab_config_containers.append(ahab_image_map)

        ahab_container_map = CommentedMap()
        container_map = CommentedMap()
        container_map["srk_set"] = "none"
        container_map["used_srk_id"] = 1
        container_map["fuse_version"] = 0
        container_map["sw_version"] = 0
        container_images = CommentedSeq()

        quick_boot = (config_data.sys_params.get(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT) ==
                      Const.PHY_QUICK_BOOT)
        phy_init_options = Options.get_instance().get_snps_phy_init_options()
        skip_training = (phy_init_options.skip_training() and (not quick_boot)) or (
                        Const.PARAM_SERDES_SKIP_DDR_PHY in config_data.params[Const.PARAM_S_BASIC])
        train_2d = config_data.train_2d and phy_init_options.execute_full_training() and (not quick_boot)

        # create aligned bin for final image
        bin_file_path = self.get_test_second_bin_file_name(config_data)  # type: ignore
        bin_data, bin_size = get_bin_data(bin_file_path)
        aligned_bin_size = align(bin_size, align_to_value)
        bin_data_with_padding = bytearray(aligned_bin_size)
        bin_data_with_padding[0:bin_size] = bin_data
        application_file_path = os.path.join(workspace_dir, os.path.basename(bin_file_path))
        write_file(bin_data_with_padding, application_file_path, mode="wb")

        # add data sections
        imem_1d_size = 0
        imem_2d_size = 0
        dmem_1d_size = 0
        dmem_2d_size = 0
        diag_imem_size = 0
        diag_dmem_size = 0
        fw_size = 0
        if not skip_training:
            imem_1d_file_path = config_data.fw_bin_info[Const.FW_IMEM_1D_FILE_PATH]
            imem_1d_data, imem_1d_size = get_bin_data(imem_1d_file_path)
            aligned_imem_1d_size = align(imem_1d_size, align_to_value)
            fw_size += aligned_imem_1d_size if align_data_sections else imem_1d_size

            if train_2d:
                imem_2d_file_path = config_data.fw_bin_info[Const.FW_IMEM_2D_FILE_PATH]
                imem_2d_data, imem_2d_size = get_bin_data(imem_2d_file_path)
                aligned_imem_2d_size = align(imem_2d_size, align_to_value)
                fw_size += aligned_imem_2d_size if align_data_sections else imem_2d_size

            dmem_1d_file_path = config_data.fw_bin_info[Const.FW_DMEM_1D_FILE_PATH]
            dmem_1d_data, dmem_1d_size = get_bin_data(dmem_1d_file_path)
            aligned_dmem_1d_size = align(dmem_1d_size, align_to_value)
            fw_size += aligned_dmem_1d_size if align_data_sections else dmem_1d_size

            if train_2d:
                dmem_2d_file_path = config_data.fw_bin_info[Const.FW_DMEM_2D_FILE_PATH]
                dmem_2d_data, dmem_2d_size = get_bin_data(dmem_2d_file_path)
                aligned_dmem_2d_size = align(dmem_2d_size, align_to_value)
                fw_size += aligned_dmem_2d_size if align_data_sections else dmem_2d_size

            if (train_2d or config_data.is_phy_v3(
                    config_data.snps_phy_info)) and \
                    Const.DIAGS_IMEM_FILE_PATH in config_data.fw_bin_info and \
                    Const.DIAGS_DMEM_FILE_PATH in config_data.fw_bin_info:
                diag_imem_file_path = config_data.fw_bin_info[Const.DIAGS_IMEM_FILE_PATH]
                diag_imem_data, diag_imem_size = get_bin_data(diag_imem_file_path)
                aligned_diag_imem_size = align(diag_imem_size, align_to_value)
                fw_size += aligned_diag_imem_size if align_data_sections else diag_imem_size

                diag_dmem_file_path = config_data.fw_bin_info[Const.DIAGS_DMEM_FILE_PATH]
                diag_dmem_data, diag_dmem_size = get_bin_data(diag_dmem_file_path)
                aligned_diag_dmem_size = align(diag_dmem_size, align_to_value)
                fw_size += aligned_diag_dmem_size if align_data_sections else diag_dmem_size

        fw_load_addr = Const.IMX95_FW_START_ADDRESS_NS_NSRAM

        if fw_size > 0:
            fw_data = bytearray(fw_size)
            offset = 0

            config_data.sys_params[Const.FW_IMEM_1D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_IMEM_1D_FILE_SIZE] = hex(imem_1d_size)
            if imem_1d_size > 0:
                fw_data[offset: offset + imem_1d_size] = imem_1d_data
                offset += aligned_imem_1d_size if align_data_sections else imem_1d_size

            config_data.sys_params[Const.FW_IMEM_2D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_IMEM_2D_FILE_SIZE] = hex(imem_2d_size)
            if imem_2d_size > 0:
                fw_data[offset: offset + imem_2d_size] = imem_2d_data
                offset += aligned_imem_2d_size if align_data_sections else imem_2d_size

            config_data.sys_params[Const.FW_DMEM_1D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_DMEM_1D_FILE_SIZE] = hex(dmem_1d_size)
            if dmem_1d_size > 0:
                fw_data[offset: offset + dmem_1d_size] = dmem_1d_data
                offset += aligned_dmem_1d_size if align_data_sections else dmem_1d_size

            config_data.sys_params[Const.FW_DMEM_2D_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.FW_DMEM_2D_FILE_SIZE] = hex(dmem_2d_size)
            if dmem_2d_size > 0:
                fw_data[offset: offset + dmem_2d_size] = dmem_2d_data
                offset += aligned_dmem_2d_size if align_data_sections else dmem_2d_size

            config_data.sys_params[Const.DIAGS_IMEM_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.DIAGS_IMEM_SIZE] = hex(diag_imem_size)
            if diag_imem_size > 0:
                fw_data[offset: offset + diag_imem_size] = diag_imem_data
                offset += aligned_diag_imem_size if align_data_sections else diag_imem_size

            config_data.sys_params[Const.DIAGS_DMEM_SOURCE] = hex(fw_load_addr + offset)
            config_data.sys_params[Const.DIAGS_DMEM_SIZE] = hex(diag_dmem_size)
            if diag_dmem_size > 0:
                fw_data[offset: offset + diag_dmem_size] = diag_dmem_data
                offset += aligned_diag_dmem_size if align_data_sections else diag_dmem_size

            fw_file_name = "fw.bin"
            fw_file_path = os.path.join(workspace_dir, fw_file_name)
            write_file(fw_data, fw_file_path, mode="wb")

            # add fw data to AHAB container
            container_images.append(
                self.__create_ahab_image_container(fw_file_path, hex(fw_load_addr),
                    hex(fw_load_addr), "cortex-m33", "data", "sha384", 0))

        # dcd creation should be delayed until all config_data.sys_params are correctly set
        processor.create_dcd_bin(config_data)
        # compute dcd address
        if config_data.soc_name == 'MIMX943':
            dcd_load_address = hex(Const.IMX943_DCD_START_ADDRESS_NS_NSRAM)
        else:
            dcd_load_address = hex(Const.IMX95_DCD_START_ADDRESS_NS_NSRAM)
        config_data.target_params['dcd_addr'] = dcd_load_address

        # add dcd to AHAB container
        dcd_load_address = config_data.target_params['dcd_addr']
        container_images.append(
            self.__create_ahab_image_container(config_data.target_params['dcd_file'],
                dcd_load_address, dcd_load_address, "cortex-m33", "data", "sha384", 0))

        # add ddr fw
        ddr_fw_file_path = processor.get_test_bin_file_name(config_data)
        tmp_ddr_fw_file = os.path.join(workspace_dir, os.path.basename(ddr_fw_file_path))
        shutil.copy(ddr_fw_file_path, tmp_ddr_fw_file)  # copy ddr fw image to workspace
        container_images.append(
            self.__create_ahab_image_container(os.path.basename(ddr_fw_file_path),
                hex(Const.IMX95_APP_START_ADDRESS_S_TCMC), hex(Const.IMX95_APP_START_ADDRESS_S_TCMC + 1),
                "cortex-m33", "oei", "sha384", 0))

        # add sm
        sm_file_path = processor.get_sm_file_name(config_data)
        tmp_sm_file = os.path.join(workspace_dir, os.path.basename(sm_file_path))
        shutil.copy(sm_file_path, tmp_sm_file)  # copy sm image to workspace
        container_images.append(
            self.__create_ahab_image_container(os.path.basename(sm_file_path),
                hex(Const.IMX95_APP_START_ADDRESS_S_TCMC), hex(Const.IMX95_APP_START_ADDRESS_S_TCMC),
                "cortex-m33", "executable", "sha384", 0))

        # add executable to AHAB container
        app_load_addr = hex(Const.IMX9_APP_START_ADDRESS)
        app_entry_addr = app_load_addr
        container_images.append(
            self.__create_ahab_image_container(application_file_path, app_load_addr,
                app_entry_addr, "cortex-a55", "executable", "sha384", 2))

        # add v2x
        v2x_file_path = processor.get_v2x_file_name(config_data)
        if v2x_file_path:
            tmp_v2x_file = os.path.join(workspace_dir, os.path.basename(v2x_file_path))
            shutil.copy(v2x_file_path, tmp_v2x_file)  # copy v2x image to workspace
            container_images.append(
                self.__create_ahab_image_container(os.path.basename(v2x_file_path),
                    hex(Const.IMX95_V2X_ADDRESS), hex(Const.IMX95_V2X_ADDRESS),
                    "cortex-m33", "v2x_dummy", "sha384", 0))

        # finalize AHAB container initialization
        container_map["images"] = container_images
        ahab_container_map["container"] = container_map
        ahab_config_containers.append(ahab_container_map)
        ahab_config_map["containers"] = ahab_config_containers

        # generate AHAB config yaml
        workspace_dir = Workspace.get_instance().get_location()
        ahab_config_file = os.path.join(workspace_dir, Const.AHAB_CONFIG_NAME)
        commented_ahab_config_data = CommentedConfig(main_title=(f"AHAB created configuration from "
            f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}."),
            schemas=AHABImage.get_validation_schemas(
                FamilyRevision(SDPSComm.get_spsdk_device(config_data.soc_name)))).get_config(ahab_config_map)
        write_file(commented_ahab_config_data, ahab_config_file)

        return ahab_config_file

    def _insert_bin_data(self, config_data, image, filename, address, size):  # type: ignore
        # TODO: see if size is needed
        _file_size = os.path.getsize(filename)
        _data = bytearray(_file_size)
        with open(filename, 'rb') as f:
            _data = f.read()

        _offset = address - int(config_data.target_params['workspace_address'], 16) + SDPUtils.IVT_HEADER_SIZE

        self.logger.debug('Address %8x offset %8x size %8x insert file %s', address, _offset, _file_size, filename)

        image[_offset: _offset + _file_size] = _data

        return image

    def execute(self, config_data: ConfigData, resume_from_bkp: bool = False) -> None:
        """Override execute from CommProtocolInterface."""
        self.sdps.close()

    def init_reg_calc(self, dram_type):  # type: ignore
        """TODO:summary line."""
        super(SDPSProcessor, self).init_reg_calc(dram_type)
