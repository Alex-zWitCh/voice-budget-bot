"""
Reminder handler for SmartExpenseBot.
Handles reminder creation and scheduling.
"""

import telebot
import os
import subprocess
import re
import logging
from datetime import datetime, timedelta, timezone
import pytz
from database import Database
from ai_functions import deepseek_ai_reminder
from translations import get_translation
from keyboards import create_back_keyboard
from voice_transcriber import VoiceTranscriber
from timezonefinderL import TimezoneFinder

logger = logging.getLogger(__name__)


def format_reminder_time(dt: datetime, language: str = "en") -> str:
    """
    Format reminder datetime with localized month names.
    Format: "14-November 16:06" or "14-ноябрь 16:06" or "14-noyabr 16:06"
    """
    month_names = {
        "uz": {
            1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun",
            7: "iyul", 8: "avgust", 9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
        },
        "ru": {
            1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь",
            7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
        },
        "en": {
            1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
            7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
        }
    }
    
    lang = language if language in month_names else "en"
    months = month_names.get(lang, month_names["en"])
    
    day = dt.day
    month = months.get(dt.month, str(dt.month))
    hour = dt.hour
    minute = dt.minute
    
    return f"{day}-{month} {hour:02d}:{minute:02d}"


def get_timezone_from_location(latitude, longitude):
    """
    Get timezone from latitude and longitude coordinates.
    Tries timezonefinderL first (local, fast), then falls back to API.
    Returns timezone name string or None.
    """
    # First, try timezonefinderL (local library, no network call, faster)
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=latitude, lng=longitude)
        if tz_name:
            logger.info(f"Detected timezone {tz_name} from coordinates ({latitude}, {longitude}) using timezonefinderL")
            return tz_name
    except ImportError:
        logger.debug("timezonefinderL not available, trying API")
    except Exception as e:
        logger.debug(f"Error using timezonefinderL: {e}, trying API")

    
    return None


