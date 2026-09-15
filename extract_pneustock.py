import requests
import json
import csv
import os
from datetime import datetime

EMAIL = "oraiche-pneus@gmail.com"
PASSWORD = "AleatoireTire2027"
BASE_URL = "https://pneustock.tech"

OUTPUT_DIR = os.path.join(os.getcwd(), "extracted_pneustock_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/stock"
})

print("1. Authenticating with pneustock.tech...")
login_res = session.post(f"{BASE_URL}/api/auth/login", json={
    "userName": EMAIL,
    "password": PASSWORD
})

if login_res.status_code != 200:
    print(f"Error logging in: HTTP {login_res.status_code} - {login_res.text}")
    exit(1)

jwt = login_res.json().get("jwt")
session.headers.update({"Authorization": f"Bearer {jwt}"})
print("Login successful! JWT acquired.")

# --- 1. Extract Warehouses Tires (Stock view) ---
print("\n2. Fetching stock per warehouse (/warehouses/tires)...")
wh_res = session.get(f"{BASE_URL}/warehouses/tires")
warehouses = wh_res.json()

flattened_stock = []
total_units = 0

for wh in warehouses:
    wh_id = wh.get("id", "")
    wh_name = wh.get("warehouseName", "")
    wh_capacity = wh.get("capacity", "")
    
    tires = wh.get("tiresInStock", [])
    for t in tires:
        qty = t.get("stock", 0)
        price = t.get("price", 0.0)
        row = {
            "warehouse_name": wh_name,
            "warehouse_id": wh_id,
            "warehouse_capacity": wh_capacity,
            "reference": t.get("tireReference", ""),
            "brand": t.get("brandName", ""),
            "model": t.get("model") or "",
            "manufacture_country": t.get("manufactureCountry", ""),
            "manufacture_year": t.get("manufactureYear", ""),
            "unit_price_mad": price,
            "stock_quantity": qty,
            "total_value_mad": round(qty * price, 2),
            "tire_id": t.get("tireId", ""),
            "warehouse_tire_id": t.get("warehouseTireId", "")
        }
        total_units += qty
        flattened_stock.append(row)

print(f"-> Total stock rows across warehouses: {len(flattened_stock)}")
print(f"-> Total physical tyre units in stock: {total_units}")

# Save CSV
stock_csv_path = os.path.join(OUTPUT_DIR, "stock_items.csv")
if flattened_stock:
    keys = list(flattened_stock[0].keys())
    with open(stock_csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flattened_stock)
    print(f"-> Saved CSV: {stock_csv_path}")

with open(os.path.join(OUTPUT_DIR, "stock_warehouses_raw.json"), "w", encoding="utf-8") as f:
    json.dump(warehouses, f, ensure_ascii=False, indent=2)

with open(os.path.join(OUTPUT_DIR, "stock_items.json"), "w", encoding="utf-8") as f:
    json.dump(flattened_stock, f, ensure_ascii=False, indent=2)

