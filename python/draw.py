import argparse
import sys
from pathlib import Path
import numpy as np
import SimpleITK as sitk
from PIL import Image, ImageDraw, ImageFont
import colorsys


def validate_path_ascii(path: Path):
    try:
        _ = str(path).encode("ascii")
    except Exception:
        print(
            f"❌ Path contains non-ASCII characters: {path}\n"
            "Please move to a path with only ASCII characters and retry."
        )
        sys.exit(1)


def get_base_name(name: str):
    base = name.replace(".nii.gz", "").replace(".nii", "")
    for suffix in ["_left", "_right"]:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base


def generate_color_palette(n: int):
    colors = []
    for i in range(n):
        h, s, v = (i / max(1, n)) % 1.0, 0.8, 0.9
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        colors.append((int(r * 255), int(g * 255), int(b * 255)))
    return colors


def draw_legend(image, slice_labels, color_map):
    if not slice_labels:
        return

    font_size = 14
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(image)
    slice_labels = list(dict.fromkeys(slice_labels))  # unique

    padding, swatch, row_height = 8, 10, 14
    usable_h = max(1, image.height - 2 * padding)
    max_rows = max(1, usable_h // row_height)
    cols = max(1, (len(slice_labels) + max_rows - 1) // max_rows)
    col_width = min(160, max(80, (image.width - 2 * padding) // cols))

    for idx, name in enumerate(slice_labels):
        x0 = padding + (idx // max_rows) * col_width
        y0 = padding + (idx % max_rows) * row_height
        color = color_map.get(name, (255, 255, 255))
        draw.rectangle([x0, y0, x0 + swatch, y0 + swatch], fill=color + (255,))
        tx, ty = x0 + swatch + 3, y0 - 1
        draw.text((tx + 1, ty + 1), name, fill=(0, 0, 0, 230), font=font)
        draw.text((tx, ty), name, fill=(255, 255, 255, 255), font=font)


def discover_mask_files(
    dicom_dir: Path, masks_dir: Path = None, task_name=None, fast=False
):
    """
    原始邏輯：如果有傳 masks_dir 就用，否則自己算
    """
    mask_files = []

    # 優先使用傳入的 masks_dir
    if masks_dir and masks_dir.exists():
        mask_files.extend(
            sorted([*masks_dir.glob("*.nii"), *masks_dir.glob("*.nii.gz")])
        )
        return mask_files

    # Fallback: 自己算（舊邏輯）
    seg_dir_name = f"segmentation_{task_name}" + ("_fast" if fast else "")
    seg_dir = dicom_dir.parent / f"{dicom_dir.name}_output" / seg_dir_name

    if seg_dir.exists():
        mask_files.extend(sorted([*seg_dir.glob("*.nii"), *seg_dir.glob("*.nii.gz")]))

    return mask_files


def load_masks(mask_files, reference):
    masks = []
    if not mask_files:
        print("❌ [ERROR] No mask files found!")
        raise RuntimeError("No mask files found!")

    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(reference)
    resampler.SetInterpolator(sitk.sitkNearestNeighbor)
    resampler.SetTransform(sitk.Transform())

    for mf in mask_files:
        try:
            mask_img = sitk.ReadImage(str(mf))
            mask_arr = sitk.GetArrayFromImage(resampler.Execute(mask_img))
            masks.append((get_base_name(mf.stem), mask_arr))
        except Exception as err:
            print(f"❌ [ERROR] Failed to load mask: {mf} - {err}")
            raise

    return masks


# 加入 0.1 版本：找出當前 slice 的脊椎標籤
def find_spine_label(slice_idx, dicom_dir: Path, fast=False):
    for seg_name in [
        "segmentation_total",
        "segmentation_total_fast",
        "segmentation_spine_fast",
    ]:
        seg_dir = dicom_dir.parent / f"{dicom_dir.name}_output" / (seg_name)
        if not seg_dir.is_dir():
            continue
        for mask_file in sorted(seg_dir.glob("vertebrae_*.nii.gz")):
            try:
                arr = sitk.GetArrayFromImage(sitk.ReadImage(str(mask_file)))
                if slice_idx < arr.shape[0] and np.any(arr[slice_idx] > 0):
                    name = (
                        mask_file.name.replace("vertebrae_", "")
                        .replace(".nii.gz", "")
                        .replace(".nii", "")
                    )
                    return name
            except Exception:
                continue
    return None


# 加入 0.1 版本：在影像上繪製脊椎標籤文字
def draw_spine_label(image, spine_label):
    if not spine_label:
        return
    font_size = 18
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(image)
    x, y = image.width - 90, 8
    labeltext = f"Spine:{spine_label}"
    draw.text((x + 1, y + 1), labeltext, fill=(0, 0, 0, 240), font=font)
    draw.text((x, y), labeltext, fill=(255, 255, 255, 255), font=font)


def dicom_to_overlay_png(
    dicom_dir: Path,
    out_dir: Path,
    masks_dir: Path = None,
    show_spine=True,
    task_name=None,
    fast=False,
):
    validate_path_ascii(dicom_dir)
    validate_path_ascii(out_dir)

    reader = sitk.ImageSeriesReader()
    files = reader.GetGDCMSeriesFileNames(str(dicom_dir))
    if not files:
        print(f"❌ [ERROR] No DICOM found in: {dicom_dir}")
        raise RuntimeError(f"No DICOM found in: {dicom_dir}")

    reader.SetFileNames(files)
    image = sitk.Cast(reader.Execute(), sitk.sitkInt16)
    arr = sitk.GetArrayFromImage(image)

    wc, ww = 40, 400  # Window center and width

    mask_files = discover_mask_files(dicom_dir, masks_dir, task_name, fast)
    all_masks = load_masks(mask_files, image)

    color_map = {
        name: color
        for name, color in zip(
            [name for name, _ in all_masks], generate_color_palette(len(all_masks))
        )
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    output_count = 0

    for idx, dicom_file in enumerate(files):
        try:
            slice_arr = arr[idx]
            minv, maxv = wc - ww / 2, wc + ww / 2
            windowed = np.clip((slice_arr - minv) / (maxv - minv), 0, 1)
            base_u8 = (windowed * 255.0 + 0.5).astype(np.uint8)
            base_rgb = np.stack([base_u8] * 3, axis=-1).astype(np.float32)
            overlay_rgb = base_rgb.copy()

            slice_labels = []
            for name, mask_arr in all_masks:
                mask_slice = mask_arr[idx] > 0
                if np.any(mask_slice):
                    slice_labels.append(name)
                    color = color_map.get(name, (255, 0, 0))
                    for c in range(3):
                        overlay_rgb[mask_slice, c] = (
                            overlay_rgb[mask_slice, c] * 0.4 + color[c] * 0.6
                        )

            overlay_img = Image.fromarray(np.clip(overlay_rgb, 0, 255).astype(np.uint8))
            draw_legend(overlay_img, list(dict.fromkeys(slice_labels)), color_map)
            # 加入 0.1 版本的脊椎文字標示邏輯
            if show_spine:
                label = find_spine_label(idx, dicom_dir, fast)
                draw_spine_label(overlay_img, label)
            png_filename = Path(dicom_file).with_suffix(".png").name
            overlay_img.save(out_dir / png_filename)
            output_count += 1

        except Exception as e:
            print(
                f"⚠ [WARNING] Overlay failed for slice {idx}: {files[idx]}, error: {e}"
            )
            continue

    print(f"✅ [SUCCESS] Total overlays saved: {output_count} in {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Draw overlays for segmentation.")
    parser.add_argument(
        "--dicom", type=str, default="SER00005", help="Input DICOM folder"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output base folder (parent of xxx_output)",
    )
    parser.add_argument(
        "--spine", type=int, default=1, help="Show spine labels (1=Yes, 0=No)"
    )
    parser.add_argument(
        "--task", type=str, default="abdominal_muscles", help="Segmentation task"
    )
    parser.add_argument(
        "--fast", type=int, default=0, help="Use fast segmentation (1=Yes)"
    )

    args = parser.parse_args()

    # === Path calculation (same as seg.py) ===
    dicom_path = Path(args.dicom).resolve()

    output_base = (
        Path(args.out) if args.out else dicom_path.parent
    ) / f"{dicom_path.name}_output"

    output_base.mkdir(parents=True, exist_ok=True)

    seg_folder_name = f"segmentation_{args.task}" + ("_fast" if args.fast else "")
    seg_output = output_base / seg_folder_name
    png_folder = output_base / "png"

    # === Debug output ===
    print("\n" + "=" * 60)
    print("🔍 [DEBUG] Path Resolution")
    print("=" * 60)
    print(f"  DICOM input:       {dicom_path}")
    print(f"  Output base:       {output_base}")
    print(f"  Mask folder:       {seg_output}")
    print(f"  PNG folder:        {png_folder}")
    print("=" * 60 + "\n")

    # === Error checking ===
    if not dicom_path.exists():
        print(f"❌ [ERROR] DICOM folder not found: {dicom_path}")
        print(f"   Current working directory: {Path.cwd()}")
        sys.exit(1)

    if not seg_output.exists():
        print(f"❌ [ERROR] Mask folder not found: {seg_output}")
        print(f"   Expected path: {seg_output}")
        print(f"\n   Possible reasons:")
        print(f"   1. seg.py hasn't run yet or failed")
        print(f"   2. Task name mismatch (current: {args.task})")
        print(
            f"   3. Fast mode mismatch (current: {'fast' if args.fast else 'normal'})"
        )
        sys.exit(1)

    try:
        dicom_to_overlay_png(
            dicom_path,
            png_folder,  # 傳 PNG 資料夾
            seg_output,  # 傳 mask 資料夾
            show_spine=bool(args.spine),
            task_name=args.task,
            fast=bool(args.fast),
        )
    except Exception as ex:
        print(f"\n❌ [FATAL ERROR] Unexpected error during drawing:")
        print(f"   {type(ex).__name__}: {ex}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
