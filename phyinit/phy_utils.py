# Copyright 2021-2025 NXP

"""TODO:summary line."""
from enum import Enum


class PhyV2Utils:
    """PHY V2 utils."""

    start_phy_init = 'Start of dwc_ddrphy_phyinit_C_initPhyConfig'
    end_phy_init = 'End of dwc_ddrphy_phyinit_C_initPhyConfig'
    start_load_bin = '// [dwc_ddrphy_phyinit_WriteOutMem] STARTING'
    end_load_bin = '// [dwc_ddrphy_phyinit_WriteOutMem] DONE'
    start_load_pie = "// [phyinit_I_loadPIEImage] Start of dwc_ddrphy_phyinit_I_loadPIEImage()"
    end_load_pie = "// [phyinit_I_loadPIEImage] End"
    phyinit_set_dfi_clk = 'dwc_ddrphy_phyinit_userCustom_E_setDfiClk'
    start_phyinit_load_imem = 'Start of dwc_ddrphy_phyinit_D_loadIMEM'
    end_phyinit_load_imem = 'End of dwc_ddrphy_phyinit_D_loadIMEM'
    start_phyinit_load_dmem = 'Start of dwc_ddrphy_phyinit_F_loadDMEM'
    start_phyinit_skip_train = 'Start of dwc_ddrphy_phyinit_progCsrSkipTrain'
    end_phyinit_skip_train = 'End of dwc_ddrphy_phyinit_progCsrSkipTrain'


class PhyV3Utils:
    """PHY V3 utils."""

    COMMON_DATA = "common"
    PHY_CONFIG_PHASE = "C"
    PHY_CONFIG_DATA = "phyinit_C_initPhyConfig"
    PHY_CONFIG_PS_DATA = "phyinit_C_initPhyConfigPsLoop"
    IMEM_CONFIG_PHASE = "D"
    IMEM_CONFIG_DATA = "dwc_ddrphy_phyinit_D_loadIMEM"
    DMEM_CONFIG_PHASE = "F"
    DMEM1D_CONFIG_DATA = "dwc_ddrphy_phyinit_F_loadDMEM1D"
    DMEM2D_CONFIG_DATA = "dwc_ddrphy_phyinit_F_loadDMEM2D"
    PIE_CONFIG_PHASE = "I"
    PIE_CONFIG_DATA = "phyinit_I_loadPIEImage"
    PIE_CONFIG_PS_DATA = "dwc_ddrphy_phyinit_I_loadPIEImagePsLoop"
    SKIPTRAIN_DATA = "dwc_ddrphy_phyinit_progCsrSkipTrain"
    SKIPTRAIN_PS_DATA = "dwc_ddrphy_phyinit_progCsrSkipTrainPsLoop"


class PhyPhase(Enum):
    """Phy phases."""

    # A phases
    BRING_UP_POWER = (1, 'bringupPower')
    # B phases
    START_CLOCK_RESET_PHY = (2, 'startClockResetPhy')
    # C phases
    PHY_INIT_CONFIG = (3, 'initPhyConfig')
    # D phases
    LOAD_IMEM_1 = (4, 'loadIMEM_1')  # in this state we ignore the output for generating the  binary
    LOAD_IMEM_1D = (5, 'loadIMEM_1D')
    LOAD_IMEM_2 = (6, 'loadIMEM_2')
    LOAD_IMEM_2D = (7, 'loadIMEM_2D')
    # E phases
    SET_DFI_CLOCK = (8, 'setDfiClk')
    # F phases
    LOAD_DMEM_1 = (9, 'loadDMEM_1')
    LOAD_DMEM_1D = (10, 'loadDMEM_1D')
    LOAD_DMEM_2 = (11, 'loadDMEM_2')
    LOAD_DMEM_2D = (12, 'loadDMEM_2D')
    # G phases
    EXEC_FW = (13, 'exec_fw')
    # H phases
    READ_MSG_BLOCK = (14, 'readMsgBlock')
    # I phases
    LOAD_PIE = (15, 'loadPIEImage')
    # J phases
    ENTER_MISSION_MODE = (16, 'enterMissionMode')
    # Skip phase
    SKIP_TRAIN_MODE = (17, 'progCsrSkipTrain')


    def __init__(self, id: int, display_name: str) -> None:  # type: ignore
        """Constructor.

        @param id: phase id
        @param display_name: phase display name
        """
        self._id = id
        self._display_name = display_name

    @property
    def value(self) -> int:
        """Phase id."""
        return self._id

    @property
    def name(self) -> str:
        """Phase display name."""
        return self._display_name
