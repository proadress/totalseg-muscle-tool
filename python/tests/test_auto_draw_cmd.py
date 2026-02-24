from auto_draw_cmd import build_auto_draw_command


def test_build_auto_draw_command_omits_optional_args_when_none():
    cmd = build_auto_draw_command(
        dicom="SER00005",
        out=None,
        task="abdominal_muscles",
        spine=1,
        fast=0,
        erosion_iters=7,
        slice_start=None,
        slice_end=None,
    )

    assert "--out" not in cmd
    assert "--slice_start" not in cmd
    assert "--slice_end" not in cmd
    assert "" not in cmd


def test_build_auto_draw_command_includes_optional_args_when_set():
    cmd = build_auto_draw_command(
        dicom="SER00005",
        out="/tmp/output",
        task="abdominal_muscles",
        spine=1,
        fast=0,
        erosion_iters=7,
        slice_start=10,
        slice_end=20,
    )

    assert "--out" in cmd
    assert "--slice_start" in cmd
    assert "--slice_end" in cmd

    out_idx = cmd.index("--out")
    start_idx = cmd.index("--slice_start")
    end_idx = cmd.index("--slice_end")

    assert cmd[out_idx + 1] == "/tmp/output"
    assert cmd[start_idx + 1] == "10"
    assert cmd[end_idx + 1] == "20"
