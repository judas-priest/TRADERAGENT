# Testnet Testing Guide

This directory contains scripts and documentation for testing the TRADERAGENT bot on exchange testnets.

## Supported Testnets

### Binance Testnet
- **Website**: https://testnet.binance.vision/
- **API Documentation**: https://testnet.binance.vision/api-doc.html
- **Features**: Spot trading, futures trading (separate testnet)

### Bybit Testnet
- **Website**: https://testnet.bybit.com/
- **API Documentation**: https://bybit-exchange.github.io/docs/testnet/
- **Features**: Spot and derivatives trading

## Getting Started

### 1. Create Testnet Account

#### Binance Testnet
1. Visit https://testnet.binance.vision/
2. Register for an account
3. Login to your account
4. Generate API keys:
   - Go to API Management
   - Create new API key
   - Save your API Key and Secret Key securely
   - Enable spot trading permissions

#### Bybit Testnet
1. Visit https://testnet.bybit.com/
2. Register using your email
3. Verify your email
4. Go to API Management
5. Create testnet API keys

### 2. Get Test Funds

**Binance Testnet:**
- Login to testnet
- Go to "Wallet" > "Faucet"
- Request test BTC, ETH, USDT, and other assets
- Funds are credited immediately

**Bybit Testnet:**
- Test funds are automatically credited upon account creation
- Additional funds can be requested from support if needed

### 3. Configure Bot for Testnet

Edit your bot configuration file (`configs/testnet.yaml`):

```yaml
database_url: postgresql+asyncpg://user:password@localhost/traderagent_testnet
log_level: DEBUG  # Use DEBUG for testnet testing
encryption_key: your_encryption_key_here

bots:
  - version: 1
    name: testnet_grid_bot
    symbol: BTC/USDT
    strategy: grid

    exchange:
      exchange_id: binance  # or bybit
      credentials_name: binance_testnet
      sandbox: true  # IMPORTANT: Must be true for testnet
      rate_limit: true

    grid:
      enabled: true
      upper_price: "48000"
      lower_price: "42000"
      grid_levels: 10
      amount_per_grid: "50"
      profit_per_grid: "0.01"

    risk_management:
      max_position_size: "5000"
      stop_loss_percentage: "0.15"
      min_order_size: "10"

    notifications:
      enabled: true  # Enable to monitor trades

    dry_run: false  # Set to false to execute real testnet orders
    auto_start: false  # Manual start recommended
```

### 4. Store Testnet Credentials

**Option A: Via Telegram Bot (Recommended)**
```
/add_credentials binance_testnet binance YOUR_API_KEY YOUR_SECRET_KEY --sandbox
```

**Option B: Via Python Script**
```python
python bot/tests/testnet/add_testnet_credentials.py \
    --name binance_testnet \
    --exchange binance \
    --api-key YOUR_API_KEY \
    --secret YOUR_SECRET_KEY \
    --sandbox
```

### 5. Run Testnet Tests

**Automated Test Suite:**
```bash
# Run all testnet tests
pytest bot/tests/testnet/ -v --testnet

# Run specific test
pytest bot/tests/testnet/test_exchange_connection.py -v --testnet

# Run with detailed logging
pytest bot/tests/testnet/ -v --testnet --log-cli-level=DEBUG
```

**Manual Testing:**
```bash
# Start bot in testnet mode
python -m bot.main --config configs/testnet.yaml

# Or use docker-compose with testnet config
docker-compose -f docker-compose.testnet.yml up
```

## Test Scenarios

### Test 1: Exchange Connection
**Objective**: Verify API credentials and connection
**Steps**:
1. Check API connectivity
2. Verify API permissions
3. Test rate limiting
4. Fetch account balance

**Expected Result**: All API calls succeed without errors

### Test 2: Market Data Fetching
**Objective**: Verify market data retrieval
**Steps**:
1. Fetch ticker data
2. Get order book
3. Retrieve historical OHLCV data
4. Test WebSocket connection

**Expected Result**: All data retrieved successfully

### Test 3: Order Placement
**Objective**: Test order creation and management
**Steps**:
1. Place limit buy order
2. Place limit sell order
3. Cancel open orders
4. Query order status
5. Retrieve order history

**Expected Result**: All orders created, queried, and canceled successfully

