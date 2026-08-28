# Copyright 2020-2025 NXP
"""TODO:summary line."""
from typing import Union

from pycel import AddressCell, AddressRange
from pycel.excelutil import coerce_to_number

from memtool.utils.constants import Const

BUS_CONFIG_SHEET = 'BoardDataBusConfig'
REG_CONFIG_SHEET = 'Register Configuration'
DSF_CONFIG_SHEET = 'DDR stress test file'

MIMX8MP_LP4_ECC_BINARY_ALIGNED_SHEET = "ECC_Config_BinaryAligned"
MIMX8MP_LP4_ECC_NON_BINARY_ALIGNED_SHEET = "ECC_Config_nonBinaryAligned"
MIMX8MP_DDR4_ECC_SHEET = "ECC_CONFIG"

MIMX_DS_RANGE = "A1:E375"
MIMX_CELLS_TO_VALIDATE = (
    AddressRange(f'{DSF_CONFIG_SHEET}!{MIMX_DS_RANGE}'),
    AddressRange(f'{REG_CONFIG_SHEET}!B16:K40'),
    AddressRange(f'{REG_CONFIG_SHEET}!C629:C833'),
    AddressRange(f'{MIMX8MP_LP4_ECC_BINARY_ALIGNED_SHEET}!B13:D34'),
    AddressRange(f'{MIMX8MP_LP4_ECC_NON_BINARY_ALIGNED_SHEET}!B13:D76'),
    AddressRange(f'{MIMX8MP_DDR4_ECC_SHEET}!B12:D74'),
)

#TODO split for each device
MIMX9_DS_RANGE = "A1:E335"
MIMX9_CELLS_TO_VALIDATE = (
    AddressRange(f'{DSF_CONFIG_SHEET}!{MIMX9_DS_RANGE}'),
    AddressRange(f'{REG_CONFIG_SHEET}!B3:E77'),
)

LX2_DS_RANGE = "A1:E240"
LX2_CELLS_TO_VALIDATE = (
    AddressRange(f'{DSF_CONFIG_SHEET}!{LX2_DS_RANGE}'),
    AddressRange(f'{REG_CONFIG_SHEET}!B3:J55'),
)
CLOCK_FREQ_LABEL = 'clockFreqMHz'

PLL_CONFIG_SHEET = 'Sheet1'
PLL_CELLS_TO_VALIDATE = (
    AddressRange(f'{PLL_CONFIG_SHEET}!A1:J27'),
)


def transform_value(name: str, value: str, value_to_index: bool = True) -> Union[int, None, float, str]:
    """Transform odt value to int(index in list of values) or int to value.

    @param name: config name
    @param value: config number
    @param value_to_index: type of conversion
    @return: int or number
    """
    if value == 'None':
        print(f'param={name} value={value}')

    if name == 'soc_odt':
        soc_odt_map = {
            '240': 1, '120': 2, '80': 3, '60': 4, '48': 5, '40': 6, '34': 6, '28': 7
        }
        if value_to_index:
            return soc_odt_map[value]

        tmp_soc_odt_map = {str(y): x for x, y in soc_odt_map.items()}
        return tmp_soc_odt_map[value]

    return coerce_to_number(value)
