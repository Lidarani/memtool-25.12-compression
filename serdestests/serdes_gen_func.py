# Copyright 2021-2025 NXP
"""SerDes generic utility class."""
import re


def calculate_serdes_module_offset(params, serdesModule):  # type: ignore
    """Calculates serdes module offset.

    @param serdesModule The name of the module (e.g. 'SerDes1')
    @return             The SerDes module offset address, based on its name
    """
    kModulesDict = params['serdes_modules']['kModulesDict']
    return kModulesDict.get(serdesModule).get("Offset")


def getGenCtrlRegOffsetByName(params, serdesModuleOffset, regName):  # type: ignore
    """Gets register address.

    @param regName The general control register name
    @return        The general control register offset, based on its name
    """
    genCtrlRegOffset = params['serdes_mem_map']['genCtrlRegOffset']
    kRegisterDictGenControlReg = params['serdes_mem_map']['kRegisterDictGenControlReg']
    address = getRegAddress(serdesModuleOffset, genCtrlRegOffset, regName, kRegisterDictGenControlReg)
    return address


def getPllCtrlRegOffsetByName(params, serdesModuleOffset, pllNumber, regName):  # type: ignore
    """Gets PLL offset.

    @param serdesModuleOffset The SerDes module offset address
    @param pllNumber          The PLL number
    @param regName            The PLL register name
    @return                   The PLL register offset, based on its name, and PLL number
    """
    genCtrlRegOffset = params['serdes_mem_map']['genCtrlRegOffset']
    kRegisterDictGenControlReg = params['serdes_mem_map']['kRegisterDictGenControlReg']
    regName = "PLL" + str(pllNumber) + regName
    address = getRegAddress(serdesModuleOffset, genCtrlRegOffset, regName, kRegisterDictGenControlReg)
    return address


def getLaneRegAddressByName(params, serdesModuleOffset, laneNumber, regName):  # type: ignore
    """Gets Lane Register Address.

    @param serdesModuleOffset The SerDes module offset address
    @param laneNumber         The lane number
    @param regName            The lane register name
    @return                   The lane control register offset, based on its name, and lane number
    """
    regName = "LN" + str(laneNumber) + regName
    laneCtrlRegOffset = params['serdes_mem_map']['laneCtrlRegOffset']
    kRegisterDictPerLaneReg = params['serdes_mem_map']['kRegisterDictPerLaneReg']
    address = getRegAddress(serdesModuleOffset, int(laneCtrlRegOffset, 16), regName, kRegisterDictPerLaneReg)
    return address


def getRegAddress(serdesModuleOffset, groupOffset, regName, kRegisterDict):  # type: ignore
    """Gets Lane Register Address.

    @param serdesModuleOffset The SerDes module offset
    @param groupOffset        The group offset
    @param regName            The register name
    @return                   The register address, based on its name, serdes module offset and group offset
    """
    regOffset = kRegisterDict[regName]
    if regOffset is None:
        return regOffset
    else:
        address = int(serdesModuleOffset, 16) + groupOffset + regOffset * 4
        return address


def decodeLaneId(laneId):  # type: ignore
    """Decode Lane id.

    @param laneId: The id of lane formatted either as a number '0', '1', .. or as capital letter 'A' to 'Z'
    @return: The id of lane as int if this is a number, the id as string
        if this is a letter A-Z or None if none of the above
    """
    # check if lane id is a number
    if laneId.isdigit():
        return int(laneId)
    # check if lane id is a capital letter
    elif len(laneId) == 1 and laneId.isupper():
        return laneId
    else:
        return None


def getPLLId(regName):  # type: ignore
    """Gets PLL id.

    @param regName	The name of the register from which to extract the PLL id
    @return			The id of PLL or None if the register is not one describing the PLL
    """
    PLL_REG_EXP = r'PLL(\d+)'
    match = re.match(PLL_REG_EXP, regName)
    if match is not None:
        return int(match.group(1))
    else:
        if 'PLLF' in regName:
            return 'F'
        elif 'PLLS' in regName:
            return 'S'
    return None


def getLaneId(regName):  # type: ignore
    """Gets Lane id.

    @param regName: The name of the register from which to extract the lane id
    @return: The id of lane as int or string depending on register definition
            or None if the register is not one describing the lane
    """
    LANE_LETTER_REG_EXP = r'LN([A-Z])'
    LANE_NUMBER_REG_EXP = r'LN(\d+)'
    match = re.match(LANE_NUMBER_REG_EXP, regName)
    if match is not None:
        return int(match.group(1))
    match = re.match(LANE_LETTER_REG_EXP, regName)
    if match is not None:
        return match.group(1)
    return None
