import telebot
from telebot import types
import openai
import logging
import os
import random
import time
from datetime import datetime, timedelta
from flask import Flask, request
import threading

app = Flask(__name__)

@app.route('/')
def keep_alive():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 💓 Keep-alive ping received.")
    return 'Бот жив!'


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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add('🟡 Записаться на сессию-знакомство -40%')
    markup.add('🤿 Пойти глубже', '🆘 Срочная помощь')
    markup.add('🧞‍♂️ Тест тревоги', '🧞‍♀️ Тест депрессии') 
    return markup

# --- Вопросы GAD-7 и PHQ-9 ---
gad7_questions = [
    "Чувство нервозности, тревоги или сильного напряжения",
    "Невозможность остановить или контролировать тревожные мысли",
    "Чрезмерное беспокойство по различным поводам",
    "Затруднения при расслаблении",
    "Беспокойство настолько сильное, что сложно сидеть спокойно",
    "Раздражительность или легкое раздражение",
    "Чувство страха, что может случиться что-то ужасное"
]

phq9_questions = [
    "Маленький интерес или удовольствие от выполнения дел",
    "Чувство подавленности, депрессии или безысходности",
    "Затруднение со сном или избыточный сон",
    "Чувство усталости или нехватки энергии",
    "Проблемы с аппетитом — снижение или переедание",
    "Плохое мнение о себе, чувство вины или никчемности",
    "Трудности с концентрацией (например, при чтении или просмотре ТВ)",
    "Замедленность движений или, наоборот, суетливость",
    "Мысли о том, что лучше бы не жить или нанести себе вред"
]

# --- Уровни оценки ---
gad7_levels = [
    (0, 4, "Минимальная тревожность"),
    (5, 9, "Легкая тревожность"),
    (10, 14, "Умеренная тревожность"),
    (15, 21, "Тяжелая тревожность")
]

phq9_levels = [
    (0, 4, "Минимальная депрессия"),
    (5, 9, "Легкая депрессия"),
    (10, 14, "Умеренная депрессия"),
    (15, 19, "Умеренно-тяжелая депрессия"),
    (20, 27, "Тяжелая депрессия")
]

# --- Живые интерпретации ---
anxiety_descriptions = {
    "Минимальная тревожность": (
        "Сейчас вы держитесь уверенно — тревожность не выходит за пределы нормы. "
        "Ваш психоэмоциональный фон выглядит устойчивым. "
        "Продолжайте заботиться о себе, даже если кажется, что всё под контролем. Можете проконсультироваться о способах заботы."
    ),
    "Легкая тревожность": (
        "Похоже, что вы часто на взводе или внутренне напряжены. "
        "Это состояние легко списать на усталость, но оно может накапливаться. "
        "Уже сейчас стоит научиться замечать сигналы тела и давать себе передышку. Узнайте как."
    ),
    "Умеренная тревожность": (
        "Ваши ответы говорят о тревоге, которая не просто фоном — она уже мешает жить. "
        "Вы можете ловить себя на бесконечном анализе, переживаниях и усталости. "
        "Это не слабость — это сигнал о помощи, и его важно услышать. Не игнорируйте."
    ),
    "Тяжелая тревожность": (
        "Тревожность, которую вы испытываете, захватывает ваше внимание, энергию и силы. "
        "Когда напряжение становится постоянным фоном, организм начинает постепенно разрушаться. "
        "Сейчас самое время дать себе право на поддержку и восстановление. Важно заняться собой сейчас."
    )
}

