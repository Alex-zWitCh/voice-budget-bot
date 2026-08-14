# SmartExpense 2.0

Telegram-бот для быстрого голосового и текстового учета личного и семейного бюджета.
Рабочее имя проекта в коде и документации: Voice Budget Bot.

<p align="center">
  <img src="assets/readme-description.png?v=3" alt="Voice Budget Bot overview" width="900">
</p>

Пользователь отправляет короткое голосовое сообщение или обычный текст с одной
операцией. Для voice бот проверяет длительность, нормализует аудио через FFmpeg
и распознает речь через локальный OpenAI-compatible STT-шлюз
(`Systran/faster-whisper-large-v3`, опционально резервный Groq). Затем и голосовая
расшифровка, и текстовый ввод проходят один путь: DeepSeek извлекает структуру
операции, а результат сохраняется в локальную SQLite-базу. Приветствие, картинка
и подпись настраиваются через переменные окружения.

В приветствии всегда показывается ссылка на автора форка:
<https://github.com/Alex-zWitCh>. Эта ссылка встроена в код и не отключается
через `.env`.

## Project origin

This project is based on SmartExpenseBot by Botir Bakhtiyarov and is distributed
under the MIT License.

The bot is named SmartExpense 2.0 in memory of the repository that inspired this
fork. The current version contains a substantial redesign focused on private and
family budget tracking, local OpenAI-compatible STT speech recognition with
optional Groq fallback, direct text input,
DeepSeek-based income/expense extraction and local storage.

## MVP Features

- личные чаты и явно разрешенные семейные группы;
- Telegram voice до 16 секунд и прямой текстовый ввод операций;
- локальный OpenAI-compatible STT (`Systran/faster-whisper-large-v3` на `https://stt.example.com:7443/v1`) + опциональный резервный Groq `whisper-large-v3`;
- DeepSeek JSON extraction для `EXPENSE` и `INCOME`;
- суммы хранятся как integer minor units, без float;
- SQLite-таблицы `users`, `chats`, `transactions`, `processing_events`;
- защита от дублей по `telegram_chat_id + telegram_message_id`;
- кнопка удаления ошибочно добавленной записи;
- системная категория `Алкоголь` для покупок выпивки;
- системная категория `Переводы` для семейных внутренних переводов;
- пользовательские категории через кнопки в Telegram;
- отложенные списания, которые автоматически фиксируются в будущую дату;
- голосовые напоминания с разовыми и регулярными событиями;
- команда `/calendar` для просмотра будущих событий на 2 месяца;
- графические отчеты по расходам и доходам за последние 30 дней;
- автоматический ежемесячный пакет отчетов каждое 1-е число: диаграмма расходов, диаграмма доходов и CSV.gz со всеми записями за прошлый календарный месяц;
- настраиваемое приветствие и кнопочное меню Telegram;
- временные аудиофайлы удаляются после обработки;
- Docker Compose deployment.

## Commands

- `/start` — приветствие и меню.
- `/menu` — показать кнопки меню.
- `/calendar` — календарь будущих событий на 2 месяца.
- `/categories` — категории и управление своими категориями.
- `/report` — графические отчеты расходов и доходов за последние 30 дней.

Кнопочное меню дублирует основные действия: календарь, категории, добавление и
удаление пользовательских категорий, а также графические отчеты по расходам и
доходам за последние 30 дней.

<details>
<summary>System Categories</summary>

Расходы:

- Продукты
- Алкоголь
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

## Reports

- `/report` и кнопка `Отчет за 30 дней` отправляют две PNG-круговые диаграммы по категориям за последние 30 дней: отдельно расходы и отдельно доходы.
- Каждое 1-е число бот автоматически отправляет пользователям отчетный пакет за прошедший календарный месяц: PNG-диаграмму расходов, PNG-диаграмму доходов и CSV.gz со всеми записями периода. В CSV входят дата, тип операции, сумма, валюта, код и название категории, описание, полная расшифровка сообщения и служебные поля обработки.

## Bot Assets

- `assets/bot-icon.png` is the source icon for the Telegram bot avatar.
- `assets/readme-description.png` is the README overview image.

## Install On VPS

Поддерживаемый быстрый сценарий — чистый Ubuntu/Debian VPS, SSH под `root`.
Установщик проверит окружение, поставит недостающие `curl`, `git`, Docker и
Docker Compose, запросит токены, создаст `.env`, соберет контейнер и включит
автозапуск через `restart: unless-stopped`.

Одна строка установки:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Alex-zWitCh/voice-budget-bot/master/scripts/install.sh)"
```

Что понадобится в процессе:

- Telegram bot token — создается через Telegram-бота `@BotFather`;
- STT API key — ключ локального OpenAI-compatible шлюза распознавания речи (`https://stt.example.com:7443/v1`);
- DeepSeek API key — используется для извлечения суммы, типа операции, категории и будущих событий;
- Groq API key — опционально, резервный STT-канал (если локальный шлюз недоступен);
- `ALLOWED_CHAT_IDS` — опционально, список разрешенных чатов через запятую;
- `ALLOWED_USER_IDS` — опционально, список разрешенных пользователей через запятую.

По умолчанию бот ставится в `/opt/voice-budget-bot`.

После установки:

```bash
cd /opt/voice-budget-bot
docker compose ps
docker logs -f voice-budget-bot
```

Если на сервере доступен только старый `docker-compose`, используйте его вместо
`docker compose`.

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
Ссылка на автора форка всегда добавляется отдельно и не зависит от этих
настроек.

## Configuration

Copy `.env.example` to `.env` and fill secrets outside Git:

```dotenv
BOT_TOKEN=
STT_API_KEY=
DEEPSEEK_API_KEY=
GROQ_FALLBACK_ENABLED=false
GROQ_API_KEY=
ALLOWED_CHAT_IDS=
ALLOWED_USER_IDS=
```

When `ALLOWED_USER_IDS` is empty, any Telegram user may use the bot in private
chat. Fill it later with comma-separated Telegram user IDs to restrict access.
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

Audio is sent to the primary STT service — a local OpenAI-compatible gateway
(`https://stt.example.com:7443/v1`, model `Systran/faster-whisper-large-v3`).
If optional Groq fallback is enabled and the primary STT returns an error or an
empty transcript, the same audio is sent to Groq. Voice transcripts and direct
text messages are sent to DeepSeek for structured extraction. API keys are not
written to logs.

## Диагностические логи

Для тестовой диагностики задайте `LOG_LEVEL=DEBUG`. Лог приложения хранится в
`/data/logs/voice-budget-bot.log`; каждый файл ограничен 2 МиБ, сохраняются две предыдущие
ротации. Docker stdout также ограничен тремя файлами по 2 МиБ:

```dotenv
LOG_FILE=/data/logs/voice-budget-bot.log
LOG_MAX_BYTES=2097152
LOG_BACKUP_COUNT=2
```

Для эксплуатации используйте Docker Compose v2 (`docker compose`). Устаревший
`docker-compose` 1.x может не суметь пересоздать контейнер из современного образа.
