"""
Expense handler for SmartExpenseBot.
Handles expense input via text and voice messages.
"""

import telebot
from telebot import types
import os
import subprocess
import logging
from database import Database
from ai_functions import deepseek_ai_expense, deepseek_ai_expense_multiple
from translations import get_translation
from keyboards import create_back_keyboard, create_confirm_keyboard, create_currency_keyboard, create_main_keyboard
from voice_transcriber import VoiceTranscriber

logger = logging.getLogger(__name__)


class ExpenseHandler:
    """Handler for expense-related commands."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        self.pending_expenses = {}  # {user_id: list of expense_data} - can be multiple expenses
        self.active_expense_mode = set()  # {user_id} - users in expense mode
        self.transcriber = VoiceTranscriber()
    
    def handle_expense_command(self, message: telebot.types.Message):
        """Handle /expenses command or button - enter expense mode."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        # Check if user has currency set (first time using expense/income)
        # If user's currency is default USD and they have no expenses/incomes, ask for currency
        if not user.currency or user.currency == "USD":
            # Check if user has any expenses or incomes - if not, ask for currency
            user_expenses = self.db.get_expenses(message.from_user.id, limit=1)
            user_incomes = self.db.get_incomes(message.from_user.id, limit=1)
            if len(user_expenses) == 0 and len(user_incomes) == 0:
                # First time using expense function - ask for currency selection
                self.bot.reply_to(
                    message,
                    get_translation(language, "select_currency"),
                    reply_markup=create_currency_keyboard(language)
                )
                return
        
        # Enter expense mode
        self.active_expense_mode.add(message.from_user.id)
        
        self.bot.reply_to(
            message,
            get_translation(language, "expense_prompt"),
            reply_markup=create_back_keyboard(language)
        )
    
    def is_in_expense_mode(self, user_id: int) -> bool:
        """Check if user is in expense mode."""
        return user_id in self.active_expense_mode
    
    def handle_expense_message(self, message: telebot.types.Message):
        """Handle expense text message - supports multiple expenses."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        default_currency = user.currency or "USD"
        
        text = message.text.strip()
        
        # Show processing message
        processing_msg = self.bot.reply_to(message, get_translation(language, "processing"))
        
        try:
            # Extract multiple expenses using AI
            expenses = deepseek_ai_expense_multiple(text, language, default_currency)
            
            if not expenses or len(expenses) == 0:
                self.bot.edit_message_text(
                    get_translation(language, "error"),
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Store pending expenses (list)
            self.pending_expenses[message.from_user.id] = expenses
            
            # Build confirmation message for all expenses
            if len(expenses) == 1:
                # Single expense
                exp = expenses[0]
                confirm_text = get_translation(
                    language,
                    "expense_confirm",
                    amount=exp["amount"],
                    currency=exp["currency"],
                    description=exp["description"],
                    category=exp["category"]
                )
            else:
                # Multiple expenses
                confirm_text = get_translation(language, "multiple_expenses_found", count=len(expenses)) + "\n\n"
                for i, exp in enumerate(expenses, 1):
                    confirm_text += f"{i}. {exp['amount']} {exp['currency']} - {exp['description']} ({exp['category']})\n"
                confirm_text += f"\n{get_translation(language, 'yes')} {get_translation(language, 'save_all')}, {get_translation(language, 'no')} to cancel"
            
            # Edit message with confirmation
            self.bot.edit_message_text(
                confirm_text,
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                reply_markup=create_confirm_keyboard(language)
            )
        except Exception as e:
            logger.error(f"Error processing expense message: {e}")
            self.bot.edit_message_text(
                get_translation(language, "error"),
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
    
    def handle_expense_voice(self, message: telebot.types.Message):
        """Handle expense voice message - supports multiple expenses."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        default_currency = user.currency or "USD"
        
        # Download voice file
        file_info = self.bot.get_file(message.voice.file_id)
        downloaded_file = self.bot.download_file(file_info.file_path)
        
        # Save to temporary file
        temp_path = f"/tmp/voice_{message.from_user.id}.ogg"
        with open(temp_path, "wb") as f:
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
            
            # Extract multiple expenses using AI
            expenses = deepseek_ai_expense_multiple(transcribed_text, language, default_currency)
            
            if not expenses or len(expenses) == 0:
                self.bot.edit_message_text(
                    get_translation(language, "error"),
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Store pending expenses (list)
            self.pending_expenses[message.from_user.id] = expenses
            
            # Build confirmation message for all expenses
            if len(expenses) == 1:
                # Single expense
                exp = expenses[0]
                confirm_text = get_translation(
                    language,
                    "expense_confirm",
                    amount=exp["amount"],
                    currency=exp["currency"],
                    description=exp["description"],
                    category=exp["category"]
                )
            else:
                # Multiple expenses
                confirm_text = get_translation(language, "multiple_expenses_found", count=len(expenses)) + "\n\n"
                for i, exp in enumerate(expenses, 1):
                    confirm_text += f"{i}. {exp['amount']} {exp['currency']} - {exp['description']} ({exp['category']})\n"
                confirm_text += f"\n{get_translation(language, 'yes')} {get_translation(language, 'save_all')}, {get_translation(language, 'no')} to cancel"
            
            # Edit message with confirmation
            self.bot.edit_message_text(
                confirm_text,
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                reply_markup=create_confirm_keyboard(language)
            )
        
        except Exception as e:
            logger.error(f"Error processing expense voice: {e}")
            self.bot.edit_message_text(
                get_translation(language, "error"),
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def handle_expense_confirmation(self, call: telebot.types.CallbackQuery, confirmed: bool):
        """Handle expense confirmation (yes/no) - supports multiple expenses."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        if call.from_user.id not in self.pending_expenses:
            self.bot.answer_callback_query(call.id, get_translation(language, "error"))
            return
        
        self.bot.answer_callback_query(call.id)
        
        if confirmed:
            expenses_list = self.pending_expenses[call.from_user.id]
            
            # Ensure it's a list
            if not isinstance(expenses_list, list):
                expenses_list = [expenses_list]
            
            # Save all expenses to database
            saved_count = 0
            for expense_data in expenses_list:
                try:
                    self.db.add_expense(
                        call.from_user.id,
                        expense_data["amount"],
                        expense_data["category"],
                        expense_data["description"]
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving expense: {e}")
            
            # Send confirmation
            if saved_count == 1:
                response = get_translation(language, "expense_confirmed")
            else:
                response = f"{saved_count} {get_translation(language, 'expense_confirmed')}"
            
            self.bot.edit_message_text(
                response,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            
            # Remove pending expenses and exit expense mode
            del self.pending_expenses[call.from_user.id]
            self.active_expense_mode.discard(call.from_user.id)
            
            # Auto-return to main menu
            from keyboards import create_main_keyboard
            self.bot.send_message(
                call.message.chat.id,
                get_translation(language, "main_menu"),
                reply_markup=create_main_keyboard(language)
            )
        else:
            # User rejected
            del self.pending_expenses[call.from_user.id]
            self.bot.edit_message_text(
                get_translation(language, "expense_prompt"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )

