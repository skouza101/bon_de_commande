"""Data Normalization & Consolidation Engine for Tyre Invoices.

Standardizes handwritten tyre dimension strings, groups duplicate entries across
all submitted receipts, calculates consolidated quantities/subtotals, and fixes
any arithmetic discrepancies.
"""

import datetime
import random
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from extractor import RawInvoiceItem, SingleInvoiceExtraction


# ---------------------------------------------------------------------------
# Consolidated Pydantic Models
# ---------------------------------------------------------------------------

class ConsolidatedItem(BaseModel):
    """Consolidated line item after grouping identical tyres by description & unit price."""
    index: int = Field(description="1-based line item number")
    description: str = Field(description="Normalized tyre description, dimension, and brand code")
    reference: str = Field(default="", description="Tyre dimension/size reference e.g. 195 R14")
    brand: str = Field(default="", description="Tyre brand name e.g. Landspider")
    depot: str = Field(default="magaza 1", description="Depot or store identifier e.g. magaza 1, magaza 2, magaza 3, magaza 4")
    quantity: int = Field(description="Total consolidated quantity across all receipts", ge=1)
    unit_price: float = Field(description="Unit price in MAD / DH", ge=0.0)
    subtotal: float = Field(description="Line subtotal (quantity * unit_price)", ge=0.0)


class ConsolidatedInvoice(BaseModel):
    """Consolidated summary invoice data structure ready for PDF rendering & reporting."""
    invoice_ref: str = Field(description="Generated unique invoice reference, e.g., '#REC-2026-08-0042'")
    client_name: str = Field(description="Client or merchant name, defaulting if not specified")
    client_address: str = Field(default="", description="Client physical address")
    date_str: str = Field(description="Invoice date in DD/MM/YYYY format")
    transaction_date: str = Field(default="", description="Transaction date and time e.g. 17/08/2026 à 16:22")
    transaction_status: str = Field(default="En attente", description="Transaction status")
    items: List[ConsolidatedItem] = Field(default_factory=list, description="Consolidated line items")
    total_quantity: int = Field(default=0, description="Grand total count of tyres / pieces")
    distinct_items_count: int = Field(default=0, description="Count of distinct tyre line items")
    grand_total: float = Field(default=0.0, description="Grand total amount in MAD / DH")
    source_invoices_count: int = Field(default=1, description="Number of receipts consolidated")


# ---------------------------------------------------------------------------
# Brand Code Mapping Dictionary
# ---------------------------------------------------------------------------

BRAND_MAPPINGS: Dict[str, str] = {
    "L": "LASSA",
    "LASSA": "LASSA",
    "P": "PETLAS",
    "PETLAS": "PETLAS",
    "G": "GOODYEAR",
    "GY": "GOODYEAR",
    "GOODYEAR": "GOODYEAR",
    "ST": "STARMAXX",
    "STARMAXX": "STARMAXX",
    "LF": "LAUFENN",
    "LAUFENN": "LAUFENN",
    "HN": "HANKOOK",
    "HK": "HANKOOK",
    "HANKOOK": "HANKOOK",
    "M": "MICHELIN",
    "MI": "MICHELIN",
    "MICHELIN": "MICHELIN",
    "LE": "LEAO",
    "LEAO": "LEAO",
    "MT": "MONTREAL",
    "MONTREAL": "MONTREAL",
    "LS": "LANDSPIDER",
    "LANDSPIDER": "LANDSPIDER",
    "DL": "DELINTE",
    "DELINTE": "DELINTE",
    "TR": "TRIANGLE",
    "TRIANGLE": "TRIANGLE",
    "R": "ROTALLA",
    "ROTALLA": "ROTALLA",
    "A": "AMINE",
    "AMINE": "AMINE",
    "N": "NEXEN",
    "NX": "NEXEN",
    "NEXEN": "NEXEN",
    "BT": "BOTO",
    "BOTO": "BOTO",
    "AU": "AUSTONE",
    "AUSTONE": "AUSTONE",
    "SP": "SEMPERIT",
    "SEMPERIT": "SEMPERIT",
    "MM": "MOMO",
    "MOMO": "MOMO",
    "UN": "UNIROYAL",
    "UNIROYAL": "UNIROYAL",
    "SH": "SEHA",
    "SEHA": "SEHA",
    "D": "DUNLOP",
    "DUNLOP": "DUNLOP",
    "ML": "MILESTONE",
    "MILESTONE": "MILESTONE",
    "CS": "CITY STAR",
    "CITY STAR": "CITY STAR",
    "TF": "TIANFU",
    "TIANFU": "TIANFU",
    "F": "FIRESTONE",
    "FR": "FIRESTONE",
    "FIRESTONE": "FIRESTONE",
    "K": "KLEBER",
    "KL": "KLEBER",
    "KLEBER": "KLEBER",
    "DC": "DOUBLE COIN",
    "DOUBLE COIN": "DOUBLE COIN",
    "DVR": "DVR",
    "TM": "TRACMAX",
    "TRACMAX": "TRACMAX",
    "HW": "HW",
    "HEADWAY": "HEADWAY",
    "APLUS": "APLUS",
    "DOUBLESTAR": "DOUBLESTAR",
    "OVATION": "OVATION",
    "PIRELLI": "PIRELLI",
    "BRIDGESTONE": "BRIDGESTONE",
    "CONTINENTAL": "CONTINENTAL",
    "KUMHO": "KUMHO",
    "YOKOHAMA": "YOKOHAMA",
    "TOYO": "TOYO",
}


