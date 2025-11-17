"""
Main Telegram bot file for SmartExpenseBot.
Initializes bot, handlers, and scheduler.
"""

import telebot
from telebot import types
import signal
import sys
import logging
from telebot import apihelper
from config import Config
from database import Database
from scheduler import ReminderScheduler
from handlers.expense_handler import ExpenseHandler
from handlers.income_handler import IncomeHandler
from handlers.report_handler import ReportHandler
from handlers.reminder_handler import ReminderHandler
from handlers.settings_handler import SettingsHandler
from handlers.about_handler import AboutHandler
from keyboards import create_main_keyboard, create_language_keyboard, create_currency_keyboard, create_report_keyboard, create_back_keyboard
from translations import get_translation, get_language_name

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure proxy if provided (optional)
if Config.PROXY_URL:
    apihelper.proxy = {'https': Config.PROXY_URL}
    logger.info(f"Using proxy: {Config.PROXY_URL}")
else:
    # No proxy configured - use direct connection
    apihelper.proxy = None
    logger.info("No proxy configured - using direct connection")

# Validate configuration
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

# Initialize bot
bot = telebot.TeleBot(Config.BOT_TOKEN)

# Initialize database
db = Database()

# Initialize scheduler first (needed by reminder handler)
scheduler = ReminderScheduler(bot, db)

# Initialize handlers
expense_handler = ExpenseHandler(bot, db)
income_handler = IncomeHandler(bot, db)
report_handler = ReportHandler(bot, db)
reminder_handler = ReminderHandler(bot, db)
settings_handler = SettingsHandler(bot, db)
about_handler = AboutHandler(bot, db)

# Pass scheduler to reminder handler for scheduling new reminders
reminder_handler.scheduler = scheduler

# User states: {user_id: "expense" | "report" | "reminder" | "settings" | "none"}
user_states = {}


# Start command
@bot.message_handler(commands=['start'])
def start_command(message: telebot.types.Message):
    """Handle /start command."""
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    # First time user - ask for language
    if not user.language or user.language == "en" and user.timezone == "UTC":
        bot.reply_to(
            message,
            get_translation("en", "welcome"),
            reply_markup=create_language_keyboard()
        )
        return
    
    # If language is set but timezone is not, ask for location/country
    if not user.timezone or user.timezone == 'UTC':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(types.KeyboardButton(get_translation(language, "share_location"), request_location=True))
        keyboard.add(types.KeyboardButton(get_translation(language, "enter_country")))
        keyboard.add(types.KeyboardButton(get_translation(language, "skip")))
        
        bot.reply_to(
            message,
            get_translation(language, "request_location_for_timezone"),
            reply_markup=keyboard
        )
        return
    
    # User is set up - show main menu
    bot.reply_to(
        message,
        get_translation(language, "main_menu"),
        reply_markup=create_main_keyboard(language)
    )


# Language selection callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_callback(call: telebot.types.CallbackQuery):
    """Handle language selection."""
    language_code = call.data.split("_")[1]
    db.update_user_language(call.from_user.id, language_code)
    user_states[call.from_user.id] = "none"
    
    # Get updated user
    user = db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
    language = user.language or "en"
    
    bot.answer_callback_query(call.id)
    
    # Request location/country if timezone is not set
    if not user.timezone or user.timezone == 'UTC':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(types.KeyboardButton(get_translation(language, "share_location"), request_location=True))
        keyboard.add(types.KeyboardButton(get_translation(language, "enter_country")))
        keyboard.add(types.KeyboardButton(get_translation(language, "skip")))
        
        bot.send_message(
            call.message.chat.id,
            get_translation(language, "request_location_for_timezone"),
            reply_markup=keyboard
        )
        return
    
    # Timezone is set - show main menu
    bot.send_message(
        call.message.chat.id,
        get_translation(language_code, "language_set"),
        reply_markup=create_main_keyboard(language_code)
    )


# Main menu button handlers
@bot.message_handler(func=lambda message: message.text and (
    get_translation("en", "expenses") in message.text or
    get_translation("ru", "expenses") in message.text or
    get_translation("uz", "expenses") in message.text
))
def expenses_button(message: telebot.types.Message):
    """Handle expenses button."""
    expense_handler.handle_expense_command(message)
    user_states[message.from_user.id] = "expense"


