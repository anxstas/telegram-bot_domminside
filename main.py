import telebot
from telebot import types
import openai
import logging
import os
import random
import time
from datetime import datetime, timedelta
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 513201869
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PORT = int(os.getenv("PORT", "10000"))

bot = telebot.TeleBot(TELEGRAM_TOKEN)
logging.basicConfig(level=logging.INFO)
user_state = {}

user_selected_slots = {}

def get_next_slots():
    today = datetime.now()
    slots = []
    schedule = {
        3: ["09:00", "12:00"],
        4: ["09:00", "10:00", "12:00"],
        6: ["13:00", "15:00"],
    }
    for i in range(1, 10):
        day = today + timedelta(days=i)
        wd = day.weekday()
        if wd in schedule:
            for t in schedule[wd]:
                dt_obj = datetime.strptime(f"{day.strftime('%Y-%m-%d')} {t}", "%Y-%m-%d %H:%M")
                label = f"{day.strftime('%a %d %b')} • {t}"
                slots.append((label, dt_obj))
    return slots

def human_delay():
    time.sleep(random.uniform(1.2, 2.5))

def persistent_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('📅 Записаться на сессию-знакомство -40%')
    markup.add('🔍 Пойти глубже', '🆘 Срочная помощь')
    markup.add('📊 Тест тревоги', '📉 Тест депрессии') 
    return markup

anxiety_test_data = [
    "Ощущение онемения или покалывания в теле",
    "Ощущение жара",
    "Дрожь в ногах",
    "Неспособность расслабиться",
    "Страх, что случится наихудшее",
    "Головокружение или ощущение, что вы падаете в обморок",
    "Ускоренное сердцебиение",
    "Неуверенность в устойчивости (ощущение шаткости)",
    "Страх потери контроля",
    "Ощущение трудности дыхания",
    "Страх смерти",
    "Ощущение страха",
    "Нервозность",
    "Ощущение удушья",
    "Тремор рук",
    "Чувство дрожи",
    "Плохой сон",
    "Ощущение ужаса",
    "Расстройства желудка",
    "Головная боль",
    "Чувство слабости в ногах"
]
user_anxiety_state = {}  # {user_id: {'step': int, 'answers': []}}
@bot.message_handler(func=lambda msg: msg.text == '📊 Тест тревоги')
def start_anxiety_test(message):
    uid = message.from_user.id
    user_anxiety_state[uid] = {'step': 0, 'answers': []}
    send_anxiety_question(message.chat.id, uid)
def send_anxiety_question(chat_id, uid):
    step = user_anxiety_state[uid]['step']
    question = anxiety_test_data[step]

    markup = types.InlineKeyboardMarkup(row_width=4)
    for i in range(4):
        markup.add(types.InlineKeyboardButton(str(i), callback_data=f'anx_{i}'))

    bot.send_message(
        chat_id,
        f"{step+1}. {question}\n\nОтветь по шкале:\n0 — совсем не беспокоило\n1 — немного\n2 — сильно\n3 — очень сильно",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('anx_'))
def handle_anxiety_answer(call):
    uid = call.from_user.id
    if uid not in user_anxiety_state:
        return

    score = int(call.data.split('_')[1])
    user_anxiety_state[uid]['answers'].append(score)
    user_anxiety_state[uid]['step'] += 1

    if user_anxiety_state[uid]['step'] < len(anxiety_test_data):
        send_anxiety_question(call.message.chat.id, uid)
    else:
        show_anxiety_result(call.message.chat.id, uid)

def show_anxiety_result(chat_id, uid):
    answers = user_anxiety_state[uid]['answers']
    total_score = sum(answers)
    del user_anxiety_state[uid]

    # Пользователю
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📨 Отправить результат Стасу", callback_data='anx_send_to_admin'))
    bot.send_message(
        chat_id,
        "Готово! Спасибо, что прошёл тест. Я отправлю результат Стасу — он посмотрит и откликнется тебе бесплатно 💛 Хочешь?",
        reply_markup=markup
    )

    # Храним результат до отправки
    user_anxiety_state[uid] = {
        'final_score': total_score,
        'answers': answers
    }

@bot.callback_query_handler(func=lambda call: call.data == 'anx_send_to_admin')
def send_anxiety_to_admin(call):
    uid = call.from_user.id
    if uid not in user_anxiety_state:
        return

    result = user_anxiety_state.pop(uid)
    total_score = result['final_score']
    answers = result['answers']

    # Интерпретация (только тебе)
    if total_score <= 7:
        level = "Минимальная тревожность"
    elif total_score <= 15:
        level = "Лёгкая тревожность"
    elif total_score <= 25:
        level = "Умеренная тревожность"
    else:
        level = "Выраженная тревожность"

    bot.send_message(
        ADMIN_ID,
        f"🧠 ТЕСТ ТРЕВОГИ\n"
        f"От пользователя: {uid}\n\n"
        f"Суммарный балл: {total_score}\n"
        f"Уровень: {level}\n"
        f"Ответы: {answers}"
    )

    bot.send_message(
        call.message.chat.id,
        "Спасибо 💛 Стас получил твой тест. Он посмотрит и напишет тебе лично 🌿"
    )



