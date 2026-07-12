"""
database_sync.py — Sync Shopify orders into the local SQLite database.

During sync, each line item is enriched with:
  - Resolved color  (via data_utils.extract_color_robust)
  - Resolved size   (via data_utils.extract_size_robust)
  - Image URL       (via image_resolver.ProductImageResolver)

These enriched values are stored as ad-hoc keys on the line item dict
(_resolved_color, _resolved_size, _image_url) before batch-inserting.
"""

import threading
from typing import Callable, Optional

from .config import Config
from .shopify_api import ShopifyAPI
from .image_resolver import ProductImageResolver
from .image_cache_manager import get_image_cache
from .data_utils import extract_color_robust, extract_size_robust
from .database import DatabaseManager, get_db
from .utils import logger


class DatabaseSync:
    """Orchestrates Shopify → SQLite sync with progress reporting."""

    def __init__(
        self,
        api: Optional[ShopifyAPI] = None,
        resolver: Optional[ProductImageResolver] = None,
    ):
        self.api = api or ShopifyAPI()
        self.resolver = resolver or ProductImageResolver(self.api)
        self.db: DatabaseManager = get_db()
        self.image_cache = get_image_cache()
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public sync methods
    # ------------------------------------------------------------------

    def sync_all(
        self,
        progress_fn: Optional[Callable] = None,
        log_fn: Optional[Callable] = None,
        status_fn: Optional[Callable] = None,
    ) -> int:
        """Sync ALL orders from Shopify into the local database."""
        self._stop_event.clear()
        self._log(log_fn, "Starting full database sync (all orders)...")
        self._status(status_fn, "Syncing all orders...")

        try:
            # Fetch all orders (using a large count to get everything)
            raw_orders = self.api.get_orders(
                count=100000,
                status="any",
                financial_status="any",
            )
            return self._process_and_save(raw_orders, "full", progress_fn, log_fn, status_fn)
        except Exception as exc:
            self._log(log_fn, f"SYNC ERROR: {exc}")
            return 0

    def sync_latest(
        self,
        count: int = 250,
        progress_fn: Optional[Callable] = None,
        log_fn: Optional[Callable] = None,
        status_fn: Optional[Callable] = None,
    ) -> int:
        """Sync the latest N orders."""
        self._stop_event.clear()
        self._log(log_fn, f"Starting latest-order sync ({count} orders)...")
        self._status(status_fn, f"Syncing latest {count} orders...")

        try:
            raw_orders = self.api.get_orders(
                count=count,
                status="any",
                financial_status="any",
            )
            return self._process_and_save(raw_orders, "latest", progress_fn, log_fn, status_fn)
        except Exception as exc:
            self._log(log_fn, f"SYNC ERROR: {exc}")
            return 0

    def request_stop(self):
        """Signal the sync to stop at the next safe point."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_and_save(
        self,
        raw_orders: list,
        sync_type: str,
        progress_fn: Optional[Callable],
        log_fn: Optional[Callable],
        status_fn: Optional[Callable],
    ) -> int:
        """Enrich each line item with resolved color/size/image, then save to DB."""
        total = len(raw_orders)
        if total == 0:
            self._log(log_fn, "No orders to sync.")
            return 0

        self._log(log_fn, f"Enriching {total} orders with color/size/image...")

        # We attach enriched data directly to the line item dicts
        # so the database layer can read them.
        for idx, order in enumerate(raw_orders):
            if self._stop_event.is_set():
                self._log(log_fn, "Sync stopped by user.")
                break

            line_items = order.get("line_items", [])
            for item in line_items:
                p_id = item.get("product_id")
                v_id = item.get("variant_id")

                # ── Resolve product (for color/size extraction) ───────────
                product = None
                if p_id:
                    # Check image cache negative first
                    if self.image_cache.is_negative(p_id):
                        item["_image_url"] = ""
                        item["_resolved_color"] = extract_color_robust(item, None)
                        item["_resolved_size"] = extract_size_robust(item, None)
                        continue

                    # Try resolver cache
                    product = self.resolver._product_cache.get(p_id)
                    if product is None:
                        product = self.api.get_product(p_id)
                        if product:
                            self.resolver._product_cache[p_id] = product
                        else:
                            self.resolver._product_cache[p_id] = "__NO_IMAGE__"
                            product = None

                # ── Resolve color & size ──────────────────────────────────
                item["_resolved_color"] = extract_color_robust(item, product)
                item["_resolved_size"] = extract_size_robust(item, product)

                # ── Resolve image URL (use resolver) ──────────────────────
                url = self.resolver.get_image_url(item)
                item["_image_url"] = url

                # ── Update image cache ───────────────────────────────────
                if url and p_id:
                    self.image_cache.set_positive(p_id, url, v_id)
                elif not url and p_id:
                    self.image_cache.set_negative(p_id)

            # Update progress
            if progress_fn:
                progress_val = int((idx + 1) / total * 80)  # 0-80%
                progress_fn(progress_val)
            if status_fn:
                status_fn(f"Syncing {idx + 1}/{total}...")
            if log_fn and (idx + 1) % 50 == 0:
                self._log(log_fn, f"Processed {idx + 1}/{total} orders...")

        # ── Save to database ─────────────────────────────────────────────
        self._log(log_fn, f"Saving {total} orders to database...")
        self._status(status_fn, "Writing to database...")
        if progress_fn:
            progress_fn(85)

        saved = self.db.save_orders(raw_orders, sync_type=sync_type)

        if progress_fn:
            progress_fn(100)
        self._log(log_fn, f"Sync complete: {saved} orders saved to database.")
        self._status(status_fn, f"Sync complete — {saved} orders in DB")

        return saved

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log(log_fn, msg):
        logger.info(msg)
        if log_fn:
            log_fn(msg)

    @staticmethod
    def _status(status_fn, msg):
        if status_fn:
            status_fn(msg)
