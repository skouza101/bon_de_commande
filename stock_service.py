"""Stock service for synchronizing and serving tire inventory from pneustock.tech."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("pneustock_service")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "pneustock_stock.json"
BACKUP_CACHE = BASE_DIR / "extracted_pneustock_data" / "stock_items.json"

PNEUSTOCK_EMAIL = os.getenv("PNEUSTOCK_EMAIL", "oraiche-pneus@gmail.com")
PNEUSTOCK_PASSWORD = os.getenv("PNEUSTOCK_PASSWORD", "AleatoireTire2027")
PNEUSTOCK_BASE_URL = os.getenv("PNEUSTOCK_BASE_URL", "https://pneustock.tech")


def fetch_and_cache_stock() -> List[Dict[str, Any]]:
    """Log in to pneustock.tech, fetch /warehouses/tires, flatten, and cache locally."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": PNEUSTOCK_BASE_URL,
        "Referer": f"{PNEUSTOCK_BASE_URL}/stock"
    })

    login_res = session.post(f"{PNEUSTOCK_BASE_URL}/api/auth/login", json={
        "userName": PNEUSTOCK_EMAIL,
        "password": PNEUSTOCK_PASSWORD
    }, timeout=15)

    if login_res.status_code != 200:
        raise RuntimeError(f"Failed to authenticate with pneustock.tech: HTTP {login_res.status_code}")

    jwt = login_res.json().get("jwt")
    if not jwt:
        raise RuntimeError("No JWT token returned from pneustock.tech authentication")

    session.headers.update({"Authorization": f"Bearer {jwt}"})

    wh_res = session.get(f"{PNEUSTOCK_BASE_URL}/warehouses/tires", timeout=20)
    if wh_res.status_code != 200:
        raise RuntimeError(f"Failed to fetch warehouses tires: HTTP {wh_res.status_code}")

    warehouses = wh_res.json()
    flattened_stock: List[Dict[str, Any]] = []

    for wh in warehouses:
        wh_id = wh.get("id", "")
        wh_name = wh.get("warehouseName", "")
        wh_capacity = wh.get("capacity", 0)

        tires = wh.get("tiresInStock", [])
        for t in tires:
            qty = t.get("stock", 0)
            price = t.get("price", 0.0)
            row = {
                "warehouse_name": wh_name,
                "warehouse_id": wh_id,
                "warehouse_capacity": wh_capacity,
                "reference": t.get("tireReference", "") or "",
                "brand": t.get("brandName", "") or "",
                "model": t.get("model") or "",
                "manufacture_country": t.get("manufactureCountry", "") or "",
                "manufacture_year": t.get("manufactureYear", "") or "",
                "unit_price_mad": float(price),
                "stock_quantity": int(qty),
                "tire_id": t.get("tireId", ""),
                "warehouse_tire_id": t.get("warehouseTireId", "")
            }
            flattened_stock.append(row)

    # Save to cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(flattened_stock, f, ensure_ascii=False, indent=2)

    logger.info(f"Successfully cached {len(flattened_stock)} tire stock items to {CACHE_FILE}")
    return flattened_stock


def get_cached_stock() -> List[Dict[str, Any]]:
    """Retrieve stock items from local cache file. If not found, try backup cache or fetch."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read cache file {CACHE_FILE}: {e}")

    if BACKUP_CACHE.exists():
        try:
            with open(BACKUP_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Copy to CACHE_FILE
                with open(CACHE_FILE, "w", encoding="utf-8") as out_f:
                    json.dump(data, out_f, ensure_ascii=False, indent=2)
                return data
        except Exception as e:
            logger.warning(f"Failed to read backup cache {BACKUP_CACHE}: {e}")

    # If neither exists, attempt live fetch
    try:
        return fetch_and_cache_stock()
    except Exception as e:
        logger.error(f"Failed to fetch stock from pneustock.tech: {e}")
        return []
