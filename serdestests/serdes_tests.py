# Copyright 2023-2025 NXP
"""SerDes tests class."""
import sys
import time
from typing import Optional, Tuple

from memtool.common.app import ApplicationCommand
from memtool.common.base_test import BaseTest, TestStatus
from memtool.common.config_data import ConfigData
from memtool.common.factories import BackendFactory
from memtool.serdestests.read_mdio import MDIO
from memtool.serdestests.reset import LaneReset


class SerdesTestRegAccess(BaseTest):
    """Base class for serdes tests that do not run on target. Just register access."""

    def __init__(self, config_data: ConfigData):
        """Init."""
        super(SerdesTestRegAccess, self).__init__(config_data)
        self.test_status = TestStatus.PASS
        self.channel = BackendFactory.make_unique_instance(self.config_data.connect_params)
        self.channel.init_channel()

        try:
            if not self.channel.is_alive():
                self.channel.open(config_data)
                assert self.channel.is_alive()
        except Exception:
            self.channel.close()
            raise Exception("Connection issue")

    def read_results(self) -> TestStatus:
        """Override read results for serdes tests that do not run on target."""
        self.results['records'] = []
        self.results['num_records'] = 0
        self.results['app_state'] = 0x11223344
        self.results['err_capt_regs'] = 0
        self.results['debug'] = 0
        self.results['debug_regs'] = 0
        record = {'test_id': 304, 'state': 1}
        if self.test_status == TestStatus.FAIL:
            record = {'test_id': 304, 'state': 0}
        self.results['records'].append(record)

        return self.test_status


class SerdesTestApp(BaseTest):
    """Base class for serdes tests that run on target."""

    def get_param_symbol(self, param: str) -> Optional[Tuple[int, int, int]]:
        """Override get_param_symbol Map from BaseTest."""
        symb = {
            'test': (self.app.sym_table['TEST_IN'] + 0x0, 4, 1),
            'pattern': (self.app.sym_table['TEST_IN'] + 0x4, 2, 1),
            'loopback': (self.app.sym_table['TEST_IN'] + 0x6, 1, 1),
            'countwindow': (self.app.sym_table['TEST_IN'] + 0x7, 1, 1),
            'path': (self.app.sym_table['TEST_IN'] + 0x8, 4, 1),
            'laneNumber': (self.app.sym_table['TEST_IN'] + 0xC, 1, 1),
            'insertErrorCount': (self.app.sym_table['TEST_IN'] + 0xD, 1, 1),
            'pllNumber': (self.app.sym_table['TEST_IN'] + 0xE, 1, 1),
            'mode': (self.app.sym_table['TEST_IN'] + 0xF, 1, 1),
            'pattern_length': (self.app.sym_table['TEST_IN'] + 0x10, 4, 1),
            'double_speed': (self.app.sym_table['TEST_IN'] + 0x14, 1, 1),
            'refClock': (self.app.sym_table['TEST_IN'] + 0x15, 1, 1),
            'serdesInstance': (self.app.sym_table['TEST_IN'] + 0x16, 1, 1),
            'protocol': (self.app.sym_table['TEST_IN'] + 0x18, 4, 1),
            'isEvkBoard': (self.app.sym_table['TEST_IN'] + 0x1C, 1, 1),
            'ioExpanderConfig': (self.app.sym_table['TEST_IN'] + 0x1D, 1, 1),
            'dataRateMbps': (self.app.sym_table['TEST_IN'] + 0x1E, 1, 1),
            'params': (self.app.sym_table['TEST_IN'] + 0x1F, 4, 16), }.get(param, None)
        if symb is None:
            self.logger.warning('Unknown parameter: %s!', param)
        return symb

    def execute_test(self) -> TestStatus:
        """Override method. Use self.get_param_symbol(k) for input params map."""
        if not self.is_waiting_for_input():
            self.logger.error('Application state is not waiting for input.')
            return TestStatus.FAIL

        for (k, v) in self.config_data.params['app']['test_params'].items():
            if v is not None:
                self.logger.info('Write input param %s = %s', k, v)
                if not self.channel.write_symbol(self.get_param_symbol(k), v):
                    self.logger.error('Input parameter %s could not be set to %s', k, v)
                    return TestStatus.FAIL
                time.sleep(0.1)
            else:
                self.logger.warning('Parameter %s value is None', k)

        result = self.channel.execute_command(cmd=ApplicationCommand.EXECUTE_TEST, data=None)
        return TestStatus.PASS if result else TestStatus.FAIL


