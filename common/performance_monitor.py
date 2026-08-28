# Copyright 2023-2025 NXP
"""Performance Monitor logic and configuration."""
import logging
from enum import Enum

from memtool.common.base_test import TestStatus
from memtool.common.config_data import ConfigData
from memtool.common.factories import BackendFactory, Singleton
from memtool.utils.constants import Const

logger = logging.getLogger(__name__)


class PerfMonEvent:
    """Performance Monitor Event."""
    value = 0
    description = ''

    def __init__(self, value: int, description: str):
        """Constructor of Performance Monitor Event.

        @param value: Value as int is value to set PMLCAn[EVENT] field.
        @param description: Description as string to be displayed in UI.
        """
        self.value = value
        self.description = description


class PerfMonEventID(Enum):
    """Performance Monitor Event ID."""
    REF_0 = PerfMonEvent(0x00, 'No event')
    REF_12 = PerfMonEvent(0x0C, 'Number of read - modify - writes that are required due to ECC')
    REF_13 = PerfMonEvent(0x0D, 'Number of times a read is reordered ahead of another transaction')
    REF_14 = PerfMonEvent(0x0E, 'Number of times a write is reordered ahead of another transaction')
    REF_15 = PerfMonEvent(0x0F, 'Number of internal controller cycles DDR controller samples data from '
                                'DDR PHY for reads')
    REF_16 = PerfMonEvent(0x10, 'Number of internal controller cycles DDR controller samples data from '
                                'DDR PHY for writes')
    REF_17 = PerfMonEvent(0x11, 'Number of pipelined reads that were page misses')
    REF_18 = PerfMonEvent(0x12, 'Number of pipelined reads or writes that were page misses')
    REF_19 = PerfMonEvent(0x13, 'Number of non-pipelined reads that were page misses')
    REF_22 = PerfMonEvent(0x16, 'Number of non-pipelined reads or writes that were page misses')
    REF_23 = PerfMonEvent(0x17, 'Number of pipelined reads that were page hits')
    REF_24 = PerfMonEvent(0x18, 'Number of pipelined reads or writes that were page hits')
    REF_25 = PerfMonEvent(0x19, 'Number of non-pipelined reads that were page hits')
    REF_26 = PerfMonEvent(0x1A, 'Number of non-pipelined reads or writes that were page hits')
    REF_27 = PerfMonEvent(0x1B, 'Number of precharges issued to DRAM that are not caused by a refresh')
    REF_28 = PerfMonEvent(0x1C, 'Number of page misses for oldest transaction')
    REF_31 = PerfMonEvent(0x1F, 'Number of page hits for oldest transaction')
    REF_59 = PerfMonEvent(0x3B, 'Number of precharges including PRE_ALL commands for refreshes')
    REF_61 = PerfMonEvent(0x3D, 'Number of precharges due to bank collision')
    REF_63 = PerfMonEvent(0x3F, 'Number of cycles that commands are stalled due to lack of resources for '
                                'DRAM access timings')
    PMC2_72 = PerfMonEvent(0x48, 'Number of cycles the scheduler is empty')
    PMC2_73 = PerfMonEvent(0x49, 'Number of filtered read transactions')
    PMC3_72 = PerfMonEvent(0x48, 'Number of cycles the scheduler is full')
    PMC3_73 = PerfMonEvent(0x49, 'Number of filtered write transactions')
    PMC4_72 = PerfMonEvent(0x48, 'Number of transactions that load a read for a read-modify-write')
    PMC4_73 = PerfMonEvent(0x49, 'Number of filtered read beats returned')
    PMC5_72 = PerfMonEvent(0x48, 'Number of times medium priority read is loaded to scheduler')
    PMC6_64 = PerfMonEvent(0x40, 'Number of cycles interface is blocked for a refresh '
                                 '(only valid for all-bank refresh)')
    PMC6_72 = PerfMonEvent(0x48, 'Number of times low priority read is loaded to scheduler')
    PMC7_64 = PerfMonEvent(0x40, 'Number of cycles the scheduler is half full')
    PMC7_65 = PerfMonEvent(0x41, 'Number of times a write is loaded to scheduler')
    PMC8_64 = PerfMonEvent(0x40, 'This signal asserts each time the read / write bias is switched for arbitration')
    PMC8_65 = PerfMonEvent(0x41, 'Number of cycles the scheduler is 1 / 4 full')
    PMC9_66 = PerfMonEvent(0x42, 'Number of cycles the scheduler is 3 / 4 full')
    PMC10_66 = PerfMonEvent(0x42, 'Number of times high priority read is loaded to scheduler')
    PMC0_0 = PerfMonEvent(0x00, 'Clock cycles')


