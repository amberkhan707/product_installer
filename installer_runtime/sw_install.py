import os
import sys
import json
import subprocess
import paramiko
import re
import zipfile
import socket
import logging
import shutil
import traceback
import platform
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import uuid

# Base directory
if getattr(sys, 'frozen', False):
    # Running as PyInstaller EXE
    BASE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).resolve().parent
else:
    # Running as Python script
    BASE_DIR = Path(__file__).resolve().parent.parent
    EXE_DIR = BASE_DIR
    
PING_TIMEOUT = 1
SSH_TIMEOUT = 10
ROLE_IPS = {}
ROLE_DBS = {}
CURRENT_ROLE = None
CURRENT_OS = platform.system().lower()

## Create logs directory
LOG_DIR = EXE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log file path
LOG_FILE = LOG_DIR / "nginstaller.log"

# Logging configuration
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%b %d %H:%M:%S",
    filemode='a',
    force=True
)

logging.info(f"Application started on {CURRENT_OS}")
logging.info(f"BASE_DIR = {BASE_DIR}")
logging.info(f"EXE_DIR = {EXE_DIR}")

def load_config() -> Dict[str, Any]:
    """Loads and parses the JSON configuration file."""
    MACHINE_CONFIG_FILE = BASE_DIR /"installer_runtime"/ "config" / "sw_config.json"
    with open(MACHINE_CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in {MACHINE_CONFIG_FILE}: {e}")

def is_host_reachable(ip: str, timeout: int = 5) -> bool:
    try:
        if CURRENT_OS == "windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
        elif CURRENT_OS == "linux":
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip]

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0:
            alive = True

    except Exception:
        pass

    # fallback: check if SSH port is open
    try:
        with socket.create_connection((ip, 22), timeout=timeout):
            return True
    except OSError:
        return False

def ssh_connect(ip: str, username: str, password: str) -> paramiko.SSHClient:
    """Establishes a Paramiko SSH connection."""
    client = paramiko.SSHClient()
    known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    logging.info(f"[SSH] Connecting to {ip}")

    # Ensure .ssh directory exists
    os.makedirs(os.path.dirname(known_hosts), exist_ok=True)

    # Load known_hosts file if present
    if os.path.exists(known_hosts):
        client.load_host_keys(known_hosts)

    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=ip,
            username=username,
            password=password,
            timeout=SSH_TIMEOUT,
            allow_agent=False,
            look_for_keys=False
        )
        return client
    except Exception as e:
        logging.exception(f"[SSH FAILED] {ip}")
        raise Exception(f"SSH connection failed to {ip}: {e}")

def run_cmd(client: Optional[paramiko.SSHClient], step_config: Optional[Dict[str, Any]], password: Optional[str] = None, machine: Optional[Dict[str, Any]] = None, command: Optional[str] = None, cwd: Optional[str] = None, fail_on_error: Optional[bool] = None) -> int:
    
    if step_config:
        if command is None:
            # === NAYA LOGIC YAHAN HAI ===
            if client is not None:
                # Agar remote hai, toh pehle 'remote_cmd' dhoondho, na mile toh 'cmd' use karo
                command = step_config.get("remote_cmd", step_config.get("cmd"))
            else:
                # Agar local hai, toh hamesha sirf 'cmd' use karo
                command = step_config.get("cmd")
        
        use_sudo = step_config.get("use_sudo", True)
        if not use_sudo:
            password = None
            
        if fail_on_error is None:
            fail_on_error = step_config.get("fail_on_error", True)

        target_path = step_config.get("path")
        if cwd is None and target_path:
            if os.path.isabs(target_path):
                cwd = target_path
            else:
                cwd = os.path.abspath(os.path.join(EXE_DIR, target_path))

    # Fallback default if still None
    if fail_on_error is None:
        fail_on_error = True

    if not command:
        logging.error("Warning: No 'cmd' found to execute. Skipping.")
        return 0

    if CURRENT_OS == "linux":
        if password:
            if command and command.strip().startswith("sudo"):
                if "-S" not in command:
                    command = command.replace("sudo", "sudo -S", 1)
            else:
                command = f"sudo -S {command}"
            
        if client is None:
            logging.info(command)
            print(command)
            try:
                process = subprocess.run(
                    command,
                    cwd=cwd,                  
                    shell=True,               
                    input=(password + "\n") if (password and "sudo" in command) else None,
                    text=True,                
                    capture_output=True,      
                    executable='/bin/bash'    
                )
                
                out = process.stdout.strip()
                err = process.stderr.strip()
                exit_code = process.returncode

            except Exception as e:
                exit_code = 1
                out = ""
                err = str(e)

        else:
            # Remote handling
            final_cmd = command
            logging.info(final_cmd)
            print(final_cmd)
            if cwd:
                linux_cwd = cwd.replace("\\", "/")
                final_cmd = f"cd \"{linux_cwd}\" && {command}"

            try:
                stdin, stdout, stderr = client.exec_command(final_cmd, get_pty=False)
                
                if password and "sudo" in command:
                    stdin.write(password + "\n")
                    stdin.flush()

                exit_code = stdout.channel.recv_exit_status()
                out = stdout.read().decode().strip()
                err = stderr.read().decode().strip()

            except Exception as e:
                exit_code = 1
                out = ""
                err = str(e)
                
        if out:
            logging.info(f"  [OUT] {out}")
            print(f"  [OUT] {out}")
        if err:
            logging.error(f"  [OUT] {err}")
            print(f"  [ERR] {err}")

        if exit_code != 0 and fail_on_error:
            location = "LOCAL" if client is None else "REMOTE"
            raise RuntimeError(f"\n[ERROR] Command failed on {location} with exit code {exit_code}")

        return exit_code

    elif CURRENT_OS == "windows":
        shell_type = step_config.get("shell_type", "cmd").lower()
        cmd = step_config.get("cmd", "")
        args = step_config.get("arguments", "")
        fail_on_error = step_config.get("fail_on_error", True)
        full_cmd = f"{cmd} {args}".strip()

        # =====================================
        # REMOTE EXECUTION
        # =====================================
        if client:
            logging.info(f"[REMOTE CMD] {full_cmd}")
            print(f"[REMOTE CMD] {full_cmd}")

            # Always run through PowerShell on remote Windows
            ps_cmd = f'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -Command "{full_cmd}"'

            stdin, stdout, stderr = client.exec_command(
                ps_cmd,
                get_pty=False
            )

            exit_code = stdout.channel.recv_exit_status()

            out = stdout.read().decode()
            err = stderr.read().decode()

            if out:
                logging.info(out.strip())
                print(f"  [OUT] {out}")
            if err:
                logging.error(err.strip())
                print(f"  [ERR] {err}")

            if exit_code != 0 and fail_on_error:
                logging.error(f"[ERR] {err}")
                raise RuntimeError(f"Remote command failed:\n{err}")

            return

        # =====================================
        # LOCAL EXECUTION 
        # =====================================
        if shell_type == "powershell":
            logging.info(f"[LOCAL PS] {full_cmd}")
            print(f"[LOCAL PS] {full_cmd}")
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", full_cmd],
                check=fail_on_error
            )
        else:
            logging.info(f"[LOCAL CMD] {full_cmd}")
            print(f"[LOCAL CMD] {full_cmd}")
            subprocess.run(
                full_cmd,
                shell=True,
                check=fail_on_error
            )


