"""Test suite for the Tyre Invoice Consolidator & Dashboard.

Covers:
- Tyre dimension regex normalization
- Multi-receipt aggregation and math calculations
- Pydantic schema validation
- French A4 PDF generation
- Telegram message summary formatting
- SQLite database persistence & analytics calculations
- FastAPI REST API endpoints
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from config import settings
from consolidator import (
    normalize_tyre_description,
    consolidate_extractions,
    ConsolidatedInvoice,
    ConsolidatedItem,
)
from extractor import RawInvoiceItem, SingleInvoiceExtraction
from pdf_generator import pdf_generator
from bot import format_telegram_summary
from database import Database
from app import app


# ---------------------------------------------------------------------------
# Normalization Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_input,expected_output",
    [
        ("175 70 13 boto", "175/70 R13 (BOTO)"),
        ("175-70-R13 (boto)", "175/70 R13 (BOTO)"),
        ("175/70/13 (Boto)", "175/70 R13 (BOTO)"),
        ("175/70R13", "175/70 R13"),
        ("185 65 15 (P)", "185/65 R15 (PETLAS)"),
        ("185/65 R15 (P)", "185/65 R15 (PETLAS)"),
        ("205 R14C (L)", "205 R14C (LASSA)"),
        ("205 14C", "205 R14C"),
        ("205/14C", "205 R14C"),
        ("215-65-16C ST", "215/65 R16C (STARMAXX)"),
        ("215/65 R16C (ST)", "215/65 R16C (STARMAXX)"),
        ("315/80/22.5", "315/80 R22.5"),
        ("175/65 R14 (SH)", "175/65 R14 (SEHA)"),
        ("185/65 R15 (DL)", "185/65 R15 (DELINTE)"),
    ],
)
def test_tyre_dimension_normalization(raw_input: str, expected_output: str):
    """Test standardizing various handwritten tyre string formats."""
    result = normalize_tyre_description(raw_input)
    assert result == expected_output


# ---------------------------------------------------------------------------
# Consolidation & Aggregation Tests
# ---------------------------------------------------------------------------

def test_consolidate_multi_invoice_extractions():
    """Test grouping matching tyre sizes and calculating totals across receipts."""
    ext1 = SingleInvoiceExtraction(
        invoice_number="001",
        client_name="Pneu Service Casablanca",
        items=[
            RawInvoiceItem(raw_description="175 70 13 boto", quantity=4, unit_price=350.0),
            RawInvoiceItem(raw_description="205 R14C (L)", quantity=2, unit_price=650.0),
            RawInvoiceItem(raw_description="185/65 R15 (P)", quantity=4, unit_price=420.0),
        ],
    )

    ext2 = SingleInvoiceExtraction(
        invoice_number="002",
        client_name="Pneu Service Casablanca",
        items=[
            RawInvoiceItem(raw_description="175/70-R13 (BOTO)", quantity=6, unit_price=350.0),
            RawInvoiceItem(raw_description="315 80 22.5 (HW)", quantity=8, unit_price=2100.0),
            RawInvoiceItem(raw_description="185 65 15 (P)", quantity=2, unit_price=420.0),
        ],
    )

    consolidated = consolidate_extractions(
        extractions=[ext1, ext2],
        invoice_ref="#REC-2026-TEST",
    )

    assert consolidated.invoice_ref == "#REC-2026-TEST"
    assert consolidated.client_name == "Pneu Service Casablanca"
    assert consolidated.source_invoices_count == 2
    assert consolidated.distinct_items_count == 4

    items_map = {item.description: item for item in consolidated.items}
    assert items_map["175/70 R13 (BOTO)"].quantity == 10
    assert items_map["175/70 R13 (BOTO)"].subtotal == 3500.0
    assert items_map["185/65 R15 (PETLAS)"].quantity == 6
    assert items_map["185/65 R15 (PETLAS)"].subtotal == 2520.0
    assert items_map["205 R14C (LASSA)"].quantity == 2
    assert items_map["205 R14C (LASSA)"].subtotal == 1300.0
    assert items_map["315/80 R22.5 (HW)"].quantity == 8
    assert items_map["315/80 R22.5 (HW)"].subtotal == 16800.0

    assert consolidated.total_quantity == 26
    assert consolidated.grand_total == 24120.0


def test_consolidation_merges_repeated_same_dimension():
    """Test that duplicate items with the same dimension are merged into a single line item with summed quantities."""
    ext = SingleInvoiceExtraction(
        client_name="Transport Express",
        items=[
            RawInvoiceItem(raw_description="185/65 R15 (PETLAS)", quantity=2, unit_price=0.0),
            RawInvoiceItem(raw_description="185/65 R15 (PETLAS)", quantity=4, unit_price=475.0),
        ],
    )
    consolidated = consolidate_extractions([ext])
    assert consolidated.distinct_items_count == 1
    assert consolidated.total_quantity == 6
    assert consolidated.items[0].quantity == 6
    assert consolidated.items[0].unit_price == 475.0
    assert consolidated.items[0].subtotal == 2850.0
    assert consolidated.grand_total == 2850.0


# ---------------------------------------------------------------------------
# PDF Generation Tests
# ---------------------------------------------------------------------------

def test_pdf_generation():
    """Test rendering and compiling an A4 PDF invoice."""
    invoice = ConsolidatedInvoice(
        invoice_ref="#REC-2026-08-TESTPDF",
        client_name="Garage Auto Fès",
        date_str="17/08/2026",
        items=[
            ConsolidatedItem(index=1, description="175/70 R13 (BOTO)", quantity=8, unit_price=350.0, subtotal=2800.0),
            ConsolidatedItem(index=2, description="205 R14C (L)", quantity=4, unit_price=650.0, subtotal=2600.0),
            ConsolidatedItem(index=3, description="315/80 R22.5 (HW)", quantity=12, unit_price=2100.0, subtotal=25200.0),
        ],
        total_quantity=24,
        distinct_items_count=3,
        grand_total=30600.0,
        source_invoices_count=3,
    )

    pdf_path = pdf_generator.generate_pdf_sync(invoice, output_filename="test_invoice.pdf")

    assert pdf_path.exists()
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 1000


# ---------------------------------------------------------------------------
# Telegram Formatting Tests
# ---------------------------------------------------------------------------

def test_telegram_summary_format():
    """Test generating Telegram HTML summary text."""
    invoice = ConsolidatedInvoice(
        invoice_ref="#REC-2026-9999",
        client_name="Test Garage",
        date_str="17/08/2026",
        items=[
            ConsolidatedItem(index=1, description="175/70 R13 (BOTO)", quantity=10, unit_price=350.0, subtotal=3500.0),
        ],
        total_quantity=10,
        distinct_items_count=1,
        grand_total=3500.0,
        source_invoices_count=1,
    )
    summary = format_telegram_summary(invoice)
    assert "REC-2026-9999" in summary
    assert "Test Garage" in summary
    assert "10 pièces" in summary or "10" in summary
    assert f"3,500.00 {settings.currency}" in summary


# ---------------------------------------------------------------------------
# Database Tests
# ---------------------------------------------------------------------------

def test_database_crud_and_analytics(tmp_path):
    """Test SQLite database persistence, retrieval, recalculation, and analytics."""
    test_db_path = tmp_path / "test_invoices.db"
    test_db = Database(db_path=test_db_path)

    invoice = ConsolidatedInvoice(
        invoice_ref="#REC-TEST-DB-01",
        client_name="Station Atlas Marrakech",
        date_str="17/08/2026",
        items=[
            ConsolidatedItem(index=1, description="185/65 R15 (P)", quantity=8, unit_price=450.0, subtotal=3600.0),
            ConsolidatedItem(index=2, description="315/80 R22.5 (HW)", quantity=4, unit_price=2200.0, subtotal=8800.0),
        ],
        total_quantity=12,
        distinct_items_count=2,
        grand_total=12400.0,
        source_invoices_count=2,
    )

    # 1. Save invoice
    inv_id = test_db.save_consolidated_invoice(invoice, "Facture_TEST_DB_01.pdf", source="web")
    assert inv_id > 0

    # 2. Retrieve invoice
    record = test_db.get_invoice_by_ref("#REC-TEST-DB-01")
    assert record is not None
    assert record["client_name"] == "Station Atlas Marrakech"
    assert record["total_quantity"] == 12
    assert record["grand_total"] == 12400.0
    assert len(record["items"]) == 2

    # 3. Analytics
    analytics = test_db.get_analytics_summary()
    assert analytics["total_invoices"] == 1
    assert analytics["total_tyres"] == 12
    assert analytics["total_revenue"] == 12400.0
    assert len(analytics["top_dimensions"]) == 2

    # 4. Search and pagination
    invoices, total = test_db.get_invoices(search="Atlas")
    assert total == 1
    assert invoices[0]["invoice_ref"] == "#REC-TEST-DB-01"

    # 5. Delete invoice
    deleted = test_db.delete_invoice_by_ref("#REC-TEST-DB-01")
    assert deleted is True
    assert test_db.get_invoice_by_ref("#REC-TEST-DB-01") is None


# ---------------------------------------------------------------------------
# FastAPI REST API Tests
# ---------------------------------------------------------------------------

def test_fastapi_endpoints():
    """Test web dashboard API endpoints."""
    client = TestClient(app)

    # 1. Test GET /
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "TyreConsolidator" in res_home.text or "Consolidation" in res_home.text

    # 2. Test GET /api/analytics
    res_analytics = client.get("/api/analytics")
    assert res_analytics.status_code == 200
    data_analytics = res_analytics.json()
    assert "total_revenue" in data_analytics
    assert "top_dimensions" in data_analytics

    # 3. Test GET /api/invoices
    res_invoices = client.get("/api/invoices")
    assert res_invoices.status_code == 200
    data_invoices = res_invoices.json()
    assert "invoices" in data_invoices

    # 4. Test GET /api/settings and POST /api/settings
    res_settings = client.get("/api/settings")
    assert res_settings.status_code == 200

    res_update_settings = client.post(
        "/api/settings",
        json={
            "company_name": "Tous Pneus",
            "company_address": "189 LOT ANOUAR SIDI BENNOUR MAROC Sidi Bennour",
            "company_phone": "+212618468839",
            "company_email": "oraiche-pneus@gmail.com",
            "currency": "MAD",
        },
    )
    assert res_update_settings.status_code == 200
    updated = res_update_settings.json()
    assert updated["company_name"] == "Tous Pneus"
    assert updated["company_address"] == "189 LOT ANOUAR SIDI BENNOUR MAROC Sidi Bennour"
    assert updated["company_phone"] == "+212618468839"
    assert updated["company_email"] == "oraiche-pneus@gmail.com"
    assert updated["currency"] == "MAD"


def test_split_dimension_and_brand():
    """Test splitting tyre normalized descriptions into separate reference and brand."""
    from consolidator import split_dimension_and_brand

    dim1, brand1 = split_dimension_and_brand("195 R14 (LANDSPIDER)")
    assert dim1 == "195 R14"
    assert brand1 == "Landspider"

    dim2, brand2 = split_dimension_and_brand("175/70 R13 (LASSA)")
    assert dim2 == "175/70 R13"
    assert brand2 == "Lassa"

    dim3, brand3 = split_dimension_and_brand("205/55 R16")
    assert dim3 == "205/55 R16"
    assert brand3 == ""


def test_user_reference_sample_pdf_generation():
    """Test generating a PDF invoice matching the exact layout and data from the user's sample image."""
    invoice = ConsolidatedInvoice(
        invoice_ref="#REC-2026-08-0042",
        client_name="GARAGE CASABLANCA",
        client_address="189 LOT ANOUAR SIDI BENNOUR MAROC Sidi Bennour",
        date_str="17/08/2026",
        transaction_date="17/08/2026 à 16:22",
        transaction_status="En attente",
        items=[
            ConsolidatedItem(
                index=1,
                description="195 R14 (LANDSPIDER)",
                reference="195 R14",
                brand="Landspider",
                quantity=6,
                unit_price=650.0,
                subtotal=3900.0,
            ),
        ],
        total_quantity=6,
        distinct_items_count=1,
        grand_total=3900.0,
        source_invoices_count=1,
    )

    pdf_path = pdf_generator.generate_pdf_sync(invoice, output_filename="sample_user_invoice.pdf")
    assert pdf_path.exists()
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 1000


