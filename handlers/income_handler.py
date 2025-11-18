"""
Income handler for SmartExpenseBot.
Handles income input via text and voice messages.
"""

import telebot
from telebot import types
import os
import logging
from database import Database
from ai_functions import deepseek_ai_income
from translations import get_translation
from keyboards import (
    create_back_keyboard,
    create_confirm_keyboard,
    create_currency_keyboard,
    create_main_keyboard,
)
from voice_transcriber import VoiceTranscriber

logger = logging.getLogger(__name__)


class IncomeHandler:
    """Handler for income-related commands."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        self.pending_incomes = {}  # {user_id: income_data}
        self.active_income_mode = set()  # {user_id} - users in income mode
        self.transcriber = VoiceTranscriber()
    
    def handle_income_command(self, message: telebot.types.Message):
        """Handle income command or button - enter income mode."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        # Check if user has currency set (first time using expense/income)
        # If user's currency is default USD and they have no expenses/incomes, ask for currency
        if not user.currency or user.currency == "USD":
            # Check if user has any expenses or incomes - if not, ask for currency
            user_expenses = self.db.get_expenses(message.from_user.id, limit=1)
            user_incomes = self.db.get_incomes(message.from_user.id, limit=1)
            if len(user_expenses) == 0 and len(user_incomes) == 0:
                # First time using income function - ask for currency selection
                self.bot.reply_to(
                    message,
                    get_translation(language, "select_currency"),
                    reply_markup=create_currency_keyboard(language)
                )
                return
        
        self.active_income_mode.add(message.from_user.id)
        self.bot.reply_to(
            message,
            get_translation(language, "income_prompt"),
            reply_markup=create_back_keyboard(language)
        )
    
    def is_in_income_mode(self, user_id: int) -> bool:
        """Check if user is in income mode."""
        return user_id in self.active_income_mode
    
    def handle_income_message(self, message: telebot.types.Message):
        """Handle text message for income input."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        default_currency = user.currency or "USD"
        
        try:
            # Extract income using AI
            income_data = deepseek_ai_income(message.text, language, default_currency)
            
            if not income_data or income_data.get("amount", 0) <= 0:
                self.bot.reply_to(
                    message,
                    get_translation(language, "error") + "\n" + get_translation(language, "income_prompt")
                )
                return
            
            # Store pending income
            self.pending_incomes[message.from_user.id] = income_data
            
            # Get income type translation
            income_type_key = f"income_type_{income_data['income_type']}"
            income_type_text = get_translation(language, income_type_key)
            
            # Show confirmation
            confirm_text = get_translation(
                language,
                "income_confirm",
                amount=income_data["amount"],
                currency=income_data["currency"],
                income_type=income_type_text,
                description=income_data.get("description", "")
            )
            
            self.bot.reply_to(
                message,
                confirm_text,
                reply_markup=create_confirm_keyboard(language)
            )
        except Exception as e:
            logger.error(f"Error processing income message: {e}", exc_info=True)
            self.bot.reply_to(message, get_translation(language, "error"))
    
    def handle_income_voice(self, message: telebot.types.Message):
        """Handle voice message for income input."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        default_currency = user.currency or "USD"
        
        # Download voice file
        file_info = self.bot.get_file(message.voice.file_id)
        downloaded_file = self.bot.download_file(file_info.file_path)
        
        # Save temporarily
        temp_path = f"temp_voice_{message.from_user.id}_{message.message_id}.ogg"
        with open(temp_path, 'wb') as f:
            f.write(downloaded_file)
        
        # Show processing message
        processing_msg = self.bot.reply_to(message, get_translation(language, "processing"))
        
        try:
            # Transcribe voice
            transcribed_text = self.transcriber.transcribe(temp_path, language)
            
            if not transcribed_text or "not available" in transcribed_text.lower():
                self.bot.edit_message_text(
                    transcribed_text or get_translation(language, "error"),
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Extract income using AI
            income_data = deepseek_ai_income(transcribed_text, language, default_currency)
            
            if not income_data or income_data.get("amount", 0) <= 0:
                self.bot.edit_message_text(
                    get_translation(language, "error"),
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Store pending income
            self.pending_incomes[message.from_user.id] = income_data
            
            # Get income type translation
            income_type_key = f"income_type_{income_data['income_type']}"
            income_type_text = get_translation(language, income_type_key)
            
            # Show confirmation
            confirm_text = get_translation(
                language,
                "income_confirm",
                amount=income_data["amount"],
                currency=income_data["currency"],
                income_type=income_type_text,
                description=income_data.get("description", "")
            )
            
            self.bot.edit_message_text(
                confirm_text,
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                reply_markup=create_confirm_keyboard(language)
            )
        except Exception as e:
            logger.error(f"Error processing income voice: {e}", exc_info=True)
            self.bot.edit_message_text(
                get_translation(language, "error"),
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    def handle_income_confirm(self, call: telebot.types.CallbackQuery):
        """Handle income confirmation callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.bot.answer_callback_query(call.id)
        
        if call.data == "confirm_yes":
            income_data = self.pending_incomes.get(call.from_user.id)
            if income_data:
                try:
                    # Save income to database - currency will be taken from user's currency in User table
                    self.db.add_income(
                        call.from_user.id,
                        income_data["amount"],
                        user.currency or "USD",  # Use user's currency from User table, not from income_data
                        income_data.get("description", ""),
                        income_data.get("income_type", "monthly")
                    )
                    
                    # Remove from pending
                    del self.pending_incomes[call.from_user.id]
                    self.active_income_mode.discard(call.from_user.id)
                    
                    self.bot.edit_message_text(
                        get_translation(language, "income_confirmed"),
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id
                    )
                    self.bot.send_message(
                        call.message.chat.id,
                        get_translation(language, "main_menu"),
                        reply_markup=create_main_keyboard(language)
                    )
                except Exception as e:
                    logger.error(f"Error saving income: {e}", exc_info=True)
                    self.bot.send_message(
                        call.message.chat.id,
                        get_translation(language, "error")
                    )
        else:
            # User cancelled
            if call.from_user.id in self.pending_incomes:
                del self.pending_incomes[call.from_user.id]
            self.active_income_mode.discard(call.from_user.id)
            self.bot.edit_message_text(
                get_translation(language, "account_delete_cancelled"),  # Reusing this key for cancel
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            self.bot.send_message(
                call.message.chat.id,
                get_translation(language, "main_menu"),
                reply_markup=create_main_keyboard(language)
            )

