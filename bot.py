import os
import traceback
import aiohttp
from flask import Flask, request
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardRemove
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
application = Application.builder().token(TOKEN).build()

# Состояния пользователя
user_state = {}
user_inputs = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = "name"
    user_inputs[user_id] = {}
    await update.message.reply_text("Привет! Я астробот 🌟\nДавай составим твою натальную карту.\n\nКак тебя зовут?")

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    state = user_state.get(user_id)

    if state == "name":
        user_inputs[user_id]["name"] = text
        user_state[user_id] = "birth_date"
        await update.message.reply_text("Отлично! Теперь укажи дату рождения (ДД.ММ.ГГГГ):")

    elif state == "birth_date":
        user_inputs[user_id]["birth_date"] = text
        user_state[user_id] = "birth_time"
        await update.message.reply_text("Спасибо! Укажи время рождения (например, 14:30):")

    elif state == "birth_time":
        user_inputs[user_id]["birth_time"] = text
        user_state[user_id] = "birth_place"
        await update.message.reply_text("И последнее — укажи место рождения:")

    elif state == "birth_place":
        user_inputs[user_id]["birth_place"] = text
        user_state[user_id] = "done"
        await update.message.reply_text("Спасибо! Готовлю твой астрологический анализ... 🔮", reply_markup=ReplyKeyboardRemove())
        await generate_astrology_response(update, context, user_id)

    else:
        await update.message.reply_text("Пожалуйста, начни с команды /start, чтобы получить персональный анализ.")

# Генерация запроса к OpenRouter
async def generate_astrology_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    info = user_inputs[user_id]
    prompt = (
        f"Ты — профессиональный астролог. Сделай подробный астрологический анализ для пользователя по следующим данным:\n"
        f"Имя: {info['name']}\n"
        f"Дата рождения: {info['birth_date']}\n"
        f"Время рождения: {info['birth_time']}\n"
        f"Место рождения: {info['birth_place']}\n"
        f"Подробно расскажи о характере, жизненном пути, предрасположенностях и рекомендациях для будущего."
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
                {"role": "system", "content": "Ты — профессиональный астролог-бот."},
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

# Webhook
@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def index():
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