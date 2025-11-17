"""
DeepSeek API integration for SmartExpenseBot.
Three specialized AI functions for different tasks.
"""

import requests
import json
import logging
from typing import Dict, Optional
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


def deepseek_ai_expense(text: str, lang: str = "en") -> Dict:
    """
    DeepSeek_AI_1: Specialized for expense extraction and categorization.
    
    Args:
        text: User's expense description
        lang: User's language preference (uz, ru, en)
    
    Returns:
        Dictionary with amount, category, description, currency, and advice
    """
    prompts = {
        "uz": f"""Quyidagi xarajatni tahlil qiling va quyidagi formatda JSON javob bering:
{{
    "amount": <raqam>,
    "currency": "<valyuta>",
    "category": "<kategoriya>",
    "description": "<tavsif>",
    "advice": "<tavsiya yoki bo'sh string>"
}}

MUHIM: Valyutani matndan aniqlang (masalan: USD, EUR, CNY, RMB, Yuan, Dollar, Euro, so'm, rubl, va hokazo). Agar valyuta ko'rsatilmagan bo'lsa, "USD" dan foydalaning.

Kategoriyalar: Food, Transport, Entertainment, Education, Health, Electronics, Shopping, Bills, Other
Xarajat: {text}""",
        "ru": f"""Проанализируйте следующий расход и верните JSON ответ в следующем формате:
{{
    "amount": <число>,
    "currency": "<валюта>",
    "category": "<категория>",
    "description": "<описание>",
    "advice": "<совет или пустая строка>"
}}

ВАЖНО: Определите валюту из текста (например: USD, EUR, CNY, RMB, Yuan, Dollar, Euro, доллар, юань, рубль и т.д.). Если валюта не указана, используйте "USD".

Категории: Food, Transport, Entertainment, Education, Health, Electronics, Shopping, Bills, Other
Расход: {text}""",
        "en": f"""Analyze the following expense and return a JSON response in the following format:
{{
    "amount": <number>,
    "currency": "<currency>",
    "category": "<category>",
    "description": "<description>",
    "advice": "<advice or empty string>"
}}

IMPORTANT: Detect the currency from the text (e.g., USD, EUR, CNY, RMB, Yuan, Dollar, Euro, dollars, yuan, etc.). If no currency is mentioned, use "USD".

Categories: Food, Transport, Entertainment, Education, Health, Electronics, Shopping, Bills, Other
Expense: {text}"""
    }
    
    prompt = prompts.get(lang, prompts["en"])
    
    try:
        headers = {
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are DeepSeek_AI_1 - specialized for expense extraction and categorization. CRITICAL: Each request is completely independent - do NOT use any context from previous requests. Your ONLY job is to extract expense information (amount, currency, category, description) from the CURRENT user message and return valid JSON. You MUST detect the currency from the text itself (USD, EUR, CNY, RMB, Yuan, Dollar, Euro, etc.). If no currency is mentioned, default to USD. You do NOT add expenses to database - you only extract information for confirmation."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Try to extract JSON from response
            try:
                # Remove markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result = json.loads(content)
                
                # Validate and set defaults
                amount_value = result.get("amount")
                if amount_value is None:
                    amount = 0.0
                else:
                    try:
                        amount = float(amount_value)
                    except (ValueError, TypeError):
                        amount = 0.0
                
                # Extract currency - normalize common variations
                currency_raw = result.get("currency", "USD").upper().strip()
                currency_map = {
                    "YUAN": "CNY", "RMB": "CNY", "CN¥": "CNY", "¥": "CNY",
                    "DOLLAR": "USD", "DOLLARS": "USD", "$": "USD", "US$": "USD",
                    "EURO": "EUR", "EUROS": "EUR", "€": "EUR",
                    "RUBLE": "RUB", "RUBLES": "RUB", "RUBL": "RUB", "₽": "RUB",
                    "SOM": "UZS", "SO'M": "UZS", "UZS": "UZS"
                }
                currency = currency_map.get(currency_raw, currency_raw if len(currency_raw) <= 5 else "USD")
                
                category = result.get("category", "Other")
                description = result.get("description", text)
                advice = result.get("advice", "")
                
                return {
                    "amount": amount,
                    "currency": currency,
                    "category": category,
                    "description": description,
                    "advice": advice
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in expense AI: {e}")
                return _extract_expense_manually(text, lang)
        else:
            logger.error(f"DeepSeek API error in expense AI: {response.status_code}")
            return _extract_expense_manually(text, lang)
    
    except Exception as e:
        logger.error(f"Error calling DeepSeek API for expense: {e}")
        return _extract_expense_manually(text, lang)


def deepseek_ai_report(text: str, lang: str = "en", expenses_data: list = None, user_currency: str = "USD") -> str:
    """
    DeepSeek_AI_data: Generate financial reports based on user queries.
    
    Args:
        text: User's report query
        lang: User's language preference
        expenses_data: List of expense and/or income objects from database
        user_currency: User's currency from User table (for display)
    
    Returns:
        Formatted report string
    """
    # Prepare context with expenses and incomes
    from database import Expense, Income
    
    expenses_context = ""
    if expenses_data:
        # Separate expenses and incomes
        expenses = [e for e in expenses_data if isinstance(e, Expense)]
        incomes = [i for i in expenses_data if isinstance(i, Income)]
        
        expenses_context = "\n\nUser's financial data:\n"
        
        # Process expenses - use user's currency from User table
        if expenses:
            total_expenses = sum(e.amount for e in expenses)
            categories = {}
            for e in expenses:
                cat = getattr(e, 'category', 'Other') or "Other"
                categories[cat] = categories.get(cat, 0) + e.amount
            
            expenses_context += f"\nExpenses (total {len(expenses)} records):\n"
            expenses_context += f"Total: {total_expenses:.2f} {user_currency}\n"
            expenses_context += "By category:\n"
            for cat, amount in categories.items():
                expenses_context += f"- {cat}: {amount:.2f} {user_currency}\n"
            expenses_context += "\nRecent expenses:\n"
            for e in expenses[:10]:
                date_str = e.date.strftime("%Y-%m-%d") if hasattr(e, 'date') and e.date else 'N/A'
                category = getattr(e, 'category', 'Other') or 'Other'
                description = getattr(e, 'description', '') or ''
                expenses_context += f"- {date_str}: {e.amount:.2f} {user_currency} ({category}): {description}\n"
        
        # Process incomes - use user's currency from User table
        if incomes and len(incomes) > 0:
            total_incomes = sum(i.amount for i in incomes)
            expenses_context += f"\nIncomes (total {len(incomes)} records):\n"
            expenses_context += f"Total: {total_incomes:.2f} {user_currency}\n"
            expenses_context += "Recent incomes:\n"
            for i in incomes[:10]:
                date_str = i.date.strftime("%Y-%m-%d") if hasattr(i, 'date') and i.date else 'N/A'
                income_type = getattr(i, 'income_type', 'monthly') or 'monthly'
                description = getattr(i, 'description', '') or ''
                expenses_context += f"- {date_str}: {i.amount:.2f} {user_currency} ({income_type}): {description}\n"
        
        if not expenses and not incomes:
            expenses_context += "\nUser has no financial data recorded yet."
    else:
        expenses_context = "\n\nUser has no financial data recorded yet."
    
    prompts = {
        "uz": f"""Siz foydalanuvchining shaxsiy yordamchisisiz va uning ma'lumotlar bazasiga ulangansiz.
Sizning vazifangiz: foydalanuvchi bilan uning xarajatlari va daromadlari haqida suhbatlashish, hisobotlar berish, savollarga javob berish.

MUHIM: 
- Siz xarajatlar yoki daromadlar qo'sha OLMAYSIZ - faqat o'qish va hisobot berish mumkin
- Agar foydalanuvchi xarajat yoki daromad qo'shmoqchi bo'lsa, tegishli tugmalarni bosishi kerak
- Siz faqat mavjud ma'lumotlar haqida gapirasiz va hisobot berasiz
- Hisobotda daromad va xarajatlarni taqqoslab, balansni ko'rsating

Foydalanuvchi so'rovi: {text}
{expenses_context}

Javob bering va kerak bo'lsa, ma'lumotlar bazasidagi ma'lumotlardan foydalaning.""",
        "ru": f"""Вы личный помощник пользователя, подключенный к его базе данных.
Ваша задача: общаться с пользователем о его расходах и доходах, предоставлять отчеты, отвечать на вопросы.

ВАЖНО:
- Вы НЕ МОЖЕТЕ добавлять расходы или доходы - только читать и предоставлять отчеты
- Если пользователь хочет добавить расход или доход, он должен нажать соответствующие кнопки
- Вы только обсуждаете существующие данные и предоставляете отчеты
- В отчете сравнивайте доходы и расходы, показывайте баланс

Запрос пользователя: {text}
{expenses_context}

Ответьте и при необходимости используйте данные из базы данных.""",
        "en": f"""You are the user's personal assistant, connected to their database.
Your task: chat with the user about their expenses and income, provide reports, answer questions.

IMPORTANT:
- You CANNOT add expenses or income - you can only read and provide reports
- If the user wants to add an expense or income, they must press the appropriate buttons
- You only discuss existing data and provide reports
- In reports, compare income and expenses, show balance

User's query: {text}
{expenses_context}

Respond and use database information if relevant."""
    }
    
    prompt = prompts.get(lang, prompts["en"])
    
    try:
        headers = {
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Determine language name for system message
        lang_names = {
            "uz": "Uzbek (O'zbek tili)",
            "ru": "Russian (Русский)",
            "en": "English"
        }
        lang_name = lang_names.get(lang, "English")
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"You are DeepSeek_AI_data - a personal assistant connected to the user's database. CRITICAL: You MUST respond ONLY in {lang_name} language. The user's language is {lang_name}. You can ONLY read and discuss existing records (expenses and income). You CANNOT add, modify, or delete any records. If the user wants to add records, direct them to use the appropriate function buttons. Your role is to provide reports, answer questions, compare income vs expenses, and give advice based on existing data. IMPORTANT: Do NOT use markdown formatting (no ##, **, __, `, etc.) - use plain text only. Use simple text formatting like dashes (-) for lists."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip()
        else:
            logger.error(f"DeepSeek API error in report AI: {response.status_code}")
            return "Error generating report. Please try again."
    
    except Exception as e:
        logger.error(f"Error calling DeepSeek API for report: {e}")
        return "Error generating report. Please try again."


def deepseek_ai_reminder(text: str, lang: str = "en", user_timezone: str = "UTC", current_time: datetime = None) -> Optional[str]:
    """
    DeepSeek_AI_2: Specialized for reminder time extraction.
    
    Args:
        text: User's reminder text with time
        lang: User's language preference
        user_timezone: User's timezone (e.g., 'Asia/Tashkent', 'Europe/Moscow')
        current_time: Current datetime in user's timezone (datetime object)
    
    Returns:
        ISO format datetime string or None
    """
    prompts = {
        "uz": f"""Quyidagi matndan vaqtni ajratib oling va ISO formatda qaytaring (YYYY-MM-DD HH:MM:SS):
Matn: {text}
Agar vaqt topilmasa, None qaytaring.""",
        "ru": f"""Извлеките время из следующего текста и верните в формате ISO (YYYY-MM-DD HH:MM:SS):
Текст: {text}
Если время не найдено, верните None.""",
        "en": f"""Extract time from the following text and return in ISO format (YYYY-MM-DD HH:MM:SS):
Text: {text}
If time is not found, return None."""
    }
    
    prompt = prompts.get(lang, prompts["en"])
    
    try:
        headers = {
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Get current time in user's timezone for context
        if current_time:
            current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"You are DeepSeek_AI_2 - specialized for reminder time extraction. Your ONLY job is to extract time/date information from user messages and return ISO format datetime string (YYYY-MM-DD HH:MM:SS). IMPORTANT: The user is in timezone {user_timezone}. Current local time: {current_time_str}. For relative times like 'after 15 minutes', 'in 30 minutes', calculate the actual future datetime from the current local time. Return only the ISO datetime string or 'None' if time cannot be extracted."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if content.lower() == "none" or not content:
                return None
            
            return content
        else:
            logger.error(f"DeepSeek API error in reminder AI: {response.status_code}")
            return None
    
    except Exception as e:
        logger.error(f"Error calling DeepSeek API for reminder: {e}")
        return None


def deepseek_ai_expense_multiple(text: str, lang: str = "en", default_currency: str = "USD") -> list:
    """
    DeepSeek_AI_1: Extract multiple expenses from a single message.
    
    Args:
        text: User's expense description (may contain multiple expenses)
        lang: User's language preference
        default_currency: Default currency if not specified
    
    Returns:
        List of expense dictionaries
    """
    prompts = {
        "uz": f"""Quyidagi matndan BARCHA xarajatlarni ajratib oling va JSON array formatida javob bering:
[
    {{
        "amount": <raqam>,
        "currency": "<valyuta>",
        "category": "<kategoriya>",
        "description": "<tavsif>"
    }},
    ...
]

MUHIM: Agar bir nechta xarajat bo'lsa, ularni alohida ajratib oling. Valyutani har bir xarajat uchun alohida aniqlang.

Kategoriyalar: Food, Transport, Entertainment, Education, Health, Electronics, Shopping, Bills, Other
Matn: {text}""",
        "ru": f"""Извлеките ВСЕ расходы из следующего текста и верните JSON массив:
[
    {{
        "amount": <число>,
        "currency": "<валюта>",
        "category": "<категория>",
        "description": "<описание>"
    }},
    ...
]

ВАЖНО: Если есть несколько расходов, разделите их отдельно. Определите валюту для каждого расхода отдельно.

Категории: Food, Transport, Entertainment, Education, Health, Electronics, Shopping, Bills, Other
Текст: {text}""",
        "en": f"""Extract ALL expenses from the following text and return a JSON array:
[
    {{
        "amount": <number>,
        "currency": "<currency>",
        "category": "<category>",
        "description": "<description>"
    }},
    ...
]

IMPORTANT: If there are multiple expenses, separate them individually. Detect currency for each expense separately.

Categories: Food, Transport, Entertainment, Education, Health, Electronics, Shopping, Bills, Other
Text: {text}"""
    }
    
    prompt = prompts.get(lang, prompts["en"])
    
    try:
        headers = {
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"You are DeepSeek_AI_1 - specialized for expense extraction. Extract ALL expenses from the user's message. If there are multiple expenses, return a JSON array with each expense as a separate object. Each expense must have: amount, currency (detect from text or use {default_currency}), category, and description. Return ONLY valid JSON array."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            try:
                # Remove markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result = json.loads(content)
                
                # Ensure result is a list
                if not isinstance(result, list):
                    result = [result]
                
                # Normalize expenses
                expenses = []
                for item in result:
                    amount_value = item.get("amount", 0)
                    try:
                        amount = float(amount_value)
                    except (ValueError, TypeError):
                        amount = 0.0
                    
                    currency_raw = item.get("currency", default_currency).upper().strip()
                    currency_map = {
                        "YUAN": "CNY", "RMB": "CNY", "CN¥": "CNY", "¥": "CNY",
                        "DOLLAR": "USD", "DOLLARS": "USD", "$": "USD", "US$": "USD",
                        "EURO": "EUR", "EUROS": "EUR", "€": "EUR",
                        "RUBLE": "RUB", "RUBLES": "RUB", "RUBL": "RUB", "₽": "RUB",
                        "SOM": "UZS", "SO'M": "UZS", "UZS": "UZS"
                    }
                    currency = currency_map.get(currency_raw, currency_raw if len(currency_raw) <= 5 else default_currency)
                    
                    expenses.append({
                        "amount": amount,
                        "currency": currency,
                        "category": item.get("category", "Other"),
                        "description": item.get("description", "")
                    })
                
                return expenses
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in multiple expense AI: {e}")
                # Fallback: try single expense extraction
                single = deepseek_ai_expense(text, lang)
                return [single] if single.get("amount", 0) > 0 else []
        else:
            logger.error(f"DeepSeek API error in multiple expense AI: {response.status_code}")
            single = deepseek_ai_expense(text, lang)
            return [single] if single.get("amount", 0) > 0 else []
    
    except Exception as e:
        logger.error(f"Error calling DeepSeek API for multiple expenses: {e}")
        single = deepseek_ai_expense(text, lang)
        return [single] if single.get("amount", 0) > 0 else []


def deepseek_ai_country(country_text: str, lang: str = "en") -> Optional[str]:
    """
    DeepSeek_AI_Country: Detect country name from any language and return timezone.
    
    Args:
        country_text: Country name in any language (e.g., "Uzbekistan", "Узбекистан", "O'zbekiston")
        lang: User's language preference (uz, ru, en)
    
    Returns:
        Timezone name string (e.g., "Asia/Tashkent") or None
    """
    prompts = {
        "uz": f"""Quyidagi matndan mamlakat nomini aniqlang va uning vaqt mintaqasini (timezone) qaytaring.
Mamlakat nomi: {country_text}

Siz faqat timezone nomini qaytaring (masalan: "Asia/Tashkent", "Europe/Moscow", "America/New_York").
Agar mamlakat aniqlanmasa, "None" qaytaring.
Faqat timezone nomini yoki "None" ni qaytaring, boshqa hech narsa emas.""",
        "ru": f"""Определите название страны из следующего текста и верните её часовой пояс (timezone).
Название страны: {country_text}

Верните только название timezone (например: "Asia/Tashkent", "Europe/Moscow", "America/New_York").
Если страна не определена, верните "None".
Верните только название timezone или "None", ничего больше.""",
        "en": f"""Identify the country name from the following text and return its timezone.
Country name: {country_text}

Return only the timezone name (e.g., "Asia/Tashkent", "Europe/Moscow", "America/New_York").
If country cannot be identified, return "None".
Return only the timezone name or "None", nothing else."""
    }
    
    prompt = prompts.get(lang, prompts["en"])
    
    try:
        headers = {
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are DeepSeek_AI_Country - specialized for country detection and timezone identification from any language. Your ONLY job is to identify the country name from user input (which can be in any language: English, Russian, Uzbek, etc.) and return the corresponding IANA timezone name (e.g., 'Asia/Tashkent', 'Europe/Moscow', 'America/New_York'). Return ONLY the timezone name or 'None' if country cannot be identified. Do not include any explanation or additional text."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Clean up response - remove quotes, whitespace, etc.
            content = content.strip().strip('"').strip("'").strip()
            
            if content.lower() == "none" or not content:
                logger.debug(f"AI could not detect country from: {country_text}")
                return None
            
            # Validate timezone format (basic check)
            if "/" in content and len(content.split("/")) == 2:
                logger.info(f"AI detected timezone {content} from country text: {country_text} (language: {lang})")
                return content
            else:
                logger.warning(f"AI returned invalid timezone format: {content} from country text: {country_text}")
                return None
        else:
            logger.error(f"DeepSeek API error in country AI: {response.status_code}")
            return None
    
    except Exception as e:
        logger.error(f"Error calling DeepSeek API for country detection: {e}", exc_info=True)
        return None


def deepseek_ai_income(text: str, lang: str = "en", default_currency: str = "USD") -> Dict:
    """
    DeepSeek_AI_Income: Extract income information from natural language.
    
    Args:
        text: User's income description (text or transcribed voice)
        lang: User's language preference (uz, ru, en)
        default_currency: Default currency if not specified
    
    Returns:
        Dictionary with amount, currency, description, and income_type (monthly/daily)
    """
    prompts = {
        "uz": f"""Quyidagi matndan daromad ma'lumotlarini ajratib oling va JSON formatida javob bering:
{{
    "amount": <raqam>,
    "currency": "<valyuta>",
    "description": "<tavsif>",
    "income_type": "<monthly yoki daily>"
}}

MUHIM: 
- Valyutani matndan aniqlang (masalan: USD, EUR, CNY, RMB, Yuan, Dollar, Euro, so'm, rubl)
- income_type: Agar "oylik", "monthly", "har oy" deb aytilgan bo'lsa "monthly", "kunlik", "daily", "har kuni" bo'lsa "daily"
- Agar valyuta ko'rsatilmagan bo'lsa, "{default_currency}" dan foydalaning

Matn: {text}""",
        "ru": f"""Извлеките информацию о доходе из следующего текста и верните JSON ответ:
{{
    "amount": <число>,
    "currency": "<валюта>",
    "description": "<описание>",
    "income_type": "<monthly или daily>"
}}

ВАЖНО:
- Определите валюту из текста (например: USD, EUR, CNY, RMB, Yuan, Dollar, Euro, доллар, юань, рубль)
- income_type: Если сказано "месячный", "monthly", "каждый месяц" - "monthly", если "дневной", "daily", "каждый день" - "daily"
- Если валюта не указана, используйте "{default_currency}"

Текст: {text}""",
        "en": f"""Extract income information from the following text and return a JSON response:
{{
    "amount": <number>,
    "currency": "<currency>",
    "description": "<description>",
    "income_type": "<monthly or daily>"
}}

IMPORTANT:
- Detect the currency from the text (e.g., USD, EUR, CNY, RMB, Yuan, Dollar, Euro, dollars, yuan, etc.)
- income_type: If mentioned as "monthly", "per month", "each month" - use "monthly", if "daily", "per day", "each day" - use "daily"
- If no currency is mentioned, use "{default_currency}"

Text: {text}"""
    }
    
    prompt = prompts.get(lang, prompts["en"])
    
    try:
        headers = {
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"You are DeepSeek_AI_Income - specialized for income extraction. Extract income information from user messages. Detect amount, currency (from text or use {default_currency}), description, and income_type (monthly or daily based on context). Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            try:
                # Remove markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result = json.loads(content)
                
                # Validate and normalize
                amount_value = result.get("amount", 0)
                try:
                    amount = float(amount_value)
                except (ValueError, TypeError):
                    amount = 0.0
                
                currency_raw = result.get("currency", default_currency).upper().strip()
                currency_map = {
                    "YUAN": "CNY", "RMB": "CNY", "CN¥": "CNY", "¥": "CNY",
                    "DOLLAR": "USD", "DOLLARS": "USD", "$": "USD", "US$": "USD",
                    "EURO": "EUR", "EUROS": "EUR", "€": "EUR",
                    "RUBLE": "RUB", "RUBLES": "RUB", "RUBL": "RUB", "₽": "RUB",
                    "SOM": "UZS", "SO'M": "UZS", "UZS": "UZS"
                }
                currency = currency_map.get(currency_raw, currency_raw if len(currency_raw) <= 5 else default_currency)
                
                income_type_raw = result.get("income_type", "monthly").lower().strip()
                income_type = "monthly" if "month" in income_type_raw or income_type_raw == "monthly" else "daily"
                
                return {
                    "amount": amount,
                    "currency": currency,
                    "description": result.get("description", ""),
                    "income_type": income_type
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in income AI: {e}")
                return _extract_income_manually(text, lang, default_currency)
        else:
            logger.error(f"DeepSeek API error in income AI: {response.status_code}")
            return _extract_income_manually(text, lang, default_currency)
    
    except Exception as e:
        logger.error(f"Error calling DeepSeek API for income: {e}")
        return _extract_income_manually(text, lang, default_currency)


def _extract_income_manually(text: str, lang: str, default_currency: str) -> Dict:
    """Fallback manual extraction if API fails."""
    import re
    
    # Try to extract numbers
    numbers = re.findall(r'\d+\.?\d*', text)
    amount = float(numbers[0]) if numbers else 0.0
    
    text_lower = text.lower()
    
    # Detect income type
    income_type = "monthly"
    if any(word in text_lower for word in ["daily", "per day", "each day", "kunlik", "har kuni", "дневной", "каждый день"]):
        income_type = "daily"
    
    # Try to detect currency
    currency = default_currency
    if any(word in text_lower for word in ["yuan", "rmb", "cny", "¥"]):
        currency = "CNY"
    elif any(word in text_lower for word in ["dollar", "usd", "$"]):
        currency = "USD"
    elif any(word in text_lower for word in ["euro", "eur", "€"]):
        currency = "EUR"
    elif any(word in text_lower for word in ["ruble", "rub", "₽", "rubl"]):
        currency = "RUB"
    elif any(word in text_lower for word in ["som", "so'm", "uzs"]):
        currency = "UZS"
    
    return {
        "amount": amount,
        "currency": currency,
        "description": text,
        "income_type": income_type
    }


def _extract_expense_manually(text: str, lang: str) -> Dict:
    """Fallback manual extraction if API fails."""
    import re
    
    # Try to extract numbers
    numbers = re.findall(r'\d+\.?\d*', text)
    amount = float(numbers[0]) if numbers else 0.0
    
    # Simple keyword-based categorization
    text_lower = text.lower()
    category = "Other"
    
    food_keywords = ["burger", "food", "restaurant", "eat", "meal", "pizza", "osh", "non", "taom", "еда", "ресторан", "lunch", "dinner", "breakfast"]
    transport_keywords = ["taxi", "bus", "train", "transport", "taksi", "avtobus", "mashina", "такси", "автобус"]
    entertainment_keywords = ["cinema", "movie", "game", "entertainment", "kino", "o'yin", "кино", "игра"]
    education_keywords = ["book", "course", "education", "kitob", "kurs", "ta'lim", "книга", "курс"]
    health_keywords = ["doctor", "medicine", "hospital", "health", "doktor", "dori", "shifoxona", "доктор", "лекарство"]
    electronics_keywords = ["phone", "computer", "electronic", "telefon", "kompyuter", "телефон", "компьютер"]
    
    if any(kw in text_lower for kw in food_keywords):
        category = "Food"
    elif any(kw in text_lower for kw in transport_keywords):
        category = "Transport"
    elif any(kw in text_lower for kw in entertainment_keywords):
        category = "Entertainment"
    elif any(kw in text_lower for kw in education_keywords):
        category = "Education"
    elif any(kw in text_lower for kw in health_keywords):
        category = "Health"
    elif any(kw in text_lower for kw in electronics_keywords):
        category = "Electronics"
    
    # Try to detect currency from text
    currency = "USD"  # Default
    if any(word in text_lower for word in ["yuan", "rmb", "cny", "¥"]):
        currency = "CNY"
    elif any(word in text_lower for word in ["dollar", "usd", "$"]):
        currency = "USD"
    elif any(word in text_lower for word in ["euro", "eur", "€"]):
        currency = "EUR"
    elif any(word in text_lower for word in ["ruble", "rub", "₽"]):
        currency = "RUB"
    elif any(word in text_lower for word in ["som", "so'm", "uzs"]):
        currency = "UZS"
    
    return {
        "amount": amount,
        "currency": currency,
        "category": category,
        "description": text,
        "advice": ""
    }

