
import os
import sys
import logging
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder
from handlers import setup_handlers
from config import TOKEN, WEBHOOK_PATH, WEBHOOK_URL, PORT, BASE_URL, application

# === LOGGING: File + Console per Render ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

async def handle_webhook(request):
    try:
        data = await request.json()
        logging.info(f"📨 Update ricevuto: {data}")
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="ok")
    except Exception as e:
        logging.error(f"❌ Errore nel webhook: {e}")
        return web.Response(status=500, text="Errore interno")

async def mostra_log(request):
    try:
        with open("bot.log", "r", encoding="utf-8") as f:
            contenuto = f.read()
        return web.Response(text=contenuto, content_type='text/plain')
    except Exception as e:
        return web.Response(text=f"Errore nel leggere il log: {e}", status=500)

async def run():
    from telegram_bot_data import load_scommesse_da_csv
    load_scommesse_da_csv()

    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render"))
    app.router.add_get("/log", mostra_log)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    await application.initialize()
    await application.start()
    setup_handlers()

    info = await application.bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)

    logging.info(f"🌐 Webhook finale: {WEBHOOK_URL}")
    logging.info("🚀 Bot e server aiohttp avviati correttamente")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(run())
