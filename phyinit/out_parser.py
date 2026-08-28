# Copyright 2020-2025 NXP
"""TODO:summary line."""
import json
import logging
import os
import re
from typing import Optional

from memtool.common.config_data import ConfigData
from memtool.common.factories import ProcessorFactory
from memtool.common.workspace import Workspace
from memtool.phyinit.phy_utils import PhyPhase, PhyV2Utils, PhyV3Utils
from memtool.utils.constants import Const

import lz4.frame


class PhyStep:
    """Class used to model the node from the tree containing steps from PHY output."""

    def __init__(self, _parent, _phase: str, _step: str, _function: str):  # type: ignore
        """Constructor: PHY step info.

        @param _parent: parent node
        @param _phase: phase name
        @param _step: step name
        @param _function: function name
        """
        self.parent = _parent
        self.phase = _phase
        self.step = _step
        self.function = _function
        self.commands = {}  # type: ignore
        self.children = []  # type: ignore

    def get_parent(self):  # type: ignore
        """Get node parent."""
        return self.parent

    def get_phase(self):  # type: ignore
        """Get phase name."""
        return self.phase

    def get_step(self):  # type: ignore
        """Get step name."""
        return self.step

    def get_function(self):  # type: ignore
        """Get function name."""
        return self.function

    def get_children(self):  # type: ignore
        """Get children nodes."""
        return self.children

    def add_commands(self, _pstate: str, _commands):  # type: ignore
        """Add commands for the specified pstate.

        @param _pstate: pstate for which commands are added
        @param _commands: array of commands specified as (addr, val) pairs
        """
        if _pstate not in self.commands:
            self.commands[_pstate] = _commands.copy()
        else:
            self.commands[_pstate].extend(_commands.copy())

    def get_commands(self, _pstate: str):  # type: ignore
        """Get commands for the specified pstate.

        @param _pstate: pstate for which commands are needed
        @return: array of commands specified as (addr, val) pairs
        """
        if _pstate not in self.commands:
            return []

        return self.commands[_pstate]

    def get_child(self, _phase: str, _step: str, _function: str):  # type: ignore
        """Get the child with the specified info.

        @param _phase: phase name
        @param _step: step name
        @param _function: function name
        @return: child node
        """
        for child in self.children:
            if _phase == child.get_phase() and _step == child.get_step() and _function == child.get_function():
                return child

        # the child was not found, so we'll create it
        child = PhyStep(self, _phase, _step, _function)
        self.children.append(child)
        return child

    def print_info(self, alignment: str = ""):  # type: ignore
        """Helper function used to display PHY tree info."""
        print(f"{alignment} Node {self.phase} || {self.step} || {self.function}")

        for p in self.commands.keys():
            cmds = self.commands[p]
            no_cmds = len(cmds)
            print(f"{alignment} No commands for {p} is {no_cmds}")

        no_children = len(self.children)
        if no_children == 0:
            print(f"{alignment} No children")
        else:
            print(f"{alignment} Children:")
            for child in self.children:
                child.print_info(alignment + "     ")
                print(f"{alignment} --------------------------")

    @staticmethod
    def get_nodes_for_step(root, step: str):  # type: ignore
        """Get nodes with specified step from the tree with the specified root.

        @root: tree root node
        @step: step name
        @return: array of nodes for given step
        """
        nodes = []
        if root.get_step() == step:
            nodes.append(root)
        for child in root.get_children():
            nodes.extend(PhyStep.get_nodes_for_step(child, step))
        return nodes


