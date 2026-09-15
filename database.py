"""Database and Persistence Layer for Tyre Invoice Consolidator.

Manages SQLite storage for consolidated invoices, line items, and analytics metrics.
"""

import datetime
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from consolidator import ConsolidatedInvoice, ConsolidatedItem

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for tyre invoices and analytics."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a sqlite3 connection with foreign keys and dict row factory enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Create necessary database tables if they do not exist and ensure columns exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_ref TEXT UNIQUE NOT NULL,
                    client_name TEXT NOT NULL,
                    client_address TEXT DEFAULT '',
                    date_str TEXT NOT NULL,
                    transaction_date TEXT DEFAULT '',
                    transaction_status TEXT DEFAULT 'En attente',
                    total_quantity INTEGER NOT NULL DEFAULT 0,
                    distinct_items_count INTEGER NOT NULL DEFAULT 0,
                    grand_total REAL NOT NULL DEFAULT 0.0,
                    source_invoices_count INTEGER NOT NULL DEFAULT 1,
                    pdf_filename TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'web',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS invoice_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    index_num INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    reference TEXT DEFAULT '',
                    brand TEXT DEFAULT '',
                    depot TEXT DEFAULT 'magaza 1',
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS receipt_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS brands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    code TEXT DEFAULT '',
                    aliases TEXT DEFAULT '',
                    country TEXT DEFAULT '',
                    manufacturer_year INTEGER,
                    pneustock_id TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_invoices_ref ON invoices(invoice_ref);
                CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_name);
                CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
                CREATE INDEX IF NOT EXISTS idx_brands_name ON brands(name);
                CREATE INDEX IF NOT EXISTS idx_brands_code ON brands(code);
            """)

            # Run column migrations for existing databases
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(invoices)")
            inv_cols = [c["name"] for c in cursor.fetchall()]
            if "client_address" not in inv_cols:
                cursor.execute("ALTER TABLE invoices ADD COLUMN client_address TEXT DEFAULT ''")
            if "transaction_date" not in inv_cols:
                cursor.execute("ALTER TABLE invoices ADD COLUMN transaction_date TEXT DEFAULT ''")
            if "transaction_status" not in inv_cols:
                cursor.execute("ALTER TABLE invoices ADD COLUMN transaction_status TEXT DEFAULT 'En attente'")

            cursor.execute("PRAGMA table_info(invoice_items)")
            item_cols = [c["name"] for c in cursor.fetchall()]
            if "reference" not in item_cols:
                cursor.execute("ALTER TABLE invoice_items ADD COLUMN reference TEXT DEFAULT ''")
            if "brand" not in item_cols:
                cursor.execute("ALTER TABLE invoice_items ADD COLUMN brand TEXT DEFAULT ''")
            if "depot" not in item_cols:
                cursor.execute("ALTER TABLE invoice_items ADD COLUMN depot TEXT DEFAULT 'magaza 1'")

            conn.commit()

        # Seed brands if table is empty
        try:
            if self.get_brands_count() == 0:
                self.seed_brands()
        except Exception as err:
            logger.warning(f"Could not auto-seed brands on startup: {err}")

    def save_consolidated_invoice(
        self,
        invoice: ConsolidatedInvoice,
        pdf_filename: str,
        source: str = "web",
        image_paths: Optional[List[str]] = None,
    ) -> int:
        """Save or update a consolidated invoice with its line items in the database.

        Args:
            invoice: ConsolidatedInvoice object.
            pdf_filename: Relative or absolute filename of the PDF.
            source: Ingestion source ('telegram' or 'web').
            image_paths: Optional list of source image paths.

        Returns:
            Inserted or updated invoice database ID.
        """
        with self._get_connection() as conn:
            # Check if invoice with this ref exists
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM invoices WHERE invoice_ref = ?", (invoice.invoice_ref,))
            row = cursor.fetchone()

            if row:
                invoice_id = row["id"]
                # Update existing invoice
                cursor.execute(
                    """
                    UPDATE invoices SET
                        client_name = ?,
                        client_address = ?,
                        date_str = ?,
                        transaction_date = ?,
                        transaction_status = ?,
                        total_quantity = ?,
                        distinct_items_count = ?,
                        grand_total = ?,
                        source_invoices_count = ?,
                        pdf_filename = ?,
                        source = ?
                    WHERE id = ?
                    """,
                    (
                        invoice.client_name,
                        invoice.client_address or "",
                        invoice.date_str,
                        invoice.transaction_date or invoice.date_str,
                        invoice.transaction_status or "En attente",
                        invoice.total_quantity,
                        invoice.distinct_items_count,
                        invoice.grand_total,
                        invoice.source_invoices_count,
                        pdf_filename,
                        source,
                        invoice_id,
                    ),
                )
                # Delete old items
                cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
            else:
                # Insert new invoice
                cursor.execute(
                    """
                    INSERT INTO invoices (
                        invoice_ref, client_name, client_address, date_str,
                        transaction_date, transaction_status, total_quantity,
                        distinct_items_count, grand_total, source_invoices_count,
                        pdf_filename, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice.invoice_ref,
                        invoice.client_name,
                        invoice.client_address or "",
                        invoice.date_str,
                        invoice.transaction_date or invoice.date_str,
                        invoice.transaction_status or "En attente",
                        invoice.total_quantity,
                        invoice.distinct_items_count,
                        invoice.grand_total,
                        invoice.source_invoices_count,
                        pdf_filename,
                        source,
                    ),
                )
                invoice_id = cursor.lastrowid

            # Insert line items
            for item in invoice.items:
                depot_val = getattr(item, "depot", None) or "magaza 1"
                cursor.execute(
                    """
                    INSERT INTO invoice_items (
                        invoice_id, index_num, description, reference, brand, depot, quantity, unit_price, subtotal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id,
                        item.index,
                        item.description,
                        item.reference or item.description,
                        item.brand or "",
                        depot_val,
                        item.quantity,
                        item.unit_price,
                        item.subtotal,
                    ),
                )

            # Insert image records if provided
            if image_paths:
                for img_path in image_paths:
                    p = Path(img_path)
                    cursor.execute(
                        """
                        INSERT INTO receipt_images (invoice_id, filename, file_path)
                        VALUES (?, ?, ?)
                        """,
                        (invoice_id, p.name, str(p)),
                    )

            conn.commit()
            return invoice_id

    def get_invoices(
        self, limit: int = 50, offset: int = 0, search: str = ""
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch paginated invoices with optional search query.

        Returns:
            Tuple of (list of invoice dicts, total matching count).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_term = f"%{search.strip()}%" if search else "%"

            # Total count
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM invoices
                WHERE invoice_ref LIKE ? OR client_name LIKE ?
                """,
                (search_term, search_term),
            )
            total = cursor.fetchone()["count"]

            # Paginated list
            cursor.execute(
                """
                SELECT * FROM invoices
                WHERE invoice_ref LIKE ? OR client_name LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (search_term, search_term, limit, offset),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows], total

    def get_invoice_by_ref(self, invoice_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch full invoice record including all line items and attached images."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            clean_ref = invoice_ref.lstrip("#")
            with_hash = f"#{clean_ref}"
            cursor.execute(
                "SELECT * FROM invoices WHERE invoice_ref = ? OR invoice_ref = ? OR invoice_ref = ?",
                (invoice_ref, with_hash, clean_ref),
            )
            inv_row = cursor.fetchone()
            if not inv_row:
                return None

            inv_dict = dict(inv_row)

            # Fetch items
            cursor.execute(
                "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY index_num ASC",
                (inv_dict["id"],),
            )
            items_rows = cursor.fetchall()
            inv_dict["items"] = [dict(item) for item in items_rows]

            # Fetch images
            cursor.execute(
                "SELECT * FROM receipt_images WHERE invoice_id = ? ORDER BY id ASC",
                (inv_dict["id"],),
            )
            img_rows = cursor.fetchall()
            inv_dict["images"] = [dict(img) for img in img_rows]

            return inv_dict

    def delete_invoice_by_ref(self, invoice_ref: str) -> bool:
        """Delete an invoice record and associated database rows."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            clean_ref = invoice_ref.lstrip("#")
            with_hash = f"#{clean_ref}"
            cursor.execute(
                "DELETE FROM invoices WHERE invoice_ref = ? OR invoice_ref = ? OR invoice_ref = ?",
                (invoice_ref, with_hash, clean_ref),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Compute aggregate statistics and charts data for the dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Global Totals
            cursor.execute("""
                SELECT
                    COUNT(id) as total_invoices,
                    COALESCE(SUM(total_quantity), 0) as total_tyres,
                    COALESCE(SUM(grand_total), 0.0) as total_revenue
                FROM invoices
            """)
            totals = dict(cursor.fetchone())
            total_inv = totals["total_invoices"]
            total_rev = totals["total_revenue"]
            total_tyres = totals["total_tyres"]
            avg_ticket = round(total_rev / total_inv, 2) if total_inv > 0 else 0.0

            # Max single invoice amount
            cursor.execute("SELECT COALESCE(MAX(grand_total), 0.0) as max_invoice FROM invoices")
            max_invoice = cursor.fetchone()["max_invoice"]

            # Average distinct items per invoice
            cursor.execute("SELECT COALESCE(AVG(distinct_items_count), 0.0) as avg_items FROM invoices")
            avg_items = round(cursor.fetchone()["avg_items"], 1)

            # Top 5 Tyre Dimensions
            cursor.execute("""
                SELECT
                    description,
                    SUM(quantity) as total_qty,
                    SUM(subtotal) as total_amount
                FROM invoice_items
                GROUP BY description
                ORDER BY total_qty DESC
                LIMIT 5
            """)
            top_dimensions = [dict(row) for row in cursor.fetchall()]

            # Brand Breakdown
            cursor.execute("SELECT description, quantity FROM invoice_items")
            all_items = cursor.fetchall()

            brand_counts: Dict[str, int] = {}
            for row in all_items:
                desc = row["description"]
                qty = row["quantity"]
                # Extract brand inside parentheses or default to "AUTRES"
                match = re.search(r"\(([^)]+)\)", desc)
                brand = match.group(1).upper() if match else "AUTRES"
                brand_counts[brand] = brand_counts.get(brand, 0) + qty

            sorted_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)
            top_brands = [{"brand": b, "quantity": q} for b, q in sorted_brands[:6]]

            # Top 5 Clients by total revenue
            cursor.execute("""
                SELECT
                    client_name,
                    COUNT(id) as invoice_count,
                    COALESCE(SUM(grand_total), 0.0) as total_spent,
                    COALESCE(SUM(total_quantity), 0) as total_qty
                FROM invoices
                WHERE client_name != '' AND client_name IS NOT NULL
                GROUP BY client_name
                ORDER BY total_spent DESC
                LIMIT 5
            """)
            top_clients = [dict(row) for row in cursor.fetchall()]

            # Source Breakdown (Web vs Telegram)
            cursor.execute("""
                SELECT
                    source,
                    COUNT(id) as count,
                    COALESCE(SUM(grand_total), 0.0) as revenue
                FROM invoices
                GROUP BY source
            """)
            source_rows = cursor.fetchall()
            source_breakdown = [{"source": row["source"], "count": row["count"], "revenue": round(row["revenue"], 2)} for row in source_rows]

            # Revenue by Day (last 30 entries by date_str)
            cursor.execute("""
                SELECT
                    date_str,
                    COUNT(id) as invoice_count,
                    COALESCE(SUM(grand_total), 0.0) as daily_revenue,
                    COALESCE(SUM(total_quantity), 0) as daily_qty
                FROM invoices
                GROUP BY date_str
                ORDER BY date_str DESC
                LIMIT 30
            """)
            revenue_by_day = [dict(row) for row in cursor.fetchall()]
            revenue_by_day.reverse()  # Chronological order

            # Price Distribution (unit price buckets)
            cursor.execute("""
                SELECT
                    CASE
                        WHEN unit_price < 300 THEN 'budget'
                        WHEN unit_price BETWEEN 300 AND 500 THEN 'mid'
                        ELSE 'premium'
                    END as price_range,
                    COUNT(*) as item_count,
                    SUM(quantity) as total_qty
                FROM invoice_items
                GROUP BY price_range
            """)
            price_rows = cursor.fetchall()
            price_distribution = [{"range": row["price_range"], "count": row["item_count"], "qty": row["total_qty"]} for row in price_rows]

            # Recent Invoices
            cursor.execute("""
                SELECT invoice_ref, client_name, date_str, total_quantity, grand_total, source, created_at
                FROM invoices
                ORDER BY created_at DESC
                LIMIT 8
            """)
            recent_invoices = [dict(row) for row in cursor.fetchall()]

            return {
                "total_invoices": total_inv,
                "total_tyres": total_tyres,
                "total_revenue": round(total_rev, 2),
                "avg_ticket": avg_ticket,
                "max_invoice": round(max_invoice, 2),
                "avg_items_per_invoice": avg_items,
                "top_dimensions": top_dimensions,
                "top_brands": top_brands,
                "top_clients": top_clients,
                "source_breakdown": source_breakdown,
                "revenue_by_day": revenue_by_day,
                "price_distribution": price_distribution,
                "recent_invoices": recent_invoices,
                "currency": settings.currency,
                "company_name": settings.company_name,
            }

    # -----------------------------------------------------------------------
    # Brands (Marques) Persistence & Extraction Methods
    # -----------------------------------------------------------------------

    def seed_brands(self, brands_json_path: Optional[Path] = None) -> int:
        """Extract all brand names from pneustock brands.json & mappings, and insert into DB."""
        json_path = brands_json_path or (Path(__file__).parent / "extracted_pneustock_data" / "brands.json")
        brands_data: List[Dict[str, Any]] = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    brands_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading brands from {json_path}: {e}")

        # Also import BRAND_MAPPINGS from consolidator to attach shorthand codes
        from consolidator import BRAND_MAPPINGS

        abbrevs_by_brand: Dict[str, List[str]] = {}
        for code, full_name in BRAND_MAPPINGS.items():
            if len(code) <= 3 and code != full_name:
                abbrevs_by_brand.setdefault(full_name.upper(), []).append(code)

        unique_brands: Dict[str, Dict[str, Any]] = {}

        # 1. Ingest brands from brands.json (169 marques)
        for item in brands_data:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            name_key = name.lower()
            clean_name = name.upper().replace(" ", "").replace("-", "")

            matched_codes: List[str] = []
            for k, c_list in abbrevs_by_brand.items():
                if k == clean_name or k in clean_name or clean_name in k:
                    matched_codes.extend(c_list)

            primary_code = matched_codes[0] if matched_codes else ""
            aliases_str = ", ".join(sorted(set(matched_codes)))

            unique_brands[name_key] = {
                "name": name,
                "code": primary_code,
                "aliases": aliases_str,
                "country": (item.get("country") or "").strip(),
                "manufacturer_year": item.get("manufacturerYear"),
                "pneustock_id": (item.get("id") or "").strip(),
            }

        # 2. Ingest any additional brands known in BRAND_MAPPINGS
        for code, full_name in BRAND_MAPPINGS.items():
            if not full_name:
                continue
            name_key = full_name.lower()
            if name_key not in unique_brands:
                codes = abbrevs_by_brand.get(full_name.upper(), [code] if len(code) <= 3 else [])
                unique_brands[name_key] = {
                    "name": full_name.title(),
                    "code": codes[0] if codes else (code if len(code) <= 3 else ""),
                    "aliases": ", ".join(sorted(set(codes))),
                    "country": "",
                    "manufacturer_year": None,
                    "pneustock_id": "",
                }

        # 3. Insert or update in SQLite database
        with self._get_connection() as conn:
            cursor = conn.cursor()
            inserted_count = 0
            for b in unique_brands.values():
                cursor.execute("""
                    INSERT INTO brands (name, code, aliases, country, manufacturer_year, pneustock_id)
                    VALUES (:name, :code, :aliases, :country, :manufacturer_year, :pneustock_id)
                    ON CONFLICT(name) DO UPDATE SET
                        code = CASE WHEN excluded.code != '' THEN excluded.code ELSE brands.code END,
                        aliases = CASE WHEN excluded.aliases != '' THEN excluded.aliases ELSE brands.aliases END,
                        country = CASE WHEN excluded.country != '' THEN excluded.country ELSE brands.country END,
                        manufacturer_year = COALESCE(excluded.manufacturer_year, brands.manufacturer_year),
                        pneustock_id = CASE WHEN excluded.pneustock_id != '' THEN excluded.pneustock_id ELSE brands.pneustock_id END
                """, b)
                inserted_count += 1
            conn.commit()

        logger.info(f"Successfully seeded {inserted_count} tyre brands into SQLite database.")
        return inserted_count

    def get_all_brands(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all tyre brands from the database with optional search filtering."""
        query = "SELECT id, name, code, aliases, country, manufacturer_year, pneustock_id, created_at FROM brands"
        params: List[Any] = []
        if search and search.strip():
            query += " WHERE name LIKE ? OR code LIKE ? OR aliases LIKE ? OR country LIKE ?"
            term = f"%{search.strip()}%"
            params = [term, term, term, term]
        query += " ORDER BY name COLLATE NOCASE ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_brands_count(self) -> int:
        """Count the total number of tyre brands stored in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM brands")
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_brand_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up a brand by exact name or abbreviation code."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM brands WHERE LOWER(name) = LOWER(?) OR LOWER(code) = LOWER(?) LIMIT 1",
                (name.strip(), name.strip()),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_or_update_brand(
        self,
        name: str,
        code: str = "",
        aliases: str = "",
        country: str = "",
        manufacturer_year: Optional[int] = None,
        pneustock_id: str = "",
    ) -> int:
        """Add or update an individual tyre brand in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO brands (name, code, aliases, country, manufacturer_year, pneustock_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    code = excluded.code,
                    aliases = excluded.aliases,
                    country = excluded.country,
                    manufacturer_year = excluded.manufacturer_year,
                    pneustock_id = excluded.pneustock_id
            """, (name.strip(), code.strip(), aliases.strip(), country.strip(), manufacturer_year, pneustock_id.strip()))
            conn.commit()
            return cursor.lastrowid or 0


# Global database instance
db = Database()

