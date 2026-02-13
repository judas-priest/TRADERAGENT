/**
 * Mock Bybit Exchange for testing
 *
 * Simulates Bybit API without actual network requests:
 * - Order management (create, cancel, fill)
 * - Position tracking
 * - Balance management
 * - Time control for testing
 * - Error simulation
 */

export type OrderSide = 'Buy' | 'Sell';
export type OrderType = 'Market' | 'Limit';
export type OrderStatus = 'New' | 'PartiallyFilled' | 'Filled' | 'Cancelled' | 'Rejected';
export type PositionSide = 'Buy' | 'Sell';

export interface MockOrder {
  orderId: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  qty: number;
  price: number;
  status: OrderStatus;
  stopLoss?: number;
  takeProfit?: number;
  createdAt: number;
  filledAt?: number;
}

export interface MockPosition {
  symbol: string;
  side: PositionSide;
  size: number;
  entryPrice: number;
  markPrice: number;
  unrealizedPnl: number;
  leverage: number;
  stopLoss?: number;
  takeProfit?: number;
}

export interface MockBalance {
  coin: string;
  walletBalance: number;
  availableBalance: number;
  unrealizedPnl: number;
}

export interface MockError {
  type: 'TIMEOUT' | 'RATE_LIMIT' | 'INSUFFICIENT_BALANCE' | 'INVALID_SYMBOL' | 'INVALID_ORDER';
  message: string;
  retCode: number;
}

/**
 * Mock Bybit Exchange для тестирования стратегий
 */
export class MockBybitExchange {
  private orders: Map<string, MockOrder> = new Map();
  private positions: Map<string, MockPosition> = new Map();
  private balances: Map<string, MockBalance> = new Map();
  private currentTime: number = Date.now();
  private latencyMs: number = 0;
  private currentPrice: number = 70000; // Default BTC price
  private orderIdCounter: number = 1;

  // Error simulation
  private nextError: MockError | null = null;

  constructor(initialBalance: number = 10000) {
    // Initialize USDT balance
    this.balances.set('USDT', {
      coin: 'USDT',
      walletBalance: initialBalance,
      availableBalance: initialBalance,
      unrealizedPnl: 0,
    });
  }

  /**
   * Set current market price (for SL/TP checks)
   */
  setCurrentPrice(price: number): void {
    this.currentPrice = price;
    this.checkStopLossAndTakeProfit();
  }

  /**
   * Get current market price
   */
  getCurrentPrice(symbol: string = 'BTCUSDT'): number {
    return this.currentPrice;
  }

  /**
   * Set simulated API latency
   */
  setLatency(ms: number): void {
    this.latencyMs = ms;
  }

  /**
   * Set current time (for testing)
   */
  setTime(timestamp: number): void {
    this.currentTime = timestamp;
  }

  /**
   * Simulate API error on next request
   */
  simulateError(errorType: MockError['type'], message?: string): void {
    const errorMap: Record<MockError['type'], { message: string; retCode: number }> = {
      TIMEOUT: { message: message || 'Request timeout', retCode: 10001 },
      RATE_LIMIT: { message: message || 'Rate limit exceeded', retCode: 10006 },
      INSUFFICIENT_BALANCE: { message: message || 'Insufficient balance', retCode: 30007 },
      INVALID_SYMBOL: { message: message || 'Invalid symbol', retCode: 10004 },
      INVALID_ORDER: { message: message || 'Invalid order', retCode: 30005 },
    };

    this.nextError = {
      type: errorType,
      ...errorMap[errorType],
    };
  }

  /**
   * Check and throw next simulated error
   */
  private async checkError(): Promise<void> {
    if (this.nextError) {
      const error = this.nextError;
      this.nextError = null; // Clear after throwing
      throw new Error(`[Mock Error ${error.retCode}] ${error.message}`);
    }

    // Simulate latency
    if (this.latencyMs > 0) {
      await new Promise(resolve => setTimeout(resolve, this.latencyMs));
    }
  }

