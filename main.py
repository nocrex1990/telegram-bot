
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import os
import csv
from aiohttp import web
from collections import defaultdict
import asyncio

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = "https://telegram-bot-rexx.onrender.com"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

application = ApplicationBuilder().token(TOKEN).build()

partite_per_data = defaultdict(list)
partite_lookup = {}
scommesse_utente = defaultdict(dict)

if os.path.exists("scommesse.csv"):
    with open("scommesse.csv", newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            scommesse_utente[row["user_id"]][row["partita_id"]] = row

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot attivo con webhook su Render!")

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("partite.csv", newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            partite_per_data.clear()
            partite_lookup.clear()
            for i, riga in enumerate(reader, start=1):
                partita = {
                    "id": str(i),
                    "ora": riga["Ora"],
                    "s1": riga["Squadra1"],
                    "s2": riga["Squadra2"],
                    "stadio": riga["Stadio"]
                }
                partite_per_data[riga["Data"].strip()].append(partita)
                partite_lookup[str(i)] = partita

        user_id = str(update.effective_user.id)

        keyboard = []
        for data in partite_per_data:
            disponibili = any(p["id"] not in scommesse_utente[user_id] for p in partite_per_data[data])
            if disponibili:
                keyboard.append([InlineKeyboardButton(data, callback_data=f"data:{data}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📅 Seleziona una data:", reply_markup=reply_markup)
    except Exception as e:
        print("❌ Errore in /partite:", e)
        await update.message.reply_text("Errore nella lettura delle partite.")

async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.split(":")[1]
    user_id = str(query.from_user.id)
    partite = partite_per_data[selected_date]
    keyboard = []
    for partita in partite:
        if partita["id"] in scommesse_utente[user_id]:
            continue
        desc = f"{partita['ora']} - {partita['s1']} vs {partita['s2']} ({partita['stadio']})"
        keyboard.append([InlineKeyboardButton(desc, callback_data=f"match:{partita['id']}")])
    await query.edit_message_text(text=f"📆 Partite del {selected_date}:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_match_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data.split(":")[1]
    context.user_data["partita_id"] = partita_id
    buttons = [[InlineKeyboardButton("1", callback_data="esito:1")],
               [InlineKeyboardButton("X", callback_data="esito:X")],
               [InlineKeyboardButton("2", callback_data="esito:2")]]
    await query.edit_message_text("Scegli l'esito della partita:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_esito_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    esito = query.data.split(":")[1]
    context.user_data["esito"] = esito
    await query.edit_message_text("Scrivi il risultato esatto (es. 2-1):")

async def handle_risultato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    risultato = update.message.text.strip()
    if "-" not in risultato:
        await update.message.reply_text("Formato non valido. Usa es: 2-1")
        return
    try:
        g1, g2 = map(int, risultato.split("-"))
    except:
        await update.message.reply_text("Numeri non validi.")
        return
    esito = context.user_data.get("esito")
    if (esito == "1" and g1 <= g2) or (esito == "2" and g2 <= g1) or (esito == "X" and g1 != g2):
        await update.message.reply_text("❌ Il risultato non è coerente con l'esito scelto.")
        return
    partita_id = context.user_data.get("partita_id")
    user_id = str(update.effective_user.id)
    partita = partite_lookup.get(partita_id)
    scommesse_utente[user_id][partita_id] = {
        "user_id": user_id,
        "partita_id": partita_id,
        "esito": esito,
        "risultato": risultato,
        "desc": f"{partita['s1']} vs {partita['s2']}"
    }
    with open("scommesse.csv", "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "partita_id", "esito", "risultato", "desc"])
        writer.writeheader()
        for uid in scommesse_utente:
            for sid in scommesse_utente[uid]:
                writer.writerow(scommesse_utente[uid][sid])
    await update.message.reply_text(f"✅ Scommessa registrata per {partita['s1']} vs {partita['s2']}")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CallbackQueryHandler(handle_date_selection, pattern=r"^data:.*"))
application.add_handler(CallbackQueryHandler(handle_match_selection, pattern=r"^match:.*"))
application.add_handler(CallbackQueryHandler(handle_esito_selection, pattern=r"^esito:.*"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_risultato))

async def handle_webhook(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="ok")

async def run():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", lambda request: web.Response(text="Bot attivo su Render"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()
    await application.initialize()
    await application.start()
    info = await application.bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook impostato su {WEBHOOK_URL}")
    await application.updater.wait()

if __name__ == "__main__":
    asyncio.run(run())
