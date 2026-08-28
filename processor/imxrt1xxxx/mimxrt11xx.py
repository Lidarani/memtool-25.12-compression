# Copyright 2022-2024 NXP
"""TODO:summary line."""
from memtool.processor.imxrt1xxxx.imxrt11xx_processor import MIMXRT11XXProcessor
from memtool.processor.mboot_processor import MbootProcessor


class MIMXRT11XX(MIMXRT11XXProcessor, MbootProcessor):
    """TODO:summary line."""

    def __init__(self, name: str, ddr_type: str):
        """TODO:summary line."""
        super(MIMXRT11XX, self).__init__(name, ddr_type)
