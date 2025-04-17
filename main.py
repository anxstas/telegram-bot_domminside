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
    markup.add('🟡 Записаться на сессию-знакомство -40%')
    markup.add('🤿 Пойти глубже', '🆘 Срочная помощь')
    markup.add('🧞‍♂️ Тест тревоги', '🧞‍♀️ Тест депрессии') 
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

@bot.message_handler(func=lambda msg: msg.text == '🧞‍♂️ Тест тревоги')
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

    if total_score <= 7:
        level = "🟢 Минимальная тревожность"
        interpretation = "Ты почти не испытываешь тревожность в повседневной жизни."
    elif total_score <= 15:
        level = "🟡 Лёгкая тревожность"
        interpretation = "Тревожность есть, но ты справляешься. Обрати внимание на внутренние перегрузки."
    elif total_score <= 25:
        level = "🟠 Умеренная тревожность"
        interpretation = "Уровень тревоги уже влияет на твоё самочувствие. Возможно, стоит с кем-то это обсудить."
    else:
        level = "🔴 Выраженная тревожность"
        interpretation = "Тревожность ощутимо мешает тебе. Пора заботиться о себе и разгрузить голову."

    result_text = f"🔹 Твой результат: {total_score} баллов\n{level}\n\n{interpretation}"

    bot.send_message(chat_id, result_text)

    # Приглашение на сессию
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("🏠 Домой")

    bot.send_message(
        chat_id,
        "Если хочешь обсудить это глубже — запишись на сессию-знакомство со Стасом со скидкой 40% 👇",
        reply_markup=markup
    )

    del user_anxiety_state[uid]



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

@bot.message_handler(func=lambda msg: "Тест депрессии" in msg.text)
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

    if total_score <= 13:
        level = "🟢 Минимальная депрессия"
        interpretation = "Ты справляешься. Важно не терять контакт с собой."
    elif total_score <= 19:
        level = "🟡 Лёгкая депрессия"
        interpretation = "Эмоциональный фон немного просел. Попробуй наполнять себя чем-то приятным и бережным."
    elif total_score <= 28:
        level = "🟠 Умеренная депрессия"
        interpretation = "Возможно, стало сложнее радоваться, сосредотачиваться. Пора дать себе поддержку."
    else:
        level = "🔴 Тяжёлая депрессия"
        interpretation = "Тебе тяжело. Ты справляешься, но тебе точно не нужно быть с этим в одиночку."

    result_text = f"🔹 Твой результат: {total_score} баллов\n{level}\n\n{interpretation}"
    bot.send_message(chat_id, result_text)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("🏠 Главное меню")

    bot.send_message(
        chat_id,
        "Если хочешь обсудить это глубже — запишись на сессию-знакомство со Стасом со скидкой 40% 👇",
        reply_markup=markup
    )

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        """Привет!

Я живой бот Стаса Веречука, терапевта подхода «Домой, к себе настоящему». Хорошо, что ты здесь.

С чего начнём?

🟡 Сессия-знакомство со скидкой 40%.

🤿 Пойти глубже — там есть важное и полезное для тебя, а ещё — детальнее о подходе. Ну и, конечно, там 🚨 SOS без соплей, куда нужно заходить только в крайних эмоциях и очень осторожно.

🆘 Срочная помощь — если сейчас совсем тяжко.

🧞‍♂️🧞‍♀️ Ты можешь также пройти Тесты тревоги или депрессии. Это займет не больше 5 минут твоего времени, и, если ты увидишь проблемы, записывайся на сессию-знакомство со скидкой. Тревога и депрессия - это не приговор, с ними можно и нужно работать.""",
        reply_markup=persistent_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == '🟡 Записаться на сессию-знакомство -40%')
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

    bot.send_message(message.chat.id, "🟡 Выбери удобное тебе время:", reply_markup=markup)

    human_delay()
    bot.send_message(message.chat.id, "Если остались вопросы — можешь написать Стасу: @anxstas", reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🆘 Срочная помощь')
def handle_emergency(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("🙏 Спасибо 💛")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("🤿 Пойти глубже")  # <–– вот эта строка новая
    human_delay()
    bot.send_message(message.chat.id, "Ты зашёл сюда не просто так.")
    human_delay()
    bot.send_message(message.chat.id, "Давай вместе сделаем так, чтобы тебе стало хоть чуточку легче.")
    human_delay()
    bot.send_message(message.chat.id, "Расскажи немного, что с тобой? И я помогу тебе поддержкой, теплом и действенными техниками.\n\nПросто пиши мне в чат 👇 Прямо сейчас, без всяких приветствий. Что там с тобой? Поделись...",  reply_markup=persistent_keyboard())
    user_state[message.from_user.id] = 1

@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))
def handle_slot_choice(call):
    slot_raw = call.data.split("slot_")[1]
    user_selected_slots[call.from_user.id] = slot_raw
    dt_text = datetime.strptime(slot_raw, "%Y-%m-%d_%H:%M").strftime('%A %d %B • %H:%M')

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Оплатить", url="https://moneyyyyyy.carrd.co/"))
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
    bot.send_message(call.message.chat.id, "И можешь пока что «🤿 Пойти глубже», чтобы посмотреть, что там у нас 👇")

    # Кнопки
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤿 Пойти глубже", "🆘 Срочная помощь")
    bot.send_message(call.message.chat.id, reply_markup=markup)

    # Уведомление админу
    bot.send_message(ADMIN_ID, f"📬 Новый клиент записан на: {human_date}\nTelegram ID: {user_id}")

