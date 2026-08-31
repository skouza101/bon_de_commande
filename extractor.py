"""Extraction Engine for Handwritten Tyre Invoices (Google Gemini & DeepSeek).

Supports both Google Gemini Multimodal Vision API (google-genai SDK) and
DeepSeek API (OpenAI-compatible endpoints) with strict Pydantic Structured
Outputs to extract line items, quantities, and unit prices.
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class VisionExtractionError(Exception):
    """Raised when extraction fails due to API key or service error."""
    pass


# ---------------------------------------------------------------------------
# Pydantic Schemas for Raw Extractions
# ---------------------------------------------------------------------------

class RawInvoiceItem(BaseModel):
    """Raw line item extracted directly from a handwritten paper invoice."""
    raw_description: str = Field(
        description="Tyre size, dimension, and brand/code, e.g., '175/70 R13 (L)' or '205 R14C (LASSA)' or '315/80 R22.5'"
    )
    quantity: int = Field(
        description="Number of tyres/pieces (must be integer >= 1)",
        ge=1,
    )
    unit_price: float = Field(
        description="Unit price per tyre in Moroccan Dirhams (MAD / DH)",
        ge=0.0,
    )


class SingleInvoiceExtraction(BaseModel):
    """Structured extraction result for a single receipt image."""
    invoice_number: Optional[str] = Field(
        default=None,
        description="Invoice or receipt reference number if handwritten or printed on the slip"
    )
    client_name: Optional[str] = Field(
        default=None,
        description="Client or merchant name if visible on the slip"
    )
    items: List[RawInvoiceItem] = Field(
        default_factory=list,
        description="List of extracted tyre line items"
    )


# ---------------------------------------------------------------------------
# Extraction Prompt
# ---------------------------------------------------------------------------

VISION_SYSTEM_PROMPT = """You are an expert specialist in reading handwritten wholesale tyre delivery slips (bons de livraison / bons de commande / factures) in Morocco and North Africa.

Your task is to transcribe all handwritten tyre line items accurately from this receipt image into strict JSON format.

Domain Rules & Recognition Guidelines:
1. Tyre Dimensions:
   - Typical passenger sizes: 175/70 R13, 185/65 R15, 205/55 R16, 195/65 R15, 225/45 R17, etc.
   - Commercial van sizes: 205 R14C, 195 R15C, 215/65 R16C, 225/70 R15C, etc.
   - Heavy truck / Bus sizes: 315/80 R22.5, 295/80 R22.5, 385/65 R22.5, 12.00 R20, etc.
   - Notation variations: Handwriters may omit slashes or "R" (e.g., "175 70 13", "175/70/13", "175-70-13", "205 14C", "205R14C").
2. MANDATORY Brand Recognition Dictionary (ONLY CHOOSE FROM THIS EXACT LIST):
   Handwriters write short initials/abbreviations for tyre brands. You MUST map to one of these EXACT registered brand names:
   - L / Ls / Lass -> LASSA
   - P / Pet / Petl -> PETLAS
   - G / GY / Good -> GOODYEAR
   - St / Star -> STARMAXX
   - Lf / Lauf -> LAUFENN
   - Hn / Hk / Hank -> HANKOOK
   - M / Mi / Mich -> MICHELIN
   - Le / Leao -> LEAO
   - Mt / Mont -> MONTREAL
   - Ls / Land -> LANDSPIDER
   - Dl / Del / Dln -> DELINTE
   - Tr / Trian -> TRIANGLE
   - R / Rot / Rotl -> ROTALLA
   - A / Amin -> AMINE
   - N / Nx / Nex -> NEXEN
   - Bt / Boto -> BOTO
   - Au / Aust -> AUSTONE
   - Sp / Semp -> SEMPERIT
   - Mm / Momo -> MOMO
   - Un / Uni / Unir -> UNIROYAL
   - Sh / Seha -> SEHA
   - D / Dunl -> DUNLOP
   - Ml / Mile -> MILESTONE
   - Cs / City -> CITY STAR
   - Tf / Tian -> TIANFU
   - F / Fr / Fire -> FIRESTONE
   - K / Kl / Kleb -> KLEBER
   - Dc / Double -> DOUBLE COIN
   - Dvr -> DVR
   - Tm / Trac -> TRACMAX
   - Aplus -> APLUS
   - Doublestar -> DOUBLESTAR
   - Ovation -> OVATION
   - Pirelli -> PIRELLI
   - Bridgestone -> BRIDGESTONE
   - Continental -> CONTINENTAL
   - Kumho -> KUMHO
   - Yokohama -> YOKOHAMA
   - Toyo -> TOYO

   CRITICAL BRAND RULE:
   - Do NOT invent abbreviations like 'PL' or non-existent brand names. If you see 'P', it is PETLAS. If you see 'L', it is LASSA. If you see 'Bt', it is BOTO.
   - If a brand cannot be identified with certainty from this list, leave the brand code blank or use only a recognized brand above.
   - Keep the dimension and brand together in `raw_description`, formatted as: "DIMENSION (BRAND)", e.g. "175/70 R13 (LASSA)" or "185/65 R15 (PETLAS)".
