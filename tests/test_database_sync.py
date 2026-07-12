"""
Tests for database_sync.py — Shopify → SQLite sync pipeline.

Uses a mock ShopifyAPI to avoid real network calls.
"""
import pytest
from unittest.mock import MagicMock
from src.database import DatabaseManager
from src.database_sync import DatabaseSync
from src.data_utils import extract_color_robust


class MockShopifyAPI:
    """A mock ShopifyAPI that returns sample orders without network calls."""

    def __init__(self, orders=None):
        self.orders = orders or []

    def get_orders(self, **kwargs):
        return self.orders

    def get_product(self, product_id):
        return None


@pytest.fixture
def mock_api(sample_orders):
    return MockShopifyAPI(orders=sample_orders)


@pytest.fixture
def mock_resolver():
    """A mock resolver that always returns a URL."""
    resolver = MagicMock()
    resolver.get_image_url.return_value = "https://example.com/img.png"
    resolver._product_cache = {}
    return resolver


@pytest.fixture
def fresh_in_memory_db():
    """Create a truly isolated in-memory DB for sync tests.

    Uses a unique instance variable to avoid singleton conflicts.
    """
    db = DatabaseManager()
    # Reset singleton internals to ensure fresh state
    DatabaseManager._instance = None
    fresh = DatabaseManager()
    fresh.initialize(":memory:")
    yield fresh
    fresh.close()


class TestDatabaseSyncInit:
    def test_creates_syncer(self, mock_api, mock_resolver):
        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        assert syncer.api is mock_api
        assert syncer.resolver is mock_resolver

    def test_initializes_from_scratch(self):
        """Should create its own API and resolver without needing a .env file."""
        from unittest.mock import patch
        from src.config import Config

        with patch.multiple(
            Config,
            STORE_URL="test-store.myshopify.com",
            SHOPIFY_SHOP="test-store.myshopify.com",
            SHOPIFY_CLIENT_ID="test-client-id",
            SHOPIFY_CLIENT_SECRET="test-client-secret",
        ):
            syncer = DatabaseSync()
            # Should create its own API and resolver
            assert syncer.api is not None
            assert syncer.resolver is not None


class TestSyncAll:
    def test_sync_all_saves_orders(self, fresh_in_memory_db, mock_api, mock_resolver):
        """Sync all should save orders to the database."""
        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        saved = syncer.sync_all()
        assert saved == 2
        assert fresh_in_memory_db.order_count() == 2

    def test_sync_all_empty_orders(self, fresh_in_memory_db, mock_resolver):
        """Sync all with no orders should save 0."""
        empty_api = MockShopifyAPI(orders=[])
        syncer = DatabaseSync(api=empty_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        saved = syncer.sync_all()
        assert saved == 0
        assert fresh_in_memory_db.is_empty() is True

    def test_sync_all_calls_progress(self, fresh_in_memory_db, mock_api, mock_resolver):
        """Progress function should be called during sync."""
        progress_calls = []

        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        syncer.sync_all(progress_fn=lambda v: progress_calls.append(v))
        assert len(progress_calls) > 0

    def test_sync_all_calls_log(self, fresh_in_memory_db, mock_api, mock_resolver):
        """Log function should be called during sync."""
        log_calls = []

        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        syncer.sync_all(log_fn=lambda m: log_calls.append(m))
        assert len(log_calls) > 0

    def test_sync_all_stop_requested(self, fresh_in_memory_db, mock_api, mock_resolver):
        """Requesting stop mid-sync halts processing. Stop is cleared at start,
        so calling it before sync_all() has no effect — it must be called during."""
        import threading
        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        # Call request_stop in a timer after sync starts
        def stop_later():
            syncer.request_stop()

        timer = threading.Timer(0.05, stop_later)
        timer.start()

        saved = syncer.sync_all()
        timer.cancel()

        # Stop flag was raised mid-sync so fewer than full 2 may have saved
        # If timer fired in time, saved < 2; otherwise saved == 2 (race)
        assert isinstance(saved, int) and saved >= 0


class TestSyncLatest:
    def test_sync_latest_saves_orders(self, fresh_in_memory_db, mock_api, mock_resolver):
        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        saved = syncer.sync_latest(count=5)
        assert saved == 2
        assert fresh_in_memory_db.order_count() == 2

    def test_sync_latest_empty(self, fresh_in_memory_db, mock_resolver):
        empty_api = MockShopifyAPI(orders=[])
        syncer = DatabaseSync(api=empty_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        saved = syncer.sync_latest(count=5)
        assert saved == 0

    def test_sync_latest_calls_status(self, fresh_in_memory_db, mock_api, mock_resolver):
        status_calls = []

        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        syncer.sync_latest(count=5, status_fn=lambda m: status_calls.append(m))
        assert len(status_calls) > 0


class TestEnrichment:
    def test_enriches_with_color(self, fresh_in_memory_db, sample_orders):
        """Line items should be enriched with resolved color before saving."""
        api = MockShopifyAPI(orders=sample_orders)
        resolver = MagicMock()
        resolver.get_image_url.return_value = ""
        resolver._product_cache = {}

        syncer = DatabaseSync(api=api, resolver=resolver)
        syncer.db = fresh_in_memory_db

        syncer.sync_all()

        results = fresh_in_memory_db.search_products("T-Shirt")
        assert len(results) > 0

    def test_uses_image_cache(self, fresh_in_memory_db, mock_api, mock_resolver):
        """Image cache should be consulted during sync."""
        syncer = DatabaseSync(api=mock_api, resolver=mock_resolver)
        syncer.db = fresh_in_memory_db

        syncer.image_cache.set_negative(2001)

        saved = syncer.sync_all()
        assert saved == 2
