"""
image_cache_manager.py — Persistent image cache across application sessions.

Tracks two caches on disk (JSON):
  - Positive cache :  "product_variant_id" -> local file path
  - Negative cache :  product_id -> "__NO_IMAGE__"

This prevents re-downloading images that have already been fetched
across application restarts.
"""

import json
import threading
from pathlib import Path
from typing import Optional

from .utils import logger
from .image_resolver import _NO_IMAGE

CACHE_FILE = "image_cache.json"


class ImageCacheManager:
    """Thread-safe, persistent image cache manager."""

    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = Path(cache_file)
        self._lock = threading.Lock()
        self._positive: dict[str, str] = {}  # "product_variant" -> local path
        self._negative: dict[int, str] = {}  # product_id -> sentinel
        self._loaded = False

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _ensure_loaded(self):
        if not self._loaded:
            self.load()

    def load(self):
        """Load cache from disk."""
        if self._loaded:
            return
        self._loaded = True
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
            self._positive = data.get("positive", {})
            raw_negative = data.get("negative", {})
            self._negative = {int(k): v for k, v in raw_negative.items()}
            logger.info(
                f"Image cache loaded: {len(self._positive)} positive, "
                f"{len(self._negative)} negative entries."
            )
        except Exception as exc:
            logger.error(f"Failed to load image cache: {exc}")
            self._positive = {}
            self._negative = {}

    def save(self):
        """Write cache to disk."""
        try:
            data = {
                "positive": self._positive,
                "negative": {str(k): v for k, v in self._negative.items()},
            }
            with open(self.cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.error(f"Failed to save image cache: {exc}")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_cached(self, product_id: int, variant_id: Optional[int] = None) -> Optional[str]:
        """Return the local path for a cached image, or None.

        Checks variant-specific cache first, then generic product cache.
        """
        self._ensure_loaded()
        with self._lock:
            # Check variant-specific
            if variant_id:
                key = f"{product_id}_{variant_id}"
                path = self._positive.get(key)
                if path and Path(path).exists():
                    return path
            # Check generic product-level
            key = f"{product_id}"
            path = self._positive.get(key)
            if path and Path(path).exists():
                return path
        return None

    def is_negative(self, product_id: int) -> bool:
        """Return True if product_id is known to have no images."""
        self._ensure_loaded()
        with self._lock:
            return product_id in self._negative

    def set_positive(self, product_id: int, local_path: str, variant_id: Optional[int] = None):
        """Record a successful image download."""
        self._ensure_loaded()
        with self._lock:
            key = f"{product_id}_{variant_id}" if variant_id else f"{product_id}"
            if key in self._positive and self._positive[key] == local_path:
                return  # Already recorded
            self._positive[key] = local_path
            # Also remove from negative cache if present
            self._negative.pop(product_id, None)
        self.save()

    def set_negative(self, product_id: int):
        """Record that a product has no image available."""
        self._ensure_loaded()
        with self._lock:
            if product_id not in self._negative:
                self._negative[product_id] = _NO_IMAGE
        self.save()

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._positive.clear()
            self._negative.clear()
        self.save()
        logger.info("Image cache cleared.")

    def stats(self) -> dict:
        """Return cache statistics."""
        self._ensure_loaded()
        with self._lock:
            return {
                "positive_count": len(self._positive),
                "negative_count": len(self._negative),
            }


# ── Singleton convenience ───────────────────────────────────────────────────

_instance: Optional[ImageCacheManager] = None


def get_image_cache() -> ImageCacheManager:
    global _instance
    if _instance is None:
        _instance = ImageCacheManager()
        _instance.load()
    return _instance
