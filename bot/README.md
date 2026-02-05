# TRADERAGENT Bot - Autonomous Trading System

Autonomous DCA-Grid trading bot for cryptocurrency exchanges.

## 🎯 Features

- **Multi-Strategy Support**: Grid Trading, DCA (Dollar Cost Averaging), and Hybrid strategies
- **Exchange Integration**: CCXT-based integration with major exchanges (Binance, Bybit, OKX)
- **Risk Management**: Configurable stop-loss, position limits, and safety checks
- **Database Persistence**: PostgreSQL with async operations
- **Configuration Management**: YAML configs with hot reload and validation
- **Structured Logging**: Comprehensive logging with rotation
- **WebSocket Support**: Real-time price and order updates

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

## ⚙️ Configuration

1. **Create configuration file**:
```bash
cp configs/example.yaml configs/production.yaml
```

2. **Generate encryption key**:
```python
import os, base64
print(base64.b64encode(os.urandom(32)).decode())
```

3. **Configure database**:
```bash
# Copy alembic config
cp alembic.ini.example alembic.ini

# Edit database URL in alembic.ini and configs/production.yaml
```

4. **Apply database migrations**:
```bash
alembic upgrade head
```

## 🚀 Usage

### Basic Usage

```python
import asyncio
from pathlib import Path
from bot.config import ConfigManager
from bot.database import DatabaseManager
from bot.utils.logger import setup_logging

async def main():
    # Setup logging
    setup_logging(log_level="INFO")

    # Load configuration
    config_manager = ConfigManager(Path("configs/production.yaml"))
    config = config_manager.load()

    # Initialize database
    db_manager = DatabaseManager(config.database_url)
    await db_manager.initialize()

    # Your bot logic here

    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Configuration Example

```yaml
database_url: postgresql+asyncpg://user:pass@localhost/traderagent
log_level: INFO
encryption_key: <your_base64_key>

bots:
  - name: btc_grid_bot
    symbol: BTC/USDT
    strategy: grid

    exchange:
      exchange_id: binance
      credentials_name: binance_main
      sandbox: false

    grid:
      upper_price: "50000"
      lower_price: "40000"
      grid_levels: 10
      amount_per_grid: "100"
      profit_per_grid: "0.01"

    risk_management:
      max_position_size: "10000"
      stop_loss_percentage: "0.15"

    dry_run: false
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bot --cov-report=html

# Run specific test file
pytest bot/tests/unit/test_config_manager.py

# Run with verbose output
pytest -v
```

## 📊 Project Structure

```
bot/
├── api/                  # Exchange API clients
│   ├── exchange_client.py
│   └── exceptions.py
├── config/               # Configuration management
│   ├── manager.py
│   └── schemas.py
├── core/                 # Trading strategies (future)
├── database/             # Database management
│   ├── manager.py
│   └── models.py
├── utils/                # Utilities
│   └── logger.py
└── tests/                # Tests
    ├── unit/
    └── integration/
```

## 🔧 Development

### Code Quality

```bash
# Format code
black bot/

# Lint code
ruff check bot/

# Type check
mypy bot/

# Run pre-commit hooks
pre-commit run --all-files
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## 📝 Configuration Schemas

### Strategy Types
- `grid`: Grid trading strategy
- `dca`: Dollar Cost Averaging strategy
- `hybrid`: Combined grid + DCA strategy

### Grid Configuration
- `upper_price`: Upper boundary for grid
- `lower_price`: Lower boundary for grid
- `grid_levels`: Number of grid levels (2-100)
- `amount_per_grid`: Amount per grid level
- `profit_per_grid`: Profit percentage per level

### DCA Configuration
- `trigger_percentage`: Price drop to trigger DCA
- `amount_per_step`: Amount per DCA step
- `max_steps`: Maximum DCA steps (1-20)
- `take_profit_percentage`: Take profit after DCA

### Risk Management
- `max_position_size`: Maximum total position
- `stop_loss_percentage`: Stop loss percentage
- `max_daily_loss`: Maximum daily loss
- `min_order_size`: Minimum order size

## 🔒 Security

- API keys are encrypted using AES-256
- Encryption key stored in environment variables
- Sensitive data never logged
- Database credentials secured
- Testnet/sandbox mode for testing

## 📚 Documentation

- [Configuration Guide](../configs/example.yaml)
- [Database Schema](database/models.py)
- [API Documentation](api/exchange_client.py)
- [Main Project README](../README.md)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Run tests and linters
4. Commit your changes
5. Push to the branch
6. Create a Pull Request

## 📄 License

Mozilla Public License 2.0

## ⚠️ Disclaimer

This bot is for educational purposes. Use at your own risk. Always test with small amounts first and use testnet/sandbox mode for initial testing.