def get_techniques_block():
    return (
        "Попробуй сейчас сделать вот это. Наполную, без жалости к себе — и тревоги точно станет меньше:\n\n"
        "1. Дыхание 4-7-8.\n"
        "Вдох 4 сек, пауза 7 сек, выдох 8 сек. Делай так 5 минут — просто наблюдай, как воздух проходит через нос и глубже.\n\n"
        "⬜⬜⬜\n\n"
        "2. Выпиши всё, что внутри.\n"
        "Все свои мысли, всё, что парит — без критики, без обдумывания. Просто пиши всё как идёт.\n\n"
        "⬜⬜⬜\n\n"
        "3. Движение против тревоги.\n"
        "Сделай 10 отжиманий, 20 приседаний — и так 3 подхода. Можно сильно устать, и это хорошо.\n\n"
        "⬜⬜⬜\n\n"
        "4. Упражнение \"5-4-3-2-1\".\n"
        "Найди: 5 предметов, которые видишь, 4 - которые слышишь, 3 — трогаешь, 2 — чувствуешь, 1 — можешь съесть.\n" 
        "И в каждый из них вчувствуйся максимально. Рассматривай до деталей. Слушай до тишины. Трогай до мурашек. Чувствуй как будто ты кот(шка). Ешь до слюнек.\n\n"
        "⬜⬜⬜\n\n"
        "Хочешь — можно заглянуть в твою тревогу глубже со Стасом на сессии. Он очень бережно помогает возвращаться домой — в свою настоящесть.\n\n"
    )

@bot.message_handler(func=lambda msg: msg.text == '🙏 Спасибо 💛')
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
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("🙏 Спасибо 💛", "🍊 Тёплости")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2

@bot.message_handler(func=lambda msg: msg.text == '🧘 Техники')
def handle_techniques(message):

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.5))
    bot.send_message(message.chat.id, get_techniques_block())

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("🙏 Спасибо 💛", "🍊 Тёплости")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2

@bot.message_handler(func=lambda msg: msg.text == "🏠 Домой")
def go_main_menu(message):
    user_state.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())

    # 🤿 Пойти глубже — открывает разделы
