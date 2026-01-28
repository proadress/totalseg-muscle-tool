# segmentation_v0.8（Medical Image Segmentation Tool）

以 TotalSegmentator 為核心的醫學影像分割小工具：
- 讀取一個 DICOM 資料夾（CT series）。
- 執行指定的 TotalSegmentator task 產生分割 mask（`*.nii.gz`）。
- 產出 CSV：每個 slice 的面積（cm2）、每個 slice 的平均 HU，以及整體統計（pixelcount / volume / mean HU）。
- 可選：額外做脊椎（C/T/L）分割與輸出。
- 可選：輸出每張 slice 的 PNG overlay（把 mask 疊在原影像上，並加上 legend/脊椎標籤）。

> 注意：本專案屬研究/開發用途，請勿直接做臨床診斷依據。

---

## 專案結構

### 程式1：AI 肌肉分割工具
- `AI肌肉分割.bat`：一鍵安裝 + 啟動 GUI（Windows）。
- `python/pyproject.toml`：Python 依賴（用 `uv` 管理），Python 版本限制 `>=3.10,<3.11`。
- `python/gui_main.py`：Tkinter GUI，選 DICOM/輸出路徑、task、fast、spine、是否產 PNG。
- `python/seg.py`：主要分割流程（呼叫 TotalSegmentator + 匯出 CSV + 可選 spine + 可選自動 draw）。
- `python/draw.py`：把分割 mask 疊到影像上輸出 `png/`。

### 程式2：手動 vs AI 比較工具
- `手動vs AI比較.bat`：啟動比較工具 GUI（Windows）。
- `python/compare_gui.py`：比較工具核心邏輯 + GUI（選擇 AI 分割結果 + 手動標註 → 自動計算 Dice 係數與面積差異）。
- `python/test_compare.py`：單元測試（驗證 Dice 計算、面積計算、層數偵測的正確性）。

### 其他
- `SER00005/`、`test/`：範例 DICOM 資料（供測試）。
- `*_output/`：執行後輸出資料夾（例如 `SER00005_output/`）。

---

## 需求

- Windows 10/11（`start.bat` 以 Windows 為主；其他 OS 可用手動方式執行）。
- 網路連線（第一次安裝依賴與下載模型權重時需要）。
- 建議：NVIDIA GPU（有安裝驅動、CUDA 可用時會自動用 GPU；否則走 CPU 會較慢）。

---

## 程式1：一鍵安裝 + AI 分割 GUI（推薦）

1. 進入專案根目錄。
2. 執行 `AI肌肉分割.bat`（雙擊或用 PowerShell 執行）。
3. 腳本流程：
   - 切換到 `python/`
   - 檢查 `uv`，沒有就自動安裝（安裝完會提示你關閉視窗並再跑一次）
   - 建立虛擬環境 `python/.venv`（如不存在）
   - `uv sync` 安裝依賴（依 `python/pyproject.toml`）
   - 啟動 `python/gui_main.py`

## 程式2：手動 vs AI 比較工具

### 使用流程

1. **執行 AI 分割**（如果尚未執行）：
   - 雙擊 `AI肌肉分割.bat`
   - 選擇 DICOM 資料夾
   - 選擇 Task（例如 `tissue_types_mr`）
   - 等待分割完成（輸出：`skeletal_muscle.nii.gz`）

2. **在 3D Slicer 手動標註**：
   - 開啟 3D Slicer
   - Load DICOM（與步驟 1 相同的資料夾）
   - 進入 Segment Editor 模組
   - 選擇目標層（例如 L3 層）
   - 使用 Paint 工具手動畫肌肉輪廓
   - Segmentations → Export to file → 儲存為 `.seg.nrrd` 檔案

3. **執行比較**：
   - 雙擊 `手動vs AI比較.bat`
   - 選擇 AI 分割檔案（步驟 1 的輸出，例如 `skeletal_muscle.nii.gz`）
   - 選擇手動標註檔案（步驟 2 的輸出，例如 `manual_L3.seg.nrrd`）
   - 比較結果會自動顯示在視窗中：
     - 層數（Slice Number）
     - 手動面積 (cm²)
     - AI 面積 (cm²)
     - Dice 分數（0-1，數值越高表示相似度越高）
   - 可選擇性點擊「匯出 CSV」按鈕儲存結果

### 關鍵功能
- **自動比較**：選好兩個檔案後自動執行比較，無需按額外按鈕
- **即時顯示**：結果即時顯示在 GUI，方便快速切換不同手動標註進行比較
- **可選匯出**：只有在需要時才匯出 CSV，避免產生過多檔案

---

## 命令列用法（CLI）

在專案根目錄或 `python/` 皆可，以下以 `python/` 為例：

```powershell
cd python
uv sync
uv run seg.py --dicom ..\\SER00005 --task tissue_4_types --spine 0 --fast 0 --auto_draw 1 --erosion_iters 7
```