class TX_Pattern_Generator(SerdesTestApp):
    """TX_Pattern_Generator test class."""

    ID = 306
    NAME = 'TX Pattern Generator'

    def process_results(self) -> None:
        """Results decoding for TX Pattern Generator test."""
        if ('records' in self.results) and (len(self.results['records']) > 0):
            super().process_results()
            if (self.results['records'][0]['data'][0] != 0) and ('40' not in self.results['records'][0]['data']):
                res = self.results['records'][0]['data'].split(',')
                self.logger.error('ERROR at TX Pattern Generator step %s' % int(res[2]))
            else:
                self.logger.info("TX Pattern Generator STARTED")


class Pattern_Checker(SerdesTestApp):
    """Pattern_Checker test class."""

    ID = 307
    NAME = 'RX Pattern Checker'

    def process_results(self) -> None:
        """Results decoding for Pattern Checker test."""
        if ('records' in self.results) and (len(self.results['records']) > 0):
            super().process_results()
            if (self.results['records'][0]['data'][0] != 0) and ('40' not in self.results['records'][0]['data']):
                res = self.results['records'][0]['data'].split(',')
                if int(res[2]) == int(3):
                    self.logger.error('ERROR at Pattern Checker. Detected %d errors' % int(res[3]))
                else:
                    self.logger.error('ERROR at Pattern Checker step %d' % int(res[2]))
            else:
                self.logger.info("Pattern Checker was executed")


class Start_TX_Pattern_Gen(SerdesTestApp):
    """Start_TX_Pattern_Gen test class."""

    ID = 303
    NAME = 'start_tx_pattern_gen'

    def process_results(self) -> None:
        """Results decoding for Start_TX_Pattern_Gen test."""
        if ('records' in self.results) and (len(self.results['records']) > 0):
            super().process_results()
            if (self.results['records'][0]['data'][0] != 0) and (self.results['records'][0]['data'][2] != 0):
                self.logger.error('ERROR at BIST step %d' % self.results['records'][0]['data'][2])
            else:
                self.logger.info("Pattern Generation STARTED")


class Stop_TX_Pattern_Gen(SerdesTestRegAccess):
    """Stop_TX_Pattern_Gen test class."""

    ID = 304
    NAME = 'stop_tx_pattern_gen'

    def load_dcd_and_app(self) -> TestStatus:
        """Override method."""
        laneReset = LaneReset(self.config_data, self.channel)
        if not laneReset.putLaneIntoReset(self.config_data.params, 'both'):
            self.test_status = TestStatus.FAIL

        # STEP 4: Write   SRDS(x)LN(W)TCSR3   0000 0000 0000 0000   0000 0000 0000 0000   Program: Reset Test Register
        laneOffset = 0x7AC + 0x100 * self.config_data.params['app']['test_params']['laneNumber']
        TCSR3_REG = self.config_data.params['serDesBase'] + laneOffset
        self.channel.write_symbol((TCSR3_REG, 4, 1), 0)

        if not laneReset.getLaneOutOfReset(self.config_data.params, 'both'):
            self.test_status = TestStatus.FAIL

        self.test_status = TestStatus.PASS
        return self.test_status


class Reset(SerdesTestRegAccess):
    """Reset test class."""

    ID = 305
    NAME = 'reset'

    def load_dcd_and_app(self) -> TestStatus:
        """Override method."""
        laneReset = LaneReset(self.config_data, self.channel)
        path = 'Rx' if (self.config_data.params['app']['test_params']['path'] == 1) else 'Tx'
        if not laneReset.putLaneIntoReset(self.config_data.params, path):
            self.test_status = TestStatus.FAIL

        if not laneReset.getLaneOutOfReset(self.config_data.params, path):
            self.test_status = TestStatus.FAIL

        self.test_status = TestStatus.PASS
        return self.test_status

    def read_results(self) -> TestStatus:
        """Override method."""
        path = 'Rx' if (self.config_data.params['app']['test_params']['path'] == 1) else 'Tx'
        self.logger.info("Performed reset on " + path)
        return super().read_results()


