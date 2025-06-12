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

def aggiorna_punteggi():
    sheet = get_sheet()
    risultati_sheet = get_sheet().spreadsheet.worksheet("Risultati")

    risultati = risultati_sheet.get_all_records()
    risultati_dict = {r['partita_id']: r for r in risultati}

    records = sheet.get_all_records()
    for i, riga in enumerate(records, start=2):  # +2 per tenere conto dell'intestazione (1-based index)
        partita_id = riga['partita_id']
        if partita_id not in risultati_dict:
            continue

        risultato_reale = risultati_dict[partita_id]['risultato']
        esito_reale = risultati_dict[partita_id]['esito']

        punteggio = 0
        if riga['esito'] == esito_reale:
            punteggio += 3
        if riga['risultato'] == risultato_reale:
            punteggio += 5

        sheet.update_cell(i, 7, punteggio)  # colonna 7 = punteggio

def get_custom_name(user_id):
    sheet = get_sheet().spreadsheet.worksheet("Nome utente")
    records = sheet.get_all_records()
    for row in records:
        if str(row['user_id']) == str(user_id):
            return row.get('nome')
    return None

async def aggiorna_punteggi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        aggiorna_punteggi()
        await update.message.reply_text("✅ Punteggi aggiornati correttamente.")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante l'aggiornamento dei punteggi: {e}")

async def classifica_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()

        nome_sheet = get_sheet().spreadsheet.worksheet("Nome utente")
        nome_records = nome_sheet.get_all_records()
        nome_dict = {str(r['user_id']): r['nome'] for r in nome_records if r.get('nome')}

        classifica = {}
        for row in records:
            user_id = str(row['user_id'])
            user = nome_dict.get(user_id) or row.get('username') or f"ID:{user_id}"
            punti = row.get('punteggio')
            if isinstance(punti, int):
                classifica[user] = classifica.get(user, 0) + punti
            elif isinstance(punti, str) and punti.isdigit():
                classifica[user] = classifica.get(user, 0) + int(punti)

        if not classifica:
            await update.message.reply_text("❌ Nessun punteggio disponibile per generare la classifica.")
            return

        ordinata = sorted(classifica.items(), key=lambda x: x[1], reverse=True)
        testo = "🏆 Classifica:\n"
        for i, (utente, punti) in enumerate(ordinata, start=1):
            if i == 1:
                emoji = "🥇"
            elif i == 2:
                emoji = "🥈"
            elif i == 3:
                emoji = "🥉"
            else:
                emoji = f"{i}."
            testo += f"{emoji} {utente} — {punti} punti\n"

        await update.message.reply_text(testo)
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante la generazione della classifica: {e}")

async def imposta_nome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usa il comando così: /imposta_nome tuo_nome")
        return
    nuovo_nome = " ".join(args).strip()
    try:
        nome_sheet = get_sheet().spreadsheet.worksheet("Nome utente")
        records = nome_sheet.get_all_records()
        trovato = False
        for i, row in enumerate(records, start=2):
            if str(row['user_id']) == user_id:
                nome_sheet.update_cell(i, 2, nuovo_nome)  # seconda colonna = nome
                trovato = True
                break
        if not trovato:
            nome_sheet.append_row([user_id, nuovo_nome])

        await update.message.reply_text(f"✅ Nome impostato come: {nuovo_nome}. Verrà usato per la classifica.")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante l'impostazione del nome: {e}")