def handle_copy_folder(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]) -> None:
    """Copies folders safely locally or remotely."""
    src_relative = step_config.get("source")
    dest_parent = step_config.get("destination")
    copy_contents_only = step_config.get("copy_contents_only", False)
    permission = step_config.get("permission", "755")

    local_src_path = os.path.abspath(os.path.join(EXE_DIR, src_relative))

    if not os.path.exists(local_src_path):
        raise FileNotFoundError(f"Source does not exist: {local_src_path}")

    src_name = os.path.basename(local_src_path.rstrip(os.sep))
    final_dest_path = (dest_parent if copy_contents_only else os.path.join(dest_parent, src_name)).replace("\\", "/")

    logging.info(f"Copying: {local_src_path} -> {final_dest_path}")
    print(f"Copying: {local_src_path} -> {final_dest_path}")

    is_dir = os.path.isdir(local_src_path)

    # REMOTE COPY
    if client:
        remote_dir_to_create = final_dest_path if is_dir else os.path.dirname(final_dest_path)
        
        remote_user = machine.get("username") if machine else "ppc"
        run_cmd(client, None, command=f"bash -c \"mkdir -p {remote_dir_to_create} && chown -R {remote_user}:{remote_user} {remote_dir_to_create}\"", password=password)
        
        sftp = client.open_sftp()
        try:
            if is_dir:
                for root, dirs, files in os.walk(local_src_path):
                    rel_path = os.path.relpath(root, local_src_path)
                    remote_root = (final_dest_path if rel_path == "." else os.path.join(final_dest_path, rel_path).replace("\\", "/"))
                    
                    try:
                        sftp.stat(remote_root)
                    except FileNotFoundError:
                        sftp.mkdir(remote_root)

                    for d in dirs:
                        dpath = os.path.join(remote_root, d).replace("\\", "/")
                        try:
                            sftp.stat(dpath)
                        except FileNotFoundError:
                            sftp.mkdir(dpath)

                    for f in files:
                        remote_file = os.path.join(remote_root, f).replace("\\", "/")
                        sftp.put(os.path.join(root, f), remote_file)
            else:
                sftp.put(local_src_path, final_dest_path)
            
            logging.info("Remote copy completed successfully")
            print("Remote copy completed successfully")
        finally:
            sftp.close()
        run_cmd(client, None, command=f"chmod -R {permission} {final_dest_path}", password=password)

    # LOCAL COPY
    else:
        local_dir_to_create = final_dest_path if is_dir else os.path.dirname(final_dest_path)
        run_cmd(None, None, command=f"mkdir -p {local_dir_to_create}", password=password)
        
        if is_dir:
            if copy_contents_only:
                run_cmd(None, None, command=f"cp -r {local_src_path}/* {final_dest_path}/", password=password)
            else:
                run_cmd(None, None, command=f"cp -r {local_src_path} {dest_parent}/", password=password)
        else:
            run_cmd(None, None, command=f"cp {local_src_path} {final_dest_path}", password=password)
            
        run_cmd(None, None, command=f"chmod -R {permission} {final_dest_path}", password=password)
        logging.info("Local copy completed successfully")
        print("Local copy completed successfully")

    logging.info(f"Permissions ({permission}) applied on {final_dest_path}")
    print(f"Permissions ({permission}) applied on {final_dest_path}")

def handle_modify_files(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]) -> None:
    src_dir = step_config.get("src")
    files = step_config.get("files", [])
    
    # 1. Fetch raw line and replaced_line
    raw_lines = step_config.get("line")
    raw_replaced_lines = step_config.get("replaced_line")
    db_replacement = step_config.get("db_replacement", False)
    
    # Configuration load karna aur machines list nikalna
    linux_config = load_config()
    machines = linux_config.get("machines", [])

    if not all([src_dir, files, raw_lines]):
        raise ValueError("modify_files: Missing required configuration fields (src, files, or line)")

    # 2. String ko List me convert karo (Backward compatibility ke liye)
    lines_list = raw_lines if isinstance(raw_lines, list) else [raw_lines]
    
    replaced_lines_list = []
    if raw_replaced_lines:
        replaced_lines_list = raw_replaced_lines if isinstance(raw_replaced_lines, list) else [raw_replaced_lines]

    # 3. Aapka purana db_replacement logic
    if db_replacement:
        db_list = linux_config.get("dbstring")
        logging.info(db_list)
        print(db_list)

        if not db_list or not isinstance(db_list, (list, tuple)):
            raise ValueError("modify_files: 'db_replacement' is True but no 'dbstring' list found")

        new_replaced_lines = []
        for m_line in lines_list:
            if "=" not in m_line:
                raise ValueError("modify_files: 'line' must contain '='")
            key_part = m_line.rsplit("=", 1)[0].strip()
            new_replaced_lines.append(f"{key_part}={','.join(db_list)}")
        
        replaced_lines_list = new_replaced_lines

    if not replaced_lines_list:
        raise ValueError("modify_files: missing 'replaced_line'")
        
    # Validation: Dono lists ki length same honi chahiye
    if len(lines_list) != len(replaced_lines_list):
        raise ValueError("modify_files: 'line' and 'replaced_line' lists must have the same length")

    # EXE_DIR globally define hona chahiye (Aapke original code ke mutabiq)
    src_dir = os.path.join(EXE_DIR, src_dir)

    # 4. Pehle Har File par jao
    for file_name in files:
        file_path = f"{src_dir.rstrip('/')}/{file_name}"
        run_cmd(client, None, command=f"chmod u+rw '{file_path}'", password=password, fail_on_error=False)

        # 5. Phir us file me list ke har index/line ko replace karo
        for idx in range(len(lines_list)):
            current_match_line = lines_list[idx]
            current_replaced_line = replaced_lines_list[idx]

            # === NAYA FLAG: Check karne ke liye ki line skip karni hai ya nahi ===
            should_skip_line = False

            # === NAYA LOGIC: DYNAMIC PLACEHOLDER RESOLUTION ===
            # Line ke andar jahan bhi {{kuch-bhi}} likha hai, usko dhoondho
            placeholders = re.findall(r'\{\{(.*?)\}\}', current_replaced_line)
            
            for ph in placeholders:
                if "-" in ph:
                    # Example: 'Historian1-IP' -> role_part='Historian1', prop_part='IP'
                    # rsplit ensures ki agar username me dash ho toh split galat jagah se na ho
                    role_part, prop_part = ph.rsplit("-", 1)
                    
                    # Normalize formatting for robust matching 
                    clean_target_role = role_part.replace("-", "").upper()
                    clean_prop = prop_part.lower()
                    
                    # Configured machines list me se exact machine dhoondho
                    target_machine = next((m for m in machines if m.get("role", "").replace("-", "").upper() == clean_target_role), None)
                    
                    if target_machine:
                        val = ""
                        if clean_prop == "ip":
                            val = target_machine.get("ip", "")
                        elif clean_prop in ["user", "username"]:
                            val = target_machine.get("username", "")
                        elif clean_prop in ["password", "pwd"]:
                            val = target_machine.get("password", "")
                            
                        # Agar value mil gayi toh original string me {{placeholder}} ko replace kar do
                        if val:
                            current_replaced_line = current_replaced_line.replace(f"{{{{{ph}}}}}", str(val))
                        else:
                            should_skip_line = True # Value nahi mili, line skip hogi
                            break
                    else:
                        should_skip_line = True # Machine hi nahi mili, line skip hogi
                        break
            # ==================================================

            # Agar flag True ho gaya, toh is line ko chhod kar agle index par jao
            if should_skip_line:
                logging.info(f"Skipping line update: '{current_match_line}' (Required machine/property not found).")
                print(f"Skipping line update: '{current_match_line}' (Required machine/property not found).")
                continue

            # === AAPKA EXACT PURANA LOGIC YAHAN HAI ===
            prefix_to_match = "=".join(current_match_line.split("=", 2)[:2])
            escaped_match = re.escape(prefix_to_match)
            escaped_match = re.sub(r'\\ ', r'\\s+', escaped_match)

            sed_cmd = (f"sed -i -E '/^[[:space:]]*#/! s|^[[:space:]]*{escaped_match}.*$|{current_replaced_line}|' '{file_path}'")
            run_cmd(client, None, command=f"bash -c \"{sed_cmd}\"", password=password, fail_on_error=False)
            # ==========================================
            
        logging.info(f"Updated (if matched): {file_path}")
        print(f"Updated (if matched): {file_path}")