def get_timezone_from_country(country_name: str, language: str = "en") -> str:
    """
    Get timezone from country name.
    Tries direct mapping first, then AI detection as fallback.
    Returns timezone name string or None.
    
    Args:
        country_name: Country name in any language
        language: User's language preference (uz, ru, en) for AI fallback
    """
    # Common country to timezone mappings (English names first)
    country_timezone_map = {
        # Major countries
        "usa": "America/New_York", "united states": "America/New_York", "us": "America/New_York",
        "uk": "Europe/London", "united kingdom": "Europe/London", "britain": "Europe/London",
        "china": "Asia/Shanghai", "chinese": "Asia/Shanghai",
        "japan": "Asia/Tokyo", "japanese": "Asia/Tokyo",
        "india": "Asia/Kolkata", "indian": "Asia/Kolkata",
        "russia": "Europe/Moscow", "russian": "Europe/Moscow",
        "germany": "Europe/Berlin", "german": "Europe/Berlin",
        "france": "Europe/Paris", "french": "Europe/Paris",
        "spain": "Europe/Madrid", "spanish": "Europe/Madrid",
        "italy": "Europe/Rome", "italian": "Europe/Rome",
        "brazil": "America/Sao_Paulo", "brazilian": "America/Sao_Paulo",
        "canada": "America/Toronto", "canadian": "America/Toronto",
        "australia": "Australia/Sydney", "australian": "Australia/Sydney",
        "south korea": "Asia/Seoul", "korea": "Asia/Seoul", "korean": "Asia/Seoul",
        "singapore": "Asia/Singapore", "singaporean": "Asia/Singapore",
        "thailand": "Asia/Bangkok", "thai": "Asia/Bangkok",
        "indonesia": "Asia/Jakarta", "indonesian": "Asia/Jakarta",
        "philippines": "Asia/Manila", "filipino": "Asia/Manila",
        "vietnam": "Asia/Ho_Chi_Minh", "vietnamese": "Asia/Ho_Chi_Minh",
        "malaysia": "Asia/Kuala_Lumpur", "malaysian": "Asia/Kuala_Lumpur",
        "turkey": "Europe/Istanbul", "turkish": "Europe/Istanbul",
        "egypt": "Africa/Cairo", "egyptian": "Africa/Cairo",
        "south africa": "Africa/Johannesburg", "south african": "Africa/Johannesburg",
        "mexico": "America/Mexico_City", "mexican": "America/Mexico_City",
        "argentina": "America/Argentina/Buenos_Aires", "argentinian": "America/Argentina/Buenos_Aires",
        "chile": "America/Santiago", "chilean": "America/Santiago",
        "uzbekistan": "Asia/Tashkent", "uzbek": "Asia/Tashkent", "uzbekistani": "Asia/Tashkent",
        "kazakhstan": "Asia/Almaty", "kazakh": "Asia/Almaty",
        "kyrgyzstan": "Asia/Bishkek", "kyrgyz": "Asia/Bishkek",
        "tajikistan": "Asia/Dushanbe", "tajik": "Asia/Dushanbe",
        "turkmenistan": "Asia/Ashgabat", "turkmen": "Asia/Ashgabat",
        "afghanistan": "Asia/Kabul", "afghan": "Asia/Kabul",
        "pakistan": "Asia/Karachi", "pakistani": "Asia/Karachi",
        "bangladesh": "Asia/Dhaka", "bangladeshi": "Asia/Dhaka",
        "iran": "Asia/Tehran", "iranian": "Asia/Tehran",
        "iraq": "Asia/Baghdad", "iraqi": "Asia/Baghdad",
        "saudi arabia": "Asia/Riyadh", "saudi": "Asia/Riyadh",
        "uae": "Asia/Dubai", "united arab emirates": "Asia/Dubai",
        "israel": "Asia/Jerusalem", "israeli": "Asia/Jerusalem",
        "ukraine": "Europe/Kiev", "ukrainian": "Europe/Kiev",
        "poland": "Europe/Warsaw", "polish": "Europe/Warsaw",
        "netherlands": "Europe/Amsterdam", "dutch": "Europe/Amsterdam",
        "belgium": "Europe/Brussels", "belgian": "Europe/Brussels",
        "switzerland": "Europe/Zurich", "swiss": "Europe/Zurich",
        "austria": "Europe/Vienna", "austrian": "Europe/Vienna",
        "sweden": "Europe/Stockholm", "swedish": "Europe/Stockholm",
        "norway": "Europe/Oslo", "norwegian": "Europe/Oslo",
        "denmark": "Europe/Copenhagen", "danish": "Europe/Copenhagen",
        "finland": "Europe/Helsinki", "finnish": "Europe/Helsinki",
        "greece": "Europe/Athens", "greek": "Europe/Athens",
        "portugal": "Europe/Lisbon", "portuguese": "Europe/Lisbon",
        "new zealand": "Pacific/Auckland",
    }
    
    # Normalize country name
    country_normalized = country_name.lower().strip()
    
    # Try direct match
    if country_normalized in country_timezone_map:
        tz_name = country_timezone_map[country_normalized]
        logger.info(f"Detected timezone {tz_name} from country name: {country_name}")
        return tz_name
    
    # Try partial match
    for country_key, tz_name in country_timezone_map.items():
        if country_key in country_normalized or country_normalized in country_key:
            logger.info(f"Detected timezone {tz_name} from country name (partial match): {country_name}")
            return tz_name
    
    # Try API lookup as fallback (before AI)
    try:
        import requests
        url = f"https://restcountries.com/v3.1/name/{country_name}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # Get capital city and try to get timezone
                capital = data[0].get('capital', [])
                if capital:
                    # Use a simple mapping for capital cities
                    capital_tz_map = {
                        "washington": "America/New_York",
                        "london": "Europe/London",
                        "beijing": "Asia/Shanghai",
                        "tokyo": "Asia/Tokyo",
                        "new delhi": "Asia/Kolkata",
                        "moscow": "Europe/Moscow",
                        "berlin": "Europe/Berlin",
                        "paris": "Europe/Paris",
                        "madrid": "Europe/Madrid",
                        "rome": "Europe/Rome",
                        "tashkent": "Asia/Tashkent",
                    }
                    capital_lower = capital[0].lower()
                    if capital_lower in capital_tz_map:
                        tz_name = capital_tz_map[capital_lower]
                        logger.info(f"Detected timezone {tz_name} from country capital: {capital[0]}")
                        return tz_name
    except Exception as e:
        logger.debug(f"Error looking up country via API: {e}")
    
    # Final fallback: Use AI to detect country from any language
    try:
        from ai_functions import deepseek_ai_country
        logger.info(f"Attempting AI detection for country: {country_name} (language: {language})")
        tz_name = deepseek_ai_country(country_name, language)
        if tz_name:
            logger.info(f"AI detected timezone {tz_name} from country name: {country_name}")
            return tz_name
    except Exception as e:
        logger.error(f"Error using AI for country detection: {e}", exc_info=True)
    
    return None


