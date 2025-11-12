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

# OWNER_ID обязательно как int
try:
    OWNER_ID = int(os.getenv("OWNER_ID"))
except (TypeError, ValueError):
    raise ValueError("❌ OWNER_ID не найден или неверный формат. Укажи число в Railway Variables.")
    print(f"OWNER_ID = {OWNER_ID}")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден! Проверь переменные окружения на Railway или .env файл.")
@@ -42,6 +40,8 @@
user_messages = {}
broadcast_mode = {}
panel_shown = set()
# НОВОЕ: состояния для верификации
verification_state = {}  # {user_id: 'waiting_screenshot' | 'waiting_id' | None}

# === Вспомогательные функции ===
def track_message(user_id, message_id):
@@ -82,7 +82,6 @@
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Проверяем: это владелец?
    if user_id == OWNER_ID:
        reply_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📢 Сделать рассылку")]],
@@ -100,7 +99,6 @@
    )
    track_message(user_id, message.message_id)

    # Только владельцу — включаем панель один раз
    if user_id == OWNER_ID and user_id not in panel_shown:
        await bot.send_message(
            chat_id=chat_id,
@@ -118,7 +116,8 @@
        'subscribed': False,
        'signal_count': 0,
        'deposit_made': False,
        'last_signal_time': None
        'last_signal_time': None,
        'verification_approved': False  # НОВОЕ
    })
    user_messages.setdefault(user_id, [])
    await show_main_menu(update.effective_chat.id, user_id, context.bot)
@@ -153,6 +152,11 @@
        await show_timer_and_reset(query, user_id, context)
    elif query.data == 'back_to_start':
        await show_main_menu(query.message.chat_id, user_id, context.bot)
    # НОВЫЕ обработчики для верификации
    elif query.data.startswith('approve_'):
        await approve_user(query, context)
    elif query.data.startswith('reject_'):
        await reject_user(query, context)


# === Регистрация ===
@@ -182,8 +186,40 @@
    track_message(user_id, msg.message_id)


# === После регистрации ===
# === НОВОЕ: После нажатия "Зарегистрировался" - запрос верификации ===
async def handle_registered(query, user_id, context):
    # Проверяем, прошёл ли пользователь верификацию
    if not user_data[user_id].get('verification_approved', False):
        # Запускаем процесс верификации
        text = (
            "📸 <b>Верификация аккаунта</b>\n\n"
            "Пожалуйста, отправьте скриншот вашего профиля на сайте 1W.\n"
            "На скриншоте должен быть виден ваш ID."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            msg = await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        track_message(user_id, msg.message_id)
        
        # Устанавливаем состояние ожидания скриншота
        verification_state[user_id] = 'waiting_screenshot'
        return
    
    # Если уже верифицирован - продолжаем
    await proceed_after_verification(query, user_id, context)


# === НОВОЕ: Продолжение после верификации ===
async def proceed_after_verification(query, user_id, context):
    user_data[user_id]['registered'] = True
    text = (
        "✅ <b>Ваш аккаунт успешно синхронизирован с ботом!</b>\n\n"
@@ -208,6 +244,134 @@
    track_message(user_id, msg.message_id)


# === НОВОЕ: Обработка фото и текста для верификации ===
async def handle_verification_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Пропускаем владельца и рассылку
    if user_id == OWNER_ID:
        return
    
    state = verification_state.get(user_id)
    
    if state == 'waiting_screenshot':
        if update.message.photo:
            # Сохраняем фото
            user_data[user_id]['verification_photo'] = update.message.photo[-1].file_id
            
            await update.message.reply_text(
                "✅ Скриншот получен!\n\n"
                "Теперь отправьте ваш ID (только цифры)."
            )
            verification_state[user_id] = 'waiting_id'
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте именно фото (скриншот)."
            )
    
    elif state == 'waiting_id':
        if update.message.text and update.message.text.replace(' ', '').isdigit():
            # Сохраняем ID
            user_data[user_id]['verification_id'] = update.message.text.strip()
            
            # Отправляем владельцу на проверку
            await send_verification_to_owner(update, context, user_id)
            
            await update.message.reply_text(
                "⏳ <b>Ваша заявка отправлена на проверку!</b>\n\n"
                "Ожидайте подтверждения от администратора.",
                parse_mode="HTML"
            )
            
            # Сбрасываем состояние
            verification_state[user_id] = None
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте только цифры (ваш ID)."
            )


