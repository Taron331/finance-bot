import datetime
import gspread
from google.oauth2 import service_account
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = "8926455676:AAEmvLB7-D68aFIlK982bnMVeofTiA4gI0Y"
SPREADSHEET_NAME = "Транзакции"

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

CATEGORIES_EXPENSE = ["🍔 Еда", "🛒 Продукты", "🚗 Авто", "🏠 Дом", "🎉 Развлечения", "📦 Другое"]
CATEGORIES_INCOME = ["💼 Зарплата", "📈 Инвестиции", "🎁 Подарок", "💰 Другое"]
ACCOUNTS = ["💳 Карта", "💵 Наличные"]
PRESET_AMOUNTS_EXPENSE = [5, 10, 15, 20, 50, 100]
PRESET_AMOUNTS_INCOME = [100, 200, 500, 1000]

user_data_store = {}

def get_main_reply_keyboard():
    keyboard = [
        ["➖ Добавить Расход", "➕ Добавить Доход"],
        ["🗑 Удалить последнюю запись", "📊 Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет, {update.message.from_user.first_name}!\n\n"
        "Выберите действие с помощью кнопок снизу:",
        reply_markup=get_main_reply_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name or "Пользователь"

    if text == "🗑 Удалить последнюю запись":
        await delete_last_row(update, context)
        return

    if text in ["📊 Помощь", "❓ Помощь"]:
        await update.message.reply_text(
            "💡 Используйте нижнее меню для выбора действия. Все операции выполняются по кнопкам!",
            reply_markup=get_main_reply_keyboard()
        )
        return

    if text == "➖ Добавить Расход":
        user_data_store[user_id] = {"type": "Расход", "user_name": user_name}
        keyboard = []
        row = []
        for amt in PRESET_AMOUNTS_EXPENSE:
            row.append(InlineKeyboardButton(f"{amt} €", callback_data=f"amt_{amt}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("✏️ Ввести свою сумму", callback_data="manual_amount")])

        await update.message.reply_text(
            "🔴 *Добавление расхода*\nВыберите сумму:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if text == "➕ Добавить Доход":
        user_data_store[user_id] = {"type": "Доход", "user_name": user_name}
        keyboard = []
        row = []
        for amt in PRESET_AMOUNTS_INCOME:
            row.append(InlineKeyboardButton(f"+{amt} €", callback_data=f"amt_{amt}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("✏️ Ввести свою сумму", callback_data="manual_amount")])

        await update.message.reply_text(
            "🟢 *Добавление дохода*\nВыберите сумму:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Если пользователь решил вписать число вручную
    amount_str = text.replace(",", ".")
    try:
        if amount_str.startswith("+"):
            trans_type = "Доход"
            amount = float(amount_str[1:])
        else:
            trans_type = "Расход"
            amount = float(amount_str)

        user_data_store[user_id] = {
            "amount": amount,
            "type": trans_type,
            "user_name": user_name
        }
        await show_categories(update.message, user_id)
    except ValueError:
        await update.message.reply_text("Пожалуйста, используйте кнопки меню снизу.", reply_markup=get_main_reply_keyboard())

async def show_categories(target, user_id):
    trans_type = user_data_store[user_id]["type"]
    categories = CATEGORIES_INCOME if trans_type == "Доход" else CATEGORIES_EXPENSE

    keyboard = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    msg_text = f"Сумма: *{user_data_store[user_id]['amount']:.2f} €* ({trans_type})\nВыберите категорию:"
    if hasattr(target, 'edit_message_text'):
        await target.edit_message_text(msg_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await target.reply_text(msg_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "delete_last":
        await delete_last_row_query(query)
        return

    if data == "manual_amount":
        await query.edit_message_text("Отправьте сумму сообщением (например: `12.50`):", parse_mode="Markdown")
        return

    if data.startswith("amt_"):
        amount = float(data.replace("amt_", ""))
        if user_id in user_data_store:
            user_data_store[user_id]["amount"] = amount
            await show_categories(query, user_id)
        return

    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        if user_id in user_data_store:
            user_data_store[user_id]["category"] = category
            keyboard = [[InlineKeyboardButton(acc, callback_data=f"acc_{acc}")] for acc in ACCOUNTS]
            await query.edit_message_text(
                f"Сумма: *{user_data_store[user_id]['amount']:.2f} €*\nКатегория: *{category}*\n\nВыберите счет:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    if data.startswith("acc_"):
        account = data.replace("acc_", "")
        if user_id in user_data_store:
            info = user_data_store.pop(user_id)
            now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            sheet.append_row([now, info["user_name"], info["type"], info["category"], info["amount"], account])

            keyboard = [[InlineKeyboardButton("❌ Отменить/Удалить", callback_data="delete_last")]]
            await query.edit_message_text(
                f"✅ *Успешно сохранено!*\n\n"
                f"• Тип: {info['type']}\n"
                f"• Сумма: {info['amount']:.2f} €\n"
                f"• Категория: {info['category']}\n"
                f"• Счет: {account}",
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
            parse_mode="Markdown",
            reply_markup=get_main_reply_keyboard()
        )
    else:
        await update.message.reply_text("⚠️ Таблица пуста, нечего удалять.", reply_markup=get_main_reply_keyboard())

async def delete_last_row_query(query):
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    app.run_polling()

if __name__ == "__main__":
    main()
