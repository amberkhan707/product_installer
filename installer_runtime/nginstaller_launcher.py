import os
import subprocess
import sys
from datetime import datetime

# Determine the operating system once
IS_WIN = sys.platform == "win32"

def setup_logging():
    log_dir = os.path.join(os.path.dirname(sys.executable), "logs") \
        if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(
        log_dir,
        f"installer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    sys.stdout = open(log_file, "w", buffering=1, encoding="utf-8")
    sys.stderr = sys.stdout

    print("=== NGInstaller Log Started ===")
    print("Log file:", log_file)
    print()

setup_logging()

def get_subprocess_kwargs():
    """Returns OS-specific subprocess arguments to hide windows."""
    kwargs = {}
    if IS_WIN:
        # CREATE_NO_WINDOW is Windows-only
        kwargs['creationflags'] = 0x08000000 # Integer value for CREATE_NO_WINDOW
    return kwargs

def run(cmd):
    kwargs = get_subprocess_kwargs()
    process = subprocess.run(cmd, **kwargs)
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")

def command_exists(cmd):
    kwargs = get_subprocess_kwargs()
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs
        ).returncode == 0
    except FileNotFoundError:
        return False

def get_paths():
    if getattr(sys, 'frozen', False):
        return {
            "temp_dir": sys._MEIPASS,
            "exe_dir": os.path.dirname(sys.executable)
        }
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        return {
            "temp_dir": base,
            "exe_dir": base
        }

paths = get_paths()
temp_dir = paths["temp_dir"]
exe_dir = paths["exe_dir"]
ui_dir = os.path.join(temp_dir, "installer_runtime", "UI")
build_dir = os.path.join(exe_dir, "build_files")

# Dynamically point to the correct OS folder
# Route based on your fixed folder structure
if IS_WIN:
    third_party_dir = os.path.join(exe_dir, "third_party_softwares", "windows")
else:
    # On Linux, files are directly in third_party_softwares
    third_party_dir = os.path.join(exe_dir, "third_party_softwares")

print("Starting UI Installer prerequisites setup...")
print("TEMP directory        :", temp_dir)
print("EXE directory         :", exe_dir)
print("UI directory          :", ui_dir)
print("Build files directory :", build_dir)
print("Third-party directory :", third_party_dir)

def fatal_error(msg):
    print(msg)
    # input() fails without a console. Catch EOFError for GUI apps.
    try:
        input("Press Enter to exit...")
    except EOFError:
        pass
    sys.exit(1)

if not os.path.exists(build_dir):
    fatal_error(f"Missing build_files folder at: {build_dir}")

if not os.path.exists(third_party_dir):
    fatal_error(f"Missing third_party_softwares folder at: {third_party_dir}")

print("Launching UI Setup Wizard...")

if temp_dir not in sys.path:
    sys.path.insert(0, temp_dir)

try:
    from installer_runtime.UI import ui_setup_wizard
except ImportError as e:
    print("Failed to import UI module:", e)
    print("Available files:", os.listdir(os.path.join(temp_dir, "installer_runtime", "UI")))
    fatal_error("Critical UI failure.")

ui_setup_wizard.main(build_dir, third_party_dir)
print("UI Installer started")
