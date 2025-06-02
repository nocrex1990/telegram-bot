from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram_bot_data import scommesse_utente, salva_scommessa_locale, partite_lookup
from google_utils import get_google_sheet, scrivi_su_google_sheet
from config import application

# Lista partite demo
PARTITE = [
    {"id": "match1", "desc": "Al Ahly vs Inter Miami - 15/06 ore 02:00"},
    {"id": "match2", "desc": "Bayern Monaco vs Auckland City - 15/06 ore 18:00"},
    {"id": "match3", "desc": "PSG vs Atletico Madrid - 15/06 ore 21:00"},
]

def setup_handlers():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("partite", partite))
    application.add_handler(CommandHandler("debug", debug))
    application.add_handler(CallbackQueryHandler(scelta_partita, pattern="^match"))
    application.add_handler(CallbackQueryHandler(scelta_esito, pattern="^(1|X|2)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_risultato))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Benvenuto! Il bot è pronto per ricevere le tue scommesse.")

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(p["desc"], callback_data=p["id"])]
        for p in PARTITE
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📅 Seleziona una partita:", reply_markup=reply_markup)

async def scelta_partita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data
    context.user_data["partita_id"] = partita_id
    partita_desc = next((p["desc"] for p in PARTITE if p["id"] == partita_id), "")
    context.user_data["partita_desc"] = partita_desc

    keyboard = [
        [InlineKeyboardButton("1", callback_data="1"),
         InlineKeyboardButton("X", callback_data="X"),
         InlineKeyboardButton("2", callback_data="2")]
    ]
    await query.edit_message_text(
        f"📌 Partita selezionata: {partita_desc}\n\nScegli l’esito:",
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

    if not (partita_id and esito):
        await update.message.reply_text("❌ Per favore usa /partite per iniziare una nuova scommessa.")
        return

    riga = [user_id, nome_utente, partita_id, esito, risultato, partita_desc]
    salva_scommessa_locale(riga)

    sheet = get_google_sheet()
    if sheet:
        scrivi_su_google_sheet(sheet, riga)

    await update.message.reply_text(
        f"✅ Scommessa registrata:\n\n📝 {partita_desc}\n📊 Esito: {esito}\n🎯 Risultato: {risultato}"
    )
    context.user_data.clear()

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_url = "https://telegram-bot-rexx.onrender.com/log"
    await update.message.reply_text(f"🪵 Ecco il link per visualizzare i log:\n{log_url}")