def get_user_timezone(user, message=None, db=None):
    """
    Get user's timezone. Tries to detect from location first, then falls back to language.
    Returns pytz timezone object.
    """
    # If user has timezone set and it's not UTC, use it
    if user.timezone and user.timezone != 'UTC':
        try:
            return pytz.timezone(user.timezone)
        except:
            pass
    
    # Try to detect timezone from message location if available
    if message and hasattr(message, 'location') and message.location:
        tz_name = get_timezone_from_location(message.location.latitude, message.location.longitude)
        if tz_name and db:
            try:
                db.update_user_timezone(user.telegram_id, tz_name)
                logger.info(f"Updated timezone for user {user.telegram_id} to {tz_name} from location")
                return pytz.timezone(tz_name)
            except Exception as e:
                logger.error(f"Error updating user timezone from location: {e}")
    
    # Fallback: Default timezones based on language
    language_timezones = {
        'uz': 'Asia/Tashkent',  # Uzbekistan
        'ru': 'Europe/Moscow',  # Russia
        'en': 'UTC'  # Default to UTC for English
    }
    
    default_tz_name = language_timezones.get(user.language or 'en', 'UTC')
    default_tz = pytz.timezone(default_tz_name)
    
    # Update user's timezone in database if it's not set or is UTC
    if db and (not user.timezone or user.timezone == 'UTC'):
        try:
            db.update_user_timezone(user.telegram_id, default_tz_name)
            logger.info(f"Updated timezone for user {user.telegram_id} to {default_tz_name} (language-based)")
        except Exception as e:
            logger.error(f"Error updating user timezone: {e}")
    
    return default_tz


