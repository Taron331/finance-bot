import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "Finance")

# --- 1. Легкий HTTP-сервер для Health Check на Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаем фоновый поток сервера сразу при старте файла
threading.Thread(target=start_health_check_server, daemon=True).start()


# --- 2. Функция подключения к Google Таблице из файла creds.json ---
def get_sheet():
    try:
        if not os.path.exists("creds.json"):
            return None, "Файл creds.json не найден. Загрузите его на Render в Secret Files или в репозиторий GitHub."

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        gc = gspread.service_account(filename="creds.json", scopes=scopes)
        sheet = gc.open(SPREADSHEET_NAME).sheet1
        return sheet, None

    except Exception as e:
        err_msg = f"Ошибка подключения к Таблице: {e}"
        logging.error(err_msg)
        return None, err_msg


# --- 3. Обработчики команд Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и готов к работе!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Отчет по месяцам":
        sheet, error = get_sheet()
        if error:
            await update.message.reply_text(f"⚠️ {error}")
            return
        try:
            records = sheet.get_all_records()
            await update.message.reply_text(f"Успешно получено записей: {len(records)}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при чтении данных: {e}")


# --- 4. Точка входа ---
def main():
    if not BOT_TOKEN:
        print("ОШИБКА: Переменная TELEGRAM_BOT_TOKEN не задана в Environment Variables!")
        return

    # Явная инициализация event loop для стабильной работы на Render
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN.strip()).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот успешно запущен и слушаeт сообщения...")
    application.run_polling(close_loop=False)


if __name__ == '__main__':
    main()
