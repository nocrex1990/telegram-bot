from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = "/webhook/" + TOKEN
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

application = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("✅ Comando /start ricevuto!")
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