def handle_env_setup(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]) -> None:
    """Updates .bashrc idempotently."""
    bashrc_path = step_config.get("env_path", "/home/ppc/.bashrc")
    configured_path = step_config.get("configured_path")

    if not configured_path:
        return

    export_line = f"export PATH=$PATH:{configured_path}"
    
    cmd = f"grep -qF \"{export_line}\" {bashrc_path} || echo \"{export_line}\" >> {bashrc_path}"

    logging.info(f"  [ENV] Checking/Updating PATH in {bashrc_path}...")
    print(f"  [ENV] Checking/Updating PATH in {bashrc_path}...")
    run_cmd(client, None, command=cmd)
 
def handle_extract(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    src = os.path.join(EXE_DIR, step_config["source"])
    dest = step_config["destination"]

    # === NAYA LOGIC: File Transfer for Remote Machine ===
    if client is not None:
        try:
            sftp = client.open_sftp()
            file_name = os.path.basename(src)
            remote_src = f"/tmp/{file_name}"
            
            print(f"[INFO] Uploading local file '{src}' to remote '{remote_src}'...")
            sftp.put(src, remote_src)
            sftp.close()
            
            # Ab remote par tar file ka path yeh hoga
            extract_src = remote_src
        except Exception as e:
            print(f"[ERROR] Failed to transfer file via SFTP: {e}")
            raise e
    else:
        # Agar local machine hai, toh direct original path use hoga
        extract_src = src
    # ====================================================

    run_cmd(client, None, command=f"sudo rm -rf '{dest}'", password=password)
    run_cmd(client, None, command=f"sudo mkdir -p '{dest}'", password=password)
    
    # Yahan 'src' ki jagah humne naya variable 'extract_src' laga diya hai
    run_cmd(client, None, command=f"sudo tar -xzf '{extract_src}' -C '{dest}'", password=password)

    flatten_cmd = (
        f"if [ \"$(ls -1 '{dest}' | wc -l)\" -eq 1 ] && "
        f"[ -d '{dest}/'$(ls -1 '{dest}') ]; then "
        f"inner=$(ls -1 '{dest}'); "
        f"mv '{dest}/'$inner/* '{dest}/' && rm -rf '{dest}/'$inner; fi"
    )
    run_cmd(client, None, command=f"bash -c '{flatten_cmd}'", password=password)
    run_cmd(client, None, command=f"sudo chmod 755 '{dest}/liquibase'", password=password)

    # === CLEANUP: Agar remote par file bheji thi, toh extract hone ke baad delete kar do ===
    if client is not None:
        run_cmd(client, None, command=f"sudo rm -f '{extract_src}'", password=password)

def handle_add_config(client: Optional[paramiko.SSHClient],step_config: Dict[str, Any],password: str, machine : Optional[Dict[str, Any]]) -> None:
    conf_file = step_config.get("conf_file")
    lines = step_config.get("configuration_append", [])

    if not conf_file or not lines:
        return

    if not conf_file.startswith("/"):
        conf_file = f"/{conf_file}"

    print(f"    Writing {conf_file}...")
    logging.info(f"    Writing {conf_file}...")
    content = "\n".join(lines) + "\n"

    cmd = f"""sudo bash -c 'cat << "EOF" > "{conf_file}"
{content}EOF'
"""
    run_cmd(client, None, command=cmd, password=password)
    run_cmd(client, None, command="sudo systemctl daemon-reload", password=password)

    if conf_file.endswith(".service"):
        service_name = conf_file.split("/")[-1]
        run_cmd(client, None, command=f"sudo systemctl enable {service_name}", password=password)

def handle_create_db(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]) -> None:
    CONFIG = load_config()

    if CURRENT_OS == "linux":
        path = step_config.get("path")
        db_user = step_config.get("db_user", "postgres")
        db_password = step_config.get("db_password")

        if not path:
            raise ValueError("path is required in step_config")

        # ==========================================
        # RESOLVED 1: DYNAMIC PATH VALIDATION
        # ==========================================
        if client:
            # REMOTE CASE: Use SFTP to check if directory exists on target node
            try:
                sftp = client.open_sftp()
                sftp.stat(path)
                sftp.close()
            except FileNotFoundError:
                raise FileNotFoundError(f"Remote directory not found on target machine: {path}")
        else:
            # LOCAL CASE: Standard OS path check
            if not os.path.isdir(path):
                raise FileNotFoundError(f"Local directory not found: {path}")

        if not db_password:
            raise ValueError("db_password is required")

        # Fetch dynamic variables
        remote_user = machine.get("username") if machine else "ppc"
        script_name = step_config.get("script_name", "./ppc.sh") 

        # === NAYA LOGIC: DBNAME DIRECTLY FROM MACHINE CONFIG ===
        if not machine or not machine.get("dbname"):
            raise ValueError("Machine configuration is missing 'dbname'. Cannot create DB.")
        
        # Current machine ka dbname nikal liya
        dbname = machine.get("dbname")
        current_role = machine.get("role", "UNKNOWN")
        # =======================================================

        print(f"\n[CREATE-DB] Starting dynamic DB creation for machine role: {current_role}...")
        logging.info(f"\n[CREATE-DB] Starting dynamic DB creation for machine role: {current_role}...")

        logging.info(f"[CREATE-DB] Creating database: {dbname}")
        print(f"[CREATE-DB] Creating database: {dbname}")

        cmd = (
            f"sudo -E -u {remote_user} bash -c "
            f"'export PATH=$PATH:/opt/liquibase && {script_name} {db_user} {db_password} {dbname}'"
        )

        # Using your run_cmd handles Local/Remote automatically.
        exit_code = run_cmd(
            client=client,
            step_config=None,
            command=cmd,
            cwd=path,          # run_cmd will automatically cd to this path locally or remotely
            password=password, 
            fail_on_error=False
        )

        if exit_code != 0:
            error_msg = f"[CREATE-DB] ERROR: Database creation failed for {dbname} (exit code {exit_code}). Ignoring error and continuing..."
            print(error_msg)
            logging.error(error_msg)
        else:
            print(f"[CREATE-DB] {dbname} created successfully")
            logging.info(f"[CREATE-DB] {dbname} created successfully")
            
        print("\n[CREATE-DB] DB creation process completed.")
        logging.info("\n[CREATE-DB] DB creation process completed.")

    elif CURRENT_OS == "windows":
        bat_path = Path(step_config["bat_path"])
        db_user = step_config["db_user"]
        db_password = step_config["db_password"]

        db_list = CONFIG.get("dbstring", [])
        if not db_list:
            logging.info("[PPCTODO] No databases defined")
            print("[PPCTODO] No databases defined")
            return

        for db_name in db_list:
            logging.info(f"[PPCTODO] Creating DB: {db_name}")
            print(f"[PPCTODO] Creating DB: {db_name}")

            subprocess.run(
                [
                    str(bat_path),
                    db_user,
                    db_password,
                    db_name,
                    db_name
                ],
                cwd=str(bat_path.parent),  # <-- THIS is critical
                shell=True,
                check=True
            )


