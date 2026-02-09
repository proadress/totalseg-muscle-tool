"""
批次處理工具 - 自動掃描並處理多個 DICOM 資料夾

使用方式：
1. 將所有要處理的 DICOM 資料夾整理到一個大資料夾內
2. 執行此腳本，選擇大資料夾
3. 自動掃描所有 DICOM 資料夾並逐一處理
4. 失敗的案例會自動跳過，並記錄在 log 檔案中
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import SimpleITK as sitk
import json


def is_valid_dicom_folder(folder_path):
    """
    檢查資料夾是否包含有效的 DICOM 檔案

    Args:
        folder_path: 資料夾路徑

    Returns:
        bool: 是否為有效的 DICOM 資料夾
    """
    try:
        reader = sitk.ImageSeriesReader()
        dicom_files = reader.GetGDCMSeriesFileNames(str(folder_path))
        return len(dicom_files) > 0
    except Exception:
        return False


def find_all_dicom_folders(root_path, max_depth=10):
    """
    遞迴掃描所有 DICOM 資料夾

    Args:
        root_path: 根目錄路徑
        max_depth: 最大搜尋深度

    Returns:
        list: 所有找到的 DICOM 資料夾路徑
    """
    root_path = Path(root_path)
    dicom_folders = []

    def scan_folder(current_path, depth):
        if depth > max_depth:
            return

        if not current_path.is_dir():
            return

        # 檢查當前資料夾是否為 DICOM 資料夾
        if is_valid_dicom_folder(current_path):
            dicom_folders.append(current_path)
            # 如果找到 DICOM 資料夾，不再往下搜尋子資料夾
            return

        # 繼續搜尋子資料夾
        try:
            for item in current_path.iterdir():
                if item.is_dir():
                    # 跳過輸出資料夾
                    if "_output" in item.name or item.name.startswith("."):
                        continue
                    scan_folder(item, depth + 1)
        except PermissionError:
            print(f"⚠ 權限不足，跳過: {current_path}")

    print(f"🔍 開始掃描資料夾: {root_path}")
    scan_folder(root_path, 0)
    print(f"✓ 掃描完成，找到 {len(dicom_folders)} 個 DICOM 資料夾")

    return dicom_folders


def process_single_dicom(dicom_path, output_base, task, spine, fast, auto_draw, erosion_iters):
    """
    處理單個 DICOM 資料夾

    Args:
        dicom_path: DICOM 資料夾路徑
        output_base: 輸出根目錄
        task: 分割任務名稱
        spine: 是否額外做脊椎分割
        fast: 是否使用快速模式
        auto_draw: 是否自動產生 PNG overlay
        erosion_iters: 侵蝕次數

    Returns:
        dict: 處理結果 {"success": bool, "message": str}
    """
    try:
        cmd = [
            "uv",
            "run",
            "seg.py",
            "--dicom",
            str(dicom_path),
            "--out",
            str(output_base),
            "--task",
            task,
            "--spine",
            str(spine),
            "--fast",
            str(fast),
            "--auto_draw",
            str(auto_draw),
            "--erosion_iters",
            str(erosion_iters),
        ]

        print(f"\n{'='*80}")
        print(f"處理中: {dicom_path.name}")
        print(f"{'='*80}")

        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )

        return {
            "success": True,
            "message": "處理成功",
            "stdout": result.stdout,
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"處理失敗: {e}",
            "stdout": e.stdout if e.stdout else "",
            "stderr": e.stderr if e.stderr else "",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"未預期的錯誤: {e}",
        }


def batch_process(
    root_folder,
    output_base=None,
    task="abdominal_muscles",
    spine=0,
    fast=0,
    auto_draw=1,
    erosion_iters=7,
    max_depth=10,
):
    """
    批次處理主函數

    Args:
        root_folder: 包含多個 DICOM 資料夾的根目錄
        output_base: 輸出根目錄（若為 None，則使用各 DICOM 資料夾的 parent）
        task: 分割任務名稱
        spine: 是否額外做脊椎分割 (0 或 1)
        fast: 是否使用快速模式 (0 或 1)
        auto_draw: 是否自動產生 PNG overlay (0 或 1)
        erosion_iters: 侵蝕次數
        max_depth: 最大搜尋深度
    """
    root_folder = Path(root_folder)

    if not root_folder.exists():
        print(f"❌ 錯誤: 資料夾不存在: {root_folder}")
        return

    # 掃描所有 DICOM 資料夾
    dicom_folders = find_all_dicom_folders(root_folder, max_depth)

    if not dicom_folders:
        print("❌ 未找到任何 DICOM 資料夾")
        return

    # 建立日誌
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = root_folder / f"batch_processing_log_{timestamp}.txt"
    results_file = root_folder / f"batch_processing_results_{timestamp}.json"

    print(f"\n📝 日誌檔案: {log_file}")
    print(f"📊 結果檔案: {results_file}")
    print(f"\n開始批次處理 {len(dicom_folders)} 個資料夾...")

    # 處理結果統計
    results = {
        "total": len(dicom_folders),
        "success": 0,
        "failed": 0,
        "details": [],
    }

    with open(log_file, "w", encoding="utf-8") as log:
        log.write(f"批次處理日誌 - {datetime.now()}\n")
        log.write(f"根目錄: {root_folder}\n")
        log.write(f"任務: {task}\n")
        log.write(f"脊椎分割: {'是' if spine else '否'}\n")
        log.write(f"快速模式: {'是' if fast else '否'}\n")
        log.write(f"自動產圖: {'是' if auto_draw else '否'}\n")
        log.write(f"侵蝕次數: {erosion_iters}\n")
        log.write(f"找到 {len(dicom_folders)} 個 DICOM 資料夾\n")
        log.write("="*80 + "\n\n")

        for i, dicom_path in enumerate(dicom_folders, 1):
            print(f"\n[{i}/{len(dicom_folders)}] {dicom_path.name}")
            log.write(f"[{i}/{len(dicom_folders)}] {dicom_path.name}\n")
            log.write(f"路徑: {dicom_path}\n")

            # 決定輸出路徑
            if output_base:
                out_dir = Path(output_base)
            else:
                out_dir = dicom_path.parent

            # 處理單個資料夾
            result = process_single_dicom(
                dicom_path, out_dir, task, spine, fast, auto_draw, erosion_iters
            )

            # 記錄結果
            if result["success"]:
                results["success"] += 1
                print(f"✓ 成功")
                log.write(f"狀態: 成功\n")
            else:
                results["failed"] += 1
                print(f"✗ 失敗: {result['message']}")
                log.write(f"狀態: 失敗\n")
                log.write(f"錯誤訊息: {result['message']}\n")
                if "stderr" in result:
                    log.write(f"錯誤輸出:\n{result['stderr']}\n")

            results["details"].append({
                "folder": str(dicom_path),
                "name": dicom_path.name,
                "success": result["success"],
                "message": result["message"],
            })

            log.write("-"*80 + "\n\n")
            log.flush()

    # 儲存 JSON 結果
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 顯示總結
    print(f"\n{'='*80}")
    print(f"批次處理完成！")
    print(f"{'='*80}")
    print(f"總共: {results['total']} 個資料夾")
    print(f"成功: {results['success']} 個 ({results['success']/results['total']*100:.1f}%)")
    print(f"失敗: {results['failed']} 個 ({results['failed']/results['total']*100:.1f}%)")
    print(f"\n詳細日誌: {log_file}")
    print(f"結果檔案: {results_file}")

    if results["failed"] > 0:
        print(f"\n失敗的資料夾:")
        for detail in results["details"]:
            if not detail["success"]:
                print(f"  - {detail['name']}: {detail['message']}")


def main():
    parser = argparse.ArgumentParser(
        description="批次處理工具 - 自動掃描並處理多個 DICOM 資料夾"
    )
    parser.add_argument(
        "--root",
        type=str,
        required=True,
        help="包含多個 DICOM 資料夾的根目錄",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="輸出根目錄（若不指定，則使用各 DICOM 資料夾的 parent）",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="abdominal_muscles",
        help="分割任務名稱（預設: abdominal_muscles）",
    )
    parser.add_argument(
        "--spine",
        type=int,
        default=0,
        help="是否額外做脊椎分割 (1=是, 0=否，預設: 0)",
    )
    parser.add_argument(
        "--fast",
        type=int,
        default=0,
        help="是否使用快速模式 (1=是, 0=否，預設: 0)",
    )
    parser.add_argument(
        "--auto_draw",
        type=int,
        default=1,
        help="是否自動產生 PNG overlay (1=是, 0=否，預設: 1)",
    )
    parser.add_argument(
        "--erosion_iters",
        type=int,
        default=7,
        help="侵蝕次數（預設: 7）",
    )
    parser.add_argument(
        "--max_depth",
        type=int,
        default=10,
        help="最大搜尋深度（預設: 10）",
    )

    args = parser.parse_args()

    batch_process(
        root_folder=args.root,
        output_base=args.out,
        task=args.task,
        spine=args.spine,
        fast=args.fast,
        auto_draw=args.auto_draw,
        erosion_iters=args.erosion_iters,
        max_depth=args.max_depth,
    )


if __name__ == "__main__":
    main()
