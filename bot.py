import logging
import os
import signal
import sys
import threading
from logging.handlers import RotatingFileHandler

import telebot
from telebot import apihelper, types

from categories import format_categories
from config import Config
from database import Database
from handlers.voice_transaction_handler import VoiceTransactionHandler
from services.deepseek_transaction_parser import DeepSeekTransactionParser
from services.stt_transcriber import FallbackTranscriber, SttTranscriber
from services.reports import build_last_30_days_expense_chart, build_last_30_days_income_chart
from services.scheduler import ScheduledEventRunner, calendar_text
from welcome import COMMANDS, categories_text, commands_text, welcome_text


def build_bot(config: Config):
    if proxy_url := os.getenv("PROXY_URL", ""):
        apihelper.proxy = {"https": proxy_url}
    bot = telebot.TeleBot(config.bot_token)
    _set_bot_commands(bot)
    db = Database(config.sqlite_db_path)
    category_states = {}
    scheduler = ScheduledEventRunner(bot, db, config)
    semaphore = threading.BoundedSemaphore(config.max_concurrent_processing)
    transcriber = SttTranscriber(
        config.stt_api_key,
        config.stt_base_url,
        config.stt_model,
        config.stt_timeout_sec,
        config.stt_verify_ssl,
        "stt",
    )
    if config.groq_fallback_enabled:
        groq_fallback = SttTranscriber(
            config.groq_api_key,
            config.groq_base_url,
            config.groq_stt_model,
            config.groq_timeout_sec,
            True,
            "groq_fallback",
        )
        transcriber = FallbackTranscriber(transcriber, groq_fallback)
    handler = VoiceTransactionHandler(
        bot=bot,
        db=db,
        config=config,
        transcriber=transcriber,
        parser=DeepSeekTransactionParser(config.deepseek_api_key, config.deepseek_api_url, config.deepseek_model, config.deepseek_timeout_sec),
        semaphore=semaphore,
    )

    @bot.message_handler(commands=["start", "help"])
    def start(message):
        if not _is_allowed_message(config, message):
            return
        _send_welcome(bot, message, config)

    @bot.message_handler(commands=["menu"])
    def menu(message):
        if not _is_allowed_message(config, message):
            return
        bot.reply_to(message, commands_text(), reply_markup=_main_menu_keyboard())

    @bot.message_handler(commands=["categories"])
    def categories(message):
        if not _is_allowed_message(config, message):
            return
        bot.reply_to(message, _user_categories_text(db, message.from_user.id), reply_markup=_category_menu_keyboard())

    @bot.message_handler(commands=["calendar"])
    def calendar(message):
        if not _is_allowed_message(config, message):
            return
        bot.reply_to(message, calendar_text(db, message.from_user.id, config.app_timezone))

    @bot.message_handler(commands=["report"])
    def report(message):
        if not _is_allowed_message(config, message):
            return
        _send_last_30_days_report(bot, db, config, message.chat.id, message.from_user.id)

    @bot.message_handler(commands=["family"])
    def family(message):
        if not _is_allowed_message(config, message):
            return
        parts = (message.text or "").split(maxsplit=2)
        action = parts[1].lower() if len(parts) > 1 else ""
        if action == "create":
            name = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
            if not name:
                bot.reply_to(message, "Использование: /family create <имя семьи>")
                return
            family_id = db.create_family(name[:255], message.from_user.id)
            if family_id:
                bot.reply_to(message, f"👨‍👩‍👧 Семья «{name[:255]}» создана.\n\nПригласите партнёра: /family invite")
            else:
                bot.reply_to(message, "Вы уже состоите в семье.")
            return
        if action == "invite":
            code = db.generate_invite_code(message.from_user.id)
            if not code:
                bot.reply_to(message, "У вас пока нет семьи. Создайте её: /family create <имя семьи>")
                return
            bot.reply_to(message, f"🔑 Код приглашения: `{code}`\n\nПередайте его партнёру. Он введёт: /join {code}", parse_mode="Markdown")
            return
        _send_family_status(bot, db, message.from_user.id)

    @bot.message_handler(commands=["join"])
    def join(message):
        if not _is_allowed_message(config, message):
            return
        parts = (message.text or "").split()
        if len(parts) < 2:
            bot.reply_to(message, "Использование: /join <код приглашения>")
            return
        ok, family_name = db.join_family_by_code(message.from_user.id, parts[1])
        if ok:
            bot.reply_to(message, f"👨‍👩‍👧 Вы присоединились к семье «{family_name}».")
        else:
            messages = {
                "invite_code_not_found": "Код приглашения не найден. Проверьте код.",
                "invite_code_expired": "Код приглашения истёк. Попросите новый: /family invite",
                "already_in_family": "Вы уже состоите в семье.",
            }
            bot.reply_to(message, messages.get(family_name, "Не удалось вступить в семью."))

    @bot.callback_query_handler(func=lambda call: call.data == "show_categories")
    def show_categories(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, _user_categories_text(db, call.from_user.id), reply_markup=_category_menu_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == "cat_add")
    def category_add(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        bot.answer_callback_query(call.id)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Расход", callback_data="cat_add_type:EXPENSE"))
        keyboard.add(types.InlineKeyboardButton("Доход", callback_data="cat_add_type:INCOME"))
        bot.send_message(call.message.chat.id, "Для какого типа добавить категорию?", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_add_type:"))
    def category_add_type(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        transaction_type = call.data.split(":", 1)[1]
        category_states[call.from_user.id] = {"action": "add_category", "transaction_type": transaction_type}
        bot.answer_callback_query(call.id)
        noun = "расхода" if transaction_type == "EXPENSE" else "дохода"
        bot.send_message(call.message.chat.id, f"Напишите название новой категории {noun}. Например: Семья")

    @bot.callback_query_handler(func=lambda call: call.data == "cat_delete")
    def category_delete(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
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
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        category_id = int(call.data.split(":", 1)[1])
        deleted = db.deactivate_user_category(call.from_user.id, category_id)
        bot.answer_callback_query(call.id, "Удалено" if deleted else "Категория не найдена")
        bot.send_message(call.message.chat.id, "Категория удалена." if deleted else "Категория не найдена.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_tx:"))
    def delete_transaction(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        transaction_id = int(call.data.split(":", 1)[1])
        deleted = db.delete_transaction(transaction_id, call.from_user.id, call.message.chat.id)
        bot.answer_callback_query(call.id, "Запись удалена" if deleted else "Не удалось удалить")
        if deleted:
            bot.edit_message_text("Запись удалена.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("scope_tx:"))
    def scope_transaction(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        _, transaction_id, scope = call.data.split(":", 2)
        transaction_id = int(transaction_id)
        family_id = None
        if scope == "family":
            family = db.get_family_for_user(call.from_user.id)
            if not family:
                bot.answer_callback_query(call.id, "У вас пока нет семьи. Создайте её: /family create")
                return
            family_id = family.id
        updated = db.set_transaction_scope(transaction_id, call.from_user.id, scope, family_id)
        if not updated:
            bot.answer_callback_query(call.id, "Не удалось изменить")
            return
        bot.answer_callback_query(call.id)
        label = "семейное" if scope == "family" else "личное"
        bot.edit_message_text(f"{call.message.text}\n\n🏷️ Отмечено как {label}.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_event:"))
    def delete_scheduled_event(call):
        if not _is_allowed_call(config, call):
            bot.answer_callback_query(call.id)
            return
        event_id = int(call.data.split(":", 1)[1])
        deleted = db.delete_scheduled_event(event_id, call.from_user.id, call.message.chat.id)
        bot.answer_callback_query(call.id, "Событие удалено" if deleted else "Не удалось удалить")
        if deleted:
            bot.edit_message_text("Событие удалено.", call.message.chat.id, call.message.message_id)

    @bot.message_handler(content_types=["voice"])
    def voice(message):
        handler.handle(message)

    @bot.message_handler(content_types=["text", "audio", "video", "video_note", "document", "photo", "sticker", "contact", "location"])
    def unsupported(message):
        if not _is_allowed_message(config, message):
            return
        if message.content_type == "text" and _handle_menu_text(bot, db, config, message, category_states):
            return
        if message.content_type == "text" and message.from_user.id in category_states:
            state = category_states.pop(message.from_user.id)
            title = (message.text or "").strip()
            if len(title) < 2:
                bot.reply_to(message, "Название категории слишком короткое.")
                return
            code = db.add_user_category(message.from_user.id, state["transaction_type"], title[:100])
            bot.reply_to(message, f"Категория «{title[:100]}» создана.\nКод: {code}", reply_markup=_category_menu_keyboard())
            return
        if message.content_type == "text" and not (message.text or "").lstrip().startswith("/"):
            handler.handle_text(message)
            return
        if message.chat.type == "private":
            bot.reply_to(
                message,
                f"Бот принимает голосовые сообщения до {config.max_voice_duration_sec} секунд или текстовые записи расходов, доходов и напоминаний.",
            )

    return bot, scheduler


def _send_family_status(bot, db: Database, telegram_user_id: int) -> None:
    family = db.get_family_for_user(telegram_user_id)
    if not family:
        bot.send_message(
            telegram_user_id,
            "👨‍👩‍👧 У вас пока нет семьи.\n\nСоздайте её:\n`/family create <имя семьи>`\n\nЗатем пригласите партнёра:\n`/family invite`",
            parse_mode="Markdown",
        )
        return
    members = db.list_family_members(family.id)
    lines = [f"👨‍👩‍👧 {family.name}", ""]
    for member in members:
        role = "👑 владелец" if member.role == "owner" else "👤 участник"
        lines.append(f"{role} · {member.telegram_user_id}")
    lines.extend(["", "Сменить приглашение: /family invite"])
    bot.send_message(telegram_user_id, "\n".join(lines))


def _category_menu_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Показать категории", callback_data="show_categories"))
    keyboard.add(types.InlineKeyboardButton("Добавить категорию", callback_data="cat_add"))
    keyboard.add(types.InlineKeyboardButton("Удалить свою категорию", callback_data="cat_delete"))
    return keyboard


def _main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("Календарь", "Категории")
    keyboard.add("Отчет за 30 дней")
    keyboard.add("Добавить категорию", "Удалить категорию")
    keyboard.add("Команды")
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


def _set_bot_commands(bot) -> None:
    try:
        bot.set_my_commands([types.BotCommand(command.strip("/"), description) for command, description in COMMANDS])
    except Exception:
        logging.getLogger(__name__).warning("Could not update Telegram command menu", exc_info=True)


def _send_welcome(bot, message, config) -> None:
    keyboard = _category_menu_keyboard()
    text = welcome_text(config)
    image_path = config.welcome_image_path
    if image_path.exists():
        with open(image_path, "rb") as image:
            bot.send_photo(message.chat.id, image, caption=text, reply_markup=keyboard)
    else:
        bot.reply_to(message, text, reply_markup=keyboard)
    bot.send_message(message.chat.id, "Меню доступно кнопками ниже.", reply_markup=_main_menu_keyboard())


def _handle_menu_text(bot, db: Database, config: Config, message, category_states: dict) -> bool:
    text = (message.text or "").strip().lower()
    if text == "календарь":
        bot.reply_to(message, calendar_text(db, message.from_user.id, config.app_timezone))
        return True
    if text in {"отчет за 30 дней", "отчёт за 30 дней", "отчет за месяц", "отчёт за месяц"}:
        if not _is_allowed_message(config, message):
            return True
        _send_last_30_days_report(bot, db, config, message.chat.id, message.from_user.id)
        return True
    if text == "категории":
        bot.reply_to(message, _user_categories_text(db, message.from_user.id), reply_markup=_category_menu_keyboard())
        return True
    if text == "добавить категорию":
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Расход", callback_data="cat_add_type:EXPENSE"))
        keyboard.add(types.InlineKeyboardButton("Доход", callback_data="cat_add_type:INCOME"))
        bot.reply_to(message, "Для какого типа добавить категорию?", reply_markup=keyboard)
        return True
    if text == "удалить категорию":
        rows = db.list_user_categories(message.from_user.id)
        if not rows:
            bot.reply_to(message, "У вас пока нет пользовательских категорий.")
            return True
        keyboard = types.InlineKeyboardMarkup()
        for row in rows:
            prefix = "Расход" if row.transaction_type == "EXPENSE" else "Доход"
            keyboard.add(types.InlineKeyboardButton(f"{prefix}: {row.title}", callback_data=f"cat_delete_id:{row.id}"))
        bot.reply_to(message, "Выберите категорию для удаления:", reply_markup=keyboard)
        return True
    if text == "команды":
        bot.reply_to(message, commands_text(), reply_markup=_main_menu_keyboard())
        return True
    return False


def _send_last_30_days_report(bot, db: Database, config: Config, chat_id: int, telegram_user_id: int) -> None:
    paths = []
    try:
        for builder in (build_last_30_days_expense_chart, build_last_30_days_income_chart):
            path, caption = builder(db, telegram_user_id, config.app_timezone, config.temp_audio_dir / "reports")
            if not path:
                bot.send_message(chat_id, caption)
                continue
            paths.append(path)
            with open(path, "rb") as image:
                bot.send_photo(chat_id, image, caption=caption)
    except Exception:
        logging.getLogger(__name__).exception("Could not build last 30 days report user_id=%s", telegram_user_id)
        bot.send_message(chat_id, "⚠️ Не удалось подготовить графический отчет.")
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def _is_allowed_message(config: Config, message) -> bool:
    user_id = message.from_user.id if message.from_user else 0
    return _is_allowed_identity(config, user_id, message.chat.id, message.chat.type)


def _is_allowed_call(config: Config, call) -> bool:
    user_id = call.from_user.id if call.from_user else 0
    chat = call.message.chat if call.message else None
    chat_id = chat.id if chat else 0
    chat_type = chat.type if chat else "private"
    return _is_allowed_identity(config, user_id, chat_id, chat_type)


def _is_allowed_identity(config: Config, user_id: int, chat_id: int, chat_type: str) -> bool:
    if config.allowed_user_ids and user_id not in config.allowed_user_ids:
        return False
    if chat_type in {"group", "supergroup"}:
        return chat_id in config.allowed_chat_ids
    if config.allowed_chat_ids:
        return chat_id in config.allowed_chat_ids
    return chat_type == "private"


def main() -> int:
    config = Config.from_env()
    try:
        config.validate()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    config.log_file.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        config.log_file,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        handlers=[stream_handler, file_handler],
        force=True,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    bot, scheduler = build_bot(config)
    scheduler.start()

    def stop(_signum, _frame):
        logging.getLogger(__name__).info("Stopping bot polling")
        scheduler.stop()
        bot.stop_polling()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logging.getLogger(__name__).info("Voice Budget Bot polling is starting")
    try:
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
    finally:
        scheduler.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
