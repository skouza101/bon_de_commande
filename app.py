"""FastAPI Web Dashboard Application for Tyre Invoice Consolidation.

Provides interactive web interface, REST APIs for receipt scanning, live item editing,
real-time analytics, PDF previews, and invoice archive management.
"""

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import settings, update_env_file
from consolidator import (
    ConsolidatedInvoice,
    ConsolidatedItem,
    consolidate_extractions,
    normalize_tyre_description,
    split_dimension_and_brand,
)
from database import db
from extractor import extractor, SingleInvoiceExtraction, VisionExtractionError
from pdf_generator import pdf_generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tyre_dashboard")

# Initialize FastAPI application
app = FastAPI(
    title="Tyre Invoice Consolidator Dashboard",
    description="Web Dashboard for Handwritten Tyre Receipt Ingestion & Consolidation",
    version="2.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure static directories exist
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class UpdateItemPayload(BaseModel):
    description: str
    reference: Optional[str] = None
    brand: Optional[str] = None
    depot: Optional[str] = "magaza 1"
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.0)


class RecalculateInvoiceRequest(BaseModel):
    client_name: Optional[str] = None
    client_address: Optional[str] = None
    transaction_status: Optional[str] = None
    items: List[UpdateItemPayload]


class SettingsUpdateRequest(BaseModel):
    ai_provider: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    currency: Optional[str] = None
    gemini_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    deepseek_base_url: Optional[str] = None


class TestKeyRequest(BaseModel):
    provider: Optional[str] = "gemini"
    gemini_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: Optional[str] = None
    deepseek_model: Optional[str] = None


# ---------------------------------------------------------------------------
# Web Page Route
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serve the main Single Page Application dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "company_name": settings.company_name,
            "company_address": settings.company_address,
            "company_phone": settings.company_phone,
            "company_email": settings.company_email,
            "currency": settings.currency,
            "ai_provider": settings.ai_provider,
            "gemini_configured": bool(settings.gemini_api_key and settings.gemini_api_key.strip()),
            "deepseek_configured": bool(settings.deepseek_api_key and settings.deepseek_api_key.strip()),
        },
    )


# ---------------------------------------------------------------------------
# Analytics REST API
# ---------------------------------------------------------------------------

@app.get("/api/analytics")
async def get_analytics():
    """Return live KPI summary, top tyre dimensions, and recent invoices."""
    try:
        data = db.get_analytics_summary()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load analytics data",
        )


# ---------------------------------------------------------------------------
# Invoice Archive & Detail Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/invoices")
async def list_invoices(search: Optional[str] = None, limit: int = 50, offset: int = 0):
    """Retrieve archived invoices with optional search filter."""
    invoices, total = db.get_invoices(limit=limit, offset=offset, search=search or "")
    return JSONResponse(content={"invoices": invoices, "total": total})


@app.get("/api/invoices/{invoice_ref}")
async def get_invoice_detail(invoice_ref: str):
    """Get full details of a specific invoice including its line items."""
    invoice = db.get_invoice_by_ref(invoice_ref)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_ref}' not found.",
        )
    return JSONResponse(content=invoice)