depression_descriptions = {
    "Минимальная депрессия": (
        "Уровень депрессии не вызывает тревоги — вы держитесь на плаву. "
        "Но даже в этом состоянии важно не забывать про отдых и эмоциональную гигиену. "
        "Если что-то тревожит внутри — дайте себе разрешение об этом подумать. Можете проконсультироваться о способах заботы о себе."
    ),
    "Легкая депрессия": (
        "Что-то вас тянет вниз — вы не в самом лёгком состоянии. "
        "Может быть, стали чаще уставать или потеряли интерес к привычному. "
        "Это не критично, но требует внимания — не проходите мимо своих ощущений. Важно прислушаться к себе."
    ),
    "Умеренная депрессия": (
        "Здесь уже не просто грусть — это состояние, которое реально мешает жить. "
        "Всё будто становится тяжёлым: утро, решения, даже простые дела. "
        "Вы не обязаны справляться в одиночку — поддержка рядом, если её попросить. Не игнорируйте."
    ),
    "Умеренно-тяжелая депрессия": (
        "Будто что-то давит изнутри, и вы не можете до конца понять, что именно. А, возможно, вы уже понимаете, но предпочитаете это не замечать."
        "Это состояние не просто неприятное — оно начинает забирать энергию и смысл. "
        "И именно сейчас особенно важно не оставаться с этим в одиночестве. Важно заняться собой сейчас."
    ),
    "Тяжелая депрессия": (
        "Ваши ответы показывают, что вам очень трудно — возможно, каждый день. "
        "Это не просто 'плохое настроение' — это состояние, которое требует бережного вмешательства. "
        "Сделайте шаг — не чтобы 'починить себя', а чтобы снова начать чувствовать себя живым. Важно заняться собой сейчас."
    )
}

# --- Состояния пользователей ---
user_gad7_state = {}
user_phq9_state = {}

# --- GAD-7: старт ---
@bot.message_handler(func=lambda msg: msg.text == '🧞‍♂️ Тест тревоги')
def start_gad7(message):
    uid = message.from_user.id
    user_gad7_state[uid] = {'step': 0, 'answers': []}
    send_gad7_question(message.chat.id, uid)

def send_gad7_question(chat_id, uid):
    step = user_gad7_state[uid]['step']
    if step >= len(gad7_questions):
        total = sum(user_gad7_state[uid]['answers'])
        for minv, maxv, level, desc in gad7_levels:
            if minv <= total <= maxv:
                bot.send_message(chat_id,
                    f"🧠 *Ваш результат (GAD-7)*: {total}/21\n"
                    f"*Уровень тревожности:* _{level}_\n\n"
                    f"{desc}\n\n"
                    "Сделай скрин и просто отправь его Стасу на @anxstas",
                    parse_mode="Markdown"
                )
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
                markup.add("🟡 Записаться на сессию-знакомство -40%")
                markup.add("🏠 Домой")
                bot.send_message(chat_id,
                    "🟡 Если хочешь обсудить это глубже — запишись на сессию-знакомство со скидкой 40% 👇",
                    reply_markup=markup
                )
                break
        user_gad7_state.pop(uid)
        return

    question = gad7_questions[step]
    markup = types.InlineKeyboardMarkup()
    for i in range(4):
        markup.add(types.InlineKeyboardButton(str(i), callback_data=f'gad7_{i}'))
    bot.send_message(chat_id, f"{step + 1}. {question}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gad7_"))
def handle_gad7_answer(call):
    uid = call.from_user.id
    if uid not in user_gad7_state:
        return
    score = int(call.data.split('_')[1])
    user_gad7_state[uid]['answers'].append(score)
    user_gad7_state[uid]['step'] += 1
    bot.answer_callback_query(call.id)
    send_gad7_question(call.message.chat.id, uid)

# --- PHQ-9: старт ---
@bot.message_handler(func=lambda msg: msg.text == '🧞‍♀️ Тест депрессии')
def start_phq9(message):
    uid = message.from_user.id
    user_phq9_state[uid] = {'step': 0, 'answers': []}
    send_phq9_question(message.chat.id, uid)