def handle_modify_json(client: Optional[Any], step_config: Dict[str, Any], password: str, machine: Optional[Dict[str, Any]]) -> None:
    json_path = step_config.get("path")
    key_path = step_config.get("key")
    value_template = step_config.get("value")
    keep_master = step_config.get("keep_master", False)

    if not all([json_path, key_path, value_template]):
        raise ValueError("modify_json requires 'path', 'key', and 'value'")

    full_config = load_config()
    machines = full_config.get("machines", [])
    
    master = next(
            (m for m in machines if m.get("role") in ["MASTER", "HMI"]),
            None
        )

    if not master or not master.get("ip"):
        raise ValueError("MASTER machine or MASTER IP not found in config")

    master_ip = master["ip"]
    current_ip = machine.get("ip") if machine else None
    current_dbname = machine.get("dbname") if machine else None

    # slaves_configuration handling
    if value_template == "slaves_configuration":
        slaves_dict = {}
        for m in machines:
            if m.get("role") == "MASTER":
                continue
            dbname = m.get("dbname")
            ip = m.get("ip")
            if not dbname or not ip:
                continue
            key_name = dbname.upper()  
            slaves_dict[key_name] = {
                "IP": ip,
                "Port": 5000
            }
        final_value = slaves_dict

    # app_configuration handling
    elif value_template == "app_configuration":
        profiles_dict = {}
        if keep_master:
            profiles_dict["PPCMMRedis"] = {
                "IP": master_ip,
                "Port": "6379",
                "Password": "",
                "NoOfRetry": 3
            }
        configs = machine.get("config", []) if machine else []
        for idx, role in enumerate(configs, start=1):
            role_machine = next((m for m in machines if m.get("role") == role), None)
            if not role_machine:
                continue
            ip = role_machine.get("ip")
            if not ip:
                continue
            key_name = f"PPC{idx}Redis"
            profiles_dict[key_name] = {
                "IP": ip,
                "Port": "6379",
                "Password": "",
                "NoOfRetry": 3
            }
        final_value = profiles_dict

    else:
        final_value = value_template
        if isinstance(final_value, str):
            if "MASTER_IP" in final_value:
                final_value = final_value.replace("MASTER_IP", master_ip)

            if "PARENT_IP" in final_value and machine:
                parent_role = machine.get("parent_role")
                if parent_role:
                    parent_machine = next(
                        (m for m in machines if m.get("role") == parent_role),
                        None
                    )
                    if parent_machine and parent_machine.get("ip"):
                        final_value = final_value.replace(
                            "PARENT_IP",
                            parent_machine["ip"]
                        )

            if "IP" in final_value and current_ip:
                final_value = final_value.replace("IP", current_ip)

            if "db_name" in final_value and current_dbname:
                final_value = final_value.replace("db_name", current_dbname)

            try:
                final_value = json.loads(final_value)
            except (ValueError, TypeError):
                pass

    # =======================================================
    # === NAYA LOGIC: SMART JSON PLACEHOLDER RESOLUTION ===
    # =======================================================
    def resolve_placeholders(data):
        """
        Recursively JSON ko check karta hai. Agar kisi machine ka data na mile, 
        toh us pure dictionary block ko array me se hata deta hai.
        """
        if isinstance(data, str):
            placeholders = re.findall(r'\{\{(.*?)\}\}', data)
            if not placeholders:
                return data
            
            resolved_str = data
            for ph in placeholders:
                if "-" in ph:
                    role_part, prop_part = ph.rsplit("-", 1)
                    clean_target_role = role_part.replace("-", "").upper()
                    clean_prop = prop_part.lower()

                    target_machine = next((m for m in machines if m.get("role", "").replace("-", "").upper() == clean_target_role), None)

                    if target_machine:
                        val = ""
                        if clean_prop == "ip":
                            val = target_machine.get("ip", "")
                        elif clean_prop in ["user", "username"]:
                            val = target_machine.get("username", "")
                        elif clean_prop in ["password", "pwd"]:
                            val = target_machine.get("password", "")

                        if val:
                            resolved_str = resolved_str.replace(f"{{{{{ph}}}}}", str(val))
                        else:
                            return None # Property nahi mili, mark as invalid
                    else:
                        return None # Machine nahi mili, mark as invalid
            return resolved_str

        elif isinstance(data, list):
            new_list = []
            for item in data:
                res = resolve_placeholders(item)
                if res is not None:
                    new_list.append(res)
            return new_list

        elif isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                res = resolve_placeholders(v)
                if res is None:
                    # Agar dict ke andar kisi bhi key me placeholder resolve nahi hua,
                    # toh pura ka pura dict block hi drop kar do.
                    return None 
                new_dict[k] = res
            return new_dict
            
        else:
            return data

    # Final Value ko filter hone bhejo
    final_value = resolve_placeholders(final_value)

    # Agar value puri tarah None ho gayi (matlab kuch update karne ko bacha hi nahi)
    if final_value is None:
        logging.info(f"Skipping JSON update for '{key_path}': Required machine/property not found.")
        print(f"Skipping JSON update for '{key_path}': Required machine/property not found.")
        return
    # =======================================================

    def update_nested_dict(data_dict: dict, path_str: str, val: Any):
        path_str = path_str.replace('[', '.').replace(']', '')
        keys = [k for k in path_str.split(".") if k]
        
        cur = data_dict
        for i, k in enumerate(keys[:-1]):
            if isinstance(cur, list):
                k = int(k)
            
            next_k = keys[i+1]
            
            try:
                _ = cur[k]
            except (KeyError, IndexError):
                next_val = [] if next_k.isdigit() else {}
                if isinstance(cur, dict):
                    cur[k] = next_val
                elif isinstance(cur, list):
                    cur.insert(k, next_val)
                    
            cur = cur[k]

        last_k = keys[-1]
        if isinstance(cur, list):
            cur[int(last_k)] = val
        else:
            cur[last_k] = val

    local_tmp = None
    remote_tmp = f"/tmp/tmp_json_{uuid.uuid4().hex}.json"

    try:
        if client is None:
            if not os.path.exists(json_path):
                raise FileNotFoundError(f"File not found: {json_path}")

            tf = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json")
            local_tmp = tf.name

            with open(json_path, "r") as f:
                data = json.load(f)

            update_nested_dict(data, key_path, final_value)

            json.dump(data, tf, indent=2)
            tf.close()

            run_cmd(None, None, command=f"mv {local_tmp} {json_path}", password=password)

        else:
            sftp = client.open_sftp()
            try:
                tf = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json")
                local_tmp = tf.name
                tf.close()

                sftp.get(json_path, local_tmp)

                with open(local_tmp, "r") as f:
                    data = json.load(f)

                update_nested_dict(data, key_path, final_value)

                with open(local_tmp, "w") as f:
                    json.dump(data, f, indent=2)

                sftp.put(local_tmp, remote_tmp)
                run_cmd(client, None, command=f"mv {remote_tmp} {json_path}", password=password)
            finally:
                sftp.close()

    finally:
        if local_tmp and os.path.exists(local_tmp):
            try:
                os.remove(local_tmp)
            except Exception:
                pass
    logging.info(f"JSON updated: {key_path} -> {final_value}")
    print(f"JSON updated: {key_path} -> {final_value}")

