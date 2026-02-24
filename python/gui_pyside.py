import sys
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QCheckBox, QFrame,
    QLineEdit, QFileDialog, QPlainTextEdit, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QStackedWidget,
    QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QProcess, QTimer, QSize
from PySide6.QtGui import QFont, QTextCursor, QIcon, QColor

# Try importing SimpleITK for erosion calculation
try:
    import SimpleITK as sitk
except ImportError:
    sitk = None

# Determine if running as a bundled PyInstaller EXE
import platform
IS_BUNDLED = getattr(sys, 'frozen', False)

if IS_BUNDLED:
    EXE_DIR = Path(sys.executable).parent
    BASE_DIR = EXE_DIR / "TotalSeg_Backend"
    MEIPASS_DIR = Path(sys._MEIPASS)
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    required_files = ["pyproject.toml", "uv.lock", "seg.py", "draw.py"]
    for f in required_files:
        src = MEIPASS_DIR / f
        dst = BASE_DIR / f
        if src.exists():
            shutil.copy2(src, dst)
else:
    BASE_DIR = Path(__file__).parent

# Modern QSS Style for a premium look
MODERN_STYLE = """
QMainWindow {
    background-color: #ffffff;
}
QWidget {
    font-size: 13px;
    color: #333;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    margin-top: 15px;
    background-color: #fcfcfc;
    padding-top: 25px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    padding: 0 8px;
    color: #495057;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #f8f9fa;
    border-color: #adb5bd;
}
QPushButton:pressed {
    background-color: #e9ecef;
}
QPushButton#primary_btn {
    background-color: #0d6efd;
    color: white;
    border: none;
    font-weight: bold;
}
QPushButton#primary_btn:hover {
    background-color: #0b5ed7;
}
QPushButton#primary_btn:disabled {
    background-color: #e9ecef;
    color: #adb5bd;
}

/* Header Switcher Buttons */
QPushButton#mode_btn {
    border: none;
    background-color: transparent;
    border-radius: 0px;
    border-bottom: 3px solid transparent;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    color: #6c757d;
}
QPushButton#mode_btn:hover {
    color: #0d6efd;
}
QPushButton#mode_btn[active="true"] {
    color: #0d6efd;
    border-bottom: 3px solid #0d6efd;
}

QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    gridline-color: #f8f9fa;
}
/* Fix for Black Bar Selection */
QTableWidget::item:selected {
    background-color: #e7f1ff;
    color: #0d6efd;
}
QTableWidget::item {
    padding: 8px;
    color: #333333;
}
QHeaderView::section {
    background-color: #f8f9fa;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #e9ecef;
    font-weight: bold;
    color: #495057;
}
QProgressBar {
    border: none;
    background-color: #f1f3f5;
    height: 8px;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0d6efd;
    border-radius: 4px;
}
QPlainTextEdit {
    background-color: #fafbfc;
    color: #444;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 12px;
}
QLineEdit {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 8px;
    background-color: white;
}
"""

TASK_OPTIONS = [
    "abdominal_muscles",
    "aortic_sinuses",
    "appendicular_bones",
    "appendicular_bones_mr",
    "body",
    "body_mr",
    "brain_structures",
    "breasts",
    "cerebral_bleed",
    "coronary_arteries",
    "craniofacial_structures",
    "face",
    "face_mr",
    "head_glands_cavities",
    "head_muscles",
    "headneck_bones_vessels",
    "headneck_muscles",
    "heartchambers_highres",
    "hip_implant",
    "kidney_cysts",
    "liver_segments",
    "liver_segments_mr",
    "lung_nodules",
    "lung_vessels",
    "oculomotor_muscles",
    "pleural_pericard_effusion",
    "thigh_shoulder_muscles",
    "thigh_shoulder_muscles_mr",
    "tissue_4_types",
    "tissue_types",
    "tissue_types_mr",
    "ventricle_parts",
    "vertebrae_body",
    "vertebrae_mr",
    "total_mr",
    "total",
]

class TotalSegApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TotalSegmentator AI 影像管理系統 v0.0.1")
        self.resize(1150, 850)
        self.setStyleSheet(MODERN_STYLE)

        # State Variables
        self.spacing_xy = None
        self.batch_queue = []
        self.current_batch_index = -1
        self.is_running = False
        
        self.compare_manual_mask = ""

        # 智慧解決方案引擎 (Solution Engine)
        self.solutions = {
            "CUDA out of memory": "【建議解決方案】顯卡記憶體不足。請開啟「快速推論模式」或關閉其他佔用顯卡的程式。",
            "No Series can be found": "【建議解決方案】找不到影像。請確認資料夾內包含標準 DICOM 檔案，或嘗試掃描更深層的目錄。",
            "UnicodeEncodeError": "【建議解決方案】檔案路徑包含特殊字元。請將資料夾移動至僅包含英文與數字的路徑。",
            "Permission denied": "【建議解決方案】存取被拒。請檢查資料夾權限，或暫時關閉可能攔截程式的防毒軟體。",
            "torch_shm_manager": "【macOS 專用修復】偵測到 PyTorch 權限問題。系統已嘗試自動修復，請再次按下「啟動 AI 自動分割任務」。",
            "mach port for IMKCFRunLoopWakeUpReliable": "【系統提示】這是 macOS 的輸入法相容性警告，不影響程式執行，請放心使用。",
            "ModuleNotFoundError": "【技術提示】環境組件遺失。請重新執行 `uv sync` 以確保所有依賴項已正確安裝。"
        }

        # Central Widget & Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_v_layout = QVBoxLayout(self.central_widget)
        self.main_v_layout.setContentsMargins(0, 0, 0, 0)
        self.main_v_layout.setSpacing(0)

        # --- Top Navigation Bar ---
        self.nav_bar = QFrame()
        self.nav_bar.setStyleSheet("background-color: white; border-bottom: 1px solid #e9ecef;")
        self.nav_bar.setFixedHeight(65)
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(30, 0, 30, 0)

        brand_lbl = QLabel("TotalSeg AI")
        brand_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #0d6efd; margin-right: 30px;")
        nav_layout.addWidget(brand_lbl)

        # Mode Selector Buttons
        self.btn_mode_seg = QPushButton("🧠  AI 自動分割 (Segmentation)")
        self.btn_mode_seg.setObjectName("mode_btn")
        self.btn_mode_seg.setProperty("active", True)
        self.btn_mode_seg.clicked.connect(lambda: self.switch_mode("seg"))
        nav_layout.addWidget(self.btn_mode_seg)

        self.btn_mode_compare = QPushButton("⚖️  影像對比分析 (Manual Compare)")
        self.btn_mode_compare.setObjectName("mode_btn")
        self.btn_mode_compare.setProperty("active", False)
        self.btn_mode_compare.clicked.connect(lambda: self.switch_mode("compare"))
        nav_layout.addWidget(self.btn_mode_compare)

        nav_layout.addStretch()
        
        # Detected Device Label
        self.device_lbl = QLabel("後端推論引擎準備中...")
        self.device_lbl.setStyleSheet("color: #6c757d; font-size: 11px;")
        nav_layout.addWidget(self.device_lbl)
        
        self.main_v_layout.addWidget(self.nav_bar)

        # --- Content Area (Stacked) ---
        self.content_stack = QStackedWidget()
        self.main_v_layout.addWidget(self.content_stack)

        # PAGE 1: Segmentation
        self.page_seg = QWidget()
        self.setup_seg_page()
        self.content_stack.addWidget(self.page_seg)

        # PAGE 2: Comparison
        self.page_compare = QWidget()
        self.setup_compare_page()
        self.content_stack.addWidget(self.page_compare)

        # --- Bottom Log Area ---
        self.log_container = QWidget()
        self.log_container.setStyleSheet("background-color: white; padding: 10px 30px 30px 30px;")
        log_layout = QVBoxLayout(self.log_container)
        
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Monaco", 9)) if sys.platform == "darwin" else self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setMaximumHeight(150)
        self.log_area.setPlaceholderText("系統執行日誌將顯示於此...")
        log_layout.addWidget(self.log_area)
        
        self.main_v_layout.addWidget(self.log_container)

        # QProcess
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(BASE_DIR))
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

    def switch_mode(self, mode):
        if mode == "seg":
            self.content_stack.setCurrentIndex(0)
            self.btn_mode_seg.setProperty("active", True)
            self.btn_mode_compare.setProperty("active", False)
        else:
            self.content_stack.setCurrentIndex(1)
            self.btn_mode_seg.setProperty("active", False)
            self.btn_mode_compare.setProperty("active", True)
        
        # Refresh styles
        self.btn_mode_seg.style().unpolish(self.btn_mode_seg)
        self.btn_mode_seg.style().polish(self.btn_mode_seg)
        self.btn_mode_compare.style().unpolish(self.btn_mode_compare)
        self.btn_mode_compare.style().polish(self.btn_mode_compare)

    def setup_seg_page(self):
        layout = QHBoxLayout(self.page_seg)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(30)

        # Left Column: Config
        left_col = QFrame()
        left_col.setFixedWidth(350)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # 📂 Input Selection
        io_group = QGroupBox("1. 影像資料來源")
        io_layout = QVBoxLayout(io_group)
        
        self.btn_select_src = QPushButton("📂  選擇 DICOM 資料夾")
        self.btn_select_src.setMinimumHeight(48)
        self.btn_select_src.clicked.connect(self.select_source)
        io_layout.addWidget(self.btn_select_src)

        self.src_label = QLabel("尚未選擇來源路徑")
        self.src_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.src_label.setWordWrap(True)
        io_layout.addWidget(self.src_label)
        
        left_layout.addWidget(io_group)

        # ⚙️ AI Settings
        cfg_group = QGroupBox("2. AI 分割參數設定")
        cfg_layout = QVBoxLayout(cfg_group)
        
        grid_layout = QFormLayout()
        grid_layout.setSpacing(10)
        
        self.modality_combo = QComboBox()
        self.modality_combo.addItems(["CT", "MRI"])
        self.modality_combo.setMaxVisibleItems(12)
        self.modality_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        grid_layout.addRow("影像類別:", self.modality_combo)
        
        self.task_combo = QComboBox()
        self.task_combo.addItems(TASK_OPTIONS)
        self.task_combo.setMaxVisibleItems(12)
        self.task_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        grid_layout.addRow("分割任務:", self.task_combo)
        
        cfg_layout.addLayout(grid_layout)

        self.chk_spine = QCheckBox("標註脊椎層級 (需較長時間)")
        self.chk_spine.setChecked(True)
        self.chk_fast = QCheckBox("快速推論模式 (低解析度)")
        self.chk_draw = QCheckBox("自動產生影像疊加圖 (PNG)")
        self.chk_draw.setChecked(True)
        
        cfg_layout.addWidget(self.chk_spine)
        cfg_layout.addWidget(self.chk_fast)
        cfg_layout.addWidget(self.chk_draw)

        erosion_box = QHBoxLayout()
        erosion_box.addWidget(QLabel("肌肉收縮迭代 (Erosion):"))
        self.erosion_input = QLineEdit("7")
        self.erosion_input.setFixedWidth(40)
        self.erosion_input.textChanged.connect(self.calc_erosion)
        erosion_box.addWidget(self.erosion_input)
        cfg_layout.addLayout(erosion_box)
        
        self.erosion_mm_label = QLabel("預估邊緣收縮: N/A")
        self.erosion_mm_label.setStyleSheet("color: #198754; font-size: 11px;")
        cfg_layout.addWidget(self.erosion_mm_label)

        # Slice Range Selection
        range_box = QGroupBox("切片範圍計算 (選填)")
        range_box.setCheckable(True)
        range_box.setChecked(False)
        range_layout = QHBoxLayout(range_box)
        range_layout.addWidget(QLabel("從"))
        self.slice_start_input = QLineEdit("1")
        self.slice_start_input.setFixedWidth(40)
        range_layout.addWidget(self.slice_start_input)
        range_layout.addWidget(QLabel("至"))
        self.slice_end_input = QLineEdit("")
        self.slice_end_input.setPlaceholderText("末")
        self.slice_end_input.setFixedWidth(40)
        range_layout.addWidget(self.slice_end_input)
        range_layout.addWidget(QLabel("張"))
        cfg_layout.addWidget(range_box)
        self.range_box_widget = range_box

        left_layout.addWidget(cfg_group)
        
        # Output Group (Optional/Hidden)
        self.out_group = QGroupBox("3. 輸出路徑設定 (選填)")
        self.out_group.setCheckable(True)
        self.out_group.setChecked(False)
        out_layout = QVBoxLayout(self.out_group)
        self.btn_select_out = QPushButton("📁  修改輸出存放目錄")
        self.btn_select_out.clicked.connect(self.select_output)
        out_layout.addWidget(self.btn_select_out)
        self.out_label = QLabel("預設：於來源路徑旁產生 _output 檔案夾")
        self.out_label.setStyleSheet("font-size: 10px; color: #666;")
        out_layout.addWidget(self.out_label)
        left_layout.addWidget(self.out_group)
        
        left_layout.addStretch()
        layout.addWidget(left_col)

        # Right Column: Queue
        right_col = QFrame()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Task Table
        self.task_table = QTableWidget(0, 3)
        self.task_table.setHorizontalHeaderLabels(["", "病患 / 影像路徑", "處理狀態"])
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.task_table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        # Table Styling
        self.task_table.setShowGrid(False)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setStyleSheet("alternate-background-color: #fafbfc; selection-background-color: #e7f1ff;")
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.task_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.task_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        right_layout.addWidget(self.task_table)

        # Progress
        self.prog_bar_lbl = QLabel("待處理任務清單")
        right_layout.addWidget(self.prog_bar_lbl)
        self.pbar = QProgressBar()
        right_layout.addWidget(self.pbar)

        self.btn_start = QPushButton("🚀  啟動 AI 自動分割任務")
        self.btn_start.setObjectName("primary_btn")
        self.btn_start.setMinimumHeight(65)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_unified_process)
        right_layout.addWidget(self.btn_start)

        layout.addWidget(right_col)

    def setup_compare_page(self):
        layout = QVBoxLayout(self.page_compare)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        header_lbl = QLabel("⚖️ 人工標註 vs AI 自動分割對比分析")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #495057;")
        layout.addWidget(header_lbl)
        
        desc_lbl = QLabel("請選取 NIfTI (.nii.gz) 或 NRRD (.nrrd) 檔案，系統將計算 Dice 系數與體積差異。")
        desc_lbl.setStyleSheet("color: #6c757d;")
        layout.addWidget(desc_lbl)
        
        comp_group = QGroupBox("分析檔案選取")
        comp_layout = QFormLayout(comp_group)
        comp_layout.setSpacing(15)
        
        # AI Mask Path
        self.ai_mask_path_lbl = QLabel("尚未選取檔案")
        self.ai_mask_path_lbl.setWordWrap(True)
        btn_ai = QPushButton("🔍 選取 AI 分割結果 (NII/NRRD)")
        btn_ai.clicked.connect(self.select_compare_ai)
        comp_layout.addRow(btn_ai, self.ai_mask_path_lbl)
        
        # Manual Mask Path
        self.manual_mask_path_lbl = QLabel("尚未選取檔案")
        self.manual_mask_path_lbl.setWordWrap(True)
        btn_manual = QPushButton("🔍 選取人工標註結果 (NII/NRRD)")
        btn_manual.clicked.connect(self.select_compare_manual)
        comp_layout.addRow(btn_manual, self.manual_mask_path_lbl)
        
        layout.addWidget(comp_group)

        # Action
        self.btn_run_compare = QPushButton("📊 開始執行比對分析")
        self.btn_run_compare.setObjectName("primary_btn")
        self.btn_run_compare.setMinimumHeight(55)
        self.btn_run_compare.setEnabled(False)
        self.btn_run_compare.clicked.connect(self.run_compare_analysis)
        layout.addWidget(self.btn_run_compare)
        
        layout.addStretch()

    # --- Comparison Methods ---
    def select_compare_ai(self):
        path, _ = QFileDialog.getOpenFileName(self, "選取 AI 分割結果 (NII/NRRD)", "", "Medical Images (*.nii *.nii.gz *.nrrd)")
        if path:
            self.compare_ai_mask = path
            self.ai_mask_path_lbl.setText(path)
            self.check_compare_ready()

    def select_compare_manual(self):
        path, _ = QFileDialog.getOpenFileName(self, "選取人工標註結果 (NII/NRRD)", "", "Medical Images (*.nii *.nii.gz *.nrrd)")
        if path:
            self.compare_manual_mask = path
            self.manual_mask_path_lbl.setText(path)
            self.check_compare_ready()

    def check_compare_ready(self):
        self.btn_run_compare.setEnabled(bool(self.compare_ai_mask and self.compare_manual_mask))

    def run_compare_analysis(self):
        self.log_area.clear()
        self.append_log("系統：開始執行對比分析...\n")
        self.btn_run_compare.setEnabled(False)
        
        try:
            if not sitk:
                raise ImportError("尚未安裝 SimpleITK。")

            ai_img = sitk.ReadImage(self.compare_ai_mask)
            manual_img = sitk.ReadImage(self.compare_manual_mask)
            
            ai_arr = sitk.GetArrayFromImage(ai_img)
            manual_arr = sitk.GetArrayFromImage(manual_img)
            spacing = manual_img.GetSpacing()
            
            # Find the slice annotated by the doctor
            slice_idx = -1
            for i in range(manual_arr.shape[0]):
                if np.any(manual_arr[i] > 0):
                    slice_idx = i
                    break
                    
            if slice_idx == -1:
                self.append_log("❌ [錯誤] 無法在「人工標註結果」中找到任何標註 (皆為 0)。\n")
                return

            import numpy as np
            ai_slice = ai_arr[slice_idx] > 0
            manual_slice = manual_arr[slice_idx] > 0
            
            # Dice
            intersection = np.logical_and(ai_slice, manual_slice).sum()
            total = ai_slice.sum() + manual_slice.sum()
            dice = (2.0 * intersection / total) if total > 0 else 0.0
            
            # Area
            pixel_cm2 = (spacing[0] * spacing[1]) / 100.0
            ai_area = float(ai_slice.sum() * pixel_cm2)
            manual_area = float(manual_slice.sum() * pixel_cm2)
            
            self.append_log(f"✅ [成功] 找到標註層級：第 {slice_idx + 1} 層\n")
            self.append_log("-" * 40 + "\n")
            self.append_log(f"🧠 AI 分割面積： {ai_area:.2f} cm²\n")
            self.append_log(f"👨‍⚕️ 人工標註面積： {manual_area:.2f} cm²\n")
            self.append_log(f"🎯 Dice 重合度： {dice:.4f} (滿分 1.0)\n")
            self.append_log("-" * 40 + "\n")
            
            # HTML 樣式高亮
            if dice >= 0.9:
                self.append_log("<span style='color: #198754; font-weight: bold;'>評估：極致吻合 (Dice ≥ 0.9)</span><br>", is_html=True)
            elif dice >= 0.8:
                self.append_log("<span style='color: #0d6efd; font-weight: bold;'>評估：高度吻合 (Dice ≥ 0.8)</span><br>", is_html=True)
            else:
                self.append_log("<span style='color: #dc3545; font-weight: bold;'>評估：吻合度偏低，建議人工檢視</span><br>", is_html=True)
                
        except Exception as e:
            self.append_log(f"❌ [錯誤] 比對失敗：{str(e)}\n")
        finally:
            self.btn_run_compare.setEnabled(True)

    # --- Logic ---

    def select_source(self):
        path = QFileDialog.getExistingDirectory(self, "請選取 DICOM 資料夾或病患根目錄")
        if path:
            self.src_label.setText(path)
            parent_dir = Path(path).parent
            self.out_label.setText(str(parent_dir / (Path(path).name + "_output")))
            self.scan_directory(path)

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "請選取輸出資料存放根目錄")
        if folder:
            self.out_label.setText(folder)

    def has_dicom_files(self, folder):
        """檢查資料夾內是否有疑似 DICOM 的檔案 (包含無副檔名或 .dcm)"""
        # 1. 優先檢查是否有名顯的 .dcm 結尾
        if list(folder.glob("*.dcm")):
            return True
        # 2. 如果沒有 .dcm，檢查是否有無副檔名的非隱藏檔案 (常見於醫療系統匯出)
        # 我們只看前 3 個檔案來加快掃描速度
        files = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")]
        if files:
            # 測試第一個檔案是否能被 ITK 識別 (如果有安裝)
            if sitk:
                try:
                    reader = sitk.ImageFileReader()
                    reader.SetFileName(str(files[0]))
                    reader.ReadImageInformation()
                    return True
                except:
                    pass
        return False

    def scan_directory(self, root_path):
        self.task_table.setRowCount(0)
        root = Path(root_path)
        valid_folders = []
        
        # 1. 檢查是否直接為 DICOM 目錄
        if self.has_dicom_files(root):
            valid_folders.append(root)
        else:
            # 2. 遞迴搜尋子目錄 (最多往內找 4 層，確保效能)
            for sub_dir in root.rglob("*"):
                if sub_dir.is_dir():
                    # 避免掃描太深或掃描到輸出資料夾
                    if "_output" in sub_dir.name or "TotalSeg_Backend" in sub_dir.name:
                        continue
                    if self.has_dicom_files(sub_dir):
                        valid_folders.append(sub_dir)

        if not valid_folders:
            self.append_log("[警示] 未在所選路徑偵測到 DICOM 影像檔。\n")
            self.btn_start.setEnabled(False)
            return

        self.task_table.setRowCount(len(valid_folders))
        for i, folder in enumerate(valid_folders):
            chk = QCheckBox()
            chk.setChecked(True)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.task_table.setCellWidget(i, 0, chk_widget)
            chk.stateChanged.connect(self.update_ui_state)
            
            try:
                display_name = str(folder.relative_to(root)) if folder != root else folder.name
            except ValueError:
                display_name = str(folder)
                
            path_item = QTableWidgetItem(display_name)
            path_item.setData(Qt.UserRole, str(folder))
            self.task_table.setItem(i, 1, path_item)
            
            status_item = QTableWidgetItem("待處理 (Ready)")
            self.task_table.setItem(i, 2, status_item)
            
        self.update_ui_state()

        # 精進 Spacing 偵測邏輯，解決 ITK 無法識別單一檔案導致 N/A 的問題
        if sitk:
            try:
                reader = sitk.ImageSeriesReader()
                # 使用 SeriesReader 抓取 DICOM 系列檔案通常比 ReadImage(單檔) 更穩定
                dicom_names = reader.GetGDCMSeriesFileNames(str(valid_folders[0]))
                if dicom_names:
                    # 讀取系列中的第一張圖來獲取中繼資料
                    first_img = sitk.ReadImage(dicom_names[0])
                    spacing = first_img.GetSpacing()
                    self.spacing_xy = (spacing[0], spacing[1])
                    self.append_log(f"[系統] 成功識別影像解析度: {spacing[0]:.2f} x {spacing[1]:.2f} mm\n")
                else:
                    self.spacing_xy = None
            except Exception as e:
                self.spacing_xy = None
                # 不在 Log 顯示冗長的錯誤，保持介面簡潔
        self.calc_erosion()

    def update_ui_state(self):
        checked_count = 0
        for i in range(self.task_table.rowCount()):
            chk_widget = self.task_table.cellWidget(i, 0)
            if chk_widget.layout().itemAt(0).widget().isChecked():
                checked_count += 1
        
        self.btn_start.setEnabled(checked_count > 0)
        self.prog_bar_lbl.setText(f"目前項目中共有 {checked_count} 個待處理任務")
        self.pbar.setMaximum(checked_count if checked_count > 0 else 1)
        self.pbar.setValue(0)

    def calc_erosion(self):
        text = self.erosion_input.text()
        try:
            iters = int(text)
            if self.spacing_xy and iters >= 0:
                avg_spacing = (self.spacing_xy[0] + self.spacing_xy[1]) / 2.0
                approx_mm = iters * avg_spacing
                self.erosion_mm_label.setText(f"預估邊緣收縮: {approx_mm:.2f} mm")
            else:
                self.erosion_mm_label.setText("預估邊緣收縮: N/A")
        except ValueError:
            self.erosion_mm_label.setText("迭代數值錯誤")

    def append_log(self, text, is_html=False):
        self.log_area.moveCursor(QTextCursor.End)
        if is_html:
            self.log_area.appendHtml(text)
        else:
            self.log_area.insertPlainText(text)
        self.log_area.moveCursor(QTextCursor.End)

    def start_unified_process(self):
        self.log_area.clear()
        self.is_running = True
        self.btn_start.setEnabled(False)
        self.btn_start.setText("⏳ 初始化 AI 環境中...")
        
        self.batch_queue = []
        for i in range(self.task_table.rowCount()):
            chk_widget = self.task_table.cellWidget(i, 0)
            if chk_widget.layout().itemAt(0).widget().isChecked():
                dicom_path = self.task_table.item(i, 1).data(Qt.UserRole)
                out_root = self.out_label.text()
                
                # 自動路徑解析
                if "預設" in out_root or not out_root:
                    out_root = str(Path(dicom_path).parent / (Path(dicom_path).name + "_output"))
                
                out_path = out_root
                if self.task_table.rowCount() > 1:
                    out_path = str(Path(out_root) / Path(dicom_path).name)

                self.batch_queue.append((i, dicom_path, out_path))
                
        self.current_batch_index = -1
        QTimer.singleShot(100, self.run_setup_and_segmentation)

    def run_setup_and_segmentation(self):
        try:
            if shutil.which("uv") is None:
                self.append_log("[系統] 正在安裝『uv』環境管理工具...\n")
                cmd = 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' if os.name == 'nt' else 'curl -LsSf https://astral.sh/uv/install.sh | sh'
                subprocess.run(cmd, shell=True, capture_output=True)
                if os.name == "nt":
                    uv_paths = [
                        os.path.expanduser("~\\.local\\bin"),
                        os.path.expanduser("~\\.cargo\\bin"),
                    ]
                else:
                    uv_paths = [os.path.expanduser("~/.local/bin"), os.path.expanduser("~/.cargo/bin")]
                for uv_path in uv_paths:
                    if uv_path not in os.environ.get("PATH", ""):
                        os.environ["PATH"] += os.pathsep + uv_path

            self.append_log("同步 AI 引擎環境中...\n")
            self.process_state = "sync"
            self.process.start("uv", ["sync"])
        except Exception as e:
            self.append_log(f"[異常中斷] {str(e)}\n")
            self.reset_ui()

    def handle_stdout(self):
        self.append_log(bytes(self.process.readAllStandardOutput()).decode("utf8"))

    def handle_stderr(self):
        self.append_log(bytes(self.process.readAllStandardError()).decode("utf8"))

    def fix_macos_torch_perms(self):
        """自動修復 macOS 上 torch_shm_manager 的執行權限"""
        try:
            # 尋找 venv 中的 torch bin 目錄
            torch_bin = BASE_DIR / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "torch" / "bin" / "torch_shm_manager"
            if torch_bin.exists():
                subprocess.run(["chmod", "+x", str(torch_bin)], check=True)
                self.append_log(f"[系統] 已自動修復 macOS PyTorch 核心執行權限。\n")
        except Exception as e:
            self.append_log(f"[警告] 自動修復權限失敗: {str(e)}\n")

    def diagnose_error(self, log_text):
        """掃描 Log 內容並提供白話解決建議"""
        suggestions = []
        for key, advice in self.solutions.items():
            if key in log_text:
                suggestions.append(advice)
        
        if suggestions:
            self.append_log("\n" + "─"*30)
            self.append_log("\n🕵️ <span style='font-size: 14px; font-weight: bold;'>智慧診斷報告：</span>\n", is_html=True)
            for s in suggestions:
                # 使用 HTML 呈現黃色強調背景
                self.append_log(f"<div style='background-color: #fff3cd; color: #856404; padding: 5px; border-radius: 5px;'>{s}</div><br>", is_html=True)
            self.append_log("─"*30 + "\n")

    def process_finished(self):
        if self.process_state == "sync":
            if self.process.exitCode() == 0:
                # macOS 特殊處理：修復 torch_shm_manager 權限
                if sys.platform == "darwin":
                    self.fix_macos_torch_perms()
                self.run_next_batch_task()
            else:
                self.reset_ui()
        elif self.process_state == "seg":
            if self.current_batch_index >= 0:
                row = self.batch_queue[self.current_batch_index][0]
                if self.process.exitCode() == 0:
                    status = "處理完成"
                    self.task_table.item(row, 2).setText(status)
                    self.task_table.item(row, 2).setForeground(QColor("#198754"))
                else:
                    status = "處理失敗"
                    self.task_table.item(row, 2).setText(status)
                    self.task_table.item(row, 2).setForeground(QColor("#dc3545"))
                    self.diagnose_error(self.log_area.toPlainText())
            
            # 如果是最後一個任務，則重置 UI
            if self.current_batch_index >= len(self.batch_queue) - 1:
                self.reset_ui()
            
            self.run_next_batch_task()

    def run_next_batch_task(self):
        self.current_batch_index += 1
        if self.current_batch_index < len(self.batch_queue):
            row, dicom_path, out_path = self.batch_queue[self.current_batch_index]
            self.task_table.item(row, 2).setText("執行分割中...")
            self.task_table.item(row, 2).setForeground(QColor("#0d6efd"))
            self.prog_bar_lbl.setText(f"目前進度：第 {self.current_batch_index + 1} / {len(self.batch_queue)} 個任務")
            self.pbar.setValue(self.current_batch_index)
            
            target_script = "seg.py"

            cmd_args = [
                "run", target_script,
                "--dicom", dicom_path,
                "--out", out_path,
                "--task", self.task_combo.currentText(),
                "--modality", self.modality_combo.currentText(),
                "--spine", "1" if self.chk_spine.isChecked() else "0",
                "--fast", "1" if self.chk_fast.isChecked() else "0",
                "--auto_draw", "1" if self.chk_draw.isChecked() else "0",
                "--erosion_iters", self.erosion_input.text()
            ]

            # 1. 切片範圍防呆 (Slice Range Guard)
            if self.range_box_widget.isChecked():
                start_str = self.slice_start_input.text()
                end_str = self.slice_end_input.text()
                
                if not start_str.isdigit() or (end_str and not end_str.isdigit()):
                    QMessageBox.warning(self, "輸入錯誤", "切片範圍必須為數字！")
                    return

                start_val = int(start_str)
                if end_str:
                    end_val = int(end_str)
                    if start_val > end_val:
                        QMessageBox.warning(self, "邏輯錯誤", "起始層級不能大於結束層級！")
                        return

                if start_str:
                    cmd_args.extend(["--slice_start", start_str])
                if end_str:
                    cmd_args.extend(["--slice_end", end_str])

            self.process_state = "seg"
            self.process.start("uv", cmd_args)
        else:
            self.append_log("\n[完成] 所有自動分割任務已處理完畢。\n")
            self.pbar.setValue(len(self.batch_queue))
            self.reset_ui()

    def reset_ui(self):
        self.is_running = False
        self.btn_start.setText("🚀  啟動 AI 自動分割任務")
        self.btn_start.setEnabled(True)
        self.btn_select_src.setEnabled(True)

    def closeEvent(self, event):
        if self.process.state() == QProcess.Running:
            self.process.kill()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TotalSegApp()
    window.show()
    sys.exit(app.exec())
