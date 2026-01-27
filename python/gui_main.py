import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

BG = "#f5f8fc"
PRIMARY = "#22223b"
FONT_FACE = "Segoe UI"
FONT_SIZE = 18

root = tk.Tk()
root.title("Medical Image Segmentation")
root.geometry("430x450")
root.configure(bg=BG)

dicom_var = tk.StringVar()
output_var = tk.StringVar()
task_var = tk.StringVar(value="abdominal_muscles")
spine_var = tk.BooleanVar(value=True)
fast_var = tk.BooleanVar(value=False)
draw_var = tk.BooleanVar(value=True)

# Check GPU or CPU
try:
    import torch
    device_text = "Detected Device: GPU" if torch.cuda.is_available() else "Detected Device: CPU"
except Exception:
    device_text = "Detected Device: CPU"

frame = ttk.Frame(root, padding="25 20 25 20", style="TFrame")
frame.pack(fill="both", expand=True)

# Device label
ttk.Label(frame, text=device_text).grid(
    row=0, column=0, columnspan=2, sticky="w", pady=(3, 14)
)

ttk.Label(frame, text="DICOM Folder:").grid(row=1, column=0, sticky="w", pady=(8, 0))
dicom_entry = ttk.Entry(frame, textvariable=dicom_var, width=26)
dicom_entry.grid(row=2, column=0, sticky="we", pady=4)

def browse_dicom():
    f = filedialog.askdirectory(title="Select DICOM Folder")
    if f:
        dicom_var.set(f)
        parent_folder = str(Path(f).parent)
        output_var.set(parent_folder)
        validate()

ttk.Button(frame, text="Browse...", command=browse_dicom).grid(
    row=2, column=1, padx=8
)

def browse_output():
    f = filedialog.askdirectory(title="Select Output Folder")
    if f:
        output_var.set(f)
        validate()

def validate(*_):
    btn_start.state(
        ["!disabled"] if dicom_var.get() and output_var.get() else ["disabled"]
    )

ttk.Label(frame, text="Output Dir:").grid(row=4, column=0, sticky="w", pady=(14, 0))
output_entry = ttk.Entry(frame, textvariable=output_var, width=26)
output_entry.grid(row=5, column=0, sticky="we", pady=4)
ttk.Button(frame, text="Browse...", command=browse_output).grid(
    row=5, column=1, padx=8
)

ttk.Label(frame, text="Segmentation Task:").grid(
    row=7, column=0, sticky="w", pady=(14, 0)
)

task_menu = ttk.Combobox(
    frame,
    textvariable=task_var,
    width=24,
    values=[
        "abdominal_muscles",
        "aortic_sinuses",
        "appendicular_bones",
        "appendicular_bones_mr",
        "body",
        "body_mr",
        "brain_structures",
        "breasts",
        "cerebral_bleed",
        "coronary_arteries",
        "craniofacial_structures",
        "face",
        "face_mr",
        "head_glands_cavities",
        "head_muscles",
        "headneck_bones_vessels",
        "headneck_muscles",
        "heartchambers_highres",
        "hip_implant",
        "kidney_cysts",
        "liver_segments",
        "liver_segments_mr",
        "lung_nodules",
        "lung_vessels",
        "oculomotor_muscles",
        "pleural_pericard_effusion",
        "thigh_shoulder_muscles",
        "thigh_shoulder_muscles_mr",
        "tissue_4_types",
        "tissue_types",
        "tissue_types_mr",
        "ventricle_parts",
        "vertebrae_body",
        "vertebrae_mr",
        "total_mr",
        "total",
    ],
)

task_menu.grid(row=8, column=0, columnspan=2, sticky="we", pady=4)

ttk.Checkbutton(
    frame, text="Spine segmentation (takes more time) ⚠️", variable=spine_var
).grid(row=9, column=0, columnspan=2, sticky="w", pady=(16, 0))

ttk.Checkbutton(
    frame,
    text="Fast mode (may reduce accuracy, not supported in some tasks) ⚠️",
    variable=fast_var,
).grid(row=10, column=0, columnspan=2, sticky="w", pady=(8, 0))

ttk.Checkbutton(frame, text="Export PNG overlays", variable=draw_var).grid(
    row=11, column=0, columnspan=2, sticky="w", pady=(8, 0)
)

def start():
    btn_start.state(["disabled"])
    dicom = dicom_var.get()
    out = output_var.get()
    cmd = [
        "cmd",
        "/k",  # Keep window open to view results
        "uv",
        "run",
        "seg.py",
        "--dicom",
        dicom,
        "--out",
        out,
        "--task",
        task_var.get(),
        "--spine",
        "1" if spine_var.get() else "0",
        "--fast",
        "1" if fast_var.get() else "0",
        "--auto_draw",
        "1" if draw_var.get() else "0",
    ]
    print("Command:", " ".join(cmd))
    try:
        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
            creationflags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(cmd, creationflags=creationflags)
    except Exception as e:
        messagebox.showerror("Launch Failed", f"Unable to open process: {e}")
    root.after(0, root.destroy)

btn_start = ttk.Button(frame, text="Start", command=start)
btn_start.grid(row=12, column=1, sticky="e", pady=16)

validate()
root.mainloop()
