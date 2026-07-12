"""
Tests for order_data_builder.py — data preparation from Shopify order dicts.
"""

import pytest
from src.order_data_builder import OrderDataBuilder


class TestBuildItemData:
    def test_builds_correct_keys(self, sample_order):
        item = sample_order["line_items"][0]
        data = OrderDataBuilder.build_item_data(sample_order, item)

        assert data["order_number"] == "#1001"
        assert data["customer_name"] == "John Doe"
        assert data["customer_email"] == "john@example.com"
        assert data["phone_number"] == "+1234567890"
        assert data["product_name"] == "Classic T-Shirt"
        assert data["variant_name"] == "Red / M"
        assert data["price"] == "25.00"
        assert data["payment_status"] == "paid"
        assert data["product_id"] == 2001
        assert data["variant_id"] == 3001

    def test_all_keys_present(self, sample_order):
        item = sample_order["line_items"][0]
        data = OrderDataBuilder.build_item_data(sample_order, item)

        expected_keys = {
            "order_number", "customer_name", "customer_email",
            "phone_number", "product_name", "variant_name",
            "color", "size", "quantity", "price", "payment_status",
            "product_id", "variant_id",
        }
        assert set(data.keys()) == expected_keys

    def test_color_from_variant_title(self, sample_order):
        item = sample_order["line_items"][0]
        data = OrderDataBuilder.build_item_data(sample_order, item)

        # "Red / M" should resolve to "Red" for color
        assert data["color"] == "Red"

    def test_size_from_variant_title(self, sample_order):
        item = sample_order["line_items"][0]
        data = OrderDataBuilder.build_item_data(sample_order, item)

        # "Red / M" should upsize "M" to "L"
        assert data["size"] == "L"

    def test_customer_name_fallback(self, sample_order):
        order_no_customer = dict(sample_order)
        order_no_customer["customer"] = {}
        item = order_no_customer["line_items"][0]

        data = OrderDataBuilder.build_item_data(order_no_customer, item)
        assert data["customer_name"] == ""
        assert data["customer_email"] == ""
        assert data["phone_number"] == ""

    def test_with_product_cache(self, sample_order, sample_product_dict):
        item = sample_order["line_items"][0]
        cache = {2001: sample_product_dict}

        data = OrderDataBuilder.build_item_data(sample_order, item, cache.get(2001))
        assert data["color"] == "Red"  # From product option, not variant title
        assert data["size"] == "L"

    def test_no_variant_title(self, sample_order):
        item = dict(sample_order["line_items"][0])
        item["variant_title"] = None

        data = OrderDataBuilder.build_item_data(sample_order, item)
        assert data["color"] == ""
        assert data["variant_name"] is None


class TestBuildAllItems:
    def test_builds_all_items(self, sample_orders):
        data = OrderDataBuilder.build_all_items(sample_orders)
        assert len(data) == 3  # 2 items in first order + 1 in second

    def test_empty_orders_list(self):
        data = OrderDataBuilder.build_all_items([])
        assert data == []

    def test_order_without_line_items(self, sample_order):
        order = dict(sample_order)
        order["line_items"] = []
        data = OrderDataBuilder.build_all_items([order])
        assert data == []

    def test_all_items_have_order_number(self, sample_orders):
        data = OrderDataBuilder.build_all_items(sample_orders)
        for d in data:
            assert d["order_number"] in ("#1001", "#1002")


class TestCollectImageTasks:
    def test_collects_tasks(self, sample_order):
        orders = [sample_order]

        class MockResolver:
            def get_image_url(self, item):
                return f"https://example.com/img/{item['product_id']}.png"

        resolver = MockResolver()
        tasks = OrderDataBuilder.collect_image_tasks(orders, resolver, include_images=True)

        assert len(tasks) == 2
        urls, ids = zip(*tasks)
        assert "2001_3001" in ids
        assert "2002_3002" in ids

    def test_include_images_false(self, sample_order):
        class MockResolver:
            def get_image_url(self, item):
                return "https://example.com/img.png"

        tasks = OrderDataBuilder.collect_image_tasks(
            [sample_order], MockResolver(), include_images=False
        )
        assert tasks == []

    def test_skip_items_without_product_id(self, sample_order):
        item = dict(sample_order["line_items"][0])
        item["product_id"] = None
        sample_order["line_items"] = [item]

        class MockResolver:
            def get_image_url(self, item):
                return "https://example.com/img.png"

        tasks = OrderDataBuilder.collect_image_tasks(
            [sample_order], MockResolver(), include_images=True
        )
        assert len(tasks) == 0

    def test_skip_missing_url(self, sample_order):
        class MockResolver:
            def get_image_url(self, item):
                return ""

        tasks = OrderDataBuilder.collect_image_tasks(
            [sample_order], MockResolver(), include_images=True
        )
        assert len(tasks) == 0


class TestBuildImagePaths:
    def test_builds_paths_dict(self):
        downloaded = {
            "2001_3001": "/path/to/img1.png",
            "2002_3002": "/path/to/img2.png",
        }
        paths = OrderDataBuilder.build_image_paths(downloaded)
        assert paths == {
            (2001, 3001): "/path/to/img1.png",
            (2002, 3002): "/path/to/img2.png",
        }

    def test_handles_none_path(self):
        downloaded = {"2001_3001": None}
        paths = OrderDataBuilder.build_image_paths(downloaded)
        assert paths == {(2001, 3001): None}

    def test_handles_empty_dict(self):
        paths = OrderDataBuilder.build_image_paths({})
        assert paths == {}

    def test_handles_variant_id(self):
        downloaded = {"2001_None": "/path/img.png"}
        paths = OrderDataBuilder.build_image_paths(downloaded)
        assert paths == {(2001, None): "/path/img.png"}
