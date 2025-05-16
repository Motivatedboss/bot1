import os
import swisseph as swe
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from flask import Flask, request

# Настройки эфемерид
swe.set_ephe_path("./ephe")

# Константы
PLANETS = [
    swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
    swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO,
    swe.MEAN_NODE
]
ASPECTS = {
    "Conjunction": 0,
    "Opposition": 180,
    "Trine": 120,
    "Square": 90,
    "Sextile": 60
}
ASPECT_ORB = 6
ZODIAC_SIGNS = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
ZODIAC_MEANINGS = ["Овен: энергичность", "Телец: стабильность", "Близнецы: любознательность", "Рак: чувствительность", "Лев: уверенность", "Дева: аналитичность", "Весы: гармония", "Скорпион: страстность", "Стрелец: философичность", "Козерог: целеустремлённость", "Водолей: оригинальность", "Рыбы: мечтательность"]
PLANET_SIGN_MEANINGS = {planet: ZODIAC_MEANINGS for planet in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]}
HOUSE_MEANINGS = [f"Интерпретация дома {i+1}" for i in range(12)]
PLANET_HOUSE_MEANINGS = {planet: HOUSE_MEANINGS for planet in PLANET_SIGN_MEANINGS}

def calculate_chart(year, month, day, hour, minute, latitude, longitude):
    jd_ut = swe.julday(year, month, day, hour + minute / 60.0)
    houses, ascmc = swe.houses(jd_ut, latitude, longitude, b"P")
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    planets = {}
    for planet in PLANETS:
        lon, _, _, _ = swe.calc_ut(jd_ut, planet, swe.FLG_SIDEREAL)
        pname = swe.get_planet_name(planet)
        if pname == "Mean Node":
            pname = "Rahu"
        planets[pname] = lon
    planets["Ketu"] = (planets["Rahu"] + 180) % 360

    planet_in_house = {}
    for pname, plon in planets.items():
        for i in range(12):
            start = houses[i]
            end = houses[(i + 1) % 12] + (360 if houses[(i + 1) % 12] < start else 0)
            if start <= plon < end:
                planet_in_house[pname] = i + 1
                break

    planet_aspects = []
    names = list(planets.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            angle = abs(planets[names[i]] - planets[names[j]])
            angle = angle if angle <= 180 else 360 - angle
            for aspect_name, aspect_angle in ASPECTS.items():
                if abs(angle - aspect_angle) <= ASPECT_ORB:
                    planet_aspects.append((names[i], names[j], aspect_name))

    interpretations = []
    for pname, plon in planets.items():
        sign_index = int(plon // 30)
        sign_meaning = PLANET_SIGN_MEANINGS.get(pname, ZODIAC_MEANINGS)[sign_index]
        interp = f"{pname} в {ZODIAC_SIGNS[sign_index]}: {sign_meaning}"
        if pname in planet_in_house:
            house = planet_in_house[pname]
            if pname in PLANET_HOUSE_MEANINGS:
                desc = PLANET_HOUSE_MEANINGS[pname][house - 1]
                interp += f" | Дом {house}: {desc}"
        interpretations.append(interp)

    house_interpretations = [f"Дом {i+1}: {meaning}" for i, meaning in enumerate(HOUSE_MEANINGS)]
    asc_sign_index = int(ascmc[0] // 30)
    asc_house_desc = f"Асцендент: {ZODIAC_SIGNS[asc_sign_index]} — {ZODIAC_MEANINGS[asc_sign_index]}"

    return "\n".join([
        asc_house_desc,
        "\n\nПланеты:", *interpretations,
        "\nАспекты:", *(f"{a[0]} {a[2]} {a[1]}" for a in planet_aspects),
        "\nДома:", *house_interpretations
    ])

# Telegram bot + Flask webhook
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT = Bot(token=TOKEN)
app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправьте данные в формате: ГГГГ-ММ-ДД ЧЧ:ММ Широта Долгота\nПример: 1990-05-10 14:30 55.75 37.6")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        dt_str, time_str, lat, lon = text.split()
        year, month, day = map(int, dt_str.split("-"))
        hour, minute = map(int, time_str.split(":"))
        lat, lon = float(lat), float(lon)
        report = calculate_chart(year, month, day, hour, minute, lat, lon)
        await update.message.reply_text(report[:4000])
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}\nУбедитесь, что вы ввели данные в правильном формате.")

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Flask setup
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def index():
    return "Бот работает."

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), BOT)
    app.update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    # Установка вебхука
    import requests
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/{TOKEN}")

    print("Запуск Flask-сервера...")
    flask_app.run(host="0.0.0.0", port=8080)
