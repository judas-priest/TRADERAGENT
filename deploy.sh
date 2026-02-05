#!/bin/bash
# TRADERAGENT Bot Deployment Script

set -e  # Exit on error

echo "🚀 TRADERAGENT Bot Deployment"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    log_info "Prerequisites check passed ✓"
}

# Check environment file
check_env_file() {
    log_info "Checking environment configuration..."

    if [ ! -f .env ]; then
        log_warn ".env file not found"
        if [ -f .env.example ]; then
            log_info "Creating .env from .env.example"
            cp .env.example .env
            log_warn "Please edit .env file with your configuration before proceeding"
            exit 1
        else
            log_error ".env.example not found. Cannot create .env file"
            exit 1
        fi
    fi

    # Check for required variables
    source .env

    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" == "your_telegram_bot_token_here" ]; then
        log_error "TELEGRAM_BOT_TOKEN is not configured in .env"
        exit 1
    fi

    if [ -z "$ENCRYPTION_KEY" ] || [ "$ENCRYPTION_KEY" == "REPLACE_WITH_BASE64_ENCODED_32_BYTE_KEY" ]; then
        log_error "ENCRYPTION_KEY is not configured in .env"
        log_info "Generate one with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        exit 1
    fi

    log_info "Environment configuration check passed ✓"
}

# Check config file
check_config_file() {
    log_info "Checking bot configuration..."

    CONFIG_FILE=${CONFIG_FILE:-production.yaml}

    if [ ! -f "configs/$CONFIG_FILE" ]; then
        log_warn "Config file configs/$CONFIG_FILE not found"
        if [ -f "configs/example.yaml" ]; then
            log_info "Creating $CONFIG_FILE from example.yaml"
            cp configs/example.yaml "configs/$CONFIG_FILE"
            log_warn "Please edit configs/$CONFIG_FILE before proceeding"
            exit 1
        else
            log_error "configs/example.yaml not found. Cannot create config file"
            exit 1
        fi
    fi

    log_info "Bot configuration check passed ✓"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    docker-compose build
    log_info "Docker images built successfully ✓"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    docker-compose run --rm migrations
    log_info "Database migrations completed ✓"
}

# Start services
start_services() {
    log_info "Starting services..."
    docker-compose up -d postgres redis

    log_info "Waiting for services to be healthy..."
    sleep 5

    # Check if services are running
    if ! docker-compose ps | grep -q "postgres.*Up"; then
        log_error "PostgreSQL failed to start"
        docker-compose logs postgres
        exit 1
    fi

    if ! docker-compose ps | grep -q "redis.*Up"; then
        log_error "Redis failed to start"
        docker-compose logs redis
        exit 1
    fi

    log_info "Services started successfully ✓"
}

# Start bot
start_bot() {
    log_info "Starting trading bot..."
    docker-compose up -d bot

    log_info "Waiting for bot to start..."
    sleep 3

    if ! docker-compose ps | grep -q "bot.*Up"; then
        log_error "Bot failed to start"
        docker-compose logs bot
        exit 1
    fi

    log_info "Trading bot started successfully ✓"
}

# Show status
show_status() {
    echo ""
    log_info "Deployment Status:"
    docker-compose ps

    echo ""
    log_info "Recent bot logs:"
    docker-compose logs --tail=20 bot

    echo ""
    log_info "To view live logs, run:"
    echo "  docker-compose logs -f bot"

    echo ""
    log_info "To stop the bot, run:"
    echo "  docker-compose down"

    echo ""
    log_info "Deployment completed successfully! 🎉"
}

# Main deployment flow
main() {
    check_prerequisites
    check_env_file
    check_config_file
    build_images
    start_services
    run_migrations
    start_bot
    show_status
}

# Run main function
main "$@"