class PerfMonSuite:
    """Performance Monitor Suite is a logical group of performance monitor events."""
    description = ''
    events = list(PerfMonEventID)

    def __init__(self, description: str, events: list[PerfMonEventID]):
        """Constructor of Performance Monitor Suite.

        @param description: Description as string to be displayed in UI
        @param events: List of performance monitor events' ids.
        """
        self.description = description
        self.events = events


class PerfMonEventsSuiteID(Enum):
    """Performance Monitor Events Suite ID."""
    SUITE_0 = PerfMonSuite('Custom', [])
    SUITE_1 = PerfMonSuite('Read / Write page hits / misses', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_17, PerfMonEventID.REF_18, PerfMonEventID.REF_19,
        PerfMonEventID.REF_22, PerfMonEventID.REF_23, PerfMonEventID.REF_24, PerfMonEventID.REF_25,
        PerfMonEventID.REF_26, PerfMonEventID.REF_0, PerfMonEventID.REF_0])
    SUITE_2 = PerfMonSuite('Read / Write loaded to scheduler', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.PMC5_72, PerfMonEventID.PMC6_72, PerfMonEventID.PMC7_65,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.PMC10_66])
    # Events from this suite are de-featured but available for i.MX93 while for i.MX95 are no longer available.
    # SUITE_3 = PerfMonSuite('Read / Write filtered transactions', [
    #     PerfMonEventID.PMC0_0, PerfMonEventID.REF_0, PerfMonEventID.PMC2_73, PerfMonEventID.PMC3_73,
    #     PerfMonEventID.PMC4_73, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
    #     PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0])
    SUITE_4 = PerfMonSuite('Read / Write cycles', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_15, PerfMonEventID.REF_16, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0])
    SUITE_5 = PerfMonSuite('Precharges', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_27, PerfMonEventID.REF_59, PerfMonEventID.REF_61,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0])
    SUITE_6 = PerfMonSuite('Scheduler fullness', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_0, PerfMonEventID.PMC2_72, PerfMonEventID.PMC3_72,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.PMC7_64,
        PerfMonEventID.PMC8_65, PerfMonEventID.PMC9_66, PerfMonEventID.REF_0])
    SUITE_7 = PerfMonSuite('Reordered transactions', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_13, PerfMonEventID.REF_14, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0])
    SUITE_8 = PerfMonSuite('Read - modify - writes (ECC)', [
        PerfMonEventID.PMC0_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_12,
        PerfMonEventID.PMC4_72, PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0])


class PerfMonConfig:
    """Performance monitor configuration."""

    def __init__(self, perf_mon_enable: bool, perf_mon_suite: PerfMonEventsSuiteID,
                 perf_mon_events: list[PerfMonEventID]):
        """Constructor."""
        self.__perf_mon_enable = perf_mon_enable
        self.__perf_mon_suite = perf_mon_suite
        self.__perf_mon_events = perf_mon_events

    def get_perf_mon_enable(self) -> bool:
        """Get performance monitor enable state.

        @return: True if performance monitor is enabled, False otherwise.
        """
        return self.__perf_mon_enable

    def set_perf_mon_enable(self, value: bool) -> None:
        """Set performance monitor enable.

        @param value: True if performance monitor is enabled, False otherwise.
        """
        self.__perf_mon_enable = value

    def get_perf_mon_suite(self) -> PerfMonEventsSuiteID:
        """Get performance monitor suite.

        @return: Performance monitor events suite id.
        """
        return self.__perf_mon_suite

    def set_perf_mon_suite(self, value: PerfMonEventsSuiteID) -> None:
        """Set performance monitor suite.

        @param value: Performance monitor events suite id to be set.
        """
        self.__perf_mon_suite = value

    def get_perf_mon_events(self) -> list[PerfMonEventID]:
        """Get performance monitor events.

        @return: Performance monitor events.
        """
        return self.__perf_mon_events

    def set_perf_mon_events(self, value: list[PerfMonEventID]) -> None:
        """Set performance monitor events.

        @param value: Performance monitor events to be set.
        """
        self.__perf_mon_events = value