@app.get("/api/invoices/{invoice_ref}/pdf")
async def get_invoice_pdf(invoice_ref: str, download: bool = False):
    """Stream or download the compiled PDF document for a specific invoice."""
    invoice = db.get_invoice_by_ref(invoice_ref)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_ref}' not found.",
        )

    pdf_filename = invoice.get("pdf_filename") or f"Facture_{invoice_ref.replace('#', '')}.pdf"

    items = []
    for idx, it in enumerate(invoice.get("items", [])):
        desc = it["description"]
        dim, brand = split_dimension_and_brand(desc)
        ref = it.get("reference") or dim or desc
        b_name = it.get("brand") or brand or ""
        items.append(
            ConsolidatedItem(
                index=it.get("index_num", idx + 1),
                description=desc,
                reference=ref,
                brand=b_name,
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                subtotal=it["subtotal"],
            )
        )
    consolidated = ConsolidatedInvoice(
        invoice_ref=invoice["invoice_ref"],
        client_name=invoice["client_name"],
        client_address=invoice.get("client_address") or "",
        date_str=invoice["date_str"],
        transaction_date=invoice.get("transaction_date") or invoice["date_str"],
        transaction_status=invoice.get("transaction_status") or "En attente",
        items=items,
        total_quantity=invoice["total_quantity"],
        distinct_items_count=invoice["distinct_items_count"],
        grand_total=invoice["grand_total"],
        source_invoices_count=invoice["source_invoices_count"],
    )
    pdf_path = await pdf_generator.generate_pdf(consolidated, output_filename=pdf_filename)

    disposition = "attachment" if download else "inline"
    clean_ref = invoice_ref.replace("#", "").strip()
    download_filename = f"Facture_{clean_ref}.pdf"

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{download_filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/invoices/{invoice_ref}/pdf-magaza")
async def get_invoice_pdf_magaza(invoice_ref: str, download: bool = False):
    """Retrieve or dynamically generate the Magaza-grouped PDF document for an invoice."""
    invoice = db.get_invoice_by_ref(invoice_ref)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_ref}' not found.",
        )

    sanitized_ref = invoice_ref.replace("#", "").replace("/", "_").strip()
    pdf_filename = f"Facture_Magaza_{sanitized_ref}.pdf"

    items: List[ConsolidatedItem] = []
    for idx, it in enumerate(invoice.get("items", [])):
        desc = it["description"]
        dim, brand = split_dimension_and_brand(desc)
        ref = it.get("reference") or dim or desc
        b_name = it.get("brand") or brand or ""
        depot_name = it.get("depot") or "magaza 1"
        items.append(
            ConsolidatedItem(
                index=it.get("index_num", idx + 1),
                description=desc,
                reference=ref,
                brand=b_name,
                depot=depot_name,
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                subtotal=it["subtotal"],
            )
        )
    consolidated = ConsolidatedInvoice(
        invoice_ref=invoice["invoice_ref"],
        client_name=invoice["client_name"],
        client_address=invoice.get("client_address") or "",
        date_str=invoice["date_str"],
        transaction_date=invoice.get("transaction_date") or invoice["date_str"],
        transaction_status=invoice.get("transaction_status") or "En attente",
        items=items,
        total_quantity=invoice["total_quantity"],
        distinct_items_count=invoice["distinct_items_count"],
        grand_total=invoice["grand_total"],
        source_invoices_count=invoice["source_invoices_count"],
    )
    pdf_path = await pdf_generator.generate_magaza_pdf(consolidated, output_filename=pdf_filename)

    disposition = "attachment" if download else "inline"
    clean_ref = invoice_ref.replace("#", "").strip()
    download_filename = f"Facture_Magaza_{clean_ref}.pdf"

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{download_filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.delete("/api/invoices/{invoice_ref}")
async def delete_invoice(invoice_ref: str):
    """Permanently delete an invoice and its line items."""
    success = db.delete_invoice_by_ref(invoice_ref)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_ref}' not found.",
        )
    return JSONResponse(content={"success": True, "message": f"Facture {invoice_ref} supprimée."})


# ---------------------------------------------------------------------------
# Receipt Scanner Endpoint (Vision AI Extraction)
# ---------------------------------------------------------------------------

