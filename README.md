# 🛞 Automated Handwritten Tyre Invoice Consolidator & Web Dashboard

> Production-ready, asynchronous Python system combining a **Telegram Bot** and a **Modern Web Dashboard** to automate the intake, handwritten OCR extraction via **Google Gemini Vision AI**, line-item consolidation, and PDF generation of tyre wholesale invoices (*Bons de Commande / Bons de Livraison*).

---

## 🌟 Key Features

1. **Google Gemini Multimodal Vision AI:**
   - Powered exclusively by **Google Gemini** (`gemini-1.5-flash`, `gemini-2.0-flash`, `gemini-2.5-flash`) via `google-genai` with strict Pydantic Structured Outputs.
   - Tailored system prompt recognizing North African / Moroccan tyre receipts (Arabic/French table headers, tyre dimensions, and brand abbreviation codes).
   - **Ground-Truth Extraction**: Faithfully extracts quantities and unit prices while math and aggregations are recalculated in code.

2. **Data Normalization & Multi-Receipt Aggregation:**
   - Robust regex normalizer standardizing tyre sizes and patterns:
     - `175 70 13 boto` or `175-70-R13 (boto)` $\rightarrow$ `175/70 R13 (BOTO)`
     - `205 14C (L)` or `205R14C` $\rightarrow$ `205 R14C (L)`
     - `315 80 22.5 (HW)` $\rightarrow$ `315/80 R22.5 (HW)`
   - Aggregates matching tyres across multiple receipts using composite key `(normalized_description, unit_price)`.
   - Computes aggregated quantities, line subtotals, grand totals, and distinct tyre model counts.

3. **Modern Web Dashboard (FastAPI SPA):**
   - 📊 **Tableau de Bord (Analytics)**: Real-time KPI cards (Total Chiffre d'Affaires, Volume total pneus, Factures récapitulatives), Top 5 Dimensions charts, and Brand distribution.
   - ⚡ **Numérisation Directe (Live Scanner)**: Drag-and-drop receipt image upload, multi-file previews, animated progress stepper.
   - ✏️ **Édition Interactive en Direct**: Review and edit extracted items (modify dimensions, adjust quantities and unit prices, add/remove rows) with live total recalculations.
   - 👁️ **Aperçu PDF & Téléchargement**: In-browser PDF preview modal and one-click download.
   - 📑 **Historique & Archivage**: Searchable and filterable table of all consolidated invoices.
   - ⚙️ **Paramètres**: Customization of company name, currency (DH / MAD), and Gemini model.

4. **Telegram Bot (aiogram 3.x):**
   - In-memory `AlbumMiddleware` with a **3.5s sliding window debounce** to collect all photos in an album before processing.
   - Real-time dynamic status message editing.
   - Delivers printable A4 PDF documents directly in chat with an HTML summary caption.
   - Automatically synchronizes processed invoices into the SQLite database.

5. **Professional A4 PDF Invoices:**
   - Headless HTML/CSS-to-PDF compiler using Jinja2 + WeasyPrint (with automatic pure-Python fallback for cross-platform development).
   - Clean corporate styling with Slate/Navy accents, metadata cards, itemized tables, and signature boxes.

---

## 📁 Project Structure

```
bon_de_commande/
├── app.py                  # FastAPI web dashboard server & REST API
├── bot.py                  # aiogram 3.x Telegram bot with AlbumMiddleware
├── config.py               # pydantic-settings configuration & environment variables
├── extractor.py            # Google Gemini Vision LLM structured client
├── consolidator.py         # Regex tyre normalizer, aggregation logic & Pydantic models
├── database.py             # SQLite persistence layer & analytics aggregations
├── pdf_generator.py        # Jinja2 template loader & PDF compiler (WeasyPrint / fallback)
├── templates/
│   ├── dashboard.html      # Modern SPA Web Dashboard interface
│   └── invoice_template.html # Clean French A4 HTML/CSS invoice template
├── static/
│   ├── css/
│   │   └── dashboard.css   # Dark/Light theme design system & styles
│   └── js/
│       └── dashboard.js    # SPA frontend state & API controller
├── tests/
│   └── test_pipeline.py    # Automated test suite (20 unit & integration tests)
├── requirements.txt        # Pinned Python package dependencies
├── .env.example            # Environment variables template
├── Dockerfile              # Production container with Pango/Cairo system packages
└── pytest.ini              # Pytest configuration
```

---

## 🚀 Quickstart Guide

### 1. Installation

```bash
git clone <repo-url>
cd bon_de_commande
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
ALBUM_DEBOUNCE_SECONDS=3.5
WEB_HOST=0.0.0.0
WEB_PORT=8000
COMPANY_NAME=DISTRIBUTION PNEUMATIQUE SARL
CURRENCY=DH
```

### 3. Launching the Applications

#### Launch the Web Dashboard:
```bash
python app.py
```
Open your browser at **`http://localhost:8000`** to access the dashboard.

#### Launch the Telegram Bot:
```bash
python bot.py
```

### 4. Running Automated Tests

Run the complete test suite:

```bash
pytest -v
```

---

## 🐳 Docker Deployment

Build and run the production container:

```bash
# Build the Docker image
docker build -t tyre-invoice-system .

# Run the container
docker run -d --name tyre-system -p 8000:8000 --env-file .env tyre-invoice-system
```
