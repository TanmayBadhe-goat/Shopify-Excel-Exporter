"""
customer_search.py — Database-backed search with automatic Shopify API fallback.

Search modes:
  1. Product search — by product name, multiple keywords, partial, case-insensitive
  2. Customer search — by name, email, phone
  3. Order search — by order number

Fallback logic:
  - If the local database has data → search database
  - If the local database is empty → fall back to Shopify API
  - User never sees an error from an empty database
"""

import threading
from typing import Callable, Optional

from .database import get_db
from .shopify_api import ShopifyAPI
from .product_search import search_product_orders
from .image_resolver import ProductImageResolver
from .utils import logger


class DatabaseSearch:
    """Unified search with automatic DB → API fallback."""

    def __init__(self, api: Optional[ShopifyAPI] = None):
        self.db = get_db()
        self.api = api

    # ------------------------------------------------------------------
    # Product search
    # ------------------------------------------------------------------

    def search_products(
        self,
        keyword: str,
        order_min: Optional[int] = None,
        order_max: Optional[int] = None,
        log_fn: Optional[Callable] = None,
        progress_fn: Optional[Callable] = None,
        status_fn: Optional[Callable] = None,
    ) -> list:
        """Search products. Database first, Shopify API fallback if empty."""
        self._log(log_fn, f"Searching products for: '{keyword}'")

        if not self.db.is_empty():
            self._log(log_fn, "Searching local database...")
            results = self.db.search_products(keyword)
            if results:
                self._log(log_fn, f"Found {len(results)} results in database.")
                return results
            self._log(log_fn, "No results in database. Falling back to Shopify API...")
        else:
            self._log(log_fn, "Database is empty. Searching Shopify directly...")

        # ── Fallback to Shopify API ─────────────────────────────────────
        return self._search_shopify_products(
            keyword, order_min, order_max, log_fn, progress_fn, status_fn
        )

    def _search_shopify_products(
        self,
        keyword: str,
        order_min: Optional[int],
        order_max: Optional[int],
        log_fn: Optional[Callable],
        progress_fn: Optional[Callable],
        status_fn: Optional[Callable],
    ) -> list:
        """Fallback: use existing product_search.search_product_orders()."""
        try:
            if self.api is None:
                self.api = ShopifyAPI()
            resolver = ProductImageResolver(self.api)
            results, _ = search_product_orders(
                api=self.api,
                search_term=keyword,
                resolver=resolver,
                order_min=order_min,
                order_max=order_max,
                log_fn=log_fn,
                progress_fn=progress_fn,
                status_fn=status_fn,
            )
            return results
        except Exception as exc:
            self._log(log_fn, f"Shopify API search error: {exc}")
            return []

    # ------------------------------------------------------------------
    # Customer search
    # ------------------------------------------------------------------

    def search_customers(
        self,
        query: str,
        log_fn: Optional[Callable] = None,
    ) -> list:
        """Search customers by name, email, or phone."""
        self._log(log_fn, f"Searching customers for: '{query}'")

        if not self.db.is_empty():
            results = self.db.search_customers(query)
            if results:
                self._log(log_fn, f"Found {len(results)} customer results in database.")
                return results

        # Fallback: scan orders from API for customer match
        self._log(log_fn, "Database empty or no match. Trying Shopify API...")
        return self._search_shopify_customers(query, log_fn)

    def _search_shopify_customers(self, query: str, log_fn: Optional[Callable]) -> list:
        """Fallback: paginate through orders and filter by customer."""
        try:
            if self.api is None:
                self.api = ShopifyAPI()
            q = query.lower()
            results = []
            page_info = None
            max_pages = 10  # Safety limit to avoid infinite pagination
            page_count = 0

            while page_count < max_pages:
                page_count += 1
                if page_info:
                    params = {"limit": 250, "page_info": page_info, "status": "any"}
                else:
                    params = {"limit": 250, "status": "any", "financial_status": "any"}

                try:
                    response = self.api._make_request("orders.json", params=params)
                except Exception as exc:
                    self._log(log_fn, f"Error fetching customer page {page_count}: {exc}")
                    break

                data = response.json()
                orders = data.get("orders", [])
                if not orders:
                    break

                for order in orders:
                    customer = order.get("customer") or {}
                    name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                    email = customer.get("email", "") or ""
                    phone = customer.get("phone", "") or ""

                    if q in name.lower() or q in email.lower() or q in phone.lower():
                        for item in order.get("line_items", []):
                            results.append({
                                "order_number": f"#{order.get('order_number')}",
                                "order_date": (order.get("created_at") or "").split("T")[0],
                                "customer_name": name,
                                "customer_email": email,
                                "phone_number": phone,
                                "product_name": item.get("title"),
                                "variant_name": item.get("variant_title", ""),
                                "product_id": item.get("product_id"),
                                "variant_id": item.get("variant_id"),
                            })

                    # Stop early if we have enough results
                    if len(results) >= 500:
                        break

                if len(results) >= 500:
                    self._log(log_fn, "Reached 500 customer result limit.")
                    break

                link_header = response.headers.get("Link")
                page_info = self.api._get_next_page_info(link_header)
                if not page_info:
                    break

            self._log(log_fn, f"Found {len(results)} customer results from Shopify.")
            return results
        except Exception as exc:
            self._log(log_fn, f"Shopify customer search error: {exc}")
            return []

    # ------------------------------------------------------------------
    # Order search
    # ------------------------------------------------------------------

    def search_order(
        self,
        order_number: int,
        log_fn: Optional[Callable] = None,
    ) -> list:
        """Search for a specific order number."""
        self._log(log_fn, f"Searching for order #{order_number}")

        if not self.db.is_empty():
            results = self.db.search_order_by_number(order_number)
            if results:
                self._log(log_fn, f"Found {len(results)} items for order #{order_number} in database.")
                return results

        # Fallback to API
        return self._search_shopify_order(order_number, log_fn)

    def _search_shopify_order(self, order_number: int, log_fn: Optional[Callable]) -> list:
        """Fallback: fetch a specific order from Shopify."""
        try:
            if self.api is None:
                self.api = ShopifyAPI()
            orders = self.api.get_orders(
                order_min=order_number,
                order_max=order_number,
                status="any",
                financial_status="any",
            )
            results = []
            for order in orders:
                if order.get("order_number") == order_number:
                    customer = order.get("customer") or {}
                    name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                    for item in order.get("line_items", []):
                        results.append({
                            "order_number": f"#{order_number}",
                            "order_date": (order.get("created_at") or "").split("T")[0],
                            "customer_name": name,
                            "customer_email": customer.get("email", ""),
                            "phone_number": customer.get("phone", ""),
                            "product_name": item.get("title"),
                            "variant_name": item.get("variant_title", ""),
                            "price": item.get("price"),
                            "product_id": item.get("product_id"),
                            "variant_id": item.get("variant_id"),
                        })
            self._log(log_fn, f"Found {len(results)} items for order #{order_number}.")
            return results
        except Exception as exc:
            self._log(log_fn, f"Shopify order search error: {exc}")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log(log_fn, msg):
        logger.info(msg)
        if log_fn:
            log_fn(msg)
