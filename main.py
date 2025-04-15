import telebot
from telebot import types
import openai
import logging
import os
import random
import time
from datetime import datetime, timedelta

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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = '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'
ADMIN_ID = 513201869

openai.api_key = os.getenv("OPENAI_API_KEY")
bot = telebot.TeleBot(TELEGRAM_TOKEN)
logging.basicConfig(level=logging.INFO)
user_state = {}

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

@bot.message_handler(func=lambda msg: msg.text == '💡 Свежий взгляд')
def handle_fresh_view(message):
    user_state[message.from_user.id] = 'fresh_view_wait'
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(2.0)
    bot.send_message(
        message.chat.id,
        "Расскажи чуть подробнее о проблеме, пожалуйста. В одном сообщении"
    )

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'fresh_view_wait')
def respond_to_fresh_view(message):
    user_state[message.from_user.id] = 'fresh_view_done'

    response = select_fresh_view_response(message.text)

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(2.0)
    bot.send_message(message.chat.id, response)


    time.sleep(3.0)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("📅 Записаться на сессию-знакомство")
    markup.add("🌸 Наши теплые приколюшечки")
    markup.add("🙏 Спасибо 💛")

    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(
        message.chat.id,
        "Приходи на сессию или загляни в «Наши тёплые приколюшечки» — там есть интересные интерактивные штуки, которые могут поддержать тебя 💛👇",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'fresh_view_done')
def final_fresh_message(message):
    user_state.pop(message.from_user.id, None)

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(2.0)
    bot.send_message(message.chat.id, "К сожалению, нам нужно заканчивать 😔💛")

    time.sleep(2.5)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("📅 Записаться на сессию-знакомство")
    markup.add("🌸 Наши теплые приколюшечки")
    markup.add("🙏 Спасибо 💛")

    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(
        message.chat.id,
        "Приходи. Буду ждать тебя",
        reply_markup=markup
    )


