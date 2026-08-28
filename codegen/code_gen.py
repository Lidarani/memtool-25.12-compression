# Copyright 2020-2025 NXP
"""Generate ds and timing files."""
import io
import json
import logging
import os
import sys
import time

from memtool.codegen.codegenerator import get_code_generator
from memtool.common.config_data import ConfigData, SnpsFirmware
from memtool.common.factories import ProcessorFactory
from memtool.common.workspace import Workspace
from memtool.phyinit.phy_init import PHYInitDriver
from memtool.utils.constants import Const
from memtool.utils.helper import add_file_to_params, write_file_content

logger = logging.getLogger(__name__)


def generate_from_config(
    config_data: ConfigData,
    output_dir: str,
    start_time: float = time.time(),
    ds_name: str = "",
    timing_name: str = "",
) -> int:
    """Generate code using config data."""
    return_code = 0

    # create destination folder if it does not exist
    if not os.path.isdir(output_dir):
        logger.info("Create directory %s", os.path.abspath(output_dir))
        os.mkdir(output_dir)
    Workspace.get_instance().set_location(output_dir)

    # call synopsys phy init
    old_dir = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir))
    logger.debug(
        "chdir %s",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir),
    )

    processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)

    try:
        workspace_dir = Workspace.get_instance().get_location()
        if Const.PARAM_S_BASIC_MEM_TYPE in config_data.params[Const.PARAM_S_BASIC]:
            # Run RPA tool
            processor.ddrc_reg_calc(config_data)

            ds_file_name = f"{config_data.mem_type if not ds_name else ds_name}{Const.DS_FILE_SUFFIX}"
            with open(os.path.join(workspace_dir, ds_file_name), "wt", encoding="utf-8") as f:
                f.write(config_data.ds_file_txt)
        else:
            config_data.load_rpa_from_file()

        if not config_data.ds_is_valid:
            raise Exception("DS file generation ended with errors!")

        processor.update_connection_parameters(config_data)
        processor.update_ddrc_config(config_data)
        processor.update_phy_config(config_data)

        end = time.time()
        logger.info("XLS time %f", end - start_time)

        # create file with updated PHY config
        phy_config_file = os.path.join(workspace_dir, "phy_config_final.json")
        with open(phy_config_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(config_data.params[Const.PARAM_S_PHY], indent=4))

        # create DDR controller configuration file
        ddrc_config_file = os.path.join(workspace_dir, "ddrc_config_final.json")
        with open(ddrc_config_file, "wt", encoding="utf-8") as f:
            f.write(json.dumps(config_data.ddrc_config_full, indent=4))

        end = time.time()
        logger.info("Write files time %f", end - start_time)

        # run phyinit to update
        if len(phy_config_file) != 0:
            phy_init_driver = PHYInitDriver.make_unique_instance(
                config_data.data_dir,
                config_data.snps_phy_info.name,
                config_data.mem_type,
            )
            phy_init_driver.run_driver(config_data)
            phy_init_driver.process_results(config_data)

        end = time.time()
        logger.info("Phyinit time %f", end - start_time)

        # create generated files
        code_generator = get_code_generator(config_data, processor)
        if code_generator is not None:
            timing_file_content = code_generator.generate_timing()
            timing_file_name = f"{config_data.mem_type if not timing_name else timing_name}{Const.TIMING_FILE_SUFFIX}"
            timing_file_path = os.path.join(output_dir, f"{timing_file_name}")
            write_file_content(timing_file_path, timing_file_content)
        else:
            logger.error(
                f"Code generator for selected target ({config_data.soc_name}, "
                f"firmware {config_data.snps_phy_info.name}) could not be found!"
            )
            return_code = 1

    except Exception as ex:
        logger.error(ex)
        return_code = 1

    os.chdir(old_dir)
    return return_code


def run_code_gen(
    _log: str,
    _files: list[io.TextIOWrapper],
    _firmware_version: str,
    _mem_type: str,
    _output_dir: str,
    _data_dir: str,
) -> None:
    """Generate code (script called from Config Tools).

    @param _log: log level
    @param _files: list of json files containing configuration parameters
    @param _firmware_version: firmware version
    @param _mem_type: memory type
    @param _output_dir: output location
    @param _data_dir: processor data folder
    @return: 0 if code generation was executed without error, 1 if an error was encountered while generating the code
    """
    start = time.time()

    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        format="%(asctime)-15s %(levelname)-8s %(name)s %(message)s",
        level=getattr(logging, _log),
    )

    # TODO: see if phy_config_file is needed
    # phy_config_file = ''
    _params = {}  # type: ignore
    for file in _files:
        _params = add_file_to_params(file.name, _params)
        # if file.name.endswith('phy.json'):
        #     phy_config_file = file.name
    _params[Const.PARAM_S_TC][Const.PARAM_S_TC_FW] = SnpsFirmware.from_name(_firmware_version).id

    config_data = ConfigData(_data_dir, _params)
    config_data.mem_type = _mem_type
    # TODO: check if args match data in files

    return_code = generate_from_config(config_data, _output_dir, start)

    end = time.time()
    logger.info("Compile time %f", end - start)
    sys.exit(return_code)