@app.post("/api/scan")
async def scan_receipts(
    files: List[UploadFile] = File(...),
    client_name: Optional[str] = Form(None),
):
    """Ingest uploaded receipt images, extract handwritten items via active AI engine, and generate PDF."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier envoyé.",
        )

    # Validate active provider API key upfront
    active_provider = (settings.ai_provider or "gemini").strip().lower()
    if active_provider == "deepseek":
        if not settings.deepseek_api_key or not settings.deepseek_api_key.strip():
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "⚠️ La clé d'accès DeepSeek n'est pas configurée ! Rendez-vous dans l'onglet '⚙️ Paramètres' pour renseigner votre clé DeepSeek.",
                    "invoice": None,
                },
            )
    else:
        if not settings.gemini_api_key or not settings.gemini_api_key.strip():
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "⚠️ La clé d'accès Google Gemini n'est pas configurée ! Rendez-vous dans l'onglet '⚙️ Paramètres' pour renseigner votre clé.",
                    "invoice": None,
                },
            )

    session_id = uuid.uuid4().hex[:8]
    batch_dir = settings.temp_dir / f"web_batch_{session_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: List[Path] = []

    try:
        # 1. Save uploaded files to temporary storage
        for file in files:
            ext = Path(file.filename or "receipt.jpg").suffix or ".jpg"
            dest = batch_dir / f"{uuid.uuid4().hex}{ext}"
            with open(dest, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_paths.append(dest)

        # 2. Extract handwritten data with configured AI engine (Gemini or DeepSeek)
        extractions: List[SingleInvoiceExtraction] = await extractor.extract_from_images(saved_paths)
        valid_extractions = [ext for ext in extractions if ext.items]

        if not valid_extractions:
            logger.warning("No line items extracted from uploaded images.")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "Aucun article lisible n'a été détecté dans les photos envoyées. Veuillez vérifier la netteté de l'image.",
                    "invoice": None,
                },
            )

        # 3. Consolidate matching tyre dimensions and prices
        consolidated = consolidate_extractions(
            extractions=valid_extractions,
            client_name_override=client_name,
        )

        # 4. Generate PDF invoice
        sanitized_ref = consolidated.invoice_ref.replace("#", "").replace("/", "_").strip()
        pdf_filename = f"Facture_{sanitized_ref}.pdf"
        pdf_path = await pdf_generator.generate_pdf(consolidated, output_filename=pdf_filename)

        # 5. Persist to SQLite Database
        invoice_id = db.save_consolidated_invoice(
            invoice=consolidated,
            pdf_filename=pdf_filename,
            source="web",
            image_paths=[str(p) for p in saved_paths],
        )

        return JSONResponse(
            content={
                "success": True,
                "invoice_id": invoice_id,
                "invoice": consolidated.model_dump(),
                "pdf_url": f"/api/invoices/{consolidated.invoice_ref}/pdf",
            }
        )

    except VisionExtractionError as ve:
        logger.warning(f"Vision extraction error: {ve}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": False,
                "message": f"Erreur de reconnaissance IA : {str(ve)}",
                "invoice": None,
            },
        )
    except Exception as e:
        logger.error(f"Error scanning receipts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan error: {str(e)}",
        )

    finally:
        # Clean up temporary batch folder
        if batch_dir.exists():
            shutil.rmtree(batch_dir, ignore_errors=True)


@app.post("/api/scan-magaza")
async def scan_receipts_magaza(
    files: List[UploadFile] = File(...),
    client_name: Optional[str] = Form(None),
    default_depot: Optional[str] = Form("magaza 1"),
):
    """Ingest uploaded receipt images, extract items, set default depot, and generate Magaza PDF."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier envoyé.",
        )

    active_provider = (settings.ai_provider or "gemini").strip().lower()
    if active_provider == "deepseek":
        if not settings.deepseek_api_key or not settings.deepseek_api_key.strip():
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "⚠️ La clé d'accès DeepSeek n'est pas configurée ! Rendez-vous dans l'onglet '⚙️ Paramètres' pour renseigner votre clé DeepSeek.",
                    "invoice": None,
                },
            )
    else:
        if not settings.gemini_api_key or not settings.gemini_api_key.strip():
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "⚠️ La clé d'accès Google Gemini n'est pas configurée ! Rendez-vous dans l'onglet '⚙️ Paramètres' pour renseigner votre clé.",
                    "invoice": None,
                },
            )

    session_id = uuid.uuid4().hex[:8]
    batch_dir = settings.temp_dir / f"web_magaza_batch_{session_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: List[Path] = []

    try:
        for file in files:
            ext = Path(file.filename or "receipt.jpg").suffix or ".jpg"
            dest = batch_dir / f"{uuid.uuid4().hex}{ext}"
            with open(dest, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_paths.append(dest)

        extractions: List[SingleInvoiceExtraction] = await extractor.extract_from_images(saved_paths)
        valid_extractions = [ext for ext in extractions if ext.items]

        if not valid_extractions:
            logger.warning("No line items extracted from uploaded images.")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "Aucun article lisible n'a été détecté dans les photos envoyées. Veuillez vérifier la netteté de l'image.",
                    "invoice": None,
                },
            )

        consolidated = consolidate_extractions(
            extractions=valid_extractions,
            client_name_override=client_name,
        )

        depot_choice = (default_depot or "magaza 1").strip()
        for item in consolidated.items:
            item.depot = depot_choice

        sanitized_ref = consolidated.invoice_ref.replace("#", "").replace("/", "_").strip()
        pdf_filename = f"Facture_Magaza_{sanitized_ref}.pdf"
        pdf_path = await pdf_generator.generate_magaza_pdf(consolidated, output_filename=pdf_filename)

        invoice_id = db.save_consolidated_invoice(
            invoice=consolidated,
            pdf_filename=pdf_filename,
            source="web_magaza",
            image_paths=[str(p) for p in saved_paths],
        )

        return JSONResponse(
            content={
                "success": True,
                "invoice_id": invoice_id,
                "invoice": consolidated.model_dump(),
                "pdf_url": f"/api/invoices/{consolidated.invoice_ref}/pdf-magaza",
            }
        )

    except VisionExtractionError as ve:
        logger.warning(f"Vision extraction error: {ve}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": False,
                "message": f"Erreur de reconnaissance IA : {str(ve)}",
                "invoice": None,
            },
        )
    except Exception as e:
        logger.error(f"Error scanning receipts for magaza: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan error: {str(e)}",
        )
    finally:
        if batch_dir.exists():
            shutil.rmtree(batch_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Recalculate & Edit Line Items Endpoint
# ---------------------------------------------------------------------------

@app.post("/api/invoices/{invoice_ref}/recalculate")
async def recalculate_invoice(invoice_ref: str, payload: RecalculateInvoiceRequest):
    """Update line items, client details, recalculate totals, update DB and regenerate PDF."""
    existing = db.get_invoice_by_ref(invoice_ref)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_ref}' not found.",
        )

    client_name = payload.client_name if payload.client_name is not None else existing["client_name"]
    client_address = payload.client_address if payload.client_address is not None else existing.get("client_address", "")
    transaction_status = payload.transaction_status if payload.transaction_status is not None else existing.get("transaction_status", "En attente")

    merged_items: Dict[str, Dict[str, Any]] = {}
    for raw_item in payload.items:
        norm_desc = normalize_tyre_description(raw_item.description)
        qty = int(raw_item.quantity)
        price = round(float(raw_item.unit_price), 2)
        if qty <= 0:
            continue

        dim, brand = split_dimension_and_brand(norm_desc)
        ref = raw_item.reference or dim or norm_desc
        b_name = raw_item.brand or brand or ""

        key = f"{ref.upper()}|{b_name.upper()}"
        if key not in merged_items:
            merged_items[key] = {
                "description": norm_desc,
                "reference": ref,
                "brand": b_name,
                "depot": raw_item.depot or "magaza 1",
                "quantity": qty,
                "unit_price": price,
            }
        else:
            merged_items[key]["quantity"] += qty
            if price > 0:
                merged_items[key]["unit_price"] = price

    items: List[ConsolidatedItem] = []
    total_qty = 0
    grand_total = 0.0

    for idx, (k, d) in enumerate(merged_items.items(), start=1):
        qty = d["quantity"]
        p = d["unit_price"]
        sub = round(qty * p, 2)
        total_qty += qty
        grand_total += sub

        items.append(
            ConsolidatedItem(
                index=idx,
                description=d["description"],
                reference=d["reference"],
                brand=d["brand"],
                depot=d["depot"],
                quantity=qty,
                unit_price=p,
                subtotal=sub,
            )
        )

    consolidated = ConsolidatedInvoice(
        invoice_ref=invoice_ref,
        client_name=client_name,
        client_address=client_address,
        date_str=existing["date_str"],
        transaction_date=existing.get("transaction_date") or existing["date_str"],
        transaction_status=transaction_status,
        items=items,
        total_quantity=total_qty,
        distinct_items_count=len(items),
        grand_total=round(grand_total, 2),
        source_invoices_count=existing["source_invoices_count"],
    )

    # Regenerate PDF
    pdf_filename = existing["pdf_filename"]
    await pdf_generator.generate_pdf(consolidated, output_filename=pdf_filename)

    # Update in Database
    db.save_consolidated_invoice(
        invoice=consolidated,
        pdf_filename=pdf_filename,
        source=existing.get("source", "web"),
    )

    return JSONResponse(
        content={
            "success": True,
            "invoice": consolidated.model_dump(),
            "pdf_url": f"/api/invoices/{invoice_ref}/pdf",
        }
    )


