"""
Report handler for SmartExpenseBot.
Handles expense report generation using AI.
"""

import telebot
import logging
import re
from datetime import datetime, timedelta
from database import Database
from ai_functions import deepseek_ai_report
from translations import get_translation
from keyboards import create_back_keyboard, create_report_keyboard, create_main_keyboard

logger = logging.getLogger(__name__)


class ReportHandler:
    """Handler for report-related commands."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        self.active_report_mode = set()  # {user_id} - users in report mode
    
    def handle_report_command(self, message: telebot.types.Message):
        """Handle /reports command or button - show report period buttons."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        # Show report period selection buttons
        self.bot.reply_to(
            message,
            get_translation(language, "report_prompt"),
            reply_markup=create_report_keyboard(language)
        )
    
    def is_in_report_mode(self, user_id: int) -> bool:
        """Check if user is in report mode."""
        return user_id in self.active_report_mode
    
    def handle_report_message(self, message: telebot.types.Message):
        """Handle report query message (legacy - now uses buttons)."""
        # This is kept for backward compatibility but should not be called
        pass
    
    def generate_report(self, user_id: int, start_date=None, end_date=None, language: str = "en"):
        """Generate and return report for given date range."""
        try:
            # Get user's expenses and incomes from database with date filters
            expenses = self.db.get_expenses(user_id, start_date=start_date, end_date=end_date, limit=1000)
            incomes = self.db.get_incomes(user_id, start_date=start_date, end_date=end_date, limit=1000)
            
            # Calculate totals
            total_expenses = sum(e.amount for e in expenses) if expenses else 0
            total_income = sum(i.amount for i in incomes) if incomes else 0
            balance = total_income - total_expenses
            
            # Prepare context for AI report
            all_data = list(expenses) + list(incomes) if expenses or incomes else []
            
            if not all_data:
                no_data_msg = {
                    "uz": "Bu davr uchun ma'lumotlar topilmadi.",
                    "ru": "Данные за этот период не найдены.",
                    "en": "No data found for this period."
                }
                return no_data_msg.get(language, "No data found for this period.")
            
            # Create enhanced report query with income/expense summary
            user = self.db.get_or_create_user(user_id, "User")
            currency = user.currency or "USD"
            
            # Generate report using AI (DeepSeek_AI_data) - query in user's language
            date_from = start_date.strftime('%Y-%m-%d') if start_date else get_translation(language, "beginning")
            date_to = end_date.strftime('%Y-%m-%d') if end_date else get_translation(language, "now")
            
            # Create query in user's language
            report_queries = {
                "uz": f"{date_from} dan {date_to} gacha bo'lgan moliyaviy hisobotni ko'rsating. Daromad va xarajatlarni kiritib, balansni ko'rsating.",
                "ru": f"Покажите финансовый отчет с {date_from} по {date_to}. Включите доходы и расходы, покажите баланс.",
                "en": f"Show financial report from {date_from} to {date_to}. Include both income and expenses, show balance."
            }
            report_query = report_queries.get(language, report_queries["en"])
            
            # Pass user's currency to report function
            report = deepseek_ai_report(report_query, language, all_data, user_currency=currency)
            
            # Create summary in user's language
            summary = ""
            if total_income > 0 or total_expenses > 0:
                summary_texts = {
                    "uz": {
                        "title": "\n\nBu davr uchun xulosa:",
                        "income": "Jami daromad",
                        "expenses": "Jami xarajatlar",
                        "balance": "Balans"
                    },
                    "ru": {
                        "title": "\n\nИтоги за этот период:",
                        "income": "Общий доход",
                        "expenses": "Общие расходы",
                        "balance": "Баланс"
                    },
                    "en": {
                        "title": "\n\nSummary for this period:",
                        "income": "Total Income",
                        "expenses": "Total Expenses",
                        "balance": "Balance"
                    }
                }
                summary_dict = summary_texts.get(language, summary_texts["en"])
                summary = summary_dict["title"] + "\n"
                if total_income > 0:
                    summary += f"{summary_dict['income']}: {total_income:.2f} {currency}\n"
                if total_expenses > 0:
                    summary += f"{summary_dict['expenses']}: {total_expenses:.2f} {currency}\n"
                if balance != 0:
                    summary += f"{summary_dict['balance']}: {balance:.2f} {currency}\n"
            
            # Sanitize report and add summary
            final_report = self._sanitize_report_text(report) + summary
            
            return final_report
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            return get_translation(language, "error")

    @staticmethod
    def _sanitize_report_text(text: str) -> str:
        """Strip all Markdown formatting so Telegram renders plain text."""
        if not text:
            return ""
        
        cleaned = text
        
        # Remove markdown headers (# ## ### #### ##### ######)
        cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
        
        # Remove bold markers (**text** or __text__)
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
        
        # Remove italic markers (*text* or _text_)
        cleaned = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)", r"\1", cleaned)
        cleaned = re.sub(r"(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)", r"\1", cleaned)
        
        # Remove inline code markers (`code`)
        cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
        
        # Remove code blocks (```code```)
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
        
        # Remove remaining markdown characters
        cleaned = cleaned.replace("**", "").replace("__", "").replace("~~", "")
        
        # Replace markdown bullets with dash
        cleaned = re.sub(r"^\s*[-*+]\s+", "- ", cleaned, flags=re.MULTILINE)
        
        # Remove excessive blank lines (more than 2 consecutive)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        
        # Clean up any remaining markdown artifacts
        cleaned = cleaned.strip()
        
        return cleaned