def resolve_brand_name(brand_raw: str) -> str:
    """Map a brand abbreviation or letter code strictly to its full standardized brand name."""
    if not brand_raw:
        return ""
    clean = brand_raw.strip().upper()
    if clean in BRAND_MAPPINGS:
        return BRAND_MAPPINGS[clean]
    
    # Check if any known brand name is a substring or close match
    for alias, standard in BRAND_MAPPINGS.items():
        if alias == clean or clean.startswith(alias):
            return standard
            
    # If not recognized in registered brand dictionary, do not invent artificial brand names
    return ""


# ---------------------------------------------------------------------------
# String Normalization Utilities
# ---------------------------------------------------------------------------

def normalize_tyre_description(raw: str) -> str:
    """Normalize handwritten tyre dimension and expand brand abbreviation codes.

    Examples:
        - "175 70 13 boto"          -> "175/70 R13 (BOTO)"
        - "175-70-R13 (boto)"       -> "175/70 R13 (BOTO)"
        - "175/70/13 (Boto)"        -> "175/70 R13 (BOTO)"
        - "175/65 R14 (L)"          -> "175/65 R14 (LASSA)"
        - "175/65 R14 (P)"          -> "175/65 R14 (PETLAS)"
        - "175/65 R14 (SH)"         -> "175/65 R14 (SEHA)"
        - "205 R14C (L)"            -> "205 R14C (LASSA)"
        - "205 14C"                 -> "205 R14C"
        - "215-65-16C ST"           -> "215/65 R16C (STARMAXX)"
        - "315/80/22.5"             -> "315/80 R22.5"
        - "185/65 R15 (DL)"         -> "185/65 R15 (DELINTE)"

    Args:
        raw: Raw description string extracted by Vision AI.

    Returns:
        Clean, standardized tyre description string with full brand name.
    """
    if not raw:
        return "ARTICLE DIVERS"

    text = raw.strip()
    # Replace multiple spaces / tabs
    text = re.sub(r"\s+", " ", text)

    # 1. Extract existing brand/pattern code in parentheses or at the end
    brand_code = ""
    # Check for explicit parentheses e.g. (BOTO) or (L) or (P)
    paren_match = re.search(r"\(([^)]+)\)", text)
    if paren_match:
        brand_code = resolve_brand_name(paren_match.group(1))
        # Remove the parenthesized part from text for dimension processing
        text = re.sub(r"\([^)]+\)", "", text).strip()

    # 2. Check for standard 3-part tyre sizes: Width / Aspect Ratio / Rim
    # e.g., "175 70 13", "175/70/13", "175-70-13", "175/70R13", "185/65 R15", "315/80 R22.5", "215/65 R16C"
    three_part_pattern = re.compile(
        r"(?:\b|^)(\d{3})[\s/\-]+(\d{2})[\s/\-]*(?:R|r|ZR|zr)?[\s/\-]*(\d{2}(?:\.5)?)\s*(C|c)?(?:\b|$)",
        re.IGNORECASE,
    )

    # 3. Check for 2-part commercial tyre sizes: Width / Rim (e.g. "205 R14C", "205 14C", "195 R15C")
    two_part_commercial_pattern = re.compile(
        r"(?:\b|^)(\d{3})[\s/\-]*(?:R|r)?[\s/\-]*(\d{2})\s*(C|c)(?:\b|$)",
        re.IGNORECASE,
    )

    norm_dimension = ""
    remaining_text = text

    match3 = three_part_pattern.search(text)
    if match3:
        width = match3.group(1)
        aspect = match3.group(2)
        rim = match3.group(3)
        c_suffix = "C" if match3.group(4) else ""
        norm_dimension = f"{width}/{aspect} R{rim}{c_suffix}"
        # Remove matched dimension from text to extract remaining words (e.g. brand)
        remaining_text = three_part_pattern.sub("", text).strip()
    else:
        match2 = two_part_commercial_pattern.search(text)
        if match2:
            width = match2.group(1)
            rim = match2.group(2)
            c_suffix = "C"
            norm_dimension = f"{width} R{rim}{c_suffix}"
            remaining_text = two_part_commercial_pattern.sub("", text).strip()

    # 4. If any remaining text exists and we didn't have a brand_code, look for brand words
    if remaining_text and not brand_code:
        # Clean remaining text
        clean_rem = re.sub(r"[^\w\s\-/]", "", remaining_text).strip()
        if clean_rem:
            brand_code = resolve_brand_name(clean_rem)

    # 5. Assemble final normalized description
    if norm_dimension:
        if brand_code:
            return f"{norm_dimension} ({brand_code})"
        return norm_dimension

    # Fallback if no specific tyre dimension regex matched: clean up & uppercase
    cleaned = re.sub(r"\s+", " ", text).strip().upper()
    if brand_code and f"({brand_code})" not in cleaned:
        return f"{cleaned} ({brand_code})"
    return cleaned if cleaned else "ARTICLE SANS NOM"