@bot.message_handler(func=lambda msg: msg.text == '🤿 Пойти глубже')
def handle_deeper(message):
    user_state.pop(message.from_user.id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🧘 О подходе «Домой, к себе настоящему»")
    markup.add("🧩 Полезности", "🍊 Тёплости")
    markup.add("🚨 SOS без соплей", "🐳 Еще глубже")
    markup.add("🗣 Обратная связь", "🏠 Домой")
    bot.send_message(message.chat.id, "Выбери, что тебе интересно 👇", reply_markup=markup)

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

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🗣 Обратная связь')
def feedback(message):
    user_state.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "Здесь ты можешь написать всё, что думаешь о нём — об этом неидеальном, но точно живом и настоящем человеке.\n\n"
        "Он будет благодарен тебе за каждую твою буковку 🌞"
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🧩 Полезности')
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

@bot.message_handler(func=lambda msg: msg.text == '🚨 SOS без соплей')
def handle_sos_no_tears(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("😤 Когда всё заебало нахуй")
    markup.add("💣 Когда хочется разъебать")
    markup.add("😵‍💫 Когда в ахуе")
    markup.add("💀 Хочу сдохнуть, но не умирать")
    markup.add("😐 Не хочется ни хуя, но нажал")
    markup.add("🏠 Домой")

    bot.send_message(
        message.chat.id,
        "Выбирай, что ближе. Без прикрас, без розового. Просто ебашь.",
        reply_markup=markup
    )
    
@bot.message_handler(func=lambda msg: msg.text == "😤 Когда всё заебало нахуй")
def handle_sos_fuck_it_all(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Блядь, заебало всё")
    markup.add("Я выгорел нахуй")
    markup.add("Хочу исчезнуть к хуям")
    markup.add("Просто пошло всё нахуй")
    markup.add("🐾 Назад в SOS")

    bot.send_message(
        message.chat.id,
        "Понял. Держи варианты. Бей по тому, что ближе всего:",
        reply_markup=markup
    )
@bot.message_handler(func=lambda msg: msg.text == "Блядь, заебало всё")
def handle_sos_4099926234648959947(message):
    bot.send_message(message.chat.id, "Окей. Не фильтруй. Скажи это. Ещё громче. Ещё злее. Это не истерика. Это выход. Говори.")


@bot.message_handler(func=lambda msg: msg.text == "Я выгорел нахуй")
def handle_sos_2097721584395819975(message):
    bot.send_message(message.chat.id, "Выгорел — значит, слишком долго был в огне. Теперь ты пепел. Но пепел — это начало костра.")


@bot.message_handler(func=lambda msg: msg.text == "Хочу исчезнуть к хуям")
def handle_sos_5386086005586864426(message):
    bot.send_message(message.chat.id, "Необязательно исчезать. Достаточно выключиться. Исчезай по-настоящему — и возвращайся по-своему.")


@bot.message_handler(func=lambda msg: msg.text == "Просто пошло всё нахуй")
def handle_sos_3958503975752287122(message):
    bot.send_message(message.chat.id, "Хороший момент, чтобы перечеркнуть всё. А теперь: что хочешь оставить? Что реально твоё?")


@bot.message_handler(func=lambda msg: msg.text == "💣 Когда хочется разъебать")
def handle_sos_blow_it_up(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Хочу всё разъебать")
    markup.add("Разъебать бы кого-нибудь")
    markup.add("Я рвану сейчас нахуй")
    markup.add("Слишком всё, блядь")
    markup.add("🐾 Назад в SOS")

    bot.send_message(
        message.chat.id,
        "Чувствуешь вулкан? Выбери, как именно тебя шатает:",
        reply_markup=markup
    )
@bot.message_handler(func=lambda msg: msg.text == "Хочу всё разъебать")
def handle_sos_2582472798395486936(message):
    bot.send_message(message.chat.id, """Внутри тебя — вулкан. Не туши. Напиши. Кричи в подушку. Или просто бей воздух. Главное — не держи.""")

@bot.message_handler(func=lambda msg: msg.text == "Разъебать бы кого-нибудь")
def handle_sos_2910435303755721761(message):
    bot.send_message(message.chat.id, """Ты не агрессивный. Ты накопленный. Найди безопасный способ, и разнеси.""")

@bot.message_handler(func=lambda msg: msg.text == "Я рвану сейчас нахуй")
def handle_sos_1611018811932205984(message):
    bot.send_message(message.chat.id, """Ты не в клетке. Ты — с огнём. И это можно использовать.""")

@bot.message_handler(func=lambda msg: msg.text == "Слишком всё, блядь")
def handle_sos_7980701090421104069(message):
    bot.send_message(message.chat.id, """Слишком. Но ты держишься. Хочешь не держаться? Не держись. Я тут. Без морали.""")


@bot.message_handler(func=lambda msg: msg.text == "😵‍💫 Когда в ахуе")
def handle_sos_overwhelmed(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Что за нахуй вообще происходит")
    markup.add("У меня едет крыша, сука")
    markup.add("Меня реально накрыло")
    markup.add("Пиздец. Просто пиздец.")
    markup.add("🐾 Назад в SOS")

    bot.send_message(
        message.chat.id,
        "Состояние ахуя признано. Теперь выбери, как его лучше описать:",
        reply_markup=markup
    )
@bot.message_handler(func=lambda msg: msg.text == "Что за нахуй вообще происходит")
def handle_sos_8273854609020363593(message):
    bot.send_message(message.chat.id, """Ты в ахуе — и это нормально. Признай: сейчас — пиздец. Потом — подышим.""")

@bot.message_handler(func=lambda msg: msg.text == "У меня едет крыша, сука")
def handle_sos_2372558184027151334(message):
    bot.send_message(message.chat.id, """Это ощущение — будто расплавляется мозг. Ты не один. Повтори: 'Я еду — но я за рулём'.""")

@bot.message_handler(func=lambda msg: msg.text == "Меня реально накрыло")
def handle_sos_4512565454031012916(message):
    bot.send_message(message.chat.id, """Это не волна. Это цунами. Но в тебе есть плот. Найди его.""")

@bot.message_handler(func=lambda msg: msg.text == "Пиздец. Просто пиздец.")
def handle_sos_7426315701996593154(message):
    bot.send_message(message.chat.id, """Да. Без комментариев. Просто пиздец. Положи руку на грудь. Ты есть.""")


@bot.message_handler(func=lambda msg: msg.text == "💀 Хочу сдохнуть, но не умирать")
def handle_sos_not_really_die(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Хочу сдохнуть, но не насмерть")
    markup.add("Хочу, чтоб всё просто закончилось")
    markup.add("Задолбался быть сильным нахуй")
    markup.add("Мне всё похуй. И это пугает")
    markup.add("🐾 Назад в SOS")

    bot.send_message(
        message.chat.id,
        "Окей. Жёстко, но по-честному. Что именно сейчас ближе всего?",
        reply_markup=markup
    )
@bot.message_handler(func=lambda msg: msg.text == "Хочу сдохнуть, но не насмерть")
def handle_sos_1540063093599959811(message):
    bot.send_message(message.chat.id, """Ты хочешь исчезнуть — но чтобы тебя поняли. Это жажда жизни.""")

@bot.message_handler(func=lambda msg: msg.text == "Хочу, чтоб всё просто закончилось")
def handle_sos_8716353466281736208(message):
    bot.send_message(message.chat.id, """Это про паузу. Я с тобой. Вот тебе она.""")

@bot.message_handler(func=lambda msg: msg.text == "Задолбался быть сильным нахуй")
def handle_sos_4369674963488431275(message):
    bot.send_message(message.chat.id, """Сила — это вовремя лечь. Разреши себе упасть.""")

@bot.message_handler(func=lambda msg: msg.text == "Мне всё похуй. И это пугает")
def handle_sos_90912094602774372(message):
    bot.send_message(message.chat.id, """Похуй — это защита. Давай разморозим чуть-чуть?""")


@bot.message_handler(func=lambda msg: msg.text == "😐 Не хочется ни хуя, но нажал")
def handle_sos_numb_click(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Не знаю зачем жму, но жму")
    markup.add("Сделай хоть что-то за меня")
    markup.add("Хочу, чтоб кто-то просто обнял")
    markup.add("Просто полежу и послушаю")
    markup.add("🐾 Назад в SOS")

    bot.send_message(
        message.chat.id,
        "Я понял. На автомате. Без надрыва. Просто выбери — я подстрахую.",
        reply_markup=markup
    )
@bot.message_handler(func=lambda msg: msg.text == "Не знаю зачем жму, но жму")
def handle_sos_5118879855801710959(message):
    bot.send_message(message.chat.id, """Уже шаг. Даже если на отъебись. Я рядом.""")

@bot.message_handler(func=lambda msg: msg.text == "Сделай хоть что-то за меня")
def handle_sos_1353577155551005056(message):
    bot.send_message(message.chat.id, """Я скажу за тебя: 'Мне больно и нужна передышка'.""")

@bot.message_handler(func=lambda msg: msg.text == "Хочу, чтоб кто-то просто обнял")
def handle_sos_2336781073894284348(message):
    bot.send_message(message.chat.id, """*Обнимаю*. Без слов. Без морали.""")

@bot.message_handler(func=lambda msg: msg.text == "Просто полежу и послушаю")
def handle_sos_4994767971289124446(message):
    bot.send_message(message.chat.id, """Молчу. Но я рядом. Можешь молчать со мной сколько хочешь.""")

@bot.message_handler(func=lambda msg: msg.text == "🐾 Назад в SOS")
def handle_sos_back_to_main(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("😤 Когда всё заебало нахуй")
    markup.add("💣 Когда хочется разъебать")
    markup.add("😵‍💫 Когда в ахуе")
    markup.add("💀 Хочу сдохнуть, но не умирать")
    markup.add("😐 Не хочется ни хуя, но нажал")

    bot.send_message(
        message.chat.id,
        "Возвращаемся. Всё под контролем. Выбирай снова:",
        reply_markup=markup
    )


@bot.message_handler(func=lambda msg: msg.text == '🍊 Тёплости')
def cute_stuff(message):
    user_state[message.from_user.id] = 'cute_menu'

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🩵 Что я чувствую", "🫧 Море тишины")
    markup.add("📚 Я — дневник", "🏠 Домой")

    bot.send_message(
        message.chat.id,
        "Тут - то, что может тебя поддержать 💛\n\nВыбери что-то для себя прямо сейчас 👇",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == '🫧 Море тишины')
def handle_sea_of_silence(message):
    user_state.pop(message.from_user.id, None)

            # Гифка с морем
    bot.send_chat_action(message.chat.id, 'upload_video')
    bot.send_animation(
        message.chat.id,
        animation='https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif',  # мягкая, расслабляющая гифка
    )

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(2)
    bot.send_message(
        message.chat.id,
        "Тут ничего не надо. Просто тишина, дыхание и ты. И еще кот.\n\n"
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
    "Будь здесь, сколько захочешь.\n\nМесто внутри себя — самое прекрасное место на Земле. Зачастую оно испещрено ранами, но от этого оно становится еще и очень-очень ценным. Непохожим ни на кого и уникальным. И оно так хочет твоей заботы. Повтыкай на этого кота, у него точно можно поучиться 💛"
    )
    
@bot.message_handler(func=lambda msg: msg.text == '📚 Я — дневник')
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
        "Спасибо, что поделился. Это важно.\nТвои слова здесь навсегда в безопасности. 💛"
    )

@bot.message_handler(func=lambda msg: msg.text == '🩵 Что я чувствую')
def handle_emotional_radar(message):
    user_state[message.from_user.id] = 'emotion_wait'

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "😊 Радость", "😟 Тревога", "😢 Грусть",
        "😠 Злость", "😱 Страх", "😔 Стыд",
        "🤢 Отвращение", "⚖️ Вина",
        "🏠 Домой"
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
            "Какой же это кайф - чувствовать радость 💛 Где она у тебя в теле? Постарайся это запомнить.\n\n"
            "🔸 А давай дадим ей чуть больше пространства?\n\n"
            "Представь, что она — не чувство, а вещество. Что, если это — свет, густой мёд, теплая ванна, музыка пианино?\n\n"
            "🌿 Сделай вдох — и представь, что с ним радость растекается чуть дальше.\n"
            "Сделай выдох — и позволь ей остаться, не улетая.\n\n"
            "💛 Спроси себя: – Что она хочет мне сказать?\n"
            "Куда в жизни мне стоит её пригласить?\n\n"
            "Приходи, если еще захочешь. Я буду здесь."
        ),
        "😟 тревога": (
            "Я рядом. Тревога — это не враг. Это сигнал о том, что тебе важно в будущем, и есть риск. Что там тебя так тянет? В чем риск?\n\n"
            "🔸 Попробуй: вдохни на 4 счета, задержи дыхание еще на 4, а выдохни на 6. Повтори 10 раз.\n"
            "Это даст телу сигнал: 'всё безопасно'.\n\n"
            "Можешь написать мне позже, если захочешь."
        ),
        "😢 грусть": (
            "Грусть бывает, когда мы что-то теряем. Даже если это было воображаемое. Или что-то не так, как нам хочется. Я рядом.\n\n"
            "🔸 Обними себя руками, закрой глаза и побудь так 2 минуты.\n"
            "Это поддержка, которой мы часто недополучаем. Грусть очень важна, не погрустив, мы не можем пойти дальше\n\n"
            "Хочешь — возвращайся, я буду тут."
        ),
        "😠 злость": (
            "Злость — энергия. Она показывает границы. Спасибо, что ты с ней.\n\n"
            "🔸 Возьми лист бумаги и напиши на нём всё, на что злишься. Не подбирая слов.\n"
            "Потом можешь порвать. А можешь - сжечь.\n\n"
            "Это важно прожить. Я рядом, если захочешь вернуться."
        ),
        "😱 страх": (
            "Страх — сигнал, что тебе что-то важно прямо сейчас, и есть риск. Ты живой, и ты заботишься о себе. Что тебе так важно?\n\n"
            "🔸 Попробуй: сядь, почувствуй опору под собой, скажи вслух: *Я в безопасности.*\n"
            "Подыши глубоко. Почувствуй, как ты дышишь. Вспомни о том, что единственное лекарство от страха - это мужество.\n\n"
            "Если вернёшься — я буду рядом."
        ),
        "😔 стыд": (
            "Стыд — это про потребность быть принятым. Ты не один в этом. Я тоже много и часто стыдился. И до сих пор я в этом иногда.\n\n"
            "🔸 Напиши себе: *Я достаточно хороший, даже с этим чувством.*\n"
            "Просто прочти это 3 раза вслух. Это уже много.\n\n"
            "Захочешь — возвращайся."
        ),
        "🤢 отвращение": (
            "Отвращение говорит: *это не моё*, *я не хочу быть с этим рядом*.\n\n"
            "🔸 Можешь буквально оттолкнуть это жестом. Толкни это так, чтобы оно отлетело подальше. Или нарисуй и выбрось. С балкона. Зашвырнув как следует.\n"
            "Это — граница. Она важна.\n\n"
            "Я здесь, если захочешь поговорить ещё."
        ),
        "⚖️ вина": (
            "Здоровая вина может говорить о том, что тебе важны отношения или внутренние ценности. Это чувство часто даёт шанс восстановить что-то ценное. Что ценно для тебя?\n\n"
            "🔸 Напиши себе фразу — *Я сделал(а) ошибку, но я - не ошибка.*\n"
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
    '🟡 Записаться на сессию-знакомство -40%',
    '🤿 Пойти глубже',
    '🆘 Срочная помощь',
    '🧘 О подходе «Домой, к себе настоящему»',
    '🧩 Полезности',
    '🍊 Тёплости',
    '🚨 SOS без соплей', 
    '🐳 Еще глубже',
    '🗣 Обратная связь',
    '🏠 Домой'
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
        bot.send_message(message.chat.id, "Спасибо, что делишься. Я тебя слышу. Твой вопрос важный, как и все, что происходит с тобой... Я с тобой в этом, насколько могу.")

        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(random.uniform(1.0, 2.0))
        bot.send_message(message.chat.id, "Хочешь, перешли его прямо сейчас Стасу лично на @anxstas — он ответит, как только прочитает. Это бесплатно.")

        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(random.uniform(1.0, 2.1))
        bot.send_message(message.chat.id, "Или хочешь — побудем в этом немного вместе? Я могу дать тебе чуточку тепла и поддержки, предложить быстрые техники снижения тревожности.")

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("❤️ Тепло", "🧘 Техники", "🏠 Домой")

        bot.send_message(message.chat.id, "Как я могу тебя поддержать? Выбери внизу 👇 Что тебе сейчас ближе?", reply_markup=markup)
        user_state[uid] = 2
        return


@bot.callback_query_handler(func=lambda call: True)
def debug_callback(call):
    print(f"🔘 CALLBACK: {call.data}")

@bot.message_handler(func=lambda msg: True)
def debug_all(message):
    print(f"📩 DEBUG TEXT: {repr(message.text)}")

@bot.message_handler(func=lambda msg: True)
def debug_all(message):
    print(f"📩 msg.text = {repr(message.text)}")
    
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


if __name__ == "__main__":
    print(">>> Устанавливаем webhook:", f"{WEBHOOK_URL}/bot{TELEGRAM_TOKEN}")
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/bot{TELEGRAM_TOKEN}")
    app.run(host="0.0.0.0", port=WEBHOOK_PORT)
