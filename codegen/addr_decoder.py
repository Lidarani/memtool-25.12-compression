# Copyright 2022-2023, 2025 NXP
"""TODO:summary line."""
import logging

logger = logging.getLogger(__name__)


class PhyAddrDecoder:
    """Abstract class for decoding PHY address."""

    DDRPHY_BASE_ADDR = 0x0

    def map_ddr_space(self, phy_addr: int) -> int:  # type: ignore
        """It maps PHY address into DDR PHY address.

        @param phy_addr: PHY address to be mapped to DDR.
        @return: DDR PHY mapped address
        """
        pass

    def revert_ddr_space(self, ddrphy_addr: int) -> int:  # type: ignore
        """It reverts DDR PHY mapped address into PHY address.

        @param ddrphy_addr: DDR PHY address to be reversed.
        @return: PHY address
        """
        pass


class PhyAddrIMX8Decoder(PhyAddrDecoder):
    """It decodes PHY address for IMX8."""

    DDRPHY_BASE_ADDR = 0x3C000000

    def map_ddr_space(self, phy_addr: int) -> int:
        """It maps PHY address into DDR PHY address for IMX8.

        @param phy_addr: PHY address to be mapped to DDR.
        @return: DDR PHY mapped address
        """
        ddrphy_addr = phy_addr << 2
        ddrphy_addr = self.DDRPHY_BASE_ADDR + ddrphy_addr
        return ddrphy_addr

    def revert_ddr_space(self, ddrphy_addr: int) -> int:
        """It reverts DDR PHY mapped address into PHY address.

        @param ddrphy_addr: DDR PHY address to be reversed.
        @return: PHY address
        """
        phy_addr = ddrphy_addr - self.DDRPHY_BASE_ADDR
        if phy_addr < 0x0:
            logger.error(
                "[Error] Expecting input address to be at least %s",
                hex(self.DDRPHY_BASE_ADDR),
            )
            phy_addr = 0x0
            return phy_addr
        phy_addr = phy_addr >> 2
        return phy_addr


