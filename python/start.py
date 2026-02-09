#!/usr/bin/env python3
"""
Cross-platform Launcher GUI - Automatically detects system and installs appropriate version
"""
import os
import sys
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import threading


def get_platform():
    """Detect operating system"""
    system = platform.system()
    if system == "Darwin":
        return "mac"
    elif system == "Windows":
        return "windows"
    elif system == "Linux":
        return "linux"
    else:
        return "unknown"


def check_uv():
    """Check if uv is installed"""
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_uv(plat):
    """Install uv"""
    try:
        if plat == "windows":
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "ByPass", "-c",
                 "irm https://astral.sh/uv/install.ps1 | iex"],
                check=True
            )
        else:
            subprocess.run(
                ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                check=True
            )
        return True
    except subprocess.CalledProcessError:
        return False


def setup_venv(python_dir):
    """Create virtual environment"""
    venv_path = python_dir / ".venv"
    if not venv_path.exists():
        subprocess.run(["uv", "venv"], cwd=python_dir, check=True)


def install_dependencies(python_dir, plat, progress_callback=None):
    """Install dependencies"""
    if progress_callback:
        progress_callback("同步依賴套件 | Syncing dependencies...")

    subprocess.run(["uv", "sync"], cwd=python_dir, check=True)

    # Mac needs CPU version of PyTorch
    if plat == "mac":
        if progress_callback:
            progress_callback("安裝 CPU 版 PyTorch | Installing CPU PyTorch...")
        subprocess.run(
            ["uv", "pip", "install", "torch", "torchvision", "torchaudio",
             "--index-url", "https://download.pytorch.org/whl/cpu"],
            cwd=python_dir,
            check=True
        )