  /**
   * Create a new order (Market or Limit)
   */
  async createOrder(params: {
    symbol: string;
    side: OrderSide;
    orderType: OrderType;
    qty: number;
    price?: number;
    stopLoss?: number;
    takeProfit?: number;
  }): Promise<MockOrder> {
    await this.checkError();

    const { symbol, side, orderType, qty, price, stopLoss, takeProfit } = params;

    // Check balance
    const balance = this.balances.get('USDT');
    if (!balance) {
      throw new Error('[Mock Error 30007] Insufficient balance');
    }

    const orderValue = qty * (price || this.currentPrice);
    if (balance.availableBalance < orderValue) {
      throw new Error(`[Mock Error 30007] Insufficient balance: need $${orderValue.toFixed(2)}, have $${balance.availableBalance.toFixed(2)}`);
    }

    const orderId = `mock_order_${this.orderIdCounter++}`;
    const order: MockOrder = {
      orderId,
      symbol,
      side,
      type: orderType,
      qty,
      price: price || this.currentPrice,
      status: orderType === 'Market' ? 'Filled' : 'New',
      stopLoss,
      takeProfit,
      createdAt: this.currentTime,
    };

    this.orders.set(orderId, order);

    // If Market order, fill immediately and create position
    if (orderType === 'Market') {
      order.filledAt = this.currentTime;
      await this.fillOrder(orderId);
    }

    console.log(`[MockExchange] Order created: ${orderId}, ${side} ${qty} @ $${order.price.toFixed(2)}`);

    return order;
  }

  /**
   * Fill an order and create/update position
   */
  private async fillOrder(orderId: string): Promise<void> {
    const order = this.orders.get(orderId);
    if (!order || order.status === 'Filled') {
      return;
    }

    order.status = 'Filled';
    order.filledAt = this.currentTime;

    // Create or update position
    const existingPosition = this.positions.get(order.symbol);

    if (existingPosition) {
      // Close or reverse position
      if (existingPosition.side !== order.side) {
        // Opposite side → close position
        const pnl = this.calculatePnL(existingPosition, order.price);
        this.updateBalance(pnl);
        this.positions.delete(order.symbol);
        console.log(`[MockExchange] Position closed: PnL=$${pnl.toFixed(2)}`);
      } else {
        // Same side → increase position
        const totalSize = existingPosition.size + order.qty;
        const avgPrice = (existingPosition.entryPrice * existingPosition.size + order.price * order.qty) / totalSize;
        existingPosition.size = totalSize;
        existingPosition.entryPrice = avgPrice;
      }
    } else {
      // New position
      const position: MockPosition = {
        symbol: order.symbol,
        side: order.side === 'Buy' ? 'Buy' : 'Sell',
        size: order.qty,
        entryPrice: order.price,
        markPrice: order.price,
        unrealizedPnl: 0,
        leverage: 1,
        stopLoss: order.stopLoss,
        takeProfit: order.takeProfit,
      };

      this.positions.set(order.symbol, position);
      console.log(`[MockExchange] Position opened: ${order.side} ${order.qty} @ $${order.price.toFixed(2)}`);
    }
  }

  /**
   * Cancel an order
   */
  async cancelOrder(symbol: string, orderId: string): Promise<void> {
    await this.checkError();

    const order = this.orders.get(orderId);
    if (!order) {
      throw new Error(`[Mock Error] Order not found: ${orderId}`);
    }

    if (order.status === 'Filled') {
      throw new Error(`[Mock Error] Cannot cancel filled order: ${orderId}`);
    }

    order.status = 'Cancelled';
    console.log(`[MockExchange] Order cancelled: ${orderId}`);
  }

  /**
   * Cancel all orders for a symbol
   */
  async cancelAllOrders(symbol: string): Promise<void> {
    await this.checkError();

    let cancelledCount = 0;
    for (const [orderId, order] of this.orders.entries()) {
      if (order.symbol === symbol && order.status === 'New') {
        order.status = 'Cancelled';
        cancelledCount++;
      }
    }

    console.log(`[MockExchange] Cancelled ${cancelledCount} orders for ${symbol}`);
  }

