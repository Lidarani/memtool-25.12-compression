# Copyright 2023, 2025 NXP
"""Lane Reset class."""
import logging
import os
import sys

from memtool.common.channel import Channel
from memtool.common.config_data import ConfigData


class LaneReset:
    """LaneReset serdes class."""

    def __init__(self, config_data: ConfigData, channel: Channel):
        """Lane reset init."""
        self.logger = logging.getLogger(__name__)
        self.config_data = config_data
        self.channel = channel

        self.TRSTCTL_REG_LANE_OFFSET = 0x720
        self.RRSTCTL_REG_LANE_OFFSET = 0x740
        laneNumber = self.config_data.params['app']['test_params']['laneNumber']
        self.RRSTCTL_REG = self.config_data.params['serDesBase'] + 0x100 * laneNumber + self.RRSTCTL_REG_LANE_OFFSET
        self.TRSTCTL_REG = self.config_data.params['serDesBase'] + 0x100 * laneNumber + self.TRSTCTL_REG_LANE_OFFSET

    def putLaneIntoReset(self, params, path):  # type: ignore
        """Puts Lane Into Reset method."""
        if path == 'Tx':
            # set LNmRRSTCTL[HALT_REQ]=1
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), 0x10)
            #reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
            #trstctl = ((reg & 0x10) == 0x10)
            #if not trstctl:
            #    print("Error: TRSTCTL incorrectly set(trstctl_val)!")
            #    return False
            #trstctl = ((reg & 0x120) == 0)
            #if not trstctl:
            #    print("Error: TRSTCTL incorrectly set(trstctl_val)!")
            #    return False
        elif path == 'Rx':
            # set LNmTRSTCTL[HALT_REQ]=1
            #rrstctl_val = 0x10
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), 0x10)
            #reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
            #rrstctl = ((reg & 0x10) == 0x10)
            #if not rrstctl:
            #    print("Error: RRSTCTL incorrectly set(%x)!" % reg)
            #    return False
        else:  # both
            # Tx
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), 0x10)
            #reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
            # Rx
            #rrstctl_val = 0x10
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), 0x10)
            #reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))

        return True

    def getLaneOutOfReset(self, params, path):  # type: ignore
        """Gets the corresponding path of the lane out of reset and puts it into application mode."""
        if path == 'Rx':
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), 0x30)
            reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
            rrstctl = (reg & 0x30) == 0x30
            if not rrstctl:
                self.logger.error("Error: RRSTCTL incorrectly set(trstctl_val)!")
                return False
        elif path == 'Tx':
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), 0x30)
            reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
            trstctl = (reg & 0x30) == 0x30
            if not trstctl:
                self.logger.error("Error: TRSTCTL incorrectly set(trstctl_val)!")
                return False
            #trstctl = ((reg & 0x100) == 0)
            #if not trstctl:
            #    print("Error: TRSTCTL incorrectly set(trstctl_val)!")
            #    return False
        else:  # both
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), 0x30)
            reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
            rrstctl = (reg & 0x30) == 0x30
            if not rrstctl:
                self.logger.error("Error: RRSTCTL incorrectly set(trstctl_val)!")
                return False

            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), 0x30)
            reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
            trstctl = (reg & 0x30) == 0x30
            if not trstctl:
                self.logger.error("Error: TRSTCTL incorrectly set(trstctl_val)!")
                return False
        return True

    def power_down_lane(self, params, path):  # type: ignore
        """Power down the corresponding path of the lane.

        # path - path on which the operation will be done(receiver/transmitter)
        #      - possible values: 'Rx', 'Tx'
        # mode - power mode (up/down)
        #      - possible values: 'powerdown', 'powerup'
        """
        if path == 'Rx':
            # set LNmRRSTCTL[HALT_REQ]=1
            rrstctl_val = 0x08000000
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), rrstctl_val)

            leftTimeToWait = 5
            # wait HALT_REQ to clear
            while True:
                reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
                if (reg & rrstctl_val) == 0x0:
                    break
                leftTimeToWait = leftTimeToWait - 1
                if leftTimeToWait < 0:
                    #print "Error: RRSTCTL_REG incorrectly set(rrstctl_val)!"
                    #return False
                    break
            # LNmRRSTCTL[DIS]=1.
            rrstctl_val = 0x01000000
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), rrstctl_val)
            reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
            if (reg & rrstctl_val) != rrstctl_val:
                # try again
                self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), rrstctl_val)
                reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
                if (reg & rrstctl_val) != rrstctl_val:
                    self.logger.error("ERROR: RRSTCTL incorrectly set(rrstctl_val)!")
                    return False
            #print("Power down RX OK on lane %s" % laneNumber)
        else:
            # set LNmTRSTCTL[HALT_REQ]=1
            trstctl_val = 0x08000000
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), trstctl_val)
            leftTimeToWait = 5
            # wait HALT_REQ to clear
            while True:
                reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
                if (reg & trstctl_val) == 0x0:
                    break
                leftTimeToWait = leftTimeToWait - 1
                if leftTimeToWait < 0:
                    #print "Error: TRSTCTL incorrectly set(trstctl_val)!"
                    #return False
                    break
            # LNmTRSTCTL[DIS]=1.
            trstctl_val = 0x01000000
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), trstctl_val)
            reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
            if (reg & trstctl_val) != trstctl_val:
                # try again
                self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), trstctl_val)
                reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
                if (reg & trstctl_val) != trstctl_val:
                    self.logger.error("Error: TRSTCTL incorrectly set(trstctl_val)!")
                    return False
        return True

    def power_up_lane(self, params, path):  # type: ignore
        """Power up the corresponding path of the lane."""
        if path == 'Rx':
            # To enable a previously powered down lane, set LNmT/RRSTCTL[DIS]=0, then set LNmT/RRSTCTL[RST_REQ]=1.
            # Set DIS = 0
            rrstctl_val = 0x0
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), rrstctl_val)
            reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
            # Set RST_REQ = 1 + DIS = 0
            rrstctl_val = 0x80000030
            RST_DONE = 0x40000000
            POWERED_UP = 0x30
            self.channel.write_symbol((self.RRSTCTL_REG, 4, 1), rrstctl_val)
            reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
            rrstctl = (reg & POWERED_UP) == POWERED_UP
            if not rrstctl:
                # try again
                reg = self.channel.read_symbol((self.RRSTCTL_REG, 4, 1))
                rrstctl = (reg & RST_DONE) == RST_DONE
                if not rrstctl:
                    self.logger.error("ERROR: RRSTCTL incorrectly set(trstctl_val)!")
                    return False
        else:
            # To enable a previously powered down lane, set LNmT/RRSTCTL[DIS]=0, then set LNmT/RRSTCTL[RST_REQ]=1.
            # Set DIS = 0
            trstctl_val = 0x0
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), trstctl_val)
            # Set RST_REQ = 1 + DIS = 0
            trstctl_val = 0x80000030
            RST_DONE = 0x40000000
            POWERED_UP = 0x30
            self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), trstctl_val)
            reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
            trstctl = (reg & POWERED_UP) == POWERED_UP
            if not trstctl:
                # try again
                self.channel.write_symbol((self.TRSTCTL_REG, 4, 1), trstctl_val)
                reg = self.channel.read_symbol((self.TRSTCTL_REG, 4, 1))
                trstctl = (reg & RST_DONE) == RST_DONE
                if not trstctl:
                    self.logger.error("Error: TRSTCTL incorrectly set(trstctl_val)!")
                    return False

        return True
