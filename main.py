# main.py

import csv
import gspread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

BOT_TOKEN = "YOUR_BOT_TOKEN"
CSV_FILE = "partite_con_id.csv"
GOOGLE_SHEET_NAME = "Scommesse Mondiale Club FIFA 2025"
CREDENTIALS_FILE = "google-credentials.json"

# === SHEETS ===
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
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
        sheet.append_row([user_id, username, partita_id, esito, risultato, desc])

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
    return sorted({m[3].split()[0] for m in matches if m[0] not in bets})

def get_matches_by_date(date, bets):
    return [m for m in load_matches() if m[3].startswith(date) and m[0] not in bets]

def get_match_by_id(match_id):
    return next((m for m in load_matches() if m[0] == match_id), None)

# === CALLBACK STATE ===
user_bets = {}
scommesse_in_corso = {}

# === HANDLER ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Benvenuto nel bot del Mondiale per Club 2025!\n\n"
        "Con questo bot puoi:\n"
        "- Inserire una scommessa su ogni partita (esito + risultato esatto)\n"
        "- Modificarla fino all'inizio della partita"
    )

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_bets[user_id] = get_user_bets(user_id)
    dates = get_available_dates(user_bets[user_id])
    if not dates:
        await update.message.reply_text("✅ Hai già scommesso su tutte le partite.")
        return
    buttons = [[InlineKeyboardButton(date, callback_data=f"date_{date}")] for date in dates]
    await update.message.reply_text("📅 Scegli una data:", reply_markup=InlineKeyboardMarkup(buttons))

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    date = query.data.split("_", 1)[1]
    matches = get_matches_by_date(date, user_bets[user_id])
    buttons = [[InlineKeyboardButton(f"{m[1]} - {m[2]} ({m[3][11:]})", callback_data=f"match_{m[0]}")] for m in matches]
    await query.edit_message_text("⚽ Scegli una partita:", reply_markup=InlineKeyboardMarkup(buttons))

async def match_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    match_id = query.data.split("_", 1)[1]
    match = get_match_by_id(match_id)
    if not match:
        await query.edit_message_text("❌ Partita non trovata.")
        return
    scommesse_in_corso[user_id] = {'match_id': match_id, 'desc': match[5], 'dataora': match[3]}
    ora_partita = datetime.strptime(match[3], "%Y-%m-%d %H:%M")
    if datetime.now() > ora_partita:
        await query.edit_message_text("⛔ La partita è già iniziata.")
        return
    buttons = [
        [InlineKeyboardButton("1", callback_data="esito_1"),
         InlineKeyboardButton("X", callback_data="esito_X"),
         InlineKeyboardButton("2", callback_data="esito_2")]
    ]
    await query.edit_message_text(f"{match[5]}\n\nScegli l'esito:", reply_markup=InlineKeyboardMarkup(buttons))

async def esito_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    esito = query.data.split("_", 1)[1]
    scommesse_in_corso[user_id]['esito'] = esito
    await query.edit_message_text("✍️ Inserisci il risultato esatto (es. 2-1):")

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
    await update.message.reply_text("✅ Scommessa registrata con successo!", reply_markup=ReplyKeyboardRemove())

async def modifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    bets = get_user_bets(user_id)
    if not bets:
        await update.message.reply_text("Non hai scommesse da modificare.")
        return
    buttons = [[InlineKeyboardButton(val['desc'], callback_data=f"mod_{pid}")] for pid, val in bets.items()]
    await update.message.reply_text("📝 Quale scommessa vuoi modificare?", reply_markup=InlineKeyboardMarkup(buttons))

async def modifica_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    partita_id = query.data.split("_", 1)[1]
    match = get_match_by_id(partita_id)
    ora_partita = datetime.strptime(match[3], "%Y-%m-%d %H:%M")
    if datetime.now() > ora_partita:
        await query.edit_message_text("⛔ La partita è già iniziata e non può essere modificata.")
        return
    scommesse_in_corso[user_id] = {'match_id': partita_id, 'desc': match[5], 'dataora': match[3]}
    buttons = [
        [InlineKeyboardButton("1", callback_data="esito_1"),
         InlineKeyboardButton("X", callback_data="esito_X"),
         InlineKeyboardButton("2", callback_data="esito_2")]
    ]
    await query.edit_message_text(f"{match[5]}

Scegli il nuovo esito:", reply_markup=InlineKeyboardMarkup(buttons))

async def riepilogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    bets = get_user_bets(user_id)
    if not bets:
        await update.message.reply_text("Non hai ancora fatto nessuna scommessa.")
        return
    testo = "📋 Le tue scommesse:

"
    for val in bets.values():
        testo += f"- {val['desc']} → {val['esito']} ({val['risultato']})
"
    await update.message.reply_text(testo)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Con questo bot puoi:
"
        "- Visualizzare le partite con /partite
"
        "- Scommettere su esito e risultato esatto
"
        "- Modificare le scommesse con /modifica fino all'inizio
"
        "- Vedere il riepilogo con /riepilogo"
    )

# === SETUP ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("partite", partite))
app.add_handler(CommandHandler("modifica", modifica))
app.add_handler(CommandHandler("riepilogo", riepilogo))
app.add_handler(CommandHandler("info", info))
app.add_handler(CallbackQueryHandler(date_selected, pattern="^date_"))
app.add_handler(CallbackQueryHandler(match_selected, pattern="^match_"))
app.add_handler(CallbackQueryHandler(modifica_selected, pattern="^mod_"))
app.add_handler(CallbackQueryHandler(esito_selected, pattern="^esito_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, risultato_message))
app.run_polling()
