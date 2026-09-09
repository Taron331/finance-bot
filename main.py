import json
import datetime
import gspread
from google.oauth2 import service_account
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder

# Увеличиваем таймауты подключения и чтения до 30 секунд
app = (
    ApplicationBuilder()
    .token("ВАШ_ТОКЕН_БОТА")
    .connect_timeout(30.0)
    .read_timeout(30.0)
    .write_timeout(30.0)
    .get_updates_connect_timeout(30.0)
    .get_updates_read_timeout(30.0)
    .build()
)

if __name__ == '__main__':
    app.run_polling()

TOKEN = "8926455676:AAEmvLB7-D68aFIlK982bnMVeofTiA4gI0Y"
SPREADSHEET_NAME = "Транзакции"
WEB_APP_URL = "https://taron331.github.io/finance-bot/"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = service_account.Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)

try:
    sheet = client.open(SPREADSHEET_NAME).sheet1
except Exception:
    sheet = client.openall()[0].sheet1

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📲 Внести транзакцию (iOS барабан)", web_app=WebAppInfo(url=WEB_APP_URL))],
        [KeyboardButton("🗑 Удалить последнюю запись")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет, {update.message.from_user.first_name}!\n\n"
        "Нажмите кнопку ниже, чтобы открыть удобный колесико-барабан для ввода суммы и выбора категории 👇",
        reply_markup=get_main_keyboard()
    )

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.message.web_app_data.data)
    user_name = update.message.from_user.first_name or "Пользователь"
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    trans_type = data.get("type", "Расход")
    amount = float(data.get("amount", 0))
    category = data.get("category", "Другое")
    account = data.get("account", "Карта")

    # Запись в Google Таблицу
    sheet.append_row([now, user_name, trans_type, category, amount, account])

    keyboard = [[InlineKeyboardButton("❌ Отменить/Удалить", callback_data="delete_last")]]
    await update.message.reply_text(
        f"✅ *Сохранено через Mini App!*\n\n"
        f"• Тип: *{trans_type}*\n"
        f"• Сумма: *{amount:.2f} €*\n"
        f"• Категория: *{category}*\n"
        f"• Счет: *{account}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_last_row(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_values()
    if len(rows) > 1:
        last_row_index = len(rows)
        deleted_data = rows[-1]
        sheet.delete_rows(last_row_index)
        await update.message.reply_text(
            f"🗑 *Удалена последняя запись:*\n`{' | '.join(deleted_data)}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Таблица пуста, нечего удалять.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "delete_last":
        rows = sheet.get_all_values()
        if len(rows) > 1:
            last_row_index = len(rows)
            deleted_data = rows[-1]
            sheet.delete_rows(last_row_index)
            await query.edit_message_text(
                f"🗑 *Запись отменена и удалена из таблицы:*\n`{' | '.join(deleted_data)}`",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("⚠️ Таблица пуста, нечего удалять.")

def main():
    proxy_url = "http://proxy.server:3128"
    app = (
        Application.builder()
        .token(TOKEN)
        .proxy(proxy_url)
        .get_updates_proxy(proxy_url)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Удалить последнюю запись$"), delete_last_row))
    app.add_handler(CallbackQueryHandler(button_click))

    app.run_polling()

if __name__ == "__main__":
    main()
