"""
Shared fixtures and configuration for all tests.

All tests import from src via the src package (e.g. ``from src.module import ...``),
which resolves because pytest adds the project root to sys.path automatically.
"""

import pytest


# ── Sample Shopify Order ────────────────────────────────────────────────────

@pytest.fixture
def sample_order():
    """A minimal Shopify order dict for testing."""
    return {
        "id": 12345,
        "order_number": 1001,
        "financial_status": "paid",
        "fulfillment_status": "fulfilled",
        "created_at": "2026-06-15T10:30:00Z",
        "total_price": "150.00",
        "customer": {
            "id": 501,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
        },
        "line_items": [
            {
                "id": 10001,
                "product_id": 2001,
                "variant_id": 3001,
                "title": "Classic T-Shirt",
                "variant_title": "Red / M",
                "price": "25.00",
                "quantity": 2,
                "sku": "TSH-RED-M",
            },
            {
                "id": 10002,
                "product_id": 2002,
                "variant_id": 3002,
                "title": "Denim Jacket",
                "variant_title": "Blue / L",
                "price": "100.00",
                "quantity": 1,
                "sku": "DNM-BLU-L",
            },
        ],
    }


@pytest.fixture
def sample_orders(sample_order):
    """A list of sample orders."""
    order2 = {
        "id": 12346,
        "order_number": 1002,
        "financial_status": "pending",
        "fulfillment_status": None,
        "created_at": "2026-06-16T14:00:00Z",
        "total_price": "75.00",
        "customer": {
            "id": 502,
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "phone": "+9876543210",
        },
        "line_items": [
            {
                "id": 10003,
                "product_id": 2003,
                "variant_id": 3003,
                "title": "Leather Belt",
                "variant_title": "Black",
                "price": "75.00",
                "quantity": 1,
                "sku": "BEL-BLK",
            },
        ],
    }
    return [sample_order, order2]


@pytest.fixture
def sample_product_dict():
    """A minimal product dict for color/size extraction testing."""
    return {
        "id": 2001,
        "title": "Classic T-Shirt",
        "options": [
            {"name": "Color", "position": 1, "values": ["Red"]},
            {"name": "Size", "position": 2, "values": ["S", "M", "L"]},
        ],
        "variants": [
            {
                "id": 3001,
                "product_id": 2001,
                "title": "Red / M",
                "option1": "Red",
                "option2": "M",
                "price": "25.00",
            },
        ],
        "images": [],
    }


# ── In-memory Database ─────────────────────────────────────────────────────

@pytest.fixture
def in_memory_db():
    """Create a DatabaseManager instance backed by an in-memory SQLite DB.

    Overrides the DB_FILE by initializing manually.
    """
    from src.database import DatabaseManager

    db = DatabaseManager()
    db.initialize(":memory:")
    yield db
    db.close()


@pytest.fixture
def populated_db(in_memory_db, sample_orders):
    """A database pre-populated with sample orders."""
    # Enrich items with resolved color/size/image
    for order in sample_orders:
        for item in order.get("line_items", []):
            item["_resolved_color"] = "Red" if item["product_id"] == 2001 else ""
            item["_resolved_size"] = "M" if item["product_id"] == 2001 else ""
            item["_image_url"] = "https://example.com/img.png"

    in_memory_db.save_orders(sample_orders, sync_type="test")
    return in_memory_db


# ── Sample Remittance CSV ───────────────────────────────────────────────────

@pytest.fixture
def remittance_csv_content():
    """Returns the text content of a minimal remittance CSV."""
    return (
        "Order No,Amount,Payment Date\n"
        "1001,150.00,2026-06-20\n"
        "1002,75.00,2026-06-21\n"
    )


@pytest.fixture
def remittance_csv_path(tmp_path, remittance_csv_content):
    """Writes the sample CSV to a temp file and returns the path."""
    path = tmp_path / "remittance.csv"
    path.write_text(remittance_csv_content, encoding="utf-8-sig")
    return str(path)