@app.post("/api/invoices/{invoice_ref}/recalculate-magaza")
async def recalculate_invoice_magaza(invoice_ref: str, payload: RecalculateInvoiceRequest):
    """Update line items with assigned depots, recalculate totals, update DB and regenerate Magaza PDF."""
    existing = db.get_invoice_by_ref(invoice_ref)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_ref}' not found.",
        )

    client_name = payload.client_name if payload.client_name is not None else existing["client_name"]
    client_address = payload.client_address if payload.client_address is not None else existing.get("client_address", "")
    transaction_status = payload.transaction_status if payload.transaction_status is not None else existing.get("transaction_status", "En attente")

    merged_items: Dict[str, Dict[str, Any]] = {}
    for raw_item in payload.items:
        norm_desc = normalize_tyre_description(raw_item.description)
        qty = int(raw_item.quantity)
        price = round(float(raw_item.unit_price), 2)
        if qty <= 0:
            continue

        dim, brand = split_dimension_and_brand(norm_desc)
        ref = raw_item.reference or dim or norm_desc
        b_name = raw_item.brand or brand or ""
        depot_val = (raw_item.depot or "magaza 1").strip()

        key = f"{ref.upper()}|{b_name.upper()}|{depot_val.lower()}"
        if key not in merged_items:
            merged_items[key] = {
                "description": norm_desc,
                "reference": ref,
                "brand": b_name,
                "depot": depot_val,
                "quantity": qty,
                "unit_price": price,
            }
        else:
            merged_items[key]["quantity"] += qty
            if price > 0:
                merged_items[key]["unit_price"] = price

    items: List[ConsolidatedItem] = []
    total_qty = 0
    grand_total = 0.0

    for idx, (k, d) in enumerate(merged_items.items(), start=1):
        qty = d["quantity"]
        p = d["unit_price"]
        sub = round(qty * p, 2)
        total_qty += qty
        grand_total += sub

        items.append(
            ConsolidatedItem(
                index=idx,
                description=d["description"],
                reference=d["reference"],
                brand=d["brand"],
                depot=d["depot"],
                quantity=qty,
                unit_price=p,
                subtotal=sub,
            )
        )

    consolidated = ConsolidatedInvoice(
        invoice_ref=invoice_ref,
        client_name=client_name,
        client_address=client_address,
        date_str=existing["date_str"],
        transaction_date=existing.get("transaction_date") or existing["date_str"],
        transaction_status=transaction_status,
        items=items,
        total_quantity=total_qty,
        distinct_items_count=len(items),
        grand_total=round(grand_total, 2),
        source_invoices_count=existing["source_invoices_count"],
    )

    sanitized_ref = invoice_ref.replace("#", "").replace("/", "_").strip()
    pdf_filename = f"Facture_Magaza_{sanitized_ref}.pdf"
    await pdf_generator.generate_magaza_pdf(consolidated, output_filename=pdf_filename)

    db.save_consolidated_invoice(
        invoice=consolidated,
        pdf_filename=pdf_filename,
        source=existing.get("source", "web_magaza"),
    )

    return JSONResponse(
        content={
            "success": True,
            "invoice": consolidated.model_dump(),
            "pdf_url": f"/api/invoices/{invoice_ref}/pdf-magaza",
        }
    )