class PerfMonCnt:
    """Performance Monitor Counter."""
    address = 0x0  # Address of counter.
    value = 0x0  # Value of counter.
    size = 4  # Size in bytes of counter.

    def __init__(self, address: int = 0x0, size: int = 4, value: int = 0) -> None:
        """Constructor of Performance Monitor Counter.

        @param address: Address of counter.
        @param size: Size in bytes of counter.
        @param value: Value of counter.
        """
        self.address = address
        self.size = size
        self.value = value


class PerfMonData:
    """Performance Monitor Data."""

    class CollectStatus(Enum):
        """Performance Monitor Data Collect Status."""
        NOT_AVAILABLE = 0
        COLLECTING = 1
        COLLECTED = 2
        COLLECT_FAIL = 3

    _test_name: str = ''  # Name of the test.
    _counters_values: list[int] = []  # Values of the counters.
    _status: CollectStatus = CollectStatus.NOT_AVAILABLE  # Status of collected data.
    _reads: int = 0  # Number of read transactions.
    _writes: int = 0  # Number of write transactions.
    _exec_time_ms: int = 0  # Test execution time in ms.
    _ddr_bandwidth: int = 0  # DDR bandwidth in B/s.

    def __init__(self, test_name: str = '', status: CollectStatus = CollectStatus.NOT_AVAILABLE,
                 counters_values: list[int] = []) -> None:
        """Constructor of PerfMonData."""
        self._test_name = test_name
        self._counters_values = counters_values
        self._status = status
        self._reads = 0
        self._writes = 0
        self._exec_time_ms = 0
        self._ddr_bandwidth = 0
        self._ddr_efficiency = 0

    def set_test_name(self, test_name: str) -> None:
        """Set name of the test.

        @param test_name: Name of the test.
        """
        self._test_name = test_name

    def get_test_name(self) -> str:
        """Get name of the test.

        @return Name of the test.
        """
        return self._test_name

    def set_counters_values(self, counters_values: list[int]) -> None:
        """Set values of the counters.

        @param counters_values: Values of the counters.
        """
        self._counters_values = counters_values

    def get_counters_values(self) -> list[int]:
        """Get values of the counters.

        @return Values of the counters.
        """
        return self._counters_values

    def set_collect_status(self, status: CollectStatus) -> None:
        """Set status of data collection.

        @param status: Status of data collection.
        """
        self._status = status

    def get_collect_status(self) -> CollectStatus:
        """Get status of data collection.

        @return Status of data collection.
        """
        return self._status

    def set_reads(self, reads: int) -> None:
        """Set number of read transactions.

        @param reads: Number of read transactions.
        """
        self._reads = reads

    def get_reads(self) -> int:
        """Get number of read transactions.

        @return Number of read transactions.
        """
        return self._reads

    def set_writes(self, writes: int) -> None:
        """Set number of write transactions.

        @param writes: Number of write transactions.
        """
        self._writes = writes

    def get_writes(self) -> int:
        """Get number of write transactions.

        @return Number of write transactions.
        """
        return self._writes

    def set_exec_time(self, exec_time: int) -> None:
        """Set execution time in ms.

        @param exec_time: Execution time in ms.
        """
        self._exec_time_ms = exec_time

    def get_exec_time(self) -> int:
        """Get execution time.

        @return Execution time in ms.
        """
        return self._exec_time_ms

    def set_ddr_bandwidth(self, ddr_bandwidth: int) -> None:
        """Set DDR bandwidth in B/s.

        @param ddr_bandwidth: DDR bandwidth in B/s.
        """
        self._ddr_bandwidth = ddr_bandwidth

    def get_ddr_bandwidth(self) -> int:
        """Get DDR bandwidth in B/s.

        @return DDR bandwidth in B/s.
        """
        return self._ddr_bandwidth

    def set_ddr_efficiency(self, ddr_efficiency: int) -> None:
        """Set DDR efficiency in %.

        @param ddr_efficiency: DDR efficiency in %.
        """
        self._ddr_efficiency = ddr_efficiency

    def get_ddr_efficiency(self) -> int:
        """Get DDR efficiency in %.

        @return DDR efficiency in %.
        """
        return self._ddr_efficiency