def sftp_copy_zip(client: Optional[paramiko.SSHClient], local_zip: Path) -> Path:
    """
    Copies a ZIP from local MASTER to remote SL staging directory.
    Returns remote ZIP path.
    """
    if not client:
        return local_zip

    remote_dir = "C:/NGInstaller_Staging"
    remote_zip = f"{remote_dir}/{local_zip.name}"

    sftp = client.open_sftp()

    try:
        # ensure remote dir
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            sftp.mkdir(remote_dir)

        # copy only if missing
        try:
            sftp.stat(remote_zip)
            logging.info(f"[SFTP] Exists, skipping: {remote_zip}")
            print(f"[SFTP] Exists, skipping: {remote_zip}")
        except FileNotFoundError:
            logging.info(f"[SFTP] Copy {local_zip} -> {remote_zip}")
            print(f"[SFTP] Copy {local_zip} -> {remote_zip}")
            sftp.put(str(local_zip), remote_zip)

    finally:
        sftp.close()

    return Path(remote_zip)

def handle_zip_extract(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine: Optional[Dict[str, Any]]):
    zip_path_input = step_config["relative_zip_path"]
    extract_to = step_config["extract_to"]

    # ============================
    # Resolve zip by prefix
    # ============================
    zip_parent = Path(zip_path_input).parent

    if zip_parent.parts and zip_parent.parts[0] in ("third_party_softwares", "build_files"):
        zip_dir = EXE_DIR / zip_parent
    else:
        zip_dir = BASE_DIR / zip_parent
    zip_prefix = Path(zip_path_input).name.split(".zip")[0]

    matched_files = list(zip_dir.glob(f"{zip_prefix}*.zip"))
    if not matched_files:
        raise FileNotFoundError(f"No zip file found starting with {zip_prefix} in {zip_dir}")
    
    # Replace the zip_path in step_config with the actual matched file
    zip_path = matched_files[0]
    step_config["relative_zip_path"] = str(zip_path)

    # ============================
    # REMOTE MODE
    # ============================
    if client:
        remote_zip = sftp_copy_zip(client, zip_path)
        step_config["relative_zip_path"] = str(remote_zip)
        extract_to = Path("C:/NGInstaller_Staging")

        ps_cmd = f"$ProgressPreference='SilentlyContinue'; Expand-Archive -Force \"{remote_zip}\" \"{extract_to}\""
        run_cmd(client, {"shell_type": "powershell", "cmd": ps_cmd})
        return

    # ============================
    # LOCAL MODE
    # ============================
    zip_path = Path(zip_path)
    extract_to = EXE_DIR / extract_to
    logging.info(f"[ZIP] {zip_path} -> {extract_to}")
    print(f"[ZIP] {zip_path} -> {extract_to}")

    if not zip_path.exists():
        logging.error(f"ZIP not found: {zip_path}")
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

    logging.info("[ZIP] Extraction completed")
    print("[ZIP] Extraction completed")

def handle_remote_copy(
    client: Optional[paramiko.SSHClient],
    step_config: Dict[str, Any],
    password: str,
    machine: Optional[Dict[str, Any]]
):
    # Resolve source path properly
    path = Path(step_config["source"])
    source = path if path.is_absolute() else EXE_DIR / path
    destination = step_config["destination"]

    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    logging.info(f"[REMOTE COPY] {source} -> {destination}")
    print(f"[REMOTE COPY] {source} -> {destination}")

    # ============================
    # LOCAL MODE
    # ============================
    if not client:
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        print("[COPY] Local copy completed")
        return

    # ============================
    # REMOTE MODE
    # ============================
    sftp = client.open_sftp()

    try:
        # Ensure remote directories exist
        remote_parts = destination.replace("\\", "/").split("/")
        current_path = ""
        for part in remote_parts:
            if not part:
                continue
            current_path = f"{current_path}/{part}" if current_path else part
            try:
                sftp.mkdir(current_path)
            except:
                pass  # already exists

        # Upload logic (iterative, no recursion)
        if source.is_file():
            sftp.put(str(source), destination)
        else:
            stack = [(source, destination)]

            while stack:
                local_dir, remote_dir = stack.pop()

                try:
                    sftp.mkdir(remote_dir)
                except:
                    pass

                for item in local_dir.iterdir():
                    remote_item = f"{remote_dir}/{item.name}"

                    if item.is_dir():
                        stack.append((item, remote_item))
                    else:
                        sftp.put(str(item), remote_item)

    finally:
        sftp.close()

    print("[REMOTE COPY] Completed")

