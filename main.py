import logging
import json
import datetime
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import gspread
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8926455676:AAEmvLB7-D68aFIlK982bnMVeofTiA4gI0Y"
WEBAPP_URL = "https://taron331.github.io/finance-bot/"
CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Контроль финансов"  # Название вашей Google Таблицы

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- ФОНОВЫЙ HTTP-СЕРВЕР ДЛЯ RENDER (обязателен для Web Service) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаем сервер в фоновом режиме перед стартом бота
threading.Thread(target=start_health_check_server, daemon=True).start()
# -----------------------------------------------------------------

# Функция подключения к Google Таблице с пересозданием сессии
def get_sheet():
    try:
        # Проверяем, существует ли файл перед подключением
        if not os.path.exists(CREDENTIALS_FILE):
            return None, f"Файл {CREDENTIALS_FILE} не найден в директории проекта!"
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        return gc.open(SPREADSHEET_NAME).sheet1, None
    except Exception as e:
        logging.error(f"Ошибка подключения к Google Таблице: {e}")
        return None, str(e)

# Постоянная Reply-клавиатура внизу экрана
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("➕ Добавить транзакцию", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("📊 Отчет по месяцам"), KeyboardButton("🗑 Удалить последнюю запись")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Пользователь"
    await update.message.reply_text(
        f"Привет, {user_name}!\n\n"
        "• Записывайте расходы и доходы через меню ниже.\n"
        "• Для отчета за конкретный период отправьте команду:\n"
        "<code>/report 01.08.2026 - 15.08.2026</code>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_raw = update.effective_message.web_app_data.data
    user = update.effective_user
    user_display = user.first_name or user.username or f"ID: {user.id}"

    try:
        data = json.loads(data_raw)
        trans_type = data.get("type", "Расход")
        amount = float(data.get("amount", 0))
        category = data.get("category", "Без категории")
        account = data.get("account", "Карта")

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")

        sheet, err_msg = get_sheet()
        if sheet:
            # Записываем с колонкой "Пользователь" (Столбец F)
            sheet.append_row([date_str, trans_type, category, amount, account, user_display])
            saved_status = "✅ Сохранено в Google Таблицу!"
        else:
            saved_status = f"⚠️ Ошибка доступа к Таблице:\n<code>{err_msg}</code>"

        icon = "🔴" if trans_type == "Расход" else "🟢"

        message = (
            f"{icon} <b>Успешно записано!</b>\n\n"
            f"<b>Автор:</b> {user_display}\n"
            f"<b>Тип:</b> {trans_type}\n"
            f"<b>Сумма:</b> {amount:.2f} €\n"
            f"<b>Категория:</b> {category}\n"
            f"<b>Счет:</b> {account}\n\n"
            f"{saved_status}"
        )

        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке данных: {e}", reply_markup=get_main_keyboard())

async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet, err_msg = get_sheet()
    if not sheet:
        await update.message.reply_text(f"⚠️ Ошибка подключения к Таблице:\n<code>{err_msg}</code>", parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    records = sheet.get_all_values()
    if len(records) <= 1:
        await update.message.reply_text("ℹ️ В таблице пока нет сохраненных транзакций.", reply_markup=get_main_keyboard())
        return

    summary = {}
    for row in records[1:]:
        if len(row) < 4:
            continue
        try:
            date_part = row[0].split(" ")[0]
            month_key = date_part[:7]
            trans_type = row[1]
            amount = float(row[3].replace(',', '.'))
            user_name = row[5] if len(row) > 5 and row[5] else "Неизвестный"

            if month_key not in summary:
                summary[month_key] = {"total_exp": 0.0, "total_inc": 0.0, "users": {}}

            if user_name not in summary[month_key]["users"]:
                summary[month_key]["users"][user_name] = {"Расход": 0.0, "Доход": 0.0}

            if trans_type == "Расход":
                summary[month_key]["total_exp"] += amount
                summary[month_key]["users"][user_name]["Расход"] += amount
            elif trans_type == "Доход":
                summary[month_key]["total_inc"] += amount
                summary[month_key]["users"][user_name]["Доход"] += amount

        except ValueError:
            continue

    if not summary:
        await update.message.reply_text("ℹ️ Нет корректных данных для отчета.", reply_markup=get_main_keyboard())
        return

    text = "📊 <b>Семейный отчет по месяцам:</b>\n\n"
    for month in sorted(summary.keys(), reverse=True):
        m_data = summary[month]
        total_exp = m_data["total_exp"]
        total_inc = m_data["total_inc"]
        balance = total_inc - total_exp

        text += (
            f"📅 <b>Месяц: {month}</b>\n"
            f"  🟢 Общий доход: <code>{total_inc:.2f} €</code>\n"
            f"  🔴 Общий расход: <code>{total_exp:.2f} €</code>\n"
            f"  ⚖️ Общий баланс: <code>{balance:+.2f} €</code>\n"
            f"  ─────────────────────────\n"
            f"  <b>Личные балансы:</b>\n"
        )

        for u_name, u_stats in m_data["users"].items():
            exp = u_stats["Расход"]
            inc = u_stats["Доход"]
            user_balance = inc - exp
            text += (
                f"  👤 <b>{u_name}:</b>\n"
                f"     • Заработал(а): 🟢 +{inc:.2f} €\n"
                f"     • Потратил(а): 🔴 -{exp:.2f} €\n"
                f"     • <b>Личный баланс: {user_balance:+.2f} €</b>\n"
            )

        text += "\n"

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())

async def custom_date_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "ℹ️ <b>Формат вызова отчета за период:</b>\n"
            "<code>/report 01.08.2026 - 15.08.2026</code>\n\n"
            "Или за один день:\n"
            "<code>/report 01.08.2026</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return

    raw_input = " ".join(args)
    dates = raw_input.replace(" ", "").split("-")
    
    try:
        start_date = datetime.datetime.strptime(dates[0], "%d.%m.%Y").date()
        if len(dates) > 1:
            end_date = datetime.datetime.strptime(dates[1], "%d.%m.%Y").date()
        else:
            end_date = start_date
    except ValueError:
        await update.message.reply_text("⚠️ Ошибка формата даты. Используйте формат: <code>ДД.ММ.ГГГГ</code> (например, <code>01.08.2026</code>)", parse_mode="HTML")
        return

    sheet, err_msg = get_sheet()
    if not sheet:
        await update.message.reply_text(f"⚠️ Ошибка доступа к Таблице:\n<code>{err_msg}</code>", parse_mode="HTML")
        return

    records = sheet.get_all_values()
    if len(records) <= 1:
        await update.message.reply_text("ℹ️ В таблице нет данных.", reply_markup=get_main_keyboard())
        return

    total_exp = 0.0
    total_inc = 0.0
    users_data = {}

    for row in records[1:]:
        if len(row) < 4:
            continue
        try:
            row_date_str = row[0].split(" ")[0]
            row_date = datetime.datetime.strptime(row_date_str, "%Y-%m-%d").date()

            if start_date <= row_date <= end_date:
                trans_type = row[1]
                amount = float(row[3].replace(',', '.'))
                user_name = row[5] if len(row) > 5 and row[5] else "Неизвестный"

                if user_name not in users_data:
                    users_data[user_name] = {"Расход": 0.0, "Доход": 0.0}

                if trans_type == "Расход":
                    total_exp += amount
                    users_data[user_name]["Расход"] += amount
                elif trans_type == "Доход":
                    total_inc += amount
                    users_data[user_name]["Доход"] += amount

        except ValueError:
            continue

    if not users_data:
        await update.message.reply_text(f"ℹ️ За период с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} записей не найдено.", reply_markup=get_main_keyboard())
        return

    balance = total_inc - total_exp
    text = (
        f"📅 <b>Отчет за период: {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"🟢 Общий доход: <code>{total_inc:.2f} €</code>\n"
        f"🔴 Общий расход: <code>{total_exp:.2f} €</code>\n"
        f"⚖️ Общий баланс: <code>{balance:+.2f} €</code>\n"
        f"─────────────────────────\n"
        f"<b>Личные балансы за период:</b>\n"
    )

    for u_name, u_stats in users_data.items():
        exp = u_stats["Расход"]
        inc = u_stats["Доход"]
        u_bal = inc - exp
        text += (
            f"👤 <b>{u_name}:</b>\n"
            f"   • Доход: 🟢 +{inc:.2f} € | Расход: 🔴 -{exp:.2f} €\n"
            f"   • <b>Личный баланс: {u_bal:+.2f} €</b>\n"
        )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())

async def delete_last_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet, err_msg = get_sheet()
    if not sheet:
        await update.message.reply_text(f"⚠️ Ошибка подключения к Таблице:\n<code>{err_msg}</code>", parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    records = sheet.get_all_values()
    if len(records) <= 1:
        await update.message.reply_text("ℹ️ В таблице нет транзакций для удаления.", reply_markup=get_main_keyboard())
        return

    last_row_index = len(records)
    last_row_data = records[-1]

    sheet.delete_rows(last_row_index)

    date_str = last_row_data[0] if len(last_row_data) > 0 else ""
    trans_type = last_row_data[1] if len(last_row_data) > 1 else ""
    category = last_row_data[2] if len(last_row_data) > 2 else ""
    amount = last_row_data[3] if len(last_row_data) > 3 else ""
    user_name = last_row_data[5] if len(last_row_data) > 5 else "Неизвестный"

    msg = (
        f"🗑 <b>Удалена последняя запись:</b>\n\n"
        f"<b>Автор:</b> {user_name}\n"
        f"<b>Дата:</b> {date_str}\n"
        f"<b>Тип:</b> {trans_type}\n"
        f"<b>Категория:</b> {category}\n"
        f"<b>Сумма:</b> {amount} €"
    )

    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_main_keyboard())

def main():
    import asyncio

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", custom_date_report))
    app.add_handler(MessageHandler(filters.Regex("^📊 Отчет по месяцам$"), monthly_report))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Удалить последнюю запись$"), delete_last_entry))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    print("Бот успешно запущен...")
    
    # Принудительно создаем и устанавливаем event loop для Python 3.14+
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app.run_polling(bootstrap_retries=-1, timeout=30)
if __name__ == '__main__':
    main()