def select_fresh_view_response(text):
    text = text.lower()

    FRESH_RESPONSES = {
        "свобода": (
            "🌀 **О свободе и ответственности**\n\n"
            "Я слышу твою боль и стремление к выходу из этой ситуации. В твоих словах чувствую желание свободы и одновременно страх перед ней. "
            "Настоящая свобода всегда связана с ответственностью — они как две стороны одной монеты. "
            "Когда мы ищем свободу без ответственности, мы часто попадаем в ловушку тревоги. "
            "Твои переживания — это признак внутреннего роста, приглашение стать автором своей жизни. "
            "Представь: эта ситуация — не препятствие, а дверь к более глубокому пониманию себя.\n\n"
            "Попробуй задать себе три вопроса:\n"
            "— Что я чувствую прямо сейчас?\n"
            "— Что на самом деле важно для меня?\n"
            "— Какой маленький шаг я могу сделать в сторону своих ценностей?\n\n"
            "Я думаю, тебе будет полезно поговорить со Стасом — он поможет тебе найти свой путь к интеграции свободы и ответственности в твоей жизни.\n\n"
        ),

        "неопределенность": (
            "🌫 **О принятии неопределенности**\n\n"
            "Спасибо за твою открытость. То, что ты описываешь — это встреча с неизвестностью, с которой сталкивается каждый из нас. "
            "Мы все ищем определенности и контроля, но что если самая прочная опора — это умение стоять на зыбучих песках? "
            "Твое беспокойство — это не слабость, а мудрость тела, которое знает: жизнь непредсказуема.\n\n"
            "Представь, что неопределенность — это не враг, а пространство новых возможностей. "
            "Когда мы перестаем бороться с ней и начинаем доверять, мы находим ту внутреннюю опору, которую так долго искали.\n\n"
            "Это как плавание: мы держимся на воде не контролируя её, а доверяя ей и себе.\n\n"
            "Давай сделаем простую практику: 2 минуты побудь со своим дыханием, просто наблюдая за ним.\n\n"
            "Это первый шаг к новым отношениям с неопределенностью. Стас мог бы помочь тебе глубже исследовать этот путь на сессии.\n\n"
        ),

        "принятие": (
            "🌱 **О доверии и принятии**\n\n"
            "Я чувствую твою боль и вижу в ней глубокую потребность в принятии и доверии — к себе, к другим, к жизни. "
            "Удивительно, как строго мы судим себя, требуя совершенства там, где суть жизни — в постоянном становлении.\n\n"
            "Доверие — это не отсутствие сомнений, а способность двигаться вперед даже с ними.\n"
            "Что если твои \"несовершенства\" — это не недостатки, а двери к твоей уникальности?\n\n"
            "Принятие — это не сдача, а акт мужества встретиться с жизнью такой, какая она есть.\n\n"
            "Попробуй простую практику: положи руку на сердце и скажи:\n"
            "— Это трудный момент. Страдание — часть общего человеческого опыта. Я буду добр к себе сейчас.\n\n"
            "Разговор со Стасом поможет тебе найти путь к глубокому принятию себя и жизни во всей её сложности.\n\n"
        ),

        "смысл": (
            "🎯 **О поиске смысла и аутентичности**\n\n"
            "Благодарю за твою честность. То, что ты описываешь — это не просто трудность, а вопрос о смысле и подлинности. "
            "Мы часто ищем смысл \"где-то там\", хотя на самом деле он рождается в наших действиях, в том, как мы отвечаем на вызовы жизни.\n\n"
            "Может быть, пустота, которую ты чувствуешь — это не отсутствие, а пространство для нового рождения?\n"
            "Твое стремление к подлинности — это уже путь домой, к той части тебя, которая всегда была цельной.\n\n"
            "Попробуй упражнение:\n"
            "— Напиши письмо себе из будущего: как выглядит твоя жизнь через 10 лет, если ты живешь в согласии со своими ценностями?\n\n"
            "Стас поможет тебе исследовать, как превратить поиск смысла в процесс его создания через подлинную жизнь.\n\n"
        ),

        "страх": (
            "🔥 **О страхе и смелости**\n\n"
            "Спасибо за твою смелость говорить о страхах. Страх — это не просто эмоция, а сложное явление: он одновременно защищает нас, тормозит развитие и может стать двигателем роста.\n\n"
            "Что если твой страх говорит не об опасности, а о ценности того, что за его границей?\n"
            "Смелость — это не отсутствие страха, а готовность идти вперёд вместе с ним.\n\n"
            "Представь, что страх — это не враг, а мудрый учитель. Попробуй технику:\n"
            "— Вообрази страх в виде существа и спроси: чему ты меня учишь? от чего защищаешь? зачем ты здесь?\n\n"
            "Стас поможет тебе увидеть в страхе не препятствие, а ресурс роста.\n\n"
        ),

        "ценности": (
            "🌿 **О возвращении к ценностям и взрослении**\n\n"
            "Я слышу в твоих словах стремление к целостности и подлинности. То, что ты проходишь — часть пути взросления: движения от внешних ориентиров к внутренним, от \"должен\" к \"выбираю\".\n\n"
            "Когда мы живём не в согласии с ценностями, психика и тело подают сигналы — тревогой, пустотой, выгоранием.\n\n"
            "Попробуй практику:\n"
            "— Выпиши 5 качеств жизни, которые тебе действительно важны, и спроси: как я могу проявить их сегодня — даже в мелочах?\n\n"
            "Стас может помочь тебе восстановить контакт с этими ценностями и шаг за шагом выстраивать на них свою жизнь.\n\n"
        )
    }


    if any(k in text for k in [
        "смысл", "смысла", "смыслом", "бессмыс", "зачем", "ради чего", "ради кого", "ничто не радует", 
        "пусто", "внутренняя пустота", "всё обесценилось", "для чего жить", "что дальше", "в чем суть", 
        "не вижу будущего", "потерян", "утрат", "разочаров", "обессил", "апатия", "всё бессмысленно"
    ]):
        return FRESH_RESPONSES["смысл"]

    elif any(k in text for k in [
        "неопредел", "непонятно", "потерял опору", "ничего не ясно", "будущее пугает", "боюсь будущего",
        "всё меняется", "нет стабильности", "рушится", "всё зыбко", "невозможно планировать", 
        "контроль", "теряю почву", "всё нестабильно", "не знаю что делать", "непонятное время", 
        "хаос", "всё непредсказуемо", "на грани", "обескуражен", "не держит"
    ]):
        return FRESH_RESPONSES["неопределенность"]

    elif any(k in text for k in [
        "свобода", "сам решаю", "сам решать", "ответствен", "должен сам", "автор", "влияю", 
        "принимаю решения", "выбор", "тяжело самому", "я решаю", "мне решать", "бремя выбора", 
        "сам за себя", "никто не поможет", "я управляю", "моя ответственность", "самостоятельность", 
        "внутренняя сила", "определяю сам"
    ]):
        return FRESH_RESPONSES["свобода"]

    elif any(k in text for k in [
        "принят", "принять себя", "не принимают", "стыдно", "виню себя", "виноват", "осуждают", 
        "хочу простить себя", "жесток к себе", "самокритика", "недостаточен", "несовершенен", 
        "неидеален", "самобичевание", "не могу простить", "всё не так", "никто не принимает", 
        "мне трудно с собой", "злюсь на себя", "стараюсь быть лучше", "не заслуживаю"
    ]):
        return FRESH_RESPONSES["принятие"]

    elif any(k in text for k in [
        "страх", "страшно", "тревож", "боюсь", "паник", "паническая атака", "волнение", "сердце колотится", 
        "ужас", "дрожь", "не справлюсь", "волнуюсь", "страшит", "жутко", "мурашки", "очень страшно", 
        "потеют ладони", "голова кругом", "ужасное состояние", "всё пугает", "напряжение"
    ]):
        return FRESH_RESPONSES["страх"]

    elif any(k in text for k in [
        "ценность", "ценности", "поиск себя", "не своей жизнью", "не живу как хочу", "навязанные ожидания", 
        "я хочу по-другому", "живу не так", "хочу быть собой", "не настоящая жизнь", "не искренне", 
        "внутренний конфликт", "жить как чувствую", "больше не хочу подстраиваться", "хочу выбрать себя", 
        "аутентичность", "подлинность", "настоящесть", "не хочу притворяться", "ценностный выбор", 
        "взросление", "искренность"
    ]):
        return FRESH_RESPONSES["ценности"]

    else:
        return FRESH_RESPONSES["свобода"]


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
    markup.add("📓 Я — дневник", "💌 Письмо на завтра")
    markup.add("💌 Письмо себе через год")
    markup.add("🔙 Назад")

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
        markup.add("❤️ Тепло", "🧘 Техники", "💡 Свежий взгляд", "🔙 Назад")

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
        markup.add("❤️ Тепло", "🧘 Техники", "💡 Свежий взгляд", "🔙 Назад")
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

