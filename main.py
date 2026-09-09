import logging
import json
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Ваш токен от BotFather
BOT_TOKEN = "8926455676:AAEmvLB7-D68aFIlK982bnMVeofTiA4gI0Y"

# Ссылка на ваше веб-приложение (укажите ссылку на GitHub Pages)
WEBAPP_URL = "https://github.com/Taron331/finance-bot/"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить транзакцию", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text(
        "Привет! Нажмите на кнопку ниже, чтобы зафиксировать расход или доход:",
        reply_markup=keyboard
    )

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем данные, отправленные из WebApp (index.html)
    data_raw = update.effective_message.web_app_data.data
    try:
        data = json.loads(data_raw)
        trans_type = data.get("type", "Расход")
        amount = data.get("amount", 0)
        category = data.get("category", "Без категории")
        account = data.get("account", "Карта")

        icon = "🔴" if trans_type == "Расход" else "🟢"

        message = (
            f"{icon} <b>Успешно записано!</b>\n\n"
            f"<b>Тип:</b> {trans_type}\n"
            f"<b>Сумма:</b> {amount:.2f} €\n"
            f"<b>Категория:</b> {category}\n"
            f"<b>Счет:</b> {account}"
        )

        await update.message.reply_text(message, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке данных: {e}")

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
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    print("Бот успешно запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
