import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(asctime)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "Finance")
CREDENTIALS_FILE = "credentials.json"

# Заглушка HTTP-сервера для Railway (чтобы сервис не падал по Healthcheck)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Запуск HTTP сервера в фоновом потоке
threading.Thread(target=run_dummy_server, daemon=True).start()


def get_sheet():
    """Подключение к Google Таблице с поддержкой переменной GOOGLE_CREDS и файла credentials.json"""
    try:
        creds_json = os.environ.get("GOOGLE_CREDS")
        if creds_json:
            creds_data = json.loads(creds_json)
        else:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                creds_data = json.load(f)

        # Исправляем формат приватного ключа RSA
        if "private_key" in creds_data:
            creds_data["private_key"] = creds_data["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")

        gc = gspread.service_account_from_dict(creds_data)
        sheet = gc.open(SPREADSHEET_NAME).sheet1
        return sheet, None
    except Exception as e:
        logging.error(f"Ошибка подключения к Google Таблице: {e}")
        return None, str(e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и готов к работе!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet, error = get_sheet()
    if error:
        await update.message.reply_text(f"⚠️ Ошибка подключения к Таблице:\n{error}")
        return

    text = update.message.text
    # Здесь логика обработки сообщений/кнопок
    if text == "📊 Отчет по месяцам":
        try:
            records = sheet.get_all_records()
            await update.message.reply_text(f"Успешно получено записей из таблицы: {len(records)}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при чтении данных: {e}")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот успешно запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()
