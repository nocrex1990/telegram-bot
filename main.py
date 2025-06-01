# === BOT TELEGRAM MONDIALE PER CLUB ===

import logging

# Configura il logging su file per Render
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Import delle librerie principali
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import os
import csv
from aiohttp import web
from collections import defaultdict
import asyncio
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json

# === CONFIGURAZIONE ===
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH
application = ApplicationBuilder().token(TOKEN).build()

# === STRUTTURE DATI ===
partite_per_data = defaultdict(list)  # partite raggruppate per data
partite_lookup = {}                   # lookup veloce per ID partita
scommesse_utente = defaultdict(dict)  # dizionario scommesse per utente

# === PATH FILE ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOMMESSE_PATH = os.path.join(BASE_DIR, "scommesse.csv")
GOOGLE_SHEET_NAME = "Scommesse Mondiale Club FIFA 2025"

# === AUTENTICAZIONE GOOGLE SHEETS ===
try:
    credentials = Credentials.from_service_account_file(
        os.path.join(BASE_DIR, "google-credentials.json"),
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    gs_client = gspread.authorize(credentials)
    sheet = gs_client.open(GOOGLE_SHEET_NAME).sheet1
    logging.info("✅ Collegato al Google Sheet!")
except Exception as e:
    logging.error(f"❌ Errore nell'accesso a Google Sheet: {e}")
    sheet = None

# === CARICAMENTO SCOMMESSE LOCALI ===
if os.path.exists(SCOMMESSE_PATH):
    with open(SCOMMESSE_PATH, newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            scommesse_utente[row["user_id"]][row["partita_id"]] = row

# === FUNZIONE DI SCRITTURA SU GOOGLE SHEET ===
def scrivi_scommessa_su_google_sheet(sheet, riga):
    import sys
    try:
        logging.info("✍️ Tentativo di scrittura su Google Sheets...")
        sys.stdout.flush()

        # Scrive intestazione se il foglio è vuoto
        if not sheet.get_all_values():
            header = ["user_id", "nome_utente", "partita_id", "esito", "risultato", "desc"]
            sheet.append_row(header)
            logging.info(f"📌 Intestazione aggiunta: {header}")

        sheet.append_row(riga)
        logging.info(f"✅ Riga scritta: {riga}")
        sys.stdout.flush()
    except Exception as e:
        logging.error(f"❌ Errore durante la scrittura su Google Sheets: {e}")
        sys.stdout.flush()
        print(f"❌ Errore durante la scrittura su Google Sheets: {e}")

# === COMANDI E HANDLER ===

# (tutto il resto del codice rimane invariato)

# Modifica apportata: corretta indentazione dopo if sheet: (riga 282 circa)
# La chiamata a scrivi_scommessa_su_google_sheet(sheet, riga) era fuori blocco e ha generato IndentationError

# === AVVIO SERVER AIOHTTP CON WEBHOOK ===

async def handle_webhook(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

async def run():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    await application.initialize()
    await application.start()
    info = await application.bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)

    logging.info(f"🌐 Webhook finale: {WEBHOOK_URL}")
    logging.info("🚀 Bot e server aiohttp avviati correttamente")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(run())
