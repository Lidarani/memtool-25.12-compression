# Copyright 2020-2025 NXP
"""Import from target class."""
import argparse
import collections
import logging
import os
import struct
import sys

from defusedxml import minidom

from memtool.comm.cwtap_channel import CWTapChannel
from memtool.common.config_data import ConfigData
from memtool.common.factories import AppInterfaceFactory, BackendFactory, FactoryClass, ProcessorFactory
from memtool.utils.helper import add_file_to_params

from .serdes_gen_func import calculate_serdes_module_offset, getLaneId, getPLLId


def serializeRegisterInfo(doc, registersList, register, registerValues, file):  # type: ignore
    """Serializes register information(name, value) into xml format.

    <registers>
    <name>PLL 1 Control Register 0</name>
    <values>0, 128, 0, 8</values>
    </registers>
    @param doc			  The XML document
    @param registersList  The Element value with all registers from that module
    @param register		  The name of register
    @param registerValues The list with values for that register.
    """
    registersElm = doc.createElement('registers')
    registersList.appendChild(registersElm)
    nameElm = doc.createElement('name')
    registersElm.appendChild(nameElm)
    registerName = doc.createTextNode(register)
    nameElm.appendChild(registerName)

    valuesElm = doc.createElement('values')
    registersElm.appendChild(valuesElm)
    registerValuesStr = ', '.join(str(int(str(value), 16)) for value in registerValues)
    valuesText = doc.createTextNode(registerValuesStr)
    valuesElm.appendChild(valuesText)
    file.write(registersElm.toxml())

def readRegisterGroup(session, params, startAddress, length):  # type: ignore
    """Reads a block of memory starting from startAddress with given length.

    @param startAddress The start address of memory block
    @param length		The length of memory block
    @return				The values read from memory block
    """
    try:
        return session.read_data(startAddress, 4, length)
    except Exception as ex:
        print(ex)

def swap(values):  # type: ignore
    """Swaps the list of values."""
    n = 2
    list = []
    for i in range(0, len(values), n):
        list.append(values[i : i + n])
    new_list = [0] * len(list)
    for index in range(len(list)):
        new_list[index] = list[len(list) - index - 1]
    return new_list

def serializeRegisterGroup(params, doc, registersList, memoryValues, kRegisterDict, start, end, file):  # type: ignore
    """Gets registers from register group and serializes them into xml format.

    @param doc			 The XML document
    @param registersList The Element value with all registers from that module
    @param memoryValues	 The list with values read for the register from kRegisterDict map
    @param kRegisterDict The map with register_name: register_offset entries
    @param start		 The index of the first PLL or lane register from the group (e.g. 0)
    @param end			 The index of the last PLL or lane register from the group (e.g. 7)
    """
    if memoryValues is None:
        raise Exception("\r\nThe memory cannot be read! Please check the connection!")

    keys = kRegisterDict.keys()
    sorted(keys)
    for register in keys:
        serializeRegister = False
        # first try to see if the register contains a PLL id
        idx = getPLLId(register)
        if idx == 'F' or idx == 'S':
            serializeRegister = True
            if idx == 'F':
                idx = 1
            else:
                idx = 2

        if idx is None:
            # then try to see if the register contain a Lane id
            idx = getLaneId(register)
        # serialize all other registers which do are not PLL or Lane registers
        if idx is None:
            serializeRegister = True
        # serialize PLL or Lane registers that apply to the given device
        # meaning they are between start and end pll/lane number defined for that device
        elif idx >= start and idx <= end:
            serializeRegister = True


        if serializeRegister:
            index = kRegisterDict[register]
            switchEndianness = params['serdes_modules']['switchEndiannessReadTarget']
            if not switchEndianness:
                registerValues = swap(memoryValues[index * 8 : index * 8 + 8])
            else:
                registerValues = memoryValues[index * 8 : index * 8 + 8]

            serializeRegisterInfo(doc, registersList, register, registerValues, file)

