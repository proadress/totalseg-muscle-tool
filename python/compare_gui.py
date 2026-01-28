"""
手動 vs AI 肌肉分割比較工具

功能：
1. 選擇兩個檔案（AI 分割 .nii.gz + 手動標註 .seg.nrrd）
2. 自動執行比較，結果即時顯示在 GUI
3. 可選擇性匯出 CSV

作者: Claude + IGL
版本: 1.0
"""

import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import csv

import numpy as np
import SimpleITK as sitk

try:
    import slicerio
except ImportError:
    print("[ERROR] [ERROR] slicerio not installed. Please run: uv sync")
    sys.exit(1)

# ============================================================================
# 核心比較邏輯
# ============================================================================


def calculate_dice(mask1, mask2):
    """
    計算 Dice 相似係數

    Dice = 2 * |A ∩ B| / (|A| + |B|)

    Args:
        mask1, mask2: 二值化的 numpy array (shape相同)

    Returns:
        float: 0.0 ~ 1.0，1.0 表示完全相同
    """
    mask1_bool = mask1 > 0
    mask2_bool = mask2 > 0

    intersection = np.sum(mask1_bool & mask2_bool)
    total = np.sum(mask1_bool) + np.sum(mask2_bool)

    if total == 0:
        return 0.0  # 兩個都是空的

    return 2.0 * intersection / total


def calculate_jaccard(mask1, mask2):
    """
    計算 Jaccard 相似係數 (IoU)

    Jaccard = |A ∩ B| / |A ∪ B|
    """
    mask1_bool = mask1 > 0
    mask2_bool = mask2 > 0
    intersection = np.sum(mask1_bool & mask2_bool)
    union = np.sum(mask1_bool | mask2_bool)
    if union == 0:
        return 0.0
    return float(intersection) / float(union)


