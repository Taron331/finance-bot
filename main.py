import logging
import json
import datetime
import gspread
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8926455676:AAEmvLB7-D68aFIlK982bnMVeofTiA4gI0Y"
WEBAPP_URL = "https://taron331.github.io/finance-bot/"
CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Учет финансов"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_sheet():
    try:
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        return gc.open(SPREADSHEET_NAME).sheet1
    except Exception as e:
        logging.error(f"Ошибка подключения к Google Таблице: {e}")
        return None

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("➕ Добавить транзакцию", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("📊 Отчет по месяцам"), KeyboardButton("🗑 Удалить последнюю запись")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Пользователь"
    await update.message.reply_text(
        f"Привет, {user_name}! Записывайте расходы и доходы через меню ниже:",
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

        sheet = get_sheet()
        if sheet:
            # Записываем с колонкой "Пользователь"
            sheet.append_row([date_str, trans_type, category, amount, account, user_display])
            saved_status = "✅ Сохранено в Google Таблицу!"
        else:
            saved_status = "⚠️ Не удалось сохранить в Google Таблицу."

        icon = "🔴" if trans_type == "Расход" else "🟢"

        message = (
            f"{icon} <b>Успешно записано!</b>\n\n"
            f"<b>Автор:</b> {user_display}\n"
            f"<b>Тип:</b> {trans_type}\n"
            f"<b>Сумма:</b> {amount:.2f} €\n"
            f"<b>Категория:</b> {category}\n"
            f"<b>Счет:</b> {account}\n\n"
            f"<i>{saved_status}</i>"
        )

        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке данных: {e}", reply_markup=get_main_keyboard())

async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet()
    if not sheet:
        await update.message.reply_text("⚠️ Не удалось подключиться к Google Таблице.", reply_markup=get_main_keyboard())
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
                summary[month_key] = {
                    "total_exp": 0.0,
                    "total_inc": 0.0,
                    "users": {}
                }

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
        await update.message.reply_text("ℹ️ Нет данных для формирования отчета.", reply_markup=get_main_keyboard())
        return

    text = "📊 <b>Семейный отчет по месяцам:</b>\n\n"
    for month in sorted(summary.keys(), reverse=True):
        m_data = summary[month]
        total_exp = m_data["total_exp"]
        total_inc = m_data["total_inc"]
        balance = total_inc - total_exp

        text += (
            f"📅 <b>Месяц: {month}</b>\n"
            f"  🟢 Доходы всего: <code>{total_inc:.2f} €</code>\n"
            f"  🔴 Расходы всего: <code>{total_exp:.2f} €</code>\n"
            f"  ⚖️ Общий баланс: <code>{balance:+.2f} €</code>\n"
            f"  -------------------------\n"
            f"  <b>Детализация по пользователям:</b>\n"
        )

        for u_name, u_stats in m_data["users"].items():
            exp = u_stats["Расход"]
            inc = u_stats["Доход"]
            text += f"  👤 <b>{u_name}:</b> 🔴 {exp:.2f} € | 🟢 {inc:.2f} €\n"

        text += "\n"

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())

async def delete_last_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet()
    if not sheet:
        await update.message.reply_text("⚠️ Не удалось подключиться к Google Таблице.", reply_markup=get_main_keyboard())
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
    app.add_handler(CommandHandler("report", monthly_report))
    app.add_handler(MessageHandler(filters.Regex("^📊 Отчет по месяцам$"), monthly_report))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Удалить последнюю запись$"), delete_last_entry))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    print("Бот успешно запущен...")
    app.run_polling(bootstrap_retries=-1, timeout=30)

if __name__ == '__main__':
    main()
