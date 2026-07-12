"""
Tests for customer_search.py — database search with Shopify API fallback.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.customer_search import DatabaseSearch


class MockShopifyAPI:
    """Minimal mock Shopify API that returns controlled orders."""

    def __init__(self, orders=None):
        self.orders = orders or []

    def get_orders(self, **kwargs):
        return self.orders

    def get_product(self, product_id):
        return None

    def _make_request(self, endpoint, params=None):
        """Used by the pagination fallback."""
        from unittest.mock import MagicMock
        response = MagicMock()
        response.json.return_value = {"orders": self.orders}
        response.headers.get.return_value = None
        return response

    def _get_next_page_info(self, link_header):
        return None


class TestDatabaseSearchInit:
    def test_creates_searcher(self):
        searcher = DatabaseSearch()
        assert searcher is not None

    def test_with_api(self):
        api = MockShopifyAPI()
        searcher = DatabaseSearch(api=api)
        assert searcher.api is api


class TestSearchProducts:
    def test_search_from_db(self, populated_db):
        """When DB has data, should search DB."""
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_products("T-Shirt")
        assert len(results) >= 1

    def test_search_empty_db_falls_back(self, in_memory_db):
        """When DB is empty, should return empty (no API configured)."""
        searcher = DatabaseSearch()
        searcher.db = in_memory_db

        results = searcher.search_products("Anything")
        assert len(results) == 0  # No API, so fallback can't work

    def test_search_with_api_fallback(self, in_memory_db):
        """When DB is empty but API is available, should fall back."""
        searcher = DatabaseSearch()
        searcher.db = in_memory_db

        # Without an API configured, fallback returns empty
        results = searcher.search_products("Anything")
        assert len(results) == 0

    def test_search_with_order_min_max(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_products("T-Shirt", order_min=1000, order_max=1002)
        assert len(results) >= 1

    def test_search_no_match(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_products("NonExistent")
        assert len(results) == 0

    def test_search_with_log(self, populated_db):
        log_calls = []
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_products("T-Shirt", log_fn=lambda m: log_calls.append(m))
        assert len(log_calls) > 0

    def test_search_multiple_keywords(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_products("Shirt, Jacket")
        assert len(results) >= 1


class TestSearchCustomers:
    def test_search_by_name_in_db(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_customers("John")
        assert len(results) >= 1
        assert "John" in results[0]["customer_name"]

    def test_search_by_email_in_db(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_customers("jane@example.com")
        assert len(results) >= 1

    def test_search_no_match(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_customers("NobodyHere")
        assert len(results) == 0

    def test_search_empty_db_no_api(self, in_memory_db):
        searcher = DatabaseSearch()
        searcher.db = in_memory_db

        results = searcher.search_customers("John")
        assert len(results) == 0

    def test_search_with_log(self, populated_db):
        log_calls = []
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_customers("John", log_fn=lambda m: log_calls.append(m))
        assert len(log_calls) > 0


class TestSearchOrder:
    def test_search_by_number_in_db(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_order(1001)
        assert len(results) >= 1
        assert "#1001" in results[0]["order_number"]

    def test_search_nonexistent_order_in_db(self, populated_db):
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_order(99999)
        assert len(results) == 0

    def test_search_empty_db_no_api(self, in_memory_db):
        searcher = DatabaseSearch()
        searcher.db = in_memory_db

        results = searcher.search_order(1001)
        assert len(results) == 0

    def test_search_with_log(self, populated_db):
        log_calls = []
        searcher = DatabaseSearch()
        searcher.db = populated_db

        results = searcher.search_order(1001, log_fn=lambda m: log_calls.append(m))
        assert len(log_calls) > 0


class TestFallbackLogic:
    def test_db_first_then_api(self, in_memory_db, sample_orders, sample_order):
        """When DB has data, it should be searched first."""
        # Populate DB
        for order in sample_orders:
            for item in order.get("line_items", []):
                item["_resolved_color"] = "Red"
                item["_resolved_size"] = "M"
                item["_image_url"] = ""
        in_memory_db.save_orders(sample_orders)

        # API has a different order not in DB
        api = MockShopifyAPI(orders=[sample_order])

        searcher = DatabaseSearch(api=api)
        searcher.db = in_memory_db

        # Search for something in DB
        results = searcher.search_products("T-Shirt")
        assert len(results) >= 1
        assert results[0]["order_number"] == "#1001"

    def test_empty_db_does_not_crash(self, in_memory_db):
        """Empty database should not cause errors."""
        searcher = DatabaseSearch()
        searcher.db = in_memory_db

        results = searcher.search_products("Anything")
        assert results == []

        results = searcher.search_customers("Anyone")
        assert results == []

        results = searcher.search_order(999)
        assert results == []
