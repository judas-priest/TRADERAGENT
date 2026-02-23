#!/usr/bin/env bash
# =============================================================================
# deploy_backtest.sh — Multi-TF Backtester: деплой на новый сервер
#
# Использование:
#   bash deploy_backtest.sh [директория установки]
#
# Пример:
#   bash deploy_backtest.sh                    # установка в ~/TRADERAGENT
#   bash deploy_backtest.sh /opt/backtest      # кастомная директория
# =============================================================================

set -euo pipefail

# ── Цвета ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Константы ──────────────────────────────────────────────────────────────
PROD_USER="ai-agent"
PROD_HOST="185.233.200.13"
PROD_SERVER="${PROD_USER}@${PROD_HOST}"
PROD_DATA_PATH="/home/ai-agent/TRADERAGENT/data/historical/"
REPO_URL="https://github.com/alekseymavai/TRADERAGENT.git"
INSTALL_DIR="${1:-$HOME/TRADERAGENT}"
REQUIRED_DISK_GB=10   # минимум: 5.4 GB данные + ~1.5 GB venv + запас
MIN_PYTHON="3.10"

# ── Вспомогательные функции ────────────────────────────────────────────────
log()     { echo -e "${GREEN}[✓]${NC} $*"; }
info()    { echo -e "${BLUE}[→]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }
step()    { echo -e "\n${BOLD}${BLUE}── Шаг $* ${NC}"; }
die()     { error "$*"; exit 1; }
confirm() {
    echo -e "${YELLOW}$* [y/N]:${NC} \c"
    read -r ans
    [[ "$ans" =~ ^[Yy]$ ]]
}

# ── Баннер ─────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat <<'EOF'
╔══════════════════════════════════════════════════════════════╗
║          TRADERAGENT — Multi-TF Backtester Deploy           ║
║          M5 → M15 → H1 → H4 → D1  |  Grid DCA SMC TF       ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
info "Директория установки: ${BOLD}${INSTALL_DIR}${NC}"
info "Источник данных:       ${BOLD}${PROD_SERVER}:${PROD_DATA_PATH}${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
step "1/7 — Проверка системных требований"
# ═══════════════════════════════════════════════════════════════════════════

# OS
OS=$(uname -s)
if [[ "$OS" != "Linux" ]]; then
    die "Скрипт рассчитан на Linux. Обнаружена ОС: $OS"
fi
log "ОС: Linux"

# Свободное место на диске
AVAIL_GB=$(df -BG "${HOME}" | awk 'NR==2 {gsub("G",""); print $4}')
if (( AVAIL_GB < REQUIRED_DISK_GB )); then
    die "Недостаточно места на диске: доступно ${AVAIL_GB} GB, нужно минимум ${REQUIRED_DISK_GB} GB"
fi
log "Диск: ${AVAIL_GB} GB свободно (нужно ≥ ${REQUIRED_DISK_GB} GB)"

# Git
if ! command -v git &>/dev/null; then
    warn "git не найден. Устанавливаю..."
    sudo apt-get update -qq && sudo apt-get install -y -qq git
fi
log "Git: $(git --version)"

# rsync (для переноса данных)
if ! command -v rsync &>/dev/null; then
    warn "rsync не найден. Устанавливаю..."
    sudo apt-get install -y -qq rsync
fi
log "rsync: $(rsync --version | head -1)"

# ═══════════════════════════════════════════════════════════════════════════
step "2/7 — Поиск Python 3.10+"
# ═══════════════════════════════════════════════════════════════════════════

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if (( major >= 3 && minor >= 10 )); then
            PYTHON_BIN="$candidate"
            log "Python: $PYTHON_BIN ($version)"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    warn "Python 3.10+ не найден. Устанавливаю Python 3.12..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    PYTHON_BIN="python3.12"
    log "Python установлен: $($PYTHON_BIN --version)"
fi

# venv поддержка
if ! "$PYTHON_BIN" -m venv --help &>/dev/null; then
    warn "python3-venv не найден. Устанавливаю..."
    sudo apt-get install -y -qq "python${PYTHON_BIN##python}-venv" || \
    sudo apt-get install -y -qq python3-venv
fi

# ═══════════════════════════════════════════════════════════════════════════
step "3/7 — Клонирование репозитория"
# ═══════════════════════════════════════════════════════════════════════════

if [[ -d "${INSTALL_DIR}/.git" ]]; then
    warn "Репозиторий уже существует в ${INSTALL_DIR}"
    if confirm "Обновить до последней версии (git pull)?"; then
        git -C "${INSTALL_DIR}" pull --ff-only
        log "Репозиторий обновлён"
    else
        info "Пропускаю обновление"
    fi
else
    info "Клонирую ${REPO_URL}..."
    git clone "${REPO_URL}" "${INSTALL_DIR}"
    log "Репозиторий клонирован в ${INSTALL_DIR}"
fi

# ═══════════════════════════════════════════════════════════════════════════
step "4/7 — Виртуальное окружение и зависимости"
# ═══════════════════════════════════════════════════════════════════════════

VENV_DIR="${INSTALL_DIR}/.venv"

if [[ -d "$VENV_DIR" ]]; then
    warn "Виртуальное окружение уже существует: ${VENV_DIR}"
    info "Пропускаю создание venv"
else
    info "Создаю виртуальное окружение..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    log "venv создан: ${VENV_DIR}"
fi

VENV_PYTHON="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

info "Обновляю pip..."
"$VENV_PIP" install --upgrade pip --quiet

info "Устанавливаю зависимости из requirements.txt..."
info "(~2-5 минут в зависимости от скорости сети)"
"$VENV_PIP" install -r "${INSTALL_DIR}/requirements.txt" --quiet
log "Зависимости установлены"

# ═══════════════════════════════════════════════════════════════════════════
step "5/7 — Настройка SSH-ключа для доступа к рабочему серверу"
# ═══════════════════════════════════════════════════════════════════════════

SSH_KEY="${HOME}/.ssh/id_ed25519"

# Создаём директорию .ssh если нет
mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

# Генерируем ключ если нет
if [[ ! -f "$SSH_KEY" ]]; then
    info "SSH-ключ не найден. Генерирую новый ключ..."
    ssh-keygen -t ed25519 -f "$SSH_KEY" -N "" -C "$(whoami)@$(hostname)-backtest"
    log "SSH-ключ создан: ${SSH_KEY}"
else
    log "SSH-ключ уже существует: ${SSH_KEY}"
fi

PUB_KEY=$(cat "${SSH_KEY}.pub")

# Проверяем, работает ли уже SSH-соединение
info "Проверяю SSH-соединение с рабочим сервером..."
if ssh -o BatchMode=yes \
       -o ConnectTimeout=10 \
       -o StrictHostKeyChecking=no \
       "${PROD_SERVER}" "echo ok" &>/dev/null; then
    log "SSH-соединение с ${PROD_SERVER} работает"
else
    echo ""
    echo -e "${YELLOW}┌─────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${YELLOW}│  SSH-ключ нового сервера нужно добавить на рабочий сервер       │${NC}"
    echo -e "${YELLOW}└─────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "${BOLD}Публичный ключ нового сервера:${NC}"
    echo -e "${CYAN}${PUB_KEY}${NC}"
    echo ""
    echo -e "${BOLD}Выполни одну из команд ниже${NC} (с любого сервера с доступом к проду):"
    echo ""
    echo -e "  ${GREEN}# Вариант 1 — через ssh-copy-id (если есть пароль):${NC}"
    echo -e "  ssh-copy-id -i ${SSH_KEY}.pub ${PROD_SERVER}"
    echo ""
    echo -e "  ${GREEN}# Вариант 2 — вручную добавить строку в authorized_keys на проде:${NC}"
    echo -e "  ssh ${PROD_SERVER} \"echo '${PUB_KEY}' >> ~/.ssh/authorized_keys\""
    echo ""
    echo -e "${YELLOW}После добавления ключа нажми Enter для продолжения...${NC}"
    read -r

    # Повторная проверка
    if ! ssh -o BatchMode=yes \
             -o ConnectTimeout=10 \
             -o StrictHostKeyChecking=no \
             "${PROD_SERVER}" "echo ok" &>/dev/null; then
        die "Не удалось подключиться к ${PROD_SERVER}. Проверь что ключ добавлен в authorized_keys."
    fi
    log "SSH-соединение установлено"
fi

# ═══════════════════════════════════════════════════════════════════════════
step "6/7 — Перенос исторических данных с рабочего сервера"
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR="${INSTALL_DIR}/data/historical"
mkdir -p "$DATA_DIR"

# Проверяем сколько файлов уже есть
EXISTING=$(ls "$DATA_DIR" 2>/dev/null | wc -l)

if (( EXISTING >= 450 )); then
    warn "Данные уже присутствуют: ${EXISTING} файлов в ${DATA_DIR}"
    if ! confirm "Синхронизировать заново (только изменённые файлы)?"; then
        info "Пропускаю перенос данных"
        SKIP_TRANSFER=true
    fi
fi

SKIP_TRANSFER="${SKIP_TRANSFER:-false}"

if [[ "$SKIP_TRANSFER" != "true" ]]; then
    # Считаем размер на проде
    info "Проверяю размер данных на рабочем сервере..."
    PROD_SIZE=$(ssh -o BatchMode=yes "${PROD_SERVER}" \
        "du -sh ${PROD_DATA_PATH} 2>/dev/null | cut -f1" || echo "?")
    info "Размер данных на проде: ${BOLD}${PROD_SIZE}B${NC}"
    info "Целевая директория:     ${BOLD}${DATA_DIR}${NC}"
    echo ""
    info "Начинаю передачу через rsync..."
    info "(Прогресс-бар обновляется каждые несколько секунд)"
    echo ""

    rsync \
        --archive \
        --compress \
        --human-readable \
        --progress \
        --stats \
        --partial \
        --timeout=60 \
        -e "ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no" \
        "${PROD_SERVER}:${PROD_DATA_PATH}" \
        "${DATA_DIR}/"

    TRANSFERRED=$(ls "$DATA_DIR" | wc -l)
    log "Перенос завершён: ${TRANSFERRED} файлов в ${DATA_DIR}"
fi

# ═══════════════════════════════════════════════════════════════════════════
step "7/7 — Проверочный запуск"
# ═══════════════════════════════════════════════════════════════════════════

# Создаём папку для отчётов
mkdir -p "${INSTALL_DIR}/docs/backtesting-reports/html"

info "Запускаю тест на синтетических данных (14 дней, BTC/USDT)..."
echo ""

cd "${INSTALL_DIR}"
"${VENV_PYTHON}" scripts/run_multi_strategy_backtest.py \
    --symbol BTC_USDT \
    --days 14 \
    --trend up \
    --balance 10000

echo ""
log "Тест на синтетических данных пройден"

# Проверяем реальные данные
BTC_FILE="${DATA_DIR}/BTCUSDT_5m.csv"
if [[ -f "$BTC_FILE" ]]; then
    info "Запускаю быстрый тест на реальных данных (BTC/USDT 5m, SMC)..."
    echo ""
    "${VENV_PYTHON}" scripts/run_multi_strategy_backtest.py \
        --csv "$BTC_FILE" \
        --timeframe 5m \
        --balance 10000 \
        --strategy smc
    echo ""
    log "Тест на реальных данных пройден"
else
    warn "Файл ${BTC_FILE} не найден — пропускаю тест на реальных данных"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Итог
# ═══════════════════════════════════════════════════════════════════════════

REPORT_DIR="${INSTALL_DIR}/docs/backtesting-reports/html"
REPORT_COUNT=$(ls "$REPORT_DIR"/*.html 2>/dev/null | wc -l)

echo ""
echo -e "${BOLD}${GREEN}"
cat <<'EOF'
╔══════════════════════════════════════════════════════════════╗
║               Деплой успешно завершён!                      ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${BOLD}Директория установки:${NC}  ${INSTALL_DIR}"
echo -e "${BOLD}Виртуальное окружение:${NC} ${VENV_DIR}"
echo -e "${BOLD}Исторические данные:${NC}   ${DATA_DIR} ($(ls "$DATA_DIR" 2>/dev/null | wc -l) файлов)"
echo -e "${BOLD}HTML-отчёты:${NC}           ${REPORT_DIR} (${REPORT_COUNT} шт)"

echo ""
echo -e "${BOLD}${CYAN}Примеры запуска:${NC}"
echo ""
echo -e "  ${GREEN}# Активировать окружение:${NC}"
echo -e "  source ${VENV_DIR}/bin/activate"
echo ""
echo -e "  ${GREEN}# Все 4 стратегии на реальных данных:${NC}"
echo -e "  python scripts/run_multi_strategy_backtest.py \\"
echo -e "      --csv data/historical/ETHUSDT_5m.csv --timeframe 5m --balance 10000"
echo ""
echo -e "  ${GREEN}# Одна стратегия (SMC) на BTC:${NC}"
echo -e "  python scripts/run_multi_strategy_backtest.py \\"
echo -e "      --csv data/historical/BTCUSDT_5m.csv --timeframe 5m --strategy smc"
echo ""
echo -e "  ${GREEN}# Синтетика, нисходящий тренд:${NC}"
echo -e "  python scripts/run_multi_strategy_backtest.py \\"
echo -e "      --symbol SOL_USDT --days 30 --trend down --balance 5000"
echo ""
echo -e "  ${GREEN}# Запуск тестов (163 теста бэктестера):${NC}"
echo -e "  pytest bot/tests/backtesting/ -v"
echo ""
