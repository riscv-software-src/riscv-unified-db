# UDB VSCode Extension

A Visual Studio Code extension for working with **UDB (Unified Database)** specification files used in the [RISC-V Unified Database](https://github.com/riscv-software-src/riscv-unified-db) project. This extension works with the `.udb` file extension.


## Features
---

### Syntax Highlighting
Full syntax highlighting for UDB schema files, making it easier to read and navigate complex database definitions at a glance.

### Autocomplete
Context-aware autocomplete suggestions as you type, helping you write valid UDB schemas faster and with fewer errors.

### Schema Support
Dedicated support for the following UDB schema types:
- **CSR schemas** — author Control and Status Register definitions
- **Instruction schemas** — define and edit RISC-V instruction definitions
- **Extension schemas** — work with RISC-V extension definitions
- **Exception code schemas** — define exception codes
- **Instruction opcode schemas** — define instruction opcodes
- **Instruction variable type schemas** — define instruction variable types
- **Interrupt code schemas** — define interrupt codes
- **Manual schemas** — define manual metadata
- **Manual version schemas** — define manual version metadata
- **Non-ISA schemas** — define non-ISA specifications
- **Profile family schemas** — define profile families
- **Profile schemas** — define RISC-V profiles
- **Register file schemas** — define register files

Some schemas have partial support:
- **Config schemas** — define architecture configurations

### Cross-Referencing
Navigate across related schema definitions with cross-referencing support — jump to referenced definitions directly from within your editor.

<br>

## Workflows
---
There are two different ways to use this extension: Creating new RISC-V specifications and modifying existing RISC-V specifications (in the form of `.yaml` files),.

### Creating New Specifications
To create new specifications, simply create a file with the `.udb` file extension and enjoy the features! Once you're done, use the [convertudb.py](../../python/convertudb.py) Python script to convert the `.udb` file into a `.yaml` file as follows:
```
python convertudb.py [specification].udb
```
 This generates an equivalent `.yaml` file so that you can then push the new specification into the [RISC-V Unified Database](https://github.com/riscv-software-src/riscv-unified-db) repository.


### Modifying Existing Specifications
To modify existing specification files, use same the [convertudb.py](../../python/convertudb.py) Python script to first convert the existing `.yaml` file  into its `.udb` equivalent as follows:
```
python convertudb.py [specification].yaml
```
This generates a `.udb` file you can then use to make changes while taking advantage of this extension's features. After making your changes, you can use the same script to convert the `.udb` file back into a `.yaml` file before pushing it to the [RISC-V Unified Database](https://github.com/riscv-software-src/riscv-unified-db) repository.

<br>

## Requirements
---

- **Visual Studio Code** `v1.109.0` or higher
- **Java 21 or later** — required to run the language server
- **Python** — required to convert between `.yaml` and `.udb` files

<br>

## Installing Java
---

If you don't have Java 21+ installed, the extension will show an error with installation instructions. Here's a quick setup guide:

### macOS
```bash
brew install openjdk@21
```

### Windows
Download and install from [Adoptium](https://adoptium.net/) or [Oracle JDK](https://www.oracle.com/java/technologies/downloads/#java21)

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install openjdk-21-jdk
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install java-21-openjdk
```

Verify installation:
```bash
java -version
```

You should see output like:
```
openjdk version "21.0.x" ...
```

<br>

## Getting Started
---
1. Install Java 21+ (see above)
2. Install the extension from the VS Code Marketplace
3. Open a folder containing your UDB schema files
4. Start editing — syntax highlighting, autocomplete, and cross-referencing will activate automatically on `.udb` files

<br>

## Troubleshooting
---

### Language server doesn't start
1. Check the Output panel: `View → Output` and select **UDB Language Server** from the dropdown
2. Verify Java is installed: run `java -version` in your terminal
3. If Java is installed but the extension doesn't find it, configure the path in VS Code settings:

```json
"udb.javaPath": "/path/to/java"
```

For example on macOS with Homebrew:
```json
"udb.javaPath": "/opt/homebrew/opt/openjdk@21/bin/java"
```

### Version mismatch error
If you see an error about Java version, ensure you have Java 21 or later installed:
```bash
java -version
```

If you have multiple Java versions installed, use the `udb.javaPath` setting to point to Java 21+.

<br>

## Feedback & Contributions
---
This extension was developed by the **Harvey Mudd Clinic Team for Qualcomm** and is currently maintained by **Qualcomm**. For bugs or feature requests, please open an issue on the [project repository](https://github.com/niluo-shiqi/riscv-unified-db-hmc-clinic-team-).