3. Table Columns (in French or Arabic):
   - Quantity (Qté / Quantité / العدد): positive integer.
   - Description (Désignation / نوع البضاعة / Article): dimension + brand.
   - Unit Price (Prix / P.U / P.V / الثمن): unit price in MAD/DH as float.
4. Ground Truth Extraction Rule:
   - Faithfully extract only individual line items (raw_description, quantity, unit_price).
   - Do NOT calculate line totals or grand totals—arithmetic is handled in application code.
   - Extract all readable, valid line items.
   - If no valid tyre line items are present, return an empty items list.
"""


def _clean_json_markdown(text: str) -> str:
    """Extract clean JSON substring from potential Markdown code fences."""
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    return cleaned


def _prepare_image_bytes(path: Path, max_dimension: int = 2048) -> tuple[bytes, str]:
    """Read image bytes and optimize resolution if oversized for fast multimodal upload."""
    suffix = path.suffix.lower()
    mime_type = "image/jpeg"
    if suffix == ".png":
        mime_type = "image/png"
    elif suffix == ".webp":
        mime_type = "image/webp"

    try:
        from PIL import Image, ImageOps
        import io
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            if max(w, h) > max_dimension or path.stat().st_size > 1.5 * 1024 * 1024:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                if img.mode in ("RGBA", "P") and mime_type == "image/jpeg":
                    img = img.convert("RGB")
                img.save(buf, format="JPEG" if mime_type == "image/jpeg" else "PNG", quality=90, optimize=True)
                return buf.getvalue(), mime_type
    except Exception as e:
        logger.debug(f"Image preprocessing fallback: {e}")

    with open(path, "rb") as f:
        return f.read(), mime_type


# ---------------------------------------------------------------------------
# Gemini Multimodal Vision Extractor
# ---------------------------------------------------------------------------

class GeminiVisionExtractor:
    """Async extractor handling multimodal image requests via Google Gemini."""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(5)

    def _clean_model_name(self, model: str) -> str:
        """Strip 'models/' prefix and whitespace."""
        clean = (model or "gemini-2.5-flash").strip()
        if clean.startswith("models/"):
            clean = clean[7:]
        return clean

    def _get_client(self):
        """Get or initialize client using current settings."""
        if not settings.gemini_api_key or not settings.gemini_api_key.strip():
            raise VisionExtractionError(
                "La clé Google Gemini n'est pas configurée. "
                "Veuillez saisir votre clé d'accès dans l'onglet 'Paramètres'."
            )
        try:
            from google import genai
            return genai.Client(api_key=settings.gemini_api_key.strip())
        except Exception as e:
            try:
                import google.generativeai as gai
                gai.configure(api_key=settings.gemini_api_key.strip())
                return gai
            except Exception:
                raise VisionExtractionError(f"Impossible d'initialiser le client Google Gemini: {e}")

    async def extract_from_image(
        self, image_path: Union[str, Path]
    ) -> SingleInvoiceExtraction:
        """Extract structured tyre invoice items using Google Gemini."""
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image file not found: {path}")
            return SingleInvoiceExtraction(items=[])

        client = self._get_client()
        model_name = self._clean_model_name(settings.gemini_model or "gemini-2.5-flash")
        image_bytes, mime_type = _prepare_image_bytes(path)

        prompt = (
            f"{VISION_SYSTEM_PROMPT}\n\n"
            "Transcribe and extract all tyre line items from this receipt into the structured JSON schema."
        )

        loop = asyncio.get_running_loop()
        last_error = None

        if hasattr(client, "models"):
            from google.genai import types

            for attempt in range(3):
                try:
                    logger.info(f"Extracting receipt with Gemini model: {model_name} (attempt {attempt+1})")

                    config_args = {
                        "response_mime_type": "application/json",
                        "response_schema": SingleInvoiceExtraction,
                        "temperature": 0.1,
                    }
                    # Disable reasoning overhead on Gemini 3.7+ flash models for rapid OCR response
                    if "3.7" in model_name or "reasoning" in model_name:
                        try:
                            config_args["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
                        except Exception:
                            pass

                    def _call_model(m=model_name):
                        return client.models.generate_content(
                            model=m,
                            contents=[
                                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                                prompt,
                            ],
                            config=types.GenerateContentConfig(**config_args),
                        )

                    response = await loop.run_in_executor(None, _call_model)
                    if response and response.text:
                        data = json.loads(response.text)
                        return SingleInvoiceExtraction.model_validate(data)
                    return SingleInvoiceExtraction(items=[])

                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    logger.warning(f"Gemini {model_name} attempt {attempt+1} failed: {err_str}")

                    if "API_KEY" in err_str.upper() or "PERMISSION_DENIED" in err_str.upper() or "UNAUTHENTICATED" in err_str.upper():
                        raise VisionExtractionError(f"Clé Google Gemini invalide ou non autorisée : {err_str}")

                    if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        wait_sec = 2 * (attempt + 1)
                        logger.info(f"Gemini transient error, waiting {wait_sec}s...")
                        await asyncio.sleep(wait_sec)
                        continue
                    else:
                        break

        err_msg = str(last_error)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            raise VisionExtractionError(
                "Le quota de requêtes de votre clé Gemini est temporairement atteint. "
                "Veuillez patienter quelques secondes et relancer."
            )
        if "503" in err_msg or "UNAVAILABLE" in err_msg:
            raise VisionExtractionError(
                f"Le modèle {model_name} est temporairement indisponible (503). "
                "Veuillez réessayer dans quelques instants."
            )
        raise VisionExtractionError(f"Échec Gemini: {err_msg}")


# ---------------------------------------------------------------------------
# DeepSeek AI Extractor (OpenAI-compatible)
# ---------------------------------------------------------------------------

class DeepSeekExtractor:
    """Async extractor handling requests via DeepSeek API (OpenAI compatible)."""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(1)

    def _get_api_key(self) -> str:
        """Retrieve and validate configured DeepSeek API key."""
        if not settings.deepseek_api_key or not settings.deepseek_api_key.strip():
            raise VisionExtractionError(
                "La clé d'accès DeepSeek n'est pas configurée. "
                "Veuillez saisir votre clé DeepSeek dans l'onglet 'Paramètres'."
            )
        return settings.deepseek_api_key.strip()

    async def extract_from_image(
        self, image_path: Union[str, Path]
    ) -> SingleInvoiceExtraction:
        """Extract structured tyre invoice items using DeepSeek API."""
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image file not found: {path}")
            return SingleInvoiceExtraction(items=[])

        api_key = self._get_api_key()
        base_url = (settings.deepseek_base_url or "https://openrouter.ai/api/v1").rstrip("/")
        if api_key.startswith("sk-or-v1") and "openrouter" not in base_url:
            base_url = "https://openrouter.ai/api/v1"
        elif not base_url.endswith("/v1") and "deepseek.com" in base_url:
            base_url = f"{base_url}/v1"

        image_bytes, mime_type = _prepare_image_bytes(path)
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64_img}"

        json_instruction = (
            f"{VISION_SYSTEM_PROMPT}\n\n"
            "CRITICAL: You MUST respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "invoice_number": null,\n'
            '  "client_name": null,\n'
            '  "items": [\n'
            '    {\n'
            '      "raw_description": "dimension + brand (e.g. 175/70 R13 (LASSA))",\n'
            '      "quantity": 2,\n'
            '      "unit_price": 450.0\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        messages = [
            {"role": "system", "content": json_instruction},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe and extract all tyre line items from this delivery slip into valid JSON.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                ],
            },
        ]

        model = settings.deepseek_model or "deepseek-chat"

        try:
            import openai
            headers = {
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Tyre Consolidator",
            }
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)

            # Some models on OpenRouter or proxies reject response_format parameter; fallback safely if rejected
            use_json_object = ("reasoner" not in model.lower()) and ("deepseek" in base_url or "openai" in base_url)
            response_format = {"type": "json_object"} if use_json_object else None

            logger.info(f"Extracting receipt with OpenAI/OpenRouter model: {model} at {base_url}")
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                    temperature=0.1,
                )
            except Exception as first_attempt_err:
                if response_format is not None and ("response_format" in str(first_attempt_err) or "json" in str(first_attempt_err).lower()):
                    logger.info("Retrying completion without response_format constraint...")
                    completion = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.1,
                    )
                else:
                    raise first_attempt_err

            raw_text = completion.choices[0].message.content or "{}"
            cleaned_json = _clean_json_markdown(raw_text)
            data = json.loads(cleaned_json)
            return SingleInvoiceExtraction.model_validate(data)

        except Exception as e:
            err_str = str(e)
            logger.warning(f"Vision extraction failed via {base_url} ({model}): {err_str}")

            if "API_KEY" in err_str.upper() or "AUTHENTICATION" in err_str.upper() or "401" in err_str:
                raise VisionExtractionError(f"Clé API invalide ou refusée (401) : {err_str}")
            if "INSUFFICIENT_BALANCE" in err_str.upper() or "402" in err_str:
                raise VisionExtractionError(f"Solde du compte insuffisant (402).")
            if "429" in err_str or "RATE_LIMIT" in err_str.upper():
                raise VisionExtractionError(f"Limite de requêtes atteinte (429). Veuillez patienter.")

            raise VisionExtractionError(f"Échec de l'extraction: {err_str}")


# ---------------------------------------------------------------------------
# Unified Multi-Provider Extractor
# ---------------------------------------------------------------------------

class UnifiedVisionExtractor:
    """Unified extractor router supporting Google Gemini and OpenRouter with automatic failover."""

    def __init__(self):
        self.gemini = GeminiVisionExtractor()
        self.deepseek = DeepSeekExtractor()
        self._semaphore = asyncio.Semaphore(1)

    async def extract_from_image(
        self, image_path: Union[str, Path]
    ) -> SingleInvoiceExtraction:
        """Extract line items trying Google Gemini first, automatically falling back to OpenRouter if needed."""
        provider = (settings.ai_provider or "gemini").strip().lower()

        # If user explicitly configured only deepseek/openrouter and NO gemini key is available
        if provider == "deepseek" and not (settings.gemini_api_key and settings.gemini_api_key.strip()):
            return await self.deepseek.extract_from_image(image_path)

        # Primary attempt: Google Gemini
        gemini_error = None
        if settings.gemini_api_key and settings.gemini_api_key.strip():
            try:
                logger.info("Attempting primary vision extraction with Google Gemini...")
                res = await self.gemini.extract_from_image(image_path)
                if res and res.items:
                    return res
                logger.warning("Gemini returned empty items, trying OpenRouter fallback...")
            except Exception as e:
                gemini_error = e
                logger.warning(f"Gemini extraction failed ({e}), attempting automatic fallback to OpenRouter...")
        
        # Fallback attempt: OpenRouter (if key configured)
        if settings.deepseek_api_key and settings.deepseek_api_key.strip():
            try:
                logger.info("Executing failover vision extraction with OpenRouter...")
                return await self.deepseek.extract_from_image(image_path)
            except Exception as e:
                logger.error(f"OpenRouter fallback also failed: {e}")
                if gemini_error:
                    raise VisionExtractionError(f"Échec Gemini ({gemini_error}) et OpenRouter ({e})")
                raise

        # If OpenRouter is not configured and Gemini failed
        if gemini_error:
            raise gemini_error

        # If only Gemini was configured and returned empty items
        return SingleInvoiceExtraction(items=[])

    async def extract_from_images(
        self, image_paths: List[Union[str, Path]]
    ) -> List[SingleInvoiceExtraction]:
        """Extract line items from multiple images concurrently in parallel with bounded throttling."""
        if not image_paths:
            return []

        # Bound concurrent requests to avoid provider rate spikes while running in parallel
        sem = asyncio.Semaphore(5)

        async def _extract_bounded(path):
            async with sem:
                return await self.extract_from_image(path)

        tasks = [_extract_bounded(p) for p in image_paths]
        results = await asyncio.gather(*tasks)
        return list(results)


# Global unified extractor instance
extractor = UnifiedVisionExtractor()
