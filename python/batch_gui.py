"""
Batch Processing GUI - Automatically scan and process multiple DICOM folders
"""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
from datetime import datetime

try:
    import SimpleITK as sitk
except Exception:
    sitk = None

BG = "#f5f8fc"
PRIMARY = "#22223b"
FONT_FACE = "Segoe UI"
FONT_SIZE = 18

root = tk.Tk()
root.title("Batch Medical Image Segmentation")
root.geometry("650x700")
root.configure(bg=BG)

# Variables
root_folder_var = tk.StringVar()
output_var = tk.StringVar()
task_var = tk.StringVar(value="abdominal_muscles")
spine_var = tk.BooleanVar(value=True)
fast_var = tk.BooleanVar(value=False)
draw_var = tk.BooleanVar(value=True)
erosion_iters_var = tk.IntVar(value=7)
max_depth_var = tk.IntVar(value=10)

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

# Root folder selection
ttk.Label(frame, text="Root Folder (containing multiple DICOM):").grid(row=1, column=0, sticky="w", pady=(8, 0))
root_entry = ttk.Entry(frame, textvariable=root_folder_var, width=30)
root_entry.grid(row=2, column=0, sticky="we", pady=4)


def browse_root():
    f = filedialog.askdirectory(title="Select root folder containing multiple DICOM folders")
    if f:
        root_folder_var.set(f)
        # Default output to same folder
        output_var.set(f)
        validate()


ttk.Button(frame, text="Browse...", command=browse_root).grid(
    row=2, column=1, padx=8
)

# Output folder
ttk.Label(frame, text="Output Directory (Optional):").grid(row=3, column=0, sticky="w", pady=(14, 0))
output_entry = ttk.Entry(frame, textvariable=output_var, width=30)
output_entry.grid(row=4, column=0, sticky="we", pady=4)


def browse_output():
    f = filedialog.askdirectory(title="Select output directory")
    if f:
        output_var.set(f)


ttk.Button(frame, text="Browse...", command=browse_output).grid(
    row=4, column=1, padx=8
)

# Task selection
ttk.Label(frame, text="Segmentation Task:").grid(
    row=5, column=0, sticky="w", pady=(14, 0)
)

task_menu = ttk.Combobox(
    frame,
    textvariable=task_var,
    width=28,
    values=[
        "abdominal_muscles",
        "tissue_4_types",
        "tissue_types",
        "tissue_types_mr",
        "thigh_shoulder_muscles",
        "thigh_shoulder_muscles_mr",
        "total",
    ],
)
task_menu.grid(row=6, column=0, columnspan=2, sticky="we", pady=4)

# Options
ttk.Checkbutton(
    frame, text="Spine segmentation (takes longer) ⚠️", variable=spine_var
).grid(row=7, column=0, columnspan=2, sticky="w", pady=(16, 0))

ttk.Checkbutton(
    frame,
    text="Fast mode (not supported in some tasks) ⚠️",
    variable=fast_var,
).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

ttk.Checkbutton(frame, text="Auto-generate PNG overlays", variable=draw_var).grid(
    row=9, column=0, columnspan=2, sticky="w", pady=(8, 0)
)

# Erosion iterations
ttk.Label(frame, text="Erosion iterations (HU calc):").grid(
    row=10, column=0, sticky="w", pady=(12, 0)
)
erosion_entry = ttk.Entry(frame, textvariable=erosion_iters_var, width=8)
erosion_entry.grid(row=11, column=0, sticky="w", pady=4)

# Max depth
ttk.Label(frame, text="Max search depth:").grid(
    row=12, column=0, sticky="w", pady=(12, 0)
)
depth_entry = ttk.Entry(frame, textvariable=max_depth_var, width=8)
depth_entry.grid(row=13, column=0, sticky="w", pady=4)

# Preview button
preview_text = scrolledtext.ScrolledText(
    frame, height=8, width=50, state="disabled", wrap=tk.WORD
)
preview_text.grid(row=14, column=0, columnspan=2, sticky="we", pady=(16, 8))