depression_test_data = [
    ("0 — Я не чувствую себя расстроенным.\n"
     "1 — Я чувствую себя расстроенным чаще, чем обычно.\n"
     "2 — Я всегда расстроен и не могу избавиться от этого.\n"
     "3 — Я настолько расстроен и несчастен, что не могу этого вынести."),

    ("0 — Я не обеспокоен своим будущим.\n"
     "1 — Меня беспокоит, что в будущем могут быть проблемы.\n"
     "2 — Я чувствую, что будущее выглядит мрачно.\n"
     "3 — Я убежден, что будущего нет."),

    ("0 — Я не чувствую себя неудачником.\n"
     "1 — Я считаю, что терпел больше неудач, чем другие.\n"
     "2 — Когда я оглядываюсь на свою жизнь, я вижу только неудачи.\n"
     "3 — Я чувствую, что был полным неудачником."),

    ("0 — Я получаю столько же удовлетворения от вещей, как раньше.\n"
     "1 — Я не получаю столько же удовольствия, как раньше.\n"
     "2 — Я больше не получаю настоящего удовлетворения от чего-либо.\n"
     "3 — Я совсем не удовлетворен ничем."),

    ("0 — Я не чувствую вины.\n"
     "1 — Я часто чувствую вину.\n"
     "2 — Я чувствую вину большую часть времени.\n"
     "3 — Я чувствую вину всё время."),

    ("0 — Я не чувствую, что заслуживаю наказания.\n"
     "1 — Я чувствую, что, возможно, заслуживаю наказания.\n"
     "2 — Я чувствую, что заслуживаю наказания.\n"
     "3 — Я хочу быть наказанным."),

    ("0 — Я не разочарован в себе.\n"
     "1 — Я разочарован в себе.\n"
     "2 — Я не люблю себя.\n"
     "3 — Я ненавижу себя."),

    ("0 — Я не чувствую себя хуже, чем другие.\n"
     "1 — Я критикую себя за ошибки и слабости.\n"
     "2 — Я виню себя всё время за всё.\n"
     "3 — Я обвиняю себя во всех плохих вещах, что происходят."),

    ("0 — Я никогда не думал покончить с собой.\n"
     "1 — У меня бывают мысли покончить с собой, но я не стал бы этого делать.\n"
     "2 — Я хотел бы покончить с собой.\n"
     "3 — Я бы покончил с собой, если бы имел возможность."),

    ("0 — Я плачу не чаще, чем обычно.\n"
     "1 — Сейчас я плачу чаще, чем раньше.\n"
     "2 — Я всё время плачу.\n"
     "3 — Раньше я мог плакать, но теперь не могу, даже если хочу."),

    ("0 — Я не более раздражителен, чем обычно.\n"
     "1 — Я немного более раздражителен, чем обычно.\n"
     "2 — Я намного более раздражителен, чем раньше.\n"
     "3 — Я постоянно раздражен."),

    ("0 — Я не потерял интерес к другим людям.\n"
     "1 — Меня меньше интересуют другие люди, чем раньше.\n"
     "2 — Я почти потерял интерес к другим людям.\n"
     "3 — Я полностью утратил интерес к другим людям."),

    ("0 — Я откладываю принятие решений не чаще, чем обычно.\n"
     "1 — Я чаще, чем обычно, затрудняюсь принимать решения.\n"
     "2 — Мне трудно принимать какие-либо решения.\n"
     "3 — Я больше не могу принимать решения вообще."),

    ("0 — Я не чувствую, что выгляжу хуже, чем раньше.\n"
     "1 — Я обеспокоен тем, что выгляжу старым или непривлекательным.\n"
     "2 — Я чувствую, что выгляжу некрасиво.\n"
     "3 — Я уверен, что выгляжу ужасно."),

    ("0 — Я могу работать так же, как и раньше.\n"
     "1 — Мне нужно приложить дополнительные усилия, чтобы начать делать что-либо.\n"
     "2 — Мне очень трудно заставить себя что-либо делать.\n"
     "3 — Я совсем не могу выполнять никакую работу."),

    ("0 — Я сплю не хуже, чем обычно.\n"
     "1 — Я сплю немного хуже, чем обычно.\n"
     "2 — Я просыпаюсь на 1–2 часа раньше и мне трудно снова уснуть.\n"
     "3 — Я просыпаюсь за несколько часов до обычного и больше не могу уснуть."),

    ("0 — Я не устаю больше, чем обычно.\n"
     "1 — Я устаю быстрее, чем обычно.\n"
     "2 — Я устаю почти от всего, что я делаю.\n"
     "3 — Я слишком устал, чтобы что-либо делать."),

    ("0 — У меня обычный аппетит.\n"
     "1 — У меня немного хуже аппетит, чем раньше.\n"
     "2 — У меня гораздо хуже аппетит сейчас.\n"
     "3 — У меня совсем нет аппетита."),

    ("0 — Я не потерял много веса.\n"
     "1 — Я потерял более 2 кг.\n"
     "2 — Я потерял более 5 кг.\n"
     "3 — Я потерял более 7 кг."),

    ("0 — Я беспокоюсь о своем здоровье не больше, чем обычно.\n"
     "1 — Я обеспокоен своими физическими проблемами (боль, расстройство желудка и т.п.).\n"
     "2 — Меня очень волнуют мои физические проблемы.\n"
     "3 — Я не могу думать ни о чём, кроме своих физических проблем."),

    ("0 — Я не заметил изменений в моем интересе к сексу.\n"
     "1 — Я менее интересуюсь сексом, чем раньше.\n"
     "2 — Сейчас я гораздо меньше интересуюсь сексом.\n"
     "3 — Я полностью утратил интерес к сексу.")
]

user_depression_state = {}  # {user_id: {'step': int, 'answers': []}}

@bot.message_handler(func=lambda msg: msg.text == '📉 Тест депрессии')
def start_depression_test(message):
    uid = message.from_user.id
    user_depression_state[uid] = {'step': 0, 'answers': []}
    send_depression_question(message.chat.id, uid)

def send_depression_question(chat_id, uid):
    step = user_depression_state[uid]['step']
    question = depression_test_data[step]

    markup = types.InlineKeyboardMarkup()
    for i in range(4):
        markup.add(types.InlineKeyboardButton(str(i), callback_data=f'dep_{i}'))

    bot.send_message(
        chat_id,
        f"{step+1}. Вопрос:\n\n{question}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_'))
def handle_depression_answer(call):
    uid = call.from_user.id
    if uid not in user_depression_state:
        return

    score = int(call.data.split('_')[1])
    user_depression_state[uid]['answers'].append(score)
    user_depression_state[uid]['step'] += 1

    if user_depression_state[uid]['step'] < len(depression_test_data):
        send_depression_question(call.message.chat.id, uid)
    else:
        show_depression_result(call.message.chat.id, uid)

def show_depression_result(chat_id, uid):
    answers = user_depression_state[uid]['answers']
    total_score = sum(answers)
    del user_depression_state[uid]

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📨 Отправить результат Стасу", callback_data='dep_send_to_admin'))

    bot.send_message(
        chat_id,
        "Готово! Спасибо, что прошёл тест. Я отправлю результат Стасу — он посмотрит и откликнется тебе бесплатно 💛 Хочешь?",
        reply_markup=markup
    )

    user_depression_state[uid] = {
        'final_score': total_score,
        'answers': answers
    }
@bot.callback_query_handler(func=lambda call: call.data == 'dep_send_to_admin')
def send_depression_to_admin(call):
    uid = call.from_user.id
    if uid not in user_depression_state:
        return

    result = user_depression_state.pop(uid)
    total_score = result['final_score']
    answers = result['answers']

        # Интерпретация (только тебе)
    if total_score <= 13:
        level = "Минимальная депрессия"
    elif total_score <= 19:
        level = "Лёгкая депрессия"
    elif total_score <= 28:
        level = "Умеренная депрессия"
    else:
        level = "Тяжёлая депрессия"

    bot.send_message(
        ADMIN_ID,
        f"🧠 ТЕСТ ДЕПРЕССИИ\n"
        f"От пользователя: {uid}\n\n"
        f"Суммарный балл: {total_score}\n"
        f"Уровень: {level}\n"
        f"Ответы: {answers}"
    )

    bot.send_message(
        call.message.chat.id,
        "Спасибо 💛 Стас получил твой тест. Он посмотрит и напишет тебе лично 🌿"
    )

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        """Привет!

Я живой бот Стаса Веречука, терапевта подхода «Домой, к себе настоящему». Хорошо, что ты здесь.

С чего начнём?

📅 Сессия-знакомство со скидкой 40%

🔍 Пойти глубже — если хочешь интересный интерактив, а ещё — детальнее о подходе, и наши ресурсы.

🆘 Срочная помощь — если сейчас совсем тяжко.""",
        reply_markup=persistent_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == '📅 Записаться на сессию-знакомство -40%')
def handle_booking(message):
    user_state.pop(message.from_user.id, None)  # сбрасываем логику "срочной помощи"
    human_delay()
    bot.send_message(
        message.chat.id,
        "Ты сделал важный шаг.\n\n"
        "На сессии у тебя будет тёплое и безопасное пространство. "
        "Тебе не нужно готовиться к ней, можешь прийти и просто быть собой.\n\n",
        reply_markup=persistent_keyboard()
    )

    slots = get_next_slots()
    markup = types.InlineKeyboardMarkup()
    for label, dt in slots:
        slot_id = dt.strftime('%Y-%m-%d_%H:%M')
        markup.add(types.InlineKeyboardButton(text=label, callback_data=f"slot_{slot_id}"))

    bot.send_message(message.chat.id, "📅 Выбери удобное тебе время:", reply_markup=markup)

    human_delay()
    bot.send_message(message.chat.id, "Если остались вопросы — можешь написать Стасу: @anxstas", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🆘 Срочная помощь')
def handle_emergency(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("🙏 Спасибо ❤️")
    markup.add("📅 Записаться на сессию-знакомство")
    markup.add("🔍 Пойти глубже")  # <–– вот эта строка новая
    human_delay()
    bot.send_message(message.chat.id, "Ты зашёл сюда не просто так.")
    human_delay()
    bot.send_message(message.chat.id, "Давай вместе сделаем так, чтобы тебе стало хоть чуточку легче.")
    human_delay()
    bot.send_message(message.chat.id, "Расскажи немного, что с тобой? И я помогу тебе поддержкой, теплом и действенными техниками.\n\nПросто пиши мне в чат 👇 Прямо сейчас, без всяких приветствий. Что там с тобой? Поделись, пожалуйста...",  reply_markup=persistent_keyboard())
    user_state[message.from_user.id] = 1

@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))
def handle_slot_choice(call):
    slot_raw = call.data.split("slot_")[1]
    user_selected_slots[call.from_user.id] = slot_raw
    dt_text = datetime.strptime(slot_raw, "%Y-%m-%d_%H:%M").strftime('%A %d %B • %H:%M')

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Оплатить", url="https://moneyyyyyy.carrd.co/"))
    markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid_done"))

    bot.send_message(call.message.chat.id, f"Ты выбрал: {dt_text}\n\nПожалуйста, оплати, чтобы подтвердить запись:", reply_markup=markup)
    bot.send_message(call.message.chat.id, "Если что-то не получается — напиши Стасу: @anxstas", reply_markup=persistent_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "paid_done")
