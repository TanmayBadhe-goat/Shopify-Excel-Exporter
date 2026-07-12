"""
size_mapping_ui.py — Inline editor for size mapping rules.

Provides a reusable ttk.Frame that displays size mapping entries
(from size_mapping.json) in a Treeview with add / edit / delete
capability. Used inside the Settings window (Size Mapping tab).
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
from typing import Callable, Optional

from .utils import logger

DEFAULT_MAPPING_PATH = Path("size_mapping.json")


def load_size_mapping(path: Path = DEFAULT_MAPPING_PATH) -> dict:
    """Load size mapping from JSON file. Returns empty dict on failure."""
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.error(f"Failed to load size mapping: {exc}")
        return {}


def save_size_mapping(mapping: dict, path: Path = DEFAULT_MAPPING_PATH):
    """Save size mapping to JSON file."""
    try:
        with open(path, "w") as f:
            json.dump(mapping, f, indent=2, sort_keys=True)
    except Exception as exc:
        logger.error(f"Failed to save size mapping: {exc}")


def apply_size_mapping_to_utils(mapping: dict):
    """Apply loaded mapping to size_utils._SIZE_UP at runtime.

    This is a non-destructive update: the JSON mapping keys are merged
    into the existing _SIZE_UP dict. Existing entries are overwritten
    if they exist in the JSON, but no entries are removed.
    """
    from . import size_utils
    size_utils._SIZE_UP.update(mapping)


class SizeMappingEditor(ttk.Frame):
    """Treeview-based editor for size mapping rules."""

    def __init__(
        self,
        parent,
        mapping_path: Path = DEFAULT_MAPPING_PATH,
        change_callback: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.mapping_path = mapping_path
        self.change_callback = change_callback
        self.mapping: dict = {}
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Treeview ───────────────────────────────────────────────────
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        columns = ("original", "upsized")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("original", text="Original Size")
        self.tree.heading("upsized", text="Upsized To")
        self.tree.column("original", width=180, anchor="center")
        self.tree.column("upsized", width=180, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # ── Toolbar ─────────────────────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(8, 0))

        ttk.Button(toolbar, text="Add Rule", command=self._add_rule).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit Rule", command=self._edit_rule).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete Rule", command=self._delete_rule).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Reset to Defaults", command=self._reset_defaults).pack(side="left", padx=20)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load(self):
        self.mapping = load_size_mapping(self.mapping_path)
        self._refresh_tree()

    def _refresh_tree(self):
        """Clear and repopulate the Treeview from self.mapping."""
        self.tree.delete(*self.tree.get_children())
        for original, upsized in sorted(self.mapping.items()):
            self.tree.insert("", "end", values=(original, upsized))

    def _save(self):
        """Save mapping to JSON and refresh the tree."""
        save_size_mapping(self.mapping, self.mapping_path)
        apply_size_mapping_to_utils(self.mapping)
        self._refresh_tree()
        if self.change_callback:
            self.change_callback()

    # ------------------------------------------------------------------
    # CRUD Actions
    # ------------------------------------------------------------------

    def _add_rule(self):
        original = simpledialog.askstring("Add Rule", "Original size:", parent=self)
        if not original:
            return
        upsized = simpledialog.askstring("Add Rule", f"Upsized size for '{original}':", parent=self)
        if not upsized:
            return

        original = original.strip().upper()
        upsized = upsized.strip().upper()
        self.mapping[original] = upsized
        self._save()
        logger.info(f"Size mapping added: {original} -> {upsized}")

    def _edit_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Edit Rule", "Please select a rule to edit.", parent=self)
            return

        item = self.tree.item(selected[0])
        original, current_upsized = item["values"]

        new_original = simpledialog.askstring(
            "Edit Rule", "Original size:", initialvalue=original, parent=self
        )
        if not new_original:
            return
        new_upsized = simpledialog.askstring(
            "Edit Rule", f"Upsized size for '{new_original}':",
            initialvalue=current_upsized, parent=self
        )
        if not new_upsized:
            return

        new_original = new_original.strip().upper()
        new_upsized = new_upsized.strip().upper()

        # Remove old key if it changed
        if new_original != original and original in self.mapping:
            del self.mapping[original]

        self.mapping[new_original] = new_upsized
        self._save()
        logger.info(f"Size mapping updated: {new_original} -> {new_upsized}")

    def _delete_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Delete Rule", "Please select a rule to delete.", parent=self)
            return

        item = self.tree.item(selected[0])
        original = item["values"][0]

        if messagebox.askyesno("Confirm Delete", f"Delete rule '{original}'?", parent=self):
            self.mapping.pop(original, None)
            self._save()
            logger.info(f"Size mapping deleted: {original}")

    def _reset_defaults(self):
        if not messagebox.askyesno(
            "Reset Defaults",
            "Reset size mapping to factory defaults?",
            parent=self,
        ):
            return
        # Remove the JSON file so the default mapping from size_utils is used
        if self.mapping_path.exists():
            self.mapping_path.unlink()
        self.mapping = {}
        self._refresh_tree()
        logger.info("Size mapping reset to defaults.")
        if self.change_callback:
            self.change_callback()