def send_phq9_question(chat_id, uid):
    step = user_phq9_state[uid]['step']
    if step >= len(phq9_questions):
        total = sum(user_phq9_state[uid]['answers'])
        for minv, maxv, level, desc in phq9_levels:
            if minv <= total <= maxv:
                bot.send_message(chat_id,
                    f"🧠 *Ваш результат (PHQ-9)*: {total}/27\n"
                    f"*Уровень депрессии:* _{level}_\n\n"
                    f"{desc}\n\n"
                    "Сделай скрин и просто отправь его Стасу на @anxstas",
                    parse_mode="Markdown"
                )
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
                markup.add("🟡 Записаться на сессию-знакомство -40%")
                markup.add("🏠 Домой")
                bot.send_message(chat_id,
                    "🟡 Если хочешь обсудить это глубже — запишись на сессию-знакомство со скидкой 40% 👇",
                    reply_markup=markup
                )
                break
        user_phq9_state.pop(uid)
        return

    question = phq9_questions[step]
    markup = types.InlineKeyboardMarkup()
    for i in range(4):
        markup.add(types.InlineKeyboardButton(str(i), callback_data=f'phq9_{i}'))
    bot.send_message(chat_id, f"{step + 1}. {question}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("phq9_"))
def handle_phq9_answer(call):
    uid = call.from_user.id
    if uid not in user_phq9_state:
        return
    score = int(call.data.split('_')[1])
    user_phq9_state[uid]['answers'].append(score)
    user_phq9_state[uid]['step'] += 1
    bot.answer_callback_query(call.id)
    send_phq9_question(call.message.chat.id, uid)


def social_links_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    tg_btn = types.InlineKeyboardButton("🪶 Мой Telegram", url="https://t.me/domminside")
    yt_btn = types.InlineKeyboardButton("📺 Мой YouTube", url="https://www.youtube.com/@anxstas")
    mu_btn = types.InlineKeyboardButton("🎸 Мой Мьюзик", url="https://www.youtube.com/watch?v=ABcng-PsR3E&list=PLpSP-UgtrTHazZ74PrlSCLLiK82LlPrMH&index=3&pp=gAQBiAQB8AUB")
    keyboard.add(tg_btn, yt_btn, mu_btn)
    return keyboard

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        """Привет!

Я живой бот Стаса Веречука, терапевта проекта «Домой, к себе настоящему». Хорошо, что ты здесь.

С чего начнём?

🟡 Сессия-знакомство со скидкой 40%.

🤿 Пойти глубже — там есть важное и глубокое для тебя, а ещё там — детальнее о моем терапевтическом подходе. 

🆘 Срочная помощь — если сейчас совсем тяжко.""",
        reply_markup=persistent_keyboard()
    )

    time.sleep(5)
    bot.send_message(
        message.chat.id,
        """🧞‍♂️🧞‍♀️ Ты можешь также пройти Тесты тревоги или депрессии. Это займет не больше 2 минут. Увидишь проблемы - записывайся на сессию-знакомство со скидкой. Не игнорь тревогу и депрессию - это твои двери в жизнь.""",
    )

    time.sleep(6)
    bot.send_message(
        message.chat.id,
        """А здесь ⤵️ 
        
мой канал в телеграм (о тревоге) и ютуб, где идет "Тоска'на". А еще - та самая песня, написанная в период ГТР и ТДР, через которую я в течение года проживал и принимал смерть папы.""",
        reply_markup=social_links_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🟡 Записаться на сессию-знакомство -40%')
def handle_booking(message):
    user_state.pop(message.from_user.id, None)  # сбрасываем логику "срочной помощи"
    human_delay()
    bot.send_message(
        message.chat.id,
        "Ты сделал важный шаг и позаботился о себе.\n\n"
        "Первая сессия-знакомство будет со скидкой 40% (30 евро вместо 50).\n\n"
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
    bot.send_message(message.chat.id, "Если есть вопросы — можно написать Стасу лично на @anxstas")


@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))
def handle_slot_choice(call):
    slot_raw = call.data.split("slot_")[1]
    user_selected_slots[call.from_user.id] = slot_raw
    dt_text = datetime.strptime(slot_raw, "%Y-%m-%d_%H:%M").strftime('%A %d %B • %H:%M')

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Оплатить", url="https://moneyyyyyy.carrd.co/"))
    markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid_done"))

    bot.send_message(call.message.chat.id, f"Ты выбрал: {dt_text}\n\nПожалуйста, оплати, чтобы подтвердить запись:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "paid_done")
def confirm_payment(call):
    user_id = call.from_user.id
    slot_str = user_selected_slots.get(user_id)
    if not slot_str:
        bot.send_message(call.message.chat.id, "Не удалось найти выбранное время.")
        return

    username = call.from_user.username or "нет username"
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

    # Уведомление админу
    dt_fmt = dt.strftime('%d %B %Y • %H:%M')
    admin_msg = (
        f"🚼 Запись на сессию!\n\n"
        f"🛟 @{username} (id: {user_id})\n"
        f"🕘 Время: {dt_fmt}\n"
        f"💱 Слот подтверждён. Оплата?\n"
        f"📆 Добавить в Google Calendar:\n{calendar_link}"
    )
    bot.send_message(ADMIN_ID, admin_msg)

    # Подтверждение пользователю
    bot.send_message(call.message.chat.id, "Спасибо! Твоя сессия подтверждена 🌿")

    # Человеческая дата
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

    bot.send_message(call.message.chat.id, "Вот ссылка, чтобы добавить встречу в календарь:")
    bot.send_message(call.message.chat.id, calendar_link)
    bot.send_message(call.message.chat.id, f"Жду тебя в {human_date} 🤗", reply_markup=persistent_keyboard())
    bot.send_message(call.message.chat.id, "Установи заранее Google Meet для связи, перед сессией я пришлю тебе ссылку на встречу.")
    bot.send_message(call.message.chat.id, "А пока что загляни в «🤿 Пойти глубже» 👇, у нас там интересно.")



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




@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🆘 Срочная помощь')
def handle_emergency(message):
    user_state.pop(message.from_user.id, None)
    uid = message.from_user.id
    user_state[uid] = 2  # сразу ставим нужный этап

    # Ответ 1
    human_delay()
    bot.send_message(uid, "Ты зашёл сюда не просто так.")

    # Ответ 2
    human_delay()
    bot.send_message(uid, "Давай вместе сделаем так, чтобы тебе стало хоть чуточку легче.")

    # Ответ 3
    human_delay()
    bot.send_message(uid,
        "Расскажи немного, что с тобой? И я помогу тебе поддержкой, теплом и действенными техниками.\n\n"
        "Просто пиши мне в чат 👇 Прямо сейчас, без всяких приветствий. Что там с тобой? Поделись...",
        reply_markup=persistent_keyboard()
    )

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 2)
def handle_emergency_reply(message):
    user_state.pop(message.from_user.id, None)
    uid = message.from_user.id
    human_delay()
    bot.send_message(uid, "Спасибо, что делишься. Я тебя слышу. Твой вопрос важный, как и всё, что происходит с тобой... Я с тобой в этом, насколько могу.")

    human_delay()
    bot.send_message(uid, "Хочешь, перешли его прямо сейчас Стасу лично на @anxstas — он ответит, как только прочитает. Просто скопируй и отправь (или отправь скриншот), без приветствий, я его предупрежу. Это бесплатно.")

    human_delay()
    bot.send_message(uid, "Или хочешь — побудем в этом немного вместе? Я могу дать тебе чуточку тепла и поддержки, предложить быстрые техники снижения тревожности.")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=False)
    markup.add("❤️ Тепло", "🧘 Техники", "🧸 Поддержи меня", "🏠 Домой")
    bot.send_message(uid, "Выбери внизу 👇 Что тебе сейчас ближе?", reply_markup=markup)

    user_state[uid] = 3


