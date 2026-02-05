# TRADERAGENT Testing Guide

Comprehensive testing documentation for Stage 4: Testing and Deployment.

## Table of Contents

1. [Unit Testing](#unit-testing)
2. [Integration Testing](#integration-testing)
3. [Backtesting](#backtesting)
4. [Testnet Testing](#testnet-testing)
5. [Deployment Testing](#deployment-testing)
6. [Continuous Integration](#continuous-integration)

---

## Unit Testing

### Overview

Unit tests verify individual components in isolation. The project uses `pytest` with async support.

### Running Unit Tests

```bash
# Run all unit tests
pytest bot/tests/unit/ -v

# Run specific test file
pytest bot/tests/unit/test_grid_engine.py -v

# Run with coverage
pytest bot/tests/unit/ --cov=bot --cov-report=html

# Run tests matching pattern
pytest bot/tests/unit/ -k "test_grid" -v
```

### Coverage Requirements

- **Target**: >80% code coverage
- **Current Coverage**: Check with `pytest --cov=bot --cov-report=term-missing`

### Test Structure

```
bot/tests/
├── unit/
│   ├── test_grid_engine.py        # Grid strategy tests
│   ├── test_dca_engine.py         # DCA strategy tests
│   ├── test_risk_manager.py       # Risk management tests
│   ├── test_bot_orchestrator.py   # Orchestration tests
│   ├── test_config_manager.py     # Configuration tests
│   ├── test_database_manager.py   # Database tests
│   └── ...
├── integration/
│   ├── test_module_integration.py # Module integration tests
│   └── test_orchestration.py      # Full system tests
├── backtesting/
│   ├── market_simulator.py        # Market simulator
│   ├── backtesting_engine.py      # Backtesting engine
│   ├── test_data.py                # Test data provider
│   └── test_backtesting.py         # Backtesting tests
└── testnet/
    ├── test_exchange_connection.py # Exchange API tests
    └── README.md                    # Testnet testing guide
```

### Writing Unit Tests

Example unit test:

```python
import pytest
from decimal import Decimal
from bot.core.grid_engine import GridEngine

class TestGridEngine:
    @pytest.fixture
    def grid_config(self):
        return {
            "upper_price": Decimal("50000"),
            "lower_price": Decimal("40000"),
            "grid_levels": 10,
            "amount_per_grid": Decimal("100"),
        }

    @pytest.fixture
    def grid_engine(self, grid_config):
        return GridEngine(grid_config)

    def test_grid_initialization(self, grid_engine):
        """Test grid engine initializes correctly"""
        assert grid_engine.grid_levels == 10
        assert len(grid_engine.grid_prices) == 10

    @pytest.mark.asyncio
    async def test_grid_order_creation(self, grid_engine, mock_exchange):
        """Test grid creates orders correctly"""
        await grid_engine.initialize_grid(mock_exchange)
        assert len(mock_exchange.orders) == 10
```

---

## Integration Testing

### Overview

Integration tests verify that multiple components work together correctly.

### Running Integration Tests

```bash
# Run all integration tests
pytest bot/tests/integration/ -v

# Run with markers
pytest -m integration -v

# Run slow tests
pytest -m slow -v
```

### Test Scenarios

1. **Grid + Risk Manager Integration**
   - Grid respects risk limits
   - Stop-loss triggers correctly
   - Position size enforced

2. **DCA + Risk Manager Integration**
   - DCA respects budget limits
   - Max steps enforced
   - Daily loss limits work

3. **Full Trading Cycle**
   - Buy → Sell → Profit calculation
   - Order tracking across modules
   - Event propagation

---

## Backtesting

### Overview

Backtesting tests trading strategies against historical market data using the market simulator.

### Market Simulator

The `MarketSimulator` provides a simulated exchange environment:

```python
from bot.tests.backtesting import MarketSimulator
from decimal import Decimal

# Create simulator
simulator = MarketSimulator(
    symbol="BTC/USDT",
    initial_balance_quote=Decimal("10000"),
    maker_fee=Decimal("0.001"),
    slippage=Decimal("0.0001"),
)

# Set market price
simulator.set_price(Decimal("45000"))

# Create order
order = await simulator.create_order(
    symbol="BTC/USDT",
    order_type="limit",
    side="buy",
    amount=Decimal("0.1"),
    price=Decimal("44000"),
)

# Get balance
balance = simulator.get_balance()
```

### Running Backtests

```python
from bot.tests.backtesting import BacktestingEngine
from datetime import datetime, timedelta
from decimal import Decimal

# Create engine
engine = BacktestingEngine(
    symbol="BTC/USDT",
    initial_balance=Decimal("10000"),
)

# Configure strategy
grid_config = {
    "upper_price": "46000",
    "lower_price": "44000",
    "grid_levels": 10,
    "amount_per_grid": "100",
}

# Run backtest
result = await engine.run_grid_backtest(
    grid_config=grid_config,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)

# Print results
result.print_summary()

# Save results
engine.save_results(result, "backtest_results.json")
```

### Backtest Metrics

- **Performance**: Return %, Sharpe ratio
- **Risk**: Max drawdown, win rate
- **Trading**: Total trades, avg profit/trade
- **Time**: Duration, data points analyzed

### Example Backtest Output

```
======================================================================
Backtest Results: Grid Trading
======================================================================

Symbol: BTC/USDT
Period: 2024-01-01 to 2024-01-31
Duration: 30 days (720.0 hours)

Performance Metrics:
  Initial Balance:  $10,000.00
  Final Balance:    $10,450.00
  Total Return:     $450.00 (4.50%)
  Max Drawdown:     $120.00 (1.20%)

Trading Statistics:
  Total Trades:     45
  Winning Trades:   28
  Losing Trades:    17
  Win Rate:         62.22%
  Buy Orders:       23
  Sell Orders:      22
  Avg Profit/Trade: $10.00

Risk Metrics:
  Sharpe Ratio:     1.2345
======================================================================
```

### Running Backtest Tests

```bash
# Run all backtesting tests
pytest bot/tests/backtesting/ -v

# Run with integration marker
pytest bot/tests/backtesting/ -m integration -v
```

---

## Testnet Testing

### Overview

Testnet testing validates the bot against real exchange APIs using test funds.

### Setup

See [bot/tests/testnet/README.md](bot/tests/testnet/README.md) for detailed setup instructions.

Quick setup:

1. Create testnet account on Binance/Bybit
2. Generate API keys
3. Get test funds from faucet
4. Configure bot for testnet
5. Store testnet credentials

### Running Testnet Tests

```bash
# Run testnet tests (requires credentials)
pytest bot/tests/testnet/ --testnet -v

# Run specific test
pytest bot/tests/testnet/test_exchange_connection.py --testnet -v

# Skip if credentials not available
pytest bot/tests/testnet/ -v  # Will skip automatically
```

### Testnet Test Scenarios

1. **Exchange Connection**
   - API authentication
   - Balance fetching
   - Ticker data retrieval

2. **Order Management**
   - Create limit orders
   - Cancel orders
   - Query order status

3. **Trading Operations**
   - Place test trades
   - Monitor execution
   - Verify balances

4. **Error Handling**
   - Invalid orders
   - Insufficient balance
   - Rate limiting

### Testnet Checklist

- [ ] API connection successful
- [ ] Balance retrieval working
- [ ] Limit orders placed and canceled
- [ ] Market data fetching correctly
- [ ] Grid strategy tested for 1-2 hours
- [ ] DCA strategy tested
- [ ] Risk limits enforced
- [ ] Stop-loss triggers
- [ ] Bot restart recovery
- [ ] Error handling verified

---

## Deployment Testing

### Local Development Deployment

```bash
# Install dependencies
pip install -e .
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start bot in dry-run mode
python -m bot.main --config configs/example.yaml --dry-run
```

### Docker Deployment Testing

```bash
# Build image
docker-compose build

# Run with test configuration
docker-compose up bot

# Check logs
docker-compose logs -f bot

# Stop services
docker-compose down
```

### VPS Deployment Testing

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment guide.

```bash
# On VPS:

# 1. Clone repository
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Deploy
chmod +x deploy.sh
./deploy.sh

# 4. Verify deployment
docker-compose ps
docker-compose logs bot
```

### Deployment Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env` file configured
- [ ] Bot configuration file created
- [ ] Database migrations run
- [ ] All services healthy
- [ ] Bot starts without errors
- [ ] Telegram bot responsive
- [ ] Logs show correct operation
- [ ] Monitoring stack running (optional)

---

## Continuous Integration

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

Hooks will run automatically on commit:
- Code formatting (black)
- Linting (ruff)
- Type checking (mypy)
- YAML validation
- Trailing whitespace removal

### Manual CI Checks

Run all checks manually:

```bash
# Format code
black bot/ --check

# Lint code
ruff check bot/

# Type checking
mypy bot/

# Run tests
pytest bot/tests/ -v

# Check coverage
pytest --cov=bot --cov-report=term-missing
```

### GitHub Actions (Future)

Example CI workflow:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          pip install -e .
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest bot/tests/ --cov=bot

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Test Data Management

### Fixtures

Use pytest fixtures for test data:

```python
@pytest.fixture
def sample_config():
    return {
        "symbol": "BTC/USDT",
        "strategy": "grid",
        # ...
    }

@pytest.fixture
async def mock_exchange():
    from unittest.mock import AsyncMock
    exchange = AsyncMock()
    exchange.fetch_balance.return_value = {"USDT": {"free": 10000}}
    return exchange
```

### Test Database

Tests use SQLite in-memory database:

```python
@pytest.fixture(scope="session")
async def test_db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    # Setup tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
```

---

## Debugging Tests

### Run Tests with Debugging

```bash
# Run with Python debugger
pytest --pdb

# Run with verbose output
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Stop on first failure
pytest -x
```

### Debug in VS Code

Add to `.vscode/launch.json`:

```json
{
  "name": "Pytest Current File",
  "type": "python",
  "request": "launch",
  "module": "pytest",
  "args": [
    "${file}",
    "-v",
    "-s"
  ],
  "console": "integratedTerminal"
}
```

---

## Performance Testing

### Load Testing

Test bot under high load:

```python
@pytest.mark.performance
async def test_high_frequency_trading():
    """Test bot handles many rapid orders"""
    simulator = MarketSimulator()

    # Place 1000 orders rapidly
    for i in range(1000):
        await simulator.create_order(
            symbol="BTC/USDT",
            order_type="limit",
            side="buy" if i % 2 == 0 else "sell",
            amount=Decimal("0.001"),
            price=Decimal("45000"),
        )

    # Verify all orders processed
    assert len(simulator.orders) == 1000
```

### Stress Testing

```bash
# Run performance tests
pytest -m performance -v

# Profile test execution
pytest --profile
```

---

## Best Practices

1. **Write Tests First** (TDD)
   - Define expected behavior
   - Write failing test
   - Implement feature
   - Verify test passes

2. **Test Edge Cases**
   - Zero values
   - Negative values
   - Very large values
   - Empty inputs
   - None/null values

3. **Use Descriptive Names**
   ```python
   # Good
   def test_grid_respects_stop_loss_when_price_drops_below_threshold():
       pass

   # Bad
   def test_grid_1():
       pass
   ```

4. **Arrange-Act-Assert Pattern**
   ```python
   def test_example():
       # Arrange: Setup test data
       config = {"upper_price": "50000"}

       # Act: Execute action
       engine = GridEngine(config)

       # Assert: Verify result
       assert engine.upper_price == Decimal("50000")
   ```

5. **Mock External Dependencies**
   - Don't call real exchange APIs in unit tests
   - Use simulators for integration tests
   - Use testnet for real API testing

6. **Keep Tests Fast**
   - Unit tests should run in milliseconds
   - Use markers for slow tests
   - Run slow tests separately

7. **Maintain Test Coverage**
   - Aim for >80% coverage
   - Focus on critical paths
   - Don't test external libraries

---

## Troubleshooting

### Tests Failing Locally

1. **Check Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Clear Cache**
   ```bash
   pytest --cache-clear
   ```

3. **Check Database**
   ```bash
   # Reset test database
   rm -f test.db
   alembic upgrade head
   ```

### Async Test Errors

Ensure pytest-asyncio is installed:
```bash
pip install pytest-asyncio
```

Add to pytest.ini:
```ini
[pytest]
asyncio_mode = auto
```

### Import Errors

Ensure package is installed:
```bash
pip install -e .
```

---

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [CCXT Documentation](https://docs.ccxt.com/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