def serializeSerDesRegisters(session, params, serdesModule, doc, registersList, startAddress, file):  # type: ignore
    """Reads registers(pll and lane control registers) and serializes them into xml format.

    @param serdesModule	 The name of SerDes module (e.g. 'SerDes1')
    @param doc			 The XML document
    @param registersList The Element value with all registers from that module
    @param startAddress	 The start address of mapped register group for that module
    """
    # read params
    genCtrlRegOffset = params['serdes_mem_map']['genCtrlRegOffset']
    genCtrlRegLength = params['serdes_mem_map']['genCtrlRegLength']
    kModulesDict = params['serdes_modules']['kModulesDict']
    startLane = kModulesDict.get(serdesModule).get("StartLane")
    endLane = kModulesDict.get(serdesModule).get("EndLane")
    # make sure that startLane <= endLane; there are cases when lane h is first lane
    if startLane > endLane:
        tmp = endLane
        endLane = startLane
        startLane = tmp
    kRegisterDictGenControlReg = params['serdes_mem_map']['kRegisterDictGenControlReg']
    kNoOfPlls = params['serdes_modules']['kNoOfPlls']
    laneCtrlRegLength = params['serdes_mem_map']['laneCtrlRegLength']
    laneCtrlRegOffset = int(params['serdes_mem_map']['laneCtrlRegOffset'], 16)
    kRegisterDictPerLaneReg = params['serdes_mem_map']['kRegisterDictPerLaneReg']
    # reads the pll control registers group
    memoryValues = readRegisterGroup(session, params, int(startAddress, 16) + genCtrlRegOffset, genCtrlRegLength)
    # memoryValuesArray = memoryValues.to_array(1, False)
    serializeRegisterGroup(params, doc, registersList, memoryValues, kRegisterDictGenControlReg, 1, kNoOfPlls, file)
    # reads the lane control registers group
    memoryValues = readRegisterGroup(session, params, int(startAddress, 16) + laneCtrlRegOffset, laneCtrlRegLength)
    collections.OrderedDict(sorted(kRegisterDictPerLaneReg.items()))
    # kRegisterDictPerLaneReg.keys().sort()
    # memoryValuesArray = memoryValues.to_array(1, False)
    serializeRegisterGroup(params, doc, registersList, memoryValues, kRegisterDictPerLaneReg, startLane, endLane, file)

def createRegisterFile(session, params):  # type: ignore
    """For each SerDes module reads the registers of interest and creates corresponding elements in an xml format."""
    doc = minidom.Document()
    registersBlockElm = doc.createElement('registerBlock')
    doc.appendChild(registersBlockElm)
    registersMap = doc.createElement('registersMap')
    registersBlockElm.appendChild(registersMap)
    file = open(params['dump'] + os.path.sep + "serdes.readTarget.xml", "w")
    try:
        # gets the define serdes modules
        kModulesDict = params['serdes_modules']['kModulesDict']
        modules = kModulesDict.keys()
        file.write("<?xml version=\"1.0\" ?><registerBlock><registersMap>")
        for module in modules:
            # gets the offset of the given serdes module
            startAddress = calculate_serdes_module_offset(params, module)
            if startAddress is None:
                continue

            # creates element entry for each module
            entryElm = doc.createElement('entry')
            registersMap.appendChild(entryElm)

            # creates element key with text node module name
            keyElm = doc.createElement('key')
            entryElm.appendChild(keyElm)
            moduleNameElm = doc.createTextNode(module)
            keyElm.appendChild(moduleNameElm)
            # creates element value with all registers from that module
            valueElm = doc.createElement('value')
            entryElm.appendChild(valueElm)
            file.write("<entry><key>" + module + "</key><value>")
            serializeSerDesRegisters(session, params, module, doc, valueElm, startAddress, file)
            file.write("</value></entry>")
        file.write("</registersMap></registerBlock>")
        file.close()
        print("Dumped data in file: " + params['dump'] + os.path.sep + "serdes.readTarget.xml")

    except Exception as ex:
        print("Exception %s" % str(ex))

def import_from_target(): # type: ignore
    """Imports a serdes configuration from the target."""
    parser = argparse.ArgumentParser(description='Import target serdes')
    parser.add_argument('file', nargs='+', type=argparse.FileType('r'),
        help='JSON format files containing test parameters')
    parser.add_argument('-t', '--data-dir', default=os.getcwd(), help='Data path')
    parser.add_argument('-o', '--output-dir', default=os.getcwd(), help='Output directory path')
    parser.add_argument('-l', '--log', choices=['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'], default='CRITICAL',
        help='Specifies logging level')

    try:
        args = parser.parse_args()
    except SystemExit:
        return

    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(format='%(levelname)-8s %(name)s %(message)s',
                        level=getattr(logging, args.log))

    params = {}
    for file in args.file:
        params = add_file_to_params(file.name, params)

    config_data = ConfigData(args.data_dir, params)
    channel = BackendFactory.make_unique_instance(config_data.connect_params)

    # open ccs
    if not channel.is_alive():
        try:
            channel.open(config_data)
            #assert channel.is_alive()
            params['dump'] = os.path.dirname(args.file[0].name)
            createRegisterFile(channel, params)
        except Exception as ex:
            print("Exception on ccs open: %s" % str(ex))
        finally:
            channel.close()

import_from_target()
