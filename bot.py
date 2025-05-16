import swisseph as swe
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from flask import Flask
import threading

# Установка эфемерид
swe.set_ephe_path("./ephe")  # Убедитесь, что в папке ./ephe есть файлы эфемерид

# Константы
PLANETS = [
    swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
    swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO,
    swe.MEAN_NODE  # Раху
]
ASPECTS = {
    "Conjunction": 0,
    "Opposition": 180,
    "Trine": 120,
    "Square": 90,
    "Sextile": 60
}
ASPECT_ORB = 6  # Орбис для мажорных аспектов

# Интерпретации (сокращённо)
PLANET_HOUSE_MEANINGS = {"Sun": [...], "Moon": [...], "Mercury": [...], "Venus": [...], "Mars": [...], "Jupiter": [...], "Saturn": [...], "Mean Node": [...], "Rahu": [...], "Ketu": ["Потеря эго и переоценка личности.", ..., "Духовное очищение и отказ от иллюзий."]}
HOUSE_MEANINGS = ["Личность, внешность, восприятие мира.", ..., "Подсознание, уединение, тайны, духовность."]
ZODIAC_SIGNS = ["Овен", ..., "Рыбы"]
ZODIAC_MEANINGS = ["Овен: энергичность...", ..., "Рыбы: мечтательность..."]
PLANET_SIGN_MEANINGS = {"Sun": ZODIAC_MEANINGS, "Moon": ZODIAC_MEANINGS, "Mercury": ZODIAC_MEANINGS, "Venus": ZODIAC_MEANINGS, "Mars": ZODIAC_MEANINGS, "Jupiter": ZODIAC_MEANINGS, "Saturn": ZODIAC_MEANINGS, "Uranus": ZODIAC_MEANINGS, "Neptune": ZODIAC_MEANINGS, "Pluto": ZODIAC_MEANINGS, "Rahu": ZODIAC_MEANINGS, "Ketu": ZODIAC_MEANINGS}

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

# --- Telegram Bot ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправьте данные в формате: \nГГГГ-ММ-ДД ЧЧ:ММ Широта Долгота\nПример: 1990-05-10 14:30 55.75 37.6")

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

# --- Flask fake server for Render ---
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Telegram bot is running"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# --- Запуск Telegram-бота и Flask одновременно ---
if __name__ == "__main__":
    import os
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    threading.Thread(target=run_flask).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    asyncio.run(app.run_polling())
