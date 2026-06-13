import platform
import json
import os
import logging
import io
import sys
import socket
import re
import ipaddress
from contextlib import redirect_stdout, redirect_stderr
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QHBoxLayout,QVBoxLayout, QFrame, QStackedWidget, QTextEdit, QScrollArea, QCheckBox, QMessageBox, QProgressBar,QLineEdit, QSizePolicy
from PyQt5.QtGui import QPixmap, QRegExpValidator, QIcon
from PyQt5.QtCore import Qt, QTimer, QRegExp, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication
import sys
import warnings

os.environ["NO_AT_BRIDGE"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)
class BackgroundLabel(QLabel):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.pixmap_original = QPixmap(image_path)

    def resizeEvent(self, event):
        if not self.pixmap_original.isNull():
            scaled = self.pixmap_original.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled)
#NO DPI scaling
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_Use96Dpi, True)

os.environ["QT_FONT_DPI"] = "96"
app = QApplication(sys.argv) 
app.setStyle("Fusion")
def fix_button(btn):
    btn.setMinimumHeight(32)
    btn.setMinimumWidth(90)
    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    font = btn.font()
    font.setPointSize(9)
    btn.setFont(font)
Product= "PPC"

LINUX_HMI_BUNDLES = ["jdk", "openssh", "python", "dos2unix", "SPARK_PPC", "redis", "kafka", "zookeeper", "tomcat", "postgresql", "liquibase", "HMI_config"]
LINUX_HISTORIAN_MASTER_BUNDLES = ["jdk", "openssh", "python", "dos2unix", "SPARK_PPC", "redis", "kafka", "zookeeper", "tomcat", "postgresql", "liquibase", "HMI_config", "historian_setup_hmi"]
LINUX_CORE_RTE_BUNDLES = ["jdk", "redis", "python", "core_config"]
HISTORIAN_LINUX_BUNDLES = ["jdk", "postgresql", "liquibase", "historian_setup"]

WINDOWS_HMI_BUNDLES = ["python","jdk","redis","kafka","zookeeper","tomcat","liquibase","postgresql","openssh","SPARK_PPC","HMI_config"]
WINDOWS_CORE_RTE_BUNDLES = ["python","jdk","redis","kafka","zookeeper","tomcat","core_config"]
HISTORIAN_WINDOWS_BUNDLES = ["jdk", "liquibase", "postgresql", "historian_setup"]
WINDOWS_HISTORIAN_MASTER_BUNDLES = ["python","jdk","redis","kafka","zookeeper","tomcat","liquibase","postgresql","openssh","SPARK_PPC","HMI_config", "historian_setup_hmi"]



if getattr(sys, 'frozen', False):
    ROOT_DIR = sys._MEIPASS
else:
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
current_os = platform.system()

