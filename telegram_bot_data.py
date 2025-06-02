
import csv
import os
from collections import defaultdict
from config import SCOMMESSE_PATH

partite_per_data = defaultdict(list)
partite_lookup = {}
scommesse_utente = defaultdict(dict)

def load_scommesse_da_csv():
    if os.path.exists(SCOMMESSE_PATH):
        with open(SCOMMESSE_PATH, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                scommesse_utente[row["user_id"]][row["partita_id"]] = row

def salva_scommessa_locale(riga):
    with open(SCOMMESSE_PATH, "a", newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["user_id", "nome_utente", "partita_id", "esito", "risultato", "desc"])
        writer.writerow(riga)
