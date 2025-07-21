import requests
import datetime
from telebot import TeleBot
from telebot import types
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
    btn1 = types.KeyboardButton("Погода на сьогодні")
    btn2 = types.KeyboardButton("Обрати місто")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id,"Привіт! Обери, що тебе цікавить:", reply_markup=markup)

    bot.send_message(message.chat.id, "Ви будете отримувати беззвучні повідомлення про погоду о 9:00 (Можливо в майбутньому автор дозволить змінювати цей параметр)")

@bot.message_handler(func=lambda message: message.text == "Погода на сьогодні")
def handle_today_weather(message):
    date = datetime.date.today()
    city = user_cities.get(message.chat.id, "Lviv,UA")

    day_weather = get_weather_by_hours_for_day_from_api(date=date, city=city)
    dangerous_hours = get_dangerous_hours(weather_by_hour=day_weather)

    bot.send_message(message.chat.id, f"Погода на {date} для {city}:")

    final_message = ""
    for hour_data in dangerous_hours:
        # Визначаємо ключ із часом: або "DANGER time", або "time"
        time_key = "DANGER time" if "DANGER time" in hour_data else "time"
        time = hour_data[time_key]
        uv = hour_data["uvindex"]
        temp = hour_data["temperature"]

        if time_key == "DANGER time":
            final_message += f"⚠️ {time} - УФ-індекс: {uv}, температура: {temp}°C\n"
        else:
            final_message += f"{time} - УФ-індекс: {uv}, температура: {temp}°C\n"

    bot.send_message(message.chat.id, final_message)

@bot.message_handler(func=lambda message: message.text == "Обрати місто")
def choose_city(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn3 = types.KeyboardButton("Львів")
    btn4 = types.KeyboardButton("Нововолинськ")
    markup.add(btn3, btn4)
    bot.send_message(message.chat.id, "Обери своє місто:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Львів" or message.text == "Нововолинськ")
def change_city(message):
    if (message.text == "Львів"):
        user_cities[message.chat.id] = "Lviv,UA"
    else:
        user_cities[message.chat.id] = "Novovolynsk,UA"

    bot.send_message(message.chat.id, f"Ваше місто: {message.text}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn1 = types.KeyboardButton("Погода на сьогодні")
    btn2 = types.KeyboardButton("Обрати місто")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "Повертаю тебе в головне меню 👇", reply_markup=markup)

def send_daily_weather():
    for chat_id, city in user_cities.items():
        date = datetime.date.today()
        day_weather = get_weather_by_hours_for_day_from_api(date=date, city=city)
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
    url=f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city}/{date}/{date}?key={API_KEY}"
    response = requests.get(url)


    weather_by_days = response.json()["days"]
    weather_by_hours = weather_by_days[0]["hours"]
    return weather_by_hours

def get_dangerous_hours (*, weather_by_hour: list[dict]) -> list[dict]:
    dangerous_hours = []
    for weather in weather_by_hour:
        uvindex = weather["uvindex"]
        time = weather["datetime"]
        celsius_temperature = fahrenheit_to_celsius(fahrenheit_temperature=weather["temp"])
        if uvindex >= DANGER_UVINDEX:
            dangerous_hours.append({"DANGER " "time": time, "uvindex": uvindex, "temperature": celsius_temperature})
        else:
            dangerous_hours.append({"time": time, "uvindex": uvindex, "temperature": celsius_temperature})

    return dangerous_hours

def fahrenheit_to_celsius(*, fahrenheit_temperature: float) -> int:
    return round((fahrenheit_temperature - 32) * 5 / 9)


scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Kyiv'))

# Запускаємо функцію send_daily_weather щодня о 9:00 за київським часом
scheduler.add_job(send_daily_weather, 'cron', hour=19, minute=14)
scheduler.start()


bot.infinity_polling()