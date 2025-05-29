from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import os
import csv
from aiohttp import web
from collections import defaultdict

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

application = ApplicationBuilder().token(TOKEN).build()

# === Memoria ===
partite_per_data = defaultdict(list)
partite_lookup = {}
scommesse_utente = {}  # user_id -> {"partita_id": int, "esito": str}

SCOMMESSE_FILE = "scommesse.csv"

# === Utility ===
def carica_scommesse():
    if not os.path.exists(SCOMMESSE_FILE):
        return
    with open(SCOMMESSE_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            scommesse_utente[(int(row["utente_id"]), int(row["partita_id"]))] = {
                "esito": row["esito"],
                "risultato": row["risultato_esatto"]
            }

def salva_scommessa(user_id, username, partita_id, esito, risultato):
    nuova = not os.path.exists(SCOMMESSE_FILE)
    with open(SCOMMESSE_FILE, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if nuova:
            writer.writerow(["utente_id", "nome_utente", "partita_id", "esito", "risultato_esatto"])
        writer.writerow([user_id, username, partita_id, esito, risultato])
    scommesse_utente[(user_id, partita_id)] = {"esito": esito, "risultato": risultato}

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
                    "stadio": riga["Stadio"],
                    "data": riga["Data"].strip()
                }
                partite_per_data[partita["data"]].append(partita)
                partite_lookup[str(i)] = partita

        user_id = update.message.from_user.id
        keyboard = []
        for data, partite in partite_per_data.items():
            visibili = any((user_id, p["id"]) not in scommesse_utente for p in partite)
            if visibili:
                keyboard.append([InlineKeyboardButton(data, callback_data=f"data:{data}")])

        if keyboard:
            await update.message.reply_text("📅 Seleziona una data:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Hai già scommesso su tutte le partite!")

    except Exception as e:
        print("❌ Errore in /partite:", e)
        await update.message.reply_text("Errore nella lettura delle partite.")

# === Scelta data ===
async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.split(":")[1]
    user_id = query.from_user.id

    keyboard = []
    for partita in partite_per_data[selected_date]:
        if (user_id, partita["id"]) not in scommesse_utente:
            desc = f"{partita['ora']} - {partita['s1']} vs {partita['s2']} ({partita['stadio']})"
            keyboard.append([InlineKeyboardButton(desc, callback_data=f"match:{partita['id']}")])

    if keyboard:
        await query.edit_message_text(
            text=f"📆 Partite del {selected_date}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text("Hai già scommesso su tutte le partite di questa giornata!")

# === Scelta partita ===
async def handle_match_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data.split(":")[1]
    user_id = query.from_user.id

    context.user_data["partita_id"] = partita_id
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"esito:{partita_id}:1"),
         InlineKeyboardButton("X", callback_data=f"esito:{partita_id}:X"),
         InlineKeyboardButton("2", callback_data=f"esito:{partita_id}:2")]
    ]
    await query.edit_message_text("Scegli l'esito della partita:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Scelta esito ===
async def handle_esito_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, partita_id, esito = query.data.split(":")
    context.user_data["esito"] = esito
    await query.edit_message_text("Scrivi il risultato esatto (es. 2-1):")

# === Ricezione risultato esatto ===
async def handle_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "anonimo"
    partita_id = int(context.user_data.get("partita_id", 0))
    esito = context.user_data.get("esito")
    risultato = update.message.text.strip()

    if not partita_id or not esito:
        return

    try:
        g1, g2 = map(int, risultato.split("-"))
    except:
        await update.message.reply_text("❌ Formato risultato non valido. Usa '2-1', '1-1', ecc.")
        return

    # Validazione esito
    if (esito == "1" and g1 <= g2) or (esito == "2" and g2 <= g1) or (esito == "X" and g1 != g2):
        await update.message.reply_text("❌ Il risultato non è coerente con l'esito scelto.")
        return

    salva_scommessa(user_id, username, partita_id, esito, risultato)
    await update.message.reply_text("✅ Scommessa registrata con successo!")

# === Handlers ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CallbackQueryHandler(handle_date_selection, pattern=r"^data:.*"))
application.add_handler(CallbackQueryHandler(handle_match_selection, pattern=r"^match:.*"))
application.add_handler(CallbackQueryHandler(handle_esito_selection, pattern=r"^esito:.*"))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_result_input))

# === Webhook ===
async def handle_webhook(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

async def run():
    carica_scommesse()
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    await application.bot.set_webhook(url=WEBHOOK_URL)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
