# Copyright 2020-2024 NXP
"""Generate code for targets with PHY v3 firmware."""
from memtool.common.config_data import ConfigData
from memtool.processor.base_processor import BaseProcessor
from memtool.processor.layerscape.lx2 import LX2
from memtool.utils.constants import Const


class CodeGenerator:
    """Generate timing data base class."""

    def __init__(self, _config_data: ConfigData, _processor: BaseProcessor):
        """Constructor.

        @param _config_data: processor config data
        @param _processor: processor
        """
        self.config_data = _config_data
        self.processor = _processor

    def generate_timing(self) -> str:  # type: ignore
        """Prepare timing file contents.

        @return: timing file contents as a string
        """
        pass


@staticmethod  # type: ignore
def get_code_generator(config_data: ConfigData, processor: BaseProcessor) -> CodeGenerator:
    """Create the code generator for current target.

    @param config_data: processor config data
    @param processor: processor
    @return: code generator object or None if code generator can't be determined
    """
    from memtool.codegen.codegenerator_lx import CodeGeneratorLX
    from memtool.codegen.codegenerator_phyv2 import CodeGeneratorPHYv2
    from memtool.codegen.codegenerator_phyv3 import CodeGeneratorPHYv3

    if isinstance(processor, LX2):
        return CodeGeneratorLX(config_data, processor)
    else:
        if ConfigData.is_phy_v2(config_data.snps_phy_info):
            return CodeGeneratorPHYv2(config_data, processor)
        else:
            return CodeGeneratorPHYv3(config_data, processor)

    return None


@staticmethod  # type: ignore
def indent_block(block: str, indent: int, add_new_line: bool = True) -> str:
    """Add tabs and new lines to a block of code.

    @param block: string to be indented
    @param indent: number of tabs
    @param add_new_line: True if new line should be added after each indented line
    @return: indented code block
    """
    i_block = ""
    for line in block.split('\n'):
        if line:
            # add indent tabs in front of line
            i_block += f"{indent * Const.indent}{line}\n"
        else:
            if add_new_line:
                i_block += "\n"
    return i_block
