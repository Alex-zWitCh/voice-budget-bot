# SmartExpense 2.0

Telegram-бот для быстрого голосового учета личного и семейного бюджета.
Рабочее имя проекта в коде и документации: Voice Budget Bot.

<p align="center">
  <img src="assets/readme-description.png" alt="Voice Budget Bot overview" width="900">
</p>

Пользователь отправляет короткое голосовое сообщение с одной операцией. Бот
проверяет длительность, нормализует аудио через FFmpeg, распознает речь через
Groq Whisper, извлекает структуру операции через DeepSeek и сохраняет результат
в локальную SQLite-базу. Приветствие, картинка и подпись настраиваются через
переменные окружения.

## Project origin

This project is based on SmartExpenseBot by Botir Bakhtiyarov and is distributed
under the MIT License.

The bot is named SmartExpense 2.0 in memory of the repository that inspired this
fork. The current version contains a substantial redesign focused on voice-only
private and family budget tracking, Groq speech recognition, DeepSeek-based
income/expense extraction and local storage.

## MVP Features

- личные чаты и явно разрешенные семейные группы;
- только Telegram voice до 8 секунд;
- Groq `whisper-large-v3` для speech-to-text;
- DeepSeek JSON extraction для `EXPENSE` и `INCOME`;
- суммы хранятся как integer minor units, без float;
- SQLite-таблицы `users`, `chats`, `transactions`, `processing_events`;
- защита от дублей по `telegram_chat_id + telegram_message_id`;
- кнопка удаления ошибочно добавленной записи;
- системная категория `Переводы` для семейных внутренних переводов;
- пользовательские категории через кнопки в Telegram;
- отложенные списания, которые автоматически фиксируются в будущую дату;
- голосовые напоминания с разовыми и регулярными событиями;
- команда `/calendar` для просмотра будущих событий на 2 месяца;
- настраиваемое приветствие и кнопочное меню Telegram;
- временные аудиофайлы удаляются после обработки;
- Docker Compose deployment.

## Commands

- `/start` — приветствие и меню.
- `/menu` — показать кнопки меню.
- `/calendar` — календарь будущих событий на 2 месяца.
- `/categories` — категории и управление своими категориями.

Кнопочное меню дублирует основные действия: календарь, категории, добавление и
удаление пользовательских категорий.

<details>
<summary>System Categories</summary>

Расходы:

- Продукты
- Кафе
- Транспорт
- Автомобиль
- Жильё
- Здоровье
- Одежда
- Дети
- Развлечения
- Подписки и связь
- Техника
- Образование
- Подарки
- Переводы
- Путешествия
- Прочее

Доходы:

- Зарплата
- Подработка
- Бизнес
- Пособия
- Пенсия
- Возврат
- Подарок
- Переводы
- Продажа
- Инвестиции
- Прочее

</details>

## Calendar And Reminders

Бот понимает голосовые фразы для будущих событий:

- `20 декабря будут списаны 1000 рублей за интернет` — создаст отложенное списание. В нужный день бот зафиксирует расход и напишет сообщение.
- `напомни через 4 дня в 15:00 сходить в туалет` — создаст напоминание на событие в 15:00, а сообщение пришлёт за 30 минут.
- `напомни через 3 дня купить подарок` — если время не указано, используется текущее время суток.
- `поздравь с днем рождения маму ежегодно 5 декабря` — создаст ежегодное напоминание.

Поддерживаемая регулярность: `ежедневно`, `еженедельно`, `ежемесячно`, `ежегодно`.

Команда:

```text
/calendar
```

показывает все будущие списания и напоминания на ближайшие 2 месяца, включая
следующие срабатывания регулярных событий.

## Bot Assets

- `assets/bot-icon.png` is the source icon for the Telegram bot avatar.
- `assets/readme-description.png` is the README overview image.

## Welcome Message

Приветствие настраивается в `.env`:

```dotenv
WELCOME_TITLE=SmartExpense 2.0
WELCOME_INTRO=Отправьте короткое голосовое сообщение, чтобы записать доход, расход, напоминание или отложенное списание.
WELCOME_FOOTER=
WELCOME_IMAGE_PATH=assets/readme-description.png
```

По умолчанию текст нейтральный. Чтобы добавить личную подпись, заполните
`WELCOME_FOOTER`. Категории в приветствии не выводятся целиком: они доступны по
кнопке `Показать категории`, чтобы не загромождать стартовое сообщение.

## Configuration

Copy `.env.example` to `.env` and fill secrets outside Git:

```dotenv
BOT_TOKEN=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
ALLOWED_CHAT_IDS=
```

When `ALLOWED_CHAT_IDS` is empty, private chats are allowed and groups are
ignored. For group use, add the group ID, for example:

```dotenv
ALLOWED_CHAT_IDS=123456789,-1001234567890
```

## Run

```bash
docker compose up -d --build
```

For local tests:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Privacy

Audio is sent only to Groq for transcription. The transcript is sent to
DeepSeek for structured extraction. API keys, transcripts, amounts,
descriptions and raw model responses are not written to logs.
