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
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
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
        sheet.append_row(riga)
        logging.info(f"✅ Riga scritta: {riga}")
        sys.stdout.flush()
    except Exception as e:
        logging.error(f"❌ Errore durante la scrittura su Google Sheets: {e}")
        sys.stdout.flush()
        print(f"❌ Errore durante la scrittura su Google Sheets: {e}")

# === COMANDI E HANDLER ===

# Messaggio di benvenuto
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""👋 Benvenuto nel bot del Mondiale per Club 2025!

Con questo bot puoi:
- Inserire una scommessa su ogni partita (esito + risultato esatto)
- Modificarla fino all'inizio dell'incontro
- Visualizzare un riepilogo delle tue scommesse

Comandi disponibili:
📅 /partite – Visualizza le partite e inserisci la tua scommessa
✏️ /modifica – Modifica una scommessa già inserita
📊 /riepilogo – Mostra le tue scommesse già registrate
ℹ️ /info – Dettagli sulla competizione e il regolamento

📌 Regole:
- Una scommessa per partita
- Risultato esatto coerente con l’esito
- Nessuna modifica o scommessa dopo l'orario della partita

🔁 Usa /start in qualsiasi momento per rivedere questo messaggio.""")

# Info torneo
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
ℹ️ Dettagli sul torneo del Mondiale per Club FIFA 2025:

📍 Si gioca negli Stati Uniti dal 15 giugno al 13 luglio 2025.
🏆 32 squadre da tutto il mondo, gironi + eliminazione diretta.
🎯 Scommesse su esito + risultato esatto, modificabili fino al fischio d’inizio.
""")

# Visualizza le scommesse registrate
async def riepilogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    scommesse = scommesse_utente.get(user_id, {})
    if not scommesse:
        await update.message.reply_text("Non hai ancora inserito nessuna scommessa.")
        return

    messaggi = ["📊 Le tue scommesse registrate:"]
    for s in scommesse.values():
        messaggi.append(f"- {s['desc']}: {s['esito']} ({s['risultato']})")

    await update.message.reply_text("\n".join(messaggi))

