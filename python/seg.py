import argparse
import subprocess
from pathlib import Path
from totalsegmentator.python_api import totalsegmentator
import SimpleITK as sitk
import numpy as np
import csv
import os
import json
import cv2

VERTEBRAE_LABELS = (
    [f"vertebrae_C{i}" for i in range(1, 8)]
    + [f"vertebrae_T{i}" for i in range(1, 13)]
    + [f"vertebrae_L{i}" for i in range(1, 6)]
)


def calculate_slice_hu_with_erosion(slice_mask, slice_ct):
    """
    使用侵蝕 7 次計算 HU（與醫生測量最接近，誤差 1.08 HU）

    Args:
        slice_mask: 2D mask array
        slice_ct: 2D CT array (HU values)

    Returns:
        float: 平均 HU 值
    """
    if np.sum(slice_mask > 0) == 0:
        return 0.0

    original_pixels = np.sum(slice_mask > 0)

    # 步驟 1：侵蝕 7 次（去除邊緣約 4.6 mm）
    kernel = np.ones((3, 3), np.uint8)
    eroded_mask = cv2.erode(slice_mask.astype(np.uint8), kernel, iterations=7)

    eroded_pixels = np.sum(eroded_mask > 0)

    # 步驟 2：如果像素太少，減少侵蝕次數
    if eroded_pixels < 50 or eroded_pixels < original_pixels * 0.2:
        eroded_mask = cv2.erode(slice_mask.astype(np.uint8), kernel, iterations=3)
        eroded_pixels = np.sum(eroded_mask > 0)

    # 步驟 3：如果還是太少，不侵蝕
    if eroded_pixels < 20:
        eroded_mask = slice_mask

    hu_values = slice_ct[eroded_mask > 0]

    if len(hu_values) > 0:
        return float(np.mean(hu_values))
    else:
        return 0.0


def get_mask_area_volume_and_hu(nii_path, ct_arr, spacing, resampler):
    """
    計算每個 slice 的面積、總體積、以及每個 slice 的平均 HU

    Args:
        nii_path: mask 的路徑
        ct_arr: 原始 CT 影像的 numpy array（已經包含 HU 值）
        spacing: CT 影像的 spacing
        resampler: 重採樣器

    Returns:
        slice_area: 每個 slice 的面積 (cm²)
        total_volume: 總體積 (cm³)
        slice_mean_hu: 每個 slice 的平均 HU
    """
    mask_img = sitk.ReadImage(str(nii_path))
    mask_arr = sitk.GetArrayFromImage(resampler.Execute(mask_img))

    slice_area = (
        np.sum(mask_arr > 0, axis=(1, 2)) * spacing[0] * spacing[1] / 100
    )  # cm²
    total_volume = float(np.sum(mask_arr > 0) * np.prod(spacing) / 1000)  # cm³

    slice_mean_hu = []
    for i in range(mask_arr.shape[0]):
        slice_mask = mask_arr[i, :, :]
        slice_ct = ct_arr[i, :, :]

        mean_hu = calculate_slice_hu_with_erosion(slice_mask, slice_ct)
        slice_mean_hu.append(round(mean_hu, 2))

    slice_mean_hu = np.array(slice_mean_hu)

    return slice_area, total_volume, slice_mean_hu