LOG_DIR = os.path.join(ROOT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "nginstaller.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%b %d %H:%M:%S",
    filemode='a'
)
def load_config():
    config_path = os.path.join(ROOT_DIR, "installer_runtime", "config", "sw_config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
        return {}
config = load_config()
PRODUCT_NAME = config.get("product", {}).get("name", "Product")
db_name = "spark_ppc"
PRODUCT_VERSION = config.get("product", {}).get("version", "UNKNOWN")
def log_message(msg):
    logging.info(msg)
log_message(f"{Product} installer started")

def load_stylesheet(app):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.join(sys._MEIPASS, "installer_runtime", "UI")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
 
    qss_path = os.path.join(base_dir, "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            qss = f.read()
        tick_path = os.path.join(base_dir, "images", "tick.png")
        tick_path = tick_path.replace("\\", "/")
        qss = qss.replace("images/tick.png", tick_path)
        app.setStyleSheet(qss)

class WelcomePage(QWidget):
    """Page 1 – Welcome"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()  
    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        heading = QLabel(f"Welcome to {Product}_{PRODUCT_VERSION} Setup Wizard")
        heading.setObjectName("welcomeHeading")
        heading.setWordWrap(True)  
        heading.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) 
        desc = QLabel(
            f"Setup will guide you through the installation of {Product}.\n\n"          
            "Before you begin:\n\n"
            "Ensure SSH is installed and running on Core and Historian machines ,\n"
            "If not, follow the steps below:\n"
            "   - Linux   : Copy\n"
            "       /prerequisites/remote/remote_setup.sh\n\n"
            "   - Windows : Copy\n"
            "       /prerequisites/remote/remote_setup.bat\n\n"         
            "Click Next to continue."
        )
        desc.setWordWrap(True)
        desc.setObjectName("welcomeDescription")
        layout.addWidget(heading)
        layout.addWidget(desc)
        layout.addStretch()
        self.setLayout(layout)

class LicensePage(QWidget):
    """License Agreement"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
   
    def initUI(self):
        self.setObjectName("licensePage")

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)

        heading = QLabel("License Agreement")
        license_text = QTextEdit()
        license_text.setReadOnly(True)

        for widget, name in [(heading, "licenseHeading"), (license_text, "licenseText")]:
            widget.setObjectName(name)

        json_path = os.path.join(ROOT_DIR,"installer_runtime", "config", "sw_config.json")
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                data = json.load(f)
                license_content = data.get("license_content", "")
            license_text.setPlainText(license_content)
        else:
            license_text.setPlainText("License file not found.")

        layout.addWidget(heading)
        layout.addWidget(license_text)
        self.setLayout(layout)
   
# ---------------- MACHINE CONFIG SCREEN ----------------
class MachineConfigScreen(QWidget):
    """
    MachineConfigScreen 
    """
    def __init__(self, parent=None, stacked_widget=None, prev_screen=None, next_screen=None, log_func=None):
        super().__init__(parent)
        self.setObjectName("MachineConfigScreen")  
        self.all_credential_fields = []
        self.stacked_widget = stacked_widget
        self.prev_screen = prev_screen
        self.next_screen = next_screen
        self.log_func = log_func or (lambda *a, **k: None)
        self.historians = []
        self.master_ip_edit = None
        self._last_structured = None
        self.initUI()  
       
    def initUI(self):
        main = QVBoxLayout()  
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(10)
        title_layout = QHBoxLayout()
        title = QLabel("Machine Configuration")
        title.setObjectName("machineConfigTitle")

        # keep center alignment visually
        title.setAlignment(Qt.AlignCenter)

        # Historian label + button
        historian_label = QLabel("Historian")
        self.add_historian_btn = QPushButton("+")
        self.add_historian_btn.setFixedSize(24, 18)  
        self.add_historian_btn.setStyleSheet(
            "background-color: #27427a; color: white; border:1px solid #666; font-size:17px;"
        )
        self.add_historian_btn.setObjectName("addButton")
        self.add_historian_btn.clicked.connect(self.add_historian)

        # layout arrangement
        title_layout.addStretch()           # left spacing
        title_layout.addWidget(title)       # center title
        title_layout.addStretch()           # push historian to right
        title_layout.addWidget(historian_label)
        title_layout.addWidget(self.add_historian_btn)

        main.addLayout(title_layout)
       
        
        master_frame = QFrame()
        h = QHBoxLayout(master_frame)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        master_label = QLabel("HMI_Machine:")
        master_label.setFixedWidth(125)
        h.addWidget(master_label)
        self.master_ip_edit = QLineEdit()
       
        self.master_ip_edit.setObjectName("masterIpField")
        self.master_ip_edit.setInputMask("000.000.000.000; ")
        self.master_ip_edit.setFixedWidth(295)

        h.addWidget(self.master_ip_edit, stretch=1)                   
        
        main.addWidget(master_frame)
        self.master_cred_widget = QWidget()
        master_cred_layout = QHBoxLayout(self.master_cred_widget)
        master_cred_layout.setContentsMargins(125, 0, 0, 0)
        master_cred_layout.setSpacing(8)
        master_user_lbl = QLabel("User:")
        
        self.master_user = QLineEdit()
        self.master_user.setObjectName("credentialField")
        self.master_user.setPlaceholderText("username")
        
        master_user_lbl.setMinimumWidth(55)
        master_user_lbl.setMaximumWidth(70)

        self.master_user.setFixedHeight(25)
       
        master_pass_lbl = QLabel("Password:")

        master_pass_lbl.setFixedWidth(75)
        self.master_pass = QLineEdit()
        self.master_pass.setEchoMode(QLineEdit.Password)
        self.master_pass.setPlaceholderText("password")
        self.master_pass.setFixedWidth(80)
        self.master_pass.setFixedHeight(25)
        self.master_pass.setObjectName("credentialField")
       
        user_container = QHBoxLayout()
        user_container.setSpacing(2)  

        master_user_lbl = QLabel("User:")
        master_user_lbl.setFixedWidth(45)  # tight fit

        self.master_user = QLineEdit()
        self.master_user.setPlaceholderText("username")
        self.master_user.setFixedHeight(25)
        self.master_user.setMinimumWidth(80)

        user_container.addWidget(master_user_lbl)
        user_container.addWidget(self.master_user)

        master_cred_layout.addLayout(user_container)
        master_cred_layout.addSpacing(20)
        master_cred_layout.addWidget(master_pass_lbl)
        master_cred_layout.addWidget(self.master_pass)
        master_cred_layout.addStretch()
        main.addWidget(self.master_cred_widget)
        
        # -------- CORE RTE MACHINE --------
        core_frame = QFrame()
        core_layout = QHBoxLayout(core_frame)
        core_layout.setContentsMargins(0, 0, 0, 0)
        core_layout.setSpacing(2)

        core_label = QLabel("Core_RTE_Machine:")
        core_label.setFixedWidth(125)
        core_layout.addWidget(core_label)

        self.core_ip_edit = QLineEdit()
        self.core_ip_edit.setObjectName("ipField")
        self.core_ip_edit.setInputMask("000.000.000.000; ")
        self.core_ip_edit.setFixedWidth(295)

        core_layout.addWidget(self.core_ip_edit, stretch=1)

        main.addWidget(core_frame)

        # -------- CORE RTE CREDENTIALS --------
        self.core_cred_widget = QWidget()
        core_cred_layout = QHBoxLayout(self.core_cred_widget)
        core_cred_layout.setContentsMargins(125, 0, 0, 0)
        core_cred_layout.setSpacing(8)

        core_user_lbl = QLabel("User:")
        core_user_lbl.setFixedWidth(80)
        self.core_user = QLineEdit()
        self.core_user.setPlaceholderText("username")
        self.core_user.setFixedWidth(80)
        self.core_user.setFixedHeight(25)
        self.core_user.setObjectName("credentialField")

        core_pass_lbl = QLabel("Password:")
        core_pass_lbl.setFixedWidth(75)
        self.core_pass = QLineEdit()
        self.core_pass.setEchoMode(QLineEdit.Password)
        self.core_pass.setPlaceholderText("password")
        self.core_pass.setFixedWidth(80)
        self.core_pass.setFixedHeight(25)
        self.core_pass.setObjectName("credentialField")

        
        user_container = QHBoxLayout()
        user_container.setSpacing(2)  

        core_user_lbl = QLabel("User:")
        core_user_lbl.setFixedWidth(45)  # tight fit

        self.core_user = QLineEdit()
        self.core_user.setPlaceholderText("username")
        self.core_user.setFixedHeight(25)
        self.core_user.setMinimumWidth(80)

        user_container.addWidget(core_user_lbl)
        user_container.addWidget(self.core_user)

        core_cred_layout.addLayout(user_container)

        core_cred_layout.addSpacing(20)
        core_cred_layout.addWidget(core_pass_lbl)
        core_cred_layout.addWidget(self.core_pass)
        core_cred_layout.addStretch()

        main.addWidget(self.core_cred_widget)

        # Area that will contain CM blocks (vertical)
        
         
        # -------- CONTAINER FOR HISTORIANS --------
        self.cm_container = QVBoxLayout()
        self.cm_container.setSpacing(10)

        cm_container_widget = QWidget()
        cm_container_widget.setLayout(self.cm_container)
        self.cm_container.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("machineConfigScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(cm_container_widget)
        scroll.setFixedHeight(140)

        main.addWidget(scroll)
        # ---------- Common credentials section ----------
        common_layout = QHBoxLayout()    
        common_layout.setSpacing(10)
        # Checkbox
        self.common_cred_chk = QCheckBox("Common User:")
        self.common_cred_chk.setObjectName("commonCredentialCheck")

        self.common_cred_chk.toggled.connect(self.toggle_common_credentials)
        common_layout.addWidget(self.common_cred_chk, 0, Qt.AlignVCenter)      
       
        # Common username
        self.common_user = QLineEdit()
        self.common_user.setPlaceholderText("username")
        self.common_user.setFixedWidth(87)
        self.common_user.setFixedHeight(25)
        self.common_user.setEnabled(False)
        self.common_user.setObjectName("credentialField")
       
        common_layout.addWidget(self.common_user, 0, Qt.AlignVCenter)
        # Password label
        common_layout.addWidget(QLabel("Password:"), 0, Qt.AlignVCenter)
        # Common password
        self.common_pass = QLineEdit()
        self.common_pass.setPlaceholderText("password")
        self.common_pass.setEchoMode(QLineEdit.Password)
        self.common_pass.setFixedWidth(90)
        self.common_pass.setFixedHeight(24)
        self.common_pass.setEnabled(False)
        self.common_pass.setObjectName("credentialField")
       
        common_layout.addWidget(self.common_pass, 0, Qt.AlignVCenter)
        common_layout.addStretch()    
        main.addLayout(common_layout)
        self.common_cred_chk.setChecked(True)
        self.toggle_common_credentials(True)


        self.setLayout(main)
    def get_local_ips(self):
        ips = ['127.0.0.1']
        try:
            hostname = socket.gethostname()
            _, _, ipaddrlist = socket.gethostbyname_ex(hostname)
            ips.extend(ipaddrlist)
        except Exception:
            pass
        try:
            # Connect to a public IP to find the default route local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        return list(set(ips))
    def toggle_common_credentials(self, checked):
        self.common_user.setEnabled(checked)
        self.common_pass.setEnabled(checked)
        self.master_cred_widget.setVisible(not checked)
        self.core_cred_widget.setVisible(not checked)        
        for h in self.historians:
                h["cred_widget"].setVisible(not checked)


       

    
    def validate_ip(self, ip_text):
        ip = ip_text.replace(" ", "")
        if not ip or ip.count(".") != 3:
            return False, "IP address must be in xxx.xxx.xxx.xxx format"
        parts = ip.split(".")
        if len(parts) != 4:
            return False, "IP address must contain 4 numbers"
        for part in parts:
            if part == "":
                return False, "Each IP block must be filled"
            if not part.isdigit():
                return False, "IP address must contain only numbers"
            value = int(part)
            if value < 0 or value > 255:
                return False, "IP address must fall within the range 0 to 255"
        return True, ""
   
    def check_master_ip(self):
        ip = self.master_ip_edit.text()
        valid, message = self.validate_ip(ip)
        if not valid:
            QMessageBox.warning(
                self,
                "Invalid IP Address",
                message
            )
            self.master_ip_edit.setFocus()
            return False
        return True            

    def create_ip_validator(self):
        ip_regex = QRegExp(r"^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
                          r"(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$")
        return QRegExpValidator(ip_regex, self)
    def add_historian(self):
        if len(self.historians) >= 2:
            QMessageBox.warning(
                self,
                "Configuration Limit Reached",
                "Historian node count must not exceed 2."
            )
            return
        index = len(self.historians) + 1

        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)

        # --- Top Row ---
        row = QHBoxLayout()

        label = QLabel(f"Historian-{index}:")

        label.setFixedWidth(100)

        ip_edit = QLineEdit()
        ip_edit.setInputMask("000.000.000.000; ")
        ip_edit.setFixedWidth(200)
        ip_edit.setObjectName("ipField")
        ip_edit.setStyleSheet("background-color: #1D2951; color:white;")

        remove_btn = QPushButton("−")
        remove_btn.setFixedWidth(36)
        remove_btn.setStyleSheet("background-color: #27427a; color: white; border:1px solid #666")
        remove_btn.setObjectName("removeButton")

        row.addWidget(label)
        row.addWidget(ip_edit)
        row.addWidget(remove_btn)

        layout.addLayout(row)

        # --- Credentials ---
        user = QLineEdit()
        user.setStyleSheet("background-color: #1D2951; color:white;")
        user.setPlaceholderText("username")
        user.setFixedWidth(90)
        user.setFixedHeight(25)
        user.setObjectName("credentialField")

        password = QLineEdit()
        password.setStyleSheet("background-color: #1D2951; color:white;")
        password.setPlaceholderText("password")
        password.setEchoMode(QLineEdit.Password)
        password.setFixedWidth(90)
        password.setFixedHeight(25)
        password.setObjectName("credentialField")

        cred_layout = QHBoxLayout()
        cred_layout.setContentsMargins(100, 0, 0, 0)
        cred_layout.addWidget(QLabel("User:"))
        cred_layout.addWidget(user)
        cred_layout.addWidget(QLabel("Password:"))
        cred_layout.addWidget(password)

        cred_widget = QWidget()
        cred_widget.setLayout(cred_layout)
        if self.common_cred_chk.isChecked():
            cred_widget.setVisible(False)

        layout.addWidget(cred_widget)
        

        # --- Store ---
        hist_obj = {
            "frame": frame,
            "label": label,
            "ip": ip_edit,
            "user": user,
            "pass": password,
            "cred_widget": cred_widget
        }

        self.historians.append(hist_obj)
        # Always insert BEFORE the stretch → keeps historians at bottom
        self.cm_container.insertWidget(self.cm_container.count(), frame)

        # --- Remove logic ---
        def remove():
            self.historians.remove(hist_obj)
            self.cm_container.removeWidget(frame)
            frame.deleteLater()
            self.relabel_historians()

        remove_btn.clicked.connect(remove)

        self.relabel_historians()
    def relabel_historians(self):
        for i, h in enumerate(self.historians, start=1):
            h["label"].setText(f"Historian-{i}:")
    
    
    # ---------- Validation & logging ----------
    def validate_and_log(self):
        errors = []
        master_ip = self.master_ip_edit.text()
        valid, message = self.validate_ip(master_ip)

        if not valid:
            errors.append(f"HMI : {message}")
        else:
            # Change 1 Implementation: Check if hmi IP is the Base Machine IP
            clean_master_ip = master_ip.replace(" ", "")
            local_ips = self.get_local_ips()
            if clean_master_ip not in local_ips:
                errors.append(f"HMI : HMI machine IP must be base machine IP. (Detected Base IPs: {', '.join(local_ips)})")
            
        # Credential validation
        if self.common_cred_chk.isChecked():
            if not self.common_user.text().strip():
                errors.append("Common username is required")
            if not self.common_pass.text().strip():
                errors.append("Common password is required")
        else:
            if not self.master_user.text().strip():
                errors.append("HMI username is required")
            if not self.master_pass.text().strip():
                errors.append("HMI password is required")
        common_enabled = self.common_cred_chk.isChecked()
        common_user = self.common_user.text().strip()
        common_pass = self.common_pass.text().strip()
        #-------- CORE_RTE VALIDATION --------
        core_ip = self.core_ip_edit.text()

        valid, message = self.validate_ip(core_ip)

        if not valid:
            errors.append(f"Core_RTE : {message}")

        
        if not common_enabled:
            if not self.core_user.text().strip():
                errors.append("Core_RTE : Username is required")

            if not self.core_pass.text().strip():
                errors.append("Core_RTE : Password is required")


        structured = {
            "hmi": {
                "name": "HMI",
                "ip": master_ip,                               
                "username": self.master_user.text().strip(),
                "password": self.master_pass.text().strip()
            },            
            "core_rte": {
                    "name": "Core_RTE",
                    "ip": core_ip,                    
                    "username": common_user if common_enabled else self.core_user.text().strip(),
                    "password": common_pass if common_enabled else self.core_pass.text().strip()
                }

        }

        # -------- HISTORIANS --------
        structured["historians"] = []
        for i, h in enumerate(self.historians, start=1):
            ip = h["ip"].text()
            valid, message = self.validate_ip(ip)

            if not valid:
                errors.append(f"Historian-{i} : {message}")
            if not common_enabled:
                if not h["user"].text().strip():
                    errors.append(f"Historian-{i} : Username is required")
                if not h["pass"].text().strip():
                    errors.append(f"Historian-{i} : Password is required")
            

            structured["historians"].append({
                "name": f"Historian-{i}",
                "ip": ip,                
                "username": common_user if common_enabled else h["user"].text().strip(),
                "password": common_pass if common_enabled else h["pass"].text().strip()
            })
        
        #SHOW ALL ERRORS AT ONCE
        if errors:
            QMessageBox.critical(
                self,
                "Validation Errors",
                "Please fix the following:\n\n" + "\n".join(errors)
            )
            return False

        #Save only if ALL valid
        self._last_structured = structured

        log_message("Machine configuration summary:")
        log_message(f"HMI IP: {structured['hmi']['ip']}")
        log_message(f"Core_RTE IP: {structured['core_rte']['ip']}")

        
        
        self.save_machine_config_json(
            structured,
            common_username=self.common_user.text().strip(),
            common_password=self.common_pass.text().strip()
        )


        return True
   
    def clear_all(self):
        self.master_ip_edit.clear()
        self._last_structured = None
        

    def save_machine_config_json(self, structured_data, common_username=None, common_password=None):
        master_bundles = []
        
       
        if current_os == "Windows":
            # Check whether Historian IP is configured
            historian_present = False

            for hist in structured_data.get("historians", []):
                hist_ip = hist.get("ip", "").replace(" ", "").strip()

                if hist_ip:
                    historian_present = True
                    break

            # Select bundles based on historian availability
            if historian_present:
                master_bundles = WINDOWS_HISTORIAN_MASTER_BUNDLES
            else:
                master_bundles = WINDOWS_HMI_BUNDLES

            
            

        elif current_os == "Linux":
            historian_present = False

            for hist in structured_data.get("historians", []):
                hist_ip = hist.get("ip", "").replace(" ", "").strip()
                if hist_ip:
                    historian_present = True
                    break

            if historian_present:
                master_bundles = LINUX_HISTORIAN_MASTER_BUNDLES
            else:
                master_bundles = LINUX_HMI_BUNDLES

            
            
        else:
            raise OSError(f"Unsupported operating system: {current_os}")

        config_path = os.path.join(ROOT_DIR,"installer_runtime", "config", "sw_config.json")
        self.log_func("INFO", "save_machine_config_json RUNNING")

        machine_list_to_add = []
        master_db = []
        common_enabled = bool(common_username and common_password)

        if common_enabled:
            m_user = common_username
            m_pass = common_password
        else:
            m_user = structured_data["hmi"].get("username", self.master_user.text().strip())
            m_pass = structured_data["hmi"].get("password", self.master_pass.text().strip())

              
        
        config_list = []

        HMI_entry = {
            "role": "HMI",
            "ip": structured_data["hmi"]["ip"],
            "username": m_user,
            "password": m_pass,
            "bundles": master_bundles,
            "dbname": "ppc",
        }
        
        machine_list_to_add.append(HMI_entry)
        master_db.append("ppc")
        
        # -------- CORE RTE --------
        core_entry = {
            "role": "CORE_RTE",
            "ip": structured_data["core_rte"]["ip"],                
            "username": structured_data["core_rte"]["username"],
            "password": structured_data["core_rte"]["password"],      
            "bundles": (
                WINDOWS_CORE_RTE_BUNDLES
                if current_os == "Windows"
                else LINUX_CORE_RTE_BUNDLES
            )

        }

        machine_list_to_add.append(core_entry)

        # -------- HISTORIANS --------
        for idx, hist in enumerate(structured_data.get("historians", []), start=1):

            
            h_user = hist.get("username", "")
            h_pass = hist.get("password", "")


            hist_entry = {
                "role": f"HISTORIAN-{idx}",
                "parent_role": "MASTER",
                "ip": hist["ip"],
                "username": h_user,
                "password": h_pass,
                "bundles": (
                    HISTORIAN_WINDOWS_BUNDLES
                    if current_os == "Windows"
                    else HISTORIAN_LINUX_BUNDLES
                ),
                
                "dbname": f"ppch{idx}"
            }
            machine_list_to_add.append(hist_entry)
        sl2_count = 1
        sl1_global_count = 1  

        

        dbstring = master_db
        for m in machine_list_to_add:
            if m.get("role") == "MASTER":
                config_key = "config"
                m[config_key] = config_list
                break

        try:
            data = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = json.load(f)
            else:
                self.log_func("WARN", f"Config file not found at {config_path}. Creating new one.")

            data["machines"] = machine_list_to_add
            data["dbstring"] = dbstring

            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(data, f, indent=4)

            self.log_func("INFO", f"Machine config saved successfully at {config_path}")

        except Exception as e:
            self.log_func("ERROR", f"Error while saving machine config: {str(e)}")

           
    def get_user_inputs(self):
        master_ip = (self.master_ip_edit.text() or "").strip()
        structured = getattr(self, "_last_structured", None)
        if structured is None:   
            structured = {"hmi": {"name": "HMI", "ip": master_ip}}
            self._last_structured = structured
        return {
            "master_ip": structured["hmi"]["ip"],
            "structured": structured
        }
       
    def go_back(self):
        if self.stacked_widget and self.prev_screen is not None:
            self.stacked_widget.setCurrentIndex(self.prev_screen)  
                       
class PRODUCTInstallerWizard(QWidget):
    """Main Wizard Container"""
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(os.path.join(ROOT_DIR, "installer_runtime", "UI", "images", "nginstaller.ico")))
        self.setWindowTitle(f"{Product} Installer Setup")
        self.setFixedSize(700, 450)
        self.setObjectName("productInstallerWizard")

        self.loading_page = LoadingPage()
        self.log_func = self.loading_page.append_log
        self.current_page = 0
        self.initUI()
       
    def initUI(self):
        left_frame = QFrame()
        left_frame.setFixedSize(230, 450)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "images", "Product_background.png")
        image_label = BackgroundLabel(image_path)
        
        image_label.setFixedSize(230, 450)
        
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(image_label)
        left_frame.setLayout(left_layout)
        left_frame.setFixedSize(230, 450)
       
        self.pages = QStackedWidget()
        self.welcome_page = WelcomePage()
        self.license_page = LicensePage()
        self.machine_config = MachineConfigScreen(stacked_widget=self.pages, prev_screen=1, next_screen=3, log_func=self.log_func)
       
        self.pages.addWidget(self.welcome_page)
        self.pages.addWidget(self.license_page)
        self.pages.addWidget(self.machine_config)
        self.pages.addWidget(self.loading_page)
       
        self.back_btn = QPushButton("< Back")
        self.next_btn = QPushButton("Next >")
        self.cancel_btn = QPushButton("Cancel")
        fix_button(self.back_btn)
        fix_button(self.next_btn)
        fix_button(self.cancel_btn)

        fix_button(self.cancel_btn)
       
        self.back_btn.setObjectName("wizardButton")
        self.next_btn.setObjectName("wizardButton")
        self.cancel_btn.setObjectName("wizardButton")
        self.back_btn.setVisible(False)
        self.back_btn.clicked.connect(self.go_back)
        self.next_btn.clicked.connect(self.go_next)
        self.cancel_btn.clicked.connect(self.close)      
       
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.back_btn)
        button_layout.addWidget(self.next_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 10, 15, 15)
       
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.pages)
        right_layout.addLayout(button_layout)
       
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(left_frame)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

    def go_next(self):
        if self.current_page == 2:
            if not self.machine_config.validate_and_log():
                return
            if not self.check_all_ips_reachable():
                return
            if not self.check_ssh_available():
                return
            self.perform_install()
            return

        if self.current_page < self.pages.count() - 1:
            self.current_page += 1
            self.pages.setCurrentIndex(self.current_page)
            self.back_btn.setVisible(True)
            if self.current_page == 1:
                self.next_btn.setText("I Agree")
            elif self.current_page == 2:
                self.next_btn.setText("Install")
    def normalize_ip(self, ip):
        try:
            return str(ipaddress.ip_address(ip.replace(" ", "")))
        except:
            return ip.replace(" ", "")            
    def check_all_ips_reachable(self):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        if base_path not in sys.path:
            sys.path.insert(0, base_path)

        from installer_runtime.sw_install import is_host_reachable

        structured = self.machine_config._last_structured
        if not structured:
            return True
        
        unreachable_ips = []
        # Skip  reachability check because it is local machine
        local_ips = [
            self.normalize_ip(ip)
            for ip in self.machine_config.get_local_ips()
        ]

        HMI_ip = self.normalize_ip(structured["hmi"]["ip"])


        if HMI_ip not in local_ips:
            from installer_runtime.sw_install import is_host_reachable

            if not is_host_reachable(HMI_ip):
                unreachable_ips.append(f"HMI ({HMI_ip})")

        
        # -------- HISTORIANS --------
        for hist in structured.get("historians", []):
            if not is_host_reachable(hist["ip"]):
                unreachable_ips.append(f"{hist['name']} ({hist['ip']})")
        #  Popup
        if unreachable_ips:
            QMessageBox.critical(
                self,
                "Connection Failed",
                "Unable to reach the specified machines:\n\n"
                + "\n".join(unreachable_ips) +
                "\n\nPlease verify IP addresses and network connectivity"
            )
            return False
        return True
    
    def check_ssh_available(self):    
        structured = self.machine_config._last_structured
        if not structured:
            return True
        
        ssh_failed = []

        def is_ssh_open(ip):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)  # fast check
                result = sock.connect_ex((ip.strip(), 22))
                sock.close()
                return result == 0
            except Exception:
                return False
            
        #CHECK CORE_RTE
        core = structured.get("core_rte", {})
        core_ip = core.get("ip", "").strip()

        if core_ip and not is_ssh_open(core_ip):
            ssh_failed.append(f"Core_RTE ({core_ip})")

        
        # -------- HISTORIANS --------
        for hist in structured.get("historians", []):
            if not is_ssh_open(hist["ip"]):
                ssh_failed.append(f"{hist['name']} ({hist['ip']})")
        

        # -------- POPUP --------
        if ssh_failed:
            message = ""
            for machine in ssh_failed:
                message += f"SSH is not installed in {machine}.\n"
                message += "Please follow the steps in readme.txt to install SSH.\n\n"

            QMessageBox.critical(
                self,
                "SSH Not Installed",
                message.strip()
            )
            return False
        return True
    def go_back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.pages.setCurrentIndex(self.current_page)
            if self.current_page == 1:
                self.next_btn.setText("I Agree")
            elif self.current_page == 2:
                self.next_btn.setText("Install")
            else:
                self.next_btn.setText("Next >")
        if self.current_page == 0:
            self.back_btn.setVisible(False)

    def perform_install(self):
        inputs = self.machine_config.get_user_inputs()
        
        self.loading_page.machine_ip = inputs["master_ip"].replace(" ", "")
        self.loading_page.start()
        self.current_page += 1
        self.pages.setCurrentIndex(self.current_page)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.loading_page.cancel_action)
        self.cancel_btn.show()
        self.back_btn.hide()
        self.next_btn.hide()
        self.cancel_btn.hide()
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.show()

