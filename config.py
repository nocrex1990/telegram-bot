
import os
from telegram.ext import ApplicationBuilder

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH
PORT = int(os.environ.get("PORT", 10000))
application = ApplicationBuilder().token(TOKEN).build()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOMMESSE_PATH = os.path.join(BASE_DIR, "scommesse.csv")
GOOGLE_SHEET_NAME = "Scommesse Mondiale Club FIFA 2025"