def test_deepseek_settings_and_models():
    """Test DeepSeek settings updating and models endpoint."""
    from fastapi.testclient import TestClient
    from app import app
    from config import settings

    client = TestClient(app)

    # 1. Update settings with DeepSeek configuration
    res = client.post(
        "/api/settings",
        json={
            "ai_provider": "deepseek",
            "deepseek_api_key": "sk-mock-deepseek-test-key",
            "deepseek_model": "deepseek-chat",
            "deepseek_base_url": "https://api.deepseek.com",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ai_provider"] == "deepseek"
    assert data["deepseek_model"] == "deepseek-chat"
    assert data["deepseek_api_key_configured"] is True
    assert settings.ai_provider == "deepseek"
    assert settings.deepseek_model == "deepseek-chat"

    # 2. Test DeepSeek models endpoint
    res_models = client.post(
        "/api/settings/models",
        json={"provider": "deepseek"},
    )
    assert res_models.status_code == 200
    models_data = res_models.json()
    assert models_data["provider"] == "deepseek"
    assert len(models_data["models"]) >= 2
    model_ids = [m["id"] for m in models_data["models"]]
    assert "deepseek-chat" in model_ids
    assert "deepseek-reasoner" in model_ids

    # 3. Restore gemini as default provider
    client.post("/api/settings", json={"ai_provider": "gemini"})
    assert settings.ai_provider == "gemini"


def test_deepseek_clean_json_markdown():
    """Test cleaning JSON strings returned from DeepSeek with markdown fences."""
    from extractor import _clean_json_markdown, SingleInvoiceExtraction

    raw_markdown = '```json\n{"invoice_number": "123", "client_name": "Test Client", "items": [{"raw_description": "175/70 R13 (L)", "quantity": 4, "unit_price": 450.0}]}\n```'
    cleaned = _clean_json_markdown(raw_markdown)
    import json
    data = json.loads(cleaned)
    extraction = SingleInvoiceExtraction.model_validate(data)
    assert extraction.invoice_number == "123"
    assert len(extraction.items) == 1
    assert extraction.items[0].raw_description == "175/70 R13 (L)"
    assert extraction.items[0].quantity == 4
    assert extraction.items[0].unit_price == 450.0


def test_magaza_item_and_pdf_generation():
    """Test generating a Magaza-grouped PDF invoice matching the user reference layout."""
    items = [
        ConsolidatedItem(
            index=1,
            description="155 R12 C (BOTO)",
            reference="155 R12 C",
            brand="Boto",
            depot="magaza 4",
            quantity=4,
            unit_price=400.0,
            subtotal=1600.0,
        ),
        ConsolidatedItem(
            index=2,
            description="225/45 R17 91V XL (DELINTE)",
            reference="225/45 R17 91V XL",
            brand="Delinte",
            depot="magaza 4",
            quantity=2,
            unit_price=700.0,
            subtotal=1400.0,
        ),
        ConsolidatedItem(
            index=3,
            description="215/55 R16 93V (DELINTE)",
            reference="215/55 R16 93V",
            brand="Delinte",
            depot="magaza 4",
            quantity=4,
            unit_price=725.0,
            subtotal=2900.0,
        ),
        ConsolidatedItem(
            index=4,
            description="205/55 R16 91V (BOTO)",
            reference="205/55 R16 91V",
            brand="Boto",
            depot="magaza 3",
            quantity=2,
            unit_price=520.0,
            subtotal=1040.0,
        ),
        ConsolidatedItem(
            index=5,
            description="205/55 R16 91V (GOODYEAR)",
            reference="205/55 R16 91V",
            brand="Goodyear",
            depot="magaza 3",
            quantity=3,
            unit_price=660.0,
            subtotal=1980.0,
        ),
        ConsolidatedItem(
            index=6,
            description="185/65 R15 88T (DELINTE)",
            reference="185/65 R15 88T",
            brand="Delinte",
            depot="magaza 1",
            quantity=4,
            unit_price=480.0,
            subtotal=1920.0,
        ),
        ConsolidatedItem(
            index=7,
            description="165/60 R14 75H (DELINTE)",
            reference="165/60 R14 75H",
            brand="Delinte",
            depot="magaza 2",
            quantity=2,
            unit_price=450.0,
            subtotal=900.0,
        ),
    ]

    total_qty = sum(it.quantity for it in items)
    grand_tot = sum(it.subtotal for it in items)

    invoice = ConsolidatedInvoice(
        invoice_ref="#REC-2026-MAGAZA-TEST",
        client_name="Transport Express Maroc",
        client_address="Casablanca",
        date_str="30/08/2026",
        transaction_date="30/08/2026 à 22:00",
        transaction_status="Validé",
        items=items,
        total_quantity=total_qty,
        distinct_items_count=len(items),
        grand_total=grand_tot,
        source_invoices_count=4,
    )

    pdf_path = pdf_generator.generate_magaza_pdf_sync(invoice, "test_magaza_invoice.pdf")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000


def test_magaza_database_and_endpoints():
    """Test persisting depot assignments and recalculating via REST API."""
    from database import db as app_db

    items = [
        ConsolidatedItem(
            index=1,
            description="175/70 R13 (LASSA)",
            reference="175/70 R13",
            brand="LASSA",
            depot="magaza 1",
            quantity=4,
            unit_price=450.0,
            subtotal=1800.0,
        ),
        ConsolidatedItem(
            index=2,
            description="205/55 R16 (PETLAS)",
            reference="205/55 R16",
            brand="PETLAS",
            depot="magaza 3",
            quantity=2,
            unit_price=600.0,
            subtotal=1200.0,
        ),
    ]

    invoice = ConsolidatedInvoice(
        invoice_ref="#REC-2026-MAG-DB",
        client_name="Client Dépôt",
        date_str="30/08/2026",
        items=items,
        total_quantity=6,
        distinct_items_count=2,
        grand_total=3000.0,
        source_invoices_count=1,
    )

    invoice_id = app_db.save_consolidated_invoice(invoice, "test_mag_db.pdf", source="web_magaza")
    assert invoice_id > 0

    fetched = app_db.get_invoice_by_ref("#REC-2026-MAG-DB")
    assert fetched is not None
    assert fetched["client_name"] == "Client Dépôt"
    assert len(fetched["items"]) == 2
    assert fetched["items"][0]["depot"] == "magaza 1"
    assert fetched["items"][1]["depot"] == "magaza 3"

    # Test endpoints with TestClient
    client = TestClient(app)
    recalc_res = client.post(
        "/api/invoices/%23REC-2026-MAG-DB/recalculate-magaza",
        json={
            "client_name": "Client Dépôt Modifié",
            "items": [
                {
                    "description": "175/70 R13 (LASSA)",
                    "reference": "175/70 R13",
                    "brand": "LASSA",
                    "depot": "magaza 2",
                    "quantity": 8,
                    "unit_price": 450.0,
                },
                {
                    "description": "205/55 R16 (PETLAS)",
                    "reference": "205/55 R16",
                    "brand": "PETLAS",
                    "depot": "magaza 4",
                    "quantity": 4,
                    "unit_price": 600.0,
                },
            ],
        },
    )
    assert recalc_res.status_code == 200
    recalc_data = recalc_res.json()
    assert recalc_data["success"] is True
    assert recalc_data["invoice"]["client_name"] == "Client Dépôt Modifié"
    assert recalc_data["invoice"]["total_quantity"] == 12
    assert recalc_data["invoice"]["items"][0]["depot"] == "magaza 2"
    assert recalc_data["invoice"]["items"][1]["depot"] == "magaza 4"

    # Test PDF download endpoint
    pdf_res = client.get("/api/invoices/%23REC-2026-MAG-DB/pdf-magaza")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"

    # Cleanup test record
    app_db.delete_invoice_by_ref("#REC-2026-MAG-DB")


