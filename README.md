# Medical Image Segmentation Tool (segmentation_v0.8)

[English](#english) | [中文](#中文)

---

## English

A medical image segmentation tool based on TotalSegmentator for CT image muscle segmentation analysis.

### Features

#### **Tool 1: AI Muscle Segmentation (Single File)**
- Read DICOM folder (CT series)
- Execute TotalSegmentator task to generate segmentation masks (`*.nii.gz`)
- Export CSV: area per slice (cm²), average HU per slice, overall statistics
- Optional: Spine (C/T/L) segmentation and output
- Optional: PNG overlays for each slice

#### **Tool 2: Batch AI Muscle Segmentation**
- Automatically scan and process multiple DICOM folders
- Recursive folder search (configurable depth)
- Fault tolerance: Skip failed cases and continue
- Detailed logs and statistics

#### **Tool 3: Manual vs AI Comparison**
- Compare AI segmentation with manual annotations
- Calculate Dice coefficient (similarity)
- Calculate area differences
- Optional CSV export

### Quick Start

#### **Windows**
```bash
# Double-click to launch
launcher.bat
```

#### **Mac/Linux**
```bash
# Double-click or run in terminal
./launcher.sh
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

# Single file segmentation
uv run seg.py --dicom ../SER00005 --task tissue_4_types --spine 0 --fast 0 --auto_draw 1 --erosion_iters 7

# Batch processing
uv run batch_seg.py --root "path/to/root/folder" --task tissue_4_types

# Draw overlays only (without re-running segmentation)
uv run draw.py --dicom ../SER00005 --task tissue_4_types --fast 0 --spine 1 --erosion_iters 7
```

### Key Parameters

- `--dicom`: DICOM folder path
- `--out`: Output root directory (default: DICOM folder's parent)
- `--task`: TotalSegmentator task
- `--fast 1`: Fast mode (faster but may reduce accuracy)
- `--spine 1`: Additional spine segmentation
- `--auto_draw 1`: Auto-generate PNG overlays after segmentation
- `--erosion_iters`: Erosion iterations for HU calculation (default: 7)

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
├── launcher.bat          # Windows launcher
├── launcher.sh           # Mac/Linux launcher
├── launcher.py           # GUI launcher core
└── python/
    ├── gui_main.py       # Single file segmentation GUI
    ├── batch_gui.py      # Batch processing GUI
    ├── compare_gui.py    # Comparison tool GUI
    ├── seg.py            # Segmentation core
    ├── batch_seg.py      # Batch processing core
    ├── draw.py           # Visualization
    └── pyproject.toml    # Dependencies
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

#### **工具 1：AI 肌肉分割（單檔處理）**
- 讀取 DICOM 資料夾（CT series）
- 執行 TotalSegmentator 任務產生分割遮罩（`*.nii.gz`）
- 匯出 CSV：每層面積（cm²）、每層平均 HU、整體統計
- 可選：脊椎（C/T/L）分割與輸出
- 可選：每層 PNG 疊圖

#### **工具 2：批次 AI 肌肉分割**
- 自動掃描並處理多個 DICOM 資料夾
- 遞迴資料夾搜尋（可調整深度）
- 容錯機制：失敗案例自動跳過並繼續
- 詳細日誌與統計

#### **工具 3：手動 vs AI 比較**
- 比較 AI 分割與手動標註
- 計算 Dice 係數（相似度）
- 計算面積差異
- 可選擇性匯出 CSV

### 快速開始

#### **Windows**
```bash
# 雙擊執行
launcher.bat
```

#### **Mac/Linux**
```bash
# 雙擊或在終端機執行
./launcher.sh
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

# 單檔分割
uv run seg.py --dicom ../SER00005 --task tissue_4_types --spine 0 --fast 0 --auto_draw 1 --erosion_iters 7

# 批次處理
uv run batch_seg.py --root "路徑/到/根目錄" --task tissue_4_types

# 只畫疊圖（不重跑分割）
uv run draw.py --dicom ../SER00005 --task tissue_4_types --fast 0 --spine 1 --erosion_iters 7
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
├── launcher.bat          # Windows 啟動器
├── launcher.sh           # Mac/Linux 啟動器
├── launcher.py           # GUI 啟動器核心
└── python/
    ├── gui_main.py       # 單檔分割 GUI
    ├── batch_gui.py      # 批次處理 GUI
    ├── compare_gui.py    # 比較工具 GUI
    ├── seg.py            # 分割核心
    ├── batch_seg.py      # 批次處理核心
    ├── draw.py           # 視覺化
    └── pyproject.toml    # 依賴設定
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