class PerformanceMonitor(metaclass=Singleton):
    """Performance Monitor singleton class."""

    # List of soc names for which performance monitor is supported.
    __supported_soc_names: list[str] = ["MIMX93", "MIMX95"]

    # Performance monitor counters.
    __counters_imx93: list[PerfMonCnt] = [PerfMonCnt(0x4e300e18, size=8), PerfMonCnt(0x4e300e28),
                                PerfMonCnt(0x4e300e38), PerfMonCnt(0x4e300e48),
                                PerfMonCnt(0x4e300e58), PerfMonCnt(0x4e300e68),
                                PerfMonCnt(0x4e300e78), PerfMonCnt(0x4e300e88),
                                PerfMonCnt(0x4e300e98), PerfMonCnt(0x4e300ea8),
                                PerfMonCnt(0x4e300eb8)]
    __counters_imx95: list[PerfMonCnt] = [PerfMonCnt(0x5E090e18, size=8), PerfMonCnt(0x5E090e28),
                                PerfMonCnt(0x5E090e38), PerfMonCnt(0x5E090e48),
                                PerfMonCnt(0x5E090e58), PerfMonCnt(0x5E090e68),
                                PerfMonCnt(0x5E090e78), PerfMonCnt(0x5E090e88),
                                PerfMonCnt(0x5E090e98), PerfMonCnt(0x5E090ea8),
                                PerfMonCnt(0x5E090eb8)]

    __counters = __counters_imx93

    # Performance monitor configuration.
    __perf_mon_config: PerfMonConfig = PerfMonConfig(False, PerfMonEventsSuiteID.SUITE_0, [
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0, PerfMonEventID.REF_0,
        PerfMonEventID.REF_0, PerfMonEventID.REF_0])

    # Performance monitor data for each performance monitor suite.
    __perf_mon_data_dic: dict[PerfMonEventsSuiteID, PerfMonData] = dict.fromkeys(
            PerfMonEventsSuiteID,
            PerfMonData('', PerfMonData.CollectStatus.NOT_AVAILABLE, [0 for i in range(0, len(__counters))]))

    # Config data.
    __config_data: ConfigData = ConfigData.default()

    @staticmethod
    def get_instance():  # type: ignore
        """Get singleton instance of performance monitor."""
        return PerformanceMonitor()

    def is_supported(self, soc_name: str) -> bool:
        """Get if performance monitor is supported for given soc name.

        @param soc_name: Soc name.
        @return: True if performance monitor is supported, False otherwise.
        """
        return True if soc_name in self.__supported_soc_names else False

    def is_enabled(self, soc_name: str) -> bool:
        """Get if performance monitor is enabled for given soc name.

        @param soc_name: Soc name.
        @return: True if performance monitor is enabled, False otherwise.
        """
        if self.is_supported(soc_name):
            return self.__perf_mon_config.get_perf_mon_enable()
        else:
            return False

    def start_session(self, test_name: str, config_data: ConfigData) -> None:
        """Start performance monitor session for given test name.

        @param config_data: Config data.
        @param test_name: Test name.
        """
        self.__counters = self.__counters_imx93 if config_data.soc_name == 'MIMX93' else self.__counters_imx95
        perf_mon_suite = self.__perf_mon_config.get_perf_mon_suite()
        perf_mon_data = PerfMonData(test_name, PerfMonData.CollectStatus.COLLECTING, [0 for counter in self.__counters])
        self.__perf_mon_data_dic[perf_mon_suite] = perf_mon_data
        self.__config_data = config_data
        self._clear_counters()

    def end_session(self, test_status: TestStatus) -> None:
        """End current performance monitor session."""
        perf_mon_suite = self.__perf_mon_config.get_perf_mon_suite()
        if test_status == TestStatus.PASS:
            self._read_counters()
            self._set_counters(perf_mon_suite)
            self._compute_perf_mon_data(perf_mon_suite)

        if perf_mon_suite in self.__perf_mon_data_dic:
            if test_status == TestStatus.PASS:
                collect_status = PerfMonData.CollectStatus.COLLECTED
            else:
                collect_status = PerfMonData.CollectStatus.COLLECT_FAIL
            self.__perf_mon_data_dic[perf_mon_suite].set_collect_status(collect_status)

    def _clear_counters(self) -> None:
        """Clear values of counters."""
        for counter in self.__counters:
            counter.value = 0

    def _read_counters(self) -> None:
        """Read performance monitor counters."""
        if self.__config_data is None:
            return

        try:
            channel = BackendFactory.make_unique_instance(self.__config_data.connect_params)
            channel.init_channel(self.__config_data)
            for counter in self.__counters:
                value = channel.read_symbol((counter.address, counter.size, 1))
                if value is not None:
                    counter.value = value
                else:
                    logger.error(f"\nFailed to read value from {hex(counter.address)}\n")
            channel.close()
        except Exception as e:
            logger.error(str(e))

    def _set_counters(self, perf_mon_suite: PerfMonEventsSuiteID) -> None:
        """Set current read values of the counters into performance monitor data of given performance monitor suite.

        @param perf_mon_suite: Performance monitor suite ID.
        """
        if perf_mon_suite in self.__perf_mon_data_dic:
            values = [counter.value for counter in self.__counters]
            self.__perf_mon_data_dic[perf_mon_suite].set_counters_values(values)

    def _compute_perf_mon_data(self, perf_mon_suite: PerfMonEventsSuiteID) -> None:
        """Compute performance monitor data statistics for given performance monitor suite.

        @param perf_mon_suite: Performance monitor suite ID.
        """
        reads, writes = self._compute_reads_writes(perf_mon_suite)
        counters = self._get_counters_values(perf_mon_suite)
        clock_cycles = 0
        exec_time_ms = 0
        if len(counters) > 0:
            clock_cycles = counters[0]
        ddr_bandwidth = 0
        if self.__config_data is not None:
            ddr_data_rate_Mbps = 0
            if 'ddrDataRateMbps' in self.__config_data.params[Const.PARAM_S_BASIC]:
                ddr_data_rate_Mbps = int(self.__config_data.params[Const.PARAM_S_BASIC]['ddrDataRateMbps'])
            if Const.PARAM_S_BASIC_NUM_PSTATES in self.__config_data.params[Const.PARAM_S_BASIC]:
                num_pstates = int(self.__config_data.params[Const.PARAM_S_BASIC][Const.PARAM_S_BASIC_NUM_PSTATES])
                if num_pstates == 1 and clock_cycles != 0 and ddr_data_rate_Mbps != 0:
                    ddr_frequency = ddr_data_rate_Mbps / 2
                    # For now execution time can only be computed accurate only if test runs with one single frequency.
                    exec_time_ms = int(clock_cycles / (ddr_frequency * pow(10, 3)))
                    # DDR bandwidth B/s = 32 bytes * total number of transactions / execution time in seconds.
                    ddr_bandwidth = int(32 * (reads + writes) / (exec_time_ms * pow(10, -3)))

        cycles_reads, cycles_writes = self._compute_cycles_reads_writes(perf_mon_suite)
        ddr_efficiency = 0
        if clock_cycles != 0:
            ddr_efficiency = int(100 * (cycles_reads + cycles_writes) / clock_cycles)
        if perf_mon_suite in self.__perf_mon_data_dic:
            self.__perf_mon_data_dic[perf_mon_suite].set_reads(reads)
            self.__perf_mon_data_dic[perf_mon_suite].set_writes(writes)
            self.__perf_mon_data_dic[perf_mon_suite].set_exec_time(exec_time_ms)
            self.__perf_mon_data_dic[perf_mon_suite].set_ddr_bandwidth(ddr_bandwidth)
            self.__perf_mon_data_dic[perf_mon_suite].set_ddr_efficiency(ddr_efficiency)

    def _compute_reads_writes(self, perf_mon_suite: PerfMonEventsSuiteID) -> tuple[int, int]:
        """Compute number of read /write transactions based on currently read values of counters.

        @param perf_mon_suite: Performance monitor suite ID.
        @return: Number of read transactions and number of write transactions for a given
        performance monitor suite.
        """
        counters = self._get_counters_values(perf_mon_suite)
        no_read_transactions = 0
        no_write_transactions = 0
        if perf_mon_suite is PerfMonEventsSuiteID.SUITE_0:
            events = self.__perf_mon_config.get_perf_mon_events()
        else:
            events = perf_mon_suite.value.events
        if len(events) == len(counters):
            # Filtered read / write transactions.
            if PerfMonEventID.PMC2_73 in events and PerfMonEventID.PMC3_73 in events:
                no_read_transactions = counters[events.index(PerfMonEventID.PMC2_73)]
                no_write_transactions = counters[events.index(PerfMonEventID.PMC3_73)]
            # Number of times read / write is loaded to scheduler.
            elif PerfMonEventID.PMC5_72 in events and PerfMonEventID.PMC6_72 in events and \
                    PerfMonEventID.PMC7_65 in events and PerfMonEventID.PMC10_66 in events:
                no_read_transactions += counters[events.index(PerfMonEventID.PMC5_72)]
                no_read_transactions += counters[events.index(PerfMonEventID.PMC6_72)]
                no_write_transactions = counters[events.index(PerfMonEventID.PMC7_65)]
                no_read_transactions += counters[events.index(PerfMonEventID.PMC10_66)]
            # Number of read / write page misses / hits.
            elif PerfMonEventID.REF_17 in events and PerfMonEventID.REF_18 in events and \
                    PerfMonEventID.REF_19 in events and PerfMonEventID.REF_22 in events and \
                    PerfMonEventID.REF_23 in events and PerfMonEventID.REF_24 in events and \
                    PerfMonEventID.REF_25 in events and PerfMonEventID.REF_26 in events:
                no_read_transactions += counters[events.index(PerfMonEventID.REF_17)]
                no_write_transactions += counters[events.index(PerfMonEventID.REF_18)]
                no_read_transactions += counters[events.index(PerfMonEventID.REF_19)]
                no_write_transactions += counters[events.index(PerfMonEventID.REF_22)]
                no_read_transactions += counters[events.index(PerfMonEventID.REF_23)]
                no_write_transactions += counters[events.index(PerfMonEventID.REF_24)]
                no_read_transactions += counters[events.index(PerfMonEventID.REF_25)]
                no_write_transactions += counters[events.index(PerfMonEventID.REF_26)]
                no_write_transactions -= no_read_transactions

        return no_read_transactions, no_write_transactions

    def _compute_cycles_reads_writes(self, perf_mon_suite: PerfMonEventsSuiteID) -> tuple[int, int]:
        """Compute cycles for read /write transactions based on currently read values of counters.

        @param perf_mon_suite: Performance monitor suite ID.
        @return: Cycles for read transactions and cycles for write transactions for given
        performance monitor suite.
        """
        counters = self._get_counters_values(perf_mon_suite)
        cycles_reads = 0
        cycles_writes = 0
        if perf_mon_suite is PerfMonEventsSuiteID.SUITE_0:
            events = self.__perf_mon_config.get_perf_mon_events()
        else:
            events = perf_mon_suite.value.events
        if len(events) == len(counters):
            # Number of internal controller cycles DDR controller samples data from DDR PHY for reads / writes.
            if PerfMonEventID.REF_15 in events and PerfMonEventID.REF_16 in events:
                cycles_reads = counters[events.index(PerfMonEventID.REF_15)]
                cycles_writes = counters[events.index(PerfMonEventID.REF_16)]

        return cycles_reads, cycles_writes

    def _get_counters_values(self, perf_mon_suite: PerfMonEventsSuiteID) -> list[int]:
        """Get values of counters for given performance monitor suite.

        @param perf_mon_suite: Performance monitor suite ID.
        @return: Values of counters for given performance monitor suite.
        """
        perf_mon_data = self.__perf_mon_data_dic.get(perf_mon_suite, None)
        counters = None if perf_mon_data is None else perf_mon_data.get_counters_values()
        if counters is not None:
            return counters
        else:
            return [0 for i in range(0, len(self.__counters))]

    def get_perf_mon_config(self) -> PerfMonConfig:
        """Get Performance Monitor configuration.

        @return: Performance monitor configuration.
        """
        return self.__perf_mon_config

    def get_perf_mon_data(self, perf_mon_suite: PerfMonEventsSuiteID) -> PerfMonData:
        """Get performance monitor data for given performance monitor suite.

        @param perf_mon_suite: Performance monitor suite ID.
        @return: Get performance monitor data for for given performance monitor suite.
        """
        empty_perf_mon_data = PerfMonData(test_name='', status=PerfMonData.CollectStatus.NOT_AVAILABLE,
                                          counters_values=[0 for i in range(0, len(self.__counters))])
        return self.__perf_mon_data_dic.get(perf_mon_suite, empty_perf_mon_data)