class Power(SerdesTestRegAccess):
    """Power test class."""

    ID = 306
    NAME = 'power'

    def load_dcd_and_app(self) -> TestStatus:
        """Override method."""
        laneReset = LaneReset(self.config_data, self.channel)
        path = 'Rx' if (self.config_data.params['app']['test_params']['path'] == 1) else 'Tx'
        mode = self.config_data.params['app']['test_params']['mode']
        if mode == 1:
            if not laneReset.power_down_lane(self.config_data.params, path):
                self.test_status = TestStatus.FAIL
        else:
            if not laneReset.power_up_lane(self.config_data.params, path):
                self.test_status = TestStatus.FAIL

        self.test_status = TestStatus.PASS
        return self.test_status

    def read_results(self) -> TestStatus:
        """Override method."""
        path = 'Rx' if (self.config_data.params['app']['test_params']['path'] == 1) else 'Tx'
        mode = 'Off' if (self.config_data.params['app']['test_params']['mode'] == 1) else 'On'
        self.logger.info("Performed power " + mode + " on " + path)
        return super().read_results()


class BIST(SerdesTestApp):
    """Class implementing SerDes BIST Test."""

    ID = 300
    NAME = 'bist'
    BIST_ERR_CNT_DN = 0x00010000

    def process_results(self) -> None:
        """Results decoding for BIST test."""
        if ('records' in self.results) and (len(self.results['records']) > 0):
            super().process_results()
            processor_info = ConfigData.DEVICES_INFO[self.config_data.soc_name]
            is_layerscape = processor_info.is_lx2() or processor_info.is_la()
            if is_layerscape:
                step = int(self.results['records'][0]['data'][2])
            else:
                step = int(self.results['records'][0]['data'].split(',')[2])

            if step != 40:
                self.logger.error('ERROR at BIST step %s' % step)

                if is_layerscape:
                    # BIST configuration failure
                    if step == 1:
                        err_reg = self.results['records'][0]['data'][0]
                        # BIST fails at step 28 - CDR_LOCK check
                        self.logger.error('ERROR: PLL %d is not locked' % err_reg)

                    if step == 28:
                        # BIST fails at step 28 - CDR_LOCK check
                        self.logger.error('ERROR: CDR_LOCK was not asserted')

                    if step == 37:
                        self.logger.error('ERROR: BIST_PAT_SYNC was not asserted')

            else:
                # BIST success, step 40 is reached
                self.logger.info("BIST Test was executed")

                if is_layerscape:
                    insert_err = self.results['records'][0]['data'][1]
                    detect_err = self.results['records'][0]['data'][0]

                    if (detect_err == 0) and (insert_err == 0):
                        self.logger.info('CDR_LOCK was asserted')
                        self.logger.info('BIST_PAT_SYNC was asserted')

                    if insert_err == detect_err:
                        self.logger.info('Success! Inserted %d errors and detected %d!' % (insert_err, detect_err))

                    if self.results['records'][0]['data'][6] != self.BIST_ERR_CNT_DN:
                        self.logger.error("ERROR @ STEP 40: BIST status: 0 (should be 1).")
                        self.logger.info("TCSR3: 0x%8x\r\n" % self.results['records'][0]['data'][4])


    def read_results(self) -> TestStatus:
        """Results read for BIST test."""
        super().read_results()
        # Execute wait for errors and status bit to set only if PATT_SYNC was asserted
        if ('records' in self.results) and (len(self.results['records']) > 0):
            if self.results['records'][0]['state'] == 1:
                processor_info = ConfigData.DEVICES_INFO[self.config_data.soc_name]
                is_layerscape = processor_info.is_lx2() or processor_info.is_la()
                if is_layerscape:
                    self.wait_check_bist_layerscape()
                else:
                    self.wait_check_bist_imx()
            return TestStatus.from_state_value(self.results['records'][0]['state'])
        return TestStatus.FAIL

    def wait_check_bist_imx(self) -> None:
        """Wait for timeToWait to elapse in order to finish BIST."""
        # get timeToWait in seconds
        timeToWait = self.config_data.params['app']['test_params']['countwindow'] * 60
        if timeToWait > 0:
            self.logger.info("Time to run BIST to set was: %d seconds" % timeToWait)
            time.sleep(timeToWait % 1000)
            # reset target to stop BIST
            debug_res = self.channel.read_symbol(self.app.get_result_symbol('debug'))
            nb_errors = int(debug_res.split(',')[1])
            if nb_errors > 0:
                self.logger.error("Number of errors detected: %d" % nb_errors)
            self.channel.reset()

    def wait_check_bist_layerscape(self) -> None:
        """Bist status flag will be cleared at the end of BIST test.

        The time it takes to run depends on countWindow value.
        For values bigger than 10 for count window, time can be hours.
        We cannot sleep in the application that runs on target.
        Sleep here instead.
        """
        BIST_ERR_CNT = 0x0000FF00
        BIST_ERR_INS_OR_MASK = 0x08000000
        BIST_ERR_INS_AND_MASK = 0xF7FFFFFF

        # How much time it takes to insert an error bit on the board. This value is a guess.
        INSERT_ERROR_BIT_TIME_SEC = 2
        self.logger.info('Started to check BIST results')
        #  at this point BIST PAT_SYNC was asserted
        # execute check bist
        timeToWait = 1.5 * self.config_data.params['timeToWait']
        # STEP 39: Wait a no of seconds corresponding to the CountWindow length
        startSeconds = time.time()
        # The number of error bits requested to insert
        insertErrorCount = self.config_data.params['app']['test_params']['insertErrorCount']
        cw = self.config_data.params['app']['test_params']['countwindow']
        laneNumber = self.config_data.params['app']['test_params']['laneNumber']
        TCSR3_REG = self.config_data.params['serDesBase'] + 0x7AC + 0x100 * laneNumber

        # Wait for the (15) lnx_(W)_bist_status = 1 to be set
        while True:
            reg = self.channel.read_symbol((TCSR3_REG, 4, 1))
            # Read lnx_(W)_bist_err_cnt(7:0)
            errCNT = BIST_ERR_CNT & reg
            status = self.BIST_ERR_CNT_DN & reg
            errCNT = errCNT >> 8
            if status == self.BIST_ERR_CNT_DN:
                break

            while errCNT < insertErrorCount:
                # Check that the board has enough time to insert the error bits
                timeLeft = timeToWait - (time.time() - startSeconds)
                self.logger.info("Wait for flag BIST_ERR_CNT_DN to be set")
                if timeLeft <= INSERT_ERROR_BIT_TIME_SEC:
                    break
                # Insert error
                self.channel.write_symbol((TCSR3_REG, 4, 1), reg | BIST_ERR_INS_OR_MASK)
                time.sleep(0.8)
                self.channel.write_symbol((TCSR3_REG, 4, 1), reg | BIST_ERR_INS_OR_MASK)

                # STEP 23: Read   SRDS(x)LN(W)TCSR3
                reg = self.channel.read_symbol((TCSR3_REG, 4, 1))
                # Read lnx_(W)_bist_err_cnt(7:0)
                errCNT = BIST_ERR_CNT & reg
                # reset error insert flag
                self.channel.write_symbol((TCSR3_REG, 4, 1), reg & BIST_ERR_INS_AND_MASK)
                errCNT = errCNT >> 8
                self.logger.info("Detected errors =%d" % errCNT)
                sys.stdout.flush()

            time.sleep(1)

        # STEP 40: Read   SRDS(x)LN(W)TCSR3
        # Confirm (15): lnx_(W)_bist_status = 1   lnx_(W)_bist_err_cnt(7:0) = 0000 0000
        reg = self.channel.read_symbol((TCSR3_REG, 4, 1))

        # Confirm BIST_ERR_CNT_DN = 1 and ERR_CNT = 0
        errCNT = BIST_ERR_CNT & reg
        status = self.BIST_ERR_CNT_DN & reg
        errCNT = errCNT >> 8
        self.results['records'][0]['data'][2] = 40
        self.results['records'][0]['data'][0] = errCNT
        self.results['records'][0]['data'][1] = insertErrorCount
        self.results['records'][0]['data'][6] = status
        self.results['records'][0]['data'][4] = reg
        self.results['records'][0]['data'][5] = cw

        if status == self.BIST_ERR_CNT_DN:
            exectime = time.time() - startSeconds
            self.logger.info("Time wait for BIST_ERR_CNT_DN flag to set was: %d seconds" % exectime)

        if insertErrorCount != errCNT:
            if cw < 10 and insertErrorCount >= 0 and errCNT < insertErrorCount:
                # if count window is too short, cannot insert errors
                self.logger.info('Could not insert errors.')
                self.logger.info('Count window value is too short(%d).' % cw)
                self.logger.info('Increase count window value to at least 5.50E+11 and try again.')
            else:
                self.results['records'][0]['state'] = TestStatus.FAIL
                self.logger.error('ERROR! Inserted %d errors and detected %d' % (insertErrorCount, errCNT))


