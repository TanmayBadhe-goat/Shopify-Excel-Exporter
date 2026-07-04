"""
product_search.py — Search Shopify orders for multiple products within a range.

Paginates through order history, matches line items by multiple product
names (comma-separated, case-insensitive), and filters by order number range.
"""

from shopify_api import ShopifyAPI
from image_downloader import ImageDownloader
from image_resolver import ProductImageResolver
from color_utils import resolve_color
from size_utils import get_next_size
from utils import logger


def search_product_orders(
    api: ShopifyAPI,
    search_term: str,
    resolver: ProductImageResolver,
    downloader: ImageDownloader,
    order_min: int = None,
    order_max: int = None,
    log_fn=None,
    progress_fn=None,
    status_fn=None,
):
    """
    Search Shopify orders for line items whose product name contains
    any of the *search_term* keywords (comma-separated), within the range [order_min, order_max].
    
    NOTE: Image downloads are now skipped during search for performance.
    URLs are collected and can be downloaded in parallel during export.
    """
    def _log(msg):
        # Remove emojis to avoid UnicodeEncodeError on some Windows consoles
        clean_msg = msg.encode('ascii', 'ignore').decode('ascii').strip()
        logger.info(clean_msg)
        if log_fn: log_fn(msg)

    def _progress(val):
        if progress_fn: progress_fn(val)

    def _status(msg):
        if status_fn: status_fn(msg)

    # Support multiple keywords separated by commas
    raw_terms = [t.strip().lower() for t in search_term.split(",") if t.strip()]
    if not raw_terms:
        return [], {}

    results = []
    page_info = None
    page_num = 0
    total_scanned = 0
    
    # Range check helper
    def in_range(num):
        if order_min is not None and num < order_min: return False
        if order_max is not None and num > order_max: return False
        return True

    # Ensure min/max are in correct order for the logic
    if order_min is not None and order_max is not None and order_min > order_max:
        order_min, order_max = order_max, order_min

    _log(f"Searching orders for keywords: {raw_terms} (Range: {order_min} to {order_max})")
    _status("Searching Shopify...")

    while True:
        page_num += 1
        if page_info:
            params = {"limit": 250, "page_info": page_info}
        else:
            params = {
                "limit": 250,
                "status": "any",
                "order": "created_at desc",
            }

        try:
            response = api._make_request("orders.json", params=params)
        except Exception as exc:
            _log(f"Error fetching page {page_num}: {exc}")
            break

        data = response.json()
        orders = data.get("orders", [])
        if not orders: break

        for order in orders:
            total_scanned += 1
            order_number = order.get("order_number")
            
            # ── Range Filtering ──────────────────────────────────────────
            if order_number is not None:
                if order_min is not None and order_number < order_min:
                    _log(f"Reached order #{order_number} (below min {order_min}). Stopping search.")
                    return results, {}
                
                if order_max is not None and order_number > order_max:
                    continue

            order_date = order.get("created_at", "").split("T")[0]
            customer = order.get("customer") or {}
            customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()

            for line_item in order.get("line_items", []):
                product_name = (line_item.get("title") or "").lower()
                
                # ── Multi-keyword match ──────────────────────────────────
                if not any(term in product_name for term in raw_terms):
                    continue

                product_id = line_item.get("product_id")
                variant_id = line_item.get("variant_id")
                variant_title = line_item.get("variant_title") or ""
                quantity = line_item.get("quantity", 0)

                # Fetching color/size robustly
                # We'll fetch the product once to get full options if possible
                product = None
                if product_id:
                    product = resolver._product_cache.get(product_id)
                    if product is None:
                        # Only fetch product if not in cache (Level 3)
                        product = api.get_product(product_id)
                        resolver._product_cache[product_id] = product or "__NO_IMAGE__"

                color = resolve_color(variant_title.split("/")[0].strip()) if "/" in variant_title else resolve_color(variant_title)
                size = get_next_size(variant_title.split("/")[-1].strip()) if "/" in variant_title else ""

                results.append({
                    "order_number": f"#{order_number}",
                    "order_date": order_date,
                    "customer_name": customer_name,
                    "customer_email": customer.get("email", ""),
                    "phone_number": customer.get("phone", ""),
                    "product_name": line_item.get("title"),
                    "variant_name": variant_title,
                    "color": color,
                    "size": size,
                    "quantity": quantity,
                    "price": line_item.get("price"),
                    "payment_status": order.get("financial_status", ""),
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "line_item": line_item # Store full line item for image resolution later
                })

        _status(f"Page {page_num} | {total_scanned} scanned | {len(results)} matches")
        _progress(min(90, page_num * 5))

        link_header = response.headers.get("Link")
        page_info = api._get_next_page_info(link_header)
        if not page_info: break

    _progress(100)
    _status(f"✓ Found {len(results)} matches in {total_scanned} orders")
    return results, {}
