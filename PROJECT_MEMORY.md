# Project Memory: TotalSeg Muscle Tool (v1.0.0)

## 📌 專案概述 (Project Overview)
本專案為一套專為醫學影像分析設計的工具，基於 TotalSegmentator 預訓練模型，提供 CT/MRI 影像的肌肉分割與統計功能。目前已達成 v1.0.0 階段，擁有統一的 PySide6 圖形介面。

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

- 已移除過時的單獨介面檔與冗餘腳本 (`gui_main.py`, `batch_gui.py`, `compare_gui.py`, `start.py`, `batch_seg.py`)。
- **全面移除 legacy 啟動腳本**: 刪除了 `START 啟動.bat`。
- **全面移除 Mock 邏輯**: 刪除了 `mock_seg.py` 與所有 `mock_*` 資料集，確保程式在任何平台皆執行真實後端。
- 專案根目錄已完成隱藏檔與開發測試資料的 `.gitignore` 配置。

## 🚀 未來展望 (Next Steps)
- **Windows 打包**: 下一階段可考慮使用 PyInstaller 將 `gui_pyside.py` 打包成獨立的 `.exe` 以方便在無 Python 環境的電腦執行。
- **自動更新**: 實作檢查 GitHub Release 並自動同步最新版的功能。