def confirm_payment(call):
    user_id = call.from_user.id
    slot_str = user_selected_slots.get(user_id)
    if not slot_str:
        bot.send_message(call.message.chat.id, "Не удалось найти выбранное время.")
        return

    dt = datetime.strptime(slot_str, "%Y-%m-%d_%H:%M")

    start = dt.strftime('%Y%m%dT%H%M00Z')
    end = (dt + timedelta(hours=1)).strftime('%Y%m%dT%H%M00Z')

    calendar_link = (
        f"https://www.google.com/calendar/render?action=TEMPLATE"
        f"&text=Сессия+со+Стасом"
        f"&dates={start}/{end}"
        f"&details=Клиент+подтвердил+оплату"
        f"&location=Telegram"
    )

    # Формат для человека (воскресенье, 13 апреля в 13:00)
    days = {
        "Monday": "понедельник", "Tuesday": "вторник", "Wednesday": "среду",
        "Thursday": "четверг", "Friday": "пятницу", "Saturday": "субботу", "Sunday": "воскресенье"
    }
    months = {
        "January": "января", "February": "февраля", "March": "марта",
        "April": "апреля", "May": "мая", "June": "июня",
        "July": "июля", "August": "августа", "September": "сентября",
        "October": "октября", "November": "ноября", "December": "декабря"
    }

    day_name = days[dt.strftime("%A")]
    day = dt.strftime("%d")
    month = months[dt.strftime("%B")]
    time = dt.strftime("%H:%M")
    human_date = f"{day_name}, {day} {month} в {time}"

    # Сообщения клиенту
    bot.send_message(call.message.chat.id, "Спасибо! Ты записан. Вот ссылка, чтобы добавить встречу в календарь:")
    bot.send_message(call.message.chat.id, calendar_link)
    bot.send_message(call.message.chat.id, f"Я жду тебя в {human_date} 🌞", reply_markup=persistent_keyboard())
    bot.send_message(call.message.chat.id, "Установи Google Meet для связи, перед сессией я пришлю тебе ссылку.")
    bot.send_message(call.message.chat.id, "И можешь пока что «Пойти глубже», чтобы посмотреть, что там у нас 👇")

    # Кнопки
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Пойти глубже", "🆘 Срочная помощь")
    bot.send_message(call.message.chat.id, reply_markup=markup)

    # Уведомление админу
    bot.send_message(ADMIN_ID, f"📬 Новый клиент записан на: {human_date}\nTelegram ID: {user_id}")

def get_techniques_block():
    return (
        "Попробуй сейчас сделать вот это. Наполную, без жалости к себе — и тревоги точно станет меньше:\n\n"
        "1. Дыхание 4-7-8\n"
        "Вдох 4 сек, пауза 7 сек, выдох 8 сек. Делай так 5 минут — просто наблюдай, как воздух проходит через нос и глубже.\n\n"
        "⬜⬜⬜\n\n"
        "2. Выпиши всё, что внутри\n"
        "Все свои мысли, всё, что парит — без критики, без обдумывания. Просто пиши всё как идёт.\n\n"
        "⬜⬜⬜\n\n"
        "3. Движение против тревоги\n"
        "Сделай 10 отжиманий, 20 приседаний — и так 3 подхода. Можно сильно устать, и это хорошо.\n\n"
        "⬜⬜⬜\n\n"
        "4. Упражнение \"5-4-3-2-1\"\n"
        "Найди: 5 предметов, которые видишь, 4 - которые слышишь, 3 — трогаешь, 2 — чувствуешь, 1 — можешь съесть.\n" 
        "И в каждый из них вчувствуйся максимально. Рассматривай до деталей. Слушай до тишины. Трогай до мурашек. Чувствуй как будто ты кот(шка). Ешь до слюнек.\n\n"
        "⬜⬜⬜\n\n"
        "Хочешь — можно заглянуть в твою тревогу глубже со Стасом на сессии. Он очень бережно помогает возвращаться домой — в свою настоящесть.\n\n"
    )

@bot.message_handler(func=lambda msg: msg.text == '🙏 Спасибо ❤️')
def handle_thanks(message):
    user_state.pop(message.from_user.id, None)
    time.sleep(random.uniform(1.0, 2.3))
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(1.0, 2.3))
    bot.send_message(message.chat.id, "Возвращаю в главное меню.", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '❤️ Тепло')
def handle_warmth(message):
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.5))
    bot.send_message(message.chat.id, "Представь, что ты в теплом и мягком пледе, таком, из детства, пушистом, за окном мерцает тёплый свет, а рядом с тобой — кто-то близкий и очень заботливый. Тот, кто любит тебя. И никуда не торопит. Тебе никуда не надо бежать.")

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.4))
    bot.send_message(message.chat.id, "Тебе не нужно ничего доказывать, никуда спешить. Просто побудь в этом пространстве... в этом пледе.")

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.4))
    bot.send_message(message.chat.id, "Ты имеешь право чувствовать всё, что ты чувствуешь. Всё, что с тобой — имеет смысл и значение. И я здесь, чтобы побыть рядом хотя бы немного.")

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.4))
    bot.send_message(message.chat.id, "Если внутри всё запутано — это нормально. Позволь себе быть сейчас без ответов, без решений. Тепло приходит не с ответами, а с тем, кто рядом.")

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.4))
    bot.send_message(message.chat.id, "Мне важно быть рядом с тобой. Обнимаю тебя.")

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.5))
    bot.send_message(message.chat.id, "Хочешь — можно заглянуть в это глубже со Стасом на сессии? Он очень бережно помогает возвращаться домой — в свою настоящесть.")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📅 Записаться на сессию-знакомство")
    markup.add("🙏 Спасибо 💛")
    markup.add("🌸 Наши теплые приколюшечки")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2

@bot.message_handler(func=lambda msg: msg.text == '🧘 Техники')
def handle_techniques(message):

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.5))
    bot.send_message(message.chat.id, get_techniques_block())

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📅 Записаться на сессию-знакомство")
    markup.add("🙏 Спасибо 💛")
    markup.add("🌸 Наши теплые приколюшечки")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📅 Записаться на сессию-знакомство")
    markup.add("🙏 Спасибо 💛")
    markup.add("🌸 Наши теплые приколюшечки")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("❤️ Тепло", "🧘 Техники")
    markup.add("🙏 Спасибо", "🏠 На главную")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🙏 Спасибо", "🏠 На главную")
    bot.send_message(message.chat.id, "Выбери, пожалуйста, что дальше", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🏠 На главную")
def go_main_menu(message):
    user_state.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🙏 Спасибо")
def handle_thanks(message):
    user_state.pop(message.from_user.id, None)
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(1.5, 2.3))
    bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🙏 Спасибо 💛")
def handle_thanks_yellow(message):
    user_state.pop(message.from_user.id, None)
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(1.5, 2.3))
    bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🌸 Наши теплые приколюшечки')
def cute_stuff(message):
    user_state[message.from_user.id] = 'cute_menu'

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🌀 Что я чувствую", "🌊 Море тишины")
    markup.add("📓 Я — дневник", "🔙 Назад")
    markup.add("🌀 Пойдешь ещё глубже?")

    bot.send_message(
        message.chat.id,
        "Вот наши теплые приколюшечки 👇\nВыбери что-то для себя прямо сейчас 💛",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == '🌊 Море тишины')
