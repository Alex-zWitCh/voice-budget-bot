"""
Keyboard creation utilities for SmartExpenseBot.
"""

import telebot
from telebot import types
from translations import get_translation


def create_main_keyboard(language: str) -> types.ReplyKeyboardMarkup:
    """Create main menu keyboard."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    keyboard.add(
        types.KeyboardButton(get_translation(language, "expenses")),
        types.KeyboardButton(get_translation(language, "income"))
    )
    keyboard.add(
        types.KeyboardButton(get_translation(language, "reports")),
        types.KeyboardButton(get_translation(language, "reminders"))
    )
    keyboard.add(
        types.KeyboardButton(get_translation(language, "settings")),
        types.KeyboardButton(get_translation(language, "about"))
    )
    
    return keyboard


def create_language_keyboard() -> types.InlineKeyboardMarkup:
    """Create language selection keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("🇺🇿 O'zbek tili", callback_data="lang_uz"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    return keyboard


def create_confirm_keyboard(language: str) -> types.InlineKeyboardMarkup:
    """Create confirmation keyboard with Yes/No buttons."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_translation(language, "yes"), callback_data="confirm_yes"),
        types.InlineKeyboardButton(get_translation(language, "no"), callback_data="confirm_no")
    )
    return keyboard


def create_back_keyboard(language: str) -> types.ReplyKeyboardMarkup:
    """Create keyboard with back button."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(
        types.KeyboardButton(get_translation(language, "back"))
    )
    return keyboard


def create_donate_keyboard(language: str) -> types.InlineKeyboardMarkup:
    """Create donation keyboard with all donation options."""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Telegram Stars - preset amounts
    keyboard.add(
        types.InlineKeyboardButton("⭐ Telegram Stars (10)", callback_data="donate_10"),
        types.InlineKeyboardButton("⭐ Telegram Stars (50)", callback_data="donate_50"),
        types.InlineKeyboardButton("⭐ Telegram Stars (100)", callback_data="donate_100"),
    )
    
    # Custom amount for Telegram Stars
    keyboard.add(
        types.InlineKeyboardButton(get_translation(language, "donate_custom_stars"), callback_data="donate_custom")
    )
    
    # Other donation platforms (URL buttons)
    keyboard.add(
        types.InlineKeyboardButton("🇺🇿 Tirikchilik.uz", url="https://tirikchilik.uz/botir"),
        types.InlineKeyboardButton("💎 Patreon", url="https://www.patreon.com/15097645/join"),
        types.InlineKeyboardButton("🐙 GitHub Sponsors", url="https://github.com/sponsors/botirbakhtiyarov")
    )
    
    keyboard.add(
        types.InlineKeyboardButton(get_translation(language, "back"), callback_data="donate_back")
    )
    return keyboard


def create_about_keyboard() -> types.InlineKeyboardMarkup:
    """Create about page keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("💰 Donate", callback_data="about_donate"),
        types.InlineKeyboardButton("💬 Feedback", callback_data="about_feedback")
    )
    return keyboard


def create_currency_keyboard(language: str) -> types.InlineKeyboardMarkup:
    """Create currency selection keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💵 USD", callback_data="currency_USD"),
        types.InlineKeyboardButton("💶 EUR", callback_data="currency_EUR"),
        types.InlineKeyboardButton("💴 CNY", callback_data="currency_CNY"),
        types.InlineKeyboardButton("💷 GBP", callback_data="currency_GBP"),
        types.InlineKeyboardButton("₽ RUB", callback_data="currency_RUB"),
        types.InlineKeyboardButton("₸ UZS", callback_data="currency_UZS")
    )
    return keyboard


def create_report_keyboard(language: str) -> types.InlineKeyboardMarkup:
    """Create report period selection keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_translation(language, "report_today"), callback_data="report_today"),
        types.InlineKeyboardButton(get_translation(language, "report_week"), callback_data="report_week"),
        types.InlineKeyboardButton(get_translation(language, "report_month"), callback_data="report_month"),
        types.InlineKeyboardButton(get_translation(language, "report_custom"), callback_data="report_custom")
    )
    return keyboard

