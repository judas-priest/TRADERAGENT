#!/bin/bash
# TRADERAGENT Deployment Verification Script
# Проверка корректности развертывания бота

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

# Main verification
main() {
    clear
    print_header "TRADERAGENT Deployment Verification"
    echo -e "${BLUE}Checking deployment status...${NC}"
    echo ""

    # Check 1: Docker
    print_header "1. Docker Installation"
    print_test "Checking Docker..."
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d ' ' -f3 | sed 's/,//')
        print_pass "Docker installed: $DOCKER_VERSION"
    else
        print_fail "Docker is not installed"
        echo -e "${RED}Please install Docker: https://docs.docker.com/get-docker/${NC}"
        exit 1
    fi

    print_test "Checking Docker Compose..."
    if docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version | cut -d ' ' -f4)
        print_pass "Docker Compose installed: $COMPOSE_VERSION"
    else
        print_fail "Docker Compose is not installed"
        echo -e "${RED}Please install Docker Compose plugin${NC}"
        exit 1
    fi

    print_test "Checking Docker daemon..."
    if docker info &> /dev/null; then
        print_pass "Docker daemon is running"
    else
        print_fail "Docker daemon is not running"
        echo -e "${RED}Start Docker: sudo systemctl start docker${NC}"
        exit 1
    fi

    # Check 2: Project files
    print_header "2. Project Files"

    print_test "Checking .env file..."
    if [ -f ".env" ]; then
        print_pass ".env file exists"

        # Check required variables
        source .env

        if [ ! -z "$TELEGRAM_BOT_TOKEN" ] && [ "$TELEGRAM_BOT_TOKEN" != "your_telegram_bot_token_here" ]; then
            print_pass "TELEGRAM_BOT_TOKEN is configured"
        else
            print_fail "TELEGRAM_BOT_TOKEN is not configured"
        fi

        if [ ! -z "$ENCRYPTION_KEY" ] && [ "$ENCRYPTION_KEY" != "REPLACE_WITH_BASE64_ENCODED_32_BYTE_KEY" ]; then
            print_pass "ENCRYPTION_KEY is configured"
        else
            print_fail "ENCRYPTION_KEY is not configured"
        fi

        if [ ! -z "$DB_PASSWORD" ] && [ "$DB_PASSWORD" != "changeme_secure_password" ]; then
            print_pass "DB_PASSWORD is configured"
        else
            print_warn "DB_PASSWORD is using default value (change recommended)"
        fi
    else
        print_fail ".env file not found"
        echo -e "${RED}Create .env from .env.example: cp .env.example .env${NC}"
    fi

    print_test "Checking bot configuration..."
    CONFIG_FILE=${CONFIG_FILE:-production.yaml}
    if [ -f "configs/$CONFIG_FILE" ]; then
        print_pass "Config file exists: configs/$CONFIG_FILE"
    else
        print_fail "Config file not found: configs/$CONFIG_FILE"
        echo -e "${RED}Create config: cp configs/example.yaml configs/$CONFIG_FILE${NC}"
    fi

    print_test "Checking docker-compose.yml..."
    if [ -f "docker-compose.yml" ]; then
        print_pass "docker-compose.yml exists"
    else
        print_fail "docker-compose.yml not found"
    fi

    # Check 3: Docker containers
    print_header "3. Docker Containers"

    print_test "Checking containers status..."
    if docker-compose ps &> /dev/null; then
        # Check postgres
        if docker-compose ps postgres | grep -q "Up"; then
            print_pass "PostgreSQL container is running"
        else
            print_fail "PostgreSQL container is not running"
        fi

        # Check redis
        if docker-compose ps redis | grep -q "Up"; then
            print_pass "Redis container is running"
        else
            print_fail "Redis container is not running"
        fi

        # Check bot
        if docker-compose ps bot | grep -q "Up"; then
            print_pass "Bot container is running"
        else
            print_warn "Bot container is not running (may need to be started manually)"
        fi
    else
        print_warn "Docker Compose services not started yet"
        print_info "Run: ./deploy.sh to start services"
    fi

    # Check 4: Database connectivity
    print_header "4. Database Connectivity"

    print_test "Checking PostgreSQL connection..."
    if docker-compose ps postgres | grep -q "Up"; then
        if docker-compose exec -T postgres pg_isready -U traderagent &> /dev/null; then
            print_pass "PostgreSQL is accepting connections"
        else
            print_fail "PostgreSQL is not accepting connections"
        fi

        # Check database exists
        if docker-compose exec -T postgres psql -U traderagent -lqt | cut -d \| -f 1 | grep -qw traderagent; then
            print_pass "Database 'traderagent' exists"
        else
            print_fail "Database 'traderagent' does not exist"
            print_info "Run migrations: docker-compose run --rm migrations"
        fi
    else
        print_warn "PostgreSQL container not running, skipping database checks"
    fi

    print_test "Checking Redis connection..."
    if docker-compose ps redis | grep -q "Up"; then
        if docker-compose exec -T redis redis-cli ping &> /dev/null; then
            print_pass "Redis is responding"
        else
            print_fail "Redis is not responding"
        fi
    else
        print_warn "Redis container not running"
    fi

    # Check 5: Bot logs
    print_header "5. Bot Logs Analysis"

    if docker-compose ps bot | grep -q "Up"; then
        print_test "Checking bot logs for errors..."
        ERROR_COUNT=$(docker-compose logs bot 2>&1 | grep -i "error" | grep -v "ERROR" | wc -l)

        if [ $ERROR_COUNT -eq 0 ]; then
            print_pass "No errors found in bot logs"
        else
            print_warn "Found $ERROR_COUNT error(s) in bot logs"
            print_info "Check logs: docker-compose logs bot | grep -i error"
        fi

        print_test "Checking for critical issues..."
        if docker-compose logs bot 2>&1 | grep -qi "critical"; then
            print_fail "Critical issues found in logs"
            print_info "Check logs: docker-compose logs bot | grep -i critical"
        else
            print_pass "No critical issues found"
        fi

        # Check for successful initialization
        if docker-compose logs bot 2>&1 | grep -q "Bot Orchestrator initialized"; then
            print_pass "Bot Orchestrator initialized successfully"
        else
            print_warn "Bot Orchestrator initialization not confirmed in logs"
        fi

        if docker-compose logs bot 2>&1 | grep -q "Telegram bot started"; then
            print_pass "Telegram bot started successfully"
        else
            print_warn "Telegram bot start not confirmed in logs"
        fi
    else
        print_warn "Bot container not running, skipping log checks"
    fi

    # Check 6: System resources
    print_header "6. System Resources"

    print_test "Checking disk space..."
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $DISK_USAGE -lt 80 ]; then
        print_pass "Disk usage: ${DISK_USAGE}% (OK)"
    elif [ $DISK_USAGE -lt 90 ]; then
        print_warn "Disk usage: ${DISK_USAGE}% (getting full)"
    else
        print_fail "Disk usage: ${DISK_USAGE}% (critically low space)"
    fi

    print_test "Checking memory..."
    if command -v free &> /dev/null; then
        MEMORY_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
        if [ $MEMORY_USAGE -lt 80 ]; then
            print_pass "Memory usage: ${MEMORY_USAGE}% (OK)"
        elif [ $MEMORY_USAGE -lt 90 ]; then
            print_warn "Memory usage: ${MEMORY_USAGE}% (high)"
        else
            print_fail "Memory usage: ${MEMORY_USAGE}% (critically high)"
        fi
    else
        print_info "Memory check skipped (free command not available)"
    fi

    # Check 7: Network connectivity
    print_header "7. Network Connectivity"

    print_test "Checking internet connection..."
    if ping -c 1 8.8.8.8 &> /dev/null; then
        print_pass "Internet connection is working"
    else
        print_fail "No internet connection"
    fi

    print_test "Checking GitHub connectivity..."
    if curl -s --head https://github.com | head -n 1 | grep "200" &> /dev/null; then
        print_pass "GitHub is accessible"
    else
        print_warn "GitHub is not accessible (may affect updates)"
    fi

    print_test "Checking Telegram API..."
    if curl -s --head https://api.telegram.org | head -n 1 | grep "200" &> /dev/null; then
        print_pass "Telegram API is accessible"
    else
        print_warn "Telegram API is not accessible"
    fi

    # Summary
    print_header "Verification Summary"

    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""

    if [ $FAILED -eq 0 ]; then
        if [ $WARNINGS -eq 0 ]; then
            echo -e "${GREEN}✓ Deployment verification PASSED!${NC}"
            echo -e "${GREEN}Your bot is ready to use.${NC}"
            echo ""
            echo -e "${BLUE}Next steps:${NC}"
            echo "1. Add API credentials via Telegram: /add_credentials"
            echo "2. Start your bot: /start_bot <bot_name>"
            echo "3. Check status: /status <bot_name>"
            exit 0
        else
            echo -e "${YELLOW}⚠ Deployment verification PASSED with warnings${NC}"
            echo -e "${YELLOW}Review the warnings above and fix if necessary.${NC}"
            exit 0
        fi
    else
        echo -e "${RED}✗ Deployment verification FAILED${NC}"
        echo -e "${RED}Please fix the issues above before proceeding.${NC}"
        echo ""
        echo -e "${BLUE}For help, see:${NC}"
        echo "- DEPLOYMENT_GUIDE_RU.md"
        echo "- TROUBLESHOOTING.md"
        echo "- https://github.com/alekseymavai/TRADERAGENT/issues"
        exit 1
    fi
}

# Run main function
main "$@"