def handle_sea_of_silence(message):
    user_state.pop(message.from_user.id, None)

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(2)
    bot.send_message(
        message.chat.id,
        "Тут ничего не надо. Просто тишина, дыхание и ты.\n\n"
        "Если хочешь — включи что-то из этого:"
    )

            # Гифка с морем
    bot.send_chat_action(message.chat.id, 'upload_video')
    bot.send_animation(
        message.chat.id,
        animation='https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif',  # мягкая, расслабляющая гифка
        caption="🌊 Мягкие волны для твоего внутреннего спокойствия"
    )

            # Кнопки с шумами
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎧 Шум дождя", url="https://www.rainymood.com/"))
    markup.add(types.InlineKeyboardButton("🌿 Звуки природы", url="https://asoftmurmur.com/"))
    markup.add(types.InlineKeyboardButton("🧘 Я просто хочу здесь побыть", callback_data='just_be_here'))

    bot.send_message(message.chat.id, "Выбери, если хочешь:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'just_be_here')
def handle_just_be_here(call):
    bot.send_chat_action(call.message.chat.id, 'typing')
    time.sleep(1.5)
    bot.send_message(
        call.message.chat.id,
    "Будь здесь, сколько захочешь.\n\nМесто внутри себя — самое прекрасное место на Земле. Зачастую испещренное ранами, но от этого еще и уникальное. Которое так хочет заботы. И, конечно, повтыкай на кота, у него можно поучиться настоящести 💛"
    )
    
@bot.message_handler(func=lambda msg: msg.text == '📓 Я — дневник')
def handle_diary_start(message):
    user_state[message.from_user.id] = 'waiting_diary_entry'
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(1.5)
    bot.send_message(
        message.chat.id,
        "Хочешь записать, что сейчас внутри?\n\nМожешь написать прямо сюда. А я просто побуду рядом."
    )


@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'waiting_diary_entry')
def handle_diary_entry(message):
    user_state.pop(message.from_user.id, None)

    # Сохраняем запись в файл
    with open('diary_entries.txt', 'a', encoding='utf-8') as f:
        f.write(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — user {message.from_user.id}:\n{message.text.strip()}\n\n"
        )

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(2)
    bot.send_message(
        message.chat.id,
        "Спасибо, что поделился. Это важно.\nТвои слова здесь в безопасности. 💛"
    )

@bot.message_handler(func=lambda msg: msg.text == '🌀 Что я чувствую')
def handle_emotional_radar(message):
    user_state[message.from_user.id] = 'emotion_wait'

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "😊 Радость", "😟 Тревога", "😢 Грусть",
        "😠 Злость", "😱 Страх", "😔 Стыд",
        "🤢 Отвращение", "⚖️ Вина",
        "🔙 Назад"
    )

    bot.send_message(
        message.chat.id,
        "Что ты чувствуешь сейчас?\nВыбери одно — и мы побудем в этом вместе 💛",
        reply_markup=markup
    )


@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'emotion_wait')
def respond_to_emotion(message):
    feeling = message.text.strip().lower()
    user_state.pop(message.from_user.id, None)

    responses = {
        "😊 радость": (
            "Это прекрасно 💛 Радость — это ресурс. Постарайся запомнить это состояние телом.\n\n"
            "🔸 Микропрактика: положи руку на грудь. Скажи: *Я разрешаю себе радоваться.*\n"
            "Пусть тело запомнит это.\n\n"
            "Если захочешь — возвращайся позже, я здесь."
        ),
        "😟 тревога": (
            "Я рядом. Тревога — это не враг. Это сигнал о том, что тебе важно.\n\n"
            "🔸 Попробуй: вдохни на 4, задержи дыхание на 4, выдохни на 6. Повтори 5 раз.\n"
            "Это даст телу сигнал: 'всё безопасно'.\n\n"
            "Можешь написать мне позже, когда захочешь снова быть услышанным."
        ),
        "😢 грусть": (
            "Грусть бывает, когда мы что-то теряем. Даже если это было воображаемое. Я рядом.\n\n"
            "🔸 Упражнение: обними себя руками, закрой глаза и побудь так 2 минуты.\n"
            "Это поддержка, которой мы часто недополучаем.\n\n"
            "Хочешь — возвращайся, я буду тут."
        ),
        "😠 злость": (
            "Злость — энергия. Она показывает границы. Спасибо, что ты с ней.\n\n"
            "🔸 Техника: возьми лист бумаги и напиши на нём всё, что злишься. Без цензуры.\n"
            "Потом можешь порвать.\n\n"
            "Это важно — прожить. Я рядом, если захочешь вернуться."
        ),
        "😱 страх": (
            "Страх — сигнал, что тебе что-то важно и есть риск. Ты живой, и ты заботишься.\n\n"
            "🔸 Попробуй: сядь, почувствуй опору под собой, скажи вслух: *Я в безопасности.*\n"
            "Подыши глубоко. Почувствуй, как ты дышишь.\n\n"
            "Если вернёшься — я буду рядом."
        ),
        "😔 стыд": (
            "Стыд — это про потребность быть принятым. Ты не один в этом.\n\n"
            "🔸 Напиши себе: *Я достаточно хороший, даже с этим чувством.*\n"
            "Просто прочти это 3 раза. Это уже много.\n\n"
            "Захочешь — возвращайся."
        ),
        "🤢 отвращение": (
            "Отвращение говорит: *это не моё*, *я не хочу быть с этим рядом*.\n\n"
            "🔸 Можешь буквально оттолкнуть это жестом. Или нарисовать и выбросить.\n"
            "Это — граница. Она важна.\n\n"
            "Я здесь, если захочешь поговорить ещё."
        ),
        "⚖️ вина": (
            "Вина может говорить о том, что тебе важны отношения или внутренние ценности. Это чувство часто даёт шанс восстановить что-то ценное.\n\n"
            "🔸 Попробуй: напиши себе фразу — *Я сделал(а) ошибку, но я не ошибка.*\n"
            "Затем подумай: что я могу сделать сейчас, чтобы пойти в сторону ценностей?\n\n"
            "Я рядом. Ты не один в этом."
        ),
    }

    response = responses.get(feeling)
    if response:
        bot.send_message(message.chat.id, response, reply_markup=persistent_keyboard())
    else:
        bot.send_message(message.chat.id, "Я не совсем понял, что ты чувствуешь. Выбери одну из эмоций ниже 💛")


@bot.message_handler(func=lambda msg: msg.text not in [
    '📅 Записаться на сессию-знакомство',
    '🔍 Пойти глубже',
    '🆘 Срочная помощь',
    '🧘 О подходе «Домой, к себе настоящему»',
    '📌 Наши полезности',
    '🌸 Наши теплые приколюшечки',
    '🗣 Обратная связь',
    '🔙 Назад'
])

def gpt_flow(message):
    import random, time
    uid = message.from_user.id
    if user_state.get(uid) is None:
        return
    text = message.text.strip()
    lowered = text.lower()
    step = user_state.get(uid, 1)

    if step == 1:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(random.uniform(1.0, 2.4))
        bot.send_message(message.chat.id, "Спасибо, что делишься. Я тебя слышу. Всё, что ты чувствуешь — важно и имеет смысл... Я с тобой в этом, насколько могу.")

        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(random.uniform(1.0, 2.0))
        bot.send_message(message.chat.id, "Если у тебя что-то очень серьёзное, напиши Стасу лично на @anxstas — он обязательно прочитает и ответит. Это бесплатно.")

        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(random.uniform(1.0, 2.1))
        bot.send_message(message.chat.id, "Или хочешь — побудем в этом немного вместе? Я могу дать тебе чуточку тепла и поддержки, предложить быстрые техники снижения тревожности, а, если ты мне опишешь проблему, то и свежий взгляд со стороны.")

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("❤️ Тепло", "🧘 Техники", "🌀 Пойти глубже", "🔙 Назад")

        bot.send_message(message.chat.id, "Как я могу тебя поддержать? Выбери внизу 👇 Что тебе сейчас ближе?", reply_markup=markup)
        user_state[uid] = 2
        return

    # 🔍 Пойти глубже — открывает разделы