### Test 4: Grid Strategy
**Objective**: Test grid trading strategy in live testnet
**Steps**:
1. Initialize grid with 5-10 levels
2. Let bot run for 1-2 hours
3. Monitor order execution
4. Verify grid maintenance
5. Check profit calculation

**Expected Result**:
- Grid orders placed correctly
- Orders execute as prices fluctuate
- Grid maintains structure
- No errors or crashes

### Test 5: DCA Strategy
**Objective**: Test DCA averaging strategy
**Steps**:
1. Configure DCA parameters
2. Wait for price drops
3. Verify DCA triggers
4. Check position averaging
5. Test take-profit execution

**Expected Result**:
- DCA triggers at correct price levels
- Position size increases correctly
- Take profit executes when conditions met

### Test 6: Risk Management
**Objective**: Test risk limits and stop-loss
**Steps**:
1. Set position size limits
2. Test max position enforcement
3. Trigger stop-loss condition
4. Verify emergency stop

**Expected Result**:
- Position limits enforced
- Stop-loss triggers correctly
- Trading halts on risk breach

### Test 7: Error Handling
**Objective**: Test error recovery
**Steps**:
1. Simulate network error (disconnect internet briefly)
2. Test invalid API key (temporarily)
3. Attempt order with insufficient balance
4. Test rate limit handling

**Expected Result**:
- Graceful error handling
- Automatic reconnection
- Proper error logging
- No data loss

### Test 8: State Persistence
**Objective**: Verify bot state saves and recovers
**Steps**:
1. Start bot with active positions
2. Stop bot gracefully
3. Restart bot
4. Verify state restored

**Expected Result**:
- All open orders recovered
- Position tracking correct
- No duplicate orders

## Monitoring During Tests

### Check Bot Status
```bash
# Via Telegram
/status testnet_grid_bot

# Via logs
docker-compose logs -f bot

# Via database
psql -d traderagent_testnet -c "SELECT * FROM orders WHERE bot_name='testnet_grid_bot';"
```

### Key Metrics to Monitor
- ✅ Order execution success rate
- ✅ API call latency
- ✅ Error frequency
- ✅ Balance accuracy
- ✅ Position tracking
- ✅ Memory usage
- ✅ CPU usage

## Common Issues and Solutions

### Issue: "Invalid API key"
**Solution**:
- Verify API key copied correctly
- Check if testnet API keys are used (not production)
- Ensure sandbox=true in configuration

### Issue: "Insufficient balance"
**Solution**:
- Request more test funds from faucet
- Reduce order sizes in configuration
- Check if funds are in correct asset (USDT vs BTC)

### Issue: "Order not executing"
**Solution**:
- Check if price reaches limit order price
- Verify minimum order size requirements
- Check if sufficient balance available
- Review exchange trading rules

### Issue: "Rate limit exceeded"
**Solution**:
- Enable rate limiting in configuration
- Reduce trading frequency
- Check for duplicate API calls
- Wait for rate limit reset

## Best Practices

1. **Always Test on Testnet First**
   - Never deploy to production without testnet validation
   - Test for at least 24-48 hours on testnet

2. **Use Small Amounts**
   - Even though it's test money, use realistic small amounts
   - This simulates real trading conditions better

3. **Monitor Continuously**
   - Watch logs for the first few hours
   - Check Telegram notifications
   - Verify orders on exchange web interface

4. **Test Edge Cases**
   - Rapid price movements
   - Network interruptions
   - Bot restarts
   - Error conditions

5. **Document Issues**
   - Keep a log of any issues encountered
   - Note timestamps and error messages
   - Save relevant logs for debugging

## Automated Test Execution

Run the complete testnet validation suite:

```bash
./bot/tests/testnet/run_testnet_validation.sh
```

This will:
1. Verify configuration
2. Test exchange connection
3. Check API permissions
4. Place and cancel test orders
5. Generate validation report

## Testnet Limitations

**Be aware of testnet differences from production:**

- Testnet may have different liquidity
- Price movements might not match real market
- Some features may be limited or unavailable
- Testnet can be reset periodically
- Performance may differ from production

## Next Steps

After successful testnet testing:

1. ✅ Review all test results
2. ✅ Fix any issues discovered
3. ✅ Document any configuration changes needed
4. ✅ Prepare production configuration
5. ✅ Plan production deployment strategy
6. ✅ Set up production monitoring
7. ✅ Start with minimal funds on production