def merge_bilateral_hu_data(area_results, hu_results):
    """
    ✅ 新增：合併左右肌肉的 HU（按面積加權平均）

    Args:
        area_results: dict，每個肌肉的面積數組
        hu_results: dict，每個肌肉的 HU 數組

    Returns:
        merged_hu: dict，合併後的 HU 數據
        merged_muscles: list，合併後的肌肉名稱列表
    """
    merged_hu = {}
    processed = set()

    for muscle in hu_results.keys():
        if muscle in processed:
            continue

        # 檢查是否為左側
        if muscle.endswith("_left"):
            base_name = muscle.replace("_left", "")
            right_name = f"{base_name}_right"

            # 如果有配對的右側
            if right_name in hu_results:
                left_area = area_results[muscle]
                right_area = area_results[right_name]
                left_hu = hu_results[muscle]
                right_hu = hu_results[right_name]

                # 按面積加權平均（逐個 slice）
                total_area = left_area + right_area

                # 修正後（不會有警告）
                weighted_hu = np.zeros_like(total_area)
                for i in range(len(total_area)):
                    if total_area[i] > 0:
                        weighted_hu[i] = (
                            left_area[i] * left_hu[i] + right_area[i] * right_hu[i]
                        ) / total_area[i]
                    else:
                        weighted_hu[i] = 0  # 該 slice 沒有肌肉
                merged_hu[base_name] = np.round(weighted_hu, 2)

                processed.add(muscle)
                processed.add(right_name)
            else:
                # 沒有配對，保留原名
                merged_hu[muscle] = hu_results[muscle]
                processed.add(muscle)

        elif muscle.endswith("_right"):
            # 右側單獨存在（沒有左側）
            base_name = muscle.replace("_right", "")
            left_name = f"{base_name}_left"

            if left_name not in hu_results:
                merged_hu[muscle] = hu_results[muscle]
                processed.add(muscle)

        else:
            # 不是左右肌肉
            merged_hu[muscle] = hu_results[muscle]
            processed.add(muscle)

    return merged_hu, list(merged_hu.keys())


def export_areas_and_volumes_to_csv(mask_dir, output_csv, dicom_dir):
    """
    匯出每個 slice 的面積和 HU 值到 CSV

    ✅ 修改：
    - 第一部分（面積）：保持左右分開
    - 第二部分（HU）：合併左右，按面積加權平均
    """
    print("Starting to export slice areas, HU values, and total volumes to CSV...")

    reader = sitk.ImageSeriesReader()
    files = reader.GetGDCMSeriesFileNames(str(dicom_dir))
    if not files:
        print(f"❌ [ERROR] No DICOM found in: {dicom_dir}")
        raise RuntimeError(f"No DICOM found in: {dicom_dir}")

    reader.SetFileNames(files)
    ct_image = sitk.Cast(reader.Execute(), sitk.sitkInt16)
    ct_arr = sitk.GetArrayFromImage(ct_image)
    spacing = ct_image.GetSpacing()

    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(ct_image)
    resampler.SetInterpolator(sitk.sitkNearestNeighbor)
    resampler.SetTransform(sitk.Transform())

    mask_files = [f for f in os.listdir(mask_dir) if f.endswith(".nii.gz")]
    muscles = [f.replace(".nii.gz", "") for f in mask_files]

    area_results = {}
    hu_results = {}

    for fname in mask_files:
        nii_path = Path(mask_dir) / fname
        slice_area, _, slice_mean_hu = get_mask_area_volume_and_hu(
            nii_path, ct_arr, spacing, resampler
        )

        muscle_name = fname.replace(".nii.gz", "")
        area_results[muscle_name] = np.round(slice_area, 2)
        hu_results[muscle_name] = slice_mean_hu

    # ✅ 合併左右的 HU 數據
    merged_hu, merged_muscles = merge_bilateral_hu_data(area_results, hu_results)

    max_slices = max(len(area) for area in area_results.values())

    with open(output_csv, "w", newline="") as csvfile:
        # === 第一部分：每個 slice 的面積（保持左右分開）===
        fieldnames = ["slicenumber"] + muscles
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i in range(max_slices, 0, -1):
            row = {"slicenumber": max_slices - i + 1}
            for muscle in muscles:
                if i <= len(area_results[muscle]):
                    val = area_results[muscle][i - 1]
                    row[muscle] = f"{val:.2f}"
                else:
                    row[muscle] = "0.00"
            writer.writerow(row)

        # === 第二部分：每個 slice 的平均 HU（合併左右）===
        writer = csv.writer(csvfile)
        writer.writerow([])  # 空行
        writer.writerow(["slicenumber"] + merged_muscles)  # header（合併後的名稱）

        for i in range(max_slices, 0, -1):
            row = [max_slices - i + 1]  # slice number
            for muscle in merged_muscles:
                if i <= len(merged_hu[muscle]):
                    val = merged_hu[muscle][i - 1]
                    row.append(f"{val:.2f}")
                else:
                    row.append("0.00")
            writer.writerow(row)

        # === 第三部分：總體積（暫時保持左右分開，稍後在 merge_statistics_to_csv 合併）===
        writer.writerow([])
        writer.writerow(["structure", "pixelcount", "volume_cm3"])

        for fname in mask_files:
            nii_path = Path(mask_dir) / fname
            pixels, volume, _ = get_mask_area_volume_and_hu(
                nii_path, ct_arr, spacing, resampler
            )
            writer.writerow(
                [
                    fname.replace(".nii.gz", ""),
                    int(np.sum(pixels)),
                    round(float(volume), 2),
                ]
            )

    print(f"CSV export completed. Output saved to: {output_csv}")