# ---------------------------------------------------------------------------
# Settings Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/settings")
async def get_settings():
    """Get current application settings."""
    gemini_masked = ""
    if settings.gemini_api_key and settings.gemini_api_key.strip():
        key = settings.gemini_api_key.strip()
        gemini_masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "••••••••"

    deepseek_masked = ""
    if settings.deepseek_api_key and settings.deepseek_api_key.strip():
        key = settings.deepseek_api_key.strip()
        deepseek_masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "••••••••"

    return JSONResponse(
        content={
            "ai_provider": settings.ai_provider or "gemini",
            "company_name": settings.company_name,
            "company_address": settings.company_address,
            "company_phone": settings.company_phone,
            "company_email": settings.company_email,
            "currency": settings.currency,
            "gemini_model": settings.gemini_model,
            "gemini_api_key_configured": bool(settings.gemini_api_key and settings.gemini_api_key.strip()),
            "gemini_api_key_masked": gemini_masked,
            "deepseek_model": settings.deepseek_model or "deepseek-chat",
            "deepseek_base_url": settings.deepseek_base_url or "https://api.deepseek.com",
            "deepseek_api_key_configured": bool(settings.deepseek_api_key and settings.deepseek_api_key.strip()),
            "deepseek_api_key_masked": deepseek_masked,
            "bot_token_configured": bool(settings.bot_token and "MOCK" not in settings.bot_token),
        }
    )