def preview_folders():
    """Preview which folders will be processed"""
    root_path = root_folder_var.get()
    if not root_path:
        messagebox.showwarning("Warning", "Please select root folder first")
        return

    if sitk is None:
        messagebox.showerror("Error", "SimpleITK not installed, cannot check DICOM folders")
        return

    preview_text.config(state="normal")
    preview_text.delete(1.0, tk.END)
    preview_text.insert(tk.END, "🔍 Scanning...\n")
    preview_text.config(state="disabled")
    preview_text.update()

    def scan():
        from batch_seg import find_all_dicom_folders

        try:
            folders = find_all_dicom_folders(root_path, max_depth_var.get())

            preview_text.config(state="normal")
            preview_text.delete(1.0, tk.END)

            if not folders:
                preview_text.insert(tk.END, "❌ No DICOM folders found\n")
            else:
                preview_text.insert(tk.END, f"✓ Found {len(folders)} DICOM folders:\n\n")
                for i, folder in enumerate(folders, 1):
                    preview_text.insert(tk.END, f"{i}. {folder.name}\n")
                    preview_text.insert(tk.END, f"   {folder}\n\n")

            preview_text.config(state="disabled")
        except Exception as e:
            preview_text.config(state="normal")
            preview_text.delete(1.0, tk.END)
            preview_text.insert(tk.END, f"❌ Scan failed: {e}\n")
            preview_text.config(state="disabled")

    threading.Thread(target=scan, daemon=True).start()


ttk.Button(frame, text="Preview Folders", command=preview_folders).grid(
    row=15, column=0, sticky="w", pady=(0, 8)
)


def validate(*_):
    """驗證輸入"""
    btn_start.state(
        ["!disabled"] if root_folder_var.get() else ["disabled"]
    )


def start():
    """Start batch processing"""
    root_path = root_folder_var.get()
    output_path = output_var.get() if output_var.get() else None

    if not root_path:
        messagebox.showwarning("Warning", "Please select root folder first")
        return

    # Confirm start
    result = messagebox.askyesno(
        "Confirm",
        f"About to start batch processing\n\n"
        f"Root folder: {root_path}\n"
        f"Task: {task_var.get()}\n"
        f"Spine segmentation: {'Yes' if spine_var.get() else 'No'}\n"
        f"Fast mode: {'Yes' if fast_var.get() else 'No'}\n\n"
        f"Continue?",
    )

    if not result:
        return

    btn_start.state(["disabled"])

    # 建立命令
    cmd = [
        "cmd",
        "/k",  # 保持視窗開啟
        "uv",
        "run",
        "batch_seg.py",
        "--root",
        root_path,
        "--task",
        task_var.get(),
        "--spine",
        "1" if spine_var.get() else "0",
        "--fast",
        "1" if fast_var.get() else "0",
        "--auto_draw",
        "1" if draw_var.get() else "0",
        "--erosion_iters",
        str(erosion_iters_var.get()),
        "--max_depth",
        str(max_depth_var.get()),
    ]

    if output_path:
        cmd.extend(["--out", output_path])

    print("Command:", " ".join(cmd))

    try:
        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
            creationflags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(cmd, creationflags=creationflags)

        messagebox.showinfo(
            "Batch Processing Started",
            "Batch processing has been launched in a new window\n\n"
            "After completion, the following files will be created:\n"
            "- batch_processing_log_*.txt (log file)\n"
            "- batch_processing_results_*.json (result statistics)",
        )

    except Exception as e:
        messagebox.showerror("Launch Failed", f"Failed to start batch processing: {e}")
        btn_start.state(["!disabled"])
        return

    root.after(1000, root.destroy)


btn_start = ttk.Button(frame, text="Start Batch Processing", command=start)
btn_start.grid(row=15, column=1, sticky="e", pady=(0, 8))

validate()
root.mainloop()