class JITTER_SCOPE(SerdesTestApp):
    """Class implementing SerDes JITTER Test."""

    ID = 301
    NAME = 'jitter_scope'
    BIST_ERR_CNT_DN = 0x00010000

    def process_results(self) -> None:
        """Results decoding for JITTER test."""
        if ('records' in self.results) and (len(self.results['records']) > 0):
            super().process_results()
            step = self.results['records'][0]['data'][2]
            if (self.results['records'][0]['data'][0] != 0) and (step != 0):
                self.logger.error('ERROR at JITTER step %d' % self.results['records'][0]['data'][2])

            if step == 1:
                # JITTER fails at step 1 - PLL not asserted
                self.logger.error('ERROR: PLL %d is not locked' % self.results['records'][0]['data'][0])

            if step == 10:
                # JITTER fails at step 10 - CDR_LOCK check
                self.logger.error('ERROR: CDR_LOCK was not asserted')

            noerrors = (0 == self.results['records'][0]['data'][0]) and (0 == self.results['records'][0]['data'][1])
            if (step == 11) and noerrors:
                print('CDR_LOCK was asserted')
        else:
            self.logger.error('ERROR: Jitter scope can not be run')

    def read_results(self) -> TestStatus:
        """Results read for JITTER test."""
        super().read_results()

        if ('records' in self.results) and (len(self.results['records']) > 0):
            step = self.results['records'][0]['data'][2]
            noerrors = (self.results['records'][0]['state'] == 1) and (step == 11)
            if noerrors:
                # Execute wait for errors and status bit to set only if PATT_SYNC was asserted
                test_step = 0
                pat_length = self.results['records'][0]['data'][6]
                print("steps_per_bit=%d" % self.results['records'][0]['data'][3])
                print("pattern_length=%d" % pat_length)
                total_possible_mismatch = self.results['records'][0]['data'][4]
                bits_per_interp = self.results['records'][0]['data'][5]
                steps_per_bit = self.results['records'][0]['data'][3]
                if steps_per_bit == 256:
                    bits_per_interp = 0.5
                elif steps_per_bit == 512:
                    bits_per_interp = 0.25
                roundUp = 1 if (pat_length % bits_per_interp) else 0
                iterations = int((pat_length / bits_per_interp + roundUp))  # * 128 * 2)
                iterations_read_one_time = int(self.app.get_test_result_symbol(0, 'jitter_step')[2] / 2)
                for itr in range(0, 2 * iterations):
                    reg = self.channel.read_symbol(self.app.get_test_result_symbol(itr, 'jitter_step'))
                    for iteration in range(0, iterations_read_one_time):
                        tcsr1 = reg[2 * iteration] & 0xFFFFFFFF
                        tcsr2 = reg[2 * iteration + 1] & 0xFFFFFFFF
                        bit_comp = (tcsr1 & 0x80) >> 7
                        #datsmp_ctl = tcsr1 & 70
                        # bits 15 - 11
                        stdat_exp = (tcsr2 & 0xF800) >> 11
                        # bits 10 - 0
                        stdat_base = tcsr2 & 0x7FF
                        pwer_mis = pow(4, stdat_exp)
                        num_mismtch = pwer_mis * stdat_base
                        if bit_comp == 0:
                            norm_mismtch = 1.0 * (num_mismtch - (total_possible_mismatch / 2)) / (
                                        total_possible_mismatch / 2)
                        else:
                            norm_mismtch = -1.0 * (num_mismtch - (total_possible_mismatch / 2)) / (
                                        total_possible_mismatch / 2)
                        print("%d,%.1f,%.1f" % (test_step, num_mismtch, norm_mismtch))
                        sys.stdout.flush()
                        test_step += 1
                return TestStatus.PASS

        return TestStatus.FAIL


