from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from match_data import get_available_dates, get_unscheduled_matches_by_date
from google_sheets import get_user_bets
from scommesse_handler import start_bet_flow

user_bets = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Benvenuto nel bot del Mondiale per Club 2025!\n\n"
        "Con questo bot puoi:\n"
        "- Inserire una scommessa su ogni partita (esito + risultato esatto)\n"
        "- Modificarla fino all'inizio della partita\n"
    )

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    bets = get_user_bets(user_id)
    user_bets[user_id] = bets
    available_dates = get_available_dates(bets)
    if not available_dates:
        await update.message.reply_text("✅ Hai già scommesso su tutte le partite.")
        return
    buttons = [[InlineKeyboardButton(date, callback_data=f"date_{date}")] for date in available_dates]
    await update.message.reply_text("📅 Seleziona una data:", reply_markup=InlineKeyboardMarkup(buttons))

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    date = query.data.split("_", 1)[1]
    matches = get_unscheduled_matches_by_date(user_bets.get(user_id, []), date)
    if not matches:
        await query.edit_message_text("✅ Hai già scommesso su tutte le partite di questa data.")
        return
    buttons = [
        [InlineKeyboardButton(f"{m[0]} - {m[1]} ({m[2][11:]})", callback_data=f"match_{m[0]}_{m[1]}_{m[2]}")]
        for m in matches
    ]
    await query.edit_message_text("⚽ Seleziona una partita:", reply_markup=InlineKeyboardMarkup(buttons))

async def match_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start_bet_flow(query, context)

app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("partite", partite))
app.add_handler(CallbackQueryHandler(date_selected, pattern="^date_"))
app.add_handler(CallbackQueryHandler(match_selected, pattern="^match_"))
app.run_polling()
