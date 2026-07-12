"""
database.py — Local SQLite database for offline Shopify order storage.

Provides:
  - Schema creation with indexes
  - Batch insert for orders, customers, products, order_items
  - Search (products, customers, orders)
  - Sync metadata tracking
  - Graceful degradation (app works without database file)

Tables:
  orders         — Shopify order headers
  customers      — Customer records
  products       — Product records
  order_items    — Line items with resolved color/size/image
  sync_metadata  — Sync operation history
"""

import sqlite3
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils import logger

DB_FILE = "orders.db"

# ── Schema DDL ──────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER UNIQUE NOT NULL,
    order_number    INTEGER,
    customer_id     INTEGER,
    financial_status TEXT,
    fulfillment_status TEXT,
    created_at      TEXT,
    total_price     REAL,
    raw_data        TEXT,
    synced_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_order_number ON orders(order_number);
CREATE INDEX IF NOT EXISTS idx_orders_created_at   ON orders(created_at);

CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER UNIQUE NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    phone           TEXT,
    raw_data        TEXT,
    synced_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_name  ON customers(last_name, first_name);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER UNIQUE NOT NULL,
    title           TEXT,
    product_type    TEXT,
    vendor          TEXT,
    raw_data        TEXT,
    synced_at       TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER,
    product_id      INTEGER,
    variant_id      INTEGER,
    product_name    TEXT,
    variant_name    TEXT,
    color           TEXT,
    size            TEXT,
    price           REAL,
    quantity        INTEGER,
    image_url       TEXT,
    synced_at       TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE INDEX IF NOT EXISTS idx_order_items_product_name  ON order_items(product_name);
CREATE INDEX IF NOT EXISTS idx_order_items_color          ON order_items(color);
CREATE INDEX IF NOT EXISTS idx_order_items_size           ON order_items(size);
CREATE INDEX IF NOT EXISTS idx_order_items_composite      ON order_items(product_name, color, size);

