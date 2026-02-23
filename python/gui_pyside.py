import sys
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QPushButton, QComboBox, QCheckBox, 
    QLineEdit, QFileDialog, QPlainTextEdit, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QFont, QTextCursor

import qdarktheme

# Try importing SimpleITK for erosion calculation
try:
    import SimpleITK as sitk
except ImportError:
    sitk = None


# Determine if running as a bundled PyInstaller EXE
import platform
IS_BUNDLED = getattr(sys, 'frozen', False)

if IS_BUNDLED:
    # 這是使用者放 EXE 的那個真實資料夾 (例如桌面)
    EXE_DIR = Path(sys.executable).parent
    # 我們在旁邊悄悄建一個後端資料夾
    BASE_DIR = EXE_DIR / "TotalSeg_Backend"
    
    # 這是 PyInstaller 肚子裡解壓縮出來的純淨原始檔案
    MEIPASS_DIR = Path(sys._MEIPASS)
    
    # 確保後端資料夾存在
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 應該要解壓縮的配方檔
    required_files = ["pyproject.toml", "uv.lock", "seg.py"]
    for f in required_files:
        src = MEIPASS_DIR / f
        dst = BASE_DIR / f
        # 只要肚子裡有，就覆蓋過去旁邊的資料夾 (達成無腦升級)
        if src.exists():
            shutil.copy2(src, dst)
else:
    # 這是你在 Mac/開發環境下跑的目錄
    BASE_DIR = Path(__file__).parent

class TotalSegApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Medical Image Segmentation (PySide6)")
        self.resize(800, 750)

        # Apply light theme by default
        qdarktheme.setup_theme("light")

        # Central Widget & Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # Header Area
        header_layout = QHBoxLayout()
        title_label = QLabel("Medical Image Segmentation Tool")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.main_layout.addLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # 1. Single Segmentation Tab
        self.tab_single = QWidget()
        self.setup_single_tab()
        self.tabs.addTab(self.tab_single, "Single Segmentation")

        # 2. Batch Segmentation Tab
        self.tab_batch = QWidget()
        self.setup_batch_tab()
        self.tabs.addTab(self.tab_batch, "Batch Segmentation")

        # 3. Compare Tab (Placeholder)
        self.tab_compare = QWidget()
        self.tabs.addTab(self.tab_compare, "Manual vs AI Compare")
        
        # Log Area (Global for all tabs)
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 10))
        self.log_area.setMinimumHeight(200)
        self.main_layout.addWidget(self.log_area)

        # QProcess for running background tasks safely
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(BASE_DIR))
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

        # State Variables
        self.spacing_xy = None
        
        # Batch Mode Variables
        self.is_batch_mode = False
        self.batch_queue = []
        self.current_batch_index = -1

    def setup_single_tab(self):
        layout = QVBoxLayout(self.tab_single)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Directories Group
        dir_group = QGroupBox("Directories")
        dir_layout = QFormLayout(dir_group)
        
        # DICOM Row
        dicom_layout = QHBoxLayout()
        self.dicom_btn = QPushButton("Select DICOM Folder")
        self.dicom_btn.clicked.connect(self.select_dicom)
        self.dicom_label = QLineEdit()
        self.dicom_label.setPlaceholderText("No folder selected")
        self.dicom_label.textChanged.connect(self.validate_inputs)
        dicom_layout.addWidget(self.dicom_btn)
        dicom_layout.addWidget(self.dicom_label)
        dir_layout.addRow(dicom_layout)

        # Output Row
        out_layout = QHBoxLayout()
        self.out_btn = QPushButton("Select Output Folder")
        self.out_btn.clicked.connect(self.select_output)
        self.out_label = QLineEdit()
        self.out_label.setPlaceholderText("No folder selected")
        self.out_label.textChanged.connect(self.validate_inputs)
        out_layout.addWidget(self.out_btn)
        out_layout.addWidget(self.out_label)
        dir_layout.addRow(out_layout)
        
        layout.addWidget(dir_group)

        # Configuration Group
        cfg_group = QGroupBox("Configuration")
        cfg_layout = QVBoxLayout(cfg_group)

        # Task Selection
        task_layout = QHBoxLayout()
        task_layout.addWidget(QLabel("Segmentation Task:"))
        self.task_combo = QComboBox()
        tasks = [
            "abdominal_muscles", "aortic_sinuses", "appendicular_bones", "body", 
            "brain_structures", "breasts", "coronary_arteries", "face", 
            "head_glands_cavities", "head_muscles", "headneck_bones_vessels", 
            "heartchambers_highres", "liver_segments", "lung_nodules", 
            "lung_vessels", "oculomotor_muscles", "pleural_pericard_effusion",
            "thigh_shoulder_muscles", "tissue_types", "ventricle_parts", 
            "vertebrae_body", "total"
        ]
        self.task_combo.addItems(tasks)
        self.task_combo.setCurrentText("abdominal_muscles")
        task_layout.addWidget(self.task_combo)
        task_layout.addStretch()
        cfg_layout.addLayout(task_layout)

        # Checkboxes
        self.chk_spine = QCheckBox("Spine segmentation (takes more time)")
        self.chk_spine.setChecked(True)
        self.chk_fast = QCheckBox("Fast mode (may reduce accuracy)")
        self.chk_draw = QCheckBox("Export PNG overlays")
        self.chk_draw.setChecked(True)
        
        cfg_layout.addWidget(self.chk_spine)
        cfg_layout.addWidget(self.chk_fast)
        cfg_layout.addWidget(self.chk_draw)

        # Erosion
        erosion_layout = QHBoxLayout()
        erosion_layout.addWidget(QLabel("Erosion iterations (HU):"))
        self.erosion_input = QLineEdit("7")
        self.erosion_input.setFixedWidth(50)
        self.erosion_input.textChanged.connect(self.calc_erosion)
        self.erosion_mm_label = QLabel("Approx erosion: N/A")
        self.erosion_mm_label.setStyleSheet("color: gray;")
        
        erosion_layout.addWidget(self.erosion_input)
        erosion_layout.addWidget(self.erosion_mm_label)
        erosion_layout.addStretch()
        cfg_layout.addLayout(erosion_layout)
        
        layout.addWidget(cfg_group)

        # Start Button Layout
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_start = QPushButton("Start Segmentation")
        self.btn_start.setMinimumSize(200, 45)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet("font-weight: bold;")
        self.btn_start.clicked.connect(self.start_process)
        btn_layout.addWidget(self.btn_start)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    def setup_batch_tab(self):
        layout = QVBoxLayout(self.tab_batch)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Config Panel (Top)
        config_layout = QHBoxLayout()
        
        # Directories Group
        dir_group = QGroupBox("Batch Directories")
        dir_layout = QFormLayout(dir_group)
        
        # Root DICOM Row
        dicom_layout = QHBoxLayout()
        self.batch_dicom_btn = QPushButton("Select Root DICOM Folder")
        self.batch_dicom_btn.clicked.connect(self.select_batch_dicom)
        self.batch_dicom_label = QLineEdit()
        self.batch_dicom_label.setPlaceholderText("Select folder containing multiple patients")
        self.batch_dicom_label.setReadOnly(True)
        dicom_layout.addWidget(self.batch_dicom_btn)
        dicom_layout.addWidget(self.batch_dicom_label)
        dir_layout.addRow(dicom_layout)

        # Output Root Row
        out_layout = QHBoxLayout()
        self.batch_out_btn = QPushButton("Select Output Root")
        self.batch_out_btn.clicked.connect(self.select_batch_output)
        self.batch_out_label = QLineEdit()
        self.batch_out_label.setPlaceholderText("Output folder for all results")
        out_layout.addWidget(self.batch_out_btn)
        out_layout.addWidget(self.batch_out_label)
        dir_layout.addRow(out_layout)
        
        config_layout.addWidget(dir_group)

        # Inherit settings visually (just labels referring to Single Tab settings for MVP)
        settings_group = QGroupBox("Shared Configuration")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.addWidget(QLabel("[!] Batch mode uses the Task, Spine, Fast,"))
        settings_layout.addWidget(QLabel("and Erosion settings from the 'Single' tab."))
        settings_layout.addStretch()
        config_layout.addWidget(settings_group)
        
        layout.addLayout(config_layout)

        # Queue List Area (Middle)
        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels(["Include", "Patient Folder Path", "Status"])
        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.batch_table)

        # Start Button Layout
        btn_layout = QHBoxLayout()
        self.batch_progress_label = QLabel("0 / 0 Completed")
        self.batch_progress_label.setStyleSheet("font-weight: bold; color: gray;")
        btn_layout.addWidget(self.batch_progress_label)
        btn_layout.addStretch()
        self.btn_batch_start = QPushButton("Start Batch Processing")
        self.btn_batch_start.setMinimumSize(200, 45)
        self.btn_batch_start.setEnabled(False)
        self.btn_batch_start.setStyleSheet("font-weight: bold;")
        self.btn_batch_start.clicked.connect(self.start_batch_process)
        btn_layout.addWidget(self.btn_batch_start)
        
        layout.addLayout(btn_layout)

    def select_dicom(self):
        folder = QFileDialog.getExistingDirectory(self, "Select DICOM Directory")
        if folder:
            self.dicom_label.setText(folder)
            parent_dir = str(Path(folder).parent)
            self.out_label.setText(parent_dir)
            
            # Extract spacing if SimpleITK is available
            if sitk:
                try:
                    reader = sitk.ImageSeriesReader()
                    files = reader.GetGDCMSeriesFileNames(folder)
                    if files:
                        img = sitk.ReadImage(files[0])
                        spacing = img.GetSpacing()
                        self.spacing_xy = (spacing[0], spacing[1])
                except Exception:
                    self.spacing_xy = None
            self.calc_erosion()

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.out_label.setText(folder)

    def select_batch_dicom(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Root DICOM Directory")
        if folder:
            self.batch_dicom_label.setText(folder)
            parent_dir = str(Path(folder).parent)
            self.batch_out_label.setText(parent_dir + "_batch_output")
            self.scan_batch_directory(folder)

    def select_batch_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Batch Output Directory")
        if folder:
            self.batch_out_label.setText(folder)
            
    def scan_batch_directory(self, root_path):
        self.batch_table.setRowCount(0)
        root = Path(root_path)
        valid_folders = []
        
        self.append_log(f"Scanning {root_path} for DICOM folders...\n")
        
        # Fast scan: looking for folders containing .dcm files
        for sub_dir in root.rglob("*"):
            if sub_dir.is_dir():
                # Check if it contains at least one .dcm file directly
                if any(sub_dir.glob("*.dcm")):
                    valid_folders.append(sub_dir)

        if not valid_folders:
            self.append_log("[WARNING] No DICOM folders found in the selected root.\n")
            self.btn_batch_start.setEnabled(False)
            return

        self.append_log(f"Found {len(valid_folders)} patient folders.\n")
        self.batch_table.setRowCount(len(valid_folders))
        
        for i, folder in enumerate(valid_folders):
            chk = QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(self.update_batch_start_button)
            
            # Center the checkbox
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            
            self.batch_table.setCellWidget(i, 0, chk_widget)
            
            # Store relative path for cleaner UI, but absolute path in data
            rel_path = str(folder.relative_to(root))
            path_item = QTableWidgetItem(rel_path)
            path_item.setData(Qt.UserRole, str(folder))
            self.batch_table.setItem(i, 1, path_item)
            
            status_item = QTableWidgetItem("Pending")
            self.batch_table.setItem(i, 2, status_item)
            
        self.update_batch_start_button()

    def update_batch_start_button(self):
        checked_count = 0
        for i in range(self.batch_table.rowCount()):
            chk_widget = self.batch_table.cellWidget(i, 0)
            chk = chk_widget.layout().itemAt(0).widget()
            if chk.isChecked():
                checked_count += 1
                
        if checked_count > 0 and self.batch_out_label.text().strip():
            self.btn_batch_start.setEnabled(True)
            self.btn_batch_start.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold;")
            self.batch_progress_label.setText(f"0 / {checked_count} Completed")
        else:
            self.btn_batch_start.setEnabled(False)
            self.btn_batch_start.setStyleSheet("font-weight: bold;")
            self.batch_progress_label.setText("0 / 0 Completed")

    def validate_inputs(self):
        if self.dicom_label.text().strip() and self.out_label.text().strip():
            self.btn_start.setEnabled(True)
            self.btn_start.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold;")
        else:
            self.btn_start.setEnabled(False)
            self.btn_start.setStyleSheet("font-weight: bold;")

    def calc_erosion(self):
        text = self.erosion_input.text()
        try:
            iters = int(text)
            if self.spacing_xy and iters >= 0:
                avg_spacing = (self.spacing_xy[0] + self.spacing_xy[1]) / 2.0
                approx_mm = iters * avg_spacing
                self.erosion_mm_label.setText(f"Approx erosion: {approx_mm:.2f} mm")
                self.erosion_mm_label.setStyleSheet("color: #198754;")
            else:
                self.erosion_mm_label.setText("Approx erosion: N/A")
                self.erosion_mm_label.setStyleSheet("color: gray;")
        except ValueError:
            self.erosion_mm_label.setText("Invalid iterations")
            self.erosion_mm_label.setStyleSheet("color: #dc3545;")

    def append_log(self, text):
        self.log_area.moveCursor(QTextCursor.End)
        self.log_area.insertPlainText(text)
        self.log_area.moveCursor(QTextCursor.End)

    def check_uv_installed(self):
        return shutil.which("uv") is not None

    def start_process(self):
        self.log_area.clear()
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Installing / Syncing Environment...")
        self.dicom_btn.setEnabled(False)
        self.out_btn.setEnabled(False)

        # Note: In a production app, the uv installation itself could also be run via QProcess 
        # to not block the main UI thread. For simplicity, we create a QTimer to simulate async.
        QTimer.singleShot(100, self.run_setup_and_segmentation)

    def start_batch_process(self):
        self.log_area.clear()
        self.btn_batch_start.setEnabled(False)
        self.btn_batch_start.setText("Running Batch...")
        self.batch_dicom_btn.setEnabled(False)
        self.batch_out_btn.setEnabled(False)
        
        self.is_batch_mode = True
        self.batch_queue = []
        
        # Build Queue
        for i in range(self.batch_table.rowCount()):
            chk_widget = self.batch_table.cellWidget(i, 0)
            chk = chk_widget.layout().itemAt(0).widget()
            if chk.isChecked():
                dicom_path = self.batch_table.item(i, 1).data(Qt.UserRole)
                out_name = Path(dicom_path).name
                out_path = str(Path(self.batch_out_label.text()) / out_name)
                self.batch_queue.append((i, dicom_path, out_path))
                
        self.current_batch_index = -1
        
        QTimer.singleShot(100, self.run_setup_and_segmentation)

    def run_setup_and_segmentation(self):
        try:
            # 1. Install uv if missing (blocking call here since it's just a small curl/powershell)
            if not self.check_uv_installed():
                self.append_log("[SYSTEM] Installing 'uv' package manager...\n")
                if os.name == 'nt':
                    cmd = 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
                else:
                    cmd = 'curl -LsSf https://astral.sh/uv/install.sh | sh'
                
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                self.append_log(res.stdout)
                
                if res.returncode != 0:
                    self.append_log("[ERROR] Failed to install uv.\n" + res.stderr)
                    self.reset_ui()
                    return

                # Add to PATH
                uv_path = os.path.expanduser("~\\.cargo\\bin") if os.name == 'nt' else os.path.expanduser("~/.cargo/bin")
                os.environ["PATH"] += os.pathsep + uv_path
                self.append_log("[SUCCESS] 'uv' installed.\n")

            # 2. Sync Environment via QProcess
            self.append_log("Syncing AI environment dependencies...\n")
            
            # We chain the QProcess commands: first sync, then seg
            self.process.start("uv", ["sync"])
            self.process_state = "sync"

        except Exception as e:
            self.append_log(f"[EXCEPTION] {str(e)}\n")
            if self.is_batch_mode:
                self.reset_batch_ui()
            else:
                self.reset_ui()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        self.append_log(stdout)

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.append_log(stderr)

    def process_finished(self):
        if self.process_state == "sync":
            if self.process.exitCode() == 0:
                self.append_log("\n[SUCCESS] Environment synced. Starting AI Inference...\n")
                if self.is_batch_mode:
                    self.run_next_batch_task()
                else:
                    self.execute_segmentation()
            else:
                self.append_log("\n[ERROR] Dependency sync failed.\n")
                if self.is_batch_mode:
                    self.reset_batch_ui()
                else:
                    self.reset_ui()
        elif self.process_state == "seg":
            if self.process.exitCode() == 0:
                self.append_log("\n[SUCCESS] Segmentation Completed!\n")
                if self.is_batch_mode and self.current_batch_index >= 0:
                    row = self.batch_queue[self.current_batch_index][0]
                    self.batch_table.item(row, 2).setText("Success")
            else:
                self.append_log(f"\n[ERROR] Segmentation Process exited with code {self.process.exitCode()}.\n")
                if self.is_batch_mode and self.current_batch_index >= 0:
                    row = self.batch_queue[self.current_batch_index][0]
                    self.batch_table.item(row, 2).setText("Failed")
                    
            if self.is_batch_mode:
                self.run_next_batch_task()
            else:
                self.reset_ui()

    def run_next_batch_task(self):
        self.current_batch_index += 1
        
        if self.current_batch_index < len(self.batch_queue):
            row, dicom_path, out_path = self.batch_queue[self.current_batch_index]
            self.batch_table.item(row, 2).setText("Running")
            self.batch_progress_label.setText(f"{self.current_batch_index} / {len(self.batch_queue)} Completed")
            self.execute_segmentation(dicom_path=dicom_path, out_path=out_path)
        else:
            self.append_log("\n[SUCCESS] All batch tasks completed!\n")
            self.batch_progress_label.setText(f"{len(self.batch_queue)} / {len(self.batch_queue)} Completed")
            self.reset_batch_ui()

    def execute_segmentation(self, dicom_path=None, out_path=None):
        if not dicom_path:
            dicom_path = self.dicom_label.text()
        if not out_path:
            out_path = self.out_label.text()
            
        if not self.is_batch_mode:
            self.btn_start.setText("Running Inference...")
        
        target_script = "seg.py"
        
        # 檢查是否有 mock_seg.py (用於開發與初次測試)
        if (BASE_DIR / "mock_seg.py").exists():
            target_script = "mock_seg.py"

        cmd_args = [
            "run", target_script,
            "--dicom", dicom_path,
            "--out", out_path,
            "--task", self.task_combo.currentText(),
            "--spine", "1" if self.chk_spine.isChecked() else "0",
            "--fast", "1" if self.chk_fast.isChecked() else "0",
            "--auto_draw", "1" if self.chk_draw.isChecked() else "0",
            "--erosion_iters", self.erosion_input.text()
        ]
        
        self.append_log(f"\n> uv {' '.join(cmd_args)}\n\n")
        self.process_state = "seg"
        self.process.start("uv", cmd_args)

    def reset_ui(self):
        self.is_batch_mode = False
        self.btn_start.setText("Start Segmentation")
        self.btn_start.setEnabled(True)
        self.dicom_btn.setEnabled(True)
        self.out_btn.setEnabled(True)
        
    def reset_batch_ui(self):
        self.is_batch_mode = False
        self.btn_batch_start.setText("Start Batch Processing")
        self.batch_dicom_btn.setEnabled(True)
        self.batch_out_btn.setEnabled(True)
        self.update_batch_start_button()

    def closeEvent(self, event):
        # Kill the QProcess cleanly
        if self.process.state() == QProcess.Running:
            self.process.kill()
            self.process.waitForFinished()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set global font for a modern look
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = TotalSegApp()
    window.show()
    sys.exit(app.exec())
