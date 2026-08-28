# Copyright 2020-2023 NXP
"""TODO:summary line."""
# DEPRECATED

# import logging
# import os
# import sys
# from ctypes import CDLL
# from memtool.utils.constants import Const
#
#
# def run_phyinit(input_file, output_dir, dram_type, fw_version):
#
#     logger = logging.getLogger(__name__)
#
#     logger.info(" Run phyinit for %s%s%s", fw_version, os.path.sep, dram_type)
#
#     if sys.platform == "win32":
#         dll_name = f'phyinit_{fw_version}_{dram_type}.dll'
#     else:
#         dll_name = f'phyinit_{fw_version}_{dram_type}.so'
#
#     dll_path = os.path.abspath(
#         f'{os.path.dirname(__file__)}{os.path.sep}{Const.lib_dir_name}{os.path.sep}{dll_name}')
#
#     out_file = f'{output_dir}/{Const.out_file_name}'
#
#     train2d = (dram_type != 'ddr3')
#     logger.debug("PHY config file %s", os.path.abspath(input_file))
#     logger.debug("Phyinit output file %s", os.path.abspath(out_file))
#     logger.debug("Shared library %s", os.path.abspath(dll_path))
#
#     # load the shared object file
#     if os.path.isfile(dll_path) and os.path.isfile(input_file):
#
#         run_dir = os.getcwd()
#         os.chdir(os.path.dirname(os.path.abspath(__file__)))
#
#         shared_obj = CDLL(dll_path)
#         shared_obj.phy_init_config(input_file.encode('utf-8'), out_file.encode('utf-8'), train2d)
#
#         os.chdir(run_dir)
#     else:
#         logger.error("Cannot find %s or %s", os.path.abspath(dll_path), os.path.abspath(input_file))
#         sys.exit(1)
