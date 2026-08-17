# Project Specification: Automated Handwritten Tyre Invoice Consolidator (Telegram Bot)

## 1. Project Overview & Objective
Build a production-ready, asynchronous Python Telegram Bot that automates the intake, handwritten OCR extraction, line-item consolidation, and PDF generation of tyre wholesale invoices.

### End-to-End User Flow:
1. **User Action:** The user sends one or multiple photos of handwritten paper invoices via Telegram (supporting single uploads or multi-image Telegram Albums / `media_group_id`).
2. **Buffering & Intake:** The bot debounces album uploads within a 3–4 second sliding window, collects all image file paths, and updates the user with dynamic status messages.
3. **Vision LLM Extraction:** Concurrently processes all images using a multimodal Vision LLM (e.g., `gemini-1.5-flash` or `gpt-4o-mini`) to extract line items directly into a strict Pydantic schema.
4. **Data Normalization & Consolidation:** Standardizes tyre dimension strings, groups duplicate entries across all submitted receipts, computes consolidated quantities/subtotals, and fixes any arithmetic inconsistencies from paper slips.
5. **PDF Generation & Delivery:** Compiles a clean, printable A4 PDF invoice in **French** (or English) using Jinja2 + WeasyPrint and returns the document directly to the user in Telegram alongside a brief textual summary.

---

## 2. Technical Architecture & Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Runtime** | Python 3.11+ | Core language environment |
| **Bot Framework** | `aiogram` (v3.x) | Async Telegram bot handling, routing, and album middlewares |
| **Vision / Structured OCR** | Google Generative AI SDK (`google-genai`) or OpenAI SDK | Multimodal extraction with strict Pydantic Structured Outputs |
| **Validation & Business Logic** | `pydantic` (v2.x) | Schema validation, typing, normalization, and aggregation |
| **PDF Rendering Engine** | `WeasyPrint` + `Jinja2` | Headless HTML/CSS-to-PDF compiler (LTR, French typography) |
| **Fonts & Styling** | Inter / Roboto / DejaVu Sans | Clean, crisp, cross-platform typography for tabular financial data |
| **Configuration** | `pydantic-settings` / `python-dotenv` | Type-safe environment variable management |

---

## 3. Detailed Component Specifications

### A. Telegram Ingestion & Debouncing (`bot.py`)
- **Album Handling:** Telegram sends photo albums as separate concurrent messages sharing a `media_group_id`. Implement an in-memory `AlbumMiddleware` (using an `asyncio.Lock` and a 3-second debounce timer) to collect all `file_id` references before dispatching to the processing pipeline.
- **Single Photo Support:** Route single photos immediately without debounce delays.
- **Real-Time User Feedback:** Send and edit a status message through each stage:
  - `📥 Receiving images... (X files)`
  - `🔍 Extracting handwritten data with Vision AI...`
  - `📊 Consolidating matching tyre sizes & calculating totals...`
  - `📄 Compiling consolidated PDF invoice...`

### B. Vision AI Extraction Engine (`extractor.py`)
- **Model Configuration:** Use `gemini-1.5-flash` (or `gpt-4o-mini`) with `response_mime_type="application/json"`.
- **System Prompt Rules for Vision Model:**
  - Extract line items from handwritten tyre invoice slips (often mixing French/English terms and short codes).
  - Common Tyre Dimensions: `175/70 R13`, `185/65 R15`, `205/55 R16`, `215/65 R16C`, `315/80 R22.5`.
  - Common Brand / Pattern Codes: `(Boto)`, `(P)`, `(L)`, `(ST)`, `(DL)`, `(HW)`, `(LF)`, `(BT)`, `(TR)`, etc.
  - Table Columns: Quantity (`Qté / العدد`), Description (`Désignation / نوع البضاعة`), Unit Price (`Prix / الثمن`).
  - **Ground Truth Rule:** Extract `quantity` and `unit_price` faithfully. Subtotals and totals must be recalculated in code, not relied upon from handwritten math.