def split_dimension_and_brand(description: str) -> Tuple[str, str]:
    """Split a description like '195 R14 (LANDSPIDER)' into dimension ('195 R14') and brand ('Landspider')."""
    if not description:
        return ("", "")
    text = description.strip()
    match = re.search(r"\(([^)]+)\)", text)
    if match:
        brand_raw = match.group(1).strip()
        brand = resolve_brand_name(brand_raw)
        # Format brand in Title Case (e.g. Landspider) unless short acronym
        brand_formatted = brand.title() if len(brand) > 3 else brand.upper()
        dim = re.sub(r"\s*\([^)]+\)", "", text).strip()
        return (dim, brand_formatted)
    return (text, "")


# ---------------------------------------------------------------------------
# Aggregation & Consolidation Logic
# ---------------------------------------------------------------------------

def consolidate_extractions(
    extractions: List[SingleInvoiceExtraction],
    client_name_override: Optional[str] = None,
    client_address_override: Optional[str] = None,
    invoice_ref: Optional[str] = None,
) -> ConsolidatedInvoice:
    """Consolidate multiple invoice extractions into a single structured summary.

    Aggregation key: (normalized_description.upper(), unit_price)

    Calculations:
        - Consolidated Quantity = sum(quantity)
        - Line Subtotal = Consolidated Quantity * unit_price
        - Total Tyres = sum(Consolidated Quantity)
        - Grand Total = sum(Line Subtotal)

    Args:
        extractions: List of single invoice extraction models.
        client_name_override: Optional client name override.
        client_address_override: Optional client address override.
        invoice_ref: Optional custom invoice reference.

    Returns:
        ConsolidatedInvoice with aggregated items and summary metrics.
    """
    # Group items strictly by normalized description
    # Map: normalized_description -> dict(quantity, prices, depots)
    grouped: Dict[str, Dict[str, Any]] = {}
    detected_client_names: List[str] = []

    for ext in extractions:
        if ext.client_name and ext.client_name.strip():
            detected_client_names.append(ext.client_name.strip())

        for item in ext.items:
            norm_desc = normalize_tyre_description(item.raw_description)
            price = round(float(item.unit_price), 2)
            qty = int(item.quantity)
            if qty <= 0:
                continue

            key = norm_desc.strip()
            item_depot = getattr(item, "depot", None) or ""

            if key not in grouped:
                grouped[key] = {
                    "quantity": qty,
                    "prices": [price] if price > 0 else [],
                    "depots": [item_depot] if item_depot else [],
                }
            else:
                grouped[key]["quantity"] += qty
                if price > 0:
                    grouped[key]["prices"].append(price)
                if item_depot:
                    grouped[key]["depots"].append(item_depot)

    # Sort items by description alphabetically
    sorted_keys = sorted(grouped.keys())

    consolidated_items: List[ConsolidatedItem] = []
    total_quantity = 0
    grand_total = 0.0

    for idx, desc in enumerate(sorted_keys, start=1):
        data = grouped[desc]
        qty = data["quantity"]
        prices = data["prices"]
        # Use the highest non-zero unit price found across receipts, or 0.0
        final_price = max(prices) if prices else 0.0
        subtotal = round(qty * final_price, 2)
        total_quantity += qty
        grand_total += subtotal

        dim, brand = split_dimension_and_brand(desc)
        depot_val = data["depots"][0] if data["depots"] else "magaza 1"

        consolidated_items.append(
            ConsolidatedItem(
                index=idx,
                description=desc,
                reference=dim or desc,
                brand=brand,
                depot=depot_val,
                quantity=qty,
                unit_price=final_price,
                subtotal=subtotal,
            )
        )

    # Determine Client Name
    if client_name_override and client_name_override.strip():
        final_client = client_name_override.strip()
    elif detected_client_names:
        final_client = detected_client_names[0]
    else:
        final_client = ""

    # Generate Invoice Reference if not provided
    now = datetime.datetime.now()
    if not invoice_ref:
        rand_suffix = random.randint(1000, 9999)
        invoice_ref = f"#REC-{now.strftime('%Y-%m')}-{rand_suffix}"

    date_str = now.strftime("%d/%m/%Y")
    transaction_date = now.strftime("%d/%m/%Y à %H:%M")

    return ConsolidatedInvoice(
        invoice_ref=invoice_ref,
        client_name=final_client,
        client_address=(client_address_override or "").strip(),
        date_str=date_str,
        transaction_date=transaction_date,
        transaction_status="En attente",
        items=consolidated_items,
        total_quantity=total_quantity,
        distinct_items_count=len(consolidated_items),
        grand_total=round(grand_total, 2),
        source_invoices_count=len(extractions),
    )
