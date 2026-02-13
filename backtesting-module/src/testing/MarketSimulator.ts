/**
 * Market Simulator for comprehensive strategy testing
 *
 * Provides realistic market data simulation with:
 * - Tick-by-tick playback
 * - Synthetic scenario generation
 * - Gap simulation (price jumps)
 * - Historical data support
 */

export interface SimulatedTick {
  timestamp: number;
  price: number;
  high?: number;
  low?: number;
  volume?: number;
}

export interface ScenarioConfig {
  name: string;
  description: string;
  startPrice: number;
  ticks: SimulatedTick[];
  expectedOutcome: {
    finalState: string;
    pnl: number;
    reversals: number;
    totalTrades?: number;
    error?: string;
  };
}

export class MarketSimulator {
  private currentTime: number = Date.now();

  /**
   * Сценарий 1: Идеальный цикл
   * Простой breakout → TP без разворотов
   */
  static generatePerfectCycle(): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;

    return {
      name: 'Сценарий 1: Идеальный цикл',
      description: 'Простой breakout вверх → TP без разворотов',
      startPrice,
      ticks: [
        { timestamp: 0, price: 71000, high: 71000, low: 70900 },       // Breakout вверх
        { timestamp: 1000, price: 71200, high: 71200, low: 71000 },    // Движение к TP
        { timestamp: 2000, price: 71500, high: 71500, low: 71200 },
        { timestamp: 3000, price: 71800, high: 71800, low: 71500 },
        { timestamp: 4000, price: 72000, high: 72000, low: 71800 },    // TP hit (+$100)
      ],
      expectedOutcome: {
        finalState: 'success',
        pnl: 100,  // 0.1 BTC * $1000 channel width
        reversals: 0,
        totalTrades: 1,
      },
    };
  }

  /**
   * Сценарий 2: Один разворот
   * SL → удвоение лота → TP
   */
  static generateOneReversal(): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;

    return {
      name: 'Сценарий 2: Один разворот',
      description: 'Breakout → SL → удвоение лота → TP',
      startPrice,
      ticks: [
        // Breakout вверх
        { timestamp: 0, price: 71000, high: 71000, low: 70900 },       // BUY 0.1 @ 71000
        { timestamp: 1000, price: 70800, high: 71000, low: 70800 },    // Цена падает
        { timestamp: 2000, price: 70500, high: 70800, low: 70500 },
        { timestamp: 3000, price: 70000, high: 70500, low: 70000 },    // SL hit (-$100)

        // Разворот: SELL 0.2
        { timestamp: 4000, price: 69800, high: 70000, low: 69800 },    // Движение вниз
        { timestamp: 5000, price: 69500, high: 69800, low: 69500 },
        { timestamp: 6000, price: 69000, high: 69500, low: 69000 },    // TP hit (+$200)
      ],
      expectedOutcome: {
        finalState: 'success',
        pnl: 100,  // -$100 + $200 = +$100 net
        reversals: 1,
        totalTrades: 2,
      },
    };
  }

  /**
   * Сценарий 3: Серия из 5 разворотов
   * Тестирует удвоение лота и мартингейл-логику
   */
  static generateReversalChain(count: number): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;
    const ticks: SimulatedTick[] = [];
    let price = startPrice;
    let time = 0;

    // Начальный breakout вверх
    ticks.push({ timestamp: time, price, high: price, low: price - 100 });
    time += 1000;

    // Серия SL (разворотов)
    for (let i = 0; i < count; i++) {
      // SL hit (цена идет против позиции)
      if (i % 2 === 0) {
        // Позиция была BUY → падаем к SL
        price = startPrice - channelWidth;
        ticks.push({ timestamp: time, price, high: price + 100, low: price });
      } else {
        // Позиция была SELL → растем к SL
        price = startPrice;
        ticks.push({ timestamp: time, price, high: price, low: price - 100 });
      }
      time += 1000;
    }

    // Финальный TP (успешное закрытие)
    if (count % 2 === 0) {
      // Последняя позиция BUY → растем к TP
      price = startPrice + channelWidth;
    } else {
      // Последняя позиция SELL → падаем к TP
      price = startPrice - channelWidth * 2;
    }
    ticks.push({ timestamp: time, price, high: price, low: price - 100 });

    // Расчет ожидаемого PnL
    const calculatePnL = (reversals: number): number => {
      let totalLoss = 0;
      let lot = 0.1;

      for (let i = 0; i < reversals; i++) {
        totalLoss += lot * channelWidth;
        lot *= 2;
      }

      const finalProfit = lot * channelWidth;
      return finalProfit - totalLoss;
    };

    return {
      name: `Сценарий 3: Серия из ${count} разворотов`,
      description: `${count} SL подряд → финальный TP (тест мартингейла)`,
      startPrice,
      ticks,
      expectedOutcome: {
        finalState: 'success',
        pnl: calculatePnL(count),
        reversals: count,
        totalTrades: count + 1,
      },
    };
  }

  /**
   * Сценарий 4: Максимум разворотов → failure
   * 12 разворотов подряд без TP → стратегия останавливается
   */
  static generateMaxReversalsFailure(maxReversals: number = 12): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;
    const ticks: SimulatedTick[] = [];
    let price = startPrice;
    let time = 0;

    // Начальный breakout
    ticks.push({ timestamp: time, price, high: price, low: price - 100 });
    time += 1000;

    // Серия SL до достижения максимума
    for (let i = 0; i < maxReversals; i++) {
      if (i % 2 === 0) {
        price = startPrice - channelWidth;
      } else {
        price = startPrice;
      }
      ticks.push({ timestamp: time, price, high: price + 100, low: price - 100 });
      time += 1000;
    }

    // Расчет убытка
    const calculateLoss = (reversals: number): number => {
      let totalLoss = 0;
      let lot = 0.1;

      for (let i = 0; i <= reversals; i++) {
        totalLoss += lot * channelWidth;
        lot = Math.min(lot * 2, 3.0); // Cap at maxLot
      }

      return -totalLoss;
    };

    return {
      name: `Сценарий 4: Максимум ${maxReversals} разворотов → failure`,
      description: `${maxReversals} SL подряд → стратегия останавливается`,
      startPrice,
      ticks,
      expectedOutcome: {
        finalState: 'failure',
        pnl: calculateLoss(maxReversals),
        reversals: maxReversals,
        error: 'MAX_REVERSALS_REACHED',
      },
    };
  }

  /**
   * Сценарий 5: Динамика канала - отмена ордеров
   * Границы канала меняются → старые ордера отменяются
   */
  static generateChannelDynamics(): ScenarioConfig {
    const startPrice = 70500;

    return {
      name: 'Сценарий 5: Динамика канала',
      description: 'Границы канала смещаются → ордера отменяются и пересоздаются',
      startPrice,
      ticks: [
        // Канал: $70,000 - $71,000
        { timestamp: 0, price: 70500, high: 71000, low: 70000 },
        { timestamp: 1000, price: 70600, high: 71000, low: 70000 },

        // Канал смещается: $70,500 - $71,500
        { timestamp: 2000, price: 71000, high: 71500, low: 70500 },
        { timestamp: 3000, price: 71200, high: 71500, low: 70500 },

        // Проверка что новые границы применились
        { timestamp: 4000, price: 71400, high: 71500, low: 70500 },
      ],
      expectedOutcome: {
        finalState: 'waiting', // Без breakout, просто обновление канала
        pnl: 0,
        reversals: 0,
      },
    };
  }

  /**
   * Сценарий 6: Недостаточно баланса
   * После N разворотов баланс не покрывает удвоенный лот
   */
  static generateInsufficientBalance(): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;
    const ticks: SimulatedTick[] = [];
    let price = startPrice;
    let time = 0;

    // Breakout
    ticks.push({ timestamp: time, price, high: price, low: price - 100 });
    time += 1000;

    // 3 разворота (0.1 → 0.2 → 0.4 → 0.8)
    // На 4-м развороте нужен лот 0.8, что требует ~$56,000
    // При начальном балансе $1000 это невозможно
    for (let i = 0; i < 4; i++) {
      price = i % 2 === 0 ? startPrice - channelWidth : startPrice;
      ticks.push({ timestamp: time, price, high: price + 100, low: price - 100 });
      time += 1000;
    }

    return {
      name: 'Сценарий 6: Недостаточно баланса',
      description: 'Баланс не покрывает удвоенный лот → стратегия останавливается',
      startPrice,
      ticks,
      expectedOutcome: {
        finalState: 'failure',
        pnl: -700, // Losses from 0.1, 0.2, 0.4 lots
        reversals: 3, // Stops at 4th reversal due to insufficient balance
        error: 'Insufficient balance',
      },
    };
  }

  /**
   * Сценарий 7: Gap через SL
   * Цена проскакивает SL (gapping) → убыток больше ожидаемого
   */
  static generateGapThroughSL(): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;

    return {
      name: 'Сценарий 7: Gap через SL',
      description: 'Цена делает gap и проскакивает SL → убыток больше расчетного',
      startPrice,
      ticks: [
        // BUY 0.1 @ 71000, SL=$70000, TP=$72000
        { timestamp: 0, price: 71000, high: 71000, low: 70900 },
        { timestamp: 1000, price: 70800, high: 71000, low: 70800 },

        // GAP: цена падает с $70,000 до $68,500 (проскочила SL)
        { timestamp: 2000, price: 68500, high: 70000, low: 68500 }, // SL triggered at $68,500

        // Разворот с учетом реального убытка
        { timestamp: 3000, price: 68000, high: 68500, low: 68000 },
        { timestamp: 4000, price: 67000, high: 68000, low: 67000 }, // TP hit
      ],
      expectedOutcome: {
        finalState: 'success',
        pnl: -50, // Loss больше из-за gap: -$250 + $200 = -$50
        reversals: 1,
      },
    };
  }

  /**
   * Сценарий 8: Узкий канал
   * Ширина канала меньше minChannel → вход блокируется
   */
  static generateNarrowChannel(): ScenarioConfig {
    const startPrice = 70500;

    return {
      name: 'Сценарий 8: Узкий канал',
      description: 'Канал уже minChannel → breakout блокируется guard',
      startPrice,
      ticks: [
        // Канал слишком узкий: width=$50 (< minChannel=$100)
        { timestamp: 0, price: 70500, high: 70525, low: 70475 }, // Width = 50
        { timestamp: 1000, price: 70530, high: 70530, low: 70475 }, // Breakout attempt
        { timestamp: 2000, price: 70540, high: 70540, low: 70475 },
      ],
      expectedOutcome: {
        finalState: 'waiting',
        pnl: 0,
        reversals: 0,
        error: 'Channel too narrow',
      },
    };
  }

  /**
   * Сценарий 9: Восстановление после рестарта
   * State machine восстанавливается с активной позицией
   */
  static generateRecoveryAfterRestart(): ScenarioConfig {
    const startPrice = 71000;
    const channelWidth = 1000;

    return {
      name: 'Сценарий 9: Восстановление после рестарта',
      description: 'Стратегия перезапускается с активной позицией → продолжает мониторинг',
      startPrice,
      ticks: [
        // Позиция уже открыта: BUY 0.4 @ 70000 (reversal #2)
        // После рестарта продолжаем мониторинг
        { timestamp: 0, price: 70200, high: 70200, low: 70000 },
        { timestamp: 1000, price: 70500, high: 70500, low: 70200 },
        { timestamp: 2000, price: 70800, high: 70800, low: 70500 },
        { timestamp: 3000, price: 71000, high: 71000, low: 70800 }, // TP hit
      ],
      expectedOutcome: {
        finalState: 'success',
        pnl: 400, // 0.4 BTC * $1000
        reversals: 2, // Restored from context
      },
    };
  }

  /**
   * Сценарий 10: Конкурентные breakout'ы
   * Два breakout'а одновременно → только один проходит
   */
  static generateConcurrentBreakouts(): ScenarioConfig {
    const startPrice = 70500;

    return {
      name: 'Сценарий 10: Конкурентные breakout\'ы',
      description: 'Два breakout одновременно → только первый открывает позицию',
      startPrice,
      ticks: [
        // Одновременный breakout вверх и вниз (edge case)
        { timestamp: 0, price: 71000, high: 71500, low: 69500 }, // Wide range
        { timestamp: 100, price: 71200, high: 71500, low: 69500 }, // Still in wide range
        { timestamp: 200, price: 71400, high: 71500, low: 69500 },
      ],
      expectedOutcome: {
        finalState: 'placeOrder', // Only one position opened
        pnl: 0,
        reversals: 0,
        totalTrades: 1,
      },
    };
  }

  /**
   * Проигрывает сценарий tick-by-tick
   * Вызывает callback для каждого тика с задержкой
   */
  async playScenario(
    scenario: ScenarioConfig,
    onTick: (tick: SimulatedTick) => Promise<void>,
    options: {
      speedMultiplier?: number; // Ускорение времени (1 = real-time, 0 = instant)
    } = {}
  ): Promise<void> {
    const { speedMultiplier = 0 } = options;

    console.log(`\n🎬 Запуск сценария: ${scenario.name}`);
    console.log(`📝 ${scenario.description}`);
    console.log(`📊 Тиков: ${scenario.ticks.length}`);
    console.log(`💰 Ожидаемый PnL: $${scenario.expectedOutcome.pnl}`);
    console.log(`🔄 Ожидаемые развороты: ${scenario.expectedOutcome.reversals}\n`);

    for (const tick of scenario.ticks) {
      this.currentTime = scenario.ticks[0].timestamp + tick.timestamp;

      console.log(`⏱️  Tick ${tick.timestamp}ms: price=$${tick.price.toFixed(2)}`);

      await onTick(tick);

      // Задержка для реалистичности (если speedMultiplier > 0)
      if (speedMultiplier > 0) {
        const delayMs = 10 * speedMultiplier;
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }

    console.log(`\n✅ Сценарий завершен: ${scenario.name}\n`);
  }

  /**
   * Получить текущее время симуляции
   */
  getCurrentTime(): number {
    return this.currentTime;
  }

  /**
   * Сгенерировать все тестовые сценарии
   */
  static generateAllScenarios(): ScenarioConfig[] {
    return [
      MarketSimulator.generatePerfectCycle(),
      MarketSimulator.generateOneReversal(),
      MarketSimulator.generateReversalChain(5),
      MarketSimulator.generateMaxReversalsFailure(12),
      MarketSimulator.generateChannelDynamics(),
      MarketSimulator.generateInsufficientBalance(),
      MarketSimulator.generateGapThroughSL(),
      MarketSimulator.generateNarrowChannel(),
      MarketSimulator.generateRecoveryAfterRestart(),
      MarketSimulator.generateConcurrentBreakouts(),
    ];
  }
}