def merge_statistics_to_csv(mask_dir, output_csv):
    """
    ✅ 修改：讀取 statistics.json，合併左右肌肉的數據，加入器官級 mean_hu

    合併邏輯：
    - pixelcount: 相加
    - volume_cm3: 相加
    - mean_hu: 按 pixelcount 加權平均
    """
    stats_json_path = Path(mask_dir) / "statistics.json"

    if not stats_json_path.exists():
        print(f"⚠ Warning: statistics.json not found at {stats_json_path}")
        print(
            "  Skipping organ-level HU export. Make sure statistics=True in totalsegmentator."
        )
        return

    # 讀取 statistics.json
    with open(stats_json_path, "r") as f:
        stats_data = json.load(f)

    # 讀取現有 CSV
    with open(output_csv, "r", newline="") as f:
        existing_lines = f.readlines()

    # 找到 summary 表格的起始位置
    summary_start_idx = None
    for i, line in enumerate(existing_lines):
        if line.startswith("structure,pixelcount,volume_cm3"):
            summary_start_idx = i
            break

    if summary_start_idx is None:
        print("⚠ Warning: Could not find summary table in CSV")
        return

    # 讀取原本的 summary 內容
    summary_reader = csv.DictReader(existing_lines[summary_start_idx:])
    summary_rows = list(summary_reader)

    # ✅ 合併左右肌肉的數據
    merged_summary = {}
    processed = set()

    for row in summary_rows:
        muscle = row["structure"]

        if muscle in processed:
            continue

        if muscle.endswith("_left"):
            base_name = muscle.replace("_left", "")
            right_name = f"{base_name}_right"

            # 找右側數據
            right_row = next(
                (r for r in summary_rows if r["structure"] == right_name), None
            )

            if right_row:
                # 合併數據
                left_pixels = int(row["pixelcount"])
                right_pixels = int(right_row["pixelcount"])
                total_pixels = left_pixels + right_pixels

                left_volume = float(row["volume_cm3"])
                right_volume = float(right_row["volume_cm3"])

                # 加權平均 HU
                left_hu = stats_data.get(muscle, {}).get("intensity", 0)
                right_hu = stats_data.get(right_name, {}).get("intensity", 0)

                if total_pixels > 0:
                    weighted_hu = (
                        left_pixels * left_hu + right_pixels * right_hu
                    ) / total_pixels
                else:
                    weighted_hu = 0

                merged_summary[base_name] = {
                    "pixelcount": total_pixels,
                    "volume_cm3": left_volume + right_volume,
                    "mean_hu": weighted_hu,
                }

                processed.add(muscle)
                processed.add(right_name)
            else:
                # 沒有配對，保留原名
                merged_summary[muscle] = {
                    "pixelcount": int(row["pixelcount"]),
                    "volume_cm3": float(row["volume_cm3"]),
                    "mean_hu": stats_data.get(muscle, {}).get("intensity", 0),
                }
                processed.add(muscle)

        elif muscle.endswith("_right"):
            # 單獨右側
            base_name = muscle.replace("_right", "")
            left_name = f"{base_name}_left"

            if left_name not in [r["structure"] for r in summary_rows]:
                merged_summary[muscle] = {
                    "pixelcount": int(row["pixelcount"]),
                    "volume_cm3": float(row["volume_cm3"]),
                    "mean_hu": stats_data.get(muscle, {}).get("intensity", 0),
                }
                processed.add(muscle)

        else:
            # 不是左右
            merged_summary[muscle] = {
                "pixelcount": int(row["pixelcount"]),
                "volume_cm3": float(row["volume_cm3"]),
                "mean_hu": stats_data.get(muscle, {}).get("intensity", 0),
            }
            processed.add(muscle)

    # 重寫 CSV
    with open(output_csv, "w", newline="") as f:
        # 先寫回前面的部分（slice area + slice HU）
        f.writelines(existing_lines[:summary_start_idx])

        # 寫新的 header（加上 mean_hu）
        writer = csv.writer(f)
        writer.writerow(["structure", "pixelcount", "volume_cm3", "mean_hu"])

        # 寫入合併後的數據
        for structure, data in merged_summary.items():
            writer.writerow(
                [
                    structure,
                    data["pixelcount"],
                    round(data["volume_cm3"], 2),
                    round(data["mean_hu"], 2),
                ]
            )

    print(f"✓ Statistics merged. Bilateral muscles combined. Output: {output_csv}")


