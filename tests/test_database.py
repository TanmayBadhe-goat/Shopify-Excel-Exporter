"""
Tests for database.py — SQLite database layer.
"""

import pytest
from src.database import DatabaseManager, get_db


class TestDatabaseManager:
    def test_singleton(self):
        """DatabaseManager should be a singleton."""
        db1 = DatabaseManager()
        db2 = DatabaseManager()
        assert db1 is db2

    def test_initialize_in_memory(self, in_memory_db):
        assert in_memory_db.is_available is True

    def test_initialize_is_idempotent(self, in_memory_db):
        """Calling initialize twice should not raise."""
        in_memory_db.initialize(":memory:")  # Second call
        assert in_memory_db.is_available is True

    def test_new_db_is_empty(self, in_memory_db):
        assert in_memory_db.is_empty() is True
        assert in_memory_db.order_count() == 0

    def test_no_db_available_graceful(self):
        """Without initialization, methods should return safe defaults."""
        db = DatabaseManager()
        db._initialized = False
        db.conn = None
        assert db.is_available is False
        assert db.is_empty() is True
        assert db.order_count() == 0
        assert db.get_last_sync() == {}


class TestSaveOrders:
    def test_save_empty_list(self, in_memory_db):
        result = in_memory_db.save_orders([])
        assert result == 0
        assert in_memory_db.is_empty() is True

    def test_save_single_order(self, in_memory_db, sample_order):
        for item in sample_order["line_items"]:
            item["_resolved_color"] = "Red"
            item["_resolved_size"] = "M"
            item["_image_url"] = "https://example.com/img.png"

        result = in_memory_db.save_orders([sample_order])
        assert result == 1
        assert in_memory_db.is_empty() is False
        assert in_memory_db.order_count() == 1

    def test_save_multiple_orders(self, in_memory_db, sample_orders):
        for order in sample_orders:
            for item in order["line_items"]:
                item["_resolved_color"] = "Red"
                item["_resolved_size"] = "M"
                item["_image_url"] = ""

        result = in_memory_db.save_orders(sample_orders)
        assert result == 2
        assert in_memory_db.order_count() == 2

    def test_upsert_updates_existing(self, in_memory_db, sample_order):
        """Saving the same order_id twice should update, not duplicate."""
        for item in sample_order["line_items"]:
            item["_resolved_color"] = "Red"
            item["_resolved_size"] = "M"
            item["_image_url"] = ""

        in_memory_db.save_orders([sample_order])

        # Modify and save again
        sample_order["financial_status"] = "refunded"
        in_memory_db.save_orders([sample_order])

        assert in_memory_db.order_count() == 1  # Not duplicated


class TestSearchProducts:
    def test_search_by_product_name(self, populated_db):
        results = populated_db.search_products("T-Shirt")
        assert len(results) >= 1
        assert "T-Shirt" in results[0]["product_name"]

    def test_search_by_partial_name(self, populated_db):
        results = populated_db.search_products("Shirt")
        assert len(results) >= 1

    def test_search_case_insensitive(self, populated_db):
        results = populated_db.search_products("t-shirt")
        assert len(results) >= 1

    def test_search_multiple_keywords(self, populated_db):
        results = populated_db.search_products("T-Shirt, Jacket")
        assert len(results) >= 2

    def test_search_no_match(self, populated_db):
        results = populated_db.search_products("NonExistentProductXYZ")
        assert len(results) == 0

    def test_search_empty_query(self, populated_db):
        results = populated_db.search_products("")
        assert len(results) == 0

    def test_search_with_empty_db(self, in_memory_db):
        results = in_memory_db.search_products("T-Shirt")
        assert len(results) == 0

    def test_search_results_have_expected_keys(self, populated_db):
        results = populated_db.search_products("T-Shirt")
        assert len(results) >= 1
        r = results[0]
        expected_keys = {
            "order_number", "order_date", "customer_name",
            "customer_email", "product_name", "color",
            "size", "price", "payment_status",
        }
        assert expected_keys.issubset(r.keys())


class TestSearchCustomers:
    def test_search_by_name(self, populated_db):
        results = populated_db.search_customers("John")
        assert len(results) >= 1
        assert "John" in results[0]["customer_name"]

    def test_search_by_email(self, populated_db):
        results = populated_db.search_customers("john@example.com")
        assert len(results) >= 1

    def test_search_by_phone(self, populated_db):
        results = populated_db.search_customers("1234567890")
        assert len(results) >= 1

    def test_search_no_match(self, populated_db):
        results = populated_db.search_customers("NobodyHere")
        assert len(results) == 0

    def test_search_empty_query(self, populated_db):
        results = populated_db.search_customers("")
        assert len(results) == 0


class TestSearchOrderByNumber:
    def test_search_by_order_number(self, populated_db):
        results = populated_db.search_order_by_number(1001)
        assert len(results) >= 1
        assert "#1001" in results[0]["order_number"]

    def test_search_nonexistent_order(self, populated_db):
        results = populated_db.search_order_by_number(99999)
        assert len(results) == 0


class TestClearAll:
    def test_clear_removes_all_data(self, populated_db):
        assert populated_db.order_count() > 0
        populated_db.clear_all()
        assert populated_db.order_count() == 0
        assert populated_db.is_empty() is True

    def test_clear_empty_db(self, in_memory_db):
        """Clearing an empty DB should not raise."""
        in_memory_db.clear_all()
        assert in_memory_db.is_empty() is True


class TestSyncMetadata:
    def test_save_records_metadata(self, in_memory_db, sample_order):
        for item in sample_order["line_items"]:
            item["_resolved_color"] = "Red"
            item["_resolved_size"] = "M"
            item["_image_url"] = ""

        in_memory_db.save_orders([sample_order], sync_type="full")
        meta = in_memory_db.get_last_sync()
        assert meta.get("sync_type") == "full"
        assert meta.get("orders_count") == 1
        assert meta.get("status") == "success"


class TestVacuum:
    def test_vacuum_does_not_raise(self, populated_db):
        """VACUUM should run without error on a populated DB."""
        populated_db.vacuum()
        assert populated_db.is_available is True
        assert populated_db.order_count() == 2

    def test_vacuum_on_empty_db(self, in_memory_db):
        in_memory_db.vacuum()
        assert in_memory_db.is_empty() is True


class TestGetDb:
    def test_get_db_returns_initialized_instance(self):
        db = get_db()
        assert db is DatabaseManager()
        assert db.is_available
        db.close()