@app.post("/api/settings")
async def update_settings(payload: SettingsUpdateRequest):
    """Update editable company branding, address, phone, email, currency, model, and API keys."""
    env_updates: Dict[str, str] = {}

    if payload.ai_provider is not None and payload.ai_provider.strip():
        settings.ai_provider = payload.ai_provider.strip().lower()
        env_updates["AI_PROVIDER"] = settings.ai_provider

    if payload.company_name is not None and payload.company_name.strip():
        settings.company_name = payload.company_name.strip()
        env_updates["COMPANY_NAME"] = settings.company_name

    if payload.company_address is not None and payload.company_address.strip():
        settings.company_address = payload.company_address.strip()
        env_updates["COMPANY_ADDRESS"] = settings.company_address

    if payload.company_phone is not None and payload.company_phone.strip():
        settings.company_phone = payload.company_phone.strip()
        env_updates["COMPANY_PHONE"] = settings.company_phone

    if payload.company_email is not None and payload.company_email.strip():
        settings.company_email = payload.company_email.strip()
        env_updates["COMPANY_EMAIL"] = settings.company_email

    if payload.currency is not None and payload.currency.strip():
        settings.currency = payload.currency.strip()
        env_updates["CURRENCY"] = settings.currency

    if payload.gemini_model is not None and payload.gemini_model.strip():
        settings.gemini_model = payload.gemini_model.strip()
        env_updates["GEMINI_MODEL"] = settings.gemini_model

    if payload.gemini_api_key is not None and payload.gemini_api_key.strip():
        settings.gemini_api_key = payload.gemini_api_key.strip()
        env_updates["GEMINI_API_KEY"] = settings.gemini_api_key

    if payload.deepseek_api_key is not None and payload.deepseek_api_key.strip():
        settings.deepseek_api_key = payload.deepseek_api_key.strip()
        env_updates["DEEPSEEK_API_KEY"] = settings.deepseek_api_key

    if payload.deepseek_model is not None and payload.deepseek_model.strip():
        settings.deepseek_model = payload.deepseek_model.strip()
        env_updates["DEEPSEEK_MODEL"] = settings.deepseek_model

    if payload.deepseek_base_url is not None and payload.deepseek_base_url.strip():
        settings.deepseek_base_url = payload.deepseek_base_url.strip()
        env_updates["DEEPSEEK_BASE_URL"] = settings.deepseek_base_url

    if env_updates:
        update_env_file(env_updates)

    gemini_masked = ""
    if settings.gemini_api_key and settings.gemini_api_key.strip():
        k = settings.gemini_api_key.strip()
        gemini_masked = f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "••••••••"

    deepseek_masked = ""
    if settings.deepseek_api_key and settings.deepseek_api_key.strip():
        k = settings.deepseek_api_key.strip()
        deepseek_masked = f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "••••••••"

    return JSONResponse(
        content={
            "success": True,
            "ai_provider": settings.ai_provider,
            "company_name": settings.company_name,
            "company_address": settings.company_address,
            "company_phone": settings.company_phone,
            "company_email": settings.company_email,
            "currency": settings.currency,
            "gemini_model": settings.gemini_model,
            "gemini_api_key_configured": bool(settings.gemini_api_key and settings.gemini_api_key.strip()),
            "gemini_api_key_masked": gemini_masked,
            "deepseek_model": settings.deepseek_model,
            "deepseek_base_url": settings.deepseek_base_url,
            "deepseek_api_key_configured": bool(settings.deepseek_api_key and settings.deepseek_api_key.strip()),
            "deepseek_api_key_masked": deepseek_masked,
        }
    )