# === CALLBACK STATE ===
user_bets = {}
scommesse_in_corso = {}
modifica_in_corso = {}

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or "-"
    nome_personalizzato = get_custom_name(user_id)

    if username == "-" and not nome_personalizzato:
        await update.message.reply_text(
            "👤 Non hai un nome utente impostato.\n"
            "👉 Usa il comando /imposta_nome seguito dal nome che vuoi usare in classifica (es. /imposta_nome Marco Rossi)"
        )

    await update.message.reply_text(
        "👋 Benvenuto nel bot del Mondiale per Club 2025!\n\n"
        "Con questo bot puoi partecipare a una sfida tra amici pronosticando tutte le partite del torneo.\n\n"
        "📌 Cosa puoi fare:\n"
        "⚽ /partite — per vedere le partite disponibili e inserire una scommessa (esito + risultato esatto)\n"
        "✏️ /modifica — per modificare una scommessa già fatta, fino all'inizio della partita\n"
        "📋 /riepilogo — per vedere tutte le tue scommesse attuali\n"
        "👤 /imposta_nome — per assegnare un nome personalizzato da usare in classifica\n"
        "ℹ️ /info — per rileggere queste istruzioni in qualsiasi momento"
    )

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_bets[user_id] = get_user_bets(user_id)
    dates = get_available_dates(user_bets[user_id])
    if not dates:
        await update.message.reply_text("✅ Hai già scommesso su tutte le partite disponibili.")
        return
    buttons = [[InlineKeyboardButton(date, callback_data=f"date_{date}")] for date in dates]
    await update.message.reply_text("📅 Scegli una data:", reply_markup=InlineKeyboardMarkup(buttons))

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    date = query.data.split("_", 1)[1]
    matches = get_matches_by_date(date, user_bets[user_id])
    if not matches:
        await query.edit_message_text("⛔ Nessuna partita disponibile per quella data.", reply_markup=InlineKeyboardMarkup([[]]))
        return
    buttons = [[InlineKeyboardButton(f"{m[1]} - {m[2]} ({m[3][11:]})", callback_data=f"match_{m[0]}")] for m in matches]
    await query.edit_message_text("⚽ Scegli una partita:", reply_markup=InlineKeyboardMarkup(buttons))

async def match_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    match_id = query.data.split("_", 1)[1]
    match = get_match_by_id(match_id)
    if not match:
        await query.edit_message_text("❌ Partita non trovata.", reply_markup=InlineKeyboardMarkup([[]]))
        return
    ora_partita = datetime.strptime(match[3], "%Y-%m-%d %H:%M")
    if datetime.now() > ora_partita:
        await query.edit_message_text("⛔ La partita è già iniziata.", reply_markup=InlineKeyboardMarkup([[]]))
        return
    scommesse_in_corso[user_id] = {'match_id': match_id, 'desc': match[5], 'dataora': match[3]}
    buttons = [[
        InlineKeyboardButton("1", callback_data="esito_1"),
        InlineKeyboardButton("X", callback_data="esito_X"),
        InlineKeyboardButton("2", callback_data="esito_2")
    ]]
    await query.edit_message_text(f"{match[5]}\n\nScegli l'esito:", reply_markup=InlineKeyboardMarkup(buttons))

async def esito_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    esito = query.data.split("_", 1)[1]
    if user_id in modifica_in_corso:
        modifica_in_corso[user_id]['esito'] = esito
    else:
        scommesse_in_corso[user_id]['esito'] = esito
    await query.edit_message_text(
        f"✅ Hai selezionato l'esito: {esito}\n✍️ Ora inserisci il risultato esatto (es. 2-1):",
        reply_markup=InlineKeyboardMarkup([[]])
    )

async def risultato_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    risultato = update.message.text.strip()
    if user_id in scommesse_in_corso:
        scommessa = scommesse_in_corso.pop(user_id)
        tipo = "nuova"
    elif user_id in modifica_in_corso:
        scommessa = modifica_in_corso.pop(user_id)
        tipo = "modifica"
    else:
        return

    esito = scommessa['esito']
    try:
        squadra1_gol, squadra2_gol = map(int, risultato.split("-"))
    except:
        await update.message.reply_text("❌ Formato risultato non valido. Usa il formato es. 2-1.")
        return

    if (esito == "1" and squadra1_gol <= squadra2_gol) or \
       (esito == "2" and squadra1_gol >= squadra2_gol) or \
       (esito == "X" and squadra1_gol != squadra2_gol):
        await update.message.reply_text(
            f"❌ Il risultato {risultato} non è coerente con l'esito {esito}.\n"
            "✍️ Inserisci un nuovo risultato esatto coerente (es. 2-1):"
        )
        # Reinserisce la scommessa corrente nel dizionario
        if tipo == "nuova":
            scommesse_in_corso[user_id] = scommessa
        else:
            modifica_in_corso[user_id] = scommessa
        return

    write_bet(user_id, update.message.from_user.username, scommessa['match_id'], esito, risultato, scommessa['desc'])
    msg = "✏️ Scommessa modificata!" if tipo == "modifica" else "✅ Scommessa registrata!"