class StreamEmitter(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal()
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, log_func, mode="install"):
        super().__init__()
        self.log_func = log_func
        self._buffer = ""
        self.mode = mode

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            clean_line = line.strip()
            if clean_line:
                if clean_line.startswith("###PROGRESS_UPDATE###"):
                    self.progress_signal.emit()
                elif clean_line.startswith("###STATUS###"):
                    msg = clean_line.replace("###STATUS###", "").strip()
                    self.status_signal.emit(msg)
                else:
                    self.log_signal.emit(clean_line)

    def flush(self):
        if self._buffer.strip():
            self.log_signal.emit(self._buffer.strip())
        self._buffer = ""

    def run(self):
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

            if base_path not in sys.path:
                sys.path.insert(0, base_path)

            from installer_runtime import sw_install

            with redirect_stdout(self), redirect_stderr(self):
                if self.mode == "install":
                    sw_install.main()
                


            if self.mode == "install":
                self.finished_signal.emit(True, "Installation completed successfully.")
            
            

        except Exception as e:
            self.finished_signal.emit(False, str(e))

class LoadingPage(QWidget):
    """Screen 4 – Installation log viewer with user input and progress logs"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        
        self.install_type = ""
        self.installation_running = False
        self.total_steps = 0
        self.completed_steps = 0
        self.last_step = None
        self.error_occurred = False
        self.initUI()
       
    def initUI(self):
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(40, 40, 40, 40)
        outer_layout.setSpacing(15)      
       
        title = QLabel(f"Installing {Product} Components...")
        title.setObjectName("loadingTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        outer_layout.addWidget(title)
       
        self.progress = QProgressBar()
        self.progress.setFixedHeight(22)
        font = self.progress.font()
        font.setPointSize(10)   # force readable size
        self.progress.setFont(font)
        self.progress.setValue(0)
        self.progress.setObjectName("loadingProgressBar")
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        outer_layout.addWidget(self.progress)
        self.status_label = QLabel("Processing INstallation...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumHeight(30)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Fix font shrinking
        font = self.status_label.font()
        font.setPointSize(10)
        self.status_label.setFont(font)
        outer_layout.addWidget(self.status_label)
        log_frame = QFrame()
        log_frame.setStyleSheet("border: 1px solid #1D2951; background-color: black;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(0, 0, 0, 0)  
       
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_view.setObjectName("logViewer")
        log_layout.addWidget(self.log_view, stretch=1)
        outer_layout.addWidget(log_frame, stretch=1)
       
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)
        self.finish_button = QPushButton("Finish")
        self.cancel_button = QPushButton("Cancel")
       
        button_layout.addWidget(self.finish_button)
        button_layout.addSpacing(20)
        button_layout.addWidget(self.cancel_button)
        outer_layout.addLayout(button_layout)
        self.setLayout(outer_layout)
       
        self.finish_button.hide()
        self.cancel_button.hide()
       
        self.finish_button.clicked.connect(self.finish_action)
        self.finish_button.setObjectName("finishButton")
        self.cancel_button.clicked.connect(self.cancel_action)
        self.cancel_button.setObjectName("cancelButton")
    def is_historian_present(self):
        config_path = os.path.join(ROOT_DIR, "installer_runtime", "config", "sw_config.json")
        if not os.path.exists(config_path):
            return False

        with open(config_path, "r") as f:
            data = json.load(f)

        for m in data.get("machines", []):
            if "HISTORIAN" in m.get("role", ""):
                return True

        return False

    def handle_log(self, message):
        self.append_log("INFO", message)

    def installation_finished(self, success, message):
        if self.error_occurred:
            return
        
        if success:
            self.progress.setMinimum(0)
            self.progress.setMaximum(100)
            self.progress.setValue(100)
            # Show text
            self.progress.setFormat("Installation Completed")
            self.progress.setTextVisible(True)
            self.status_label.setWordWrap(True)
            ip = getattr(self, "machine_ip", "localhost")
            self.status_label.setText(
                f'Please paste the following link in your web browser:<br>'
                f'<a href="https://{ip}/#/login" style="color:#C0C0C0;">'
                f'https://{ip}/#/login</a>'
            )
            self.status_label.setTextFormat(Qt.RichText)
            self.status_label.setOpenExternalLinks(True)
            #  IMPORTANT
            self.progress.setProperty("completed", True)
            self.progress.style().unpolish(self.progress)
            self.progress.style().polish(self.progress)
            parent = self.window()
            if parent:
                parent.setWindowFlag(Qt.WindowCloseButtonHint, True)
                parent.show() 

            self.append_log("INFO", message)
            self.finish_button.show()
            self.cancel_button.show()
            self.finish_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
        else:
            self.error_occurred = True
            self.append_log("ERROR", message)
            QMessageBox.critical(self, "Installation Failed", message)
            self.cancel_button.show()
            self.cancel_button.setEnabled(True)

        self.installation_running = False
    def update_status(self, message):
        self.status_label.setText(message)
    def start(self):
        self.error_occurred = False
        self.log_view.clear()
        self.installation_running = True
        self.last_step = None
        
        #  Detect historian
        historian_present = self.is_historian_present()

        # Select correct bundle count
        if current_os == "Windows":
            if historian_present:
                master_count = len(WINDOWS_HISTORIAN_MASTER_BUNDLES)
                historian_bundle_count = len(HISTORIAN_WINDOWS_BUNDLES)
            else:
                master_count = len(WINDOWS_HMI_BUNDLES)
                historian_bundle_count = 0
        else:
            if historian_present:
                master_count = len(LINUX_HISTORIAN_MASTER_BUNDLES)
                historian_bundle_count = len(HISTORIAN_LINUX_BUNDLES)
            else:
                master_count = len(LINUX_HMI_BUNDLES)
                historian_bundle_count = 0

        # Count historian nodes from config
        config_path = os.path.join(ROOT_DIR, "installer_runtime", "config", "sw_config.json")
        historian_nodes = 0

        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
                for m in data.get("machines", []):
                    if "HISTORIAN" in m.get("role", ""):
                        historian_nodes += 1
        
        if current_os == "Windows":
            core_count = len(WINDOWS_CORE_RTE_BUNDLES)
        else:
            core_count = len(LINUX_CORE_RTE_BUNDLES)

        # FINAL total steps
        self.total_steps = (
            master_count
            + core_count
            + (historian_nodes * historian_bundle_count)
            
        )


        # 3. Progress Bar Reset
        self.progress.setMinimum(0)
        self.progress.setMaximum(self.total_steps)  # PyQt will auto % calculate 
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")

        self.finish_button.show()
        self.cancel_button.show()

        self.finish_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.thread = StreamEmitter(self.append_log)
        self.thread.status_signal.connect(self.update_status)
        self.thread.log_signal.connect(self.handle_log)
        self.thread.progress_signal.connect(self.increment_progress)
        self.thread.finished_signal.connect(self.installation_finished)
        self.thread.start() 
    def increment_progress(self):
        """Safely increments the progress bar when a step finishes"""
        self.completed_steps += 1
        # Edge case precaution
        if self.completed_steps <= self.total_steps:
            self.progress.setValue(self.completed_steps)
       
    def append_log(self, level, message):
        from datetime import datetime
        if self.error_occurred:
           return 
        timestamp = datetime.now().strftime("%b %d %H:%M:%S")
        if level == "ERROR":
            self.error_occurred = True
            #  FIRST: Stop thread immediately
            if hasattr(self, "thread") and self.thread.isRunning():
                self.thread.terminate()
                self.thread.wait()
             #  Block further UI updates
            self.installation_running = False
           # Update UI immediately
            self.status_label.setText("Installation Failed")
            self.progress.setFormat("Failed to install components")
            self.progress.setValue(0)


            QMessageBox.critical(self, "Installation Error", message)

            return # IMPORTANT: stop further log processing

        timestamp_color = "#3F704D"
        level_colors = {
            "INFO": "#9DC183",  
            "WARN": "#FFD700",  
            "ERROR": "#FF6347"  
        }
        level_color = level_colors.get(level, "#9DC183")
        text_color = "#FAFBF5"
       
        log_line = (
            f"<span style='color:{timestamp_color}'>{timestamp}</span> "
            f"<span style='color:{level_color}'>{level}:</span> "
            f"<span style='color:{text_color}'>{message}</span>"
        )
        self.log_view.append(log_line)
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )
       
    def finish_action(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Installation completed")
        msg.setText(f"{Product} installation completed successfully!")
        msg.setObjectName("finishMessageBox")

        msg.exec_()

        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.wait()
        QApplication.quit()       
    
    def on_rollback_finished(self, success, message):

        # If rollback succeeded AND historian exists → start revert_back
        if success and getattr(self, "historian_present", False):

            self.status_label.setText("Reverting Historian components ...")
            self.log_view.append("<b>Revert_back started ...</b>")

            # Start revert_back thread
            self.revert_thread = StreamEmitter(self.append_log, mode="revert")
            self.revert_thread.progress_signal.connect(self.increment_progress)
            self.revert_thread.status_signal.connect(self.update_status)
            self.revert_thread.finished_signal.connect(self.on_revert_finished)
            self.revert_thread.start()

            return  #  IMPORTANT → STOP normal flow

        #  Existing logic continues below
        msg = QMessageBox(self)


        if success:
            self.status_label.setText("Rollback Completed Successfully")
            self.progress.setValue(self.total_steps)
            self.finish_button.setEnabled(True)
            msg.setWindowTitle("Rollback Completed")
            msg.setText(
                "The system has been restored to its previous state."
            )
            msg.setIcon(QMessageBox.Information)

        else:
            self.status_label.setText("Rollback Failed")

            msg.setWindowTitle("Rollback Failed")
            msg.setText(
                "Failed to revert all changes.\n\n"
                f"Details:\n{message}"
            )
            msg.setIcon(QMessageBox.Critical)

            #  Better sizing (no fixed height → avoids text cut)
            msg.setMinimumWidth(420)

            #  Improve readability
            msg.setStyleSheet("""
                    QMessageBox {
                        min-width: 430px;
                    }
                    QLabel {
                        min-height: 60px;
                    }
                """)

    #  Enable proper word wrapping
            label = msg.findChild(QLabel)
            if label:
                label.setWordWrap(True)

    #  Adjust dynamically based on content
        msg.adjustSize()

        msg.exec_()
        QApplication.quit()
    def on_revert_finished(self, success, message):
        self.final_rollback_result(success, message)
    def final_rollback_result(self, success, message):
        msg = QMessageBox(self)

        if success:
            self.status_label.setText("Revert Completed Successfully")
            msg.setWindowTitle("Revert Completed")
            msg.setText("System fully restored (including Historian).")
            msg.setIcon(QMessageBox.Information)
        else:
            self.status_label.setText("Revert Failed")
            msg.setWindowTitle("Revert Failed")
            msg.setText(f"Error:\n{message}")
            msg.setIcon(QMessageBox.Critical)

        msg.exec_()
        QApplication.quit()
    def cancel_action(self):
        if not self.installation_running:
            if hasattr(self, "thread") and self.thread.isRunning():
                self.thread.terminate()
                self.thread.wait()
            QApplication.quit()
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Cancel Installation")
        msg.setText("")
        msg.setText("Confirm cancellation of the installation.")
        msg.setObjectName("cancelMessageBox")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec_() != QMessageBox.Yes:
            return
        # Stop running installation thread
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()

        
        # Stop thread if running
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()

        QApplication.quit()


       
def main(build_dir=None, third_party_dir=None):
    load_stylesheet(app)
    wizard = PRODUCTInstallerWizard()
    wizard.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