def fetch_supported_gemini_models(api_key: str) -> List[Dict[str, Any]]:
    """Fetch live list of supported generative vision models for the given API key."""
    supported = []
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for m in client.models.list():
            raw_id = getattr(m, "name", "") or ""
            clean_id = raw_id.replace("models/", "").strip()
            display_name = getattr(m, "display_name", "") or clean_id
            
            is_gen = False
            actions = getattr(m, "supported_actions", None)
            if actions:
                if any("generateContent" in str(a) or "generate_content" in str(a) for a in actions):
                    is_gen = True
            elif "gemini" in clean_id.lower():
                is_gen = True

            if "embedding" in clean_id.lower() or "aqa" in clean_id.lower() or "imagen" in clean_id.lower() or "veo" in clean_id.lower():
                is_gen = False

            if is_gen and clean_id:
                supported.append({
                    "id": clean_id,
                    "name": display_name,
                    "description": getattr(m, "description", "") or "",
                    "is_flash": "flash" in clean_id.lower(),
                })
    except Exception as e:
        logger.warning(f"Failed to list models via google.genai: {e}")
        try:
            import google.generativeai as gai
            gai.configure(api_key=api_key)
            for m in gai.list_models():
                clean_id = m.name.replace("models/", "").strip()
                if "generateContent" in getattr(m, "supported_generation_methods", []) and "gemini" in clean_id.lower():
                    supported.append({
                        "id": clean_id,
                        "name": getattr(m, "display_name", "") or clean_id,
                        "description": getattr(m, "description", "") or "",
                        "is_flash": "flash" in clean_id.lower(),
                    })
        except Exception as e2:
            logger.warning(f"Failed to list models via google.generativeai: {e2}")

    if not supported:
        supported = [
            {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite (Ultra Rapide - Recommandé)", "description": "Modèle vision ultra rapide (2s)", "is_flash": True},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Modèle standard rapide", "is_flash": True},
            {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "description": "Modèle multimodal avancé", "is_flash": True},
            {"id": "gemini-3.7-flash", "name": "Gemini 3.7 Flash", "description": "Modèle avec capacités étendues", "is_flash": False},
        ]
    return supported