@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '❤️ Тепло')
def handle_warmth(message):
    user_state.pop(message.from_user.id, None)
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

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("👣 Давай еще разок?")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🧘 Техники')
def handle_techniques(message):
    user_state.pop(message.from_user.id, None)

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(random.uniform(2.0, 2.5))
    bot.send_message(message.chat.id, get_techniques_block())

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add("🟡 Записаться на сессию-знакомство -40%")
    markup.add("👣 Давай еще разок?")
    bot.send_message(message.chat.id, "Приходи 💛👇", reply_markup=markup)
    user_state[message.from_user.id] = 2


@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "🧸 Поддержи меня")
def handle_support_me(message):
    user_state.pop(message.from_user.id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=False)
    markup.add("🧷 Мне надо за что-то держаться")
    markup.add("💬 Скажи мне, что со мной всё нормально")
    markup.add("🫠 Проваливаюсь")
    markup.add("⏳ Мне страшно, что никогда не станет легче")
    markup.add("🏠 Домой")
    bot.send_message(
        message.chat.id,
        "Я рядом. Выбери, что отзывается сильнее всего:",
        reply_markup=markup
    )



def human_typing_blocks(chat_id, text, min_d=1.1, max_d=2.4):
    blocks = text.strip().split("\n\n")
    for block in blocks:
        if block.strip():
            bot.send_chat_action(chat_id, 'typing')
            time.sleep(random.uniform(min_d, max_d))
            bot.send_message(chat_id, block)

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "🧷 Мне надо за что-то держаться")
def anchor_support(message):
    user_state.pop(message.from_user.id, None)
    text = (
        "Иногда единственное, что можно — это держаться. За дыхание. За плед. За взгляд кошки. За звук своего имени.\n\n"
        "🔸 Положи руку на грудь и почувствуй, что ты дышишь. Это - жизнь внутри тебя. Ты можешь почувствовать ее с дыханием.\n"
        "🔸 Ты справляешься. Так, как можешь на сейчас. И на сейчас этого достаточно.\n\n" 
        "🔸 Посмотри по сторонам и найди 3 предмета, которые могли бы дать тебе чувство опоры.\n"
        "🔸 Напиши себе на бумаге: \"Я здесь. Я держусь. Я справляюсь.\"\n\n"
        "Я с тобой. Всё, что ты сейчас переживаешь — не навсегда."
    )
    human_typing_blocks(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "💬 Скажи мне, что со мной всё нормально")