def handle_env_change(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    name = step_config["env_var"]
    raw_value = str(step_config["env_path"]).strip()
    # =============================
    # Replace dynamic placeholders
    # =============================
    if machine:
        if "${dbstring}" in raw_value:
            dbs = ",".join(machine.get("dbstring", []))
            raw_value = raw_value.replace("${dbstring}", dbs)
    # Detect path-like values
    is_path = (
        "\\" in raw_value
        or "/" in raw_value
        or raw_value.startswith(".")
        or Path(raw_value).drive
    )

    p = Path(raw_value)
    if is_path:
        value = str(p if p.is_absolute() else EXE_DIR / p)
    else:
        value = raw_value
    logging.info(f"[ENV] Setting {name} = {value}")
    print(f"[ENV] Setting {name} = {value}")

    # =============================
    # REMOTE
    # =============================
    if client:
        ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

        cmds = [
            f'[System.Environment]::SetEnvironmentVariable("{name}","{value}","Process")',
            f'[System.Environment]::SetEnvironmentVariable("{name}","{value}","User")',
            f'[System.Environment]::SetEnvironmentVariable("{name}","{value}","Machine")'
        ]

        if is_path:
            cmds.append(
                '$p=[System.Environment]::GetEnvironmentVariable("PATH","Machine");'
                f'if ($p -notlike "*{value}*") '
                '{{[System.Environment]::SetEnvironmentVariable("PATH",$p+";{value}","Machine")}}'
            )

        ps_cmd = "; ".join(cmds)
        ps_cmd = ps_cmd.replace('"', '\\"')
        stdin, stdout, stderr = client.exec_command(
            f'{ps_exe} -NoProfile -Command "{ps_cmd}"'
        )

        exit_code = stdout.channel.recv_exit_status()
        err = stderr.read().decode()

        if exit_code != 0:
            logging.error(f"[REMOTE ENV FAILED]\n{err}")
            raise RuntimeError(f"[REMOTE ENV FAILED]\n{err}")

        print("[REMOTE ENV] Applied")
        logging.info("[REMOTE ENV] Applied")
        return

    # =============================
    # LOCAL 
    # =============================
    for scope in ("Process", "User", "Machine"):
        subprocess.run(
            [
                "powershell",
                "-Command",
                f'[System.Environment]::SetEnvironmentVariable("{name}","{value}","{scope}")'
            ],
            check=True
        )

    os.environ[name] = value

    if is_path:
        current_machine_path = subprocess.check_output(
            [
                "powershell",
                "-Command",
                "[System.Environment]::GetEnvironmentVariable('PATH','Machine')"
            ],
            text=True
        ).strip()

        if value.lower() not in map(str.lower, current_machine_path.split(";")):
            new_path = f"{current_machine_path};{value}" if current_machine_path else value
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    f'[System.Environment]::SetEnvironmentVariable("PATH","{new_path}","Machine")'
                ],
                check=True
            )

