"""Modal dialogs (e.g. university email)."""

from typing import Optional

import tkinter as tk
from tkinter import messagebox

from recorder import config


def ask_university_email(parent: tk.Tk) -> Optional[str]:
    """Show modal dialog: 'Enter your University email address'. Returns email or None if cancelled."""
    result = [None]

    d = tk.Toplevel(parent)
    d.title("University email")
    d.configure(bg=config.BG2)
    d.resizable(False, False)
    d.transient(parent)
    d.grab_set()

    tk.Label(
        d, text="Enter your University email address",
        font=config.sans_font(), bg=config.BG2, fg=config.FG,
    ).pack(pady=(16, 8), padx=20, anchor="w")
    entry = tk.Entry(d, font=config.sans_font(), width=40, bg=config.BG3, fg=config.FG, insertbackground=config.FG)
    entry.pack(pady=(0, 16), padx=20, fill="x", ipady=6)
    entry.focus_set()

    def _validate() -> bool:
        s = (entry.get() or "").strip()
        if "@" in s and "." in s and len(s) > 5:
            result[0] = s
            return True
        messagebox.showwarning("Invalid email", "Please enter a valid university email address.", parent=d)
        return False

    def _ok():
        if _validate():
            d.destroy()

    def _cancel():
        d.destroy()

    btn_frame = tk.Frame(d, bg=config.BG2)
    btn_frame.pack(pady=(0, 16))
    tk.Button(
        btn_frame, text="OK", font=config.sans_font(), bg=config.BG3, fg=config.FG,
        relief="flat", cursor="hand2", padx=16, pady=6, command=_ok,
    ).pack(side="left", padx=4)
    tk.Button(
        btn_frame, text="Cancel", font=config.sans_font(), bg=config.BG3, fg=config.FG2,
        relief="flat", cursor="hand2", padx=16, pady=6, command=_cancel,
    ).pack(side="left", padx=4)

    entry.bind("<Return>", lambda e: _ok())
    d.protocol("WM_DELETE_WINDOW", _cancel)
    d.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - d.winfo_reqwidth()) // 2
    y = parent.winfo_y() + (parent.winfo_height() - d.winfo_reqheight()) // 2
    d.geometry(f"+{max(0, x)}+{max(0, y)}")
    d.wait_window()
    return result[0]
