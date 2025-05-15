import os
from flask import Flask, request
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# Получение переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Flask-приложение
flask_app = Flask(__name__)

# Telegram-приложение
application = Application.builder().token(TOKEN).build()

# Простая логика обработки сообщений

# Словарь для хранения даты рождения пользователей
user_data = {}

# Темы
topics = [
    "1. Общая информация о тебе",
    "2. Тотемное животное",
    "3. Финансы",
    "4. Бизнес",
    "5. Предназначение",
    "6. Доходы",
    "7. Отношения",
    "8. Жизненный период",
    "9. Меня интересует всё",
]

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я астробот.\nНапиши, пожалуйста, свою дату рождения (в формате ДД.ММ.ГГГГ):")

# Обработка даты рождения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Проверка, указал ли пользователь дату рождения
    if user_id not in user_data:
        user_data[user_id] = text
        # Отправка тем для выбора
        reply_keyboard = [[topics[i], topics[i + 1], topics[i + 2]] for i in range(0, len(topics), 3)]
        await update.message.reply_text(
            "Спасибо! Теперь выбери интересующую тему:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        )
    else:
        # Выбранная тема
        selected = text.strip()
        if selected in topics:
            await update.message.reply_text(f"Ты выбрал тему: {selected}\n(Здесь будет ответ по теме позже)")
        else:
            await update.message.reply_text("Пожалуйста, выбери одну из тем с клавиатуры.")

# Обработка Telegram webhook
@flask_app.route("/webhook", methods=["POST"])
def webhook() -> str:
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "OK", 200

# Проверка работоспособности сервиса
@flask_app.route("/", methods=["GET"])
def index() -> str:
    return "Бот работает.", 200

# Подключаем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Запуск в режиме webhook
if __name__ == "__main__":
    print("Запуск бота с webhook...")
    application.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 5000)),
    webhook_url=WEBHOOK_URL
)