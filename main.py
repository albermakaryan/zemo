"""
Screen & Webcam Recorder – entry point.
Run: pip install -r requirements.txt (once per machine).
Start: double-click run_recorder.bat (Windows) or: python main.py
"""

import sys


def _check_deps():
    missing = []
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import mss
    except ImportError:
        missing.append("mss")
    try:
        from PIL import Image, ImageTk
    except ImportError:
        missing.append("Pillow")
    if not missing:
        return
    msg = (
        "Missing packages: " + ", ".join(missing) + ".\n\n"
        "In this folder, open a terminal and run:\n"
        "  pip install -r requirements.txt\n\n"
        "Or install Python packages and try again."
    )
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("Recorder – install dependencies", msg)
        root.destroy()
    except Exception:
        print(msg)
        input("Press Enter to exit.")
    sys.exit(1)


def main():
    _check_deps()
    from recorder.ui import App
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
