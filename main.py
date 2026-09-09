import os
import json
from google.oauth2.service_account import Credentials

def get_sheet():
    try:
        creds_raw = os.environ.get("GOOGLE_CREDS")
        source = "Переменная GOOGLE_CREDS"
        
        if not creds_raw:
            source = f"Файл {CREDENTIALS_FILE}"
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                creds_raw = f.read()

        creds_data = json.loads(creds_raw)

        pk = creds_data.get("private_key", "")
        # Проверяем, есть ли реальные переносы строк
        has_real_newlines = "\n" in pk and "\\n" not in pk
        email = creds_data.get("client_email", "не найден")

        # Если ключи кривые, мы увидим это в ошибке
        if "private_key" in creds_data:
            creds_data["private_key"] = creds_data["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
        gc = gspread.authorize(credentials)
        sheet = gc.open(SPREADSHEET_NAME).sheet1
        return sheet, None
    except Exception as e:
        debug_info = (
            f"❌ Ошибка: {e}\n"
            f"📍 Источник: {source}\n"
            f"📧 Email: {email}\n"
            f"🔑 Длина ключа: {len(pk)}\n"
            f"↵ Настоящие переносы: {has_real_newlines}"
        )
        logging.error(debug_info)
        return None, debug_info