  /**
   * Get all positions
   */
  async getPositions(symbol?: string): Promise<MockPosition[]> {
    await this.checkError();

    const positions = Array.from(this.positions.values());

    if (symbol) {
      return positions.filter(p => p.symbol === symbol);
    }

    return positions;
  }

  /**
   * Get all orders
   */
  async getOrders(symbol?: string): Promise<MockOrder[]> {
    await this.checkError();

    const orders = Array.from(this.orders.values());

    if (symbol) {
      return orders.filter(o => o.symbol === symbol);
    }

    return orders;
  }

  /**
   * Get balance
   */
  async getBalance(coin: string = 'USDT'): Promise<MockBalance> {
    await this.checkError();

    const balance = this.balances.get(coin);
    if (!balance) {
      throw new Error(`[Mock Error] Balance not found for ${coin}`);
    }

    return balance;
  }

  /**
   * Check if price hit SL/TP and close position
   */
  private checkStopLossAndTakeProfit(): void {
    for (const [symbol, position] of this.positions.entries()) {
      position.markPrice = this.currentPrice;

      // Update unrealized PnL
      position.unrealizedPnl = this.calculateUnrealizedPnL(position);

      // Check Stop Loss
      if (position.stopLoss) {
        const slHit =
          (position.side === 'Buy' && this.currentPrice <= position.stopLoss) ||
          (position.side === 'Sell' && this.currentPrice >= position.stopLoss);

        if (slHit) {
          console.log(`[MockExchange] 🛑 Stop Loss hit at $${this.currentPrice.toFixed(2)}`);
          const pnl = this.calculatePnL(position, this.currentPrice);
          this.updateBalance(pnl);
          this.positions.delete(symbol);
          continue;
        }
      }

      // Check Take Profit
      if (position.takeProfit) {
        const tpHit =
          (position.side === 'Buy' && this.currentPrice >= position.takeProfit) ||
          (position.side === 'Sell' && this.currentPrice <= position.takeProfit);

        if (tpHit) {
          console.log(`[MockExchange] 🎯 Take Profit hit at $${this.currentPrice.toFixed(2)}`);
          const pnl = this.calculatePnL(position, this.currentPrice);
          this.updateBalance(pnl);
          this.positions.delete(symbol);
        }
      }
    }
  }

  /**
   * Calculate PnL for a position
   */
  private calculatePnL(position: MockPosition, exitPrice: number): number {
    if (position.side === 'Buy') {
      return (exitPrice - position.entryPrice) * position.size;
    } else {
      return (position.entryPrice - exitPrice) * position.size;
    }
  }

  /**
   * Calculate unrealized PnL
   */
  private calculateUnrealizedPnL(position: MockPosition): number {
    return this.calculatePnL(position, position.markPrice);
  }

  /**
   * Update balance after trade
   */
  private updateBalance(pnl: number): void {
    const balance = this.balances.get('USDT')!;
    balance.walletBalance += pnl;
    balance.availableBalance = balance.walletBalance;

    console.log(`[MockExchange] Balance updated: $${balance.walletBalance.toFixed(2)} (${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)})`);
  }

  /**
   * Get trading statistics
   */
  getStats(): {
    totalOrders: number;
    filledOrders: number;
    cancelledOrders: number;
    openPositions: number;
    balance: number;
  } {
    const orders = Array.from(this.orders.values());
    const balance = this.balances.get('USDT')!;

    return {
      totalOrders: orders.length,
      filledOrders: orders.filter(o => o.status === 'Filled').length,
      cancelledOrders: orders.filter(o => o.status === 'Cancelled').length,
      openPositions: this.positions.size,
      balance: balance.walletBalance,
    };
  }

  /**
   * Reset exchange state (for testing)
   */
  reset(initialBalance: number = 10000): void {
    this.orders.clear();
    this.positions.clear();
    this.balances.clear();
    this.balances.set('USDT', {
      coin: 'USDT',
      walletBalance: initialBalance,
      availableBalance: initialBalance,
      unrealizedPnl: 0,
    });
    this.currentTime = Date.now();
    this.orderIdCounter = 1;
    this.nextError = null;
  }
}
