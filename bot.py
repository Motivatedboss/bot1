import os
import traceback
import aiohttp
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

# Переменные окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Flask-приложение
flask_app = Flask(__name__)

# Telegram-приложение
application = Application.builder().token(TOKEN).build()

# Данные пользователей
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я астробот.\nНапиши, пожалуйста, свою дату рождения (в формате ДД.ММ.ГГГГ):")

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if user_id not in user_data:
        user_data[user_id] = text
        reply_keyboard = [[topics[i], topics[i + 1], topics[i + 2]] for i in range(0, len(topics), 3)]
        await update.message.reply_text(
            "Спасибо! Теперь выбери интересующую тему:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        )
    else:
        if text in topics:
            selected_topic = text[3:]  # убираем номер
            dob = user_data.get(user_id, "неизвестна")
            prompt = (
                f"Ты — профессиональный астролог. Пользователь родился {dob}. "
                f"Дай подробный, дружелюбный и полезный астрологический совет по теме: '{selected_topic}'."
            )

            try:
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://yourdomain.com",  # при необходимости укажи свой сайт
                    "X-Title": "AstroBot"
                }
                payload = {
                    "model": "openai/gpt-3.5-turbo",  # можно сменить на любую доступную модель OpenRouter
                    "messages": [
                        {"role": "system", "content": "Ты — астролог-бот."},
                        {"role": "user", "content": prompt}
                    ]
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            reply_text = data["choices"][0]["message"]["content"]
                        else:
                            error = await resp.text()
                            print("Ошибка OpenRouter:", error)
                            reply_text = "Произошла ошибка при обращении к OpenRouter 😔"

            except Exception as e:
                traceback.print_exc()
                reply_text = "Произошла непредвиденная ошибка 😢"

            await update.message.reply_text(reply_text)
        else:
            await update.message.reply_text("Пожалуйста, выбери тему из предложенного списка.")

# Webhook для Telegram
@flask_app.route("/webhook", methods=["POST"])
def webhook() -> str:
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "OK", 200

# Проверка статуса
@flask_app.route("/", methods=["GET"])
def index() -> str:
    return "Бот работает.", 200

# Хендлеры
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Запуск
if __name__ == "__main__":
    print("Запуск бота с webhook...")
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL
    )