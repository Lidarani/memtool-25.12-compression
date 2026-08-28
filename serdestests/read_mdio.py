# Copyright 2021-2025 NXP

"""Read MDIO class."""
import collections
import logging
import os
import struct
import sys
import time

from memtool.common.base_test import TestStatus
from memtool.common.channel import Channel
from memtool.common.config_data import ConfigData


class MDIO:
    """MDIO test class."""

    def __init__(self, config_data: ConfigData, channel: Channel):
        """MDIO init."""
        self.macNumber = config_data.params["config"]["MAC"]
        self.clause = config_data.params["config"]["clause"]
        self.operation = config_data.params["config"]["operation"]
        self.regAddress = config_data.params["config"]["regAddress"]
        self.data = config_data.params["config"]["data"]
        self.mmd = config_data.params["config"]["mmd"]  # device address
        self.phyAddr = config_data.params["config"]["phy_address"]
        self.channel = channel
        self.logger = logging.getLogger(__name__)

    def run(self) -> TestStatus:
        """MDIO run method."""
        if self.operation == 0:
            print("Results for Read MDIO Registers Test with clause %d:" % (22 if (self.clause == 0) else 45))
        else:
            print("Results for Write MDIO Registers Test with clause %d:" % (22 if (self.clause == 0) else 45))

        try:
            #for mdioMac in MEMAC:
            if self.clause == 0:
                return self.c22_clause()
            else:
                return self.c45_clause()

        except Exception:
            self.logger.error('Exception while reading MDIO registers')
            return TestStatus.FAIL

    def c45_clause(self) -> TestStatus:
        """Implementation of MDIO test c45_clause."""
        MEMAC1_MDIO_CFG = 0x30
        MEMAC1_MDIO_CTRL = 0x34
        MEMAC1_MDIO_DATA = 0x38
        MEMAC1_MDIO_ADDR = 0x3c

        MEMAC1_MDIO_CFG = self.macNumber + MEMAC1_MDIO_CFG
        MEMAC1_MDIO_CTRL = self.macNumber + MEMAC1_MDIO_CTRL
        MEMAC1_MDIO_DATA = self.macNumber + MEMAC1_MDIO_DATA
        MEMAC1_MDIO_ADDR = self.macNumber + MEMAC1_MDIO_ADDR

        print("\tMAC=0x%x" % self.macNumber)
        PHY = self.mmd
        EXT_PHY = self.phyAddr
        PHY = (EXT_PHY << 5) | PHY
        REG = self.regAddress
        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 0xFF80
        val = val | 0x1C
        val = val | 0x40
        #print("DIV=0x%x" % val)
        self.channel.write_symbol((MEMAC1_MDIO_CFG, 4, 1), val)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 0x1
        while val != 0:
            print("MDIO_CFG_BSY ")
            val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
            val = val & 1
            time.sleep(0.01)
        self.channel.write_symbol((MEMAC1_MDIO_CTRL, 4, 1), PHY)
        self.channel.write_symbol((MEMAC1_MDIO_ADDR, 4, 1), REG)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 0x1
        while val != 0:
            print("MDIO_CFG_BSY ")
            val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
            val = val & 1
            time.sleep(0.01)

        if self.operation == 1:
            # write operation
            self.channel.write_symbol((MEMAC1_MDIO_DATA, 4, 1), self.data)
        else:
            # read operation
            val = PHY
            val = val | 0x8000
            self.channel.write_symbol((MEMAC1_MDIO_CTRL, 4, 1), val)

        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        val = val & 0x80000000
        while val != 0:
            print("MDIO_CFG_BSY ")
            val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
            val = val & 0x80000000
            time.sleep(0.01)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        print("\tDATA=0x%x" % val)

        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 0x2
        #this should always be 0 -check for any error on MDIO read
        print("\tERROR=0x%x" % val)

        if val != 0:
            print("ERROR should be 0!\nEnd Test!")
            print("\n#####################################")
            return TestStatus.FAIL

        return TestStatus.PASS

    def c22_clause(self) -> TestStatus:
        """Implementation of MDIO test c22_clause."""
        print("\tMAC=0x%x" % self.macNumber)

        MEMAC1_MDIO_CFG = 0x30
        MEMAC1_MDIO_CTRL = 0x34
        MEMAC1_MDIO_DATA = 0x38
        MDIO_CTL_READ = 0x8000
        PHY = 0x0
        EXT_PHY = self.phyAddr

        PHY = (EXT_PHY << 5) | PHY
        MEMAC1_MDIO_CFG = self.macNumber + MEMAC1_MDIO_CFG
        MEMAC1_MDIO_CTRL = self.macNumber + MEMAC1_MDIO_CTRL
        MEMAC1_MDIO_DATA = self.macNumber + MEMAC1_MDIO_DATA

        # poll MDIO_CFG_BSY
        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & (0xFF80 | 0x1C)
        #print("DIV=0x%x" % val)
        self.channel.write_symbol((MEMAC1_MDIO_CFG, 4, 1), val)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 1
        while val != 0:
            print("MDIO_CFG_BSY ")
            val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
            val = val & 1
            time.sleep(0.01)

        val = PHY
        val = val | self.regAddress
        val = val | MDIO_CTL_READ
        self.channel.write_symbol((MEMAC1_MDIO_CTRL, 4, 1), val)

        #print("Register 0x%x:" % regOffset)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 1
        while val != 0:
            print("MDIO_CFG_BSY ")
            val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
            val = val & 1
            time.sleep(0.01)

        if self.operation == 1:
            # write operation
            self.channel.write_symbol((MEMAC1_MDIO_DATA, 4, 1), self.data)

        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        val = val & 0x80000000
        while val != 0:
            print("MDIO_CFG_BSY ")
            val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
            val = val & 0x80000000
            time.sleep(0.01)

        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        val = int(self.channel.read_symbol((MEMAC1_MDIO_DATA, 4, 1)) or 0)
        print("\tDATA=0x%x" % val)

        val = int(self.channel.read_symbol((MEMAC1_MDIO_CFG, 4, 1)) or 0)
        val = val & 0x2
        #this should always be 0 -check for any error on MDIO read
        print("\tERROR=0x%x" % val)

        if val != 0:
            print("ERROR should be 0!\nEnd Test!")
            print("\n#####################################")
            return TestStatus.FAIL

        return TestStatus.PASS