@bot.message_handler(func=lambda msg: msg.text == '🔍 Пойти глубже')
def handle_deeper(message):
    user_state.pop(message.from_user.id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🧘 О подходе «Домой, к себе настоящему»")
    markup.add("📌 Наши полезности")
    markup.add("🌸 Наши теплые приколюшечки")
    markup.add("🗣 Обратная связь")
    markup.add("🔙 Назад")
    bot.send_message(message.chat.id, "Выбери, что тебе интересно:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🧘 О подходе «Домой, к себе настоящему»')
def about_method(message):
    user_state.pop(message.from_user.id, None)
    text = (
        "Загляни к нам на сайт, там чуть больше о Стасе Веречуке, и вкратце о его терапевтическом подходе по преодолению тревоги и депрессии.\n\n"
        "А если хочешь разобраться поглубже, то почитай концепцию подхода."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🌐 Сайт", url="https://anxstas.github.io/"),
        types.InlineKeyboardButton("📖 Концепция", url="https://page.genspark.site/page/toolu_01MDfAf2WCfQ9Bey23eeESjN/%D0%B4%D0%BE%D0%BC%D0%BE%D0%B9_%D0%BA_%D1%81%D0%B5%D0%B1%D0%B5_%D0%BD%D0%B0%D1%81%D1%82%D0%BE%D1%8F%D1%89%D0%B5%D0%BC%D1%83_%D1%84%D0%B8%D0%BD%D0%B0%D0%BB.html")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)
    bot.send_message(message.chat.id, "И всегда можно вернуться в главное меню 👇", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '📌 Наши полезности')
def resources(message):
    user_state.pop(message.from_user.id, None)
    text = (
        "Тут - много всего на важные тревожно-депрессивные темы.\n\n" 
        "Я буду рад видеть тебя среди своих подписчиков. Только так я смогу развиваться и давать людям больше пользы.\n\n"
        "▶️ YouTube о тревоге и депрессии (и чуть-чуть личного)\n\n"
        "📸 Instagram о тревоге и депрессии (и побольше личного)\n\n"
        "✉️ Telegram о тревоге и депрессии (и чуть-чуть науки)\n\n"
        "📘 Facebook — где личное, и немного о тревоге и депрессии"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("YouTube", url="https://www.youtube.com/@anxstas"),
        types.InlineKeyboardButton("Instagram", url="https://www.instagram.com/verechuk_/"),
        types.InlineKeyboardButton("Telegram", url="https://www.t.me/domminside"),
        types.InlineKeyboardButton("Facebook", url="https://www.facebook.com/stanislav.verechuk/")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🗣 Обратная связь')
def feedback(message):
    user_state.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "Здесь ты можешь написать всё, что думаешь о нём — об этом неидеальном, но точно живом и настоящем человеке.\n\n"
        "Он будет благодарен тебе за каждую твою буковку 🌞"
    )

@bot.message_handler(func=lambda msg: msg.text == '🔙 Назад')
def handle_back(message):
    if user_state.get(message.from_user.id) not in ['waiting_letter_text', 'waiting_letter_text_year']:
        user_state.pop(message.from_user.id, None)
    step = user_state.get(message.from_user.id)

    # если пользователь был в старой логике — возвращаем поддерживающее меню
    if step in [2, 'after_response']:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("❤️ Тепло", "🧘 Техники", "🌀 Пойти глубже", "🔙 Назад")
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(random.uniform(1.5, 2.5))
        bot.send_message(message.chat.id, "Как я могу тебя поддержать? Выбери внизу 👇", reply_markup=markup)
        user_state[message.from_user.id] = 2

    # если пользователь после свежего взгляда — сразу в главное меню
    elif step == 'fresh_view_done':
        user_state.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())

    else:
        user_state.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())


@bot.message_handler(commands=['завершить','end'])
def finish_chat(message):
    bot.send_message(message.chat.id, "🌿 Спасибо за доверие. Если захочешь вернуться — я рядом.", reply_markup=persistent_keyboard())
    user_state.pop(message.from_user.id, None)


    logging.info("Бот запущен")