- **Pydantic Schemas:**
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class RawInvoiceItem(BaseModel):
    raw_description: str = Field(description="Tyre size and brand/code, e.g., '175/70 R13 (Boto)' or '205 R14C (L)'")
    quantity: int = Field(description="Number of tyres", ge=1)
    unit_price: float = Field(description="Unit price per tyre in MAD (DH)", ge=0.0)

class SingleInvoiceExtraction(BaseModel):
    invoice_number: Optional[str] = Field(default=None, description="Invoice reference number if visible")
    client_name: Optional[str] = Field(default=None, description="Client or merchant name if visible")
    items: List[RawInvoiceItem] = Field(default_factory=list)


C. Data Normalization & Consolidation Engine (consolidator.py)String Normalization:Standardize spacing, slashes, and uppercase letters.Clean up regex variations: convert 175 70 13 boto or 175-70-R13 (boto) $\rightarrow$ 175/70 R13 (BOTO).Aggregation Algorithm:Group items using the composite key: (normalized_description.upper(), unit_price).Calculate consolidated line items and summary metrics:$$\text{Consolidated Quantity} = \sum \text{quantity}$$$$\text{Line Subtotal} = \text{Consolidated Quantity} \times \text{unit\_price}$$$$\text{Total Tyres} = \sum \text{Consolidated Quantity}$$$$\text{Grand Total (MAD / DH)} = \sum \text{Line Subtotal}$$Consolidated Schema:Pythonclass ConsolidatedItem(BaseModel):
    index: int
    description: str
    quantity: int
    unit_price: float
    subtotal: float

class ConsolidatedInvoice(BaseModel):
    invoice_ref: str
    client_name: str
    date_str: str
    items: List[ConsolidatedItem]
    total_quantity: int
    distinct_items_count: int
    grand_total: float
    source_invoices_count: int

    D. French / English PDF Invoice Generation (pdf_generator.py)Template Engine: Jinja2 rendering templates/invoice_template.html.CSS / Styling Requirements:Page standard: @page { size: A4 portrait; margin: 12mm 15mm; }Direction: Standard LTR (dir="ltr").Modern, minimalist corporate invoice design (Slate / Navy Blue accents).Invoice Layout Structure:Header: Company title ("FACTURE RÉCAPITULATIVE" / "SUMMARY INVOICE"), Reference ID (#REC-YYYY-MM-XXXX), Date, and Client Name.Table Structure:#Désignation / Dimension (Item Description)Quantité (Qty)Prix Unitaire (Unit Price)Total (Montant HT/TTC)Summary & Totals Card:Total Pneus (Total Tyre Count): X piècesVariétés d'articles (Distinct Models): Y articlesMONTANT TOTAL GLOBAL (Grand Total): XX,XXX.00 DH4. Project Structure & File Layouttyre_invoice_bot/
├── bot.py                  # aiogram 3.x bot setup, album debouncer, file downloaders
├── config.py               # pydantic-settings config (BOT_TOKEN, GEMINI_API_KEY)
├── extractor.py            # Vision LLM structured client
├── consolidator.py         # Regex normalization, dictionary aggregation, totals
├── pdf_generator.py        # Jinja2 template loader and WeasyPrint PDF compiler
├── templates/
│   └── invoice_template.html # Clean French/English HTML+CSS invoice template
├── requirements.txt        # Pinned Python packages
├── .env.example            # Environment variables template
├── Dockerfile              # Container definition with Pango/Cairo system packages
└── README.md               # Quickstart guide
5. System Dependencies & Dockerfile RequirementsEnsure the setup installs the required OS libraries for WeasyPrint:DockerfileFROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "bot.py"]
6. Implementation InstructionsProvide fully working, modular Python code with proper type annotations and docstrings.Implement error handling for invalid image formats, API rate limits, and zero-item edge cases.Ensure all file operations and network requests are asynchronous (aiofiles, aiohttp, aiogram).