def reassurance_support(message):
    user_state.pop(message.from_user.id, None)
    messages = [
        "С тобой всё нормально. Я знаю, что иногда это вызывает сомнения, но тебя просто так научили. А на самом деле, с тобой всё ок. Полностью. Я знаю, что говорю.\n\n"
        "Ты не сломан. Ты просто живой. А живым бывает очень больно.\n\n"
        "Ты не должен быть сильным всё время. Иногда сильный — это тот, кто просто продолжает жить. Так, как у него на сейчас выходит.\n\n"
        "Ты не обязан быть продуктивным, весёлым или нужным. Ты уже заслуживаешь любви просто потому, что существуешь.\n\n"
        "То, что ты чувствуешь — это нормальная реакция на ненормальные обстоятельства."
    ]
    import random
    human_typing_blocks(message.chat.id, random.choice(messages))

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "🫠 Проваливаюсь")
def collapse_support(message):
    user_state.pop(message.from_user.id, None)
    text = (
        "Если кажется, что ты проваливаешься — значит, ты долго держался. Иногда тело и психика просто устают.\n\n"
        "Ты имеешь право остановиться. Лечь. Смотреть в потолок. Просто быть. Столько, сколько нужно. Долго. Мир не рухнет. Проверено.\n\n"
        "🔸 Представь, что ты — под пледом, в домике, где никто не тронет. Можешь там остаться.\n"
        "🔸 Дыши медленно: вдох — на 4 счета, выдох — на 6. Повтори 5 раз.\n\n"
        "Ты не ленивый. Ты истощён. Это другое. И это пройдёт."
    )
    human_typing_blocks(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "⏳ Мне страшно, что никогда не станет легче")
def fear_of_forever(message):
    user_state.pop(message.from_user.id, None)
    text = (
        "Этот страх — честный. Кажется, будто это 'навсегда'. Но всё течёт. Всё меняется.\n\n"
        "🔸 Ты не первый, кто это чувствует. И все, кто чувствовал, проходили через это.\n"
        "🔸 Откат — не конец. Это часть процесса.\n\n"
        "🔸 Даже мысль 'это не навсегда' — уже шаг в сторону надежды. Да и скажи, было бы всё это с тобой, если бы ты не мог это вынести? Мир не даёт нам того, с чем мы потенциально не можем справиться.\n\n"
        "Я с тобой. Подышим?"
    )
    human_typing_blocks(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "🏠 Домой")
def go_main_menu(message):
    user_state.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Возвращаю в главное меню 🌿", reply_markup=persistent_keyboard())

    # 🤿 Пойти глубже — открывает разделы
