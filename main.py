import os
import time
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- 1. ФИКС ЧАСОВ ДЛЯ GOOGLE AUTH ---
# Корректируем системное время на 20 секунд назад, чтобы Google
# не отвергал JWT-подпись из-за рассинхронизации часов Render.
_original_time = time.time
time.time = lambda: _original_time() - 20

import gspread
from google.oauth2 import service_account
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "Finance")


# --- 2. HTTP-Сервер для поддержания активности на Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()


# --- 3. Авторизация в Google Таблице через файл creds.json ---
def get_sheet():
    try:
        if not os.path.exists("creds.json"):
            return None, "Ошибка: Файл creds.json не найден в корне проекта!"

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        credentials = service_account.Credentials.from_service_account_file(
            "creds.json",
            scopes=scopes
        )

        gc = gspread.authorize(credentials)
        sheet = gc.open(SPREADSHEET_NAME).sheet1
        return sheet, None

    except Exception as e:
        err_msg = f"Ошибка подключения к Таблице: {e}"
        logging.error(err_msg)
        return None, err_msg


# --- 4. Обработка команд Telegram ---
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


# --- 5. Главный цикл ---
def main():
    if not BOT_TOKEN:
        print("ОШИБКА: TELEGRAM_BOT_TOKEN не задан в Environment Variables!")
        return

    # Задаем Event Loop для Python 3.10+
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN.strip()).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот успешно запущен...")
    application.run_polling(close_loop=False)


if __name__ == '__main__':
    main()