CREATE TABLE IF NOT EXISTS sync_metadata (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type       TEXT,
    sync_start      TEXT,
    sync_end        TEXT,
    orders_count    INTEGER,
    status          TEXT
);
"""


class DatabaseManager:
    """Singleton SQLite database manager."""

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls, *args, **kwargs)
                    cls._instance._initialized = False
        return cls._instance

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, db_path: str = DB_FILE):
        """Create / open the database file and apply the schema."""
        with self._lock:
            if self._initialized:
                return

            self.db_path = db_path
            try:
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self.conn.executescript(SCHEMA_SQL)
                self.conn.commit()
                self._initialized = True
                logger.info(f"Database initialized: {db_path}")
            except Exception as exc:
                logger.exception("Failed to initialize database")
                self.conn = None

    def close(self):
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            self._initialized = False

    @property
    def is_available(self) -> bool:
        """Return True if the database is connected."""
        return self._initialized and self.conn is not None

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return True if the orders table has no rows."""
        if not self.is_available:
            return True
        try:
            cur = self.conn.execute("SELECT COUNT(*) FROM orders")
            return cur.fetchone()[0] == 0
        except Exception:
            return True

    def order_count(self) -> int:
        """Return total number of orders in the database."""
        if not self.is_available:
            return 0
        try:
            cur = self.conn.execute("SELECT COUNT(*) FROM orders")
            return cur.fetchone()[0]
        except Exception:
            return 0

    def get_last_sync(self) -> dict:
        """Return the most recent sync_metadata row or empty dict."""
        if not self.is_available:
            return {}
        try:
            cur = self.conn.execute(
                "SELECT * FROM sync_metadata ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Batch save
    # ------------------------------------------------------------------

    def save_orders(self, orders: list, sync_type: str = "full") -> int:
        """Insert / upsert orders, customers, products, and order_items.

        Parameters
        ----------
        orders : list
            Raw Shopify order dicts (as returned by ShopifyAPI.get_orders).
        sync_type : str
            'full' or 'latest' — recorded in sync_metadata.

        Returns
        -------
        int
            Number of orders saved.
        """
        if not self.is_available or not orders:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        saved_count = 0

        try:
            with self.conn:
                for order in orders:
                    order_id = order.get("id")
                    if not order_id:
                        continue

                    order_number = order.get("order_number")
                    customer = order.get("customer") or {}
                    financial_status = order.get("financial_status", "")
                    fulfillment_status = order.get("fulfillment_status", "")
                    created_at = order.get("created_at", "")
                    total_price = order.get("total_price", 0)

                    # ── Upsert order (ON CONFLICT DO UPDATE avoids DELETE+INSERT) ──
                    self.conn.execute(
                        """INSERT INTO orders
                           (order_id, order_number, customer_id,
                            financial_status, fulfillment_status,
                            created_at, total_price, raw_data, synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(order_id) DO UPDATE SET
                               order_number      = excluded.order_number,
                               customer_id       = excluded.customer_id,
                               financial_status  = excluded.financial_status,
                               fulfillment_status = excluded.fulfillment_status,
                               created_at        = excluded.created_at,
                               total_price       = excluded.total_price,
                               raw_data          = excluded.raw_data,
                               synced_at         = excluded.synced_at""",
                        (
                            order_id,
                            order_number,
                            customer.get("id"),
                            financial_status,
                            fulfillment_status,
                            created_at,
                            float(total_price) if total_price else 0,
                            json.dumps(order, default=str),
                            now,
                        ),
                    )

                    # ── Upsert customer (ON CONFLICT DO UPDATE) ─────────
                    if customer.get("id"):
                        self.conn.execute(
                            """INSERT INTO customers
                               (customer_id, first_name, last_name,
                                email, phone, raw_data, synced_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(customer_id) DO UPDATE SET
                                   first_name  = excluded.first_name,
                                   last_name   = excluded.last_name,
                                   email       = excluded.email,
                                   phone       = excluded.phone,
                                   raw_data    = excluded.raw_data,
                                   synced_at   = excluded.synced_at""",
                            (
                                customer.get("id"),
                                customer.get("first_name", ""),
                                customer.get("last_name", ""),
                                customer.get("email", ""),
                                customer.get("phone", ""),
                                json.dumps(customer, default=str),
                                now,
                            ),
                        )

                    # ── Process line items ───────────────────────────────
                    for item in order.get("line_items", []):
                        product_id = item.get("product_id")
                        # Delete existing items for this order+product+variant
                        # so we can re-insert fresh data
                        self.conn.execute(
                            """DELETE FROM order_items
                               WHERE order_id = ?
                                 AND product_id = ?
                                 AND variant_id = ?""",
                            (order_id, product_id, item.get("variant_id")),
                        )

                        self.conn.execute(
                            """INSERT INTO order_items
                               (order_id, product_id, variant_id,
                                product_name, variant_name,
                                color, size, price, quantity,
                                image_url, synced_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                order_id,
                                product_id,
                                item.get("variant_id"),
                                item.get("title", ""),
                                item.get("variant_title", ""),
                                item.get("_resolved_color", ""),
                                item.get("_resolved_size", ""),
                                float(item.get("price", 0)),
                                int(item.get("quantity", 0)),
                                item.get("_image_url", ""),
                                now,
                            ),
                        )

                    # ── Upsert product (minimal, for lookup) ────────────
                    if product_id:
                        self.conn.execute(
                            """INSERT OR REPLACE INTO products
                               (product_id, title, synced_at)
                               VALUES (?, ?, ?)""",
                            (product_id, item.get("title", ""), now),
                        )

                    saved_count += 1

            # ── Record sync metadata ───────────────────────────────────
            self.conn.execute(
                """INSERT INTO sync_metadata
                   (sync_type, sync_start, sync_end, orders_count, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (sync_type, now, datetime.now(timezone.utc).isoformat(), saved_count, "success"),
            )
            self.conn.commit()

            logger.info(f"Database sync complete: {saved_count} orders saved.")
            return saved_count

        except Exception as exc:
            logger.error(f"Database save failed: {exc}")
            return 0

    # ------------------------------------------------------------------
    # Search — Products
    # ------------------------------------------------------------------

    def search_products(
        self, keyword: str, limit: int = 500
    ) -> list:
        """Search order_items by product name (case-insensitive, partial).

        Supports multiple comma-separated keywords.
        """
        if not self.is_available or not keyword:
            return []

        terms = [t.strip() for t in keyword.split(",") if t.strip()]
        if not terms:
            return []

        try:
            conditions = []
            params = []
            for term in terms:
                conditions.append("LOWER(product_name) LIKE ?")
                params.append(f"%{term.lower()}%")

            where_clause = " OR ".join(conditions)
            sql = f"""
                SELECT DISTINCT oi.*, o.order_number, o.created_at,
                       c.first_name, c.last_name, c.email, c.phone,
                       o.financial_status
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                WHERE {where_clause}
                ORDER BY o.created_at DESC
                LIMIT ?
            """
            params.append(limit)
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall()

            results = []
            for row in rows:
                r = dict(row)
                results.append({
                    "order_number": f"#{r.get('order_number')}",
                    "order_date": (r.get("created_at") or "").split("T")[0],
                    "customer_name": f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
                    "customer_email": r.get("email", ""),
                    "phone_number": r.get("phone", ""),
                    "product_name": r.get("product_name"),
                    "variant_name": r.get("variant_name"),
                    "color": r.get("color", ""),
                    "size": r.get("size", ""),
                    "price": r.get("price"),
                    "quantity": r.get("quantity"),
                    "payment_status": r.get("financial_status", ""),
                    "product_id": r.get("product_id"),
                    "variant_id": r.get("variant_id"),
                    "image_url": r.get("image_url", ""),
                })
            return results

        except Exception as exc:
            logger.error(f"Database search error (products): {exc}")
            return []

    # ------------------------------------------------------------------
    # Search — Customers
    # ------------------------------------------------------------------

    def search_customers(
        self, query: str, limit: int = 200
    ) -> list:
        """Search customers by name, email, or phone (partial, case-insensitive)."""
        if not self.is_available or not query:
            return []

        try:
            like = f"%{query.strip().lower()}%"
            sql = """
                SELECT DISTINCT c.*, o.order_number, o.created_at,
                       oi.product_name, oi.variant_name, oi.color, oi.size
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                JOIN order_items oi ON o.order_id = oi.order_id
                WHERE LOWER(c.first_name || ' ' || c.last_name) LIKE ?
                   OR LOWER(c.email) LIKE ?
                   OR LOWER(c.phone) LIKE ?
                ORDER BY o.created_at DESC
                LIMIT ?
            """
            cur = self.conn.execute(sql, (like, like, like, limit))
            rows = cur.fetchall()

            results = []
            for row in rows:
                r = dict(row)
                results.append({
                    "order_number": f"#{r.get('order_number')}",
                    "order_date": (r.get("created_at") or "").split("T")[0],
                    "customer_name": f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
                    "customer_email": r.get("email", ""),
                    "phone_number": r.get("phone", ""),
                    "product_name": r.get("product_name"),
                    "variant_name": r.get("variant_name"),
                    "color": r.get("color", ""),
                    "size": r.get("size", ""),
                })
            return results

        except Exception as exc:
            logger.error(f"Database search error (customers): {exc}")
            return []

    # ------------------------------------------------------------------
    # Search — Order by number
    # ------------------------------------------------------------------

    def search_order_by_number(
        self, order_number: int, limit: int = 50
    ) -> list:
        """Search for a specific order number."""
        if not self.is_available:
            return []

        try:
            sql = """
                SELECT oi.*, o.order_number, o.created_at,
                       c.first_name, c.last_name, c.email, c.phone,
                       o.financial_status
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_number = ?
                ORDER BY o.created_at DESC
                LIMIT ?
            """
            cur = self.conn.execute(sql, (order_number, limit))
            rows = cur.fetchall()

            results = []
            for row in rows:
                r = dict(row)
                results.append({
                    "order_number": f"#{r.get('order_number')}",
                    "order_date": (r.get("created_at") or "").split("T")[0],
                    "customer_name": f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
                    "customer_email": r.get("email", ""),
                    "phone_number": r.get("phone", ""),
                    "product_name": r.get("product_name"),
                    "variant_name": r.get("variant_name"),
                    "color": r.get("color", ""),
                    "size": r.get("size", ""),
                    "price": r.get("price"),
                    "quantity": r.get("quantity"),
                    "payment_status": r.get("financial_status", ""),
                    "product_id": r.get("product_id"),
                    "variant_id": r.get("variant_id"),
                    "image_url": r.get("image_url", ""),
                })
            return results

        except Exception as exc:
            logger.error(f"Database search error (order): {exc}")
            return []

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def clear_all(self):
        """Delete all data from all tables."""
        if not self.is_available:
            return
        try:
            with self.conn:
                for table in (
                    "order_items",
                    "orders",
                    "customers",
                    "products",
                    "sync_metadata",
                ):
                    self.conn.execute(f"DELETE FROM {table}")
            logger.info("Database cleared.")
        except Exception as exc:
            logger.exception("Failed to clear database")

    def vacuum(self):
        """Reclaim disk space by rebuilding the database file.

        Call periodically (e.g., once a week) or after clearing large
        amounts of data to keep the database file compact.
        """
        if not self.is_available:
            return
        try:
            self.conn.execute("VACUUM")
            logger.info("Database vacuumed successfully.")
        except Exception as exc:
            logger.exception("Failed to vacuum database")


# ── Convenience singleton accessor ──────────────────────────────────────────

def get_db() -> DatabaseManager:
    """Return the initialized DatabaseManager singleton."""
    db = DatabaseManager()
    if not db.is_available:
        db.initialize()
    return db
