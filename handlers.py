from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram_bot_data import salva_scommessa_locale
from google_utils import get_google_sheet, scrivi_su_google_sheet
from config import application
from datetime import datetime

PARTITE = [
    {"id": "match1", "desc": "Al Ahly vs Inter Miami - 15/06 ore 02:00", "data": "2025-06-15 02:00"},
    {"id": "match2", "desc": "Bayern Monaco vs Auckland City - 15/06 ore 18:00", "data": "2025-06-15 18:00"},
    {"id": "match3", "desc": "PSG vs Atletico Madrid - 15/06 ore 21:00", "data": "2025-06-15 21:00"}
]

def get_partita(partita_id):
    return next((p for p in PARTITE if p["id"] == partita_id), None)

def partita_scaduta(partita):
    try:
        inizio = datetime.strptime(partita["data"], "%Y-%m-%d %H:%M")
        return datetime.now() > inizio
    except Exception:
        return False

def risultato_coerente(esito, risultato):
    try:
        g1, g2 = map(int, risultato.split("-"))
        if esito == "1":
            return g1 > g2
        elif esito == "X":
            return g1 == g2
        elif esito == "2":
            return g1 < g2
        return False
    except:
        return False

def setup_handlers():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("partite", partite))
    application.add_handler(CommandHandler("modifica", modifica))
    application.add_handler(CommandHandler("riepilogo", riepilogo))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CallbackQueryHandler(scelta_partita, pattern="^match"))
    application.add_handler(CallbackQueryHandler(scelta_esito, pattern="^(1|X|2)$"))
    application.add_handler(CallbackQueryHandler(scelta_modifica, pattern="^mod_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_risultato))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messaggio = (
        "👋 *Benvenuto nel bot del Mondiale per Club 2025!*\n\n"
        "Con questo bot puoi:\n"
        "- Inserire una scommessa su ogni partita (esito + risultato esatto)\n"
        "- Modificarla fino all'inizio dell'incontro\n"
        "- Visualizzare un riepilogo delle tue scommesse\n\n"
        "*Comandi disponibili:*\n"
        "📅 /partite – Visualizza le partite e inserisci la tua scommessa\n"
        "✏️ /modifica – Modifica una scommessa già inserita\n"
        "📊 /riepilogo – Mostra le tue scommesse già registrate\n"
        "ℹ️ /info – Dettagli sulla competizione e il regolamento\n\n"
        "📌 *Regole:*\n"
        "- Una scommessa per partita\n"
        "- Risultato esatto coerente con l’esito\n"
        "- Nessuna modifica o scommessa dopo l'orario della partita\n\n"
        "🔁 Usa /start in qualsiasi momento per rivedere questo messaggio."
    )
    await update.message.reply_text(messaggio, parse_mode="Markdown")

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_google_sheet()
    user_id = str(update.effective_user.id)
    scommesse_esistenti = []
    if sheet:
        scommesse_esistenti = [r["partita_id"] for r in sheet.get_all_records() if r["user_id"] == user_id]

    keyboard = []
    for p in PARTITE:
        if p["id"] not in scommesse_esistenti and not partita_scaduta(p):
            keyboard.append([InlineKeyboardButton(p["desc"], callback_data=p["id"])])

    if not keyboard:
        await update.message.reply_text("📭 Non ci sono partite disponibili per scommettere.")
    else:
        await update.message.reply_text("📅 Seleziona una partita:", reply_markup=InlineKeyboardMarkup(keyboard))

async def scelta_partita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data
    partita = get_partita(partita_id)

    if not partita or partita_scaduta(partita):
        await query.edit_message_text("❌ La partita è già iniziata o non è valida.")
        return

    context.user_data["partita_id"] = partita_id
    context.user_data["partita_desc"] = partita["desc"]
    context.user_data["partita_data"] = partita["data"]

    keyboard = [
        [InlineKeyboardButton("1", callback_data="1"),
         InlineKeyboardButton("X", callback_data="X"),
         InlineKeyboardButton("2", callback_data="2")]
    ]
    await query.edit_message_text(
        f"📌 Partita selezionata: {partita['desc']}\n\nScegli l’esito:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def scelta_esito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    esito = query.data
    context.user_data["esito"] = esito
    await query.edit_message_text(f"✅ Esito selezionato: {esito}\n\n✍️ Ora inviami il risultato esatto (es. 2-1):")

async def inserisci_risultato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    risultato = update.message.text.strip()
    user = update.effective_user
    user_id = str(user.id)
    nome_utente = user.full_name or user.username
    partita_id = context.user_data.get("partita_id")
    partita_desc = context.user_data.get("partita_desc")
    esito = context.user_data.get("esito")

    partita = get_partita(partita_id)
    if not partita or partita_scaduta(partita):
        await update.message.reply_text("⛔ Impossibile registrare: la partita è iniziata.")
        return

    if not risultato_coerente(esito, risultato):
        await update.message.reply_text("⚠️ Il risultato non è coerente con l’esito scelto. Riprova (es. 2-1 per '1').")
        return

    riga = [user_id, nome_utente, partita_id, esito, risultato, partita_desc]
    sheet = get_google_sheet()
    if sheet:
        tutte = sheet.get_all_records()
        index = next((i for i, r in enumerate(tutte)
                     if r.get("user_id") == user_id and r.get("partita_id") == partita_id), None)
        if index is not None:
            sheet.delete_rows(index + 2)
        scrivi_su_google_sheet(sheet, riga)

    salva_scommessa_locale(riga)
    await update.message.reply_text(
        f"🎉 *Scommessa registrata con successo!*\n\n"
        f"📝 *{partita_desc}*\n"
        f"📊 Esito: *{esito}*\n"
        f"🎯 Risultato: *{risultato}*",
        parse_mode="Markdown"
    )
    context.user_data.clear()

async def modifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_google_sheet()
    if not sheet:
        await update.message.reply_text("⚠️ Errore durante l'accesso al foglio.")
        return

    user_id = str(update.effective_user.id)
    tutte = sheet.get_all_records()
    scommesse = [r for r in tutte if r.get("user_id") == user_id]

    keyboard = []
    for r in scommesse:
        partita = get_partita(r["partita_id"])
        if partita and not partita_scaduta(partita):
            keyboard.append([InlineKeyboardButton(r["desc"], callback_data=f"mod_{r['partita_id']}")])

    if not keyboard:
        await update.message.reply_text("⏱️ Nessuna partita ancora modificabile.")
        return

    await update.message.reply_text("✏️ Seleziona la partita da modificare:", reply_markup=InlineKeyboardMarkup(keyboard))

async def scelta_modifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data.replace("mod_", "")
    partita = get_partita(partita_id)

    if not partita or partita_scaduta(partita):
        await query.edit_message_text("⛔ La partita è già iniziata, non è più modificabile.")
        return

    context.user_data["partita_id"] = partita_id
    context.user_data["partita_desc"] = partita["desc"]
    context.user_data["partita_data"] = partita["data"]

    keyboard = [
        [InlineKeyboardButton("1", callback_data="1"),
         InlineKeyboardButton("X", callback_data="X"),
         InlineKeyboardButton("2", callback_data="2")]
    ]
    await query.edit_message_text(
        f"✏️ Modifica per: {partita['desc']}\n\nSeleziona il nuovo esito:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def riepilogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_google_sheet()
    if not sheet:
        await update.message.reply_text("⚠️ Impossibile accedere al riepilogo al momento.")
        return

    user_id = str(update.effective_user.id)
    tutte = sheet.get_all_records()
    scommesse_utente = [row for row in tutte if row.get("user_id") == user_id]

    if not scommesse_utente:
        await update.message.reply_text("📭 Non hai ancora inserito nessuna scommessa.")
        return

    msg = "📊 *Le tue scommesse registrate:*\n"
    for r in scommesse_utente:
        msg += (
            f"\n📝 {r.get('desc', 'Partita sconosciuta')}"
            f"\n📊 Esito: {r.get('esito', '?')}"
            f"\n🎯 Risultato: {r.get('risultato', '?')}\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Mondiale per Club FIFA 2025*\n\n"
        "- 32 squadre da tutto il mondo\n"
        "- Partite a eliminazione diretta\n"
        "- Vince chi indovina più risultati esatti!\n\n"
        "Scommesse gratuite tra amici, nessun premio reale.\n"
        "Tanto onore, tanto divertimento 😎",
        parse_mode="Markdown"
    )
