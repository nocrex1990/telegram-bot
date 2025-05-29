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
        import traceback
        traceback.print_exc()
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

async def handle_modifica_selezione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partita_id = query.data.split(":")[1]
    context.user_data["modifica"] = True
    context.user_data["partita_id"] = partita_id

    buttons = [
        [InlineKeyboardButton("1", callback_data="modifica_esito:1")],
        [InlineKeyboardButton("X", callback_data="modifica_esito:X")],
        [InlineKeyboardButton("2", callback_data="modifica_esito:2")]
    ]
    await query.edit_message_text("✏️ Seleziona il nuovo esito:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_modifica_esito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    esito = query.data.split(":")[1]
    context.user_data["esito"] = esito
    await query.edit_message_text("Scrivi il nuovo risultato esatto (es. 2-1):")

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

    await update.message.reply_text(f"✅ {'Modifica' if context.user_data.get('modifica') else 'Scommessa'} registrata per {partita['s1']} vs {partita['s2']}")
    context.user_data.clear()

# ... (resto invariato)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("info", info))
application.add_handler(CommandHandler("partite", partite))
application.add_handler(CommandHandler("modifica", modifica))
application.add_handler(CommandHandler("riepilogo", riepilogo))
application.add_handler(CallbackQueryHandler(handle_modifica_selezione, pattern=r"^modifica:.*"))
application.add_handler(CallbackQueryHandler(handle_modifica_esito, pattern=r"^modifica_esito:.*"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_risultato))
