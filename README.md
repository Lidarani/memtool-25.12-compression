# Memtool compression version

This repository contains the Python module taken from Config Tools for i.MX 25.12.
It represents the open-source part of the DDR Tool used for DDR memory
configuration and validation.

The 25.12 version of Config Tools for i.MX must be used. Other versions may
contain different board data and may not work with this module.

This module has been modified to enable compression support for DDR-related
firmware and data handled by the DDR Tool.

## Prerequisites
- VS Code. This project currently uses the VS Code workflow until it is
	integrated into the official architecture.
- The Serial Monitor VS Code extension or PuTTY for logging.
- Windows: WSL with the required build tools. Linux users can use Ubuntu
	20.04, 22.04, or 24.04.
- The ARM toolchain placed inside `imx-oei/tools`; see the `imx-oei` submodule
	README for toolchain instructions.
- An i.MX 95 board set to Serial Downloader mode and connected with two cables:
	USB 3.0 and Debug.

## Steps to use
Clone the repository and initialize the `imx-oei` submodule:

```bash
git clone <memtool-repository-url>
cd memtool
git submodule update --init --recursive
```

The `imx-oei` submodule is the compression-enabled fork hosted at
`https://github.com/Lidarani/imx-oei.git`.

Back up the original `memtool` directory before replacing it. Then copy this
repository's contents into the `bin/python3/memtool` directory in the Config
Tools for i.MX 25.12 installation.

Open the `memtool` folder in VS Code. From the Command Palette, select the
Python interpreter shipped with Config Tools for i.MX. From this workspace,
the interpreter is normally located at:

```text
..\python.exe
```

This allows the module to access the Python packages shipped with Config Tools.

Enter the `imx-oei` folder and build the DDR OEI image:

```bash
make img oei=ddr board=mx95lp4x-15 d=1 v=1
```

The `board` argument can also be `mx95lp4x` or `mx95lp5`, depending on the
target board.

Connect the board and open Config Tools for i.MX 25.12. Create a new
configuration and select the appropriate i.MX 95 derivative. Select DDR, open
the DDR Configuration panel, and choose the preset for the connected board.

Return to the DDR Test panel and use the flashlight button next to `Select COM
port` to find the connected device and generate the connection JSON. The tool
should find at least one HID and at least four grouped COM ports for the board.

To identify the correct COM port, select the Firmware Init test and start a
test on the four COM ports until one passes. After a normal PHY Init firmware
test passes, close Config Tools and return to the `memtool` folder in VS Code.

With the configuration generated, the Python interpreter selected, and the
paths aligned with the generated Config Tools files and the built `imx-oei`,
use the Run and Debug view in VS Code to run the DDR initialization flow. The
available launch configurations support both uncompressed and compressed
flows.

For the compressed flow, open the Serial Monitor VS Code extension and monitor
the other three COM ports associated with the board at 115200 baud. One port
will show the board output. After identifying it, close the other two monitors.