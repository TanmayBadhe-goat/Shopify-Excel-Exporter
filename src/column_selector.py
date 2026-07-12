"""
column_selector.py — Column selection dialog for Excel exports.

Allows users to select which columns appear in generated Excel files.
Preferences are saved to user_settings.json.

If no preferences are saved (first use), exports use the full default
column set — preserving full backwards compatibility.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
from typing import Optional

from .utils import logger
from .config import Config

# All available columns in order
ALL_COLUMNS = [
    "Image",
    "Order Number",
    "Customer Name",
    "Customer Email",
    "Phone Number",
    "Product Name",
    "Variant Name",
    "Color",
    "Size",
    "Price",
    "Payment Status",
    "Quantity",
]

SETTINGS_KEY = "export_columns"


def get_enabled_columns() -> list:
    """Return the list of enabled column names.

    If no preferences are saved, returns ALL_COLUMNS (backwards compatible).
    """
    settings_path = Path("user_settings.json")
    if not settings_path.exists():
        return list(ALL_COLUMNS)
    try:
        with open(settings_path, "r") as f:
            data = json.load(f)
        columns = data.get(SETTINGS_KEY)
        if columns and isinstance(columns, list) and len(columns) > 0:
            return columns
    except Exception:
        pass
    return list(ALL_COLUMNS)


def save_columns(columns: list):
    """Save column preferences to user_settings.json.

    Preserves all existing keys in the settings file.
    """
    settings_path = Path("user_settings.json")
    try:
        if settings_path.exists():
            with open(settings_path, "r") as f:
                data = json.load(f)
        else:
            data = {}
        data[SETTINGS_KEY] = columns
        with open(settings_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Column preferences saved: {len(columns)} columns")
    except Exception as exc:
        logger.error(f"Failed to save column preferences: {exc}")


class ColumnSelectorDialog:
    """Modal dialog for selecting export columns."""

    def __init__(self, parent):
        self.parent = parent
        self.result: Optional[list] = None
        self._vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("Select Export Columns")
        self.win.geometry("400x500")
        self.win.transient(self.parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        main_frame = ttk.Frame(self.win, padding=15)
        main_frame.pack(fill="both", expand=True)

        # ── Instructions ────────────────────────────────────────────────
        ttk.Label(
            main_frame,
            text="Choose which columns appear in the Excel export:",
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=(0, 10))

        # ── Select All / Deselect All toolbar ────────────────────────────
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(
            toolbar, text="Select All", command=self._select_all, width=12
        ).pack(side="left", padx=2)
        ttk.Button(
            toolbar, text="Deselect All", command=self._deselect_all, width=12
        ).pack(side="left", padx=2)

        # ── Checkbox list ────────────────────────────────────────────────
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel for scrolling (bound to canvas only, not global)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        enabled = get_enabled_columns()
        for col in ALL_COLUMNS:
            var = tk.BooleanVar(value=(col in enabled))
            self._vars[col] = var
            cb = ttk.Checkbutton(
                scrollable_frame,
                text=col,
                variable=var,
                bootstyle="round-toggle",
            )
            cb.pack(anchor="w", pady=2, padx=5)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(
            btn_frame,
            text="Save",
            command=self._save,
            bootstyle="success",
            width=15,
        ).pack(side="right", padx=3)

        ttk.Button(
            btn_frame,
            text="Cancel",
            command=self._cancel,
            bootstyle="secondary",
            width=15,
        ).pack(side="right", padx=3)

        # Center on parent
        self.win.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - self.win.winfo_width()) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - self.win.winfo_height()) // 2
        self.win.geometry(f"+{x}+{y}")

        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.parent.wait_window(self.win)

    def _select_all(self):
        for var in self._vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self._vars.values():
            var.set(False)

    def _save(self):
        selected = [col for col, var in self._vars.items() if var.get()]
        if not selected:
            messagebox.showwarning(
                "No Columns",
                "At least one column must be selected.",
                parent=self.win,
            )
            return
        save_columns(selected)
        self.result = selected
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()
