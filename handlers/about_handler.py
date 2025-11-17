"""
About handler for SmartExpenseBot.
Handles about page, donations, and feedback.
"""

import telebot
from telebot import types
from database import Database
from translations import get_translation
from keyboards import create_main_keyboard, create_about_keyboard, create_donate_keyboard, create_back_keyboard
from config import Config


class AboutHandler:
    """Handler for about-related commands."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        self.waiting_for_feedback = set()  # Set of user IDs waiting for feedback
        self.waiting_for_custom_donation = set()  # Set of user IDs waiting for custom donation amount
    
    def handle_about_command(self, message: telebot.types.Message):
        """Handle /about command or button."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        about_text = get_translation(language, "about_text")
        
        self.bot.reply_to(
            message,
            about_text,
            reply_markup=create_about_keyboard()
        )
    
    def handle_donate_callback(self, call: telebot.types.CallbackQuery):
        """Handle donate callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            call.message.chat.id,
            get_translation(language, "donate_message"),
            parse_mode='Markdown',
            reply_markup=create_donate_keyboard(language)
        )
    
    def send_donation_invoice(self, chat_id: int, stars_amount: int):
        """Send Telegram Stars donation invoice."""
        prices = [types.LabeledPrice(label=f"Donation ⭐ {stars_amount} Stars", amount=stars_amount)]
        
        self.bot.send_invoice(
            chat_id=chat_id,
            title="Bot Donation ❤️",
            description=f"Thank you for donating {stars_amount} Telegram Stars!\nThis supports future development.",
            invoice_payload=f"donation_{stars_amount}_{chat_id}",
            provider_token="",  # EMPTY for Telegram Stars
            currency="XTR",    # THIS is the key for Stars
            prices=prices,
            start_parameter="donation",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
    
    def handle_custom_donation_input(self, message: telebot.types.Message):
        """Handle custom donation amount input."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        if message.from_user.id not in self.waiting_for_custom_donation:
            return False
        
        try:
            amount = int(message.text.strip())
            if amount < 1:
                raise ValueError
            self.waiting_for_custom_donation.discard(message.from_user.id)
            self.send_donation_invoice(message.chat.id, amount)
            return True
        except (ValueError, TypeError):
            self.bot.reply_to(message, get_translation(language, "donate_invalid"))
            return True  # Handled
    
    def handle_feedback_callback(self, call: telebot.types.CallbackQuery):
        """Handle feedback callback."""
        user = self.db.get_or_create_user(call.from_user.id, call.from_user.first_name or "User")
        language = user.language or "en"
        
        self.waiting_for_feedback.add(call.from_user.id)
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            call.message.chat.id,
            get_translation(language, "feedback_prompt"),
            reply_markup=create_main_keyboard(language)
        )
    
    def handle_feedback_message(self, message: telebot.types.Message):
        """Handle feedback text message."""
        if message.from_user.id not in self.waiting_for_feedback:
            return False
        
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        feedback_text = message.text.strip()
        
        if feedback_text and Config.DEVELOPER_ID:
            # Forward feedback to developer
            try:
                self.bot.send_message(
                    Config.DEVELOPER_ID,
                    f"📩 Feedback from @{message.from_user.username or message.from_user.first_name} ({message.from_user.id}):\n\n{feedback_text}"
                )
            except Exception as e:
                print(f"Error forwarding feedback: {e}")
        
        # Remove from waiting set
        self.waiting_for_feedback.discard(message.from_user.id)
        
        self.bot.reply_to(
            message,
            get_translation(language, "feedback_sent"),
            reply_markup=create_main_keyboard(language)
        )
        return True

