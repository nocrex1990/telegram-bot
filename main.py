# main.py

import os
import csv
import gspread
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from google.oauth2.service_account import Credentials
from datetime import datetime

BOT_TOKEN = "7325517939:AAGlZfdCwK8q7xaTfyGjO-EUDw-hTWuUrDA"
CSV_FILE = "partite.csv"
GOOGLE_SHEET_NAME = "Scommesse Mondiale Club FIFA 2025"
CREDENTIALS_FILE = "google-credentials.json"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://telegram-bot-rexx.onrender.com{WEBHOOK_PATH}"

# === SHEETS ===
def get_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
    client = gspread.authorize(creds)
    return client.open(GOOGLE_SHEET_NAME).sheet1

def get_user_bets(user_id):
    sheet = get_sheet()
    records = sheet.get_all_records()
    return {row['partita_id']: row for row in records if str(row['user_id']) == str(user_id)}

def write_bet(user_id, username, partita_id, esito, risultato, desc):
    sheet = get_sheet()
    existing = get_user_bets(user_id)
    if partita_id in existing:
        cell = sheet.find(partita_id)
        sheet.update_cell(cell.row, 4, esito)
        sheet.update_cell(cell.row, 5, risultato)
    else:
        sheet.append_row([user_id, username or "-", partita_id, esito, risultato, desc])

# === PARTITE ===
def load_matches():
    matches = []
    with open(CSV_FILE, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            id = row['partita_id']
            squadra1 = row['Squadra1']
            squadra2 = row['Squadra2']
            dataora = f"{row['Data']} {row['Ora']}"
            stadio = row['Stadio']
            desc = f"{squadra1} vs {squadra2} - {row['Data']} ore {row['Ora']}"
            matches.append((id, squadra1, squadra2, dataora, stadio, desc))
    return matches

def get_available_dates(bets):
    matches = load_matches()
    return sorted({m[3].split()[0] for m in matches if m[0] not in bets and datetime.strptime(m[3], "%Y-%m-%d %H:%M") > datetime.now()})

def get_matches_by_date(date, bets):
    return [m for m in load_matches() if m[3].startswith(date) and m[0] not in bets and datetime.strptime(m[3], "%Y-%m-%d %H:%M") > datetime.now()]

def get_match_by_id(match_id):
    return next((m for m in load_matches() if m[0] == match_id), None)

# === CALLBACK STATE ===
user_bets = {}
scommesse_in_corso = {}

# === HANDLERS ===
# ... (resto del codice invariato fino a modifica_selected)

async def modifica_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    partita_id = query.data.split("_", 1)[1]
    match = get_match_by_id(partita_id)
    if not match:
        await query.edit_message_text("❌ Partita non trovata.")
        return
    ora_partita = datetime.strptime(match[3], "%Y-%m-%d %H:%M")
    if datetime.now() > ora_partita:
        await query.edit_message_text("⛔ La partita è già iniziata e non può essere modificata.")
        return
    scommesse_in_corso[user_id] = {'match_id': partita_id, 'desc': match[5], 'dataora': match[3], 'modifica': True}
    buttons = [[
        InlineKeyboardButton("1", callback_data="esito_1"),
        InlineKeyboardButton("X", callback_data="esito_X"),
        InlineKeyboardButton("2", callback_data="esito_2")
    ]]
    await query.edit_message_text(
        f"✏️ Stai modificando la scommessa per: {match[5]}\nScegli un nuovo esito:",
        reply_markup=InlineKeyboardMarkup(buttons))

# Aggiornamento in risultato_message per conferma modifica
async def risultato_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in scommesse_in_corso:
        return
    risultato = update.message.text.strip()
    scommessa = scommesse_in_corso.pop(user_id)
    esito = scommessa['esito']
    try:
        squadra1_gol, squadra2_gol = map(int, risultato.split("-"))
    except:
        await update.message.reply_text("❌ Formato risultato non valido. Usa il formato es. 2-1.")
        return
    if (esito == "1" and squadra1_gol <= squadra2_gol) or \
       (esito == "2" and squadra1_gol >= squadra2_gol) or \
       (esito == "X" and squadra1_gol != squadra2_gol):
        await update.message.reply_text("❌ Il risultato non è coerente con l'esito scelto.")
        return
    write_bet(user_id, update.message.from_user.username, scommessa['match_id'], esito, risultato, scommessa['desc'])
    conferma = "✏️ Modifica effettuata con successo!" if scommessa.get('modifica') else "✅ Scommessa registrata!"
    await update.message.reply_text(
        f"{conferma}\n📝 {scommessa['desc']}\nEsito: {esito} — Risultato: {risultato}",
        reply_markup=ReplyKeyboardRemove())

# === AIOHTTP WEBHOOK ===
async def handle(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="OK")

async def on_startup(app):
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)

application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CommandHandler("modifica", modifica))
application.add_handler(CommandHandler("riepilogo", riepilogo))
application.add_handler(CommandHandler("info", info))
application.add_handler(CallbackQueryHandler(date_selected, pattern="^date_"))
application.add_handler(CallbackQueryHandler(match_selected, pattern="^match_"))
application.add_handler(CallbackQueryHandler(modifica_selected, pattern="^mod_"))
application.add_handler(CallbackQueryHandler(esito_selected, pattern="^esito_"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, risultato_message))

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, port=port)