class PATTERN_INDEPENDENT_JITTER_SCOPE(SerdesTestApp):
    """Class implementing SerDes PATTERN_INDEPENDENT_JITTER Test."""

    ID = 302
    NAME = 'pattern_independent_jitter_scope'
    BIST_ERR_CNT_DN = 0x00010000

    def process_results(self) -> None:
        """Results decoding for PATTERN_INDEPENDENT_JITTER test."""
        if ('records' in self.results) and (len(self.results['records']) > 0):
            super().process_results()
            error_step = self.results['records'][0]['data'][2]
            if (self.results['records'][0]['data'][0] != 0) and (error_step != 0):
                self.logger.error('ERROR at Pattern Independent JITTER step %d' % error_step)

            if error_step == 1:
                # PATTERN_INDEPENDENT_JITTER fails at step 28 - PLL ot locked
                self.logger.error('ERROR: PLL %d is not locked' % self.results['records'][0]['data'][0])

            if error_step == 10:
                # PATTERN_INDEPENDENT_JITTER fails at step 10 - CDR_LOCK check
                self.logger.error('ERROR: CDR_LOCK was not asserted')

            noerrors = (self.results['records'][0]['data'][0] == 0) and (self.results['records'][0]['data'][1] == 0)
            if (error_step == 11) and noerrors:
                self.logger.info('CDR_LOCK was asserted')

    def read_results(self) -> TestStatus:
        """Results read for PATTERN_INDEPENDENT_JITTER test."""
        super().read_results()
        # Execute wait for errors and status bit to set only if PATT_SYNC was asserted
        if ('records' in self.results) and (len(self.results['records']) > 0):
            noerrors = (self.results['records'][0]['state'] == 1) and (self.results['records'][0]['data'][2] == 11)
            if noerrors:
                step = 0
                pat_length = self.results['records'][0]['data'][6]
                rx_rate = self.results['records'][0]['data'][8]
                print("steps_per_bit=%d" % self.results['records'][0]['data'][3])
                print("pattern_length=%d" % pat_length)
                print("count_window_bits=%d" % self.results['records'][0]['data'][7])
                print("rx_rate=%d" % rx_rate)
                bits_per_interp = self.results['records'][0]['data'][5]
                iterations = 256 if (rx_rate == 2) else 128
                iterations_read_one_time = int(self.app.get_test_result_symbol(0, 'jitter_step')[2] / 2)

                loop = int(iterations / iterations_read_one_time)
                for i in range(0, loop):
                    # 2 reads for rx_rate = 2, (iterations = 256)
                    reg = self.channel.read_symbol(self.app.get_test_result_symbol(0, 'jitter_step'))
                    for iteration in range(0, iterations_read_one_time):
                        tst4 = reg[2 * iteration] & 0xFFFFFFFF
                        tcsr2 = reg[2 * iteration + 1] & 0xFFFFFFFF

                        data1_pos = tst4 & 0x000007F0  # tst4(4:10)
                        edge1_pos = tst4 & 0x003F8000  # tst4 (11:17)
                        data2_pos = tst4 & 0x01FC0000  # tst4 (18:24)
                        edge2_pos = tst4 & 0xFE000000  # tst4 (25:31)

                        if bits_per_interp == 2:  # rx_rate == 0
                            # Set $data2_pi_ctrl = 0 since data2 interp is not used in full rate mode
                            # may not be strictly necessary.
                            data2_pos = 0
                        exp_edge1_pos = 0

                        smpl_offset = iteration
                        # self.logger.info(iteration)
                        if bits_per_interp == 2:  # rx_rate == 0
                            # Calculate expected rover sampler position
                            # TCL math gets a little funny with negative numbers
                            if data1_pos < 32:
                                exp_edge1_pos = (128 + data1_pos) - (32 - smpl_offset)
                            else:
                                exp_edge1_pos = data1_pos - (32 - smpl_offset)
                            if exp_edge1_pos > 127:
                                exp_edge1_pos = exp_edge1_pos - 128
                        elif bits_per_interp == 4:  # rx_rate == 3
                            if data1_pos < 16:
                                exp_edge1_pos = (128 + data1_pos) - (16 - smpl_offset)
                            else:
                                exp_edge1_pos = data1_pos - (16 - smpl_offset)
                            if exp_edge1_pos > 127:
                                exp_edge1_pos = exp_edge1_pos - 128

                        # bits 15 - 11
                        stdat_exp = (tcsr2 & 0xF800) >> 11
                        # bits 10 - 0
                        stdat_base = tcsr2 & 0x7FF
                        pwer_mis = pow(4, stdat_exp)
                        num_mismtch = pwer_mis * stdat_base
                        output = "%d, %.1f, %d, %d, %d, %d, %d"
                        print(output % (step, num_mismtch, data1_pos, edge1_pos, data2_pos, edge2_pos, exp_edge1_pos))
                        sys.stdout.flush()
                        step += 1
                return TestStatus.FAIL

        return TestStatus.PASS


class Read_Mdio(SerdesTestRegAccess):
    """Read_Mdio serdes test class."""

    ID = 308
    NAME = 'read_mdio'

    def load_dcd_and_app(self) -> TestStatus:
        """Override method."""
        mdio = MDIO(self.config_data, self.channel)
        self.test_status = mdio.run()
        return self.test_status