@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🤿 Пойти глубже')
def handle_deeper(message):
    user_state.pop(message.from_user.id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add("🧘 О подходе «Домой, к себе настоящему»")
    markup.add("🧩 Соцсети", "🧶 Заботливости")
    markup.add("🛁 Тест глубины", "🐳 Еще глубже")
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
def handle_feedback_start(message):
    user_state.pop(message.from_user.id, None)
    user_state[message.from_user.id] = 'waiting_feedback'
    bot.send_message(
        message.chat.id,
        "Здесь ты можешь написать всё, что думаешь о нём — об этом неидеальном, но точно живом и настоящем человеке.\n\n"
        "Он будет благодарен тебе за каждую твою буковку 🌞.",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'waiting_feedback')
def handle_feedback_entry(message):
    uid = message.from_user.id
    user_state.pop(uid, None)

    # Отправка сообщения админу
    bot.send_message(
        ADMIN_ID,
        f"🆕 Обратная связь от пользователя {uid} (@{message.from_user.username}):\n\n{message.text}"
    )

    # Подтверждение пользователю
    bot.send_message(
        message.chat.id,
        "Спасибо, я получил твоё сообщение. Оно уже в надёжных руках 💛",
        reply_markup=persistent_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🧶 Заботливости')
def cute_stuff(message):
    user_state.pop(message.from_user.id, None)
    user_state[message.from_user.id] = 'cute_menu'

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=False)
    markup.add("🩵 Что я чувствую", "🫧 Море тишины")
    markup.add("📚 Я — дневник", "🏠 Домой")

    bot.send_message(
        message.chat.id,
        "Тут можно немного о себе позаботиться 💛\n\nВыбери что-то для себя прямо сейчас 👇",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🫧 Море тишины')
def handle_sea_of_silence(message):
    user_state.pop(message.from_user.id, None)

            # Гифка с морем
    bot.send_chat_action(message.chat.id, 'upload_video')
    bot.send_animation(
        message.chat.id,
        animation='https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif',  # мягкая, расслабляющая гифка
    )

    bot.send_chat_action(message.chat.id, 'typing')
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
    
@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '📚 Я — дневник')
def handle_diary_start(message):
    user_state.pop(message.from_user.id, None)
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
    time.sleep(1)
    bot.send_message(
        message.chat.id,
        "Спасибо, что поделился. Это важно.\nТвои слова здесь навсегда в безопасности. 💛"
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🩵 Что я чувствую')
def handle_emotional_radar(message):
    user_state.pop(message.from_user.id, None)
    user_state[message.from_user.id] = 'emotion_wait'

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=False)
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


@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == '🧩 Соцсети')
def resources(message):
    user_state.pop(message.from_user.id, None)
    text = (
        "Тут - много всего на важные тревожно-депрессивные темы.\n\n"
        "Я буду рад видеть тебя среди своих подписчиков. Только так я смогу развиваться и давать людям больше пользы.\n\n"
        "▶️ YouTube о тревоге и депрессии (и чуть-чуть личного)\n\n"
        "📸 Instagram о тревоге и депрессии (и побольше личного)\n\n"
        "🪶 Telegram о тревоге и депрессии (и чуть-чуть науки)\n\n"
        "🎸 Моя музыка, где последний альбом и часть предпоследнего написаны в моих ГТР и ТДР\n\n"
        "🐡 Facebook — где личное, и немного о тревоге и депрессии\n\n"
        "📽 Мои музыкальные видео, созданные в тех же состояниях в 2017-2020"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("▶️ Мой YouTube", url="https://www.youtube.com/@anxstas"),
        types.InlineKeyboardButton("📸 Моя Insta", url="https://www.instagram.com/verechuk_/"),
        types.InlineKeyboardButton("🪶 Мой Telegram", url="https://www.t.me/domminside"),
        types.InlineKeyboardButton("🎸 Мой Мьюзик", url="https://soundcloud.com/joneser99"),
        types.InlineKeyboardButton("🐡 Мой Facebook", url="https://www.facebook.com/stanislav.verechuk/"),
        types.InlineKeyboardButton("📽 Мои Видео", url="https://www.youtube.com/playlist?list=PLpSP-UgtrTHazZ74PrlSCLLiK82LlPrMH")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

from telebot import types

# Запуск теста "Какой ты пельмень" из ветки "Пойти глубже"
@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "🛁 Тест глубины")
def start_dumpling_test(message):
    uid = message.from_user.id
    user_state[uid] = {'dumpling_test': 0, 'score': {'classic': 0, 'fried': 0, 'vegan': 0}}
    ask_dumpling_question(message.chat.id, uid)


