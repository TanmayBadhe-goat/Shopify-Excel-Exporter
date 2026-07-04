"""
image_resolver.py — Intelligent, multi-level product image resolver.

Priority order (fastest / cheapest first):
  L1  Image already embedded in the order line item  → use immediately
  L2  Product already in the in-memory product cache → reuse cached data
  L3  Fetch the product from Shopify once            → cache it
  L4  Variant-specific image (exact match by image_id)
  L5  Product featured image
  L6  First image in the product images array
  L7  Nothing found → record in negative cache so we never retry

Performance guarantees
  • Each unique product_id is fetched at most ONCE per export session.
  • Products with no image anywhere are recorded so future rows skip the lookup.
  • The file-level download cache (image_paths in gui.py) is unchanged.
"""

from utils import logger


# Sentinel stored in the negative cache for products that have no image.
_NO_IMAGE = "__NO_IMAGE__"


class ProductImageResolver:
    """Resolves the best available image URL for a Shopify line item."""

    def __init__(self, api):
        """
        Parameters
        ----------
        api : ShopifyAPI
            A live ShopifyAPI instance used for product fetches (Level 3).
        """
        self._api = api
        # product_id -> full product dict (or _NO_IMAGE sentinel)
        self._product_cache: dict = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_image_url(self, line_item: dict) -> str:
        """Return the best image URL for *line_item*, or '' if none exists.

        Priority:
          1. Variant-specific image  (matches the exact ordered color)
          2. Line item image         (provided by Shopify in the order)
          3. Product featured image
          4. First product gallery image
        """

        product_id = line_item.get("product_id")
        variant_id = line_item.get("variant_id")

        if not product_id:
            # No product — try line item image as last resort
            line_item_src = (line_item.get("image") or {}).get("src", "")
            return line_item_src

        # ── Negative cache pre-check ────────────────────────────────────
        cached = self._product_cache.get(product_id)
        if cached == _NO_IMAGE:
            logger.info(f"[IMG] No image exists for product {product_id} (negative cache)")
            return ""

        # ── Ensure product is loaded (from cache or Shopify) ────────────
        if cached is not None and cached != _NO_IMAGE:
            product = cached
        else:
            product = self._fetch_product(product_id)
            if product is None:
                # Product fetch failed — try line item image as fallback
                line_item_src = (line_item.get("image") or {}).get("src", "")
                if line_item_src:
                    logger.info(f"[IMG] Using line item image (product unavailable) for product {product_id}")
                return line_item_src

        # ── Priority 1: Variant-specific image ──────────────────────────
        if variant_id:
            url = self._variant_image_url(product, variant_id)
            if url:
                logger.info(f"[IMG] P1 – Using variant image for product {product_id} / variant {variant_id}")
                return url

        # ── Priority 2: Line item image from the order ──────────────────
        line_item_src = (line_item.get("image") or {}).get("src", "")
        if line_item_src:
            logger.info(f"[IMG] P2 – Using line item image for product {product_id}")
            return line_item_src

        # ── Priority 3: Product featured image ──────────────────────────
        featured_src = (product.get("image") or {}).get("src", "")
        if featured_src:
            logger.info(f"[IMG] P3 – Using featured product image for product {product_id}")
            return featured_src

        # ── Priority 4: First image in the images array ─────────────────
        for img in product.get("images") or []:
            src = img.get("src", "")
            if src:
                logger.info(f"[IMG] P4 – Using first gallery image for product {product_id}")
                return src

        # ── No image anywhere — record in negative cache ────────────────
        logger.info(f"[IMG] No image exists for product {product_id}")
        self._product_cache[product_id] = _NO_IMAGE
        return ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_product(self, product_id) -> dict | None:
        """
        Call the Shopify Products API once and cache the result.
        Returns the product dict, or None on any error.
        """
        logger.info(f"[IMG] L3 – Fetching product {product_id} from Shopify")
        try:
            product = self._api.get_product(product_id)
            if product:
                self._product_cache[product_id] = product
                logger.info(f"[IMG] L3 – Product {product_id} cached successfully")
                return product
            else:
                logger.warning(f"[IMG] L3 – Product {product_id} not found or has been deleted")
                self._product_cache[product_id] = _NO_IMAGE
                return None
        except Exception as exc:
            logger.error(f"[IMG] L3 – Could not fetch product {product_id}: {exc}")
            self._product_cache[product_id] = _NO_IMAGE
            return None

    @staticmethod
    def _variant_image_url(product: dict, variant_id) -> str:
        """
        Return the image URL for *variant_id* if that variant has a dedicated
        image assigned (linked via image_id), otherwise return ''.
        """
        # Build a map of image_id → src for fast lookup
        image_map = {
            img["id"]: img.get("src", "")
            for img in (product.get("images") or [])
            if "id" in img
        }

        for variant in product.get("variants") or []:
            if variant.get("id") == variant_id:
                image_id = variant.get("image_id")
                if image_id and image_id in image_map:
                    return image_map[image_id]
                break  # Found the variant but it has no image_id

        return ""