@bot.message_handler(func=lambda message: message.text and (
    get_translation("en", "income") in message.text or
    get_translation("ru", "income") in message.text or
    get_translation("uz", "income") in message.text
))
def income_button(message: telebot.types.Message):
    """Handle income button."""
    income_handler.handle_income_command(message)
    user_states[message.from_user.id] = "income"


@bot.message_handler(func=lambda message: message.text and (
    get_translation("en", "reports") in message.text or
    get_translation("ru", "reports") in message.text or
    get_translation("uz", "reports") in message.text
))
def reports_button(message: telebot.types.Message):
    """Handle reports button."""
    report_handler.handle_report_command(message)
    # Report mode removed - now uses buttons only


@bot.message_handler(func=lambda message: message.text and (
    get_translation("en", "reminders") in message.text or
    get_translation("ru", "reminders") in message.text or
    get_translation("uz", "reminders") in message.text
))
def reminders_button(message: telebot.types.Message):
    """Handle reminders button."""
    reminder_handler.handle_reminder_command(message)
    user_states[message.from_user.id] = "reminder"


@bot.message_handler(func=lambda message: message.text and (
    get_translation("en", "settings") in message.text or
    get_translation("ru", "settings") in message.text or
    get_translation("uz", "settings") in message.text
))
def settings_button(message: telebot.types.Message):
    """Handle settings button."""
    # Exit any active modes
    expense_handler.active_expense_mode.discard(message.from_user.id)
    income_handler.active_income_mode.discard(message.from_user.id)
    report_handler.active_report_mode.discard(message.from_user.id)
    reminder_handler.active_reminder_mode.discard(message.from_user.id)
    user_states[message.from_user.id] = "none"
    settings_handler.handle_settings_command(message)


@bot.message_handler(func=lambda message: message.text and (
    get_translation("en", "about") in message.text or
    get_translation("ru", "about") in message.text or
    get_translation("uz", "about") in message.text
))
def about_button(message: telebot.types.Message):
    """Handle about button."""
    # Exit any active modes
    expense_handler.active_expense_mode.discard(message.from_user.id)
    income_handler.active_income_mode.discard(message.from_user.id)
    report_handler.active_report_mode.discard(message.from_user.id)
    reminder_handler.active_reminder_mode.discard(message.from_user.id)
    user_states[message.from_user.id] = "none"
    about_handler.handle_about_command(message)


# Expense confirmation callbacks
@bot.callback_query_handler(func=lambda call: call.data == "confirm_yes" and call.from_user.id in expense_handler.pending_expenses)
def confirm_expense(call: telebot.types.CallbackQuery):
    """Handle expense confirmation (yes)."""
    expense_handler.handle_expense_confirmation(call, confirmed=True)


@bot.callback_query_handler(func=lambda call: call.data == "confirm_no" and call.from_user.id in expense_handler.pending_expenses)
def reject_expense(call: telebot.types.CallbackQuery):
    """Handle expense rejection (no)."""
    expense_handler.handle_expense_confirmation(call, confirmed=False)


# Income confirmation callbacks
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_yes", "confirm_no"] and call.from_user.id in income_handler.pending_incomes)
def income_confirm_callback(call: telebot.types.CallbackQuery):
    """Handle income confirmation callback."""
    income_handler.handle_income_confirm(call)


# Settings callbacks
@bot.callback_query_handler(func=lambda call: call.data == "settings_lang")
def settings_lang_callback(call: telebot.types.CallbackQuery):
    """Handle language change from settings."""
    settings_handler.handle_language_change(call)


@bot.callback_query_handler(func=lambda call: call.data == "settings_profile")
def settings_profile_callback(call: telebot.types.CallbackQuery):
    """Handle profile edit from settings."""
    settings_handler.handle_profile_edit(call)


@bot.callback_query_handler(func=lambda call: call.data == "settings_timezone")
def settings_timezone_callback(call: telebot.types.CallbackQuery):
    """Handle timezone change from settings."""
    settings_handler.handle_timezone_change(call)


@bot.callback_query_handler(func=lambda call: call.data == "settings_currency")
def settings_currency_callback(call: telebot.types.CallbackQuery):
    """Handle currency change from settings."""
    settings_handler.handle_currency_change(call)


@bot.callback_query_handler(func=lambda call: call.data == "settings_delete_account")
def settings_delete_account_callback(call: telebot.types.CallbackQuery):
    """Handle delete account from settings."""
    settings_handler.handle_delete_account(call)


