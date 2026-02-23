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
import shutil
import tempfile
import time
from datetime import datetime

VERTEBRAE_LABELS = (
    [f"vertebrae_C{i}" for i in range(1, 8)]
    + [f"vertebrae_T{i}" for i in range(1, 13)]
    + [f"vertebrae_L{i}" for i in range(1, 6)]
)


def log_info(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def _is_ascii_path(path):
    return str(path).isascii()


def read_image_with_ascii_fallback(image_path):
    """
    Read image with a fallback for Windows non-ASCII paths.
    Some SimpleITK builds fail to open unicode file paths on Windows.
    """
    image_path = Path(image_path)
    try:
        return sitk.ReadImage(str(image_path))
    except RuntimeError as first_error:
        if _is_ascii_path(image_path):
            log_info(
                f"[ERROR] Failed to read mask: {image_path} (ASCII path, no fallback)."
            )
            raise
        exists = image_path.exists()
        size = image_path.stat().st_size if exists else -1
        log_info(
            f"[WARN] ReadImage failed on non-ASCII path. "
            f"path={image_path} exists={exists} size={size} bytes. "
            "Trying ASCII temp fallback..."
        )
        with tempfile.TemporaryDirectory(prefix="sitk_ascii_") as tmp_dir:
            tmp_path = Path(tmp_dir) / image_path.name
            shutil.copy2(image_path, tmp_path)
            try:
                return sitk.ReadImage(str(tmp_path))
            except RuntimeError:
                log_info(f"[ERROR] Fallback read also failed for: {image_path}")
                raise first_error


def calculate_slice_hu_with_erosion(slice_mask, slice_ct, erosion_iters=7):
    """
    使用侵蝕 7 次計算 HU（與醫生測量最接近，誤差 1.08 HU）

    Args:
        slice_mask: 2D mask array
        slice_ct: 2D CT array (HU values)

    Returns:
        float: 平均 HU 值
    """
    if np.sum(slice_mask > 0) == 0:
        return 0.0, 0.0

    original_pixels = np.sum(slice_mask > 0)

    # 步驟 1：侵蝕 N 次（預設 7；去除邊緣約 4.6 mm）
    kernel = np.ones((3, 3), np.uint8)
    erosion_iters = max(int(erosion_iters), 0)
    if erosion_iters > 0:
        eroded_mask = cv2.erode(
            slice_mask.astype(np.uint8), kernel, iterations=erosion_iters
        )
    else:
        eroded_mask = slice_mask.astype(np.uint8)

    eroded_pixels = np.sum(eroded_mask > 0)

    # 步驟 2：如果像素太少，減少侵蝕次數
    if erosion_iters > 3 and (
        eroded_pixels < 50 or eroded_pixels < original_pixels * 0.2
    ):
        eroded_mask = cv2.erode(slice_mask.astype(np.uint8), kernel, iterations=3)
        eroded_pixels = np.sum(eroded_mask > 0)

    # 步驟 3：如果還是太少，不侵蝕
    if eroded_pixels < 20:
        eroded_mask = slice_mask.astype(np.uint8)

    hu_values = slice_ct[eroded_mask > 0]

    if len(hu_values) > 0:
        return float(np.mean(hu_values)), float(np.std(hu_values))
    else:
        return 0.0, 0.0


def get_mask_area_volume_and_hu(nii_path, ct_arr, spacing, resampler, erosion_iters=7):
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
        slice_std_hu: 每個 slice 的 HU 標準差
        total_pixels: mask 的總像素數
    """
    mask_img = read_image_with_ascii_fallback(nii_path)
    mask_arr = sitk.GetArrayFromImage(resampler.Execute(mask_img))

    slice_area = (
        np.sum(mask_arr > 0, axis=(1, 2)) * spacing[0] * spacing[1] / 100
    )  # cm²
    total_pixels = int(np.sum(mask_arr > 0))
    total_volume = float(total_pixels * np.prod(spacing) / 1000)  # cm³

    slice_mean_hu = []
    slice_std_hu = []
    for i in range(mask_arr.shape[0]):
        slice_mask = mask_arr[i, :, :]
        slice_ct = ct_arr[i, :, :]

        mean_hu, std_hu = calculate_slice_hu_with_erosion(
            slice_mask, slice_ct, erosion_iters
        )
        slice_mean_hu.append(round(mean_hu, 2))
        slice_std_hu.append(round(std_hu, 2))

    slice_mean_hu = np.array(slice_mean_hu)
    slice_std_hu = np.array(slice_std_hu)

    return slice_area, total_volume, slice_mean_hu, slice_std_hu, total_pixels


def merge_bilateral_hu_data(area_results, hu_results):
    """
    # 新增：合併左右肌肉的 HU（按面積加權平均）

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


def merge_bilateral_std_data(area_results, hu_results, std_results):
    """
    合併左右肌肉的 HU 標準差（按面積加權）
    """
    merged_std = {}
    processed = set()

    for muscle in std_results.keys():
        if muscle in processed:
            continue

        if muscle.endswith("_left"):
            base_name = muscle.replace("_left", "")
            right_name = f"{base_name}_right"

            if right_name in std_results:
                left_area = area_results[muscle]
                right_area = area_results[right_name]
                left_mean = hu_results[muscle]
                right_mean = hu_results[right_name]
                left_std = std_results[muscle]
                right_std = std_results[right_name]

                total_area = left_area + right_area
                merged = np.zeros_like(total_area)

                for i in range(len(total_area)):
                    if total_area[i] > 0:
                        mu = (
                            left_area[i] * left_mean[i] + right_area[i] * right_mean[i]
                        ) / total_area[i]
                        var = (
                            left_area[i]
                            * (left_std[i] ** 2 + (left_mean[i] - mu) ** 2)
                            + right_area[i]
                            * (right_std[i] ** 2 + (right_mean[i] - mu) ** 2)
                        ) / total_area[i]
                        merged[i] = np.sqrt(var)
                    else:
                        merged[i] = 0

                merged_std[base_name] = np.round(merged, 2)
                processed.add(muscle)
                processed.add(right_name)
            else:
                merged_std[muscle] = std_results[muscle]
                processed.add(muscle)

        elif muscle.endswith("_right"):
            base_name = muscle.replace("_right", "")
            left_name = f"{base_name}_left"
            if left_name not in std_results:
                merged_std[muscle] = std_results[muscle]
                processed.add(muscle)
        else:
            merged_std[muscle] = std_results[muscle]
            processed.add(muscle)

    return merged_std, list(merged_std.keys())


def export_areas_and_volumes_to_csv(mask_dir, output_csv, dicom_dir, erosion_iters=7):
    """
    # 修改：
    - 第一部分（面積）：保持左右分開
    - 第二部分（HU）：合併左右，按面積加權平均
    - 第三部分（HU std）：合併左右，按面積加權
    """
    t0 = time.perf_counter()
    log_info(
        "Stage: CSV export started "
        f"(mask_dir={mask_dir}, output_csv={output_csv}, erosion_iters={erosion_iters})"
    )

    reader = sitk.ImageSeriesReader()
    files = reader.GetGDCMSeriesFileNames(str(dicom_dir))
    if not files:
        log_info(f"[ERROR] No DICOM found in: {dicom_dir}")
        raise RuntimeError(f"No DICOM found in: {dicom_dir}")
    log_info(f"DICOM slices discovered: {len(files)} from {dicom_dir}")

    reader.SetFileNames(files)
    ct_image = sitk.Cast(reader.Execute(), sitk.sitkInt16)
    ct_arr = sitk.GetArrayFromImage(ct_image)
    spacing = ct_image.GetSpacing()

    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(ct_image)
    resampler.SetInterpolator(sitk.sitkNearestNeighbor)
    resampler.SetTransform(sitk.Transform())

    mask_files = [f for f in os.listdir(mask_dir) if f.endswith(".nii.gz")]
    if not mask_files:
        raise RuntimeError(f"No mask .nii.gz files found in: {mask_dir}")
    log_info(f"Masks discovered for CSV export: {len(mask_files)}")
    muscles = [f.replace(".nii.gz", "") for f in mask_files]

    area_results = {}
    hu_results = {}
    hu_std_results = {}

    for idx, fname in enumerate(mask_files, 1):
        nii_path = Path(mask_dir) / fname
        log_info(f"Processing mask [{idx}/{len(mask_files)}]: {nii_path}")
        slice_area, _, slice_mean_hu, slice_std_hu, _ = get_mask_area_volume_and_hu(
            nii_path, ct_arr, spacing, resampler, erosion_iters
        )

        muscle_name = fname.replace(".nii.gz", "")
        area_results[muscle_name] = np.round(slice_area, 2)
        hu_results[muscle_name] = slice_mean_hu
        hu_std_results[muscle_name] = slice_std_hu

    # 合併左右的 HU 數據
    merged_hu, merged_muscles = merge_bilateral_hu_data(area_results, hu_results)
    merged_std, merged_std_muscles = merge_bilateral_std_data(
        area_results, hu_results, hu_std_results
    )

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

        # === 第三部分：每個 slice 的 HU 標準差（合併左右）===
        writer.writerow([])
        writer.writerow(["slicenumber"] + merged_std_muscles)

        for i in range(max_slices, 0, -1):
            row = [max_slices - i + 1]
            for muscle in merged_std_muscles:
                if i <= len(merged_std[muscle]):
                    val = merged_std[muscle][i - 1]
                    row.append(f"{val:.2f}")
                else:
                    row.append("0.00")
            writer.writerow(row)

        # === 第四部分：總體積（暫時保持左右分開，稍後在 merge_statistics_to_csv 合併）===
        writer.writerow([])
        writer.writerow(["structure", "pixelcount", "volume_cm3"])

        for idx, fname in enumerate(mask_files, 1):
            nii_path = Path(mask_dir) / fname
            log_info(
                f"Computing summary volume [{idx}/{len(mask_files)}]: {nii_path.name}"
            )
            _, volume, _, _, total_pixels = get_mask_area_volume_and_hu(
                nii_path, ct_arr, spacing, resampler, erosion_iters
            )
            writer.writerow(
                [
                    fname.replace(".nii.gz", ""),
                    total_pixels,
                    round(float(volume), 2),
                ]
            )

    log_info(
        f"Stage: CSV export completed in {time.perf_counter()-t0:.2f}s. "
        f"Output saved to: {output_csv}"
    )


def merge_statistics_to_csv(mask_dir, output_csv):
    """
    # 修改：讀取 statistics.json，合併左右肌肉的數據，加入器官級 mean_hu

    合併邏輯：
    - pixelcount: 相加
    - volume_cm3: 相加
    - mean_hu: 按 pixelcount 加權平均
    """
    t0 = time.perf_counter()
    stats_json_path = Path(mask_dir) / "statistics.json"
    log_info(
        "Stage: merge statistics started "
        f"(mask_dir={mask_dir}, output_csv={output_csv})"
    )

    if not stats_json_path.exists():
        log_info(f"[WARN] statistics.json not found at {stats_json_path}")
        log_info(
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
        log_info("[WARN] Could not find summary table in CSV; skip merge.")
        return

    # 讀取原本的 summary 內容
    summary_reader = csv.DictReader(existing_lines[summary_start_idx:])
    summary_rows = list(summary_reader)

    # 合併左右肌肉的數據
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

    log_info(
        f"Stage: merge statistics completed in {time.perf_counter()-t0:.2f}s. "
        f"Output: {output_csv}"
    )


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

    t0 = time.perf_counter()
    log_info(
        "Stage: totalsegmentator started "
        f"(task={task}, fast={fast}, out_dir={out_dir}, roi_subset={'yes' if roi_subset else 'no'})"
    )
    totalsegmentator(**params)
    log_info(
        f"Stage: totalsegmentator completed in {time.perf_counter()-t0:.2f}s "
        f"(task={task}, out_dir={out_dir})"
    )


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
    parser.add_argument(
        "--erosion_iters",
        type=int,
        default=7,
        help="Erosion iterations for HU calculation (default: 7)",
    )

    args = parser.parse_args()
    pipeline_t0 = time.perf_counter()

    if args.fast:
        print(
            "Note: Fast mode is enabled. Speed prioritized over accuracy. For preview only."
        )

    dicom_path = Path(args.dicom)
    output_base = (
        Path(args.out) if args.out else dicom_path.parent
    ) / f"{dicom_path.name}_output"
    output_base.mkdir(parents=True, exist_ok=True)
    log_info(
        "Pipeline started "
        f"(dicom={dicom_path}, output_base={output_base}, task={args.task}, "
        f"spine={args.spine}, fast={args.fast}, auto_draw={args.auto_draw}, "
        f"erosion_iters={args.erosion_iters})"
    )

    seg_folder_name = f"segmentation_{args.task}" + ("_fast" if args.fast else "")
    seg_output = output_base / seg_folder_name
    seg_output.mkdir(exist_ok=True)
    log_info(f"Primary segmentation output dir: {seg_output}")

    log_info(f"Running segmentation task: {args.task}")
    run_task(dicom_path, seg_output, args.task, fast=bool(args.fast))

    csv_name = f"mask_{args.task}" + ("_fast" if args.fast else "") + ".csv"
    output_csv = output_base / csv_name

    export_areas_and_volumes_to_csv(
        seg_output, str(output_csv), dicom_path, erosion_iters=args.erosion_iters
    )
    merge_statistics_to_csv(seg_output, str(output_csv))

    if args.spine and args.task != "total":
        log_info("Running spine segmentation task: total")
        spine_folder_name = "segmentation_spine_fast"
        seg_spine_output = output_base / spine_folder_name
        seg_spine_output.mkdir(exist_ok=True)
        log_info(f"Spine segmentation output dir: {seg_spine_output}")

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
            seg_spine_output,
            str(output_spine_csv),
            dicom_path,
            erosion_iters=args.erosion_iters,
        )
        merge_statistics_to_csv(seg_spine_output, str(output_spine_csv))

    if args.auto_draw:
        draw_t0 = time.perf_counter()
        log_info("Stage: auto_draw started")
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
                "--erosion_iters",
                str(args.erosion_iters),
            ],
            check=True,
        )
        log_info(f"Stage: auto_draw completed in {time.perf_counter()-draw_t0:.2f}s")

    log_info(f"Pipeline completed in {time.perf_counter()-pipeline_t0:.2f}s")


if __name__ == "__main__":
    main()
