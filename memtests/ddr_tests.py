# Copyright 2019-2025 NXP
"""Classes corresponding to various DDR memory tests."""
from memtool.common.config_data import ConfigData

from ..common.options import Options
from ..common.performance_monitor import PerformanceMonitor
from ..utils.constants import Const
from .phy_test import DDRBaseTest


class DDRMemoryTest(DDRBaseTest):
    """Base class for memory configuration tests."""

    # store checkbox values in class as they are not stored in the widget
    ck_vars = {}  # type: ignore

    # For memory tests, for quick boot 2D training should not be executed
    Train2DDisabled = '0'
    initial_train_2d = None

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from BaseTest."""
        super(DDRMemoryTest, cls).update_config_params(config_data)

        if Options.get_instance().get_snps_phy_boot_options().quick_boot():
            # set function to quick boot
            config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_QUICK_BOOT)

            # do not execute 2D training; note that this will be passed to the application through dcd.bin
            DDRMemoryTest.initial_train_2d = config_data.train_2d
            # this must be set also in overwrite_params because it will be overwritten at import ds
            config_data.params[Const.PARAM_S_APP][Const.OVERWRITE_TEST_PARAMS]\
                [Const.PARAM_S_SYS_TRAIN_2D] = DDRMemoryTest.Train2DDisabled
        else:
            # set function to full init (exec firmware)
            config_data.update_sys_params(Const.PARAM_S_SYS_FUNCTION, Const.PHY_FULL_INIT)

        # Update test parameters according to Performance Monitor options.
        perf_mon_config = PerformanceMonitor.get_instance().get_perf_mon_config()
        perf_mon_enable = perf_mon_config.get_perf_mon_enable()
        if perf_mon_enable:
            config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS]['perf_mon_enable'] = perf_mon_enable
            perf_mon_events = perf_mon_config.get_perf_mon_events()
            perf_mon_events_vals = []
            for perf_mon_event in perf_mon_events:
                perf_mon_events_vals.append(perf_mon_event.value.value)
            config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS]['perf_mon_events'] = perf_mon_events_vals

    def use_system_manager(self) -> bool:
        """Check if System Manager (SM) should be used for building DDR memory test application.

        By default, if processor is SM controlled,
        SM image should be imported in the final image for DDR memory tests.

        @return: True if processor is controlled by SM, False otherwise.
        """
        return self.processor.is_system_manager_on()

    @classmethod
    def restore_config_params(cls, config_data: ConfigData):  # type: ignore
        """Restore parameters."""
        if Options.get_instance().get_snps_phy_boot_options().quick_boot():
            # restore 2D training status
            config_data.train_2d = DDRMemoryTest.initial_train_2d  # type: ignore


class ReadWriteTest(DDRMemoryTest):
    """Base class for implementing Read / Write Tests."""

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(ReadWriteTest, cls).update_config_params(config_data)


class WRCTest(ReadWriteTest):
    """Class implementing Write-Read-Compare Test."""

    ID = 101
    NAME = 'Write-Read-Compare'


class OnlyReadTest(ReadWriteTest):
    """Class implementing Only-Read Test."""

    ID = 105
    NAME = 'Only-Read'


class OnlyWriteTest(ReadWriteTest):
    """Class implementing Only-Read Test."""

    ID = 106
    NAME = 'Only-Write'


class BISTTurnaroundTest(DDRMemoryTest):
    """Base class for BIST1Turnaround / BIST2Turnaround / BIST4Turnaround Tests."""

    def use_system_manager(self) -> bool:
        """Check if System Manager (SM) should be used for building BIST memory test application.

        @return: False because BIST test is by default run without SM (it could be run with SM also).
        """
        return False

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(BISTTurnaroundTest, cls).update_config_params(config_data)

        # Memory test pattern size for BIST tests is 40 bytes / 4 bytes = 10
        # padding must be added up to 16 test parameters length.
        # size refleted in flags will be actuale size of the BIST test pattern, which is 10
        if Const.PARAM_TEST_PARAMS in config_data.params[Const.PARAM_S_APP]:
            test_params = config_data.params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS]
            if Const.PARAM_TEST_PARAMS_PARAMS in test_params:
                pattern = test_params[Const.PARAM_TEST_PARAMS_PARAMS]
                if pattern != '':
                    padding_size = Const.PARAM_TEST_PARAMS_SIZE - len(pattern.strip('[ ]').split(','))
                    test_params[Const.PARAM_TEST_PARAMS_PARAMS] = pattern[:-1] + ', 0x0' * padding_size + pattern[-1]


class BIST1Turnaround(BISTTurnaroundTest):
    """Class implementing BIST1Turnaround Test."""

    ID = 107
    NAME = 'BIST-1Write-1Read-Turnaround'


class BIST2Turnaround(BISTTurnaroundTest):
    """Class implementing BIST2Turnaround Test."""

    ID = 108
    NAME = 'BIST-2Write-2Read-Turnaround'


class BIST4Turnaround(BISTTurnaroundTest):
    """Class implementing BIST4Turnaround Test."""

    ID = 109
    NAME = 'BIST-4Write-4Read-Turnaround'


class BISTNoTurnaround(BISTTurnaroundTest):
    """Class implementing BISTNoTurnaround Test."""

    ID = 110
    NAME = 'BIST-No-Turnaround'

    def get_test_window_class_name(self) -> str:
        """Get UI class name."""
        return self.__name__ + 'TestWindow'  # type: ignore


class WOZTest(DDRMemoryTest):
    """Base Class for implementing Walking Zero and Walking One Tests."""

    def __init__(self, config_data: ConfigData):
        """TODO:summary line."""
        super(WOZTest, self).__init__(config_data)

        # Handle unusual params - until they are treated uniformly in upper layers
        params = self.config_data.params
        if Const.PARAM_TEST_PARAMS_FLAGS not in params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS]:
            custom_flags = {
                '1_byte_access': 1,
                '2_byte_access': 2,
                '4_byte_access': 4
            }
            flags = 0
            for f, custom_flag in custom_flags.items():
                if f in params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS]:
                    if params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][f]:
                        flags += custom_flag
                    del params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][f]
            params[Const.PARAM_S_APP][Const.PARAM_TEST_PARAMS][Const.PARAM_TEST_PARAMS_FLAGS] = flags

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(WOZTest, cls).update_config_params(config_data)


class WOTest(WOZTest):
    """Class implementing Walking Ones Test."""

    ID = 102
    NAME = 'Walking Ones'


class WZTest(WOZTest):
    """Class implementing Walking Zeros Test."""

    ID = 103
    NAME = 'Walking Zeros'


class EccQuickTest(DDRMemoryTest):
    """Class implementing ECC Quick Test."""

    ID = 500
    NAME = 'ECC Quick Test'

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(EccQuickTest, cls).update_config_params(config_data)


class EccTest(DDRMemoryTest):
    """Class implementing ECC Test."""

    ID = 501
    NAME = 'ECC Test'

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(EccTest, cls).update_config_params(config_data)


class MemcpyThroughputTest(DDRMemoryTest):
    """Class implementing Throughput Test."""

    ID = 600
    NAME = 'Memcpy Throughput Test'

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(MemcpyThroughputTest, cls).update_config_params(config_data)


class StressTests(DDRMemoryTest):
    """Class implementing DDR config stress tests."""

    ID = 300
    NAME = 'Stress tests'

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(StressTests, cls).update_config_params(config_data)


class Memtester(DDRMemoryTest):
    """Class implementing DDR config stress tests."""

    ID = 400
    NAME = 'Memtester'

    @classmethod
    def update_config_params(cls, config_data: ConfigData):  # type: ignore
        """Override update_config_params from DDRMemoryTest."""
        super(Memtester, cls).update_config_params(config_data)
