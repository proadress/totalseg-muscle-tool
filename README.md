# TotalSeg Muscle Tool (v0.0.1)

[English](#english) | [中文](#中文)

---

## English

A medical image segmentation tool based on TotalSegmentator for CT image muscle segmentation analysis.

### Features

#### **Tool 1: Unified AI Analysis (Unified UI)**
- **MRI & CT Support**: Select modality to automatically use `total_mr` or standard CT models.
- **Partial Volume Calculation**: Specify a slice range (e.g., Slices 10-50) for targeted volumetric analysis.
- **Smart Detection**: Recursive scanning of nested folders and identification of extension-less DICOMs.
- **Solution Engine**: Professional error diagnosis that translates technical logs into medical-friendly advice.
- **Manual vs AI Comparison**: Integrated DICE coefficient and volume difference analysis.

### Quick Start

#### **Windows**
Double-click `START 啟動.bat` (Windows) or run `uv run python/gui_pyside.py` (Mac/Linux) to launch. Background dependencies will be auto-managed on first run via `uv`.

#### **Mac/Linux**
```bash
cd python
uv run gui_pyside.py
```

### System Requirements

- **OS**: Windows 10/11, macOS, or Linux
- **Python**: 3.10
- **GPU**: NVIDIA GPU recommended (CUDA support), CPU also supported
- **Network**: Required for first-time installation

### Cross-Platform Support

- **Windows/Linux**: Automatically installs GPU version (CUDA 12.1)
- **macOS**: Automatically installs CPU version
- The launcher automatically detects your system and installs the appropriate PyTorch version

### Output Description

#### **Tool 1: AI Segmentation Output**

Example: Input `SER00005/`, output will be created in `SER00005_output/`:

- `segmentation_<task>/`: One mask per structure (`*.nii.gz`) + `statistics.json`
- `mask_<task>.csv`: Analysis results (4 sections)
  - Section 1: Area per slice (cm²)
  - Section 2: Average HU per slice (with erosion, weighted by area for L/R muscles)
  - Section 3: HU standard deviation per slice (with erosion, weighted by area)
  - Section 4: Overall summary (pixelcount / volume_cm³ / mean_hu, L/R muscles combined)
- `png/`: PNG overlay for each slice (if enabled)

#### **Tool 2: Batch Processing Output**

Results displayed in real-time in GUI and saved in root folder:
- `batch_processing_log_YYYYMMDD_HHMMSS.txt` - Detailed log
- `batch_processing_results_YYYYMMDD_HHMMSS.json` - Statistics (JSON format)

#### **Tool 3: Comparison Tool Output**

Results displayed in real-time in GUI:
- Slice Number: Manual annotation slice index
- Manual Area (cm²): Manually annotated muscle area
- AI Area (cm²): TotalSegmentator segmentation area on same slice
- Dice Score: Similarity between masks (formula: `2 * |A ∩ B| / (|A| + |B|)`)

Optional CSV export:
```csv
slice_number, manual_area_cm2, ai_area_cm2, dice_score
45, 52.30, 48.70, 0.8900
```

### CLI Usage (Advanced)

```bash
cd python

# Unified segmentation with new modality and range support
uv run seg.py --dicom ../SER00005 --task total --modality MRI --slice_start 10 --slice_end 50 --auto_draw 1

# Manual vs AI comparison
uv run gui_pyside.py  # Switch to Comparison tab in unified UI
```

### Key Parameters

- `--dicom`: DICOM folder path
- `--out`: Output root directory
- `--task`: TotalSegmentator task
- `--modality`: CT or MRI
- `--slice_start` / `--slice_end`: Range for volume calculation
- `--fast 1`: Fast mode
- `--spine 1`: Additional spine segmentation
- `--auto_draw 1`: Auto-generate PNG overlays
- `--erosion_iters`: Erosion iterations (default: 7)

### Calculation Logic

- **Area (cm²)**: Mask pixels per slice × `spacing_x × spacing_y / 100`
- **Volume (cm³)**: Total mask pixels × `spacing_x × spacing_y × spacing_z / 1000`
- **Slice average HU**: Morphological erosion on mask (default 7 iterations, reduced to 3 or none if too few pixels), then average HU of eroded region
- **Slice HU std**: Same erosion process, then standard deviation of HU in eroded region
- **L/R muscle merge (HU)**: Area-weighted average for each slice
- **Summary merge (mean_hu)**: Weighted by pixelcount

### Project Structure

```
totalseg-muscle-tool/
totalseg-muscle-tool/
├── START 啟動.bat          # Windows double-click launcher
└── python/
    ├── gui_pyside.py     # Unified PySide6 GUI (Single/Batch/Compare)
    ├── seg.py            # Segmentation core
    ├── draw.py           # PNG Visualization
    └── pyproject.toml    # Dependencies (uv)
```

### Testing

```bash
cd python
uv run python test_compare.py
```

Test items:
- Dice coefficient calculation (4 cases)
- Area calculation (4 cases)
- Slice detection (5 cases)

All tests passing indicates core logic is working properly.

### FAQ

#### **Tool 1 (AI Segmentation)**
- **Non-ASCII path causing drawing failure**: `draw.py` checks if path is ASCII. Move project/DICOM to pure English path.
- **Slow on first run**: TotalSegmentator may need to download model weights, and CPU inference is very slow.
- **GPU/CPU detection**: GUI displays detected device (`torch.cuda.is_available()`).

#### **Tool 2 (Batch Processing)**
- **No DICOM folders found**: Check max search depth setting or folder structure.
- **Some cases failed**: Check log file for specific error messages.

#### **Tool 3 (Manual vs AI Comparison)**
- **Dice score lower than expected**: (1) Slice mismatch, (2) Different segmentation scope, (3) Poor AI quality. Check overlap in 3D Slicer.
- **Spacing inconsistency warning**: When spacing differs >10%, program auto-resamples. Confirm both files are from same DICOM series.
- **Multi-slice warning**: Program designed for single-slice comparison. If manual annotation has multiple slices, first slice is automatically selected.

### Notes

> This project is for research/development purposes. Do not use for clinical diagnosis.

### License

This project is open source for research and educational purposes.

---

## 中文

基於 TotalSegmentator 的醫學影像分割小工具，用於 CT 影像的肌肉分割分析。

### 功能特色

#### **功能 1：統一 AI 分析介面 (Unified UI)**
- **MRI & CT 雙模態支援**：切換影像類別自動調用 `total_mr` 或 CT 專屬模型。
- **特定切片範圍計算**：可指定張數範圍（如第 20 到 40 張）進行精確的局部體積統計。
- **強健掃描邏輯**：自動識別深層嵌套目錄與無副檔名的 DICOM 檔案。
- **智慧診斷引擎**：發生報錯時自動提供白話文「解決建議」，不需閱讀代碼。
- **手動 vs AI 比較**：整合 DICE 系數與體積差異分析。

### 快速開始

#### **Windows**
雙擊執行 `START 啟動.bat` (Windows) 啟動程式。首次執行會自動完成環境配置。

> ⚠️ **溫馨提示**：若啟動失敗或無法讀取檔案，建議將解壓縮後的資料夾移至 **C 槽或 D 槽等純英文路徑下**執行，以避免 Windows 中文路徑造成的不可預期錯誤。

#### **Mac/Linux**
```bash
cd python
uv run gui_pyside.py
```

### 系統需求

- **作業系統**：Windows 10/11、macOS 或 Linux
- **Python**：3.10
- **GPU**：建議使用 NVIDIA GPU（支援 CUDA），也支援 CPU
- **網路**：第一次安裝時需要

### 跨平台支援

- **Windows/Linux**：自動安裝 GPU 版本（CUDA 12.1）
- **macOS**：自動安裝 CPU 版本
- 啟動器會自動偵測系統並安裝對應的 PyTorch 版本

### 輸出說明

#### **工具 1：AI 分割輸出**

範例：輸入 `SER00005/`，輸出會建立在 `SER00005_output/`：

- `segmentation_<task>/`：每個結構一個遮罩（`*.nii.gz`）+ `statistics.json`
- `mask_<task>.csv`：分析結果（4 個區塊）
  - 區塊 1：每層面積（cm²）
  - 區塊 2：每層平均 HU（經侵蝕處理，左右肌肉按面積加權合併）
  - 區塊 3：每層 HU 標準差（經侵蝕處理，左右肌肉按面積加權合併）
  - 區塊 4：整體摘要（pixelcount / volume_cm³ / mean_hu，左右肌肉合併）
- `png/`：每層一張疊圖 PNG（若有開啟）

#### **工具 2：批次處理輸出**

結果即時顯示在 GUI 並儲存於根目錄：
- `batch_processing_log_YYYYMMDD_HHMMSS.txt` - 詳細日誌
- `batch_processing_results_YYYYMMDD_HHMMSS.json` - 結果統計（JSON 格式）

#### **工具 3：比較工具輸出**

結果即時顯示在 GUI：
- 層數（Slice Number）：手動標註的層數索引
- 手動面積（cm²）：醫生手動標註的肌肉面積
- AI 面積（cm²）：TotalSegmentator 在同一層的分割面積
- Dice 分數：兩個遮罩的相似度（公式：`2 * |A ∩ B| / (|A| + |B|)`）

可選擇性匯出 CSV：
```csv
slice_number, manual_area_cm2, ai_area_cm2, dice_score
45, 52.30, 48.70, 0.8900
```

### CLI 用法（進階）

```bash
cd python

# 單檔/批次分割
uv run seg.py --dicom ../SER00005 --task total --modality MRI --slice_start 10 --slice_end 50 --auto_draw 1

# 手動 vs AI 比較
uv run gui_pyside.py  # 在統一介面中切換至「比較分析」分頁
```

### 主要參數

- `--dicom`：DICOM 資料夾路徑
- `--out`：輸出根目錄（預設為 DICOM 資料夾的 parent）
- `--task`：TotalSegmentator 任務
- `--fast 1`：快速模式（較快但精度可能下降）
- `--spine 1`：額外執行脊椎分割
- `--auto_draw 1`：分割完成後自動產生 PNG 疊圖
- `--erosion_iters`：HU 計算用的侵蝕次數（預設：7）

### 計算邏輯

- **面積（cm²）**：每層遮罩像素數 × `spacing_x × spacing_y / 100`
- **體積（cm³）**：所有遮罩像素數 × `spacing_x × spacing_y × spacing_z / 1000`
- **層平均 HU**：對該層遮罩做形態學侵蝕（預設 7 次，像素太少會降為 3 次或不侵蝕），取侵蝕後區域的 HU 平均
- **層 HU 標準差**：同上侵蝕流程，取侵蝕後區域的 HU 標準差
- **左右合併（HU）**：以每層的左右面積做加權平均
- **摘要合併（mean_hu）**：以 pixelcount 做加權平均

### 專案結構

```
totalseg-muscle-tool/
totalseg-muscle-tool/
├── START 啟動.bat                # Windows 雙擊啟動腳本
└── python/
    ├── gui_pyside.py     # 統一的 PySide6 視覺化介面 (包含單檔、批次、比較)
    ├── seg.py            # 分割核心演算法
    ├── draw.py           # PNG 疊圖繪製
    └── pyproject.toml    # 依賴套件清單 (uv)
```

### 測試

```bash
cd python
uv run python test_compare.py
```

測試項目：
- Dice 係數計算（4 個案例）
- 面積計算（4 個案例）
- 層數偵測（5 個案例）

所有測試通過表示核心邏輯運作正常。

### 常見問題

#### **工具 1（AI 分割）**
- **路徑含中文/特殊字元導致畫圖失敗**：`draw.py` 會檢查路徑是否為 ASCII。請將專案或 DICOM 移到純英文路徑。
- **第一次跑很慢**：TotalSegmentator 可能需要下載模型權重，且 CPU 推論會非常耗時。
- **GPU/CPU 判斷**：GUI 會顯示偵測到的裝置（`torch.cuda.is_available()`）。

#### **工具 2（批次處理）**
- **找不到 DICOM 資料夾**：檢查最大搜尋深度設定或資料夾結構。
- **部分案例失敗**：查看日誌檔案了解具體錯誤訊息。

#### **工具 3（手動 vs AI 比較）**
- **Dice 分數低於預期**：可能原因：(1) 手動標註與 AI 分割的層數不一致、(2) 分割範圍定義不同、(3) AI 分割品質較差。建議在 3D Slicer 中檢視重疊情況。
- **spacing 不一致警告**：當 spacing 差異超過 10% 時會顯示警告。程式會自動重採樣對齊，但仍建議確認兩個檔案是否來自同一個 DICOM series。
- **多層標註警告**：程式設計為只比較單層。如果手動標註包含多層，會自動選擇第一層。

### 注意事項

> 本專案屬研究/開發用途，請勿直接做臨床診斷依據。

### 授權

本專案開源供研究與教育用途使用。