class PhyAddrIMX93Decoder(PhyAddrDecoder):
    """It decodes PHY address for IMX93."""

    DDRPHY_BASE_ADDR = 0x4E100000
    ADDR_MASK_BITS_22_13 = 0x007FE000
    ADDR_MASK_BITS_19_13 = 0x000FE000
    ADDR_MASK_BITS_12_1 = 0x00001FFE
    # Dictionary used for converting PHY address into DDR mapped PHY address for IMX9:
    # key is a subset of bits from PHY address, value is a subset of bits from DDR PHY mapped address.
    PHY_ADDR_APB_DIC = {
        0x000: 0x00,
        0x001: 0x01,
        0x002: 0x02,
        0x003: 0x03,
        0x004: 0x04,
        0x005: 0x05,
        0x006: 0x06,
        0x007: 0x07,
        0x008: 0x08,
        0x009: 0x09,
        0x00A: 0x0A,
        0x00B: 0x0B,
        0x100: 0x0C,
        0x101: 0x0D,
        0x102: 0x0E,
        0x103: 0x0F,
        0x104: 0x10,
        0x105: 0x11,
        0x106: 0x12,
        0x107: 0x13,
        0x108: 0x14,
        0x109: 0x15,
        0x10A: 0x16,
        0x10B: 0x17,
        0x200: 0x18,
        0x201: 0x19,
        0x202: 0x1A,
        0x203: 0x1B,
        0x204: 0x1C,
        0x205: 0x1D,
        0x206: 0x1E,
        0x207: 0x1F,
        0x208: 0x20,
        0x209: 0x21,
        0x20A: 0x22,
        0x20B: 0x23,
        0x300: 0x24,
        0x301: 0x25,
        0x302: 0x26,
        0x303: 0x27,
        0x304: 0x28,
        0x305: 0x29,
        0x306: 0x2A,
        0x307: 0x2B,
        0x308: 0x2C,
        0x309: 0x2D,
        0x30A: 0x2E,
        0x30B: 0x2F,
        0x010: 0x30,
        0x011: 0x31,
        0x012: 0x32,
        0x013: 0x33,
        0x014: 0x34,
        0x015: 0x35,
        0x016: 0x36,
        0x017: 0x37,
        0x018: 0x38,
        0x019: 0x39,
        0x110: 0x3A,
        0x111: 0x3B,
        0x112: 0x3C,
        0x113: 0x3D,
        0x114: 0x3E,
        0x115: 0x3F,
        0x116: 0x40,
        0x117: 0x41,
        0x118: 0x42,
        0x119: 0x43,
        0x210: 0x44,
        0x211: 0x45,
        0x212: 0x46,
        0x213: 0x47,
        0x214: 0x48,
        0x215: 0x49,
        0x216: 0x4A,
        0x217: 0x4B,
        0x218: 0x4C,
        0x219: 0x4D,
        0x310: 0x4E,
        0x311: 0x4F,
        0x312: 0x50,
        0x313: 0x51,
        0x314: 0x52,
        0x315: 0x53,
        0x316: 0x54,
        0x317: 0x55,
        0x318: 0x56,
        0x319: 0x57,
        0x020: 0x58,
        0x120: 0x59,
        0x220: 0x5A,
        0x320: 0x5B,
        0x040: 0x5C,
        0x140: 0x5D,
        0x240: 0x5E,
        0x340: 0x5F,
        0x050: 0x60,
        0x051: 0x61,
        0x052: 0x62,
        0x053: 0x63,
        0x054: 0x64,
        0x055: 0x65,
        0x056: 0x66,
        0x057: 0x67,
        0x070: 0x68,
        0x090: 0x69,
        0x190: 0x6A,
        0x290: 0x6B,
        0x390: 0x6C,
        0x0C0: 0x6D,
        0x0D0: 0x6E,
    }

    def get_value_from_phy_addr_apb_dic(self, key_addr: int) -> int:
        """TODO:summary line.

        It gets value for given key from dictionary used for
        converting PHY address into DDR mapped PHY address
        for IMX9x. Any subset of bits from PHY address that has
        no specific mapping it collapses into 0x0 value.

        @param key_addr: Key is a subset of bits from PHY address.
        @return: A subset of bits from DDR PHY address.
        If key is not found in dictionary 0x0 is returned.
        """
        if key_addr in self.PHY_ADDR_APB_DIC:
            return self.PHY_ADDR_APB_DIC.get(key_addr)  # type: ignore
        return 0x00

    def get_key_from_phy_addr_apb_dic(self, value_addr: int) -> int:
        """TODO:summary line.

        It gets key for given value from dictionary used for
        converting PHY address into DDR mapped PHY address
        for IMX9x.

        @return: A subset of bits from PHY address.
        If no key is not found in dictionary for given value 0x0 is returned.
        """
        for key, addr in self.PHY_ADDR_APB_DIC.items():
            if addr == value_addr:
                return key
        return 0x0

    def map_ddr_space(self, phy_addr: int) -> int:
        """It maps PHY address into DDR PHY address for IMX9.

        @param phy_addr: PHY address to be mapped to DDR.
        @return: DDR PHY mapped address
        """
        paddr_apb_qual = phy_addr << 1
        paddr_apb_unqual_dec_22_13 = (paddr_apb_qual & self.ADDR_MASK_BITS_22_13) >> 13
        paddr_apb_unqual_dec_12_1 = (paddr_apb_qual & self.ADDR_MASK_BITS_12_1) >> 1
        paddr_apb_unqual_dec_19_13 = self.get_value_from_phy_addr_apb_dic(paddr_apb_unqual_dec_22_13)
        paddr_apb_unqual = (paddr_apb_unqual_dec_19_13 << 13) | (paddr_apb_unqual_dec_12_1 << 1)
        paddr_apb_phy = paddr_apb_unqual << 1
        paddr_apb_phy = self.DDRPHY_BASE_ADDR + paddr_apb_phy
        return paddr_apb_phy

    def revert_ddr_space(self, ddrphy_addr: int) -> int:
        """It reverts DDR PHY mapped address into PHY address for IMX9.

        @param ddrphy_addr: DDR PHY address to be reversed.
        @return: PHY address
        """
        paddr_apb_phy = ddrphy_addr - self.DDRPHY_BASE_ADDR
        if paddr_apb_phy < 0x0:
            logger.error(
                "[Error] Expecting input address to be at least %s",
                hex(self.DDRPHY_BASE_ADDR),
            )
            phy_addr = 0x0
            return phy_addr
        paddr_apb_unqual = paddr_apb_phy >> 1
        paddr_apb_unqual_dec_19_13 = (paddr_apb_unqual & self.ADDR_MASK_BITS_19_13) >> 13
        paddr_apb_qual = paddr_apb_unqual  # It should be updated based on dic.
        if paddr_apb_unqual_dec_19_13 == 0x0:
            logger.debug("[Warning] Value from bits 19-13 is 0x0, reconverted bits 22-13 as 0x0 might be wrong!")
        for key in self.PHY_ADDR_APB_DIC:
            match_paddr_apb_unqual_dec_19_13 = self.get_value_from_phy_addr_apb_dic(key)
            paddr_apb_unqual_dec_22_13 = key
            paddr_apb_unqual_dec_12_1 = (paddr_apb_unqual & self.ADDR_MASK_BITS_12_1) >> 1
            if paddr_apb_unqual_dec_19_13 == match_paddr_apb_unqual_dec_19_13:
                paddr_apb_qual = (paddr_apb_unqual_dec_22_13 << 13) | (paddr_apb_unqual_dec_12_1 << 1)
                break
        phy_addr = paddr_apb_qual >> 1
        return phy_addr


class PhyAddrIMX95Decoder(PhyAddrIMX8Decoder):
    """It decodes PHY address for IMX95."""

    DDRPHY_BASE_ADDR = 0x5E800000