class PhyInitParser:
    """Class for parsing PhyInit data from config and writing to out file."""

    logger = logging.getLogger(__file__)

    DETAILED_DEBUG_INFO = False

    def __init__(self):  # type: ignore
        """TODO:summary line."""
        pass

    @staticmethod
    def _process_out_line(line):  # type: ignore
        """Extract values from a line of the out file.

        @param line: line to be processed
        @return: new_line, addr, val
        """
        if re.search(Const.comm_re, line):
            return line, 0, 0
        if re.search(Const.write16_re, line):
            write16 = re.findall(Const.hex_num_re, line)
            if len(write16) != 2:
                logging.getLogger(__name__).warning('Could not extract values from %s', line)
                return f'// {line}', 0, 0

            new_line = f"{Const.write16_txt}(0x{write16[0][1:]}, 0x{write16[1][1:]})\n"
            return new_line, int(write16[0][1:], 16), int(write16[1][1:], 16)

        return line, 0, 0

    @staticmethod
    def _write_to_file(out_dir, filename: str, _format: str, info: str, data, mode='w'):  # type: ignore
        """Write data to file.

        @param out_dir: directory for generated files
        @param filename: name of file
        @param _format: file format (name of extension)
        @param info: what the file refers to
        @param data: data to be written; str or bytearray
        @param mode: mode used to open the file (by default is 'write')
        """
        out_file = f'{out_dir}{os.path.sep}{filename}'

        logging.getLogger(__name__).debug('Write %s as %s size 0x%x to file %s', info, _format, len(data),
                                          os.path.abspath(out_file))

        # if _format == 'bin':
        #     #compress data using LZ4 algorithm and write to file
        #     data = lz4.frame.compress(data, compression_level=Const.LZ4_COMPRESSION_LEVEL)
        _fmt = f'{mode}b' if _format == 'bin' else f'{mode}t'
        with open(out_file, _fmt) as f_out:
            f_out.write(data)

    @staticmethod
    def _get_dmem_msg_blk_size(mem_type: str, phy_version: int) -> int:
        """Get message block size based on mem type.

        @param mem_type: memory type
        @param phy_version: phy version
        @return message block size
        """
        assert mem_type in ConfigData.MEMORY_TYPES.values()
        if mem_type == 'ddr3':
            return 0x51
        if mem_type == 'ddr4':
            return 0x1FC
        if mem_type in ('lpddr4', 'lpddr4x'):
            if phy_version == 2:
                return 0x44
            elif phy_version == 3:
                return 0x1FF
        if mem_type in ('lpddr5', 'lpddr5x'):
            if phy_version == 3:
                return 0x1FF

        PhyInitParser.logger.error('PHY version %d is not supported for %s!', phy_version, mem_type)
        return 0

    @staticmethod
    def _update_phy_init_files(out_dir: str, segment_dict: list[tuple[str, str]], segment_txt: str,
                               pstate: Optional[int] = None, mode: str = 'w') -> None:
        """Update phy_init.c, phy_init.json and pstate-specific phy_init files with a segment of data."""
        file_name = Const.phy_init_out_file_name + str(pstate) if pstate is not None else Const.phy_init_out_file_name

        # write PHY init to file
        PhyInitParser._write_to_file(out_dir, file_name + Const.phy_init_out_file_ext, 'txt', 'PHY CONFIG',
                                     segment_txt, mode)

        # add corresponding keys to hex values for json
        segment_dict_with_tags = [dict(zip(("address", "value"), t)) for t in segment_dict]
        PhyInitParser._write_to_file(out_dir, file_name + Const.json_ext, 'txt', 'PHY CONFIG',
                                     json.dumps(segment_dict_with_tags, indent=4), mode)

    @staticmethod
    def _update_pie_files(out_dir: str, segment_dict: list[tuple[str, str]], segment_txt: str,
                          pstate: Optional[int] = None, mode: str = 'w') -> None:
        """Update pie.txt, pie.json and pstate-specific pie files with a segment of data."""
        file_name = Const.pie_file_name + str(pstate) if pstate is not None else Const.pie_file_name

        # write output to file
        PhyInitParser._write_to_file(out_dir, file_name + Const.pie_txt_ext, 'txt', 'PIE', segment_txt, mode)

        # add corresponding keys to hex values for json
        segment_dict_with_tags = [dict(zip(("address", "value"), t)) for t in segment_dict]
        PhyInitParser._write_to_file(out_dir, file_name + Const.json_ext, 'txt', 'PIE',
                                     json.dumps(segment_dict_with_tags, indent=4), mode)

    @staticmethod
    def parse_phy_v2(config_data: ConfigData, phyinit_out_file, retention_out_file):  # type: ignore
        """Process file line by line, add info to config_data, compose out files and write them.

        Parsing goes through multiple phases, each dedicated to a certain type of data and files to be generated
        @param config_data: processor config data
        @param phyinit_out_file: file to be parsed
        @param retention_out_file: file to be parsed
        """
        logger = logging.getLogger(__name__)
        logger.debug('Parse phyinit output file %s', os.path.abspath(phyinit_out_file))
        logger.debug('Parse retention output file %s', os.path.abspath(retention_out_file))

        config_data.message_block_1d = []
        config_data.message_block_tmg_1d = []
        config_data.message_block_2d = ''
        config_data.message_block_tmg_2d = ''
        config_data.phy_full_config = {}
        msg_block = []  # type: ignore
        msg_block_v = ""
        msg_block_size = PhyInitParser._get_dmem_msg_blk_size(config_data.mem_type, config_data.snps_phy_info.version)

        out_dir = Workspace.get_instance().get_location()

        with open(phyinit_out_file, "rt", encoding="utf-8") as f:
            line = f.readline()
            segment_txt = ''
            segment_dict = []  # type: ignore
            binary = bytearray()
            logging.getLogger(__name__).debug('Parse state A_BRING_UP_POWER')
            phase = PhyPhase.BRING_UP_POWER
            line_number = 1
            pstate_idx = 0
            while line:
                if phase == PhyPhase.BRING_UP_POWER:
                    if PhyV2Utils.start_phy_init in line:
                        phase = PhyPhase.PHY_INIT_CONFIG
                        logging.getLogger(__name__).debug('Parse state C_PHY_INIT_CONFIG(%d)', line_number)
                elif phase == PhyPhase.PHY_INIT_CONFIG:
                    if PhyV2Utils.start_phyinit_skip_train in line:
                        phase = PhyPhase.SKIP_TRAIN_MODE
                        logging.getLogger(__name__).debug('Parse state SKIP_TRAIN_MODE(%d)', line_number)
                    elif PhyV2Utils.start_phyinit_load_imem in line:
                        phase = PhyPhase.LOAD_IMEM_1
                        logging.getLogger(__name__).debug('Parse state LOAD_IMEM_1(%d)', line_number)
                    elif PhyV2Utils.end_phy_init in line:
                        if segment_txt:
                            PhyInitParser._update_phy_init_files(out_dir, segment_dict, segment_txt)
                            config_data.phy_full_config[PhyPhase.PHY_INIT_CONFIG.name] = segment_dict.copy()
                            segment_dict = []
                            segment_txt = ''
                        else:
                            PhyInitParser.logger.error('No PHY commands were found for the '
                                                       'dwc_ddrphy_phyinit_C_initPhyConfig segment')
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        if addr != 0:
                            segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))
                        segment_txt += f"{new_line}"
                elif phase == PhyPhase.LOAD_IMEM_1:
                    if PhyV2Utils.start_load_bin in line:
                        phase = PhyPhase.LOAD_IMEM_1D
                        logging.getLogger(__name__).debug('Parse state D_LOAD_IMEM_1D(%d)', line_number)
                elif phase == PhyPhase.LOAD_IMEM_1D:
                    if PhyV2Utils.end_load_bin in line:
                        phase = PhyPhase.SET_DFI_CLOCK
                        # write output to file
                        PhyInitParser._write_to_file(out_dir, Const.imem_1d_bin, 'bin', 'IMEM 1D', binary)
                        PhyInitParser._write_to_file(out_dir, Const.imem_1d_txt, 'txt', 'IMEM 1D', segment_txt)
                        binary = bytearray()
                        segment_txt = ''
                        logging.getLogger(__name__).debug('Parse state PHASE.E_SET_DFI_CLOCK(%d)', line_number)
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        segment_txt += f"{new_line}"
                        offset = addr - Const.phy_imem_addr
                        binary[2 * offset: 2 * offset + 2] = bytes([val & 0xFF, (val >> 8) & 0xFF])
                elif phase == PhyPhase.SET_DFI_CLOCK:
                    if PhyV2Utils.start_phyinit_load_dmem in line:
                        phase = PhyPhase.LOAD_DMEM_1
                        msg_block = []
                        msg_block_v = ""
                        logging.getLogger(__name__).debug('Parse state PHASE.F_LOAD_DMEM_1(%d)', line_number)
                    elif PhyV2Utils.start_phyinit_load_imem in line:
                        phase = PhyPhase.LOAD_IMEM_2
                        logging.getLogger(__name__).debug('Parse state PHASE.D_LOAD_IMEM_2(%d)', line_number)
                elif phase == PhyPhase.LOAD_DMEM_1:
                    if PhyV2Utils.start_load_bin in line:
                        phase = PhyPhase.LOAD_DMEM_1D
                        logging.getLogger(__name__).debug('Parse state PHASE.F_LOAD_DMEM_1D(%d)', line_number)
                elif phase == PhyPhase.LOAD_IMEM_2:
                    if PhyV2Utils.start_load_bin in line:
                        phase = PhyPhase.LOAD_IMEM_2D
                        logging.getLogger(__name__).debug('Parse state PHASE.D_LOAD_IMEM_2D(%d)', line_number)
                elif phase == PhyPhase.LOAD_DMEM_2:
                    if PhyV2Utils.start_load_bin in line:
                        phase = PhyPhase.LOAD_DMEM_2D
                        logging.getLogger(__name__).debug('Parse state PHASE.D_LOAD_DMEM_2D(%d)', line_number)
                elif phase == PhyPhase.LOAD_DMEM_1D:
                    if PhyV2Utils.end_load_bin in line:
                        phase = PhyPhase.EXEC_FW
                        # write output to file
                        PhyInitParser._write_to_file(out_dir, Const.dmem_1d_bin[pstate_idx], 'bin', 'DMEM 1D', binary)
                        PhyInitParser._write_to_file(out_dir, Const.dmem_1d_txt[pstate_idx], 'txt', 'DMEM 1D',
                                                     segment_txt)
                        config_data.phy_full_config[PhyPhase.LOAD_DMEM_1D.name + str(pstate_idx)] = segment_dict.copy()
                        config_data.message_block_1d.append(msg_block)
                        config_data.message_block_tmg_1d.append(msg_block_v)
                        binary = bytearray()
                        segment_dict = []
                        segment_txt = ''
                        pstate_idx = pstate_idx + 1
                        logging.getLogger(__name__).debug('Parse state PHASE.G_EXEC_FW(%d)', line_number)
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        if addr < 0x54200 and val != 0:
                            msg_block.append((f"0x{addr:x}", f"0x{val:x}"))
                            msg_block_v += f"{{0x{addr:x}, 0x{val:x}}},\n"
                        if pstate_idx == 0 or addr < 0x54200:
                            segment_txt += f"{new_line}"
                            offset = addr - Const.phy_v2_dmem_addr
                            if (addr - Const.phy_v2_dmem_addr) <= msg_block_size:
                                segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))
                            binary[2 * offset: 2 * offset + 2] = bytes([val & 0xFF, (val >> 8) & 0xFF])
                elif phase == PhyPhase.EXEC_FW:
                    if PhyV2Utils.phyinit_set_dfi_clk in line:
                        phase = PhyPhase.SET_DFI_CLOCK
                        logging.getLogger(__name__).debug('Parse state PHASE.E_SET_DFI_CLOCK(%d)', line_number)
                    elif PhyV2Utils.start_load_pie in line:
                        phase = PhyPhase.LOAD_PIE
                        segment_dict = []
                        logging.getLogger(__name__).debug('Parse state PHASE.PHASE.I_LOAD_PIE(%d)', line_number)
                elif phase == PhyPhase.LOAD_IMEM_2D:
                    if PhyV2Utils.end_load_bin in line:
                        phase = PhyPhase.LOAD_DMEM_2
                        # write output to file
                        PhyInitParser._write_to_file(out_dir, Const.imem_2d_txt, 'txt', 'IMEM 2D', segment_txt)
                        PhyInitParser._write_to_file(out_dir, Const.imem_2d_bin, 'bin', 'IMEM 2D', binary)
                        binary = bytearray()
                        segment_txt = ''
                        logging.getLogger(__name__).debug('Parse state PHASE.PHASE.F_LOAD_DMEM_2(%d)', line_number)
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        segment_txt += f"{new_line}"
                        offset = addr - Const.phy_imem_addr
                        binary[2 * offset: 2 * offset + 2] = bytes([val & 0xFF, (val >> 8) & 0xFF])
                elif phase == PhyPhase.LOAD_DMEM_2D:
                    if PhyV2Utils.end_load_bin in line:
                        phase = PhyPhase.EXEC_FW
                        # write output to file
                        PhyInitParser._write_to_file(out_dir, Const.dmem_2d_bin, 'bin', 'DMEM 2D', binary)
                        PhyInitParser._write_to_file(out_dir, Const.dmem_2d_txt, 'txt', 'DMEM 2D', segment_txt)
                        config_data.phy_full_config[PhyPhase.LOAD_DMEM_2D.name] = segment_dict.copy()
                        binary = bytearray()
                        segment_dict = []
                        segment_txt = ''
                        logging.getLogger(__name__).debug('Parse state PHASE.PHASE.G_EXEC_FW(%d)', line_number)
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        segment_txt += f"{new_line}"
                        if addr < 0x54200 and val != 0:
                            config_data.message_block_2d += f"{Const.phy_io_write}(0x{addr:x}, 0x{val:x});\n"
                            config_data.message_block_tmg_2d += f"{{0x{addr:x}, 0x{val:x}}},\n"
                        offset = addr - Const.phy_v2_dmem_addr
                        if (addr - Const.phy_v2_dmem_addr) <= msg_block_size:
                            segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))
                        binary[2 * offset: 2 * offset + 2] = bytes([val & 0xFF, (val >> 8) & 0xFF])
                elif phase == PhyPhase.LOAD_PIE:
                    if PhyV2Utils.end_load_pie in line:
                        phase = PhyPhase.READ_MSG_BLOCK
                        if segment_txt:
                            PhyInitParser._update_pie_files(out_dir, segment_dict, segment_txt)
                            config_data.phy_full_config[PhyPhase.LOAD_PIE.name] = segment_dict.copy()
                            segment_dict = []
                            segment_txt = ''
                            logging.getLogger(__name__).debug('Parse state PHASE.H_READ_MSG_BLOCK(%d)', line_number)
                        else:
                            PhyInitParser.logger.error('No PHY commands were found for the PIE image')
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        segment_txt += f'{new_line}'
                        if addr != 0:
                            segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))
                elif phase == PhyPhase.SKIP_TRAIN_MODE:
                    if PhyV2Utils.start_phyinit_load_imem in line:
                        phase = PhyPhase.LOAD_IMEM_1
                        logging.getLogger(__name__).debug('Parse state LOAD_IMEM_1(%d)', line_number)
                    elif PhyV2Utils.start_load_pie in line:
                        phase = PhyPhase.LOAD_PIE
                        logging.getLogger(__name__).debug('Parse state LOAD_PIE(%d)', line_number)
                    elif PhyV2Utils.end_phyinit_skip_train in line:
                        if segment_txt:
                            PhyInitParser._update_phy_init_files(out_dir, segment_dict, segment_txt, mode='a')
                            config_data.phy_full_config[PhyPhase.SKIP_TRAIN_MODE.name] = segment_dict.copy()
                            segment_dict = []
                            segment_txt = ''
                        else:
                            PhyInitParser.logger.error('No PHY commands were found for the '
                                                       'dwc_ddrphy_phyinit_progCsrSkipTrain segment')
                    else:
                        new_line, addr, val = PhyInitParser._process_out_line(line)
                        segment_txt += f"{new_line}"
                        if addr != 0:
                            segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))

                # read next line
                line = f.readline()
                line_number = line_number + 1

        config_data.retention_registers = []
        processor = ProcessorFactory.make_unique_instance(config_data.soc_name, config_data.mem_type)
        if processor.processor_info.is_imx8():
            # for IMX8 CSR data must be loaded from hardcoded list stored in processor data
            csr_file_path = os.path.join(config_data.data_dir, Const.IMX8_CSR_DIR_NAME, Const.IMX8_CSR_FILE_NAME)
            if os.path.exists(os.path.abspath(csr_file_path)):
                with open(csr_file_path, 'r', encoding='utf-8') as csr_file:
                    try:
                        csr_list = json.loads(csr_file.read())
                    except Exception as e:
                        PhyInitParser.logger.error('Exception while parsing the user csr json file: %s', str(e))
                    config_data.retention_registers.extend(csr_list)
        else:
            with open(retention_out_file, "rt", encoding="utf-8") as f:
                line = f.readline()
                logging.getLogger(__name__).debug('Parse retention register list')
                while line:
                    new_line, addr, val = PhyInitParser._process_out_line(line)
                    config_data.retention_registers.append(f"0x{addr:x}")

                    # read next line
                    line = f.readline()

    @staticmethod
    def parse_phy_v3(config_data: ConfigData, out_file: str, retention_out_file: str):  # type: ignore
        """Process PHY v3 file line by line, add info to config_data, compose out files and write them.

        Parsing goes through multiple phases, each dedicated to a certain type of data and files to be generated
        @param config_data: processor config data
        @param out_file: file to be parsed
        @param retention_out_file: file to be parsed
        """
        logger = logging.getLogger(__name__)

        # get skip mask info if available
        #######################

        skip_train_mask_remove = []
        skip_train_mask_change = {}
        skip_train_folder = os.path.join(config_data.data_dir, Const.EMU_MASK_DIR_NAME)
        emu_mask_present = False
        if os.path.exists(skip_train_folder):
            emu_mask_present = True
            skip_train_files = os.listdir(skip_train_folder)
            if len(skip_train_files) > 1:
                logger.error(f'{skip_train_folder} has to include a single file!')
            elif len(skip_train_files) == 1:
                skip_train_file_name = skip_train_files[0]
                skip_train_file_path = os.path.join(skip_train_folder, skip_train_file_name)
                logger.debug('Parse skip train mask file %s', os.path.abspath(skip_train_file_path))
                change = True
                with open(skip_train_file_path, "rt", encoding="utf-8") as f:
                    line_number = 0
                    while True:
                        # read line
                        line = f.readline()
                        if len(line) == 0:
                            break
                        line_number += 1
                        line = line.strip()
                        if len(line) == 0:
                            continue

                        # search command
                        re_command = re.search(Const.write16_re, line)
                        if re_command is not None:
                            # command
                            new_line, addr, val = PhyInitParser._process_out_line(line)
                            if change:
                                skip_train_mask_change[addr] = val
                            else:
                                skip_train_mask_remove.append(addr)
                        else:
                            lline = line.lower()
                            if lline.startswith('remove'):
                                change = False
                            elif lline.startswith('change') or lline.startswith('zero'):
                                change = True

        # parse PHY output
        ##################

        step_start_pattern = r"\[(\w+)\]\s+[S|s]tart\s+of\s+(\w+)"
        step_stop_pattern = r"\[(\w+)\]\s+[E|e]nd\s+of\s+(\w+)"
        phase_pattern = r"\w+(_[A-J]+_)\w+"
        pstate_pattern = r"\W+([P|p][S|s]tate\s*[=]*\s*)([0-9]+)\W*"

        phy_tree_root = PhyStep(None, "PHY_INIT_TREE", "", "")
        crt_phy_tree_node = phy_tree_root
        crt_phase = None
        crt_step = None
        crt_function = None
        crt_pstate = PhyV3Utils.COMMON_DATA
        commands = []  # type: ignore

        logger.debug('Parse output file %s', os.path.abspath(out_file))
        with open(out_file, "rt", encoding="utf-8") as f:
            line_number = 0
            while True:
                # read line
                line = f.readline()
                if len(line) == 0:
                    break
                line_number += 1
                line = line.strip()
                if len(line) == 0:
                    continue

                re_step_start = re.search(step_start_pattern, line)
                # search step start
                if re_step_start is not None:
                    # start step
                    crt_step = re_step_start.group(1)
                    re_phase = re.search(phase_pattern, crt_step)
                    crt_phase = None
                    if re_phase is not None:
                        crt_phase = re_phase.group(1).replace("_", "")
                    crt_function = re_step_start.group(2)

                    # tree depth = 3
                    crt_phy_tree_node_parent = crt_phy_tree_node.get_parent()
                    if (crt_phy_tree_node_parent is not None) and \
                       ("PHY_INIT_TREE" != crt_phy_tree_node_parent.get_phase()):
                        if PhyInitParser.DETAILED_DEBUG_INFO:
                            print(f"[INFO {line_number}] Start of {crt_phase} || {crt_step} || {crt_function} "
                                  f"is the end of {crt_phy_tree_node.get_phase()} || {crt_phy_tree_node.get_step()} "
                                  f"|| {crt_phy_tree_node.get_function()}")
                        crt_phy_tree_node.add_commands(crt_pstate, commands)
                        crt_phy_tree_node = crt_phy_tree_node_parent

                    # reset pstate
                    re_pstate = re.search(pstate_pattern, line)
                    if re_pstate is not None:
                        crt_pstate = re_pstate.group(2)
                    else:
                        crt_pstate = PhyV3Utils.COMMON_DATA
                    if PhyInitParser.DETAILED_DEBUG_INFO:
                        print(f"[INFO {line_number}] pstate = {crt_pstate}")

                    # get the tree node for current step
                    crt_phy_tree_node = crt_phy_tree_node.get_child(crt_phase, crt_step, crt_function)  # type: ignore
                    if PhyInitParser.DETAILED_DEBUG_INFO:
                        print(f"[INFO {line_number}] Start of {crt_phase} || {crt_step} || {crt_function}")
                        print(f"[NEW CRT NODE] {crt_phase} || {crt_step} || {crt_function}")

                    # reset commands array
                    commands = []
                else:
                    # search step stop
                    re_step_stop = re.search(step_stop_pattern, line)
                    if re_step_stop is not None:
                        # stop step
                        tmp_step = re_step_stop.group(1)
                        re_phase = re.search(phase_pattern, tmp_step)
                        tmp_phase = None
                        if re_phase is not None:
                            tmp_phase = re_phase.group(1).replace("_", "")
                        tmp_function = re_step_stop.group(2)

                        if crt_phase != tmp_phase or crt_step != tmp_step or crt_function != tmp_function:
                            if PhyInitParser.DETAILED_DEBUG_INFO:
                                print(f"[ERROR {line_number}] After start of {crt_phase} || {crt_step} || "
                                      f"{crt_function} found end of {tmp_phase} || {tmp_step} || {tmp_function}")
                        else:
                            crt_phy_tree_node.add_commands(crt_pstate, commands)

                            # reset commands array
                            commands = []

                            if PhyInitParser.DETAILED_DEBUG_INFO:
                                print(f"[INFO {line_number}] End of {crt_phase} || {crt_step} || {crt_function}")
                            crt_phy_tree_node = crt_phy_tree_node.get_parent()
                            crt_phase = crt_phy_tree_node.get_phase()
                            crt_step = crt_phy_tree_node.get_step()
                            crt_function = crt_phy_tree_node.get_function()
                            if PhyInitParser.DETAILED_DEBUG_INFO:
                                print(f"[CRT NODE] {crt_phase} || {crt_step} || {crt_function}")

                            # reset current pstate
                            crt_pstate = PhyV3Utils.COMMON_DATA
                            if PhyInitParser.DETAILED_DEBUG_INFO:
                                print(f"[INFO {line_number}] pstate = {crt_pstate}")
                    else:
                        # search pstate
                        re_pstate = re.search(pstate_pattern, line)
                        if re_pstate is not None:
                            # pstate info
                            tmp_pstate = re_pstate.group(2)
                            if crt_pstate != tmp_pstate:
                                if crt_pstate == PhyV3Utils.COMMON_DATA:
                                    crt_pstate = tmp_pstate
                                else:
                                    if PhyInitParser.DETAILED_DEBUG_INFO:
                                        print(f"[ERROR {line_number}] Current pstate is {crt_pstate}, "
                                              f"found pstate {tmp_pstate}")
                                if PhyInitParser.DETAILED_DEBUG_INFO:
                                    print(f"[INFO {line_number}] pstate = {crt_pstate}")
                        else:
                            # search command
                            re_command = re.search(Const.write16_re, line)
                            if re_command is not None:
                                # command
                                new_line, addr, val = PhyInitParser._process_out_line(line)
                                if addr not in skip_train_mask_remove:
                                    if addr in skip_train_mask_change:
                                        val = skip_train_mask_change[addr]
                                    commands.append((addr, val))

        # log tree info
        if PhyInitParser.DETAILED_DEBUG_INFO:
            phy_tree_root.print_info()

        # update config_data structures
        ##############################

        out_dir = Workspace.get_instance().get_location()

        # phyinit_C_initPhyConfig, dwc_ddrphy_phyinit_progCsrSkipTrain -> initPhyConfig
        segment_txt = ''
        segment_dict = []
        for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.PHY_CONFIG_DATA):
            for addr, val in node.get_commands(PhyV3Utils.COMMON_DATA):
                segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                if addr != 0:
                    segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))

        if segment_txt:
            PhyInitParser._update_phy_init_files(out_dir, segment_dict, segment_txt)
            config_data.phy_full_config[PhyPhase.PHY_INIT_CONFIG.name] = segment_dict.copy()
        else:
            PhyInitParser.logger.error('No PHY commands were found for the initPhyConfig segment')

        # dwc_ddrphy_phyinit_progCsrSkipTrain -> progCsrSkipTrain
        if emu_mask_present:
            segment_txt = ''
            segment_dict = []
            for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.SKIPTRAIN_DATA):
                for addr, val in node.get_commands(PhyV3Utils.COMMON_DATA):
                    segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                    if addr != 0:
                        segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))

            if segment_txt:
                PhyInitParser._update_phy_init_files(out_dir, segment_dict, segment_txt, mode='a')
                config_data.phy_full_config[PhyPhase.SKIP_TRAIN_MODE.name] = segment_dict.copy()
            else:
                PhyInitParser.logger.error('No PHY commands were found for the progCsrSkipTrain segment')

        # phyinit_C_initPhyConfigPsLoop[idx] -> initPhyConfig[idx]
        for pstate in range(config_data.num_pstates):
            segment_txt = ''
            segment_dict = []
            for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.PHY_CONFIG_PS_DATA):
                for addr, val in node.get_commands(str(pstate)):
                    segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                    if addr != 0:
                        segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))

            if segment_txt:
                PhyInitParser._update_phy_init_files(out_dir, segment_dict, segment_txt, pstate=pstate)
                config_data.phy_full_config[PhyPhase.PHY_INIT_CONFIG.name + str(pstate)] = segment_dict.copy()
            else:
                PhyInitParser.logger.error(f'No PHY commands were found for the pstate {pstate} initPhyConfig segment')

        # dwc_ddrphy_phyinit_progCsrSkipTrainPsLoop[idx] -> progCsrSkipTrain[idx]
        if emu_mask_present:
            for pstate in range(config_data.num_pstates):
                segment_txt = ''
                segment_dict = []
                for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.SKIPTRAIN_PS_DATA):
                    for addr, val in node.get_commands(str(pstate)):
                        segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                        if addr != 0:
                            segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))

                if segment_txt:
                    PhyInitParser._update_phy_init_files(out_dir, segment_dict, segment_txt, pstate=pstate, mode='a')
                    config_data.phy_full_config[PhyPhase.SKIP_TRAIN_MODE.name + str(pstate)] = segment_dict.copy()
                else:
                    PhyInitParser.logger.error(f'No PHY commands were found for the pstate {pstate} '
                                               f'progCsrSkipTrain segment')

        # prepare ConfigData IMEM
        segment_txt = ''
        binary = bytearray()
        for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.IMEM_CONFIG_DATA):
            for addr, val in node.get_commands(PhyV3Utils.COMMON_DATA):
                segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                offset = addr - Const.phy_imem_addr
                binary[2 * offset: 2 * offset + 2] = bytes([val & 0xFF, (val >> 8) & 0xFF])
        PhyInitParser._write_to_file(out_dir, Const.imem_1d_bin, 'bin', 'IMEM', binary)
        PhyInitParser._write_to_file(out_dir, Const.imem_1d_txt, 'txt', 'IMEM', segment_txt)

        # prepare ConfigData DMEM
        for pstate in range(config_data.num_pstates):
            segment_txt = ''
            segment_dict = []
            binary = bytearray()
            msg_block = []
            msg_block_v = ""
            msg_block_size = PhyInitParser._get_dmem_msg_blk_size(config_data.mem_type,
                                                                  config_data.snps_phy_info.version)
            for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.DMEM1D_CONFIG_DATA):
                for addr, val in node.get_commands(str(pstate)):
                    if addr == Const.phy_micro_cont_mux_sel_addr:
                        continue
                    if addr < 0x58200:
                        msg_block.append((f"0x{addr:x}", f"0x{val:x}"))
                        if val != 0:
                            msg_block_v += f"{{{hex(addr)}, {hex(val)}}},\n"
                    if pstate == 0 or addr < 0x58200:
                        segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                        offset = addr - Const.phy_v3_dmem_addr
                        if offset <= msg_block_size:
                            segment_dict.append((f"{hex(addr)}", f"{hex(val)}"))
                        binary[2 * offset: 2 * offset + 2] = bytes([val & 0xFF, (val >> 8) & 0xFF])

            dmem_1d_bin = 'dmem_1d.bin' if pstate == 0 else f'msb_pstate_{pstate}.bin'
            dmem_1d_txt = 'dmem_1d.txt' if pstate == 0 else f'msb_pstate_{pstate}.txt'

            PhyInitParser._write_to_file(out_dir, dmem_1d_bin, 'bin', 'DMEM 1D', binary)
            PhyInitParser._write_to_file(out_dir, dmem_1d_txt, 'txt', 'DMEM 1D', segment_txt)
            config_data.phy_full_config[PhyPhase.LOAD_DMEM_1D.name + str(pstate)] = segment_dict.copy()
            config_data.message_block_1d.append(msg_block)
            config_data.message_block_tmg_1d.append(msg_block_v)

        # prepare ConfigData PIE
        segment_txt = ''
        segment_dict = []
        for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.PIE_CONFIG_DATA):
            for addr, val in node.get_commands(PhyV3Utils.COMMON_DATA):
                if addr == Const.phy_micro_cont_mux_sel_addr:
                    continue
                segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                if addr != 0:
                    segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))
        if segment_txt:
            PhyInitParser._update_pie_files(out_dir, segment_dict, segment_txt)
            config_data.phy_full_config[PhyPhase.LOAD_PIE.name] = segment_dict.copy()
        else:
            PhyInitParser.logger.error('No PHY commands were found for the PIE image')

        for pstate in range(config_data.num_pstates):
            segment_txt = ''
            segment_dict = []
            for node in PhyStep.get_nodes_for_step(phy_tree_root, PhyV3Utils.PIE_CONFIG_PS_DATA):
                for addr, val in node.get_commands(str(pstate)):
                    segment_txt += f"{Const.write16_txt}({hex(addr)}, {hex(val)});\n"
                    if addr != 0:
                        segment_dict.append((f"0x{addr:x}", f"0x{val:x}"))
            if segment_txt:
                PhyInitParser._update_pie_files(out_dir, segment_dict, segment_txt, pstate=pstate)
                config_data.phy_full_config[PhyPhase.LOAD_PIE.name + str(pstate)] = segment_dict.copy()
            else:
                PhyInitParser.logger.error(f'No PHY commands were found for the pstate {pstate} PIE image')

        if PhyInitParser.DETAILED_DEBUG_INFO:
            print("ConfigData phy_full_config DONE")

        logger.debug('Parse retention output file %s', os.path.abspath(retention_out_file))
        config_data.retention_registers = []
        with open(retention_out_file, "rt", encoding="utf-8") as f:
            line = f.readline()
            logging.getLogger(__name__).debug('Parse retention register list')
            while line:
                new_line, addr, val = PhyInitParser._process_out_line(line)
                config_data.retention_registers.append(f"0x{addr:x}")

                # read next line
                line = f.readline()
