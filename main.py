import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8926455676:AAEmvLB7-D68aFIlK982bnMVeofTiA4gI0Y"
SPREADSHEET_NAME = "Транзакции"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

try:
    sheet = client.open(SPREADSHEET_NAME).sheet1
except Exception:
    sheet = client.openall()[0].sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📊 Отчет", "❓ Помощь"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Привет, {update.message.from_user.first_name}!\n\n"
        "⚡️ Бот подключен и работает без задержек.\n\n"
        "Формат записи:\n"
        "• `15 Обед` — расход 15 € (Карта)\n"
        "• `15 Обед Наличка` — расход с другого счета\n"
        "• `+1000 Зарплата` — доход\n",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_name = update.message.from_user.first_name or "Пользователь"

    if text == "❓ Помощь":
        await update.message.reply_text("💡 Примеры:\n• `20 Продукты`\n• `+500 Зарплата`", parse_mode="Markdown")
        return

    parts = text.split(" ")
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

            await update.message.reply_text(
                f"✅ *Записано:*\n"
                f"• {trans_type}: {amount:.2f} €\n"
                f"• Категория: {category}\n"
                f"• Счет: {account}",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("⚠️ Ошибка в сумме. Напишите, например: `15 Обед`", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Укажите сумму и категорию (например: `15 Обед`)", parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()