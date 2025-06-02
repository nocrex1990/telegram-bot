
import os
import logging
import gspread
from google.oauth2.service_account import Credentials
from config import BASE_DIR, GOOGLE_SHEET_NAME

def get_google_sheet():
    try:
        credentials = Credentials.from_service_account_file(
            os.path.join(BASE_DIR, "google-credentials.json"),
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(credentials)
        return client.open(GOOGLE_SHEET_NAME).sheet1
    except Exception as e:
        logging.error(f"❌ Errore nell'accesso a Google Sheet: {e}")
        return None

def scrivi_su_google_sheet(sheet, riga):
    try:
        if not sheet.get_all_values():
            header = ["user_id", "nome_utente", "partita_id", "esito", "risultato", "desc"]
            sheet.append_row(header)
        sheet.append_row(riga)
    except Exception as e:
        logging.error(f"❌ Errore scrittura Google Sheets: {e}")