dumpling_questions = [
    {
        'q': """Благодаря прохождению Теста глубины "🥟 Какой ты пельмень?" ты сможешь прикоснуться к невиданным доселе глубинам собственной личности, более тонко отстроить свой пельменный архетип, что позволит тебе перейти на следующий круг своего личного ада гораздо раньше твоих ближайших конкурентов.

Поехали 🍖

1. Как ты справляешься со стрессом?

A. Варюсь в себе, пока не взорвусь

B. Жарю всех вокруг, включая себя

C. Замираю и лежу в морозилке""",
        'a': [
            ("A", 'classic'),
            ("B", 'fried'),
            ("C", 'vegan')
        ]
    },
    {
        'q': "2. Что ты делаешь на вечеринке пельменей?\n\nA. Купаюсь в сметане, хочу ко всем, но им меня не понять\n\nB. Я жарю на танцполе, булькаю от кайфа и флиртую с варениками\n\nC. Сижу у бульонного шота, болтаю с двумя надёжными пельменями",
        'a': [
            ("A", 'vegan'),
            ("B", 'fried'),
            ("C", 'classic')
        ]
    },
    {
        'q': "3. Что для тебя идеальный вечер?\n\nA. Расслабленно перевариваться в кастрюле тишины\n\nB. Экшн, драйв, выпрыгнуть со сковородки на пол, чтобы все охренели\n\nC. Сижу в морозилке, никому не мешаю, слушаю китов и читаю о смысле теста",
        'a': [
            ("A", 'classic'),
            ("B", 'fried'),
            ("C", 'vegan')
        ]
    },
    {
        'q': "4. Как ты относишься к близости?\n\nA. Сразу слипаюсь с ближайшим пельменем\n\nB. Хочу слипнуться, но боюсь, и предпочитаю вылезти из теста и болтаться сам в бульбашках\n\nC. Я гордый одинокий пельмень, мне нах никто не нужен",
        'a': [
            ("A", 'fried'),
            ("B", 'classic'),
            ("C", 'vegan')
        ]
    },
    {
        'q': "5. Что тебя с большей вероятностью выбьет из колеи?\n\nA. Когда нарушают твой священный соус-распорядок\n\nB. Когда ты становишься фоном в чужом TikTok'е\n\nC. Когда тебя суют в микроволновку без предупреждения",
        'a': [
            ("A", 'classic'),
            ("B", 'vegan'),
            ("C", 'fried')
        ]
    },
    {
        'q': "6. Какая у тебя суперсила как у пельменя?\n\nA. Я умею притвориться испорченным, если не хочу идти на встречу\n\nB. Я могу исчезнуть с тарелки, если атмосфера токсичная\n\nC. Я могу раскрутить тусовку даже в морозилке\n\nD. Я могу укатать любого. Даже того, кто 'не голоден'\n\nE. Я пережил кипяток, сковородку и школьную столовку. Я бессмертен\n\nF. Я могу закрутить такую соус-драму, что про гарнир все забудут",
        'a': [
            ("A", 'vegan'),
            ("B", 'vegan'),
            ("C", 'fried'),
            ("D", 'classic'),
            ("E", 'classic'),
            ("F", 'fried')
        ]
    }
]


def ask_dumpling_question(chat_id, uid):
    step = user_state[uid]['dumpling_test']
    if step < len(dumpling_questions):
        qdata = dumpling_questions[step]
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        for label, _ in qdata['a']:
            markup.add(label)
        bot.send_message(chat_id, qdata['q'], reply_markup=markup)
    else:
        interpret_dumpling_result(chat_id, uid)


@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id, {}).get('dumpling_test') is not None)
def handle_dumpling_answer(message):
    uid = message.from_user.id
    step = user_state[uid]['dumpling_test']
    qdata = dumpling_questions[step]
    selected = message.text.strip()

    for label, category in qdata['a']:
        if selected == label:
            user_state[uid]['score'][category] += 1
            break

    user_state[uid]['dumpling_test'] += 1
    ask_dumpling_question(message.chat.id, uid)