def launch_gui(python_dir, script_name):
    """Launch GUI"""
    if platform.system() == "Windows":
        # Windows: Open in new window
        subprocess.Popen(
            ["cmd", "/c", "uv", "run", script_name],
            cwd=python_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Mac/Linux: Direct execution
        subprocess.Popen(["uv", "run", script_name], cwd=python_dir)


class LauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TotalSegmentator 工具啟動器 | Tool Launcher")
        self.root.geometry("550x500")
        self.root.configure(bg="#f5f8fc")

        self.plat = get_platform()
        self.script_dir = Path(__file__).parent
        # launcher.py is already in python/, so python_dir is current directory
        self.python_dir = self.script_dir

        self.setup_ui()

    def setup_ui(self):
        """Build UI"""
        # Main frame
        frame = ttk.Frame(self.root, padding="30 30 30 30")
        frame.pack(fill="both", expand=True)

        # Title
        title = ttk.Label(
            frame,
            text="TotalSegmentator 工具啟動器",
            font=("Segoe UI", 16, "bold")
        )
        title.grid(row=0, column=0, columnspan=2, pady=(0, 5))

        # Subtitle
        subtitle = ttk.Label(
            frame,
            text="Tool Launcher",
            font=("Segoe UI", 10),
            foreground="#888"
        )
        subtitle.grid(row=1, column=0, columnspan=2, pady=(0, 10))

        # System info
        plat_text = f"系統 System: {self.plat.capitalize()}"
        plat_label = ttk.Label(frame, text=plat_text, font=("Segoe UI", 10))
        plat_label.grid(row=2, column=0, columnspan=2, pady=(0, 20))

        # Status label
        self.status_label = ttk.Label(
            frame,
            text="請選擇要啟動的工具 | Please select a tool",
            font=("Segoe UI", 10),
            foreground="#666"
        )
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(0, 20))

        # Button style
        button_style = {"width": 40, "padding": 10}

        # Tool buttons
        btn1 = ttk.Button(
            frame,
            text="1. AI 肌肉分割 (單檔) | AI Muscle Segmentation",
            command=lambda: self.launch_tool("gui_main.py"),
            **button_style
        )
        btn1.grid(row=4, column=0, columnspan=2, pady=5)

        btn2 = ttk.Button(
            frame,
            text="2. 批次 AI 分割 | Batch AI Segmentation",
            command=lambda: self.launch_tool("batch_gui.py"),
            **button_style
        )
        btn2.grid(row=5, column=0, columnspan=2, pady=5)

        btn3 = ttk.Button(
            frame,
            text="3. 手動 vs AI 比較 | Manual vs AI Comparison",
            command=lambda: self.launch_tool("compare_gui.py"),
            **button_style
        )
        btn3.grid(row=6, column=0, columnspan=2, pady=5)

        # Exit button
        btn_exit = ttk.Button(
            frame,
            text="退出 Exit",
            command=self.root.quit,
            **button_style
        )
        btn_exit.grid(row=7, column=0, columnspan=2, pady=(20, 0))

        # Progress bar (hidden)
        self.progress = ttk.Progressbar(
            frame,
            mode='indeterminate',
            length=350
        )

        # Help text
        help_text = ttk.Label(
            frame,
            text="首次啟動需要下載依賴套件，請耐心等待\nFirst launch requires downloading dependencies",
            font=("Segoe UI", 9),
            foreground="#999",
            justify="center"
        )
        help_text.grid(row=8, column=0, columnspan=2, pady=(15, 0))

    def update_status(self, message):
        """Update status message"""
        self.status_label.config(text=message)
        self.root.update()

    def show_progress(self):
        """Show progress bar"""
        self.progress.grid(row=7, column=0, columnspan=2, pady=10)
        self.progress.start()

    def hide_progress(self):
        """Hide progress bar"""
        self.progress.stop()
        self.progress.grid_remove()

    def launch_tool(self, script_name):
        """Launch tool (background installation check)"""
        def setup_and_launch():
            try:
                # Check uv
                if not check_uv():
                    self.update_status("正在安裝 uv | Installing uv...")
                    self.show_progress()

                    if not install_uv(self.plat):
                        messagebox.showerror(
                            "錯誤 Error",
                            "uv 安裝失敗\nFailed to install uv\n\n請手動安裝 Please install manually:\nhttps://astral.sh/uv"
                        )
                        return

                    messagebox.showinfo(
                        "安裝完成 Installation Complete",
                        "uv 安裝成功！\nuv installed successfully!\n\n請重新啟動此程式\nPlease restart this program"
                    )
                    self.root.quit()
                    return

                # Create virtual environment
                self.update_status("檢查虛擬環境 | Checking environment...")
                self.show_progress()
                setup_venv(self.python_dir)

                # Install dependencies
                install_dependencies(
                    self.python_dir,
                    self.plat,
                    progress_callback=self.update_status
                )

                self.hide_progress()
                self.update_status("啟動工具中 | Launching tool...")

                # Launch tool
                launch_gui(self.python_dir, script_name)

                # Show success message
                tool_names = {
                    "gui_main.py": "AI 肌肉分割 | AI Muscle Segmentation",
                    "batch_gui.py": "批次 AI 分割 | Batch AI Segmentation",
                    "compare_gui.py": "手動 vs AI 比較 | Manual vs AI Comparison"
                }

                messagebox.showinfo(
                    "啟動成功 Launch Successful",
                    f"{tool_names.get(script_name, 'Tool')} 已啟動！\nhas been launched!"
                )

                self.update_status("請選擇要啟動的工具 | Please select a tool")

            except subprocess.CalledProcessError as e:
                self.hide_progress()
                messagebox.showerror(
                    "錯誤 Error",
                    f"執行失敗 Execution failed:\n{str(e)}"
                )
                self.update_status("發生錯誤 | Error occurred")
            except Exception as e:
                self.hide_progress()
                messagebox.showerror(
                    "錯誤 Error",
                    f"未預期的錯誤 Unexpected error:\n{str(e)}"
                )
                self.update_status("發生錯誤 | Error occurred")

        # Execute in background to avoid UI freeze
        thread = threading.Thread(target=setup_and_launch, daemon=True)
        thread.start()

    def run(self):
        """Run GUI"""
        self.root.mainloop()


def main():
    # Check platform
    plat = get_platform()
    if plat == "unknown":
        messagebox.showerror(
            "Error",
            "Unsupported operating system"
        )
        sys.exit(1)

    # Launch GUI
    app = LauncherGUI()
    app.run()


if __name__ == "__main__":
    main()
