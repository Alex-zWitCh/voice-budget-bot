#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="voice-budget-bot"
DEFAULT_APP_DIR="/opt/voice-budget-bot"
DEFAULT_REPO_URL="https://github.com/Alex-zWitCh/voice-budget-bot.git"
DEFAULT_BRANCH="master"

APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
REPO_URL="${REPO_URL:-$DEFAULT_REPO_URL}"
BRANCH="${BRANCH:-$DEFAULT_BRANCH}"
DRY_RUN=0

info() {
  printf '\033[1;34m==>\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m!!\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<USAGE
SmartExpense 2.0 / Voice Budget Bot installer

Usage:
  bash scripts/install.sh [--dry-run] [--help]

Environment overrides:
  APP_DIR=/opt/voice-budget-bot
  REPO_URL=https://github.com/Alex-zWitCh/voice-budget-bot.git
  BRANCH=master
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

need_tty() {
  [[ -r /dev/tty ]] || fail "Интерактивная установка требует TTY. Запустите скрипт из обычной SSH-сессии под root."
}

prompt() {
  local var_name="$1"
  local text="$2"
  local default_value="${3:-}"
  local secret="${4:-0}"
  local value
  if [[ "$secret" == "1" ]]; then
    printf '%s' "$text" > /dev/tty
    IFS= read -r -s value < /dev/tty
    printf '\n' > /dev/tty
  else
    if [[ -n "$default_value" ]]; then
      printf '%s [%s]: ' "$text" "$default_value" > /dev/tty
    else
      printf '%s: ' "$text" > /dev/tty
    fi
    IFS= read -r value < /dev/tty
  fi
  if [[ -z "$value" ]]; then
    value="$default_value"
  fi
  printf -v "$var_name" '%s' "$value"
}

confirm() {
  local text="$1"
  local default_value="${2:-y}"
  local answer
  prompt answer "$text" "$default_value" 0
  case "${answer,,}" in
    y|yes|д|да) return 0 ;;
    *) return 1 ;;
  esac
}

detect_os() {
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt"
  elif command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="dnf"
  elif command -v yum >/dev/null 2>&1; then
    PKG_MANAGER="yum"
  elif [[ "$DRY_RUN" == "1" ]]; then
    PKG_MANAGER="dry-run"
    info "DRY_RUN: пакетный менеджер не требуется"
  else
    fail "Не найден apt-get, dnf или yum. Установите Docker, git и curl вручную, затем повторите."
  fi
}

install_packages() {
  info "Проверяю системные зависимости"
  local missing=()
  command -v curl >/dev/null 2>&1 || missing+=("curl")
  command -v git >/dev/null 2>&1 || missing+=("git")
  command -v docker >/dev/null 2>&1 || missing+=("docker")

  if [[ "${#missing[@]}" -eq 0 ]]; then
    info "curl, git и Docker уже доступны"
    return
  fi

  info "Будут установлены недостающие пакеты: ${missing[*]}"
  case "$PKG_MANAGER" in
    apt)
      run apt-get update
      run apt-get install -y ca-certificates curl git docker.io
      run apt-get install -y docker-compose-plugin || run apt-get install -y docker-compose
      ;;
    dnf)
      run dnf install -y ca-certificates curl git docker docker-compose-plugin
      ;;
    yum)
      run yum install -y ca-certificates curl git docker
      ;;
    dry-run)
      run install ca-certificates curl git docker docker-compose-plugin
      ;;
  esac
}

ensure_docker() {
  if [[ "$DRY_RUN" == "1" ]]; then
    info "DRY_RUN: пропускаю проверку Docker daemon"
    return
  fi
  command -v docker >/dev/null 2>&1 || fail "Docker не установлен."
  if command -v systemctl >/dev/null 2>&1; then
    run systemctl enable --now docker
  else
    warn "systemctl недоступен: убедитесь, что Docker daemon запущен."
  fi
}

detect_compose() {
  if [[ "$DRY_RUN" == "1" ]]; then
    COMPOSE_CMD=("docker" "compose")
    info "DRY_RUN: использую команду проверки docker compose"
    return
  fi
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("docker" "compose")
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=("docker-compose")
  else
    fail "Docker Compose не найден. Установите docker-compose-plugin или docker-compose."
  fi
}

