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

# Временное хранение выборов пользователя
user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🗑 Удалить последнюю запись", "📊 Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Привет, {update.message.from_user.first_name}!\n\n"
        "💡 *Как вносить данные:*\n"
        "• Отправьте сумму (например: `15` для расхода или `+1000` для дохода) — бот покажет кнопки выбора.\n"
        "• Или напишите в одну строку: `15 Обед Карта`.\n"
        "• Для отмены используйте кнопку *'🗑 Удалить последнюю запись'*.",
        parse_mode="Markdown",
        reply_markup=reply_markup
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
            "💡 *Инструкция:*\n"
            "1. Введите число: `25` (расход) или `+500` (доход).\n"
            "2. Выберите категорию и счет кнопками.\n"
            "3. Нажмите *'Удалить последнюю запись'* для очистки тестов.",
            parse_mode="Markdown"
        )
        return

    parts = text.split(" ")
    
    # Запись в одну строку (например: "15 Обед Карта")
    if len(parts) >= 2:
        amount_str = parts[0].replace(",", ".")
        try:
            if amount_str.startswith("+"):
                trans_type = "Доход"
                amount = float(amount_str[1:])
            else:
                trans_type = "Расход"
                amount = float(amount_str)

            category = parts[1]
            account = " ".join(parts[2:]) if len(parts) > 2 else "Карта"
            now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            sheet.append_row([now, user_name, trans_type, category, amount, account])
            
            keyboard = [[InlineKeyboardButton("❌ Отменить/Удалить", callback_data="delete_last")]]
            await update.message.reply_text(
                f"✅ *Записано:*\n• {trans_type}: {amount:.2f} €\n• Категория: {category}\n• Счет: {account}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        except ValueError:
            pass

    # Интерактивный ввод (например: "15" или "+1000")
    amount_str = text.replace(",", ".")
    try:
        if amount_str.startswith("+"):
            trans_type = "Доход"
            amount = float(amount_str[1:])
            categories = CATEGORIES_INCOME
        else:
            trans_type = "Расход"
            amount = float(amount_str)
            categories = CATEGORIES_EXPENSE

        user_data_store[user_id] = {
            "amount": amount,
            "type": trans_type,
            "user_name": user_name
        }

        keyboard = []
        row = []
        for cat in categories:
            row.append(InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        await update.message.reply_text(
            f"Сумма: *{amount:.2f} €* ({trans_type})\nВыберите категорию:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except ValueError:
        await update.message.reply_text("⚠️ Введите сумму числом (например: `15` или `+500`)", parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "delete_last":
        await delete_last_row_query(query)
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
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Таблица пуста, нечего удалять.")

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
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    app.run_polling()

if __name__ == "__main__":
    main()