@bot.callback_query_handler(func=lambda call: call.data in ["confirm_yes", "confirm_no"] and call.from_user.id in settings_handler.deleting_account)
def delete_account_confirm_callback(call: telebot.types.CallbackQuery):
    """Handle account deletion confirmation."""
    settings_handler.handle_delete_account_confirm(call, scheduler=scheduler)


# About callbacks
@bot.callback_query_handler(func=lambda call: call.data == "about_donate")
def about_donate_callback(call: telebot.types.CallbackQuery):
    """Handle donate from about page."""
    about_handler.handle_donate_callback(call)


# Donation callbacks
@bot.callback_query_handler(func=lambda call: call.data.startswith("donate_"))
def donate_callback(call: telebot.types.CallbackQuery):
    """Handle donation amount selection."""
    if call.data == "donate_back":
        bot.answer_callback_query(call.id)
        user = db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        bot.send_message(
            call.message.chat.id,
            get_translation(language, "main_menu"),
            reply_markup=create_main_keyboard(language)
        )
        return
    
    if call.data == "donate_custom":
        bot.answer_callback_query(call.id)
        user = db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        bot.send_message(
            call.message.chat.id,
            get_translation(language, "donate_custom")
        )
        about_handler.waiting_for_custom_donation.add(call.from_user.id)
        return
    
    try:
        amount = int(call.data.split("_")[1])
        about_handler.send_donation_invoice(call.message.chat.id, amount)
        bot.answer_callback_query(call.id)
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "Invalid amount")


# Custom donation command
@bot.message_handler(commands=['custom', 'donate'])
def custom_donate_command(message: telebot.types.Message):
    """Handle custom donation command."""
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    if message.text.startswith('/custom'):
        bot.reply_to(message, get_translation(language, "donate_custom"))
        about_handler.waiting_for_custom_donation.add(message.from_user.id)
    else:
        about_handler.handle_donate_callback(types.CallbackQuery(
            id=0,
            from_user=message.from_user,
            message=message,
            data="donate",
            chat_instance=0
        ))


# Pre-checkout query handler (always approve for donations)
@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    """Always approve pre-checkout queries for donations."""
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# Successful payment handler
@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message: telebot.types.Message):
    """Handle successful payment."""
    # Get user to retrieve their language preference
    try:
        user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
    except:
        # Fallback to English if user lookup fails
        language = "en"
    
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount
    
    thanks_message = get_translation(language, "donate_thanks", amount=stars)
    bot.send_message(message.chat.id, thanks_message)
    
    logger.info(f"Received donation: {stars} ⭐ from user {message.from_user.id} (language: {language})")


@bot.callback_query_handler(func=lambda call: call.data == "about_feedback")
def about_feedback_callback(call: telebot.types.CallbackQuery):
    """Handle feedback from about page."""
    about_handler.handle_feedback_callback(call)


