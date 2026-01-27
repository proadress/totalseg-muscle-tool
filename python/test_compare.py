"""
單元測試：compare_gui.py 核心功能

測試項目：
1. Dice 係數計算正確性
2. 面積計算正確性
3. 層數偵測正確性
"""

import numpy as np
import SimpleITK as sitk
from compare_gui import calculate_dice, calculate_area, find_annotated_slice


def test_dice_coefficient():
    """Test 1.1: Dice 係數計算正確性"""
    print("\n" + "=" * 60)
    print("Test 1.1: Dice 係數計算正確性")
    print("=" * 60)

    # Case 1: 完全相同的 mask
    print("\n[Case 1] 完全相同的 mask → Dice 應該 = 1.0")
    mask_a = np.array([[1, 1, 0], [1, 0, 0]])
    mask_b = np.array([[1, 1, 0], [1, 0, 0]])
    dice = calculate_dice(mask_a, mask_b)
    print(f"  結果: {dice:.4f}")
    assert dice == 1.0, f"Failed: Expected 1.0, got {dice}"
    print("  [OK] 通過")

    # Case 2: 完全不重疊
    print("\n[Case 2] 完全不重疊 → Dice 應該 = 0.0")
    mask_a = np.array([[1, 1, 0], [0, 0, 0]])
    mask_b = np.array([[0, 0, 1], [1, 1, 0]])
    dice = calculate_dice(mask_a, mask_b)
    print(f"  結果: {dice:.4f}")
    assert dice == 0.0, f"Failed: Expected 0.0, got {dice}"
    print("  [OK] 通過")

    # Case 3: 部分重疊（已知答案）
    print("\n[Case 3] 部分重疊 → Dice = 2*2/(3+3) = 0.6667")
    mask_a = np.array([[1, 1, 1], [0, 0, 0]])  # 3 個像素
    mask_b = np.array([[1, 1, 0], [1, 0, 0]])  # 3 個像素，重疊 2 個
    dice = calculate_dice(mask_a, mask_b)
    print(f"  結果: {dice:.4f}")
    assert abs(dice - 0.6667) < 0.001, f"Failed: Expected 0.6667, got {dice}"
    print("  [OK] 通過")

    # Case 4: 兩個都是空的
    print("\n[Case 4] 兩個都是空的 → Dice 應該 = 0.0")
    mask_a = np.zeros((3, 3))
    mask_b = np.zeros((3, 3))
    dice = calculate_dice(mask_a, mask_b)
    print(f"  結果: {dice:.4f}")
    assert dice == 0.0, f"Failed: Expected 0.0, got {dice}"
    print("  [OK] 通過")

    print("\n[PASS] Test 1.1 全部通過！")


def test_area_calculation():
    """Test 1.2: 面積計算正確性"""
    print("\n" + "=" * 60)
    print("Test 1.2: 面積計算正確性")
    print("=" * 60)

    # Case 1: 10x10 像素, spacing 1mm x 1mm
    print("\n[Case 1] 10x10 像素, spacing 1mm x 1mm → 面積 = 1.0 cm^2")
    mask = np.ones((10, 10), dtype=np.uint8)
    area = calculate_area(mask, spacing=(1.0, 1.0))
    print(f"  計算: 100 像素 * (1.0 * 1.0) / 100 = {area:.4f} cm^2")
    assert abs(area - 1.0) < 0.001, f"Failed: Expected 1.0, got {area}"
    print("  [OK] 通過")

    # Case 2: 10x10 像素, spacing 2mm x 2mm
    print("\n[Case 2] 10x10 像素, spacing 2mm x 2mm → 面積 = 4.0 cm^2")
    area = calculate_area(mask, spacing=(2.0, 2.0))
    print(f"  計算: 100 像素 * (2.0 * 2.0) / 100 = {area:.4f} cm^2")
    assert abs(area - 4.0) < 0.001, f"Failed: Expected 4.0, got {area}"
    print("  [OK] 通過")

    # Case 3: 部分填滿的 mask
    print("\n[Case 3] 5x5 像素部分填滿 (9個像素), spacing 1mm x 1mm → 面積 = 0.09 cm^2")
    mask = np.zeros((5, 5), dtype=np.uint8)
    mask[1:4, 1:4] = 1  # 中間 3x3 = 9 個像素
    area = calculate_area(mask, spacing=(1.0, 1.0))
    print(f"  計算: 9 像素 * (1.0 * 1.0) / 100 = {area:.4f} cm^2")
    assert abs(area - 0.09) < 0.001, f"Failed: Expected 0.09, got {area}"
    print("  [OK] 通過")

    # Case 4: 空的 mask
    print("\n[Case 4] 空的 mask → 面積 = 0.0 cm^2")
    mask = np.zeros((10, 10), dtype=np.uint8)
    area = calculate_area(mask, spacing=(1.0, 1.0))
    print(f"  結果: {area:.4f} cm^2")
    assert area == 0.0, f"Failed: Expected 0.0, got {area}"
    print("  [OK] 通過")

    print("\n[PASS] Test 1.2 全部通過！")


