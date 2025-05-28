from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from flask import Flask, request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = "/webhook/" + TOKEN
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

app = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    print("👉 Richiesta ricevuta da Telegram!")
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

@app.route("/", methods=["GET"])
def index():
    return "Bot Telegram attivo con webhook!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot attivo con webhook su Render!")

def setup():
    application.add_handler(CommandHandler("start", start))
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    setup()

