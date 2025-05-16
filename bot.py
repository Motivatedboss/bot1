import swisseph as swe
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Установка эфемерид
swe.set_ephe_path("./ephe")

# Планеты, включая Раху и Кету
PLANETS = [
    swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
    swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO,
    swe.MEAN_NODE  # Раху
]
ASPECTS = {"Соединение": 0, "Оппозиция": 180, "Трин": 120, "Квадрат": 90, "Секстиль": 60}
ASPECT_ORB = 6  # Орбис

ZODIAC_SIGNS = [
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"
]

ZODIAC_MEANINGS = [
    "энергичность, инициатива", "стабильность, чувственность", "общительность, интеллект",
    "эмоции, забота", "лидерство, творчество", "практичность, анализ",
    "гармония, партнёрство", "интенсивность, трансформация", "философия, путешествия",
    "дисциплина, амбиции", "оригинальность, свобода", "мечтательность, интуиция"
]

HOUSE_MEANINGS = [
    "Личность, внешность, самовосприятие",
    "Деньги, ценности, самооценка",
    "Коммуникации, мышление, братья/сёстры",
    "Семья, дом, корни",
    "Творчество, дети, удовольствия",
    "Здоровье, работа, служение",
    "Партнёрство, брак",
    "Кризисы, смерть, возрождение",
    "Философия, религия, обучение",
    "Карьера, статус",
    "Друзья, группы, мечты",
    "Подсознание, уединение"
]

PLANET_HOUSE_MEANINGS = {
    "Sun": HOUSE_MEANINGS, "Moon": HOUSE_MEANINGS, "Mercury": HOUSE_MEANINGS,
    "Venus": HOUSE_MEANINGS, "Mars": HOUSE_MEANINGS, "Jupiter": HOUSE_MEANINGS,
    "Saturn": HOUSE_MEANINGS, "Rahu": HOUSE_MEANINGS, "Ketu": HOUSE_MEANINGS
}

PLANET_SIGN_MEANINGS = {
    name: ZODIAC_MEANINGS for name in
    ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]
}


def calculate_chart(year, month, day, hour, minute, latitude, longitude):
    jd_ut = swe.julday(year, month, day, hour + minute / 60.0)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    houses, ascmc = swe.houses(jd_ut, latitude, longitude, b"P")

    planets = {}
    for planet in PLANETS:
        lon, _, _, _ = swe.calc_ut(jd_ut, planet, swe.FLG_SIDEREAL)
        name = swe.get_planet_name(planet)
        if name == "Mean Node":
            name = "Rahu"
        planets[name] = lon
    planets["Ketu"] = (planets["Rahu"] + 180) % 360

    planet_in_house = {}
    for name, lon in planets.items():
        for i in range(12):
            start = houses[i]
            end = houses[(i + 1) % 12] + (360 if houses[(i + 1) % 12] < start else 0)
            if start <= lon < end:
                planet_in_house[name] = i + 1
                break

    planet_aspects = []
    names = list(planets.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            angle = abs(planets[names[i]] - planets[names[j]])
            angle = angle if angle <= 180 else 360 - angle
            for asp_name, asp_angle in ASPECTS.items():
                if abs(angle - asp_angle) <= ASPECT_ORB:
                    planet_aspects.append((names[i], names[j], asp_name))

    interpretations = []
    for name, lon in planets.items():
        sign_index = int(lon // 30)
        interp = f"{name} в {ZODIAC_SIGNS[sign_index]} — {PLANET_SIGN_MEANINGS[name][sign_index]}"
        house = planet_in_house.get(name)
        if house:
            interp += f" | Дом {house}: {PLANET_HOUSE_MEANINGS[name][house - 1]}"
        interpretations.append(interp)

    house_interps = [f"Дом {i+1}: {desc}" for i, desc in enumerate(HOUSE_MEANINGS)]
    asc_sign_index = int(ascmc[0] // 30)
    asc_interp = f"Асцендент: {ZODIAC_SIGNS[asc_sign_index]} — {ZODIAC_MEANINGS[asc_sign_index]}"

    return "\n".join([
        asc_interp,
        "\nПланеты и дома:", *interpretations,
        "\nАспекты между планетами:", *(f"{a} {c} {b}" for a, b, c in planet_aspects),
        "\nЗначения домов:", *house_interps
    ])


# --- Telegram bot handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите данные в формате:\n`ГГГГ-ММ-ДД ЧЧ:ММ Широта Долгота`\nПример: `1990-05-10 14:30 55.75 37.6`", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        dt_str, time_str, lat_str, lon_str = text.split()
        year, month, day = map(int, dt_str.split("-"))
        hour, minute = map(int, time_str.split(":"))
        lat, lon = float(lat_str), float(lon_str)
        result = calculate_chart(year, month, day, hour, minute, lat, lon)
        await update.message.reply_text(result[:4000])
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


# --- Запуск ---

if __name__ == "__main__":
    import os
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    asyncio.run(app.run_polling())