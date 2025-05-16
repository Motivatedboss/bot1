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

# Отправка длинного сообщения по частям
async def send_long_message(text, update):
    MAX_LENGTH = 4096
    for i in range(0, len(text), MAX_LENGTH):
        await update.message.reply_text(text[i:i+MAX_LENGTH])

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"step": "name"}
    await update.message.reply_text("Привет! Я астробот.\nКак тебя зовут?")

# Обработка всех сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_data:
        await start(update, context)
        return

    state = user_data[user_id]

    if state.get("step") == "name":
        state["name"] = text
        state["step"] = "date"
        await update.message.reply_text("Укажи дату рождения (ДД.ММ.ГГГГ):")
    elif state.get("step") == "date":
        state["birth_date"] = text
        state["step"] = "time"
        await update.message.reply_text("Теперь время рождения (например, 14:30):")
    elif state.get("step") == "time":
        state["birth_time"] = text
        state["step"] = "place"
        await update.message.reply_text("Где ты родился? Укажи город или населённый пункт:")
    elif state.get("step") == "place":
        state["birth_place"] = text
        state["step"] = "topic"
        reply_keyboard = [[topics[i], topics[i + 1], topics[i + 2]] for i in range(0, len(topics), 3)]
        await update.message.reply_text(
            "Спасибо! Теперь выбери интересующую тему:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        )
    elif state.get("step") == "topic":
        if text in topics:
            state["selected_topic"] = text[3:]
            await generate_astrology_response(update, context, user_id)
        else:
            await update.message.reply_text("Пожалуйста, выбери тему из списка.")
    else:
        await update.message.reply_text("Что-то пошло не так. Напиши /start чтобы начать сначала.")

# Генерация астрологического ответа
async def generate_astrology_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    state = user_data[user_id]
    prompt = (
        f"Ты — профессиональный астролог. Вот данные пользователя:\n"
        f"Имя: {state['name']}\n"
        f"Дата рождения: {state['birth_date']}\n"
        f"Время рождения: {state['birth_time']}\n"
        f"Место рождения: {state['birth_place']}\n"
        f"Тема: {state['selected_topic']}\n\n"
        f"Составь развернутую, дружелюбную, понятную и полезную астрологическую консультацию."
    )

    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yourdomain.com",
            "X-Title": "AstroBot"
        }
        payload = {
            "model": "meta-llama/llama-3-8b-instruct",
            "messages": [
                {"role": "system", "content": "Ты — опытный астролог."},
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

    await send_long_message(reply_text, update)

# Webhook
@flask_app.route("/webhook", methods=["POST"])
def webhook() -> str:
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "OK", 200

# Проверка
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