def handle_move_folder(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    """
    Robust folder move function.
    Works for REMOTE (PowerShell over SSH) and LOCAL.
    Correctly handles spaces and special characters in paths.
    """
    path = Path(step_config["destination"])
    dst = path if path.is_absolute() else EXE_DIR / path

    # REMOTE
    if client:
        src_name = Path(step_config["source"]).name
        src = Path(f"C:/NGInstaller_Staging/{src_name}")
        dst_parent = dst.parent

        ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        def quote_path(path: Path):
            p = str(path).replace("'", "''")
            return f"'{p}'"

        src_quoted = quote_path(src)
        dst_quoted = quote_path(dst)
        dst_parent_quoted = quote_path(dst_parent)


        cmd = (
            f"$src={src_quoted}; "
            f"$dst={dst_quoted}; "
            f"$dst_parent={dst_parent_quoted}; "
            f"if (-Not (Test-Path $src)) {{ Write-Host '[REMOTE MOVE] Source not found, skipping'; exit 0 }}; "
            f"if (Test-Path $dst) {{ Write-Host '[REMOTE MOVE] Destination exists, skipping'; exit 0 }}; "
            f"if (-Not (Test-Path $dst_parent)) {{ New-Item -ItemType Directory -Force $dst_parent | Out-Null }}; "
            f"Copy-Item -Recurse -Force $src $dst"
        )

        print(f"[REMOTE MOVE] {src} -> {dst}")
        logging.info(f"[REMOTE MOVE] {src} -> {dst}")
        stdin, stdout, stderr = client.exec_command(
            f'{ps_exe} -NoProfile -Command "{cmd}"'
        )

        exit_code = stdout.channel.recv_exit_status()
        err = stderr.read().decode()

        if exit_code != 0:
            logging.error(f"[REMOTE MOVE FAILED]\n{err}")
            raise RuntimeError(f"[REMOTE MOVE FAILED]\n{err}")

        logging.info("[REMOTE MOVE] Completed")
        print("[REMOTE MOVE] Completed")
        return

    # =============================
    # LOCAL 
    # =============================
    path = Path(step_config["source"])
    src = path if path.is_absolute() else EXE_DIR / path

    if not src.exists():
        logging.info(f"[MOVE] Source not found, skipping: {src}")
        print(f"[MOVE] Source not found, skipping: {src}")
        return

    if dst.exists():
        logging.info(f"[MOVE] Destination exists, skipping move: {dst}")
        print(f"[MOVE] Destination exists, skipping move: {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    logging.info(f"[MOVE] Moved {src} -> {dst}")
    print(f"[MOVE] Moved {src} -> {dst}")

def handle_update_xml_attr(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    """
    Update a single XML attribute in a file.
    Expected keys in cfg:
      - file_path : relative path to the XML file
      - attribute : XML attribute name to update
      - new_value : new value for the attribute
    """
    p = Path(step_config["file_path"])
    path = p if p.is_absolute() else EXE_DIR / p
    attr = step_config["attribute"]
    new_value = step_config["new_value"]

    if not path.exists():
        logging.error(f"XML file not found: {path}")
        raise FileNotFoundError(f"XML file not found: {path}")

    # Read file
    text = path.read_text(encoding="utf-8")

    # Replace the attribute value
    text_new = re.sub(rf'{attr}="[^"]*"', f'{attr}="{new_value}"', text)

    # Save file
    path.write_text(text_new, encoding="utf-8")
    logging.info(f"[XML] Updated {attr} in {path}")
    print(f"[XML] Updated {attr} in {path}")

def handle_json_update(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    file_path = os.path.normpath(step_config["file"].strip())
    logging.info(f"JSON Update: remote={client is not None}, path={file_path}")

    full_config = load_config()
    machines = full_config.get("machines", [])
    
    master = next(
        (m for m in machines if m.get("role") in ["MASTER", "HMI"]),
        None
    )

    parent_role = machine.get("parent_role")
    parent = next((m for m in machines if m.get("role") == parent_role), None)
    CURRENT_ROLE = machine.get("role")
    tokens = {
        "SELF_IP": machine.get("ip"),
        "MASTER_IP":  master.get("ip"),
        "SELF_DB": machine.get("dbname"),
        "MASTER_DB":  master.get("dbname"),
        "PARENT_IP": parent.get("ip") if parent else None
    }
    if client:
        sftp = client.open_sftp()

        try:
            sftp.stat(file_path)  # Check remote file exists
        except IOError:
            logging.error(f"Remote JSON file not found: {file_path}")
            raise RuntimeError(f"Remote JSON file not found: {file_path}")

        with sftp.open(file_path, "r") as f:
            data = json.load(f)

    else:
        if not os.path.exists(file_path):
            logging.error(f"JSON file not found: {file_path}")
            raise RuntimeError(f"JSON file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    for path, value in step_config.get("updates", {}).items():

        if isinstance(value, str):
            for name, token_value in tokens.items():
                placeholder = f"{{{{{name}}}}}"

                if placeholder in value:
                    if token_value:
                        value = value.replace(placeholder, str(token_value))
                    else:
                        logging.warning(
                            f"{name} is empty while executing role {CURRENT_ROLE}. "
                            f"Leaving placeholder unchanged."
                        )
        
        is_append = path.endswith("[]")
        clean_path = path[:-2] if is_append else path

        keys = clean_path.split(".")
        ref = data
        for k in keys[:-1]:
            ref = ref.setdefault(k, {})

        last = keys[-1]

        if is_append:
            ref.setdefault(last, [])
            if value not in ref[last]:
                ref[last].append(value)
        else:
            ref[last] = value

    # ---------------------------
    # REBUILD SECTIONS
    # ---------------------------
    for rebuild in step_config.get("rebuild", []):
        target_keys = rebuild["target"].split(".")
        include_roles = rebuild["include_roles"]

        # navigate to parent
        ref = data
        for k in target_keys[:-1]:
            ref = ref.setdefault(k, {})

        section_name = target_keys[-1]

        # clear section
        ref[section_name] = {}
        CONFIG = load_config()
        for machine in CONFIG["machines"]:
            role = machine["role"]
            if not any(role.startswith(r) for r in include_roles):
                continue

            raw_key = machine[rebuild["key_from"]]
            key = raw_key.upper() if rebuild.get("key_transform") == "UPPER" else raw_key

            entry = {}
            for out_key, rule in rebuild["fields"].items():
                if "value" in rule:
                    entry[out_key] = rule["value"]
                else:
                    val = machine[rule["from"]]
                    if rule.get("transform") == "UPPER":
                        val = val.upper()
                    entry[out_key] = val

            ref[section_name][key] = entry

    if client:
        with sftp.open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        sftp.close()
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

def handle_appconfig_update(client, step_config, password, machine):

    full_config = load_config()
    machines = full_config.get("machines", [])

    CURRENT_ROLE = machine.get("role")
    target_roles = machine.get("config", []).copy()
   
    parent_role = machine.get("parent_role")
    if parent_role:
        target_roles.append(parent_role)
    file_path = step_config["file"]
    if not os.path.exists(file_path):
        logging.error(f"JSON file not found: {file_path}")
        raise RuntimeError(f"JSON file not found: {file_path}")

    if client:
        sftp = client.open_sftp()
        with sftp.open(file_path, "r") as f:
            data = json.load(f)
    else:
        if not os.path.exists(file_path):
            logging.error(f"JSON file not found: {file_path}")
            raise RuntimeError(f"JSON file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)


    # rebuild RedisServerProfiles
    redis_profiles = {}

    for role in target_roles:

        target_machine = next(
            (m for m in machines if m.get("role") == role), None
        )

        if not target_machine:
            continue

        machine_role = target_machine.get("role")
        ip = target_machine.get("ip")

        if not ip:
            logging.error(f"Invalid machine entry for role {role}")
            raise RuntimeError(f"Invalid machine entry for role {role}")

        if machine_role.startswith("SL2"):
            num = machine_role.split("-")[1]
            key = f"PPCCM{num}Redis"
        elif machine_role.startswith("SL1"):
            num = machine_role.split("-")[1]
            key = f"PPC{num}Redis"
        elif machine_role.startswith("MASTER"):
            key = f"PPCMMRedis"
        else:
            continue

        fields = step_config["fields"]
        entry = {}
        for k, v in fields.items():
            if isinstance(v, str) and "{{ip}}" in v:
                entry[k] = v.replace("{{ip}}", ip)
            else:
                entry[k] = v

        redis_profiles[key] = entry

    data["RedisServerProfiles"] = redis_profiles

    if client:
        with sftp.open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        sftp.close()
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    logging.info(f"[APPCONFIG UPDATED] {file_path} for role {CURRENT_ROLE}")
    print(f"[APPCONFIG UPDATED] {file_path} for role {CURRENT_ROLE}")

def handle_update_properties(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    base_dir = Path(step_config["base_dir"])
    keys = step_config.get("keys", [])
    CONFIG = load_config()
    db_list = CONFIG.get("dbstring", [])

    if not keys:
        logging.info("[PROPS] No keys provided")
        print("[PROPS] No keys provided")
        return

    if not db_list:
        logging.info("[PROPS] No dbstring defined")
        print("[PROPS] No dbstring defined")
        return

    db_value = ",".join(db_list)

    for service_dir in base_dir.iterdir():
        if not service_dir.is_dir():
            continue

        config_dir = service_dir / "config"
        conf_dir = service_dir / "conf"

        if config_dir.is_dir():
            dir = config_dir
        elif conf_dir.is_dir():
            dir = conf_dir
        else:
            continue

        for prop_file in dir.glob("*.properties"):
            lines = prop_file.read_text(encoding="utf-8").splitlines()
            updated = False
            new_lines = []

            for line in lines:
                replaced = False
                for key in keys:
                    if line.startswith(f"{key}="):
                        new_lines.append(f"{key}={db_value}")
                        updated = True
                        replaced = True
                        break

                if not replaced:
                    new_lines.append(line)

            if updated:
                prop_file.write_text("\n".join(new_lines), encoding="utf-8")
                logging.info(f"[PROPS UPDATED] {prop_file}")
                print(f"[PROPS UPDATED] {prop_file}")

def handle_append_config(client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]):
    base_var = step_config["base_var"]
    rel_path = step_config["relative_path"]
    values = step_config["updates"]
    kv_style = step_config.get("kv_style", "preserve")  # default = safe

    base_path = os.environ.get(base_var)
    if not base_path:
        logging.error(f"{base_var} not set")
        raise RuntimeError(f"{base_var} not set")

    config_path = Path(base_path) / rel_path
    if not config_path.exists():
        logging.error(config_path)
        raise FileNotFoundError(config_path)

    lines = config_path.read_text(encoding="utf-8").splitlines()
    updated_lines = []

    for line in lines:
        replaced = False

        for key, value in values.items():
            pattern = rf'^(\s*#?\s*{re.escape(key)}\s*)(=|\s+)?(.*)$'
            m = re.match(pattern, line)

            if m:
                # Decide separator
                if kv_style == "equals":
                    sep = " = "
                elif kv_style == "space":
                    sep = " "
                else:  # preserve
                    sep = f" {m.group(2).strip()} " if m.group(2) else " "

                updated_lines.append(f"{key}{sep}{value}")
                replaced = True
                break

        if not replaced:
            updated_lines.append(line)

    config_path.write_text("\n".join(updated_lines), encoding="utf-8")

def dispatch_step(step_name: str, client: Optional[paramiko.SSHClient], step_config: Dict[str, Any], password: str, machine : Optional[Dict[str, Any]]) -> None:
    """Routes to the correct function based on step name."""
    role = machine.get("role", "UNKNOWN")
    ip = machine.get("ip", "LOCAL")

    functions = {
        "copy_folder": handle_copy_folder,
        "env_setup": handle_env_setup,
        "extract": handle_extract,
        "add_config": handle_add_config,
        "modify_files": handle_modify_files,
        "modify_json": handle_modify_json,
        "create_db": handle_create_db,
        "zip_extract": handle_zip_extract,
        "run_cmd": run_cmd,
        "env_change": handle_env_change,
        "remote_copy": handle_remote_copy,
        "append_config": handle_append_config,
        "move_folder": handle_move_folder,
        "update_xml_attr": handle_update_xml_attr,
        "json_update": handle_json_update,
        "appconfig_update": handle_appconfig_update,
        "update_properties": handle_update_properties,
    }

    if step_name in functions:
        logging.info(f"STEP:{role}:{step_name}")
        print(f"STEP:{step_name}")
        functions[step_name](client, step_config, password, machine)
    else:
        logging.info(f"  Warning: Unknown step '{step_name}'. Skipping.")
        print(f"  Warning: Unknown step '{step_name}'. Skipping.")

def process_machine(machine: Dict[str, Any], full_config: Dict[str, Any]) -> None:
    """Process installation for one machine."""
    role = machine.get("role", "SLAVE")
    ip = machine.get("ip")
    username = machine.get("username")
    password = machine.get("password")
    bundles = machine.get("bundles", [])

    client = None
    is_local = role in ("MASTER", "HMI")

    if is_local:
        logging.info(f"\n[MASTER/LOCAL] Processing on local machine (IP in config: {ip})...")
        print(f"\n[MASTER/LOCAL] Processing on local machine (IP in config: {ip})...")
    else:
        if not is_host_reachable(ip):
            logging.info(f"Error: Host {ip} is unreachable (ping + SSH failed).")
            print(f"Error: Host {ip} is unreachable (ping + SSH failed).")
            return

        print(f"\n[{ip}] Connecting via SSH...")
        logging.info(f"\n[{ip}] Connecting via SSH...")
        client = ssh_connect(ip, username, password)

    try:
        software_map = full_config.get("software", {})
        for bundle in bundles:
            current_bundle = bundle
            if bundle not in software_map:
                logging.info(f" Bundle '{bundle}' not found. Skipping.")
                print(f" Bundle '{bundle}' not found. Skipping.")
                continue

            print(f"[{'LOCAL' if is_local else ip}] Processing bundle: {bundle}")
            logging.info(f"[{'LOCAL' if is_local else ip}] Processing bundle: {bundle}")
            if CURRENT_OS == "windows":
                config = software_map[bundle].get("windows", {})
            elif CURRENT_OS == "linux":
                config = software_map[bundle].get("linux", {})
            else:
                config = {}
            steps_list = config.get("steps", [])

            for step_data in steps_list:
                step_name = step_data.get("step")
                if step_name:
                    status_progress = {
                        "python":"Installing Python",
                        "jdk": "Installing JDK",
                        "SPARK_PPC": "Setting up SPARK_PPC folder",
                        "redis": "installing redis",
                        "dos2unix": "Preparing Scripts",
                        "kafka": "configuring Kafka",
                        "zookeeper": "configuring Zookeeper",
                        "tomcat": "Configuring Tomcat",
                        "postgresql": "Setting up Postgresql",
                        "liquibase": "Applying Database Migrations",
                        "HMI_config": "HMI Configuration of SPARK_PPC",
                        "historian_setup_hmi":"Configuring Historian on the HMI Machine",
                        "historian_setup":"Configuring Historian"
                    }

                    status_text = status_progress.get(current_bundle, f"Processing {current_bundle}")
                    print(f"###STATUS### {role} → {status_text}", flush=True)
                    
                    
                    dispatch_step(step_name, client, step_data, password, machine)
                    
                else:
                    logging.info(f"  Skipping invalid step: {step_data}")
                    print(f"  Skipping invalid step: {step_data}")
            print("###PROGRESS_UPDATE###", flush=True)

        
    finally:
        if client:
            client.close()
            print(f"[{ip}] Disconnected.")
            logging.info(f"[{ip}] Disconnected.")
        else:
            logging.info("[MASTER/LOCAL] Processing complete.")
            print("[MASTER/LOCAL] Processing complete.")

def main():
    """
    Entry point for the software installer.
    Iterates through all machines defined in sw_config.json and processes them.
    """
    print("[INSTALLER] Starting installation...")

    try:
        full_config = load_config()
    except Exception as e:
        logging.info(f"[ERROR] Failed to load configuration: {e}")
        print(f"[ERROR] Failed to load configuration: {e}")
        traceback.print_exc()
        return

    machines = full_config.get("machines", [])
    if not machines:
        print("[WARN] No machines defined in configuration.")
        return

    for machine in machines:
        role = machine.get("role", "UNKNOWN")
        

        ip = machine.get("ip", "localhost")
        logging.info(f"[INSTALLER] Processing machine: {role} ({ip})")
        print(f"\n[INSTALLER] Processing machine: {role} ({ip})")

        try:
            # pass full_config as the second argument
            process_machine(machine, full_config)
        except Exception as e:
            logging.exception(f"[ERROR] Failed processing {role} ({ip})")
            print(f"[ERROR] Failed processing {role} ({ip}): {e}")
            traceback.print_exc()

    print("\n[INSTALLER] Installation completed for all machines.")


if __name__ == "__main__":
    main()