from apscheduler.schedulers.background import BackgroundScheduler
import json

LETTERS_FILE = 'letters_for_tomorrow.json'

def load_letters():
    if not os.path.exists(LETTERS_FILE):
        return []
    with open(LETTERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_letters(letters):
    with open(LETTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(letters, f, ensure_ascii=False, indent=2)

from pytz import timezone

def send_scheduled_letters():
    today = datetime.now(timezone('Europe/Kiev')).date()
    letters = load_letters()
    to_send = [l for l in letters if l['send_date'] == str(today)]
    letters = [l for l in letters if l['send_date'] != str(today)]
    save_letters(letters)

    logging.info(f"Сегодня: {today}, писем для отправки: {len(to_send)}")

    for entry in to_send:
        try:
            bot.send_message(entry['user_id'], f"Ты написал себе это ранее:\n\n‘{entry['text']}’ 💛")
        except Exception as e:
            logging.error(f"Не удалось отправить письмо {entry['user_id']}: {e}")


@bot.message_handler(func=lambda msg: msg.text == '💌 Письмо на завтра')
def handle_letter_prompt(message):
    user_state[message.from_user.id] = 'waiting_letter_text'
    bot.send_message(
        message.chat.id,
        "Хочешь оставить себе записку, которую я пришлю тебе утром?\n\nНапиши её сюда. Она дойдёт к тебе завтра 🌅"
    )
    
@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'waiting_letter_text')
def save_letter_for_tomorrow(message):
    user_state.pop(message.from_user.id, None)
    letters = load_letters()
    letters.append({
        'user_id': message.from_user.id,
        'text': message.text.strip(),
        'send_date': (datetime.now() + timedelta(days=1)).date().isoformat()
    })
    save_letters(letters)
    bot.send_message(
        message.chat.id,
        "Сохранил 💌 Завтра утром я напомню тебе об этом. Спокойной ночи 🌙"
    )


@bot.message_handler(func=lambda msg: msg.text == '💌 Письмо себе через год')
def handle_letter_next_year_prompt(message):
    user_state.pop(message.from_user.id, None)
    user_state[message.from_user.id] = 'waiting_letter_text_year'
    bot.send_message(
        message.chat.id,
        "Хочешь оставить себе письмо, которое я пришлю тебе ровно через год?\n\nНапиши его сюда — и оно обязательно найдёт тебя. 💫"
    )

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'waiting_letter_text_year')
def save_letter_for_next_year(message):
    user_state.pop(message.from_user.id, None)
    user_state.pop(message.from_user.id, None)
    letters = load_letters()
    letters.append({
        'user_id': message.from_user.id,
        'text': message.text.strip(),
        'send_date': (datetime.now() + timedelta(days=365)).date().isoformat()
    })
    save_letters(letters)

    bot.send_message(
        message.chat.id,
        "Письмо сохранено 🕊️ Я пришлю его тебе через год. Прикинь, сколько всего может произойти за это время... 💛"
    )

@bot.message_handler(commands=['письма_файл'])
def print_letter_file(message):
    letters = load_letters()
    bot.send_message(message.chat.id, f"Сейчас в файле:\n{json.dumps(letters, ensure_ascii=False, indent=2)}")

@bot.message_handler(commands=['письма'])
def debug_send_letters(message):
    send_scheduled_letters()
    bot.send_message(message.chat.id, "Попробовал отправить письма 💌")


if __name__ == '__main__':
    logging.info("Бот запущен")

    scheduler = BackgroundScheduler()
    scheduler.add_job(send_scheduled_letters, 'cron', hour=9, minute=0)
    scheduler.start()
    from pytz import timezone
    scheduler = BackgroundScheduler(timezone=timezone('Europe/Kiev'))
    scheduler.add_job(send_scheduled_letters, 'cron', hour=9, minute=0)
    scheduler.start()

    bot.polling(none_stop=True)
