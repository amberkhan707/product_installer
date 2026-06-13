# NGInstaller Runtime

## Overview

NGInstaller Runtime is a Python-based software installation and deployment framework designed to automate software setup on both local and remote machines.

The application provides a graphical setup wizard and executes installation workflows based on a JSON configuration file. It supports Windows and Linux environments and can perform remote operations using SSH.

---

## Features

* Cross-platform support (Windows and Linux)
* GUI-based setup wizard
* JSON-driven installation workflow
* Local and remote software deployment
* SSH-based remote execution using Paramiko
* Automatic logging
* Third-party software installation
* PyInstaller executable support

---

## Project Structure

```text
installer_runtime/
│
├── bootstrap.py                  # Entry point
├── nginstaller_launcher.py       # Application launcher
├── sw_install.py                 # Core installation engine
│
├── config/
│   └── sw_config.json            # Installation configuration
│
├── UI/
│   ├── ui_setup_wizard.py        # GUI wizard
│   ├── styles.qss                # UI styling
│   └── images/                   # Icons and images
│
└── __pycache__/
```

---

## How It Works

1. `bootstrap.py` starts the application.
2. The launcher initializes logging and validates required folders.
3. The GUI setup wizard is launched.
4. Installation steps are loaded from `sw_config.json`.
5. The installer executes commands locally or remotely.
6. Logs are generated for troubleshooting.

---

## Configuration

All installation steps are managed through:

```text
config/sw_config.json
```

The configuration file contains:

* Software name
* Operating system
* Installation steps
* Commands to execute
* ZIP extraction details
* Environment variable updates
* Remote command support

Example:

```json
{
    "software": {
        "python": {
            "linux": {
                "steps": [
                    {
                        "cmd": "sudo apt-get update"
                    }
                ]
            }
        }
    }
}
```

---

## Requirements

### Python

* Python 3.10 or above

### Required Libraries

```text
paramiko
json
pathlib
logging
socket
zipfile
tempfile
shutil
```

Install dependencies:

```bash
pip install paramiko
```

---

## Running the Project

Run directly with Python:

```bash
python bootstrap.py
```

Or build and execute as a PyInstaller executable.

---

## Folder Requirements

The application expects the following directories:

```text
build_files/
third_party_softwares/
logs/
```

If any required folder is missing, the application will stop with an error.

---

## Logging

Log files are automatically created inside the `logs` directory.

Example:

```text
logs/
    installer_20260613_103000.log
    nginstaller.log
```

The logs contain:

* Application startup
* SSH connection status
* Installation progress
* Errors and exceptions

---

## Remote Installation

The installer supports remote execution through SSH.

Capabilities:

* Check host availability
* Establish SSH connection
* Execute remote commands
* Transfer and install software
* Maintain execution logs

---

## Supported Operations

* Command execution
* ZIP extraction
* Folder movement
* Environment variable updates
* Local installation
* Remote installation
* PowerShell command execution
* Linux package installation

---

## Technologies Used

* Python
* Paramiko
* PyInstaller
* JSON Configuration
* PowerShell
* Linux Shell Commands
* Qt-based UI Styling (QSS)

---

## Use Cases

* Product installation automation
* Server provisioning
* Software deployment
* Remote environment setup
* Internal enterprise installation tools

---

## Future Improvements

* Multi-machine parallel installation
* Progress dashboard
* Rollback mechanism
* Plugin architecture
* Configuration validation
* Detailed installation reports

---

## Author

Developed for automating software deployment and installation workflows across Windows and Linux environments.

---

## License

This project is intended for internal or organizational use. Update the license section according to your project requirements.
