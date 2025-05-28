from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import json
import csv
from aiohttp import web

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

application = ApplicationBuilder().token(TOKEN).build()

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        username = update.effective_user.username or update.effective_user.first_name or "utente"
        print(f"✅ /start ricevuto da: {username}")
        await update.message.reply_text("✅ Bot attivo con webhook su Render!")
    except Exception as e:
        print("❌ Errore in /start:", e)
        await update.message.reply_text("⚠️ Errore durante l'avvio del bot.")

# === /partite ===
async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("partite.csv", newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            messaggi = []
            for riga in reader:
                partita = f"📅 {riga['Data']} 🕒 {riga['Ora']}\n⚽ {riga['Squadra1']} vs {riga['Squadra2']} 🏟 {riga['Stadio']}"
                messaggi.append(partita)
            messaggio_finale = "\n\n".join(messaggi)
            await update.message.reply_text(messaggio_finale or "Nessuna partita trovata.")
    except Exception as e:
        print("❌ Errore in /partite:", e)
        await update.message.reply_text("⚠️ Errore nella lettura delle partite.")

# === Registrazione handler ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("partite", partite))

# === Webhook handler ===
async def handle_webhook(request):
    print("📩 Richiesta ricevuta da Telegram!")
    data = await request.json()
    print(json.dumps(data, indent=2))
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

# === Aiohttp Server ===
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