@app.get("/api/settings/models")
@app.post("/api/settings/models")
async def get_supported_models(payload: Optional[TestKeyRequest] = None):
    """Retrieve available models for the specified or active AI provider."""
    provider = payload.provider if (payload and payload.provider) else settings.ai_provider

    if provider == "deepseek":
        return JSONResponse(
            content={
                "success": True,
                "provider": "deepseek",
                "models": [
                    {"id": "deepseek-chat", "name": "DeepSeek Chat (V3)", "description": "Modèle général rapide & performant", "is_flash": True},
                    {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner (R1)", "description": "Modèle avec capacités de raisonnement avancé", "is_flash": False},
                ],
                "selected": settings.deepseek_model,
            }
        )

    # Gemini
    key = None
    if payload and payload.gemini_api_key and payload.gemini_api_key.strip():
        key = payload.gemini_api_key.strip()
    elif settings.gemini_api_key and settings.gemini_api_key.strip():
        key = settings.gemini_api_key.strip()

    if not key:
        return JSONResponse(
            content={
                "success": False,
                "provider": "gemini",
                "models": [
                    {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite (Ultra Rapide - Recommandé)", "is_flash": True},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "is_flash": True},
                    {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "is_flash": True},
                    {"id": "gemini-3.7-flash", "name": "Gemini 3.7 Flash", "is_flash": False},
                ],
                "selected": settings.gemini_model,
            }
        )

    loop = asyncio.get_running_loop()
    models = await loop.run_in_executor(None, lambda: fetch_supported_gemini_models(key))
    return JSONResponse(
        content={
            "success": True,
            "provider": "gemini",
            "models": models,
            "selected": settings.gemini_model,
        }
    )


@app.post("/api/settings/test-key")
async def test_ai_key(payload: Optional[TestKeyRequest] = None):
    """Test API key connectivity and models for either Google Gemini or DeepSeek AI."""
    provider = payload.provider if (payload and payload.provider) else settings.ai_provider

    # 1. Test DeepSeek API
    if provider == "deepseek":
        key_to_test = None
        if payload and payload.deepseek_api_key and payload.deepseek_api_key.strip():
            key_to_test = payload.deepseek_api_key.strip()
        elif settings.deepseek_api_key and settings.deepseek_api_key.strip():
            key_to_test = settings.deepseek_api_key.strip()

        if not key_to_test:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"valid": False, "message": "Aucune clé DeepSeek fournie à tester."},
            )

        base_url = (payload.deepseek_base_url or settings.deepseek_base_url or "https://openrouter.ai/api/v1").rstrip("/")
        if key_to_test.startswith("sk-or-v1") and "openrouter" not in base_url:
            base_url = "https://openrouter.ai/api/v1"
        elif not base_url.endswith("/v1") and "deepseek.com" in base_url:
            base_url = f"{base_url}/v1"

        model = payload.deepseek_model or settings.deepseek_model or "deepseek/deepseek-v4-flash-0731"

        try:
            import openai
            headers = {
                "HTTP-Referer": "https://localhost:8000",
                "X-Title": "Tyre Consolidator",
            }
            client = openai.AsyncOpenAI(api_key=key_to_test, base_url=base_url, default_headers=headers)
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            if res and res.choices:
                provider_title = "OpenRouter" if "openrouter" in base_url else "DeepSeek"
                return JSONResponse(
                    content={
                        "valid": True,
                        "provider": "deepseek",
                        "model": model,
                        "message": f"Connexion {provider_title} validée avec succès (Moteur: {model}) ! ✅",
                    }
                )
        except Exception as ex:
            err_str = str(ex)
            logger.warning(f"DeepSeek/OpenRouter test key failed: {err_str}")
            user_msg = f"Échec de connexion : {err_str}"
            if "402" in err_str or "Insufficient Balance" in err_str:
                user_msg = "Clé authentifiée mais solde insuffisant (Insufficient Balance). Veuillez recharger votre compte."
            elif "401" in err_str or "Authentication" in err_str:
                user_msg = "Clé API invalide ou non autorisée (401 Authentication Fails)."
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"valid": False, "provider": "deepseek", "message": user_msg},
            )

    # 2. Test Google Gemini API
    key_to_test = None
    if payload and payload.gemini_api_key and payload.gemini_api_key.strip():
        key_to_test = payload.gemini_api_key.strip()
    elif settings.gemini_api_key and settings.gemini_api_key.strip():
        key_to_test = settings.gemini_api_key.strip()

    if not key_to_test:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"valid": False, "message": "Aucune clé Google Gemini fournie à tester."},
        )

    candidate_ids = [settings.gemini_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.7-flash"]
    # Deduplicate while preserving order
    seen_mods = set()
    unique_candidates = [m for m in candidate_ids if m and not (m in seen_mods or seen_mods.add(m))]

    working_model = None
    last_error = None
    loop = asyncio.get_running_loop()

    try:
        from google import genai
        client = genai.Client(api_key=key_to_test)
        supported_models = await loop.run_in_executor(None, lambda: fetch_supported_gemini_models(key_to_test))

        for mod in unique_candidates:
            try:
                def _probe(m=mod):
                    return client.models.generate_content(
                        model=m,
                        contents="Hello, reply with OK if you read this.",
                    )
                res = await loop.run_in_executor(None, _probe)
                if res and res.text:
                    working_model = mod
                    settings.gemini_model = mod
                    update_env_file({"GEMINI_MODEL": mod})
                    break
            except Exception as ex:
                last_error = ex
                err_str = str(ex)
                if "API_KEY" in err_str.upper() or "PERMISSION_DENIED" in err_str.upper() or "UNAUTHENTICATED" in err_str.upper():
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"valid": False, "message": f"Clé invalide : {err_str}"},
                    )
                continue

        if working_model:
            return JSONResponse(
                content={
                    "valid": True,
                    "provider": "gemini",
                    "model": working_model,
                    "supported_models": supported_models,
                    "message": f"Clé Google Gemini validée et connectée avec succès (Moteur: {working_model}) ! ✅",
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "valid": False,
                    "provider": "gemini",
                    "supported_models": supported_models,
                    "message": f"Échec de validation de la clé: {str(last_error)}",
                },
            )

    except Exception as e:
        logger.warning(f"Test Gemini API key failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"valid": False, "message": f"Échec de validation de la clé: {str(e)}"},
        )


# ---------------------------------------------------------------------------
# Server Startup Helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    settings.setup_directories()
    uvicorn.run(
        "app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
    )