# === НОВОЕ: Отправка владельцу для проверки ===
async def send_verification_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    photo_id = user_data[user_id].get('verification_photo')
    user_game_id = user_data[user_id].get('verification_id')
    username = update.effective_user.username or "Нет username"
    full_name = update.effective_user.full_name
    
    text = (
        f"🔔 <b>Новая заявка на регистрацию!</b>\n\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"📱 Username: @{username}\n"
        f"🎮 ID на сайте: <code>{user_game_id}</code>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f'approve_{user_id}'),
            InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_{user_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_photo(
        chat_id=OWNER_ID,
        photo=photo_id,
        caption=text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )


# === НОВОЕ: Одобрение заявки ===
async def approve_user(query, context):
    user_id = int(query.data.split('_')[1])
    
    # Помечаем пользователя как верифицированного
    user_data[user_id]['verification_approved'] = True
    
    # Уведомляем владельца
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ <b>ОДОБРЕНО</b>",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            "✅ <b>Ваша заявка одобрена!</b>\n\n"
            "Для того чтобы продолжить работу с ботом напишите /start и пройдите процедуру вновь."
        ),
        parse_mode="HTML"
    )


# === НОВОЕ: Отклонение заявки ===
async def reject_user(query, context):
    user_id = int(query.data.split('_')[1])
    
    # Уведомляем владельца
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ <b>ОТКЛОНЕНО</b>",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            "❌ <b>Ваша заявка отклонена</b>\n\n"
            "Возможные причины:\n"
            "• Неверный ID\n"
            "• Некорректный скриншот\n"
            "• Не использован промокод\n\n"
            f"Свяжитесь с поддержкой: @{HELP_CONTACT}"
        ),
        parse_mode="HTML"
    )


# === Инструкция ===
async def show_exit_instruction(query, user_id, context):
    text = "📖 Нажмите кнопку ниже, чтобы открыть инструкцию и затем вернитесь назад 👇"
@@ -223,8 +387,13 @@
    track_message(user_id, msg.message_id)


# === Сигналы ===
# === Сигналы (требуют верификации) ===
async def send_signal_1(query, user_id, context):
    # НОВОЕ: Проверяем верификацию
    if not user_data[user_id].get('verification_approved', False):
        await query.answer("❌ Сначала пройдите верификацию!", show_alert=True)
        return
    
    await delete_all_messages(query.message.chat_id, user_id, context.bot)
    photo_path = os.path.join(os.getcwd(), "signal1.png")
    text = (
@@ -237,11 +406,20 @@
    )
    keyboard = [[InlineKeyboardButton("✅ Сигнал сработал, перейти ко 2", callback_data='signal1_success')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    with open(photo_path, "rb") as photo:
        msg = await context.bot.send_photo(
    
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            msg = await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    else:
        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=text,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
@@ -270,11 +448,20 @@
    )
    keyboard = [[InlineKeyboardButton("➡️ Перейти к 3 сигналу", callback_data='signal2_next')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    with open(photo_path, "rb") as photo:
        msg = await context.bot.send_photo(
    
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            msg = await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    else:
        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=text,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
@@ -293,11 +480,20 @@
    )
    keyboard = [[InlineKeyboardButton("🔄 Получить новые сигналы", callback_data='new_signals')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    with open(photo_path, "rb") as photo:
        msg = await context.bot.send_photo(
    
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            msg = await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    else:
        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            photo=photo,
            caption=text,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
@@ -313,6 +509,8 @@
# === Рассылка ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Владелец - рассылка
    if user_id == OWNER_ID and update.message.text == "📢 Сделать рассылку":
        await update.message.reply_text("✍️ Отправьте сообщение, фото или ссылку для рассылки пользователям.")
        broadcast_mode[user_id] = True
@@ -337,6 +535,10 @@

        await msg.reply_text(f"✅ Рассылка завершена. Отправлено {count} пользователям.")
        broadcast_mode[user_id] = False
        return
    
    # Обычные пользователи - верификация
    await handle_verification_media(update, context)


# === Запуск ===
@@ -345,9 +547,10 @@
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_verification_media))
    logger.info("🤖 Бот запущен и готов к работе!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

    main()
