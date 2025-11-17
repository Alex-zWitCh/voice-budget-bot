"""
Settings handler for SmartExpenseBot.
Handles user settings and profile management.
"""

import telebot
from telebot import types
from database import Database
from translations import get_translation, get_language_name
from keyboards import create_main_keyboard, create_language_keyboard, create_currency_keyboard, create_confirm_keyboard


class SettingsHandler:
    """Handler for settings-related commands."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        self.editing_name = set()  # Set of user IDs editing their name
        self.changing_timezone = set()  # Set of user IDs changing timezone
        self.deleting_account = set()  # Set of user IDs confirming account deletion
    
    def handle_settings_command(self, message: telebot.types.Message):
        """Handle /settings command or button."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(
                get_translation(language, "change_language"),
                callback_data="settings_lang"
            ),
            types.InlineKeyboardButton(
                get_translation(language, "edit_profile"),
                callback_data="settings_profile"
            ),
            types.InlineKeyboardButton(
                get_translation(language, "change_timezone"),
                callback_data="settings_timezone"
            ),
            types.InlineKeyboardButton(
                get_translation(language, "change_currency"),
                callback_data="settings_currency"
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                get_translation(language, "delete_account"),
                callback_data="settings_delete_account"
            )
        )
        
        # Get timezone display name
        timezone_display = user.timezone or "UTC"
        currency_display = user.currency or "USD"
        user_info = get_translation(
            language,
            "user_info",
            name=user.name,
            lang_name=get_language_name(user.language or "en"),
            timezone=timezone_display
        )
        user_info += f"\n{get_translation(language, 'currency_set', currency=currency_display)}"
        
        self.bot.reply_to(
            message,
            f"{get_translation(language, 'settings_menu')}\n\n{user_info}",
            reply_markup=keyboard
        )
    
    def handle_language_change(self, call: telebot.types.CallbackQuery):
        """Handle language change callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        current_language = user.language or "en"
        
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            call.message.chat.id,
            get_translation(current_language, "change_language"),
            reply_markup=create_language_keyboard()
        )
    
    def handle_profile_edit(self, call: telebot.types.CallbackQuery):
        """Handle profile edit callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.editing_name.add(call.from_user.id)
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            call.message.chat.id,
            "Send your new name:",
            reply_markup=create_main_keyboard(language)
        )
    
    def handle_timezone_change(self, call: telebot.types.CallbackQuery):
        """Handle timezone change callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.changing_timezone.add(call.from_user.id)
        self.bot.answer_callback_query(call.id)
        
        # Request location
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(types.KeyboardButton(get_translation(language, "share_location"), request_location=True))
        keyboard.add(types.KeyboardButton(get_translation(language, "back")))
        
        self.bot.send_message(
            call.message.chat.id,
            get_translation(language, "request_location_for_timezone"),
            reply_markup=keyboard
        )
    
    def handle_name_update(self, message: telebot.types.Message):
        """Handle name update message."""
        if message.from_user.id not in self.editing_name:
            return False
        
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        new_name = message.text.strip()
        if new_name:
            self.db.update_user_name(message.from_user.id, new_name)
            self.editing_name.discard(message.from_user.id)
            self.bot.reply_to(
                message,
                f"Name updated to: {new_name}",
                reply_markup=create_main_keyboard(language)
            )
            return True
        
        return False
    
    def handle_currency_change(self, call: telebot.types.CallbackQuery):
        """Handle currency change callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            call.message.chat.id,
            get_translation(language, "select_currency"),
            reply_markup=create_currency_keyboard(language)
        )
    
    def handle_delete_account(self, call: telebot.types.CallbackQuery):
        """Handle delete account callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.deleting_account.add(call.from_user.id)
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            call.message.chat.id,
            get_translation(language, "delete_account_confirm"),
            reply_markup=create_confirm_keyboard(language)
        )
    
    def handle_delete_account_confirm(self, call: telebot.types.CallbackQuery, scheduler=None):
        """Handle account deletion confirmation."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.bot.answer_callback_query(call.id)
        
        if call.data == "confirm_yes":
            try:
                # Cancel all scheduled reminders for this user before deletion
                if scheduler:
                    scheduler.cancel_user_reminders(call.from_user.id)
                
                # Delete user and all related data (cascade delete handles cleanup)
                success = self.db.delete_user(call.from_user.id)
                self.deleting_account.discard(call.from_user.id)
                
                if success:
                    # Send final message
                    self.bot.send_message(
                        call.message.chat.id,
                        get_translation(language, "account_deleted")
                    )
                    # Bot will now stop responding to this user's messages
                    # They need to use /start again to create a new account
                else:
                    self.bot.send_message(
                        call.message.chat.id,
                        get_translation(language, "error")
                    )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error deleting user account: {e}", exc_info=True)
                self.bot.send_message(
                    call.message.chat.id,
                    get_translation(language, "error")
                )
        else:
            self.deleting_account.discard(call.from_user.id)
            self.bot.send_message(
                call.message.chat.id,
                get_translation(language, "account_delete_cancelled"),
                reply_markup=create_main_keyboard(language)
            )