`seg.py` 參數（重點）：
- `--dicom`：DICOM 資料夾路徑
- `--out`：輸出根目錄（預設為 DICOM 資料夾的 parent）
- `--task`：TotalSegmentator task（GUI 下拉選單內也有）
- `--fast 1`：加速模式（較快但精度可能下降；某些 task 不支援）
- `--spine 1`：額外跑脊椎分割（會用 `total` task 的 `vertebrae_*` ROI 子集合；固定 fast）
- `--auto_draw 1`：分割完成後自動執行 `draw.py` 產 PNG overlay
- `--erosion_iters`：HU 計算用的侵蝕次數（預設 7；像素太少時會改成 3 或不侵蝕）

只畫 PNG overlay（不重跑分割）：

```powershell
cd python
uv run draw.py --dicom ..\\SER00005 --task tissue_4_types --fast 0 --spine 1 --erosion_iters 7
```

---

## 輸出說明

### 程式1：AI 分割輸出

以輸入 `SER00005/`、未指定 `--out` 為例，輸出會在 `SER00005` 同層建立 `SER00005_output/`：

- `SER00005_output/segmentation_<task>/`：每個結構一個 mask（`*.nii.gz`），並含 `statistics.json`
- `SER00005_output/mask_<task>.csv`：分析結果（分成 4 個區塊）
  - 區塊 1：每個 slice 的面積（cm2）
  - 區塊 2：每個 slice 的平均 HU（會先做 mask 侵蝕再取 HU；並把左右肌肉做面積加權合併）
  - 區塊 3：每個 slice 的 HU 標準差（同樣使用侵蝕後區域；左右肌肉面積加權合併）
  - 區塊 4：整體 summary（pixelcount / volume_cm3 / mean_hu；左右肌肉會合併）
- `SER00005_output/png/`：每張 slice 一張 overlay PNG（若有開啟輸出）

### 程式2：比較工具輸出

比較結果會即時顯示在 GUI 視窗中，包含：
- 層數（Slice Number）：手動標註的層數索引
- 手動面積 (cm²)：醫生手動標註的肌肉面積
- AI 面積 (cm²)：TotalSegmentator 在同一層的分割面積
- Dice 分數：兩個 mask 的相似度（公式：`2 * |A ∩ B| / (|A| + |B|)`）

可選擇性匯出為 CSV 檔案，格式如下：
```csv
slice_number, manual_area_cm2, ai_area_cm2, dice_score
45, 52.30, 48.70, 0.8900
```

---

## 計算邏輯摘要（給需要對數據負責的人）

- 面積（cm2）：每個 slice 的 mask 像素數 × `spacing_x × spacing_y / 100`
- 體積（cm3）：所有 mask 像素數 × `spacing_x × spacing_y × spacing_z / 1000`
- slice 平均 HU：對該 slice mask 做形態學侵蝕（預設 7 次，像素太少會降為 3 次或不侵蝕）後，取侵蝕後區域的 HU 平均
- slice HU 標準差：同上侵蝕流程，取侵蝕後區域的 HU 標準差
- 左右合併（HU）：以每個 slice 的左右面積做加權平均
- summary 合併（mean_hu）：以 pixelcount 做加權平均

---

## 常見問題

### 程式1（AI 分割）
- 路徑含中文/特殊字元導致畫圖失敗：`python/draw.py` 目前會檢查路徑是否為 ASCII；請把專案或 DICOM 移到純英文路徑後再跑。
- 第一次跑很慢：TotalSegmentator 可能需要下載模型權重，且 CPU 推論會非常耗時。
- GPU/CPU 判斷：GUI 會顯示偵測到的裝置（`torch.cuda.is_available()`）。

### 程式2（手動 vs AI 比較）
- **Dice 分數低於預期**：可能原因包括：(1) 手動標註與 AI 分割的層數不一致、(2) 分割範圍定義不同（如是否包含皮下脂肪）、(3) AI 分割品質較差。建議在 3D Slicer 中同時檢視兩個 mask 的重疊情況。
- **spacing 不一致警告**：當手動標註與 AI 結果的 spacing 差異超過 10% 時會顯示警告。程式會自動進行重採樣對齊，但仍建議確認兩個檔案是否來自同一個 DICOM series。
- **找不到手動標註**：請確認在 3D Slicer 匯出時選擇了正確的格式（Segmentation → Export to file → 格式選擇 `.seg.nrrd`）。
- **多層標註警告**：程式設計為只比較單層，如果手動標註包含多層，會自動選擇第一層並顯示警告訊息。

## 測試

執行單元測試以驗證比較工具的核心功能：

```powershell
cd python
uv run python test_compare.py
```

測試項目包含：
- Dice 係數計算正確性（4 個案例）
- 面積計算正確性（4 個案例）
- 層數偵測正確性（5 個案例）

所有測試通過表示核心邏輯運作正常。
