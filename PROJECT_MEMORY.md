# Project Memory: TotalSeg Muscle Tool (v0.0.1)

## 📌 專案概述 (Project Overview)
本專案為一套專為醫學影像分析設計的工具，基於 TotalSegmentator 預訓練模型，提供 CT/MRI 影像的肌肉分割與統計功能。目前已穩定至 v0.0.1 階段，採用輕量、免安裝、不依賴系統權限的 `.bat` 與 `.zip` 部署架構。

## 🛠️ 技術架構 (Technical Stack)
- **核心引擎**: `seg.py` (呼叫 TotalSegmentator API)
- **視覺化**: `draw.py` (產生 PNG 疊加圖)
- **圖形介面**: `gui_pyside.py` (PySide6, 整合單次/批次/比對功能)
- **環境管理**: `uv` (管理 Python 依賴與獨立環境)

## ✨ 重要功能紀錄 (Major Features)
- **雙模態支援**: 支援 CT 與 MRI (自動切換至 `total_mr`)。
- **局部體積計算**: 可指定切片範圍 (`--slice_start`, `--slice_end`)。
- **智慧路徑掃描**: 遞迴識別嵌套目錄與無副檔名 DICOM。
- **專家級診斷系統**: UI 內建解決方案引擎，將技術報錯轉譯為醫學建議。
- **全中文化**: 介面完成台灣繁體用語優化。

- 已移除過時的單獨介面檔與冗餘腳本 (`gui_main.py`, `batch_gui.py`, `compare_gui.py`, `start.py`, `batch_seg.py`, `test_compare.py`)。
- **全面移除 EXE 打包架構與 CI/CD**: 為了適應醫院高資安環境 (繞過 SmartScreen 警告與防毒軟體誤判)，我們捨棄了 GitHub Actions 的 `.exe` 打包路徑，回歸最原始但最穩定的原始碼 `Zip + START 啟動.bat`。

## 🚀 部署與更新策略 (Deployment Strategy)
- **隨放即用 (Drop Anywhere)**: 利用 Windows 批次檔的彈性，資料夾解壓縮在哪裡都能跑，**完全免疫中文路徑導致的 PyTorch 報錯**。
- **快取秒開 (Cache Advantage)**: 利用 `uv` 全域快取，即使未來醫生刪除舊資料夾解壓縮新版，也能 1 秒內重建環境，不需重新下載數 GB 模型。