def calculate_precision_recall(mask_pred, mask_gt):
    """
    計算 Precision / Recall（以 GT 為標準）
    """
    pred = mask_pred > 0
    gt = mask_gt > 0
    tp = np.sum(pred & gt)
    fp = np.sum(pred & (~gt))
    fn = np.sum((~pred) & gt)

    precision = float(tp) / float(tp + fp) if (tp + fp) > 0 else 0.0
    recall = float(tp) / float(tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def _surface_distances(mask_a, mask_b, spacing_xy):
    """
    計算 A 的邊界到 B 邊界的距離 (mm)
    """
    img_a = sitk.GetImageFromArray(mask_a.astype(np.uint8))
    img_b = sitk.GetImageFromArray(mask_b.astype(np.uint8))
    img_a.SetSpacing((spacing_xy[0], spacing_xy[1]))
    img_b.SetSpacing((spacing_xy[0], spacing_xy[1]))

    contour_a = sitk.BinaryContour(img_a, fullyConnected=True)
    contour_b = sitk.BinaryContour(img_b, fullyConnected=True)
    contour_a_arr = sitk.GetArrayFromImage(contour_a) > 0
    contour_b_arr = sitk.GetArrayFromImage(contour_b) > 0

    # 極小物件可能導致 contour 空，退回用 mask 本身
    if not np.any(contour_a_arr):
        contour_a_arr = mask_a > 0
    if not np.any(contour_b_arr):
        contour_b_arr = mask_b > 0

    dist_map_b = sitk.SignedMaurerDistanceMap(
        img_b,
        squaredDistance=False,
        useImageSpacing=True,
        insideIsPositive=False,
    )
    dist_map_b_arr = sitk.GetArrayFromImage(dist_map_b)

    distances = np.abs(dist_map_b_arr[contour_a_arr])
    return distances


def calculate_surface_metrics(mask1, mask2, spacing_xy):
    """
    計算 HD / HD95 / ASSD（單層 2D, 單位 mm）
    """
    mask1_bool = mask1 > 0
    mask2_bool = mask2 > 0

    if not np.any(mask1_bool) and not np.any(mask2_bool):
        return {"hd": 0.0, "hd95": 0.0, "assd": 0.0}

    if not np.any(mask1_bool) or not np.any(mask2_bool):
        return {"hd": float("inf"), "hd95": float("inf"), "assd": float("inf")}

    dist_1_to_2 = _surface_distances(mask1_bool, mask2_bool, spacing_xy)
    dist_2_to_1 = _surface_distances(mask2_bool, mask1_bool, spacing_xy)

    if dist_1_to_2.size == 0 or dist_2_to_1.size == 0:
        return {"hd": float("inf"), "hd95": float("inf"), "assd": float("inf")}

    combined = np.concatenate([dist_1_to_2, dist_2_to_1])
    hd = float(max(dist_1_to_2.max(), dist_2_to_1.max()))
    hd95 = float(np.percentile(combined, 95))
    assd = float(np.mean(combined))

    return {"hd": hd, "hd95": hd95, "assd": assd}


def calculate_area(mask_slice, spacing):
    """
    計算單層 mask 的面積（與 seg.py 一致的邏輯）

    Args:
        mask_slice: 2D numpy array
        spacing: tuple (spacing_x, spacing_y) in mm

    Returns:
        float: 面積 (cm^2)
    """
    pixel_count = np.sum(mask_slice > 0)
    area_mm2 = pixel_count * spacing[0] * spacing[1]
    area_cm2 = area_mm2 / 100.0
    return area_cm2


def find_annotated_slice(mask_array):
    """
    找出手動標註的層數（假設只有一層）

    Args:
        mask_array: 3D numpy array (slices, height, width)

    Returns:
        int: 層數索引（從0開始）

    Raises:
        ValueError: 如果沒有找到任何標註
    """
    annotated_slices = []

    for i in range(mask_array.shape[0]):
        if np.sum(mask_array[i] > 0) > 0:
            annotated_slices.append(i)

    if len(annotated_slices) == 0:
        raise ValueError("手動標註檔案沒有任何內容（所有層都是空的）")

    if len(annotated_slices) > 1:
        print(
            f"[WARNING] 找到 {len(annotated_slices)} 層標註: {annotated_slices}"
        )
        print(f"          只處理第一層: slice {annotated_slices[0]}")

    return annotated_slices[0]


def check_spacing_match(spacing1, spacing2, tolerance=0.1):
    """
    檢查兩個 spacing 是否匹配

    Args:
        spacing1, spacing2: tuple (x, y, z)
        tolerance: 允許的差異百分比 (0.1 = 10%)

    Returns:
        bool: True if matched within tolerance
    """
    for s1, s2 in zip(spacing1[:2], spacing2[:2]):  # 只檢查 x, y
        diff = abs(s1 - s2) / max(s1, s2)
        if diff > tolerance:
            return False
    return True


def align_manual_to_ai(manual_img, ai_img):
    """
    將手動標註重採樣到 AI 結果的空間

    使用 NearestNeighbor 插值以保持二值化特性

    Args:
        manual_img: SimpleITK.Image（手動標註）
        ai_img: SimpleITK.Image（AI 結果）

    Returns:
        SimpleITK.Image: 對齊後的手動標註
    """
    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(ai_img)
    resampler.SetInterpolator(sitk.sitkNearestNeighbor)
    resampler.SetDefaultPixelValue(0)
    resampler.SetTransform(sitk.Transform())  # Identity transform - 用物理座標對齊

    return resampler.Execute(manual_img)


def load_seg_nrrd(nrrd_path):
    """
    讀取 Slicer 匯出的 .seg.nrrd 檔案

    Args:
        nrrd_path: str or Path

    Returns:
        sitk.Image: segmentation image
        str: segment name

    Raises:
        FileNotFoundError: 檔案不存在
        ValueError: 檔案格式錯誤或沒有 segment
    """
    nrrd_path = Path(nrrd_path)

    if not nrrd_path.exists():
        raise FileNotFoundError(f"找不到手動標註檔案: {nrrd_path}")

    try:
        # 使用 slicerio 讀取
        segmentation_info = slicerio.read_segmentation(str(nrrd_path))
    except Exception as e:
        raise ValueError(f"無法讀取 .seg.nrrd 檔案: {e}")

    # 檢查資料結構
    if 'voxels' not in segmentation_info:
        raise ValueError(".seg.nrrd 檔案格式錯誤：找不到 voxels 資料")

    if 'segments' not in segmentation_info or len(segmentation_info['segments']) == 0:
        raise ValueError(".seg.nrrd 檔案中沒有找到任何 segment")

    # 取得 voxels（整個 labelmap）
    voxels = segmentation_info['voxels']
    segments_list = segmentation_info['segments']

    # 取得第一個 segment 的資訊
    first_segment = segments_list[0]
    segment_name = first_segment.get('name', 'Unknown')
    label_value = first_segment.get('labelValue', 1)

    print(f"[OK] 載入手動標註: '{segment_name}' (labelValue={label_value})")

    if len(segments_list) > 1:
        print(
            f"[WARNING] 找到 {len(segments_list)} 個 segments，使用第一個: '{segment_name}'"
        )

    # 從 voxels 中提取該 segment 的 mask（只保留該 labelValue 的像素）
    mask_array = (voxels == label_value).astype(np.uint8)

    # slicerio 的 voxels 是 (X, Y, Z) 順序，需要轉置成 (Z, Y, X) 才能用 GetImageFromArray
    # 轉置軸向：(0, 1, 2) -> (2, 1, 0)
    mask_array = np.transpose(mask_array, (2, 1, 0))

    # 轉換為 SimpleITK Image
    manual_img = sitk.GetImageFromArray(mask_array)

    # 設定 spacing, origin, direction（從 ijkToLPS 矩陣提取）
    if 'ijkToLPS' in segmentation_info:
        ijkToLPS = segmentation_info['ijkToLPS']

        # 1. 提取 spacing（對角線元素）
        spacing = (
            abs(ijkToLPS[0, 0]),  # X spacing
            abs(ijkToLPS[1, 1]),  # Y spacing
            abs(ijkToLPS[2, 2])   # Z spacing
        )
        manual_img.SetSpacing(spacing)

        # 2. 提取 origin（最後一行的前三個元素）
        origin = (
            ijkToLPS[0, 3],  # X origin
            ijkToLPS[1, 3],  # Y origin
            ijkToLPS[2, 3]   # Z origin
        )
        manual_img.SetOrigin(origin)

        # 3. 提取 direction（歸一化的方向向量）
        # ijkToLPS 的前3x3部分包含 spacing * direction
        # 需要除以 spacing 得到純方向向量
        direction = []
        for row in range(3):  # LPS 物理座標
            for col in range(3):  # IJK 影像座標
                spacing_val = abs(ijkToLPS[col, col])
                if spacing_val != 0:
                    direction.append(ijkToLPS[row, col] / spacing_val)
                else:
                    direction.append(0.0)
        manual_img.SetDirection(tuple(direction))

        print(f"[OK] 設定 spacing: {spacing}")
        print(f"[OK] 設定 origin: ({origin[0]:.2f}, {origin[1]:.2f}, {origin[2]:.2f})")
        print(f"[OK] 設定 direction")

    return manual_img, segment_name


def compare_segmentations(ai_nii_path, manual_nrrd_path):
    """
    比較手動標註和 AI 分割結果

    Args:
        ai_nii_path: str or Path - AI 分割結果 (.nii.gz)
        manual_nrrd_path: str or Path - 手動標註 (.seg.nrrd)

    Returns:
        dict: 單層比較結果

    Raises:
        FileNotFoundError: 檔案不存在
        ValueError: 資料錯誤
    """
    ai_nii_path = Path(ai_nii_path)
    manual_nrrd_path = Path(manual_nrrd_path)

    print("\n" + "=" * 60)
    print("[INFO] 手動 vs AI 肌肉分割比較")
    print("=" * 60)
    print(f"  AI 分割檔案:    {ai_nii_path.name}")
    print(f"  手動標註檔案:  {manual_nrrd_path.name}")
    print("=" * 60 + "\n")

    # === Step 1: 讀取 AI 結果 ===
    print("[1/5] 讀取 AI 分割結果...")
    if not ai_nii_path.exists():
        raise FileNotFoundError(f"找不到 AI 分割檔案: {ai_nii_path}")

    ai_img = sitk.ReadImage(str(ai_nii_path))
    ai_spacing = ai_img.GetSpacing()
    print(f"  [OK] AI spacing: {ai_spacing}")

    # === Step 2: 讀取手動標註 ===
    print("\n[2/5] 讀取手動標註...")
    manual_img, segment_name = load_seg_nrrd(manual_nrrd_path)
    manual_spacing = manual_img.GetSpacing()
    print(f"  [OK] Manual spacing: {manual_spacing}")

    # === Step 3: 對齊影像幾何 ===
    print("\n[3/5] 對齊影像幾何...")

    # 檢查是否需要 resample（檢查所有幾何參數）
    size_match = ai_img.GetSize() == manual_img.GetSize()
    spacing_match = check_spacing_match(ai_spacing, manual_spacing, tolerance=0.01)
    origin_match = np.allclose(ai_img.GetOrigin(), manual_img.GetOrigin(), atol=1.0)
    direction_match = np.allclose(ai_img.GetDirection(), manual_img.GetDirection(), atol=0.01)

    need_resample = not (size_match and spacing_match and origin_match and direction_match)

    if need_resample:
        # 顯示不匹配的項目
        if not size_match:
            print(f"  [INFO] 尺寸不同 (AI: {ai_img.GetSize()}, Manual: {manual_img.GetSize()})")
        if not spacing_match:
            print(f"  [INFO] Spacing 不同")
        if not origin_match:
            print(f"  [INFO] Origin 不同")
            print(f"         AI:     {ai_img.GetOrigin()}")
            print(f"         Manual: {manual_img.GetOrigin()}")
        if not direction_match:
            print(f"  [INFO] Direction 不同 (可能有翻轉或旋轉)")

        print("  -> 正在 Resample 對齊到 AI 影像空間...")
        manual_img = align_manual_to_ai(manual_img, ai_img)
        print("  [OK] Resample 完成")
    else:
        print("  [OK] 影像幾何完全一致，無需 resample")

    # === Step 4: 轉換為 numpy array ===
    print("\n[4/5] 偵測手動標註層數...")
    ai_array = sitk.GetArrayFromImage(ai_img)
    manual_array = sitk.GetArrayFromImage(manual_img)

    # 找出手動標註的層數
    try:
        slice_idx = find_annotated_slice(manual_array)
        print(f"  [OK] 手動標註位於: slice {slice_idx}")
    except ValueError as e:
        raise ValueError(f"[ERROR] {e}")

    # 檢查 AI 結果是否有該層
    if slice_idx >= ai_array.shape[0]:
        raise ValueError(
            f"Slice 索引 {slice_idx} 超出範圍 (AI 只有 {ai_array.shape[0]} 層)"
        )

    # === Step 5: 計算比較結果 ===
    print("\n[5/5] 計算 Dice 係數和面積...")

    manual_slice = manual_array[slice_idx]
    ai_slice = ai_array[slice_idx]

    # 計算 Dice
    dice_score = calculate_dice(manual_slice, ai_slice)
    jaccard_score = calculate_jaccard(manual_slice, ai_slice)
    precision, recall = calculate_precision_recall(ai_slice, manual_slice)
    surface_metrics = calculate_surface_metrics(ai_slice, manual_slice, ai_spacing[:2])

    # 計算面積（使用 AI 的 spacing，因為已經對齊）
    manual_area = calculate_area(manual_slice, ai_spacing[:2])
    ai_area = calculate_area(ai_slice, ai_spacing[:2])
    area_diff = ai_area - manual_area
    area_diff_abs = abs(area_diff)
    area_diff_pct = (area_diff / manual_area * 100.0) if manual_area > 0 else None

    print(f"  [OK] Dice 係數: {dice_score:.4f}")
    print(f"  [OK] Jaccard: {jaccard_score:.4f}")
    print(f"  [OK] Precision: {precision:.4f}")
    print(f"  [OK] Recall: {recall:.4f}")
    print(f"  [OK] 手動面積: {manual_area:.2f} cm^2")
    print(f"  [OK] AI 面積: {ai_area:.2f} cm^2")
    print(f"  [OK] 面積差: {area_diff:+.2f} cm^2")
    if area_diff_pct is not None:
        print(f"  [OK] 面積差(%): {area_diff_pct:+.2f}%")
    print(f"  [OK] HD: {surface_metrics['hd']:.2f} mm")
    print(f"  [OK] HD95: {surface_metrics['hd95']:.2f} mm")
    print(f"  [OK] ASSD: {surface_metrics['assd']:.2f} mm")

    print("\n" + "=" * 60)
    print("[SUCCESS] 比較完成！")
    print("=" * 60 + "\n")

    return {
        "slice_number": slice_idx,
        "manual_area": manual_area,
        "ai_area": ai_area,
        "dice_score": dice_score,
        "jaccard_score": jaccard_score,
        "precision": precision,
        "recall": recall,
        "hd": surface_metrics["hd"],
        "hd95": surface_metrics["hd95"],
        "assd": surface_metrics["assd"],
        "area_diff": area_diff,
        "area_diff_abs": area_diff_abs,
        "area_diff_pct": area_diff_pct,
        "segment_name": segment_name,
    }


# ============================================================================
# GUI 介面
# ============================================================================

# 配色與字體（與 gui_main.py 一致）
BG = "#f5f8fc"
PRIMARY = "#22223b"
FONT_FACE = "Segoe UI"
FONT_SIZE = 10


def format_metric(value, fmt, na="N/A"):
    if value is None:
        return na
    try:
        if not np.isfinite(value):
            return na
    except Exception:
        pass
    return fmt.format(value)




class CompareApp:
    def __init__(self, root):
        self.root = root
        self.root.title("手動 vs AI 肌肉分割比較工具")
        self.root.geometry("550x420")
        self.root.configure(bg=BG)

        # 變數
        self.ai_file_var = tk.StringVar()
        self.manual_file_var = tk.StringVar()
        self.result_data = None  # 儲存比較結果

        # 追蹤檔案選擇變化，自動觸發比較
        self.ai_file_var.trace_add("write", self.on_file_changed)
        self.manual_file_var.trace_add("write", self.on_file_changed)

        # 建立 UI
        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="25 20 25 20")
        frame.pack(fill="both", expand=True)

        # === 標題 ===
        title_label = ttk.Label(
            frame,
            text="手動 vs AI 肌肉分割比較",
            font=(FONT_FACE, 14, "bold"),
            foreground=PRIMARY,
        )
        title_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 20))

        # === AI 分割檔案 ===
        ttk.Label(frame, text="AI 分割檔案 (.nii.gz):").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ai_entry = ttk.Entry(frame, textvariable=self.ai_file_var, width=40)
        ai_entry.grid(row=2, column=0, columnspan=2, sticky="we", pady=4)
        ttk.Button(frame, text="瀏覽", command=self.browse_ai_file).grid(
            row=2, column=2, padx=(8, 0)
        )

        # === 手動分割檔案 ===
        ttk.Label(frame, text="手動標註檔案 (.seg.nrrd):").grid(
            row=3, column=0, sticky="w", pady=(14, 0)
        )
        manual_entry = ttk.Entry(frame, textvariable=self.manual_file_var, width=40)
        manual_entry.grid(row=4, column=0, columnspan=2, sticky="we", pady=4)
        ttk.Button(frame, text="瀏覽", command=self.browse_manual_file).grid(
            row=4, column=2, padx=(8, 0)
        )

        # === 分隔線 ===
        separator = ttk.Separator(frame, orient="horizontal")
        separator.grid(row=5, column=0, columnspan=3, sticky="we", pady=(20, 15))

        # === 結果顯示區 ===
        result_frame = ttk.LabelFrame(frame, text="比較結果", padding="15 10 15 10")
        result_frame.grid(row=6, column=0, columnspan=3, sticky="we", pady=(0, 15))

        # 結果文字（使用 Text widget 以便更新）
        self.result_text = tk.Text(
            result_frame,
            height=8,
            width=55,
            font=(FONT_FACE, 10),
            bg="#ffffff",
            relief="flat",
            borderwidth=0,
            state="disabled",
        )
        self.result_text.pack(fill="both", expand=True)

        # 預設顯示提示
        self.update_result_display("請選擇 AI 分割檔案和手動標註檔案\n比較結果將自動顯示在這裡")

        # === 匯出 CSV 按鈕 ===
        self.export_btn = ttk.Button(
            frame, text="匯出 CSV", command=self.export_csv, state="disabled"
        )
        self.export_btn.grid(row=7, column=2, sticky="e", pady=(5, 0))

    def browse_ai_file(self):
        """選擇 AI 分割檔案"""
        f = filedialog.askopenfilename(
            title="選擇 AI 分割檔案",
            filetypes=[("NIfTI files", "*.nii.gz *.nii"), ("All files", "*.*")],
        )
        if f:
            self.ai_file_var.set(f)

    def browse_manual_file(self):
        """選擇手動標註檔案"""
        f = filedialog.askopenfilename(
            title="選擇手動標註檔案",
            filetypes=[("Slicer Segmentation", "*.seg.nrrd *.nrrd"), ("All files", "*.*")],
        )
        if f:
            self.manual_file_var.set(f)

    def on_file_changed(self, *args):
        """當檔案選擇變化時，自動觸發比較"""
        ai_file = self.ai_file_var.get().strip()
        manual_file = self.manual_file_var.get().strip()

        # 兩個檔案都選好才執行
        if ai_file and manual_file:
            # 檢查檔案是否存在
            if not Path(ai_file).exists():
                self.update_result_display(f"[ERROR] 錯誤：找不到 AI 分割檔案\n{ai_file}")
                self.result_data = None
                self.export_btn.state(["disabled"])
                return

            if not Path(manual_file).exists():
                self.update_result_display(f"[ERROR] 錯誤：找不到手動標註檔案\n{manual_file}")
                self.result_data = None
                self.export_btn.state(["disabled"])
                return

            # 啟動比較（使用 threading 避免凍結）
            self.run_comparison(ai_file, manual_file)
        else:
            # 尚未選好兩個檔案
            self.update_result_display("請選擇 AI 分割檔案和手動標註檔案\n比較結果將自動顯示在這裡")
            self.result_data = None
            self.export_btn.state(["disabled"])

    def run_comparison(self, ai_file, manual_file):
        """執行比較（在背景執行緒）"""
        self.update_result_display("[LOADING] 正在比較中，請稍候...\n（讀取檔案、計算 Dice 係數、計算面積）")
        self.export_btn.state(["disabled"])

        def compare_thread():
            try:
                # 執行比較
                result = compare_segmentations(ai_file, manual_file)

                # 更新 UI（必須在主執行緒）
                self.root.after(0, lambda: self.on_comparison_complete(result))

            except Exception as e:
                error_msg = f"[ERROR] 比較失敗\n\n錯誤類型: {type(e).__name__}\n錯誤訊息: {str(e)}"
                self.root.after(0, lambda: self.update_result_display(error_msg))
                self.root.after(0, lambda: self.export_btn.state(["disabled"]))

        # 啟動背景執行緒
        thread = threading.Thread(target=compare_thread, daemon=True)
        thread.start()

    def on_comparison_complete(self, result):
        """比較完成後的回調"""
        self.result_data = result

        # 格式化結果文字
        area_diff_pct_text = format_metric(
            result["area_diff_pct"], "{:+.2f}%", na="N/A"
        )
        hd_text = format_metric(result["hd"], "{:.2f}", na="N/A")
        hd95_text = format_metric(result["hd95"], "{:.2f}", na="N/A")
        assd_text = format_metric(result["assd"], "{:.2f}", na="N/A")

        result_text = f"""[SUCCESS] 比較完成！

層數 (Slice Number):  {result['slice_number']}

手動面積:  {result['manual_area']:.2f} cm^2
AI 面積:    {result['ai_area']:.2f} cm^2
面積差:    {result['area_diff']:+.2f} cm^2
面積差(%): {area_diff_pct_text}

Dice 分數:  {result['dice_score']:.4f}
Jaccard:   {result['jaccard_score']:.4f}
Precision: {result['precision']:.4f}
Recall:    {result['recall']:.4f}

HD (mm):   {hd_text}
HD95 (mm): {hd95_text}
ASSD (mm): {assd_text}

Segment 名稱: {result['segment_name']}
"""

        self.update_result_display(result_text)

        # 啟用「匯出 CSV」按鈕
        self.export_btn.state(["!disabled"])

    def update_result_display(self, text):
        """更新結果顯示區"""
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", text)
        self.result_text.config(state="disabled")

    def export_csv(self):
        """匯出 CSV"""
        if not self.result_data:
            messagebox.showwarning("無結果", "目前沒有可匯出的比較結果")
            return

        # 選擇儲存位置
        csv_file = filedialog.asksaveasfilename(
            title="儲存 CSV 檔案",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="comparison_result.csv",
        )

        if not csv_file:
            return  # 使用者取消

        try:
            # 寫入 CSV
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "slice_number",
                        "manual_area_cm2",
                        "ai_area_cm2",
                        "area_diff_cm2",
                        "area_diff_abs_cm2",
                        "area_diff_pct",
                        "dice_score",
                        "jaccard_score",
                        "precision",
                        "recall",
                        "hd_mm",
                        "hd95_mm",
                        "assd_mm",
                    ]
                )
                writer.writerow(
                    [
                        self.result_data["slice_number"],
                        f"{self.result_data['manual_area']:.2f}",
                        f"{self.result_data['ai_area']:.2f}",
                        f"{self.result_data['area_diff']:+.2f}",
                        f"{self.result_data['area_diff_abs']:.2f}",
                        format_metric(
                            self.result_data["area_diff_pct"], "{:+.2f}%", na="N/A"
                        ),
                        f"{self.result_data['dice_score']:.4f}",
                        f"{self.result_data['jaccard_score']:.4f}",
                        f"{self.result_data['precision']:.4f}",
                        f"{self.result_data['recall']:.4f}",
                        format_metric(self.result_data["hd"], "{:.2f}", na="N/A"),
                        format_metric(self.result_data["hd95"], "{:.2f}", na="N/A"),
                        format_metric(self.result_data["assd"], "{:.2f}", na="N/A"),
                    ]
                )

            messagebox.showinfo("匯出成功", f"CSV 檔案已儲存至:\n{csv_file}")

        except Exception as e:
            messagebox.showerror("匯出失敗", f"無法儲存 CSV 檔案:\n{e}")


def main():
    root = tk.Tk()
    app = CompareApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
