from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import json
from aiohttp import web

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

application = ApplicationBuilder().token(TOKEN).build()

# ✅ Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("✅ /start ricevuto da:", update.effective_user.username)
    await update.message.reply_text("✅ Bot ti ha ricevuto di nuovo!")

application.add_handler(CommandHandler("start", start))

# ✅ Webhook handler
async def handle_webhook(request):
    print("📩 Richiesta ricevuta da Telegram!")
    data = await request.json()
    print(json.dumps(data, indent=2))
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

# ✅ Server aiohttp
async def run():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render (GET)"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    print(f"🌐 Webhook attivo su: {WEBHOOK_URL}")
    await application.bot.set_webhook(url=WEBHOOK_URL)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