await update.message.reply_text(
    f"{msg}\n📝 {scommessa['desc']}\nEsito: {esito} — Risultato: {risultato}\n\n"
    "📌 Per fare nuove scommesse puoi usare /partite oppure premere /start per rileggere le istruzioni iniziali.",
    reply_markup=ReplyKeyboardRemove()
)

async def modifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    bets = get_user_bets(user_id)
    if not bets:
        await update.message.reply_text("Non hai scommesse da modificare.")
        return

    buttons = []
    for pid, val in bets.items():
        match = get_match_by_id(pid)
        if not match:
            continue
        ora_partita = datetime.strptime(match[3], "%Y-%m-%d %H:%M")
        if ora_partita > datetime.now():
            buttons.append([InlineKeyboardButton(val['desc'], callback_data=f"mod_{pid}")])

    if not buttons:
        await update.message.reply_text("⛔ Tutte le partite su cui hai scommesso sono già iniziate.")
        return

    await update.message.reply_text("📜 Quale scommessa vuoi modificare?", reply_markup=InlineKeyboardMarkup(buttons))
    await update.message.reply_text("✏️ Dopo aver selezionato, potrai cambiare esito e risultato.")

async def modifica_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    partita_id = query.data.split("_", 1)[1]
    match = get_match_by_id(partita_id)
    ora_partita = datetime.strptime(match[3], "%Y-%m-%d %H:%M")
    if datetime.now() > ora_partita:
        await query.edit_message_text("⛔ La partita è già iniziata e non può essere modificata.", reply_markup=InlineKeyboardMarkup([[]]))
        return
    modifica_in_corso[user_id] = {'match_id': partita_id, 'desc': match[5], 'dataora': match[3]}
    buttons = [[
        InlineKeyboardButton("1", callback_data="esito_1"),
        InlineKeyboardButton("X", callback_data="esito_X"),
        InlineKeyboardButton("2", callback_data="esito_2")
    ]]
    await query.edit_message_text(
        f"✏️ Stai modificando la scommessa per: {match[5]}\nScegli un nuovo esito:",
        reply_markup=InlineKeyboardMarkup(buttons))

async def riepilogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    bets = get_user_bets(user_id)
    if not bets:
        await update.message.reply_text("Non hai ancora fatto nessuna scommessa.")
        return
    testo = "📋 Le tue scommesse:\n"
    for val in bets.values():
        testo += f"- {val['desc']} → {val['esito']} ({val['risultato']})\n"
    await update.message.reply_text(testo)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Con questo bot puoi:\n"
        "- Visualizzare le partite con /partite\n"
        "- Scommettere su esito e risultato esatto\n"
        "- Modificare le scommesse con /modifica fino all'inizio della partita\n"
        "- Vedere il riepilogo delle tue scommesse con /riepilogo"
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = (
        "🛠️ *Comandi disponibili*\n\n"
        "👋 /start >Avvia il bot e mostra le istruzioni iniziali\n" 
        "⚽ /partite >Visualizza le partite disponibili per scommettere (esito + risultato)\n" 
        "✏️ /modifica >Modifica una scommessa fatta, se la partita non è ancora iniziata\n" 
        "📋 /riepilogo >Mostra l'elenco delle scommesse già effettuate\n" 
        "ℹ️ /info >Riepilogo delle funzionalità principali del bot\n" 
        "📊 /classifica >Visualizza la classifica generale aggiornata\n" 
        "🔁 /aggiorna_punteggi >Confronta le scommesse con i risultati e aggiorna i punteggi\n" 
        "👤 /imposta_nome >Imposta un nome personalizzato da usare in classifica\n" 
        "🛠️ /admin >Elenco dei comandi disponibili e relative funzioni (questo messaggio)" 
    )
    await update.message.reply_text(testo, parse_mode="Markdown")

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
application.add_handler(CommandHandler("aggiorna_punteggi", aggiorna_punteggi_command))
application.add_handler(CommandHandler("classifica", classifica_command))
application.add_handler(CommandHandler("imposta_nome", imposta_nome_command))
application.add_handler(CommandHandler("admin", admin_command))

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, port=port)
