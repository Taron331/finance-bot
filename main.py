import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "Finance")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()


def get_sheet():
    try:
        creds_raw = os.environ.get("GOOGLE_CREDS")
        if not creds_raw:
            return None, "Переменная GOOGLE_CREDS не найдена в Railway Variables"

        creds_data = json.loads(creds_raw)

        if "private_key" in creds_data:
            creds_data["private_key"] = creds_data["private_key"].replace("\\n", "\n")

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
        gc = gspread.authorize(credentials)
        sheet = gc.open(SPREADSHEET_NAME).sheet1
        return sheet, None
    except Exception as e:
        logging.error(f"Ошибка подключения: {e}")
        return None, str(e)


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
