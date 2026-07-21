import logging
import os
import signal
import sys
import threading

import telebot
from telebot import apihelper, types

from categories import format_categories
from config import Config
from database import Database
from handlers.voice_transaction_handler import VoiceTransactionHandler
from services.deepseek_transaction_parser import DeepSeekTransactionParser
from services.groq_transcriber import GroqTranscriber


def build_bot(config: Config):
    if proxy_url := os.getenv("PROXY_URL", ""):
        apihelper.proxy = {"https": proxy_url}
    bot = telebot.TeleBot(config.bot_token)
    db = Database(config.sqlite_db_path)
    category_states = {}
    semaphore = threading.BoundedSemaphore(config.max_concurrent_processing)
    handler = VoiceTransactionHandler(
        bot=bot,
        db=db,
        config=config,
        transcriber=GroqTranscriber(config.groq_api_key, config.groq_base_url, config.groq_stt_model, config.groq_timeout_sec),
        parser=DeepSeekTransactionParser(config.deepseek_api_key, config.deepseek_api_url, config.deepseek_model, config.deepseek_timeout_sec),
        semaphore=semaphore,
    )

    @bot.message_handler(commands=["start", "help"])
    def start(message):
        bot.reply_to(
            message,
            "SmartExpense 2.0 готов.\n\n"
            "Отправьте короткое голосовое сообщение до 8 секунд с одной операцией: "
            "например, «пятьсот продукты молоко» или «получил зарплату сто тысяч».\n\n"
            "Доступные категории:\n"
            f"{format_categories()}\n\n"
            "P.S. Этот бот создан благодаря моей любимой жене.",
            reply_markup=_category_menu_keyboard(),
        )

    @bot.message_handler(commands=["categories"])
    def categories(message):
        bot.reply_to(message, _user_categories_text(db, message.from_user.id), reply_markup=_category_menu_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == "cat_add")
    def category_add(call):
        bot.answer_callback_query(call.id)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Расход", callback_data="cat_add_type:EXPENSE"))
        keyboard.add(types.InlineKeyboardButton("Доход", callback_data="cat_add_type:INCOME"))
        bot.send_message(call.message.chat.id, "Для какого типа добавить категорию?", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_add_type:"))
    def category_add_type(call):
        transaction_type = call.data.split(":", 1)[1]
        category_states[call.from_user.id] = {"action": "add_category", "transaction_type": transaction_type}
        bot.answer_callback_query(call.id)
        noun = "расхода" if transaction_type == "EXPENSE" else "дохода"
        bot.send_message(call.message.chat.id, f"Напишите название новой категории {noun}. Например: Семья")

    @bot.callback_query_handler(func=lambda call: call.data == "cat_delete")
    def category_delete(call):
        rows = db.list_user_categories(call.from_user.id)
        bot.answer_callback_query(call.id)
        if not rows:
            bot.send_message(call.message.chat.id, "У вас пока нет пользовательских категорий.")
            return
        keyboard = types.InlineKeyboardMarkup()
        for row in rows:
            prefix = "Расход" if row.transaction_type == "EXPENSE" else "Доход"
            keyboard.add(types.InlineKeyboardButton(f"{prefix}: {row.title}", callback_data=f"cat_delete_id:{row.id}"))
        bot.send_message(call.message.chat.id, "Выберите категорию для удаления:", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_delete_id:"))
    def category_delete_id(call):
        category_id = int(call.data.split(":", 1)[1])
        deleted = db.deactivate_user_category(call.from_user.id, category_id)
        bot.answer_callback_query(call.id, "Удалено" if deleted else "Категория не найдена")
        bot.send_message(call.message.chat.id, "Категория удалена." if deleted else "Категория не найдена.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_tx:"))
    def delete_transaction(call):
        transaction_id = int(call.data.split(":", 1)[1])
        deleted = db.delete_transaction(transaction_id, call.from_user.id, call.message.chat.id)
        bot.answer_callback_query(call.id, "Запись удалена" if deleted else "Не удалось удалить")
        if deleted:
            bot.edit_message_text("Запись удалена.", call.message.chat.id, call.message.message_id)

    @bot.message_handler(content_types=["voice"])
    def voice(message):
        handler.handle(message)

    @bot.message_handler(content_types=["text", "audio", "video", "video_note", "document", "photo", "sticker", "contact", "location"])
    def unsupported(message):
        if message.content_type == "text" and message.from_user.id in category_states:
            state = category_states.pop(message.from_user.id)
            title = (message.text or "").strip()
            if len(title) < 2:
                bot.reply_to(message, "Название категории слишком короткое.")
                return
            code = db.add_user_category(message.from_user.id, state["transaction_type"], title[:100])
            bot.reply_to(message, f"Категория «{title[:100]}» создана.\nКод: {code}", reply_markup=_category_menu_keyboard())
            return
        if message.chat.type == "private":
            bot.reply_to(message, "Первая версия бота принимает только голосовые сообщения до 8 секунд.")

    return bot


def _category_menu_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Добавить категорию", callback_data="cat_add"))
    keyboard.add(types.InlineKeyboardButton("Удалить свою категорию", callback_data="cat_delete"))
    return keyboard


def _user_categories_text(db: Database, telegram_user_id: int) -> str:
    rows = db.list_user_categories(telegram_user_id)
    if not rows:
        custom = "Пользовательских категорий пока нет."
    else:
        custom = "\n".join(
            f"- {'Расход' if row.transaction_type == 'EXPENSE' else 'Доход'}: {row.title} ({row.code})" for row in rows
        )
    return f"SmartExpense 2.0\n\nСистемные категории:\n{format_categories()}\n\nВаши категории:\n{custom}"


def main() -> int:
    config = Config.from_env()
    try:
        config.validate()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    bot = build_bot(config)

    def stop(_signum, _frame):
        logging.getLogger(__name__).info("Stopping bot polling")
        bot.stop_polling()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logging.getLogger(__name__).info("Voice Budget Bot polling is starting")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