def test_slice_detection():
    """Test 1.3: 層數偵測正確性"""
    print("\n" + "=" * 60)
    print("Test 1.3: 層數偵測正確性")
    print("=" * 60)

    # Case 1: 第 5 層有內容
    print("\n[Case 1] 第 5 層有內容 → 應偵測到 slice 5")
    mask_3d = np.zeros((10, 20, 20), dtype=np.uint8)
    mask_3d[5, 5:15, 5:15] = 1  # 第 5 層有一個方塊
    slice_idx = find_annotated_slice(mask_3d)
    print(f"  偵測到: slice {slice_idx}")
    assert slice_idx == 5, f"Failed: Expected 5, got {slice_idx}"
    print("  [OK] 通過")

    # Case 2: 第 0 層有內容（邊界測試）
    print("\n[Case 2] 第 0 層有內容 → 應偵測到 slice 0")
    mask_3d = np.zeros((10, 20, 20), dtype=np.uint8)
    mask_3d[0, :, :] = 1
    slice_idx = find_annotated_slice(mask_3d)
    print(f"  偵測到: slice {slice_idx}")
    assert slice_idx == 0, f"Failed: Expected 0, got {slice_idx}"
    print("  [OK] 通過")

    # Case 3: 最後一層有內容（邊界測試）
    print("\n[Case 3] 最後一層（第 9 層）有內容 → 應偵測到 slice 9")
    mask_3d = np.zeros((10, 20, 20), dtype=np.uint8)
    mask_3d[9, :, :] = 1
    slice_idx = find_annotated_slice(mask_3d)
    print(f"  偵測到: slice {slice_idx}")
    assert slice_idx == 9, f"Failed: Expected 9, got {slice_idx}"
    print("  [OK] 通過")

    # Case 4: 沒有任何標註（應拋出例外）
    print("\n[Case 4] 沒有任何標註 → 應拋出 ValueError")
    mask_empty = np.zeros((10, 20, 20), dtype=np.uint8)
    try:
        find_annotated_slice(mask_empty)
        assert False, "Should raise ValueError"
    except ValueError as e:
        print(f"  拋出例外: {e}")
        assert "手動標註檔案沒有任何內容" in str(e)
        print("  [OK] 通過")

    # Case 5: 多層標註（應只回傳第一層）
    print("\n[Case 5] 多層標註（第 2, 5, 8 層）→ 應回傳第一層 slice 2")
    mask_3d = np.zeros((10, 20, 20), dtype=np.uint8)
    mask_3d[2, 5:10, 5:10] = 1
    mask_3d[5, 8:12, 8:12] = 1
    mask_3d[8, 10:15, 10:15] = 1
    slice_idx = find_annotated_slice(mask_3d)
    print(f"  偵測到: slice {slice_idx} (應顯示警告訊息)")
    assert slice_idx == 2, f"Failed: Expected 2, got {slice_idx}"
    print("  [OK] 通過")

    print("\n[PASS] Test 1.3 全部通過！")


def main():
    """執行所有測試"""
    print("\n" + "=" * 60)
    print("肌肉分割比較工具 - 單元測試")
    print("=" * 60)

    try:
        test_dice_coefficient()
        test_area_calculation()
        test_slice_detection()

        print("\n" + "=" * 60)
        print("[SUCCESS] 所有測試通過！")
        print("=" * 60)
        print("\n測試摘要：")
        print("  [OK] Dice 係數計算正確（4 個案例）")
        print("  [OK] 面積計算正確（4 個案例）")
        print("  [OK] 層數偵測正確（5 個案例）")
        print("\n總計：13 個測試案例全部通過\n")

    except AssertionError as e:
        print(f"\n[FAIL] 測試失敗: {e}\n")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 發生錯誤: {type(e).__name__}: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