@app.route(f"/bot{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

metaphoric_cards = [
"""## 1. Клетка без дверей

Мы строим невидимые тюрьмы из своих убеждений, страхов и привычных паттернов мышления. Эти стены кажутся непреодолимыми, хотя существуют только в нашем восприятии. Парадокс свободы в том, что самые прочные цепи — те, которые мы сами продолжаем носить после того, как замок давно открыт. Иногда мы остаемся в клетке, потому что несвобода стала частью нашей идентичности, и выход пугает больше, чем заточение.

**Вопросы в глубину:**

- Если бы твои ограничения оказались иллюзией, что было бы для тебя самым страшным в этом открытии?

- Какую тайную выгоду ты получаешь, считая себя несвободным?

- Что произойдет, если ты просто сделаешь шаг за пределы того, что считаешь возможным?""",
"""## 2. Маски безопасности

Каждый из нас носит множество масок — они защищают нас от уязвимости, от страха быть отвергнутыми, от встречи с неизвестным в себе. Мы надеваем маску силы, когда чувствуем слабость; маску безразличия, когда нам больно; маску уверенности, когда мы потеряны. С течением времени мы забываем, что это лишь маски, и принимаем их за свое истинное лицо. Но подлинная безопасность возникает только тогда, когда мы осмеливаемся показать миру свою незащищенность.

**Вопросы в глубину:**

- Какая маска стала настолько привычной, что ты считаешь ее своим лицом?

- Чего ты боишься больше всего, если снимешь свою защитную маску?

- Кто тот, кто смотрит из-за всех твоих масок — тот, кого ты, возможно, не видел очень давно?""",
"""## 3. Танец с тенью

Все, что мы отрицаем в себе, не исчезает, а становится тенью — теми аспектами личности, которые мы вытеснили из сознания. Чем сильнее мы отвергаем эти части, тем больше власти они приобретают над нашей жизнью. Они проявляются в наших реакциях, проекциях, сновидениях, в том, что нас раздражает в других. Интеграция тени — это не борьба с ней, а приглашение ее к танцу, к диалогу, признание ее существования и мудрости.

**Вопросы в глубину:**

- Какие качества или эмоции ты больше всего осуждаешь в других, и как они могут быть отражением твоей собственной непризнанной тени?

- Что бы сказала твоя тень, если бы получила голос? Какие непризнанные потребности она выражает?

- Как изменилась бы твоя жизнь, если бы ты перестал тратить энергию на подавление тех частей себя, которые считаешь неприемлемыми?""",
"""## 4. Река времени

Время — это не линейный поток от прошлого к будущему, а многомерная река, в которой мы существуем постоянно меняющимся присутствием. Мы часто живем не в настоящем, а в воображаемых реальностях — в ностальгии по прошлому, которого больше нет, или в тревоге о будущем, которое может никогда не наступить. Но лишь в точке "сейчас" мы обладаем силой действия и выбора. Только здесь, в настоящем моменте, жизнь действительно происходит.

**Вопросы в глубину:**

- Где ты проводишь большую часть своего внутреннего времени — в воспоминаниях о прошлом, в планировании будущего или в тотальном присутствии в настоящем?

- Что ты откладываешь "на потом", словно у тебя в запасе вечность?

- Если бы ты мог полностью присутствовать в своей жизни прямо сейчас, без бегства в прошлое или будущее, что бы изменилось?""",
"""## 5. Смерть как советчик

Осознание конечности существования — не повод для отчаяния, а самый мощный катализатор подлинной жизни. Смерть срывает пелену иллюзий, обнажая то, что действительно имеет значение. В свете смертности наши страхи мнения других, наша откладываемая жизнь, наши мелкие обиды теряют власть. Остается только самое существенное — любовь, смысл, подлинность, проживание каждого момента в его полноте.

**Вопросы в глубину:**

- Если бы ты знал, что у тебя остался ровно один год жизни, что бы ты перестал терпеть и откладывать?

- Чего ты будешь больше всего жалеть на смертном одре, если продолжишь жить так, как живешь сейчас?

- Что для тебя значит "прожить жизнь полностью", не оставив непрожитых частей?""",
"""## 6. Архитектура идентичности

Мы создаем себя каждый день через истории, которые рассказываем о себе. Эти нарративы определяют, кто мы есть, что возможно для нас, какие границы мы не можем переступить. Но мы — не только авторы этих историй, но и их персонажи. Мы забываем, что можем переписать свою историю в любой момент, изменить фокус повествования, увидеть альтернативные интерпретации тех же событий. Наша идентичность — не фиксированная реальность, а творческий, развивающийся процесс.

**Вопросы в глубину:**

- Какую историю о себе ты рассказываешь так часто, что она стала твоей клеткой?

- Если бы ты мог переписать историю своей жизни из точки силы, а не жертвы, как бы она звучала?

- Какие возможности открываются, если признать, что ты — не только персонаж, но и автор своей истории?""",
"""## 7. Зеркала отношений

Наши отношения с другими людьми — это система зеркал, в которых мы видим отражения различных аспектов себя. То, что привлекает нас в других, часто указывает на наши скрытые потенциалы; то, что раздражает — на непризнанные тени. В глубоком смысле, все наши отношения — это отношения с самими собой. Не существует "другого" вне нашего восприятия, проекций, ожиданий. Осознание этого не обесценивает отношения, а углубляет их, превращая в пространство взаимного роста и самопознания.

**Вопросы в глубину:**

- Какие качества в других людях вызывают у тебя самую сильную эмоциональную реакцию, и что эти реакции говорят о твоих непризнанных аспектах?

- Какими глазами ты смотришь на своих близких — глазами любви, принятия, или глазами суждения, исправления, контроля?

- Что, если все твои отношения — это приглашение встретиться с разными частями себя?""",
"""## 8. Колодец страданий

Страдание неизбежно в человеческой жизни, но существует разница между естественной болью жизни и дополнительным страданием, которое мы создаем своим сопротивлением. Мы углубляем колодец страданий через привязанность к определенным исходам, через отрицание того, что есть, через повторение историй о своей боли. Принятие не означает пассивность или капитуляцию — это акт глубокого мужества, позволяющий трансформировать даже самую глубокую боль в источник мудрости и сострадания.

**Вопросы в глубину:**

- Как ты поддерживаешь свое страдание через истории, которые постоянно повторяешь о себе?

- Какое страдание в твоей жизни является необходимой частью роста, а какое — лишь результатом сопротивления реальности?

- Что случится, если ты перестанешь бороться с тем, что не можешь изменить, и направишь эту энергию на то, что в твоей власти?""",
"""## 9. Пустота и полнота

Мы часто боимся пустоты — эмоциональной, социальной, экзистенциальной — и заполняем свою жизнь постоянной активностью, отношениями, информацией. Но именно в пустоте рождаются новые возможности. Как в музыке паузы между нотами создают мелодию, так в жизни интервалы тишины, уединения, неделания позволяют проявиться более глубоким аспектам бытия. Настоящая полнота жизни часто приходит через принятие пустоты, а не через бегство от нее.

**Вопросы в глубину:**

- Чего ты боишься встретить в тишине и одиночестве?

- Как бы изменилась твоя жизнь, если бы ты перестал заполнять каждую паузу активностью, развлечениями, шумом?

- Что если пустота, которой ты так боишься — это не отсутствие, а присутствие чего-то более глубокого, что невозможно ухватить привычным сознанием?""",
"""## 10. Весы ответственности

Быть ответственным означает признать себя автором своей жизни, но не контролером всей вселенной. Мы часто раскачиваемся между двумя крайностями: берем на себя ответственность за то, что вне нашего контроля (чувства других, непредвиденные обстоятельства), и отрицаем ответственность за то, что полностью в нашей власти (наши реакции, выборы, действия). Зрелость приходит с пониманием разницы между тем, что мы можем изменить, и тем, что нам следует принять.

**Вопросы в глубину:**

- За что в своей жизни ты берешь ответственность, которая тебе не принадлежит?

- От какой ответственности ты отказываешься, хотя она полностью твоя?

- Как изменилась бы твоя жизнь, если бы ты взял 100% ответственности за свои реакции и выборы, и 0% — за обстоятельства и выборы других людей?""",
"""## 11. Корни и крылья

Каждый человек нуждается в балансе между корнями, дающими стабильность и питание, и крыльями, позволяющими расти и исследовать. Когда корни слишком глубоки, мы теряем способность к изменениям; когда крылья слишком сильны без достаточных корней, мы теряем связь с собой и своей основой. Искусство жизни — в нахождении динамического равновесия между принадлежностью и свободой, традицией и новизной, безопасностью базы и риском полета.

**Вопросы в глубину:**

- Что дает тебе корни в жизни — ощущение принадлежности, устойчивости, традиции?

- Что дает тебе крылья — чувство свободы, возможностей, роста?

- В какой сфере жизни ты сейчас нуждаешься в более глубоких корнях, а где тебе пора расправить крылья?""",
"""## 12. Алхимия эмоций

Наши эмоции — не просто реакции на внешние события, а глубокие сигналы внутренней системы ценностей, потребностей и восприятия. Как в древней алхимии, где обычные металлы превращались в золото, так и наши сложные, иногда мучительные эмоции содержат в себе драгоценную мудрость, которую можно извлечь через осознанность. Даже самые тяжелые чувства, если их не подавлять, а проживать с присутствием, могут трансформироваться в источник силы, понимания и глубины.

**Вопросы в глубину:**

- Какие эмоции ты считаешь "плохими" или "неприемлемыми" и пытаешься подавить?

- Что произойдет, если ты позволишь себе полностью прожить эмоцию, не осуждая её и не отождествляясь с ней?

- Какую мудрость несут твои наиболее сложные и болезненные эмоциональные состояния?""",
"""## 13. Кривое зеркало прошлого

Наши воспоминания — не точные записи событий, а постоянно меняющиеся интерпретации, окрашенные нашими убеждениями, эмоциями, текущим состоянием. Мы воссоздаем свое прошлое каждый раз, когда его вспоминаем, усиливая одни аспекты и затеняя другие. Эта пластичность памяти — не только ограничение, но и возможность для исцеления: мы можем переосмыслить свою историю, увидеть в ней новые значения, найти силу там, где раньше видели только травму.

**Вопросы в глубину:**

- Какие истории о своем прошлом ты рассказываешь снова и снова, и как они формируют твое настоящее?

- Какую новую перспективу ты мог бы внести в понимание травматичных или болезненных событий своей жизни?

- Если бы ты мог переписать историю своего прошлого из позиции мудрости и сострадания, а не жертвы, как бы она изменилась?""",
"""## 14. Голод подлинности

За многими нашими желаниями — успеха, признания, безопасности, любви — стоит более глубокий голод: быть подлинным, быть увиденным и принятым в своей истинной сущности. Мы часто пытаемся утолить этот голод внешними достижениями, статусами, отношениями, но это похоже на питье соленой воды — чем больше пьешь, тем сильнее жажда. Подлинное удовлетворение приходит не извне, а из связи с нашей глубинной природой и мужества быть собой.

**Вопросы в глубину:**

- Что ты используешь как "заменитель" для утоления голода подлинности?

- Что для тебя значит "быть собой", и в каких областях жизни тебе это удается меньше всего?

- Как изменилась бы твоя жизнь, если бы ты перестал искать подтверждения своей ценности извне и нашел её источник внутри?""",
"""## 15. Перекресток выбора

Каждый момент жизни — это перекресток, где даже не сделанный выбор является выбором. Мы часто откладываем решения из страха ошибки, не осознавая, что нерешительность сама по себе — это решение в пользу статус-кво. Свобода выбора одновременно дарует нам огромные возможности и возлагает ответственность. Мы создаем себя через цепочку выборов — больших и малых, сознательных и бессознательных.

**Вопросы в глубину:**

- Какой важный выбор ты откладываешь, надеясь, что решение каким-то образом примется само собой?

- Какие ценности и критерии лежат в основе твоих важнейших жизненных решений?

- Если бы ты принимал решения не из страха последствий, а из верности своей глубинной сущности, как бы изменились твои выборы?""",
"""## 16. Маятник контроля

Наша потребность контролировать жизнь — естественное стремление к безопасности, но она часто становится источником страдания в мире, который по своей природе непредсказуем. Мы раскачиваемся между иллюзией полного контроля и чувством полной беспомощности, не находя срединного пути. Истинная мудрость заключается не в абсолютном контроле или бездействии, а в искусстве различать, что в нашей власти изменить, а где нам нужно развивать принятие и гибкость.

**Вопросы в глубину:**

- В каких областях жизни ты пытаешься контролировать то, что находится за пределами твоей власти?

- Как твоя потребность в определенности и предсказуемости ограничивает твою способность к росту и новому опыту?

- Что бы изменилось, если бы ты перенаправил энергию контроля внешнего мира на управление своими внутренними реакциями?""",
"""## 17. Цена непрожитой жизни

Многие из нас проживают жизнь, которая меньше той, на которую мы способны. Мы принимаем привычное за возможное, комфорт за счастье, безопасность за полноту. Но непрожитая жизнь имеет свою цену — она проявляется как смутное беспокойство, тихое отчаяние, экзистенциальная пустота, которую не могут заполнить ни материальный успех, ни развлечения, ни поверхностные отношения. Каждый компромисс с собой, каждое неиспользованное дарование, каждое несказанное "да" жизни накапливается как долг, который в итоге мы платим своей витальностью и радостью.

**Вопросы в глубину:**

- Какие аспекты себя ты не позволяешь проживать полностью из страха риска или неодобрения?

- Что ты будешь больше всего жалеть, если в конце жизни оглянешься на непрожитые возможности?

- Какой первый шаг ты мог бы сделать сегодня в направлении более полной, аутентичной жизни?""",
"""## 18. Песочные часы настоящего

Время не линейно, а многомерно. Верхняя колба песочных часов — наше прошлое, нижняя — будущее, а узкая перемычка между ними — настоящий момент, через который один превращается в другой. Только находясь в полном присутствии "здесь и сейчас", мы обретаем силу трансформировать прошлый опыт и создавать новое будущее. Большинство наших страданий происходит от психологического времени — сожалений о том, что уже случилось, или тревог о том, что может никогда не произойти, в то время как настоящий момент ускользает непрожитым.

**Вопросы в глубину:**

- Сколько времени в течение дня ты действительно присутствуешь в настоящем моменте, а не в ментальных проекциях прошлого или будущего?

- Что удерживает тебя от полного присутствия в своей жизни прямо сейчас?

- Как бы изменился твой опыт, если бы ты перестал воспринимать настоящий момент как средство достижения будущего и начал видеть его как саму жизнь?""",
"""## 19. Архитектура смысла

Смысл не дается нам извне — мы создаем его через отношения, творчество, выборы, даже через то, как мы встречаем страдание. В мире, который часто кажется абсурдным или равнодушным, наша способность создавать и находить смысл — это глубочайший акт человеческой свободы. Смысл не статичен, а динамичен; не универсален, а глубоко личен; не обнаруживается как готовый ответ, а конструируется в процессе проживания жизни с открытостью, вовлеченностью и ответственностью.

**Вопросы в глубину:**

- Что делает твою жизнь осмысленной на самом глубоком уровне?

- Если бы тебе пришлось определить ключевые темы своей жизненной истории, какими бы они были?

- Как ты можешь создавать смысл даже в самых сложных или кажущихся бессмысленными обстоятельствах?""",
"""## 20. Взгляд сквозь маски

Мы живем в мире социальных масок и ролей, которые со временем принимаем за свою истинную сущность. За маской профессионализма, уверенности, компетентности, даже за маской духовности скрывается наша сырая, уязвимая, подлинная человечность. Страх показать эту человечность создает внутренний раскол, чувство одиночества и отчуждения. Подлинная связь с другими возможна только тогда, когда мы осмеливаемся быть видимыми в своей истине, со всеми нашими противоречиями, несовершенствами и красотой.

**Вопросы в глубину:**

- Какую маску ты носишь чаще всего, и что она скрывает?

- Что бы произошло, если бы ты позволил людям увидеть твою подлинную уязвимость, а не только твою силу или компетентность?

- С кем в твоей жизни ты можешь быть полностью собой, без притворства и защитных механизмов?

# Продолжение терапевтических метафорических карт (21-30)""",
"""## 21. Тень отвергнутого ребенка

В каждом взрослом живет внутренний ребенок — та часть нас, которая сохранила детские чувства, потребности и раны. Когда мы отрицаем или подавляем эту часть, она не исчезает, а уходит в тень, управляя нашими реакциями из подсознания. Наши иррациональные страхи, вспышки эмоций, глубокие обиды часто исходят именно из этого внутреннего ребенка, который все еще ждет утешения, признания и любви. Диалог с этим забытым аспектом себя может стать целительным путешествием к собственной целостности.

**Вопросы в глубину:**

- В каком возрасте ты перестал быть собой? Когда научился подавлять свои истинные чувства и желания ради выживания или принятия?

- Какие непрожитые потребности твоего внутреннего ребенка проявляются в твоих сегодняшних реакциях и отношениях?

- Если бы ты мог поговорить с тем маленьким собой, что бы ты сказал ему? И что он, возможно, хотел бы сказать тебе?""",
"""## 22. Экология внутреннего мира

Наш внутренний ландшафт подобен экосистеме, где все элементы взаимосвязаны и нуждаются в гармоничном балансе. Как в природе нарушение одного звена цепи может вызвать каскад изменений во всей системе, так и в психике отрицание или гипертрофия какого-либо аспекта влияет на целое. Мы часто пытаемся устранить "неугодные" элементы нашего внутреннего мира — тревогу, гнев, страх, сексуальность — не понимая, что они выполняют важную функцию в общей экологии души. Здоровье психики — не в устранении "негативных" частей, а в понимании их роли и восстановлении баланса.

**Вопросы в глубину:**

- Какие аспекты своей психической жизни ты считаешь "сорняками", которые пытаешься выполоть или заглушить?

- Как эти отвергаемые части все же служат тебе — какую функцию или защиту они обеспечивают?

- Что значило бы для тебя создать внутреннюю экосистему, где есть место для всех аспектов твоей природы?""",
"""## 23. Границы идентичности

Наша идентичность — не фиксированное ядро, а скорее пространство взаимодействия между различными аспектами нашего опыта. Мы часто воспринимаем себя как отдельное, изолированное существо с четкими границами между "я" и "не-я", но эти границы более проницаемы и условны, чем кажется. Мы постоянно находимся в процессе обмена с окружающим миром — физически, эмоционально, энергетически, информационно. Осознание этой фундаментальной взаимосвязанности не растворяет нашу уникальность, а расширяет ее до более глубокого понимания себя как части более широкого целого.

**Вопросы в глубину:**

- Где для тебя проходит граница между "я" и "не-я"? Относишь ли ты свое тело, эмоции, мысли, отношения, культуру к своей идентичности?

- Как меняется твое самоощущение в разных контекстах и отношениях? Есть ли неизменное "я" за всеми этими изменениями?

- Что бы изменилось в твоем восприятии себя и мира, если бы ты признал фундаментальную взаимосвязь всего существующего?""",
"""## 24. Коллекция идентификаций

Мы накапливаем идентификации, как коллекционер собирает редкие предметы: "я успешный профессионал", "я жертва обстоятельств", "я духовный искатель", "я любящий родитель". Эти самоопределения создают иллюзию стабильности и предсказуемости, но часто становятся клеткой, ограничивающей нашу способность к росту и изменению. Чем сильнее мы цепляемся за определенный образ себя, тем больше энергии тратим на его поддержание и защиту, упуская возможность быть более гибкими, спонтанными и открытыми новому опыту.

**Вопросы в глубину:**

- Какие ярлыки и идентификации ты присвоил себе, и как они ограничивают полноту твоего самовыражения?

- От какого образа себя тебе было бы наиболее больно или страшно отказаться? Что произойдет, если этот образ будет подвергнут сомнению?

- Как изменилось бы твое самоощущение, если бы ты воспринимал себя не как фиксированную сущность, а как постоянно развивающийся процесс?""",
"""## 25. Археология душевных ран

Наши старые травмы и раны не исчезают со временем, если не были осознаны и интегрированы — они становятся фундаментом, на котором мы строим свою жизнь. Как археологи раскапывают древние города, обнаруживая один культурный слой под другим, так и мы можем исследовать слои своего опыта, чтобы понять, на каком основании построены наши нынешние реакции, отношения, убеждения. Часто то, что мы считаем своими личностными чертами или предпочтениями, на самом деле — адаптивные реакции на давно минувшие события. Осознание этой глубинной обусловленности — первый шаг к свободе выбора.

**Вопросы в глубину:**

- Какие ранние раны и травмы продолжают влиять на твою сегодняшнюю жизнь, даже если сознательно ты давно их "преодолел"?

- Какие защитные стратегии ты развил в детстве, которые больше не служат тебе, но от которых трудно отказаться?

- Как бы изменилась твоя жизнь, если бы ты смог исцелить эти глубинные раны, а не просто научился жить с ними?""",
"""## 26. Дом на зыбучих песках

Многие из нас строят дом своей идентичности на зыбучих песках внешних достижений, статуса, ролей, признания других. Эти основания кажутся прочными, пока жизнь не посылает испытания — потерю работы, изменение статуса, разрыв отношений, болезнь. В такие моменты мы чувствуем, как земля уходит из-под ног, потому что потеряли контакт с более глубоким, нерушимым фундаментом своего бытия. Подлинная безопасность приходит не от накопления и защиты внешних атрибутов, а от связи с тем в нас, что остается неизменным среди всех перемен.

**Вопросы в глубину:**

- Какие внешние факторы определяют твое чувство собственной ценности? Что произойдет, если они исчезнут?

- Переживал ли ты моменты, когда рушились основания твоей идентичности? Что ты обнаружил под этими руинами?

- Что для тебя означает построить дом своей жизни на нерушимом фундаменте, а не на зыбучих песках?""",
"""## 27. Багаж непрощения

Непрощение — один из самых тяжелых грузов, который мы несем по жизни. Мы держимся за старые обиды, предательства, разочарования, как будто эта тяжесть защищает нас от новых ран. На самом деле, пытаясь наказать других своим непрощением, мы прежде всего наказываем себя, отравляя собственное настоящее ядом прошлого. Прощение — это не оправдание причиненного вреда и не примирение с обидчиком; это акт освобождения себя от тирании прошлой боли, возвращение себе силы, которую мы отдали тому, кто нас ранил.

**Вопросы в глубину:**

- Какие непрощенные обиды ты носишь в себе годами, и какую цену платишь за это непрощение?

- Какую скрытую выгоду ты получаешь от статуса жертвы, от сохранения своей правоты и чужой неправоты?

- Что для тебя значило бы простить — не для другого человека, а для себя, для своего освобождения?""",
"""## 28. Танец полярностей

Наша психика — это динамическое взаимодействие полярностей: рациональное и интуитивное, контроль и спонтанность, структура и хаос, индивидуация и принадлежность. Мы часто пытаемся выбрать одну сторону и подавить другую, не понимая, что полнота жизни возникает в танце этих противоположностей. Каждый аспект нашей природы имеет свою теневую сторону, которая проявится, если мы будем слишком однобоки. Мудрость заключается не в выборе между полярностями, а в их интеграции, в нахождении гармонии, которая включает и превосходит противоположности.

**Вопросы в глубину:**

- Какие противоположные тенденции ты замечаешь в себе, и как ты обычно пытаешься разрешить это противоречие?

- Какую полярность в себе ты подавляешь или отрицаешь, и как она проявляется в теневой, деструктивной форме?

- Что для тебя означало бы принять и интегрировать обе стороны этой полярности, найдя "третий путь" за пределами простого выбора "или-или"?""",
"""## 29. Зеркальный зал восприятия

Мы воспринимаем мир не таким, какой он есть, а через множество фильтров — убеждений, ожиданий, проекций, предшествующего опыта. Как в зеркальном зале, где один объект отражается бесконечно и в искаженных формах, так и наше восприятие реальности многократно преломляется через призмы нашего ума. Часто мы реагируем не на сам опыт, а на свою интерпретацию этого опыта, принимая карту за территорию. Осознание этих фильтров не делает наше восприятие "объективным", но дает большую свободу в том, как мы решаем интерпретировать свой опыт.

**Вопросы в глубину:**

- Через какие основные фильтры ты смотришь на мир — оптимизм или пессимизм, доверие или подозрительность, изобилие или недостаток?

- Как твое нынешнее эмоциональное состояние влияет на то, что ты видишь и как интерпретируешь происходящее?

- Что бы ты увидел по-другому, если бы осознанно изменил линзы, через которые смотришь на свою ситуацию?""",
"""## 30. Время как холст

Время — наш самый ценный и невосполнимый ресурс, холст, на котором мы рисуем картину своей жизни. Мы часто тратим его так, будто у нас в запасе вечность: откладываем важное, заполняем дни автоматическими действиями, отдаем лучшие часы делам, которые не резонируют с нашими глубинными ценностями. А потом удивляемся, почему жизнь кажется пустой или бессмысленной. Как мы распоряжаемся своим временем — так мы распоряжаемся своей жизнью. Каждый выбор, куда направить этот драгоценный ресурс, это выбор типа человека, которым мы становимся.

**Вопросы в глубину:**

- Если бы ты мог увидеть, как распределялось твое время за последний месяц, что бы это рассказало о твоих истинных приоритетах (а не о тех, которые ты декларируешь)?

- Что входит в твой "список отложенной жизни" — то, что ты собираешься сделать "когда-нибудь", но постоянно откладываешь?

- Если бы ты относился к каждому дню как к драгоценному, невосполнимому ресурсу, как бы изменились твои выборы о том, на что его потратить?""",
]

# === Кнопка: Пойдешь ещё глубже? ===
@bot.message_handler(func=lambda msg: msg.text == "🌀 Пойдешь ещё глубже?")
def handle_go_deeper_intro(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Да", "Нет")
    bot.send_message(
        message.chat.id,
        "Нажми \"Да\" — и получишь важный вопрос.\nНажми \"Нет\" — и иди живи себе дальше 🙂",
        reply_markup=markup
    )

# === Ответ: Нажал Да ===
@bot.message_handler(func=lambda msg: msg.text == "Да")
def handle_deep_yes(message):
    card = random.choice(metaphoric_cards)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Спасибо 💛")
    bot.send_message(message.chat.id, card, reply_markup=markup)

# === Ответ: Нажал Нет ===
@bot.message_handler(func=lambda msg: msg.text == "Нет")
def handle_deep_no(message):
    show_main_menu(message)

# === Спасибо после карты ===
@bot.message_handler(func=lambda msg: msg.text == "Спасибо 💛")
def handle_thanks(message):
    show_main_menu(message)



if __name__ == "__main__":
    print(">>> Устанавливаем webhook:", f"{WEBHOOK_URL}/bot{TELEGRAM_TOKEN}")
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/bot{TELEGRAM_TOKEN}")
    app.run(host="0.0.0.0", port=WEBHOOK_PORT)