def run_task(dicom_path, out_dir, task, fast=False, roi_subset=None):
    """
    執行 TotalSegmentator 分割任務
    """
    params = dict(
        input=str(dicom_path),
        output=str(out_dir),
        task=task,
        fast=fast,
        statistics=True,
        verbose=True,
        statistics_exclude_masks_at_border=False,
    )

    if roi_subset:
        params["roi_subset"] = roi_subset

    totalsegmentator(**params)


def main():
    parser = argparse.ArgumentParser(
        description="Segmentation pipeline v1.1 - 自動合併左右肌肉"
    )
    parser.add_argument("--dicom", type=str, default="test", help="DICOM folder path")
    parser.add_argument("--out", type=str, default=None, help="Output folder")
    parser.add_argument(
        "--task", type=str, default="abdominal_muscles", help="Segmentation task name"
    )
    parser.add_argument(
        "--spine", type=int, default=0, help="Extra spine segmentation (1=yes, 0=no)"
    )
    parser.add_argument(
        "--fast", type=int, default=0, help="Fast/low precision mode (1=on, 0=off)"
    )
    parser.add_argument(
        "--auto_draw",
        type=int,
        default=0,
        help="Auto run draw after segment (1=yes, 0=no)",
    )

    args = parser.parse_args()

    if args.fast:
        print(
            "⚠ Note: Fast mode is enabled. Speed prioritized over accuracy. For preview only."
        )

    dicom_path = Path(args.dicom)
    output_base = (
        Path(args.out) if args.out else dicom_path.parent
    ) / f"{dicom_path.name}_output"
    output_base.mkdir(parents=True, exist_ok=True)

    seg_folder_name = f"segmentation_{args.task}" + ("_fast" if args.fast else "")
    seg_output = output_base / seg_folder_name
    seg_output.mkdir(exist_ok=True)

    print(f"Running segmentation task: {args.task}")
    run_task(dicom_path, seg_output, args.task, fast=bool(args.fast))

    csv_name = f"mask_{args.task}" + ("_fast" if args.fast else "") + ".csv"
    output_csv = output_base / csv_name

    export_areas_and_volumes_to_csv(seg_output, str(output_csv), dicom_path)
    merge_statistics_to_csv(seg_output, str(output_csv))

    if args.spine and args.task != "total":
        print("Running spine segmentation task: total")
        spine_folder_name = "segmentation_spine_fast"
        seg_spine_output = output_base / spine_folder_name
        seg_spine_output.mkdir(exist_ok=True)

        run_task(
            dicom_path,
            seg_spine_output,
            "total",
            fast=True,
            roi_subset=VERTEBRAE_LABELS,
        )

        spine_csv_name = "mask_spine_fast.csv"
        output_spine_csv = output_base / spine_csv_name

        export_areas_and_volumes_to_csv(
            seg_spine_output, str(output_spine_csv), dicom_path
        )
        merge_statistics_to_csv(seg_spine_output, str(output_spine_csv))

    if args.auto_draw:
        print("Segmentation completed. Running draw script automatically...")
        subprocess.run(
            [
                "uv",
                "run",
                "draw.py",
                "--dicom",
                str(args.dicom),
                "--out",
                str(args.out),
                "--task",
                str(args.task),
                "--spine",
                str(args.spine),
                "--fast",
                str(args.fast),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
