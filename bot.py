import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from datetime import datetime
import os
from dotenv import load_dotenv

# === Загрузка .env ===
load_dotenv()

# === Настройка логов ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
REGISTRATION_URL = os.getenv("REGISTRATION_URL")
HELP_CONTACT = os.getenv("HELP_CONTACT")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
PROMO_CODE = os.getenv("PROMO_CODE", "CXEMA4MINES")
TELEGRAPH_URL = os.getenv("TELEGRAPH_URL", "https://telegra.ph/Kak-vyjti-iz-starogo-akkaunta-11-11-2")

OWNER_ID = 1253708269  # ✅ твой Telegram ID

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env!")

# === Хранилища ===
user_data = {}
user_messages = {}
broadcast_mode = {}
panel_shown = set() 

# === Вспомогательные функции ===
def track_message(user_id, message_id):
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message_id)


async def delete_all_messages(chat_id, user_id, bot):
    if user_id in user_messages and user_messages[user_id]:
        while user_messages[user_id]:
            message_id = user_messages[user_id].pop()
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass


# === Главное меню ===
async def show_main_menu(chat_id, user_id, bot):
    await delete_all_messages(chat_id, user_id, bot)

    text = (
        "🪜 <b>Шаг 1 — Зарегистрируйся</b>\n\n"
        "Для синхронизации с ботом вам необходимо создать новый аккаунт строго по ссылке из бота и применить промокод:\n\n"
        f"🎁 <b>Промокод: 👉 {PROMO_CODE} 👈</b>\n\n"
        "Если вы открыли ссылку и попали в старый аккаунт, то вам нужно:\n"
        "🔹 Выйти из старого аккаунта\n"
        "🔹 Закрыть сайт\n"
        "🔹 Снова открыть сайт через кнопку в боте\n"
        "🔹 Пройти регистрацию с указанием промокода 💎"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Регистрация", callback_data='register')],
        [InlineKeyboardButton("📖 Инструкция выхода", callback_data='exit_instruction')],
        [InlineKeyboardButton("❓ Помощь", url=f"https://t.me/{HELP_CONTACT}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if user_id == OWNER_ID:
        reply_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📢 Сделать рассылку")]],
            resize_keyboard=True
        )
    else:
        reply_keyboard = ReplyKeyboardRemove()

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    track_message(user_id, message.message_id)

    if user_id == OWNER_ID and user_id not in panel_shown:
        await bot.send_message(
            chat_id=chat_id,
            text="💬 Панель активна (для владельца)",
            reply_markup=reply_keyboard
        )
        panel_shown.add(user_id)


# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data.setdefault(user_id, {
        'registered': False,
        'subscribed': False,
        'signal_count': 0,
        'deposit_made': False,
        'last_signal_time': None
    })
    user_messages.setdefault(user_id, [])
    await show_main_menu(update.effective_chat.id, user_id, context.bot)


# === Обработка нажатий ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        return  

    user_id = query.from_user.id

    if query.data == 'register':
        await handle_registration(query, user_id, context)
    elif query.data == 'registered':
        await handle_registered(query, user_id, context)
    elif query.data == 'exit_instruction':
        await show_exit_instruction(query, user_id, context)
    elif query.data == 'subscribed':
        await send_signal_1(query, user_id, context)
    elif query.data == 'signal1_success':
        await show_deposit_request(query, user_id, context)
    elif query.data == 'deposit_ready':
        await send_signal_2(query, user_id, context)
    elif query.data == 'signal2_next':
        await send_signal_3(query, user_id, context)
    elif query.data == 'new_signals':
        await show_timer_and_reset(query, user_id, context)
    elif query.data == 'back_to_start':
        await show_main_menu(query.message.chat_id, user_id, context.bot)