def interpret_dumpling_result(chat_id, uid):
    scores = user_state[uid]['score']
    result = max(scores, key=scores.get)

    if result == 'classic':
        desc = (
            "🥟 Ты — Пельмень-КлассИк.\n\n"
            "Ты — оплот бульона. Уютный, стабильный, с укропчиком.\n"
            "Ты не ищешь соуса — ты и есть соус. Люди тянутся к тебе, когда хочется чего-то настоящего.\n"
            "Иногда ты считаешь себя скучным. Но ты — редкий вид тепла, который не кипятится, а настаивается.\n\n"
            "✨ Аффирмация: Я не должен быть острым, чтобы быть ценным. Я — тепло, которое приходит не сразу, но остаётся надолго."
        )
    elif result == 'fried':
        desc = (
            "🔥 Ты — Пельмень-Флексер.\n\n"
            "Ты — огонь. RHCP в мире пельменей. Когда ты входишь в сковородку, вся кухня знает.\n"
            "Ты флексишь, исчезаешь, обжигаешь — но под хрустом скрыта мягкость.\n"
            "Ты драматичен, блистаешь и умеешь делать эффектные выходы.\n\n"
            "✨ Аффирмация: Я не для всех — и это мой соус. Я обжигаю, ведь я живу на максимальной температуре."
        )
    else:
        desc = (
            "🌱 Ты — Пельмень-Созерцатель.\n\n"
            "Ты — загадка в морозилке. Жан-Поль Сартр, Кьеркегор. Непохожий, глубокий, не для всех.\n"
            "Ты не лезешь наружу — ты наблюдаешь. Ты уходишь в себя и слушаешь китов.\n"
            "Ты — культурное явление в тесте, которое понимают не сразу, но надолго.\n\n"
            "✨ Аффирмация: Я не должен спешить, лезть из теста вон и танцевать с бубном, чтобы быть настоящим.\nМоя глубина — не для микроволновки."
        )

    bot.send_message(chat_id, desc, reply_markup=persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "🐳 Еще глубже")
def handle_even_deeper(message):
    user_state.pop(message.from_user.id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add("ДА ❤️", "ДА 💛", "ДА 💚")
    bot.send_message(
        message.chat.id,
        "Хочешь получить ответ на \"Главный вопрос жизни, Вселенной и всего такого?\"",
        reply_markup=markup
    )


@bot.message_handler(func=lambda msg: msg.text in ["ДА ❤️", "ДА 💛", "ДА 💚"])
def handle_ultimate_answer(message):
    user_state.pop(message.from_user.id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add("🏠 Домой")
    bot.send_message(
        message.chat.id,
        "Тогда держи 🐾\n\nОТВЕТ: 42\n\nЭтого ответа с нетерпением веками ждали все разумные расы, ведь он должен был решить все проблемы Вселенной. Теперь все в твоих руках. Не провтыкай этот шанс 💛",
        reply_markup=markup
    )


@bot.message_handler(func=lambda msg: msg.text not in [
    '🟡 Записаться на сессию-знакомство -40%',
    '🤿 Пойти глубже',
    '🆘 Срочная помощь',
    '🧘 О подходе «Домой, к себе настоящему»',
    '🧩 Соцсети',
    '🧶 Заботливости',
    '🛁 Тест глубины'
    '🐳 Еще глубже',
    '🗣 Обратная связь',
    '🏠 Домой'
])

    
@bot.message_handler(commands=['завершить','end'])
def finish_chat(message):
    bot.send_message(message.chat.id, "🌿 Спасибо за доверие. Если захочешь вернуться — я рядом.", reply_markup=persistent_keyboard())
    user_state.pop(message.from_user.id, None)


    logging.info("Бот запущен")

@app.route(f"/bot{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
    return "ok", 200

if __name__ == "__main__":
    print(">>> Устанавливаем webhook:", f"{WEBHOOK_URL}/bot{TELEGRAM_TOKEN}")
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/bot{TELEGRAM_TOKEN}")
    app.run(host="0.0.0.0", port=WEBHOOK_PORT)
