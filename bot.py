import os
import asyncio
import swisseph as swe
from datetime import datetime
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Установка пути к эфемеридам
swe.set_ephe_path("./ephe")

# Планеты и константы
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
ASPECT_ORB = 6

ZODIAC_SIGNS = [
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"
]
ZODIAC_MEANINGS = [f"{sign}: описание знака..." for sign in ZODIAC_SIGNS]

HOUSE_MEANINGS = [f"Интерпретация дома {i+1}" for i in range(12)]
PLANET_HOUSE_MEANINGS = {p: HOUSE_MEANINGS for p in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]}
PLANET_SIGN_MEANINGS = {p: ZODIAC_MEANINGS for p in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]}


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
        sign = ZODIAC_SIGNS[sign_index]
        sign_meaning = PLANET_SIGN_MEANINGS[pname][sign_index]
        interp = f"{pname} в {sign}: {sign_meaning}"
        if pname in planet_in_house:
            house = planet_in_house[pname]
            house_meaning = PLANET_HOUSE_MEANINGS[pname][house - 1]
            interp += f" | Дом {house}: {house_meaning}"
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


# Telegram handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите данные в формате: \nГГГГ-ММ-ДД ЧЧ:ММ Широта Долгота\nПример: 1990-05-10 14:30 55.75 37.6")

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
        await update.message.reply_text(f"Ошибка: {e}\nФормат: 1990-05-10 14:30 55.75 37.6")


# Web server for Render
async def web_handler(request):
    return web.Response(text="Bot is running.")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", web_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()


# Запуск
async def main():
    telegram_app = ApplicationBuilder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await start_webserver()
    await telegram_app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())