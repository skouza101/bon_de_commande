"""Automated Handwritten Tyre Invoice Consolidator - Telegram Bot.

Aiogram 3.x Telegram bot implementing debounced album ingestion, Gemini Vision AI
extraction, tyre size consolidation, SQLite persistence, and French A4 PDF delivery.
"""

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    FSInputFile,
    Message,
    TelegramObject,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from consolidator import consolidate_extractions, ConsolidatedInvoice
from database import db
from extractor import extractor, SingleInvoiceExtraction
from pdf_generator import pdf_generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tyre_bot")


# ---------------------------------------------------------------------------
# Telegram Album Middleware with Debouncing
# ---------------------------------------------------------------------------

class AlbumMiddleware(BaseMiddleware):
    """Debouncing middleware for Telegram media groups (multi-photo albums).

    Telegram delivers album photos as separate updates with a shared
    `media_group_id`. This middleware collects all messages in the group
    within a sliding window before dispatching the complete list of messages
    to the handler.
    """

    def __init__(self, debounce_seconds: float = 3.5):
        super().__init__()
        self.debounce_seconds = debounce_seconds
        self.albums: Dict[str, List[Message]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Any],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        media_group_id = event.media_group_id

        # If it's a single message without an album group, pass through directly
        if not media_group_id:
            data["album_messages"] = [event]
            return await handler(event, data)

        # Handle album group debouncing
        if media_group_id not in self.locks:
            self.locks[media_group_id] = asyncio.Lock()

        async with self.locks[media_group_id]:
            if media_group_id not in self.albums:
                self.albums[media_group_id] = [event]
                # First message in this album; wait for subsequent messages
                await asyncio.sleep(self.debounce_seconds)

                # Collect all grouped messages
                messages = self.albums.pop(media_group_id, [])
                self.locks.pop(media_group_id, None)

                data["album_messages"] = messages
                # Dispatch the handler with the complete album list
                return await handler(event, data)
            else:
                # Subsequent photo in the same album; append to list and skip handler
                self.albums[media_group_id].append(event)
                return


# ---------------------------------------------------------------------------
# Bot Initialization & Dispatcher
# ---------------------------------------------------------------------------

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
dp.message.middleware(AlbumMiddleware(debounce_seconds=settings.album_debounce_seconds))


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

async def download_telegram_file(bot_instance: Bot, file_id: str, destination_dir: Path) -> Path:
    """Download a file from Telegram servers into the specified directory."""
    file_info = await bot_instance.get_file(file_id)
    ext = Path(file_info.file_path or "image.jpg").suffix or ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    local_path = destination_dir / unique_filename

    await bot_instance.download_file(file_info.file_path, destination=local_path)
    return local_path