prepare_source() {
  info "Готовлю каталог приложения: $APP_DIR"
  if [[ -d "$APP_DIR/.git" ]]; then
    info "Найден существующий репозиторий, обновляю его"
    run git -C "$APP_DIR" fetch --tags origin
    run git -C "$APP_DIR" checkout "$BRANCH"
    run git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
  elif [[ -e "$APP_DIR" && -n "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]]; then
    fail "Каталог $APP_DIR существует и не пустой, но это не git-репозиторий. Укажите другой APP_DIR или очистите каталог вручную."
  else
    run mkdir -p "$(dirname "$APP_DIR")"
    run git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
  fi
}

explain_tokens() {
  cat > /dev/tty <<'TEXT'

Нужные токены:
- Telegram bot token: создается в Telegram через @BotFather командой /newbot.
- Groq API key: нужен для распознавания голосовых сообщений через Whisper.
- DeepSeek API key: нужен для превращения распознанной фразы в сумму, тип и категорию.

Значения будут сохранены в /opt/voice-budget-bot/.env с правами 600.
TEXT
}

write_env() {
  local env_path="$APP_DIR/.env"
  if [[ "$DRY_RUN" == "1" ]]; then
    info "DRY_RUN: пропускаю интерактивный ввод и запись $env_path"
    return
  fi
  if [[ -f "$env_path" ]]; then
    if confirm "Файл .env уже существует. Оставить его без изменений?" "y"; then
      info "Использую существующий .env"
      return
    fi
  fi

  explain_tokens
  prompt BOT_TOKEN "Telegram bot token" "" 1
  [[ -n "$BOT_TOKEN" ]] || fail "BOT_TOKEN обязателен."
  prompt GROQ_API_KEY "Groq API key" "" 1
  [[ -n "$GROQ_API_KEY" ]] || fail "GROQ_API_KEY обязателен."
  prompt DEEPSEEK_API_KEY "DeepSeek API key" "" 1
  [[ -n "$DEEPSEEK_API_KEY" ]] || fail "DEEPSEEK_API_KEY обязателен."
  prompt ALLOWED_CHAT_IDS "Разрешенные chat_id через запятую. Пусто = личные чаты разрешены, группы игнорируются" "" 0
  prompt ALLOWED_USER_IDS "Разрешенные user_id через запятую. Пусто = без ограничения пользователей" "" 0
  prompt APP_TIMEZONE "Часовой пояс" "Europe/Moscow" 0
  prompt WELCOME_TITLE "Заголовок приветствия" "SmartExpense 2.0" 0
  prompt WELCOME_INTRO "Текст приветствия" "Отправьте короткое голосовое сообщение, чтобы записать доход, расход, напоминание или отложенное списание." 0
  prompt WELCOME_FOOTER "Дополнительная подпись в приветствии, можно оставить пустой" "" 0

  umask 077
  run mkdir -p "$APP_DIR/data"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$env_path"
  else
    cat > "$env_path" <<ENV
BOT_TOKEN=$BOT_TOKEN
ALLOWED_CHAT_IDS=$ALLOWED_CHAT_IDS
ALLOWED_USER_IDS=$ALLOWED_USER_IDS
MAX_VOICE_DURATION_SEC=8

GROQ_API_KEY=$GROQ_API_KEY
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_STT_MODEL=whisper-large-v3
GROQ_TIMEOUT_SEC=30

DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SEC=30
MIN_DEEPSEEK_CONFIDENCE=0.70

REENCODE_VOICE=true
VOICE_SAMPLE_RATE=16000
VOICE_BITRATE=16k
TEMP_AUDIO_DIR=/tmp/voice-budget-bot

DB_TYPE=sqlite
SQLITE_DB_PATH=/data/voice_budget_bot.db

APP_TIMEZONE=$APP_TIMEZONE
LOG_LEVEL=INFO
PROCESSING_VERSION=1.0
MAX_CONCURRENT_PROCESSING=2

WELCOME_TITLE=$WELCOME_TITLE
WELCOME_INTRO=$WELCOME_INTRO
WELCOME_FOOTER=$WELCOME_FOOTER
WELCOME_IMAGE_PATH=assets/readme-description.png
ENV
    chmod 600 "$env_path"
  fi
}

deploy() {
  info "Собираю и запускаю контейнер"
  run mkdir -p "$APP_DIR/data"
  if [[ "$DRY_RUN" != "1" ]]; then
    chown -R 10001:10001 "$APP_DIR/data" 2>/dev/null || true
  fi
  run "${COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yml" --project-directory "$APP_DIR" build
  run "${COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yml" --project-directory "$APP_DIR" up -d --remove-orphans
}

check_installation() {
  info "Проверяю результат установки"
  run "${COMPOSE_CMD[@]}" -f "$APP_DIR/docker-compose.yml" --project-directory "$APP_DIR" ps
  if [[ "$DRY_RUN" == "1" ]]; then
    return
  fi
  local status
  status="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$SERVICE_NAME" 2>/dev/null || true)"
  [[ -n "$status" ]] || fail "Контейнер $SERVICE_NAME не найден."
  printf 'Container status: %s\n' "$status"
  if [[ "$status" != running* ]]; then
    docker logs --tail 80 "$SERVICE_NAME" || true
    fail "Контейнер не запущен."
  fi
}

finish_message() {
  cat <<TEXT

Готово.

Где что лежит:
- код бота: $APP_DIR
- конфиг и токены: $APP_DIR/.env
- база SQLite: $APP_DIR/data/voice_budget_bot.db
- логи: docker logs -f $SERVICE_NAME

Как менять приветствие:
- WELCOME_TITLE — заголовок;
- WELCOME_INTRO — основной текст;
- WELCOME_FOOTER — ваша личная подпись;
- WELCOME_IMAGE_PATH — картинка приветствия.

После изменения .env перезапустите:
  cd $APP_DIR && ${COMPOSE_CMD[*]} up -d

Ссылка на автора форка в приветствии встроена в код и не отключается через конфиг.
TEXT
}

main() {
  if [[ "$DRY_RUN" == "0" ]]; then
    [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "Запустите установку под root."
    need_tty
  fi
  detect_os
  install_packages
  ensure_docker
  detect_compose
  prepare_source
  write_env
  deploy
  check_installation
  finish_message
}

main "$@"