# --- 2. Extract Stock Stats Summary ---
print("\n3. Fetching aggregated stock stats (/api/tires/stock-stats)...")
stats_res = session.get(f"{BASE_URL}/api/tires/stock-stats")
stats = stats_res.json()
stats_csv_path = os.path.join(OUTPUT_DIR, "stock_stats_aggregated.csv")
if stats:
    with open(stats_csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats[0].keys()))
        writer.writeheader()
        writer.writerows(stats)
    with open(os.path.join(OUTPUT_DIR, "stock_stats_aggregated.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"-> Saved aggregated stats: {len(stats)} models")

# --- 3. Extract Warehouses Info ---
print("\n4. Fetching warehouse descriptions (/warehouses)...")
wh_desc = session.get(f"{BASE_URL}/warehouses").json()
wh_flat = []
for w in wh_desc:
    addr = w.get("address") or {}
    wh_flat.append({
        "id": w.get("id"),
        "name": w.get("name"),
        "street": addr.get("street", ""),
        "city": addr.get("city", ""),
        "current_stock": w.get("currentStock", 0),
        "total_capacity": w.get("totalCapacity", 0),
        "current_capital_mad": w.get("currentCapital", 0.0)
    })
wh_csv_path = os.path.join(OUTPUT_DIR, "warehouses.csv")
if wh_flat:
    with open(wh_csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(wh_flat[0].keys()))
        writer.writeheader()
        writer.writerows(wh_flat)
    with open(os.path.join(OUTPUT_DIR, "warehouses.json"), "w", encoding="utf-8") as f:
        json.dump(wh_desc, f, ensure_ascii=False, indent=2)
    print(f"-> Saved warehouses: {len(wh_flat)} depots")

# --- 4. Extract Brands ---
print("\n5. Fetching distinct brands (/brands/distinct)...")
brands = session.get(f"{BASE_URL}/brands/distinct").json()
if brands:
    with open(os.path.join(OUTPUT_DIR, "brands.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(brands[0].keys()))
        writer.writeheader()
        writer.writerows(brands)
    with open(os.path.join(OUTPUT_DIR, "brands.json"), "w", encoding="utf-8") as f:
        json.dump(brands, f, ensure_ascii=False, indent=2)
    print(f"-> Saved brands: {len(brands)} brands")

# --- 5. Extract Tire References ---
print("\n6. Fetching tire references (/tire-references)...")
refs = session.get(f"{BASE_URL}/tire-references").json()
if refs:
    with open(os.path.join(OUTPUT_DIR, "tire_references.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(refs[0].keys()))
        writer.writeheader()
        writer.writerows(refs)
    with open(os.path.join(OUTPUT_DIR, "tire_references.json"), "w", encoding="utf-8") as f:
        json.dump(refs, f, ensure_ascii=False, indent=2)
    print(f"-> Saved references: {len(refs)} references")

# --- 6. Extract Partners ---
print("\n7. Fetching partners (/api/partners)...")
partners = session.get(f"{BASE_URL}/api/partners").json()
partners_flat = []
for p in partners:
    addr = p.get("address") or {}
    partners_flat.append({
        "id": p.get("id"),
        "name": p.get("name"),
        "role": p.get("role"),
        "type": p.get("type"),
        "phone": p.get("phoneNumber"),
        "email": p.get("email"),
        "street": addr.get("street", ""),
        "city": addr.get("city", ""),
        "country": addr.get("countryIso3", "")
    })
if partners_flat:
    with open(os.path.join(OUTPUT_DIR, "partners.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(partners_flat[0].keys()))
        writer.writeheader()
        writer.writerows(partners_flat)
    with open(os.path.join(OUTPUT_DIR, "partners.json"), "w", encoding="utf-8") as f:
        json.dump(partners, f, ensure_ascii=False, indent=2)
    print(f"-> Saved partners: {len(partners)} partners")

# --- 7. Generate Multi-Sheet Excel Workbook (.xlsx) ---
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    print("\n8. Building styled multi-sheet Excel file (pneustock_data.xlsx)...")
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=10)
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    def add_sheet(title, data, columns_map):
        ws = wb.create_sheet(title=title)
        ws.views.sheetView[0].showGridLines = True
        
        # Write headers
        for col_idx, (col_key, col_label) in enumerate(columns_map, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Write data rows
        for row_idx, item in enumerate(data, start=2):
            for col_idx, (col_key, _) in enumerate(columns_map, start=1):
                val = item.get(col_key, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = regular_font
                cell.border = thin_border
                if isinstance(val, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left")

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
        ws.row_dimensions[1].height = 28

    # Sheet 1: Stock Items (Detail per warehouse)
    add_sheet(
        "Stock Détaillé",
        flattened_stock,
        [
            ("warehouse_name", "Dépôt (Magasin)"),
            ("reference", "Référence / Dimension"),
            ("brand", "Marque"),
            ("model", "Modèle"),
            ("manufacture_country", "Pays"),
            ("manufacture_year", "Année"),
            ("unit_price_mad", "Prix Unitaire (MAD)"),
            ("stock_quantity", "Quantité Stock"),
            ("total_value_mad", "Valeur Totale (MAD)"),
            ("warehouse_id", "ID Dépôt"),
            ("tire_id", "ID Pneu"),
        ]
    )

    # Sheet 2: Stock Stats (Aggregated)
    add_sheet(
        "Stock Agrégé (Stats)",
        stats,
        [
            ("brand", "Marque"),
            ("size", "Dimension"),
            ("model", "Modèle"),
            ("quantity", "Quantité Totale"),
            ("price", "Prix Indicatif"),
        ]
    )

    # Sheet 3: Warehouses
    add_sheet(
        "Dépôts",
        wh_flat,
        [
            ("name", "Nom Dépôt"),
            ("city", "Ville"),
            ("street", "Rue / Adresse"),
            ("current_stock", "Stock Actuel"),
            ("total_capacity", "Capacité Totale"),
            ("current_capital_mad", "Capital Actuel (MAD)"),
            ("id", "Identifiant Dépôt"),
        ]
    )

    # Sheet 4: Brands
    add_sheet(
        "Marques",
        brands,
        [
            ("name", "Nom Marque"),
            ("country", "Pays d'Origine"),
            ("manufacturerYear", "Année"),
            ("id", "ID"),
        ]
    )

    # Sheet 5: Partners
    add_sheet(
        "Partenaires",
        partners_flat,
        [
            ("name", "Nom"),
            ("role", "Rôle"),
            ("type", "Type"),
            ("phone", "Téléphone"),
            ("city", "Ville"),
            ("street", "Adresse"),
            ("email", "Email"),
        ]
    )

    excel_path = os.path.join(OUTPUT_DIR, "pneustock_complet.xlsx")
    wb.save(excel_path)
    print(f"-> Saved styled Excel workbook: {excel_path}")

except Exception as e:
    print(f"Warning: Could not build Excel: {e}")

print("\n==========================================")
print(f"Extraction finished! All files located in:\n{OUTPUT_DIR}")
print("==========================================")
