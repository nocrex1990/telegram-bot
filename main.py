from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import os
import csv
from aiohttp import web
from collections import defaultdict
import asyncio
from datetime import datetime

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
    await update.message.reply_text("""👋 Benvenuto nel bot del Mondiale per Club 2025!

Con questo bot puoi inserire una scommessa per ogni partita (esito + risultato esatto) e modificarla fino all'inizio dell'incontro. A fine torneo verranno confrontate tutte le scommesse!

Comandi disponibili:

📅 /partite – Visualizza le partite e inserisci la tua scommessa
✏️ /modifica – Modifica una scommessa già inserita
📊 /riepilogo – Mostra le tue scommesse già registrate
ℹ️ /info – Dettagli sulla competizione e il regolamento

📌 Regole rapide:
- Una scommessa per partita
- Risultato esatto coerente con l’esito
- Modifiche permesse fino all’inizio della partita

🔁 Usa /start in qualsiasi momento per rivedere questo messaggio.""")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
ℹ️ Dettagli sulla competizione:

🏆 Il Mondiale per Club FIFA 2025 si terrà negli Stati Uniti dal 15 giugno al 13 luglio.

📍 Parteciperanno 32 squadre da tutto il mondo, in un formato simile alla Coppa del Mondo FIFA.

🔢 Il torneo sarà diviso in fasi a gironi e a eliminazione diretta.

⚠️ Con questo bot puoi inserire scommesse per ciascuna partita (esito + risultato esatto) e modificarle fino al fischio d’inizio.

Le scommesse saranno salvate e confrontate a fine torneo. Che vinca il più preciso!
""")

async def riepilogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    scommesse = scommesse_utente.get(user_id, {})
    if not scommesse:
        await update.message.reply_text("Non hai ancora inserito nessuna scommessa.")
        return

    messaggi = ["📊 Le tue scommesse registrate:"]
    for s in scommesse.values():
        messaggi.append(f"- {s['desc']}: {s['esito']} ({s['risultato']})")

    await update.message.reply_text("\n".join(messaggi))

async def partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("partite.csv", newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            partite_per_data.clear()
            partite_lookup.clear()
            for i, riga in enumerate(reader, start=1):
                partita = {
                    "id": str(i),
                    "data": riga["Data"].strip(),
                    "ora": riga["Ora"].strip(),
                    "s1": riga["Squadra1"].strip(),
                    "s2": riga["Squadra2"].strip(),
                    "stadio": riga["Stadio"].strip()
                }
                partite_per_data[partita["data"]].append(partita)
                partite_lookup[str(i)] = partita

        user_id = str(update.effective_user.id)
        keyboard = []
        now = datetime.now()

        for data in partite_per_data:
            disponibili = any(
                p["id"] not in scommesse_utente[user_id] and
                datetime.strptime(f"{p['data']} {p['ora']}", "%Y-%m-%d %H:%M") > now
                for p in partite_per_data[data]
            )
            if disponibili:
                keyboard.append([InlineKeyboardButton(data, callback_data=f"data:{data}")])

        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📅 Seleziona una data:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("✅ Nessuna partita disponibile al momento per essere scommessa.")

    except Exception as e:
        print("❌ Errore in /partite:", e)
        await update.message.reply_text("Errore nella lettura delle partite.")

async def modifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    now = datetime.now()
    partite_scommesse = scommesse_utente.get(user_id, {})

    keyboard = []
    for pid, scommessa in partite_scommesse.items():
        partita = partite_lookup.get(pid)
        if not partita:
            continue
        data_ora = datetime.strptime(f"{partita['data']} {partita['ora']}", "%Y-%m-%d %H:%M")
        if data_ora > now:
            desc = f"{partita['s1']} vs {partita['s2']} ({partita['ora']})"
            keyboard.append([InlineKeyboardButton(desc, callback_data=f"modifica:{pid}")])

    if not keyboard:
        await update.message.reply_text("Non hai scommesse modificabili al momento.")
    else:
        await update.message.reply_text("✏️ Seleziona una scommessa da modificare:", reply_markup=InlineKeyboardMarkup(keyboard))

# ... (resto invariato)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("info", info))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CommandHandler("modifica", modifica))
application.add_handler(CommandHandler("riepilogo", riepilogo))
application.add_handler(CallbackQueryHandler(handle_modifica_selezione, pattern=r"^modifica:.*"))
application.add_handler(CallbackQueryHandler(handle_modifica_esito, pattern=r"^modifica_esito:.*"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_risultato))
