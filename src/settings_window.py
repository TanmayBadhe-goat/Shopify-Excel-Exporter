"""
settings_window.py — Multi-tab settings dialog.

Tabs:
  - General   : Store URL, API version
  - Export    : Column selection, image defaults, export directory
  - Size      : Size mapping editor (inline Treeview)
  - Database  : Sync status, clear button, resync option
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from threading import Thread
from typing import Callable, Optional

from .config import Config
from .database import get_db
from .image_cache_manager import get_image_cache
from .column_selector import ColumnSelectorDialog, get_enabled_columns
from .size_mapping_ui import SizeMappingEditor, load_size_mapping, apply_size_mapping_to_utils
from .utils import logger


class SettingsWindow:
    """Modal settings dialog with Notebook tabs."""

    def __init__(
        self,
        parent,
        on_sync_all: Optional[Callable] = None,
        on_sync_latest: Optional[Callable] = None,
    ):
        self.parent = parent
        self.on_sync_all = on_sync_all
        self.on_sync_latest = on_sync_latest
        self._build()

    def _build(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("Settings")
        self.win.geometry("650x520")
        self.win.transient(self.parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        main_frame = ttk.Frame(self.win, padding=15)
        main_frame.pack(fill="both", expand=True)

        # ── Notebook ────────────────────────────────────────────────────
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        self._tab_general = ttk.Frame(notebook, padding=15)
        self._tab_export = ttk.Frame(notebook, padding=15)
        self._tab_size = ttk.Frame(notebook, padding=15)
        self._tab_database = ttk.Frame(notebook, padding=15)

        notebook.add(self._tab_general, text="  General  ")
        notebook.add(self._tab_export, text="  Export  ")
        notebook.add(self._tab_size, text="  Size Mapping  ")
        notebook.add(self._tab_database, text="  Database  ")

        # ── Build each tab ──────────────────────────────────────────────
        self._build_general()
        self._build_export()
        self._build_size()
        self._build_database()

        # ── Close button ────────────────────────────────────────────────
        ttk.Button(
            main_frame,
            text="Close",
            command=self._close,
            bootstyle="secondary",
            width=20,
        ).pack(pady=(10, 0))

        # Center on parent
        self.win.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - self.win.winfo_width()) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - self.win.winfo_height()) // 2
        self.win.geometry(f"+{x}+{y}")

        self.parent.wait_window(self.win)

    # ── Tab: General ──────────────────────────────────────────────────────

    def _build_general(self):
        ttk.Label(self._tab_general, text="Store URL:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=5
        )
        store_var = tk.StringVar(value=Config.STORE_URL or "")
        store_entry = ttk.Entry(self._tab_general, textvariable=store_var, width=40)
        store_entry.grid(row=0, column=1, sticky="w", pady=5, padx=10)
        store_entry.config(state="readonly")
        ttk.Label(
            self._tab_general,
            text="(Set in .env or the Store Configuration field above)",
            font=("Helvetica", 8, "italic"),
        ).grid(row=0, column=2, sticky="w", padx=5)

        ttk.Label(self._tab_general, text="API Version:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.api_var = tk.StringVar(value=Config.API_VERSION)
        api_entry = ttk.Entry(self._tab_general, textvariable=self.api_var, width=15)
        api_entry.grid(row=1, column=1, sticky="w", pady=5, padx=10)

        ttk.Label(self._tab_general, text="App Version:", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=5
        )
        ttk.Label(self._tab_general, text="v3.5 + Database Edition").grid(
            row=2, column=1, sticky="w", pady=5, padx=10
        )

        ttk.Separator(self._tab_general, orient="horizontal").grid(
            row=3, column=0, columnspan=3, sticky="we", pady=15
        )

        ttk.Label(
            self._tab_general,
            text="Log File: app.log",
            font=("Helvetica", 9),
        ).grid(row=4, column=0, columnspan=3, sticky="w")

    # ── Tab: Export ──────────────────────────────────────────────────────

    def _build_export(self):
        # Column selection
        ttk.Label(self._tab_export, text="Export Columns:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=5
        )

        self.col_count_label = ttk.Label(
            self._tab_export,
            text=f"{len(get_enabled_columns())} columns enabled",
            font=("Helvetica", 9),
        )
        self.col_count_label.grid(row=0, column=1, sticky="w", pady=5, padx=10)

        ttk.Button(
            self._tab_export,
            text="Customize Columns",
            command=self._open_column_selector,
            bootstyle="info-outline",
        ).grid(row=0, column=2, sticky="w", padx=5)

        # Include images by default
        ttk.Label(self._tab_export, text="Images:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", pady=10
        )
        self.include_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self._tab_export,
            text="Include product images by default",
            variable=self.include_images_var,
            bootstyle="round-toggle",
        ).grid(row=1, column=1, columnspan=2, sticky="w", padx=10)

        # Export directory
        ttk.Label(self._tab_export, text="Export Folder:", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.export_dir_var = tk.StringVar(value="exports")
        ttk.Entry(
            self._tab_export, textvariable=self.export_dir_var, width=30
        ).grid(row=2, column=1, sticky="w", pady=5, padx=10)
        ttk.Button(
            self._tab_export,
            text="Browse",
            command=self._browse_export_dir,
            bootstyle="secondary-outline",
        ).grid(row=2, column=2, sticky="w", padx=5)

    def _open_column_selector(self):
        ColumnSelectorDialog(self.win)
        self.col_count_label.config(text=f"{len(get_enabled_columns())} columns enabled")

    def _browse_export_dir(self):
        path = filedialog.askdirectory(title="Select Export Directory", parent=self.win)
        if path:
            self.export_dir_var.set(path)

    # ── Tab: Size Mapping ────────────────────────────────────────────────

    def _close(self):
        """Save settings before closing."""
        # Save API version if changed
        new_api = self.api_var.get().strip()
        if new_api and new_api != Config.API_VERSION:
            Config.API_VERSION = new_api
            Config.save_settings()
            logger.info(f"API version saved: {new_api}")
        self.win.destroy()

    def _build_size(self):
        self.size_editor = SizeMappingEditor(self._tab_size)
        self.size_editor.pack(fill="both", expand=True)

    # ── Tab: Database ────────────────────────────────────────────────────

    def _build_database(self):
        db = get_db()

        # Status
        status_frame = ttk.LabelFrame(self._tab_database, text=" Database Status ", padding=12)
        status_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(status_frame, text="Status:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        status_text = "Connected" if db.is_available else "Unavailable"
        ttk.Label(
            status_frame,
            text=status_text,
            font=("Helvetica", 10),
            foreground="green" if db.is_available else "red",
        ).grid(row=0, column=1, sticky="w", padx=10)

        ttk.Label(status_frame, text="Orders Stored:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.db_count_label = ttk.Label(
            status_frame,
            text=str(db.order_count()),
            font=("Helvetica", 10),
        )
        self.db_count_label.grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(status_frame, text="Last Sync:", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=5
        )
        last_sync = db.get_last_sync()
        sync_info = last_sync.get("sync_end", "Never") if last_sync else "Never"
        self.db_sync_label = ttk.Label(
            status_frame,
            text=sync_info,
            font=("Helvetica", 9),
        )
        self.db_sync_label.grid(row=2, column=1, sticky="w", padx=10)

        # Actions
        actions_frame = ttk.LabelFrame(self._tab_database, text=" Actions ", padding=12)
        actions_frame.pack(fill="x")

        ttk.Button(
            actions_frame,
            text="Sync All Orders (Full)",
            command=self._trigger_sync_all,
            bootstyle="primary",
            width=25,
        ).pack(anchor="w", pady=4)

        ttk.Button(
            actions_frame,
            text="Sync Latest 250 Orders",
            command=self._trigger_sync_latest,
            bootstyle="primary-outline",
            width=25,
        ).pack(anchor="w", pady=4)

        ttk.Separator(actions_frame, orient="horizontal").pack(fill="x", pady=8)

        ttk.Button(
            actions_frame,
            text="Clear All Database Data",
            command=self._clear_database,
            bootstyle="danger-outline",
            width=25,
        ).pack(anchor="w", pady=4)

        # Image cache stats
        ttk.Separator(actions_frame, orient="horizontal").pack(fill="x", pady=8)

        cache = get_image_cache()
        cache_stats = cache.stats()
        ttk.Label(
            actions_frame,
            text=f"Image cache: {cache_stats['positive_count']} positive, "
                 f"{cache_stats['negative_count']} negative entries.",
            font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", pady=2)

        ttk.Button(
            actions_frame,
            text="Clear Image Cache",
            command=self._clear_image_cache,
            bootstyle="secondary-outline",
            width=25,
        ).pack(anchor="w", pady=4)

    def _trigger_sync_all(self):
        if self.on_sync_all:
            self.win.destroy()
            self.on_sync_all()

    def _trigger_sync_latest(self):
        if self.on_sync_latest:
            self.win.destroy()
            self.on_sync_latest()

    def _clear_database(self):
        if messagebox.askyesno(
            "Clear Database",
            "This will permanently delete all locally stored orders.\n"
            "This does NOT affect your Shopify store.\n\n"
            "Continue?",
            parent=self.win,
        ):
            db = get_db()
            db.clear_all()
            self.db_count_label.config(text="0")
            self.db_sync_label.config(text="Never")
            logger.info("Database cleared from settings.")
            messagebox.showinfo("Cleared", "Database cleared successfully.", parent=self.win)

    def _clear_image_cache(self):
        if messagebox.askyesno(
            "Clear Image Cache",
            "This will remove all cached image references.\n"
            "Images will need to be re-downloaded on next export.\n\n"
            "Continue?",
            parent=self.win,
        ):
            get_image_cache().clear()
            messagebox.showinfo(
                "Cleared",
                "Image cache cleared successfully.\n"
                "Images will be re-downloaded on next export.",
                parent=self.win,
            )
