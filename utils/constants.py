# Copyright 2020-2025 NXP
"""TODO:summary line."""


class Const:
    """Various constants for parameters, file names, writing and formatting generated files."""

    # TODO: see if commented constants are needed; PyCharm couldn't find them in any other files

    HIDE_DETAILED_DEBUG_INFO = True

    LZ4_COMPRESSION_LEVEL = 16

    INITIAL_COPYRIGHT_YEAR = {
        "MIMX95": "2023",
        "MIMX943": "2025",
        "MIMX95_B0": "2025",
        "MIMX952": "2025",
    }

    DUMP_IMAGE = True

    IMX9_OCRAM_START_ADDRESS = 0x20480000
    IMX9_APP_OFFSET = 0x2000
    IMX9_APP_START_ADDRESS = 0x204A0000
    IMX9_DCD_START_ADDRESS = 0x204D8000
    """
    OCRAM total, NS: 0x20480000 - 0x204D7FFF - according to RM
    IRAM Free Space: 0x20498000 - 0x204D7FFF - according to CA55 ROM,
    => 0x204D7FFF - 0x20498000 + 1 = 0x40000 = 262144 bytes = 256 kBytes
    """
    # DCD
    IMX95_DCD_START_ADDRESS_NS_TCMS = 0x20200000  # TCM system non-secure address
    IMX95_DCD_START_ADDRESS_NS_NSRAM = 0x4AA40000  # SRAM non-secure address
    IMX943_DCD_START_ADDRESS_NS_NSRAM = 0x4AA20000  # SRAM non-secure address

    # DDR PHY FW
    IMX95_FW_START_ADDRESS_NS_TCMC = 0x0FFD0000  # TCM code none-secure address
    IMX95_FW_START_ADDRESS_NS_NSRAM = 0x4AA00000  # Neutron SRAM non-secure address
    IMX943_DIAGS_FW_START_ADDRESS_NS_OCRAM = 0x204A0000  # OCRAM non-secure address

    # V2X
    IMX95_V2X_ADDRESS = 0x8B000000

    # APP
    IMX95_APP_START_ADDRESS_S_TCMC = 0x1FFC0000  # TCM code secure address

    AHAB_BIN_INPUT_NAME = 'final_binary_file.bin'
    AHAB_BIN_OUTPUT_NAME = 'final_ahab_binary_file.bin'
    AHAB_MERGE_CONFIG_NAME = 'AHAB_merge_config.yaml'
    AHAB_CONFIG_NAME = 'AHAB_custom_config.yaml'
    CUSTOM_BOOTABLE_IMAGE_NAME = 'custom_bootable_image.bin'

    USB_DEVICE_TIMEOUT = 30000  # timeout in milliseconds for read & write operation on target through usb
    VDDQ_PRECISION = 100  # precision for parsing float vddq values into int

    PARAM_S_ODT = 'odtConfig'
    PARAM_S_ODT_RD = 'odtReadConfig'
    PARAM_S_ODT_WR = 'odtWriteConfig'
    PARAM_S_CA_ODT = 'caOdtConfig'

    EMU_MASK_DIR_NAME = 'emu_mask'
    PARAM_S_PHY_INIT = "phy_init"
    PARAM_TEST_PARAMS = "test_params"
    PARAM_TEST_PARAMS_PARAMS = "params"
    PARAM_TEST_PARAMS_FLAGS = "flags"
    PARAM_TEST_PARAMS_SIZE = 16
    PARAM_TEST_PARAMS_DIRECTION = "direction"
    PARAM_TEST_PARAMS_BYTE = "byte"
    PARAM_TEST_PARAMS_BIT = "bit"
    PARAM_TEST_PARAMS_CS = "cs"
    OVERWRITE_TEST_PARAMS = "overwrite_params"
    PARAM_S_TARGET_PARAMS = "target_params"
    PARAM_S_DIAGS = 'diag_params'
    PARAM_S_DCD_DIAG_PARAMS = 'dcd_diag_params'
    PARAM_LOG_LEVEL = 'log_level'
    PARAM_S_APP = 'app'
    PARAM_S_SCENARIO = 'scenario'
    PARAM_S_TC = 'connect'
    PARAM_S_TC_FW = 'firmware_versions'
    PARAM_S_TC_MEM_TYPE_STR = 'dram_type_str'
    PARAM_S_TC_SOC_NAME = 'soc_name'
    PARAM_S_TC_PHY_LOG = 'phy_log'
    PARAM_S_TC_USB_ID = 'usb_id'  # Used only for RT-es with SDP.
    PARAM_S_TC_USB_SEL = 'usb_sel'
    PARAM_S_TC_DIAGS_RESULT_FILE = 'result_file'
    PARAM_S_SYS = 'sys_params'
    PARAM_S_SYS_UART = 'debug_uart'
    PARAM_S_SYS_FW_VERSION = 'firmware_version'
    PARAM_S_SYS_PMIC_CFG = 'pmic_cfg'
    PARAM_S_SYS_PMIC_SET = 'pmic_set'
    PARAM_S_SYS_SM_ENABLED = 'sm_enabled'
    PARAM_S_SYS_FUNCTION = 'function'
    PARAM_S_SYS_PMIC_OPT = 'pmic_opt'
    PARAM_S_SYS_SS_ENABLE = 'ss_enable'
    PARAM_S_SYS_SS_PERCENTAGE = 'ss_percentage'
    PARAM_S_SYS_SS_MODULATION = 'ss_modulation'
    PARAM_S_SYS_NUM_STATES = 'num_pstates'
    PARAM_S_SYS_NUM_DBYTE = 'num_dbyte'
    PARAM_S_SYS_TRAIN_2D = 'train_2d'
    PARAM_S_SYS_FREQ_0 = 'freq_0'
    PARAM_S_SYS_FREQ_1 = 'freq_1'
    PARAM_S_SYS_FREQ_2 = 'freq_2'
    PARAM_S_DCD_FW_PARAMS = 'dcd_fw_params'
    PARAM_S_BUS = "boardBusConfig"
    PARAM_S_CA_BUS = "boardCABusConfig"
    PARAM_S_BASIC = "deviceInformation"
    PARAM_S_BASIC_DENSITY_PER_CHANNEL = "densityPerChannel"
    PARAM_S_BASIC_NUM_ROW_ADDRESS = "numRowAddresses"
    PARAM_S_BASIC_MEM_TYPE = 'memoryType'
    PARAM_S_BASIC_DIMM_TYPE = 'dimmType'
    PARAM_S_BASIC_NUM_PSTATES = 'numPstates'
    PARAM_S_BASIC_LP4X_MODE = 'lp4x_mode'
    PARAM_S_BASIC_ENABLE_DBI = 'enableDBI'
    PARAM_S_PHY = "phy"
    PARAM_S_PHY_INPUT_BASIC = "userInputBasic"
    PARAM_S_PHY_NUM_PSTATES = 'NumPStates'
    PARAM_S_PHY_NUM_DBYTE = 'NumDbyte'
    PARAM_S_PHY_NUM_RANK_DFI0 = "NumRank_dfi0"
    PARAM_S_PHY_NUM_RANK_DFI1 = "NumRank_dfi1"
    PARAM_S_PHY_TRAIN_2D = "Train2D"
    PARAM_S_PHY_MB_X8MODE = "X8Mode"
    PARAM_S_BOARD_CONFIG = 'boardConfig'
    PARAM_S_BOARD_CONFIG_UART_IOMUX = 'uartIomuxConfig'
    PARAM_S_BOARD_CONFIG_UART_IOMUX_SECTION = '# Custom UART IOMUX config'
    PARAM_S_BOARD_CONFIG_PMIC = 'pmicConfig'
    PARAM_S_BOARD_CONFIG_PMIC_OPTIONS = 'pmicConfigOptions'
    PARAM_S_BOARD_CONFIG_PMIC_COMMANDS = 'pmicCommands'
    PARAM_S_BOARD_CONFIG_PMIC_COMMANDS_SECTION = '# Custom PMIC config'
    PARAM_S_BOARD_CONFIG_PMIC_IOMUX = 'pmicIomux'
    PARAM_S_BOARD_CONFIG_PMIC_IOMUX_SECTION = '# Custom PMIC IOMUX config'
    PARAM_S_BOARD_CONFIG_GENERIC_IOMUX = 'genericIomuxConfig'
    PARAM_S_BOARD_CONFIG_GENERIC_IOMUX_SECTION = '# Custom IOMUX config'
    PARAM_S_BOARD_CONFIG_CMD = 'command'
    PARAM_S_BOARD_CONFIG_ADR = 'address'
    PARAM_S_BOARD_CONFIG_SZE = 'size'
    PARAM_S_BOARD_CONFIG_VAL = 'value'
    PARAM_S_BOARD_CONFIG_UART_PORTS = "uartPorts"
    PARAM_S_BOARD_CONFIG_DBI = "enableDisableDBI"
    PARAM_S_BOARD_CONFIG_TEMP_DERATING = "temperatureDerating"
    PARAM_S_DDRC_CUSTOM_CONFIG = 'ddrcCustomConfig'
    PARAM_S_DDRC_CUSTOM_CONFIG_SECTION = '# Custom DDRC config'
    PARAM_S_BOARD_CONFIG_DATA_RATE = 'ddrDataRateMbps'
    PARAM_S_BOARD_CONFIG_FREQ_SETPOINT_1 = 'freqSetPoint1'
    PARAM_S_BOARD_CONFIG_FREQ_SETPOINT_2 = 'freqSetPoint2'

    PARAM_S_SS_ENABLE = "spreadSpectrum"
    PARAM_S_SS_PERCENTAGE = "percentageSpread"
    PARAM_S_SS_MODULATION = "modulation"

    PARAM_S_INLINE_ECC_CONFIG = "inlineEccConfig"
    PARAM_S_INLINE_ECC_STATE = "state"
    PARAM_S_INLINE_ECC_GRANULARITY = "granularity"
    PARAM_S_INLINE_ECC_CONFIG_SHEET = "sheet"
    PARAM_S_INLINE_ECC_BINARY_ALIGNED = "binaryAligned"
    PARAM_S_INLINE_ECC_REGIONS = "regions"
    PARAM_S_INLINE_ECC_PARITY_REGIONS = "ecc_region"
    PARAM_S_INLINE_ECC_MEMORY_REGIONS = "mem_region"

    PARAM_S_INLINE_ECC_CONFIG_MX9 = "enableInlineEcc"
    PARAM_S_INLINE_ECC_REGIONS_MX9 = "inlineEccRegions"
    PARAM_S_INLINE_ECC_REGIONS_START_MX9 = "startAddressOfRegion"
    PARAM_S_INLINE_ECC_REGIONS_END_MX9 = "endAddressOfRegion"

    PARAM_S_INLINE_ECC_ALIGNED_REGIONS = "alignedRegions"
    PARAM_S_INLINE_ECC_NON_ALIGNED_REGIONS = "nonAlignedRegions"
    PARAM_S_INLINE_ECC_REGION_START = "startAddressOfRegion"
    PARAM_S_INLINE_ECC_REGION_DENSITY = "densityOfEachEccRegion"
    PARAM_S_INLINE_ECC_REGION_ATTRIBUTES = "eccAttributes"

    PARAM_S_CA_CONFIG = "caConfig"
    PARAM_S_CA_VREF_START_CONFIG = "ca_vref_start"
    PARAM_S_CA_VREF_END_CONFIG = "ca_vref_end"
    PARAM_S_CA_VREF_STEP_CONFIG = "ca_vref_step"
    PARAM_S_CA_TRAIN_STATUS = "CATrainOpt"

    PARAM_S_CA_VREF = "vrefCAConfig"
    PARAM_S_CA_VREF_RANGE = "vref_ca_range"
    PARAM_S_CA_VREF_VALUE = "vref_ca_value"

    PARAM_S_DQ_VREF = "vrefDQConfig"
    PARAM_S_DQ_VREF_RANGE = "vref_dq_range"
    PARAM_S_DQ_VREF_VALUE = "vref_dq_value"

    PARAM_S_ADDR_MIRRORING = "addrMirroringConfig"

    MRR_SNOOP = "mrrSnoop"
    RX_REPLICA = "rxReplica"

    # SKIP DDR init for SerDes if this param is present in json
    PARAM_SERDES_SKIP_DDR_PHY = "skipDdrPhy"

    PICKLE_ALIASES = {'MIMX8M': 'MX8M', 'MIMX8MM': 'MX8M_Mini', 'MIMX8MN': 'MX8M_Nano', 'MIMX8MP': 'MX8M_Plus',
                      'MIMX91': 'MX91', 'MIMX93': 'MX93', 'MIMX943': 'MX943', 'MIMX95': 'MX95',
                      'MIMX95_B0': 'MX95_B0', 'MIMX952': 'MX952', 'LX2160A': 'LX2', 'LX2162A': 'LX2'}
    PICKLE_EXTENSIONS = [".pkl"]
    PKL_DIR_NAME = "rpa"
    XLS_DIR_NAME = "excel"
    BIN_DIR_NAME = 'binaries'
    MAPPING_DIR_NAME = 'dictionaries'
    ERRATAS_DIR_NAME = 'erratas'
    REGS_HASH_DIR_NAME = 'phyinit/regs_hash'
    LIB_DIR_NAME = 'phyinit/sharedlib'

    IMX8_CSR_DIR_NAME = 'csr'
    IMX8_CSR_FILE_NAME = 'csr.json'

    TEMPLATES_DIR_NAME = 'templates'
    TEMPLATE_DIAG_OVERLAY_FILE_NAME = 'diags_template.html'
    TEMPLATE_EYE_COMPARE_SINGLE_CHART_FILE_NAME = 'diags_compare_template.html'
    TEMPLATE_EYE_COMPARE_DQ_TO_DQ_FILE_NAME = 'diags_compare_template_dq.html'
    DIAG_OVERLAY_FILE_NAME = 'data_eyes.html'
    PARAM_DIAG_OVERLAY_FILE = 'diag_overlay_file'
    EYE_COMPARE_SINGLE_CHART_FILE_NAME = 'data_eyes_compare_single_chart.html'
    DIAG_OVERLAY_DQ_TO_DQ_FILE_NAME = 'data_eyes_compare_dq_to_dq.html'

    DONE_MARKER = '****DONE****'

    phyinit_out_file_name = 'phy_training_out_1d2d.txt'
    retention_out_file_name = 'phy_training_out_1d2d_retention.txt'

    # name of files generated from PHY data
    imem_1d_bin = 'imem_1d.bin'
    imem_1d_txt = 'imem_1d.txt'
    dmem_1d_bin = ['dmem_1d.bin', 'msb_pstate_1.bin', 'msb_pstate_2.bin', 'msb_pstate_3.bin']
    dmem_1d_txt = ['dmem_1d.txt', 'msb_pstate_1.txt', 'msb_pstate_2.txt', 'msb_pstate_3.txt']
    imem_2d_bin = 'imem_2d.bin'
    imem_2d_txt = 'imem_2d.txt'
    dmem_2d_bin = 'dmem_2d.bin'
    dmem_2d_txt = 'dmem_2d.txt'

    # imem/dmem parameters
    FW_IMEM_1D_FILE_PATH = 'imem_fw_path_1d'
    FW_IMEM_1D_FILE_SIZE = 'imem_fw_size_1d'
    FW_IMEM_1D_SOURCE = 'imem_fw_source_1d'
    FW_DMEM_1D_FILE_PATH = 'dmem_fw_path_1d'
    FW_DMEM_1D_FILE_SIZE = 'dmem_fw_size_1d'
    FW_DMEM_1D_SOURCE = 'dmem_fw_source_1d'
    FW_IMEM_2D_FILE_PATH = 'imem_fw_path_2d'
    FW_IMEM_2D_FILE_SIZE = 'imem_fw_size_2d'
    FW_IMEM_2D_SOURCE = 'imem_fw_source_2d'
    FW_DMEM_2D_FILE_PATH = 'dmem_fw_path_2d'
    FW_DMEM_2D_FILE_SIZE = 'dmem_fw_size_2d'
    FW_DMEM_2D_SOURCE = 'dmem_fw_source_2d'

    # compressed imem/dmem parameters
    COMPRESS_FW_IMEM_1D_SIZE = 'compressed_imem_fw_size_1d'
    COMPRESS_FW_DMEM_1D_SIZE = 'compressed_dmem_fw_size_1d'
    COMPRESS_FW_IMEM_2D_SIZE = 'compressed_imem_fw_size_2d'
    COMPRESS_FW_DMEM_2D_SIZE = 'compressed_dmem_fw_size_2d'

    # diagnostics parameters
    DIAGS_IMEM_FILE_PATH = 'imem_diags_path'
    DIAGS_IMEM_SIZE = 'diag_imem_fw_size'
    DIAGS_IMEM_SOURCE = 'diag_imem_fw_source'
    DIAGS_DMEM_FILE_PATH = 'dmem_diags_path'
    DIAGS_DMEM_SIZE = 'diag_dmem_fw_size'
    DIAGS_DMEM_SOURCE = 'diag_dmem_fw_source'

    pie_file_name = 'pie'
    pie_txt_ext = '.txt'
    json_ext = '.json'

    phy_init_out_file_name = 'phy_init'
    phy_init_out_file_ext = '.c'
    comm_re = "^//"
    write16_re = r"^dwc_ddrphy_apb_wr\(32\'h([0-9a-fa-f]+),16\'h([0-9a-fa-f]+)\);"
    hex_num_re = "h[0-9a-fa-f]+"

    write16_txt = "io_write16"
    phy_io_write = "phy_io_write"

    phy_imem_addr = 0x50000
    phy_v2_dmem_addr = 0x54000
    phy_v3_dmem_addr = 0x58000
    phy_micro_cont_mux_sel_addr = 0xD0000
    phy_v3_csr_offset = 0x400

    DS_FILE_SUFFIX = "_config.ds"
    TIMING_FILE_SUFFIX = "_timing.c"
    indent = 4 * " "  # a 4 spaces wide tab
    U_SUFFIX = "U"

    ecc_file_name = "ecc_regions_info.json"
    vref_file_name = "vref_info.json"

    # Colours used for painting graphics.
    COLOR_HEX_BROWN = '#2D0A01'
    COLOR_HEX_GREEN = '#86B233'

    MEM_SIZE = {
        "32MB": "33554432",
        "64MB": "67108864",
        "128MB": "134217728",
        "256MB": "268435456",
        "384MB": "402653184",
        "512MB": "536870912",
        "768MB": "805306368",
        "1GB": "1073741824",
        "1.5GB": "1610612736",
        "2GB": "2147483648",
        "3GB": "3221225472",
        "4GB": "4294967296",
        "6GB": "6442450944",
        "8GB": "8589934592",
        "16GB": "17179869184",
        "All density": "0"
    }

    NUMBER_CORES = {
        "1 Core": "1",
        "2 Cores": "2",
        "3 Cores": "3",
        "4 Cores": "4",
        "5 Cores": "5",
        "6 Cores": "6"
    }

    RTT_PARK = {
        0: 0,
        1: 60,
        2: 120,
        3: 40,
        4: 240,
        5: 48,
        6: 80,
        7: 34
    }

    # PMIC initialization options
    PMIC_INIT_DEFAULT = 0
    PMIC_INIT_DISABLED = 1
    PMIC_INIT_CUSTOM = 2
    PMIC_INIT_UNKNOWN = 3

    # 1024 aligned mask
    ALIGN_TO_1K = 1024

    # PHY functions
    PHY_FULL_INIT = '0'
    PHY_EXEC_FIRMWARE = '3'
    PHY_FIRST_BOOT = '7'
    PHY_QUICK_BOOT = '8'

    # Diagnostic tests
    NO_DIAG_TEST = '0'
    SEND_BURST_WRITES_TEST = '2'
    SEND_BURST_READS_TEST = '3'
    SIMPLE_WRITE_READ_TEST = '4'
    TX_EYE_TEST = '5'
    RX_EYE_TEST = '6'
    MR_WRITE_TEST = '9'
    MR_READ_TEST = '0xA'


