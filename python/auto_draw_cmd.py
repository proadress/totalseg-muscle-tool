def build_auto_draw_command(
    dicom,
    out,
    task,
    spine,
    fast,
    erosion_iters,
    slice_start=None,
    slice_end=None,
):
    cmd = [
        "uv",
        "run",
        "draw.py",
        "--dicom",
        str(dicom),
        "--task",
        str(task),
        "--spine",
        str(spine),
        "--fast",
        str(fast),
        "--erosion_iters",
        str(erosion_iters),
    ]

    if out is not None:
        cmd.extend(["--out", str(out)])
    if slice_start is not None:
        cmd.extend(["--slice_start", str(slice_start)])
    if slice_end is not None:
        cmd.extend(["--slice_end", str(slice_end)])

    return cmd