# Comando /partite - mostra date disponibili per scommettere
async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("partite.csv", newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            partite_per_data.clear()
            partite_lookup.clear()
            for i, riga in enumerate(reader, start=1):
                partita = {
                    "id": str(i),
                    "data": riga["Data"].strip(),
                    "ora": riga["Ora"].strip(),
                    "s1": riga["Squadra1"].strip(),
                    "s2": riga["Squadra2"].strip(),
                    "stadio": riga["Stadio"].strip()
                }
                partite_per_data[partita["data"]].append(partita)
                partite_lookup[str(i)] = partita

        user_id = str(update.effective_user.id)
        keyboard = []
        now = datetime.now()

        for data in partite_per_data:
            disponibili = any(
                p["id"] not in scommesse_utente[user_id] and
                datetime.strptime(f"{p['data']} {p['ora']}", "%Y-%m-%d %H:%M") > now
                for p in partite_per_data[data]
            )
            if disponibili:
                keyboard.append([InlineKeyboardButton(data, callback_data=f"data:{data}")])

        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📅 Seleziona una data:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("✅ Nessuna partita disponibile al momento per essere scommessa.")

    except Exception as e:
        await update.message.reply_text("Errore nella lettura delle partite.")
        raise e

# Callback - selezione data
async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.split(":")[1]
    user_id = str(query.from_user.id)

    partite = partite_per_data[selected_date]
    keyboard = []

    for partita in partite:
        if partita["id"] in scommesse_utente[user_id]:
            continue
        desc = f"{partita['ora']} - {partita['s1']} vs {partita['s2']} ({partita['stadio']})"
        keyboard.append([InlineKeyboardButton(desc, callback_data=f"match:{partita['id']}")])

    if keyboard:
        await query.edit_message_text(
            text=f"📆 Partite del {selected_date}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(f"Nessuna partita disponibile il {selected_date}.")

# Callback - selezione partita
async def handle_match_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data.split(":")[1]
    partita = partite_lookup.get(partita_id)
    if not partita:
        await query.edit_message_text("❌ Partita non trovata.")
        return

    data_ora = datetime.strptime(f"{partita['data']} {partita['ora']}", "%Y-%m-%d %H:%M")
    if datetime.now() >= data_ora:
        await query.edit_message_text("⏰ Non è più possibile scommettere su questa partita.")
        return

    context.user_data["partita_id"] = partita_id
    buttons = [
        [InlineKeyboardButton("1", callback_data="esito:1")],
        [InlineKeyboardButton("X", callback_data="esito:X")],
        [InlineKeyboardButton("2", callback_data="esito:2")]
    ]
    await query.edit_message_text("Scegli l'esito della partita:", reply_markup=InlineKeyboardMarkup(buttons))

# Callback - selezione esito (1/X/2)
async def handle_esito_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    esito = query.data.split(":")[1]
    context.user_data["esito"] = esito
    await query.edit_message_text("Scrivi il risultato esatto (es. 2-1):")

# Invio manuale del risultato esatto, con verifica e salvataggio CSV + Google Sheet
async def handle_risultato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # DEBUG: controllo oggetto Google Sheet
    logging.info(f"🧪 sheet è None? {sheet is None}")
    logging.info(f"📄 sheet = {type(sheet)} {sheet}")
    risultato = update.message.text.strip()
    if "-" not in risultato:
        await update.message.reply_text("Formato non valido. Usa es: 2-1")
        return

    try:
        g1, g2 = map(int, risultato.split("-"))
    except:
        await update.message.reply_text("Numeri non validi.")
        return

    esito = context.user_data.get("esito")
    if (esito == "1" and g1 <= g2) or (esito == "2" and g2 <= g1) or (esito == "X" and g1 != g2):
        await update.message.reply_text("❌ Il risultato non è coerente con l'esito scelto.")
        return

    partita_id = context.user_data.get("partita_id")
    user_id = str(update.effective_user.id)
    partita = partite_lookup.get(partita_id)

    scommesse_utente[user_id][partita_id] = {
        "user_id": user_id,
        "partita_id": partita_id,
        "esito": esito,
        "risultato": risultato,
        "desc": f"{partita['s1']} vs {partita['s2']}"
    }

    with open(SCOMMESSE_PATH, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "partita_id", "esito", "risultato", "desc"])
        writer.writeheader()
        for uid in scommesse_utente:
            for sid in scommesse_utente[uid]:
                writer.writerow(scommesse_utente[uid][sid])

    logging.info(f"✅ Scrittura scommessa in {SCOMMESSE_PATH}")

    if sheet:
        riga = [user_id, partita_id, esito, risultato, f"{partita['s1']} vs {partita['s2']}"]
        scrivi_scommessa_su_google_sheet(sheet, riga)

    await update.message.reply_text(f"✅ Scommessa registrata per {partita['s1']} vs {partita['s2']}")
    context.user_data.clear()

# === REGISTRAZIONE HANDLER ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("info", info))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CommandHandler("riepilogo", riepilogo))
application.add_handler(CallbackQueryHandler(handle_date_selection, pattern=r"^data:.*"))
application.add_handler(CallbackQueryHandler(handle_match_selection, pattern=r"^match:.*"))
application.add_handler(CallbackQueryHandler(handle_esito_selection, pattern=r"^esito:.*"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_risultato))

# === WEBHOOK SERVER ===
async def handle_webhook(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

# === AVVIO APPLICAZIONE ===
async def run():
    # Avvio server aiohttp per ricevere il webhook
    app = web.Application()

    # === ENDPOINT DI DEBUG PER VISIONARE IL FILE LOG ===
    async def mostra_log(request):
        try:
            with open("bot.log", "r", encoding="utf-8") as f:
                contenuto = f.read()[-4000:]
            return web.Response(text=contenuto, content_type="text/plain")
        except Exception as e:
            return web.Response(text=f"Errore lettura log: {e}", status=500)

    app.router.add_get("/log", mostra_log)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render"))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    # Avvio bot telegram
    await application.initialize()
    await application.start()

    info = await application.bot.get_webhook_info()
    logging.info(f"🔁 Verifica stato webhook attuale: {info.url}")
    if info.url != WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logging.info("✅ Webhook impostato")
    else:
        logging.info("✅ Webhook già attivo")

    logging.info(f"🌐 Webhook finale: {WEBHOOK_URL}")
    logging.info("🚀 Bot e server aiohttp avviati correttamente")

# === MAIN ===
asyncio.run(run())