class ReminderHandler:
    """Handler for reminder-related commands."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        self.active_reminder_mode = set()  # {user_id} - users in reminder mode
        self.transcriber = VoiceTranscriber()
        self.scheduler = None  # Will be set from bot.py
    
    def handle_reminder_command(self, message: telebot.types.Message):
        """Handle /reminders command or button - enter reminder mode."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        # Enter reminder mode
        self.active_reminder_mode.add(message.from_user.id)
        
        self.bot.reply_to(
            message,
            get_translation(language, "reminder_prompt"),
            reply_markup=create_back_keyboard(language)
        )
    
    def is_in_reminder_mode(self, user_id: int) -> bool:
        """Check if user is in reminder mode."""
        return user_id in self.active_reminder_mode
    
    def handle_reminder_message(self, message: telebot.types.Message):
        """Handle reminder text message."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        # Get user's timezone (and update in DB if needed)
        user_tz = get_user_timezone(user, message, self.db)
        
        text = message.text.strip()
        
        # Show processing message
        processing_msg = self.bot.reply_to(message, get_translation(language, "processing"))
        
        try:
            # Get current time in user's timezone for AI context
            now_user_tz = datetime.now(user_tz)
            
            # Parse time using AI (DeepSeek_AI_2) - pass user's local time
            time_str = deepseek_ai_reminder(text, language, user_timezone=user_tz.zone, current_time=now_user_tz)
            
            if time_str:
                try:
                    # Parse the time string
                    parsed_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    # If naive, assume it's in user's timezone
                    if parsed_time.tzinfo is None:
                        # Localize to user's timezone
                        parsed_time = user_tz.localize(parsed_time)
                    # Convert to UTC for storage
                    remind_time = parsed_time.astimezone(timezone.utc).replace(tzinfo=None)
                except Exception as e:
                    logger.error(f"Error parsing AI time string '{time_str}': {e}")
                    remind_time = self._parse_time_manually(text, language, user_tz)
            else:
                remind_time = self._parse_time_manually(text, language, user_tz)
            
            if not remind_time:
                self.bot.edit_message_text(
                    get_translation(language, "error") + "\n" + get_translation(language, "reminder_prompt"),
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Extract message (remove time-related words)
            reminder_message = self._extract_message(text, language)
            
            # Validate that reminder time is in the future (compare naive UTC datetimes)
            now_utc = datetime.utcnow()
            logger.info(f"Parsed reminder time: {remind_time}, Current UTC: {now_utc}, Difference: {(remind_time - now_utc).total_seconds()} seconds")
            
            if remind_time <= now_utc:
                logger.warning(f"Reminder time {remind_time} is in the past (current: {now_utc})")
                self.bot.edit_message_text(
                    "Reminder time must be in the future.",
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Save reminder with actual reminder time (not 10 minutes before)
            reminder = self.db.add_reminder(message.from_user.id, reminder_message, remind_time)
            logger.info(f"Saved reminder {reminder.id} with time {reminder.reminder_time}")
            
            # Schedule the reminder if scheduler is available
            if self.scheduler:
                self.scheduler.schedule_reminder(reminder)
            
            # Exit reminder mode
            self.active_reminder_mode.discard(message.from_user.id)
            
            # Convert reminder time back to user's timezone for display
            remind_time_user_tz = pytz.UTC.localize(remind_time).astimezone(user_tz)
            remind_time_str = format_reminder_time(remind_time_user_tz, language)
            
            # Confirm reminder added and return to main menu
            from keyboards import create_main_keyboard
            self.bot.edit_message_text(
                get_translation(language, "reminder_added") + f"\n⏰ {remind_time_str}",
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
            # Send main menu
            self.bot.send_message(
                message.chat.id,
                get_translation(language, "main_menu"),
                reply_markup=create_main_keyboard(language)
            )
        
        except Exception as e:
            logger.error(f"Error processing reminder: {e}")
            self.bot.edit_message_text(
                get_translation(language, "error"),
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
    
    def handle_reminder_voice(self, message: telebot.types.Message):
        """Handle reminder voice message."""
        user = self.db.get_or_create_user(message.from_user.id, message.from_user.first_name or "User")
        language = user.language or "en"
        
        # Get user's timezone (and update in DB if needed)
        user_tz = get_user_timezone(user, message, self.db)
        
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
            
            # Get current time in user's timezone for AI context
            now_user_tz = datetime.now(user_tz)
            
            # Parse time using AI - pass user's local time
            time_str = deepseek_ai_reminder(transcribed_text, language, user_timezone=user_tz.zone, current_time=now_user_tz)
            
            if time_str:
                try:
                    # Parse the time string
                    parsed_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    # If naive, assume it's in user's timezone
                    if parsed_time.tzinfo is None:
                        # Localize to user's timezone
                        parsed_time = user_tz.localize(parsed_time)
                    # Convert to UTC for storage
                    remind_time = parsed_time.astimezone(timezone.utc).replace(tzinfo=None)
                except Exception as e:
                    logger.error(f"Error parsing AI time string '{time_str}': {e}")
                    remind_time = self._parse_time_manually(transcribed_text, language, user_tz)
            else:
                remind_time = self._parse_time_manually(transcribed_text, language, user_tz)
            
            if not remind_time:
                self.bot.edit_message_text(
                    get_translation(language, "error"),
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Extract message
            reminder_message = self._extract_message(transcribed_text, language)
            
            # Validate that reminder time is in the future (compare naive UTC datetimes)
            now_utc = datetime.utcnow()
            logger.info(f"Parsed reminder time (voice): {remind_time}, Current UTC: {now_utc}, Difference: {(remind_time - now_utc).total_seconds()} seconds")
            
            if remind_time <= now_utc:
                logger.warning(f"Reminder time {remind_time} is in the past (current: {now_utc})")
                self.bot.edit_message_text(
                    "Reminder time must be in the future.",
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return
            
            # Save reminder with actual reminder time (not 10 minutes before)
            reminder = self.db.add_reminder(message.from_user.id, reminder_message, remind_time)
            logger.info(f"Saved reminder {reminder.id} with time {reminder.reminder_time}")
            
            # Schedule the reminder if scheduler is available
            if self.scheduler:
                self.scheduler.schedule_reminder(reminder)
            
            # Exit reminder mode
            self.active_reminder_mode.discard(message.from_user.id)
            
            # Convert reminder time back to user's timezone for display
            remind_time_user_tz = pytz.UTC.localize(remind_time).astimezone(user_tz)
            remind_time_str = format_reminder_time(remind_time_user_tz, language)
            
            # Confirm reminder added and return to main menu
            from keyboards import create_main_keyboard
            self.bot.edit_message_text(
                get_translation(language, "reminder_added") + f"\n⏰ {remind_time_str}",
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
            # Send main menu
            self.bot.send_message(
                message.chat.id,
                get_translation(language, "main_menu"),
                reply_markup=create_main_keyboard(language)
            )
        
        except Exception as e:
            logger.error(f"Error processing reminder voice: {e}")
            self.bot.edit_message_text(
                get_translation(language, "error"),
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def _parse_time_manually(self, text: str, language: str, user_tz: pytz.timezone = None) -> datetime:
        """Manual time parsing fallback. Returns naive UTC datetime."""
        if user_tz is None:
            user_tz = pytz.UTC
        
        # Get current time in user's timezone
        now_user_tz = datetime.now(user_tz)
        text_lower = text.lower()
        
        # Handle relative time expressions first
        # Pattern: "after X minutes/hours" or "in X minutes/hours"
        relative_patterns = [
            (r'after\s+(\d+)\s+minutes?', 'minutes'),
            (r'in\s+(\d+)\s+minutes?', 'minutes'),
            (r'after\s+(\d+)\s+hours?', 'hours'),
            (r'in\s+(\d+)\s+hours?', 'hours'),
            (r'after\s+(\d+)\s+days?', 'days'),
            (r'in\s+(\d+)\s+days?', 'days'),
        ]
        
        # Also check for language-specific patterns
        if language == "ru":
            relative_patterns.extend([
                (r'через\s+(\d+)\s+минут', 'minutes'),
                (r'через\s+(\d+)\s+час', 'hours'),
                (r'через\s+(\d+)\s+дн', 'days'),
            ])
        elif language == "uz":
            relative_patterns.extend([
                (r'(\d+)\s+минутдан\s+кейин', 'minutes'),
                (r'(\d+)\s+соатдан\s+кейин', 'hours'),
                (r'(\d+)\s+кундан\s+кейин', 'days'),
            ])
        
        for pattern, unit in relative_patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = int(match.group(1))
                if unit == 'minutes':
                    remind_time_user = now_user_tz + timedelta(minutes=value)
                elif unit == 'hours':
                    remind_time_user = now_user_tz + timedelta(hours=value)
                elif unit == 'days':
                    remind_time_user = now_user_tz + timedelta(days=value)
                else:
                    continue
                # Convert to UTC for storage
                if remind_time_user.tzinfo is None:
                    remind_time_user = user_tz.localize(remind_time_user)
                return remind_time_user.astimezone(timezone.utc).replace(tzinfo=None)
        
        # Look for time patterns (HH:MM or H:MM)
        time_pattern = re.search(r'(\d{1,2}):(\d{2})', text)
        if time_pattern:
            hour = int(time_pattern.group(1))
            minute = int(time_pattern.group(2))
            
            # Check for "tomorrow" keywords
            tomorrow_keywords = {
                "uz": ["ertaga", "ertasi"],
                "ru": ["завтра"],
                "en": ["tomorrow"]
            }
            
            keywords = tomorrow_keywords.get(language, [])
            is_tomorrow = any(kw in text_lower for kw in keywords)
            
            if is_tomorrow:
                remind_time_user = (now_user_tz + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                remind_time_user = now_user_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if remind_time_user <= now_user_tz:
                    remind_time_user += timedelta(days=1)
            
            # Localize and convert to UTC
            if remind_time_user.tzinfo is None:
                remind_time_user = user_tz.localize(remind_time_user)
            return remind_time_user.astimezone(timezone.utc).replace(tzinfo=None)
        
        return None
    
    def _extract_message(self, text: str, language: str) -> str:
        """Extract reminder message by removing time-related words."""
        result = text
        
        # Remove relative time expressions
        relative_patterns = [
            r'after\s+\d+\s+(?:minutes?|hours?|days?)\s*',
            r'in\s+\d+\s+(?:minutes?|hours?|days?)\s*',
        ]
        
        if language == "ru":
            relative_patterns.extend([
                r'через\s+\d+\s+(?:минут|час|дн)\s*',
            ])
        elif language == "uz":
            relative_patterns.extend([
                r'\d+\s+(?:минутдан|соатдан|кундан)\s+кейин\s*',
            ])
        
        for pattern in relative_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # Remove common time words
        time_words = {
            "uz": ["ertaga", "ertasi", "soat", "da", "da eslat"],
            "ru": ["завтра", "в", "часов", "напомнить"],
            "en": ["tomorrow", "at", "remind", "me", "after", "in"]
        }
        
        words = time_words.get(language, [])
        for word in words:
            result = re.sub(rf'\b{word}\b', '', result, flags=re.IGNORECASE)
        
        # Remove time patterns
        result = re.sub(r'\d{1,2}:\d{2}', '', result)
        
        return result.strip()