# Currency selection callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("currency_"))
def currency_callback(call: telebot.types.CallbackQuery):
    """Handle currency selection."""
    currency_code = call.data.split("_")[1]
    db.update_user_currency(call.from_user.id, currency_code)
    
    user = db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
    language = user.language or "en"
    
    bot.answer_callback_query(call.id)
    
    # Always show currency set message
    if call.message:
        bot.edit_message_text(
            get_translation(language, "currency_set", currency=currency_code),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    
    # Determine if this is from settings or initial setup
    # If currency was selected from settings, user clicked "settings_currency" before this
    # We can detect this by checking if user is NOT in any active mode
    is_from_settings = (
        call.from_user.id not in expense_handler.active_expense_mode and 
        call.from_user.id not in income_handler.active_income_mode and
        call.from_user.id not in reminder_handler.active_reminder_mode
    )
    
    if is_from_settings:
        # From settings - just confirm and show main menu
        bot.send_message(
            call.message.chat.id if call.message else call.from_user.id,
            get_translation(language, "main_menu"),
            reply_markup=create_main_keyboard(language)
        )
    else:
        # From initial setup - enter expense mode
        expense_handler.active_expense_mode.add(call.from_user.id)
        user_states[call.from_user.id] = "expense"
        chat_id = call.message.chat.id if call.message else call.from_user.id
        bot.send_message(
            chat_id,
            get_translation(language, "expense_prompt"),
            reply_markup=create_back_keyboard(language)
        )


# Report period selection callbacks
@bot.callback_query_handler(func=lambda call: call.data.startswith("report_"))
def report_period_callback(call: telebot.types.CallbackQuery):
    """Handle report period selection."""
    from datetime import datetime, timedelta
    
    user = db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
    language = user.language or "en"
    
    bot.answer_callback_query(call.id)
    
    period = call.data.split("_")[1]  # today, week, month, custom
    from datetime import timezone as dt_timezone
    now = datetime.now(dt_timezone.utc).replace(tzinfo=None)  # Convert to naive UTC for comparison
    start_date = None
    end_date = now
    
    if period == "today":
        start_date = datetime(now.year, now.month, now.day)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = datetime(now.year, now.month, 1)
    elif period == "custom":
        # For custom, we'll ask user to input dates (simplified - can be enhanced)
        bot.edit_message_text(
            "Custom date selection coming soon. Please use Today/Week/Month for now.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.send_message(
            call.message.chat.id,
            get_translation(language, "main_menu"),
            reply_markup=create_main_keyboard(language)
        )
        return
    
    # Show processing
    processing_msg = bot.send_message(call.message.chat.id, get_translation(language, "processing"))
    
    try:
        # Generate report
        report = report_handler.generate_report(call.from_user.id, start_date=start_date, end_date=end_date, language=language)
        
        # Edit message with report
        bot.edit_message_text(
            report,
            chat_id=call.message.chat.id,
            message_id=processing_msg.message_id
        )
        
        # Auto-return to main menu
        bot.send_message(
            call.message.chat.id,
            get_translation(language, "main_menu"),
            reply_markup=create_main_keyboard(language)
        )
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        bot.edit_message_text(
            get_translation(language, "error"),
            chat_id=call.message.chat.id,
            message_id=processing_msg.message_id
        )


# Text message handlers
@bot.message_handler(content_types=['text'])
def text_message_handler(message: telebot.types.Message):
    """Handle all text messages."""
    # Allow /start command to work (can recreate account)
    if message.text and message.text.startswith('/start'):
        start_command(message)
        return
    
    # Check if user exists (if not, they were deleted - ignore message silently)
    if not db.user_exists(message.from_user.id):
        return  # User was deleted - stop responding
    
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    # Check if user clicked "back" button
    back_texts = [
        get_translation("en", "back"),
        get_translation("ru", "back"),
        get_translation("uz", "back")
    ]
    if message.text in back_texts:
        # Exit all modes
        expense_handler.active_expense_mode.discard(message.from_user.id)
        income_handler.active_income_mode.discard(message.from_user.id)
        report_handler.active_report_mode.discard(message.from_user.id)
        reminder_handler.active_reminder_mode.discard(message.from_user.id)
        user_states[message.from_user.id] = "none"
        bot.reply_to(
            message,
            get_translation(language, "main_menu"),
            reply_markup=create_main_keyboard(language)
        )
        return
    
    # Check if waiting for feedback
    if about_handler.handle_feedback_message(message):
        return
    
    # Check if waiting for name update
    if settings_handler.handle_name_update(message):
        return
    
    # Check if user clicked "skip" for timezone
    skip_texts = [
        get_translation("en", "skip"),
        get_translation("ru", "skip"),
        get_translation("uz", "skip")
    ]
    if message.text in skip_texts:
        # User skipped timezone - show main menu
        user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        bot.reply_to(
            message,
            get_translation(language, "main_menu"),
            reply_markup=create_main_keyboard(language)
        )
        return
    
    # Check if user is entering country name (check if timezone is not set and not in any mode)
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    if (not user.timezone or user.timezone == 'UTC') and user_states.get(message.from_user.id, "none") == "none":
        # Check if it's not a command or button
        enter_country_texts = [
            get_translation("en", "enter_country"),
            get_translation("ru", "enter_country"),
            get_translation("uz", "enter_country")
        ]
        if message.text in enter_country_texts:
            # User clicked "Enter Country" button - just acknowledge
            bot.reply_to(
                message,
                get_translation(language, "request_location_for_timezone")
            )
            return
        
        if message.text not in back_texts:
            # Try to detect timezone from country name (with language support via AI)
            from handlers.reminder_handler import get_timezone_from_country
            tz_name = get_timezone_from_country(message.text, language=language)
            if tz_name:
                try:
                    db.update_user_timezone(message.from_user.id, tz_name)
                    logger.info(f"Updated timezone for user {message.from_user.id} to {tz_name} from country input: {message.text}")
                    # Reschedule daily expense reminder for new timezone
                    scheduler.reschedule_user_daily_reminder(message.from_user.id, tz_name, language)
                    bot.reply_to(
                        message,
                        get_translation(language, "timezone_updated", timezone=tz_name),
                        reply_markup=create_main_keyboard(language)
                    )
                    return
                except Exception as e:
                    logger.error(f"Error updating timezone from country: {e}")
            else:
                bot.reply_to(
                    message,
                    get_translation(language, "timezone_detection_failed") + "\n" + get_translation(language, "request_location_for_timezone")
                )
                return
    
    # Check if user has pending expense or income (waiting for confirmation)
    if message.from_user.id in expense_handler.pending_expenses:
        return
    if message.from_user.id in income_handler.pending_incomes:
        return
    
    # Check if waiting for custom donation amount
    if about_handler.handle_custom_donation_input(message):
        return
    
    # Check user state and route accordingly
    state = user_states.get(message.from_user.id, "none")
    
    if state == "expense" or expense_handler.is_in_expense_mode(message.from_user.id):
        expense_handler.handle_expense_message(message)
    elif state == "income" or income_handler.is_in_income_mode(message.from_user.id):
        income_handler.handle_income_message(message)
    elif state == "reminder" or reminder_handler.is_in_reminder_mode(message.from_user.id):
        reminder_handler.handle_reminder_message(message)
    # Report mode removed - now uses buttons only


# Voice message handlers
@bot.message_handler(content_types=['voice'])
def voice_message_handler(message: telebot.types.Message):
    """Handle voice messages."""
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    # Check user state
    state = user_states.get(message.from_user.id, "none")
    
    if state == "expense" or expense_handler.is_in_expense_mode(message.from_user.id):
        expense_handler.handle_expense_voice(message)
    elif state == "income" or income_handler.is_in_income_mode(message.from_user.id):
        income_handler.handle_income_voice(message)
    elif state == "reminder" or reminder_handler.is_in_reminder_mode(message.from_user.id):
        reminder_handler.handle_reminder_voice(message)
    else:
        # Default: treat as expense
        expense_handler.handle_expense_voice(message)


# Location message handlers
@bot.message_handler(content_types=['location'])
def location_message_handler(message: telebot.types.Message):
    """Handle location messages to detect timezone."""
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    # Update timezone from location
    from handlers.reminder_handler import get_timezone_from_location
    tz_name = get_timezone_from_location(message.location.latitude, message.location.longitude)
    
    if tz_name:
        try:
            db.update_user_timezone(message.from_user.id, tz_name)
            logger.info(f"Updated timezone for user {user.telegram_id} to {tz_name} from location")
            # Reschedule daily expense reminder for new timezone
            scheduler.reschedule_user_daily_reminder(message.from_user.id, tz_name, language)
            
            # Check if user was changing timezone from settings
            if message.from_user.id in settings_handler.changing_timezone:
                settings_handler.changing_timezone.discard(message.from_user.id)
                bot.reply_to(
                    message,
                    get_translation(language, "timezone_updated", timezone=tz_name),
                    reply_markup=create_main_keyboard(language)
                )
            else:
                # First time setup - show main menu
                bot.reply_to(
                    message,
                    get_translation(language, "timezone_updated", timezone=tz_name),
                    reply_markup=create_main_keyboard(language)
                )
        except Exception as e:
            logger.error(f"Error updating timezone from location: {e}")
            bot.reply_to(message, get_translation(language, "error"))
    else:
        bot.reply_to(message, get_translation(language, "timezone_detection_failed"))


# Error handler
@bot.message_handler(func=lambda message: True)
def default_handler(message: telebot.types.Message):
    """Default handler for unhandled messages."""
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
    language = user.language or "en"
    
    bot.reply_to(
        message,
        get_translation(language, "error"),
        reply_markup=create_main_keyboard(language)
    )


# Graceful shutdown
def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info("\nShutting down bot...")
    scheduler.shutdown()
    db.close()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    logger.info("SmartExpenseBot is starting...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except KeyboardInterrupt:
        signal_handler(None, None)