class JsonConfigField:
    """Fields for JSON configuration data files."""
    PROCESSOR = 'processor'
    MEMORY_TYPES = 'memory_types'
    FIRMWARE_VERSIONS = 'firmware_versions'
    TARGET_PARAMETERS = 'target_params'
    SYS_PARAMETERS = 'dcd_fw_params'
    DIAG_TEST_PARAMETERS = 'dcd_diag_params'
    PHY_PARAMETERS = 'phy_params'
    TESTS = 'tests'
    SCENARIOS = 'scenarios'
    TEST_NAME = 'name'
    TEST_MEMORY_TYPES = 'memory_types'
    TEST_PARAMETERS = 'parameters'
    TEST_PARAM_ID = 'id'
    TEST_PARAM_NAME = 'name'
    TEST_PARAM_DEFAULT_VAL = 'default-value'
    TEST_PARAM_OPTIONS = 'options'
    TEST_PARAM_START_ADDRESS = 'Start address'
    TEST_PARAM_SIZE = 'Size'
    TEST_PARAM_EN_DDR_MEM_CACHE = 'Enable DDR Memory cache'
    TEST_PARAM_PATTERN_OPTIONS = 'Pattern options'
    TEST_PARAM_PATTERN_USER_DEF = 'User defined'
    TEST_PARAM_PATTERN_HW_PRBS23 = 'Prbs23'
    TEST_PARAM_PATTERN_SW_PRBS23 = 'PRBS23'
    TEST_PARAM_PATTERN_RANDOM = 'Random'
    TEST_PARAM_PATTERN = 'Pattern'
    TEST_PARAM_1_BYTE_ACCESS_MODE = '1 byte access mode'
    TEST_PARAM_2_BYTES_ACCESS_MODE = '2 bytes access mode'
    TEST_PARAM_4_BYTES_ACCESS_MODE = '4 bytes access mode'
    TEST_PARAM_BIST_TEST_TYPE_OPTIONS = 'Test type options'
    TEST_PARAM_SOURCE_ADDRESS = 'Source address'
    TEST_PARAM_STOP_ON_FAIL = 'Stop on fail'
    TEST_PARAM_RUN_FOREVER = 'Run Forever'
    TEST_PARAM_SELECT_DIRECTION = 'Direction'
    TEST_PARAM_SELECT_BYTE_LANE = 'Select Byte Lane'
    TEST_PARAM_SELECT_BIT_LANE = 'Select Bit Lane'
    TEST_PARAM_CHIP_SELECT = 'Chip Select'
    TEST_PARAM_CHANNEL = 'Channel'
    TEST_PARAM_MODE_REGISTER = 'MR'
    TEST_PARAM_MODE_REGISTER_VALUE = 'MR Value'
    TEST_PARAM_INFINITE_BURST = 'Infinite Burst'
    TEST_PARAM_ADD_BURST_WRITE = 'Add Burst Write before Burst Read'
    TEST_PARAM_ITERATION_COUNT = 'Iteration Count'
    TEST_PARAM_NUMBERS_OF_CORES = 'Number of Cores'
    SCENARIO_NAME = 'name'
    SCENARIO_MEMORY_TYPES = 'memory_types'
    SCENARIO_PARAMETERS = 'parameters'
    SCENARIO_PARAMETER_NAME = 'name'
    SCENARIO_PARAMETER_ID = 'id'
    SCENARIO_PARAMETER_DEFAULT_VALUES = 'default-values'
    SCENARIO_PARAMETER_OPTIONS = 'options'
    SCENARIO_PARAM_PHY_ODT = 'PHY ODT'
    SCENARIO_PARAM_DRAM_DRIVER_STRENGTH = 'DRAM driver strength'
    SCENARIO_PARAM_PHY_DRIVER_STRENGTH = 'PHY driver strength'
    SCENARIO_PARAM_DRAM_ODT = 'DRAM ODT'
    SCENARIO_TESTS = 'tests'


# Fields for SPSDK YAML configuration data files.
class SpsdkYamlField:
    """Fields from SPSDK YAML configuration data files."""
    CONTAINERS = 'containers'
    CONTAINER = 'container'
    CONTAINER_SRK_SET = 'srk_set'
    CONTAINER_SRK_SET_OEM_VAL = 'oem'
    CONTAINER_USED_SRK_ID = 'used_srk_id'
    CONTAINER_SRK_REVOKE_MSK = 'srk_revoke_mask'
    CONTAINER_SIGNING_KEY = 'signing_key'
    CONTAINER_SRK_TABLE = 'srk_table'
    CONTAINER_SRK_TABLE_ARRAY = 'srk_array'
