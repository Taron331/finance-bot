import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials
import google.auth.transport.requests

def get_sheet():
    try:
        creds_raw = os.environ.get("GOOGLE_CREDS")
        if not creds_raw:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                creds_raw = f.read()

        creds_data = json.loads(creds_raw)

        # Преобразование экранированных символов переноса строки
        if "private_key" in creds_data:
            pk = creds_data["private_key"]
            pk = pk.replace("\\\\n", "\n").replace("\\n", "\n")
            creds_data["private_key"] = pk

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
        
        # Принудительное обновление токена с синхронизацией
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        gc = gspread.authorize(credentials)
        sheet = gc.open(SPREADSHEET_NAME).sheet1
        return sheet, None
    except Exception as e:
        err_msg = f"ОШИБКА ДЕТЕКТА КЛЮЧА: {e}"
        logging.error(err_msg)
        return None, err_msg


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и готов к работе!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Отчет по месяцам":
        sheet, error = get_sheet()
        if error:
            await update.message.reply_text(f"⚠️ Ошибка подключения к Таблице:\n{error}")
            return
        try:
            records = sheet.get_all_records()
            await update.message.reply_text(f"Успешно получено записей: {len(records)}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при чтении данных: {e}")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", BOT_TOKEN).strip().strip('"').strip("'")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот успешно запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()
