"""
order_data_builder.py — Builds enriched order data dicts from Shopify order objects.

Eliminates the duplicated data-preparation logic that was repeated across
export_excel(), run_remittance_report(), and show_search_results() in gui.py.
"""

from typing import Callable, Optional
from .data_utils import extract_color_robust, extract_size_robust
from .utils import logger


class OrderDataBuilder:
    """Construct uniformly structured order-item dicts from Shopify orders."""

    @staticmethod
    def build_item_data(order: dict, item: dict, product: Optional[dict] = None) -> dict:
        """Build a single order-item data dict.

        Parameters
        ----------
        order : dict
            Raw Shopify order dict.
        item : dict
            A line_item from the order.
        product : dict or None
            Pre-resolved product (for color/size extraction). Can be None.

        Returns
        -------
        dict with keys:
            order_number, customer_name, customer_email, phone_number,
            product_name, variant_name, color, size, price, payment_status,
            product_id, variant_id
        """
        customer = order.get("customer") or {}
        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        p_id = item.get("product_id")

        return {
            "order_number": f"#{order.get('order_number')}",
            "customer_name": name,
            "customer_email": customer.get("email", ""),
            "phone_number": customer.get("phone", ""),
            "product_name": item.get("title"),
            "variant_name": item.get("variant_title"),
            "color": extract_color_robust(item, product),
            "size": extract_size_robust(item, product),
            "price": item.get("price"),
            "payment_status": order.get("financial_status", ""),
            "product_id": p_id,
            "variant_id": item.get("variant_id"),
        }

    @classmethod
    def build_all_items(
        cls,
        orders: list,
        product_cache: Optional[dict] = None,
    ) -> list:
        """Build order-item data for ALL line items across ALL orders.

        Parameters
        ----------
        orders : list
            Raw Shopify order dicts.
        product_cache : dict or None
            Optional product cache (product_id -> product dict) for color/size.

        Returns
        -------
        list of item-data dicts, one per line item.
        """
        results = []
        for order in orders:
            for item in order.get("line_items", []):
                p_id = item.get("product_id")
                product = None
                if p_id and product_cache is not None:
                    cached = product_cache.get(p_id)
                    product = cached if cached != "__NO_IMAGE__" else None
                results.append(cls.build_item_data(order, item, product))
        return results

    @staticmethod
    def collect_image_tasks(
        orders: list,
        resolver,
        include_images: bool = True,
    ) -> list:
        """Collect image download tasks for all line items.

        Returns
        -------
        list of (url, file_id) tuples ready for ImageDownloader.
        """
        tasks = []
        if not include_images:
            return tasks
        for order in orders:
            for item in order.get("line_items", []):
                p_id = item.get("product_id")
                v_id = item.get("variant_id")
                if p_id:
                    url = resolver.get_image_url(item)
                    if url:
                        tasks.append((url, f"{p_id}_{v_id}"))
        return tasks

    @staticmethod
    def build_image_paths(
        downloaded: dict,
    ) -> dict:
        """Convert flat download results to {(product_id, variant_id): path} dict."""
        paths = {}
        for fid, path in downloaded.items():
            parts = fid.split("_")
            p_id = int(parts[0])
            v_id = int(parts[1]) if len(parts) > 1 and parts[1] != "None" else None
            paths[(p_id, v_id)] = str(path) if path else None
        return paths
