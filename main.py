import requests
import datetime
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TOKEN")

DANGER_UVINDEX = 3
user_cities = {}
bot = TeleBot(TOKEN)


@bot.message_handler(commands=["start"])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(
        types.KeyboardButton("Погода на сьогодні"),
        types.KeyboardButton("Обрати місто")
    )

    bot.send_message(
        message.chat.id,
        "Привіт! Обери, що тебе цікавить:",
        reply_markup=markup
    )
    bot.send_message(
        message.chat.id,
        "Ви будете отримувати беззвучні повідомлення про погоду о 9:00 🕘"
    )


@bot.message_handler(func=lambda message: message.text == "Погода на сьогодні")
def handle_today_weather(message):
    date = datetime.date.today()
    city = user_cities.get(message.chat.id, "Lviv,UA")

    try:
        day_weather = get_weather_by_hours_for_day_from_api(date=date, city=city)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Не вдалося отримати дані про погоду: {e}")
        return

    dangerous_hours = get_dangerous_hours(weather_by_hour=day_weather)

    final_message = f"Погода на {date} для {city}:\n\n"
    for hour_data in dangerous_hours:
        time_key = "DANGER time" if "DANGER time" in hour_data else "time"
        time = hour_data[time_key]
        uv = hour_data["uvindex"]
        temp = hour_data["temperature"]

        if time_key == "DANGER time":
            final_message += f"⚠️ {time} — УФ-індекс: {uv}, температура: {temp}°C\n"
        else:
            final_message += f"{time} — УФ-індекс: {uv}, температура: {temp}°C\n"

    bot.send_message(message.chat.id, final_message)


@bot.message_handler(func=lambda message: message.text == "Обрати місто")
def choose_city(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(types.KeyboardButton("Львів"), types.KeyboardButton("Нововолинськ"))
    bot.send_message(message.chat.id, "Обери своє місто:", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in ["Львів", "Нововолинськ"])
def change_city(message):
    user_cities[message.chat.id] = "Lviv,UA" if message.text == "Львів" else "Novovolynsk,UA"
    bot.send_message(message.chat.id, f"Ваше місто: {message.text}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(
        types.KeyboardButton("Погода на сьогодні"),
        types.KeyboardButton("Обрати місто")
    )
    bot.send_message(message.chat.id, "Повертаю тебе в головне меню 👇", reply_markup=markup)


def send_daily_weather():
    for chat_id, city in user_cities.items():
        date = datetime.date.today()
        try:
            day_weather = get_weather_by_hours_for_day_from_api(date=date, city=city)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Не вдалося отримати дані про погоду: {e}", disable_notification=True)
            continue

        dangerous_hours = get_dangerous_hours(weather_by_hour=day_weather)

        final_message = f"Погода на {date} для {city}:\n\n"
        for hour_data in dangerous_hours:
            time_key = "DANGER time" if "DANGER time" in hour_data else "time"
            time = hour_data[time_key]
            uv = hour_data["uvindex"]
            temp = hour_data["temperature"]

            if time_key == "DANGER time":
                final_message += f"⚠️ {time} — УФ-індекс: {uv}, температура: {temp}°C\n"
            else:
                final_message += f"{time} — УФ-індекс: {uv}, температура: {temp}°C\n"

        bot.send_message(chat_id, final_message, disable_notification=True)


def get_weather_by_hours_for_day_from_api(*, date: str, city: str) -> list[dict]:
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city}/{date}/{date}?key={API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        weather_by_days = response.json().get("days", [])
        if not weather_by_days:
            raise ValueError("API не повернуло даних.")
        return weather_by_days[0].get("hours", [])
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Помилка при з'єднанні з API: {e}")
    except Exception as e:
        raise RuntimeError(f"Некоректні дані з API: {e}")


def get_dangerous_hours(*, weather_by_hour: list[dict]) -> list[dict]:
    dangerous_hours = []
    for weather in weather_by_hour:
        uvindex = weather.get("uvindex", 0)
        time = weather.get("datetime", "невідомо")
        temp_f = weather.get("temp", 32)
        celsius_temperature = fahrenheit_to_celsius(fahrenheit_temperature=temp_f)

        if uvindex >= DANGER_UVINDEX:
            dangerous_hours.append({"DANGER time": time, "uvindex": uvindex, "temperature": celsius_temperature})
        else:
            dangerous_hours.append({"time": time, "uvindex": uvindex, "temperature": celsius_temperature})

    return dangerous_hours


def fahrenheit_to_celsius(*, fahrenheit_temperature: float) -> int:
    return round((fahrenheit_temperature - 32) * 5 / 9)


# Планувальник на 9:00
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Kyiv'))
scheduler.add_job(send_daily_weather, 'cron', hour=9, minute=0)
scheduler.start()

bot.infinity_polling()