# === Регистрация ===
async def handle_registration(query, user_id, context):
    text = (
        f"🌐 Перейдите по ссылке для регистрации и используйте промокод:\n\n"
        f"🎁 <b>{PROMO_CODE}</b>"
    )
    keyboard = [
        [InlineKeyboardButton("🔗 Перейти к регистрации", url=REGISTRATION_URL)],
        [
            InlineKeyboardButton("✅ Зарегистрировался", callback_data='registered'),
            InlineKeyboardButton("⬅️ Назад", callback_data='back_to_start')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    track_message(user_id, msg.message_id)


# === После регистрации ===
async def handle_registered(query, user_id, context):
    user_data[user_id]['registered'] = True
    text = (
        "✅ <b>Ваш аккаунт успешно синхронизирован с ботом!</b>\n\n"
        "Для получения первого сигнала подпишитесь на наш Telegram-канал 👇"
    )
    keyboard = [
        [InlineKeyboardButton("📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ Подписался", callback_data='subscribed')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    track_message(user_id, msg.message_id)


# === Инструкция ===
async def show_exit_instruction(query, user_id, context):
    text = "📖 Нажмите кнопку ниже, чтобы открыть инструкцию и затем вернитесь назад 👇"
    keyboard = [
        [InlineKeyboardButton("📘 Открыть инструкцию", url=TELEGRAPH_URL)],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await query.edit_message_text(text, reply_markup=reply_markup)
    track_message(user_id, msg.message_id)


# === Сигналы ===
async def send_signal_1(query, user_id, context):
    await delete_all_messages(query.message.chat_id, user_id, context.bot)

    photo_path = os.path.join(os.getcwd(), "signal1.png") 
    text = (
        "✅ Отлично! Вот ваш первый сигнал 1W MINES!\n\n"
        "💣 КОЛ-ВО МИН: 2\n\n"
        "🚨 СХЕМА ОТ ИИ:\n"
        "• Минимальная ставка — 11 игр на проигрыш\n"
        "• Увеличьте ставку ×2 и возьмите минимальный выигрыш\n"
        "• Потом поставьте 1000₽ и закройте поля строго по схеме ниже 💥"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Сигнал сработал, перейти ко 2", callback_data='signal1_success')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(photo_path, "rb") as photo:
        msg = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    track_message(user_id, msg.message_id)


async def show_deposit_request(query, user_id, context):
    await delete_all_messages(query.message.chat_id, user_id, context.bot)
    text = "💰 Для получения второго сигнала сделайте депозит от 2000₽ 💵"
    keyboard = [[InlineKeyboardButton("✅ Готово", callback_data='deposit_ready')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await query.message.reply_text(text, reply_markup=reply_markup)
    track_message(user_id, msg.message_id)


async def send_signal_2(query, user_id, context):
    await delete_all_messages(query.message.chat_id, user_id, context.bot)

    photo_path = os.path.join(os.getcwd(), "signal2.png")  
    text = (
        "2️⃣ <b>2-ой сигнал успешно получен!</b>\n\n"
        "💣 КОЛ-ВО МИН: 2\n\n"
        "🚨 <b>СХЕМА/СТРАТЕГИЯ ОТ ИИ:</b>\n\n"
        "1️⃣ Сыграйте на минимальный выигрыш 3 раза подряд.\n"
        "2️⃣ Утройте минимальную ставку и сыграйте на поражение.\n"
        "3️⃣ Поставьте максимальную ставку от 1000₽ и закройте поля СТРОГО как на экране 🎯"
    )
    keyboard = [[InlineKeyboardButton("➡️ Перейти к 3 сигналу", callback_data='signal2_next')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(photo_path, "rb") as photo:
        msg = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    track_message(user_id, msg.message_id)


async def send_signal_3(query, user_id, context):
    await delete_all_messages(query.message.chat_id, user_id, context.bot)

    photo_path = os.path.join(os.getcwd(), "signal3.png")  
    text = (
        "3️⃣ <b>ТРЕТИЙ СИГНАЛ</b>\n\n"
        "💣 КОЛ-ВО МИН: 2\n\n"
        "🚨 <b>СХЕМА/СТРАТЕГИЯ ОТ ИИ:</b>\n\n"
        "1️⃣ Перезагрузите игру (нажмите выйти и зайдите снова)\n"
        "2️⃣ Поставьте максимальную ставку от 1000₽ и закройте поля СТРОГО как показано на экране 💎"
    )
    keyboard = [[InlineKeyboardButton("🔄 Получить новые сигналы", callback_data='new_signals')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(photo_path, "rb") as photo:
        msg = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    track_message(user_id, msg.message_id)
    user_data[user_id]['last_signal_time'] = datetime.now()


async def show_timer_and_reset(query, user_id, context):
    await delete_all_messages(query.message.chat_id, user_id, context.bot)
    await query.message.reply_text("⏰ Новые сигналы будут доступны через 24 часа.")


# === Рассылка (только для владельца) ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id == OWNER_ID and update.message.text == "📢 Сделать рассылку":
        await update.message.reply_text("✍️ Отправьте сообщение, фото или ссылку для рассылки пользователям.")
        broadcast_mode[user_id] = True
        return

    if user_id == OWNER_ID and broadcast_mode.get(user_id):
        msg = update.message
        count = 0
        for uid in user_data.keys():
            try:
                if msg.photo:
                    await context.bot.send_photo(
                        chat_id=uid,
                        photo=msg.photo[-1].file_id,
                        caption=msg.caption or ""
                    )
                else:
                    await context.bot.send_message(uid, msg.text or "")
                count += 1
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение {uid}: {e}")

        await msg.reply_text(f"✅ Рассылка завершена. Отправлено {count} пользователям.")
        broadcast_mode[user_id] = False


# === Запуск ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🤖 Бот запущен и готов к работе!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