def format_telegram_summary(invoice: ConsolidatedInvoice) -> str:
    """Format a clean, readable Telegram HTML summary message."""
    lines = [
        f"✅ <b>Facture Récapitulative Consolidée</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📋 <b>Réf :</b> <code>{invoice.invoice_ref}</code>",
        f"👤 <b>Client :</b> <b>{invoice.client_name}</b>",
        f"📅 <b>Date :</b> {invoice.date_str}",
        f"📑 <b>Bons traités :</b> {invoice.source_invoices_count} reçu(s)",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Synthèse Pneumatiques :</b>",
        f"• <b>Total Pneus :</b> <code>{invoice.total_quantity} pièces</code>",
        f"• <b>Modèles distincts :</b> <code>{invoice.distinct_items_count} articles</code>",
        f"• <b>Montant Total Global :</b> <b><u>{invoice.grand_total:,.2f} {settings.currency}</u></b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📝 <b>Détail des lignes consolidées :</b>",
    ]

    # Show top items
    display_limit = 12
    for item in invoice.items[:display_limit]:
        lines.append(
            f"  ▫️ <b>{item.description}</b> : {item.quantity} pcs × {item.unit_price:,.2f} = <b>{item.subtotal:,.2f} {settings.currency}</b>"
        )

    if len(invoice.items) > display_limit:
        remaining = len(invoice.items) - display_limit
        lines.append(f"  <i>... et {remaining} autre(s) article(s) sur le PDF.</i>")

    lines.append(f"\n📄 <i>Le fichier PDF haute définition est attaché ci-dessous.</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def handle_start(message: Message):
    """Handle /start command with onboarding instructions."""
    welcome_text = (
        f"👋 <b>Bienvenue sur le Bot de Consolidation de Bons de Commande Pneus !</b>\n\n"
        f"Ce service extrait automatiquement les données de vos <b>bons manuscrits</b> "
        f"de pneumatiques et génère une <b>Facture Récapitulative PDF</b> propre et calculée.\n\n"
        f"<b>🚀 Comment l'utiliser ?</b>\n"
        f"1️⃣ Prenez en photo vos bons de livraison ou de commande manuscrits.\n"
        f"2️⃣ Envoyez une ou <b>plusieurs photos en même temps (Album)</b> ici.\n"
        f"3️⃣ Le système analyse les dimensions (ex: <i>175/70 R13 (BOTO)</i>, <i>205 R14C</i>, <i>315/80 R22.5</i>), "
        f"fusionne les quantités identiques et recalcule les montants avec exactitude.\n"
        f"4️⃣ Vous recevez immédiatement votre document PDF A4 prêt à imprimer ! 🖨️\n\n"
        f"<i>Envoyez vos photos de bons dès maintenant pour commencer ! 📸</i>"
    )
    await message.answer(welcome_text)


@dp.message(Command("help"))
async def handle_help(message: Message):
    """Handle /help command with format and usage guidance."""
    help_text = (
        f"ℹ️ <b>Aide & Guide d'utilisation :</b>\n\n"
        f"• <b>Formats acceptés :</b> Photos directes (JPG, PNG, WebP) ou Albums Telegram.\n"
        f"• <b>Dimensions prises en charge :</b> Voitures de tourisme (ex: <i>175/70 R13</i>, <i>185/65 R15</i>), "
        f"Utilitaires (ex: <i>205 R14C</i>, <i>215/65 R16C</i>), Poids lourds (ex: <i>315/80 R22.5</i>).\n"
        f"• <b>Marques reconnues :</b> Lassa, Petlas, Starmaxx, Boto, Laufenn, Hankook, Michelin, etc.\n"
        f"• <b>Multi-reçus :</b> Vous pouvez sélectionner jusqu'à 10 photos d'un coup dans votre galerie Telegram.\n\n"
        f"💡 <i>Conseil : Assurez-vous d'un bon éclairage et que les chiffres de quantités et de prix soient bien lisibles.</i>"
    )
    await message.answer(help_text)


# ---------------------------------------------------------------------------
# Photo & Document Message Handlers
# ---------------------------------------------------------------------------

@dp.message(F.photo | F.document)
async def handle_invoice_images(message: Message, album_messages: Optional[List[Message]] = None):
    """Handle single photos, albums, and image documents."""
    messages_to_process = album_messages or [message]
    count = len(messages_to_process)

    # 1. Send initial feedback status
    status_msg = await message.answer(
        f"📥 <b>Réception des photos en cours...</b> (<i>{count} fichier(s) détecté(s)</i>)"
    )

    # Create temporary working directory for this batch
    session_id = uuid.uuid4().hex[:8]
    batch_temp_dir = settings.temp_dir / f"batch_{session_id}"
    batch_temp_dir.mkdir(parents=True, exist_ok=True)

    downloaded_paths: List[Path] = []

    try:
        # 2. Download all files concurrently
        download_tasks = []
        for msg in messages_to_process:
            if msg.photo:
                # Get the highest resolution photo
                file_id = msg.photo[-1].file_id
                download_tasks.append(download_telegram_file(bot, file_id, batch_temp_dir))
            elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
                file_id = msg.document.file_id
                download_tasks.append(download_telegram_file(bot, file_id, batch_temp_dir))

        if not download_tasks:
            await status_msg.edit_text(
                "❌ <b>Aucune image valide n'a été trouvée.</b> Veuillez envoyer des photos de bons."
            )
            return

        downloaded_paths = await asyncio.gather(*download_tasks)

        # 3. Update status: Vision Extraction
        await status_msg.edit_text(
            f"🔍 <b>Numérisation et analyse des reçus en cours...</b>\n"
            f"<i>Traitement de {len(downloaded_paths)} reçu(s)...</i>"
        )

        extractions: List[SingleInvoiceExtraction] = await extractor.extract_from_images(downloaded_paths)

        # Filter out empty extractions
        valid_extractions = [ext for ext in extractions if ext.items]

        if not valid_extractions:
            await status_msg.edit_text(
                "⚠️ <b>Aucun article de pneu n'a pu être extrait de vos photos.</b>\n\n"
                "Veuillez vérifier que l'écriture manuscrite est lisible et réessayer avec des photos plus nettes."
            )
            return

        # 4. Update status: Normalization & Consolidation
        await status_msg.edit_text(
            "📊 <b>Consolidation des dimensions & calcul des totaux...</b>\n"
            "<i>Regroupement des références identiques et vérification des calculs...</i>"
        )

        consolidated = consolidate_extractions(valid_extractions)

        if not consolidated.items:
            await status_msg.edit_text(
                "⚠️ <b>Les données extraites ne contiennent aucun article valide.</b>"
            )
            return

        # 5. Update status: PDF Compilation
        await status_msg.edit_text(
            "📄 <b>Génération de la facture PDF récapitulative...</b>\n"
            "<i>Mise en page A4 et compilation du document...</i>"
        )

        pdf_filename = f"Facture_{consolidated.invoice_ref.replace('#', '')}.pdf"
        pdf_path = await pdf_generator.generate_pdf(consolidated, output_filename=pdf_filename)

        # 6. Save to shared database for Web Dashboard visibility
        try:
            db.save_consolidated_invoice(
                invoice=consolidated,
                pdf_filename=pdf_filename,
                source="telegram",
                image_paths=[str(p) for p in downloaded_paths],
            )
        except Exception as db_err:
            logger.warning(f"Failed to record invoice in database: {db_err}")

        # 7. Deliver the generated PDF and summary
        summary_text = format_telegram_summary(consolidated)
        pdf_input = FSInputFile(
            path=str(pdf_path),
            filename=pdf_filename,
        )

        # Delete status message to keep chat clean
        try:
            await status_msg.delete()
        except Exception:
            pass

        # Send PDF document with caption summary
        await message.answer_document(
            document=pdf_input,
            caption=summary_text,
        )

        logger.info(
            f"Successfully processed batch {session_id}: {consolidated.total_quantity} tyres, "
            f"{consolidated.grand_total} {settings.currency}"
        )

    except Exception as e:
        logger.error(f"Error processing invoice batch {session_id}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>Une erreur est survenue lors du traitement :</b>\n"
            f"<code>{str(e)[:200]}</code>\n\n"
            f"Veuillez réessayer ou contacter le support."
        )

    finally:
        # Clean up temporary downloaded files
        if batch_temp_dir.exists():
            shutil.rmtree(batch_temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Main Entrypoint
# ---------------------------------------------------------------------------

async def main():
    """Main bot startup function."""
    settings.setup_directories()

    logger.info("Starting Tyre Invoice Consolidator Bot (Gemini Vision)...")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Album debounce delay: {settings.album_debounce_seconds}s")

    # Drop pending updates and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
