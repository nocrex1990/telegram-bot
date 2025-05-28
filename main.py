from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import os
import csv
from aiohttp import web
from collections import defaultdict

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

application = ApplicationBuilder().token(TOKEN).build()

# === Memoria temporanea ===
partite_per_data = defaultdict(list)
partite_lookup = {}

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot attivo con webhook su Render!")

# === /partite ===
async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("partite.csv", newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            partite_per_data.clear()
            partite_lookup.clear()
            for i, riga in enumerate(reader, start=1):
                partita = {
                    "id": i,
                    "ora": riga["Ora"],
                    "s1": riga["Squadra1"],
                    "s2": riga["Squadra2"],
                    "stadio": riga["Stadio"]
                }
                partite_per_data[riga["Data"].strip()].append(partita)
                partite_lookup[str(i)] = partita

        keyboard = [
            [InlineKeyboardButton(data, callback_data=f"data:{data}")]
            for data in partite_per_data
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📅 Seleziona una data:", reply_markup=reply_markup)

    except Exception as e:
        print("❌ Errore in /partite:", e)
        await update.message.reply_text("Errore nella lettura delle partite.")

# === Gestione scelta data ===
async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.split(":")[1]

    partite = partite_per_data[selected_date]
    keyboard = []

    for partita in partite:
        desc = f"{partita['ora']} - {partita['s1']} vs {partita['s2']} ({partita['stadio']})"
        keyboard.append([InlineKeyboardButton(desc, callback_data=f"match:{partita['id']}")])

    await query.edit_message_text(
        text=f"📆 Partite del {selected_date}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Webhook handler ===
async def handle_webhook(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

# === Server + Webhook Setup ===
async def run():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    # Imposta webhook automaticamente
    await application.bot.set_webhook(url=WEBHOOK_URL)
    print("🌐 Webhook impostato automaticamente:", WEBHOOK_URL)

    await application.initialize()
    await application.start()
    await application.updater.idle()

# === Handlers ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CallbackQueryHandler(handle_date_selection, pattern=r"^data:.*"))

# === Avvio ===
if __name__ == "__main__":
    import asyncio
    asyncio.run(run())

