import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import { botsApi, type PnLDataPoint } from '../../api/bots';
import { Skeleton } from './Skeleton';

// ─── Types ────────────────────────────────────────────────────────────────────

type Period = '1d' | '7d' | '30d' | 'all';

interface PnlChartProps {
  botName: string;
}

// ─── Theme colours (must match globals.css / theme.ts) ────────────────────────

const COLORS = {
  background:  '#161b22',  // surface
  gridLines:   '#30363d',  // border
  text:        '#8b949e',  // text-muted
  profit:      '#3fb950',
  loss:        '#f85149',
} as const;

const PERIODS: { label: string; value: Period }[] = [
  { label: '1D',  value: '1d'  },
  { label: '7D',  value: '7d'  },
  { label: '30D', value: '30d' },
  { label: 'All', value: 'all' },
];

// ─── Component ────────────────────────────────────────────────────────────────

export function PnlChart({ botName }: PnlChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<IChartApi | null>(null);
  const seriesRef    = useRef<ISeriesApi<'Area'> | null>(null);

  const [period, setPeriod]   = useState<Period>('7d');
  const [loading, setLoading] = useState(true);
  const [isEmpty, setIsEmpty] = useState(false);
  const [isPositive, setIsPositive] = useState(true);

  // ── Create / destroy chart instance ──────────────────────────────────────

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background:  { type: ColorType.Solid, color: COLORS.background },
        textColor:   COLORS.text,
        fontFamily:  'Inter, -apple-system, sans-serif',
        fontSize:    11,
      },
      grid: {
        vertLines:  { color: COLORS.gridLines, style: 1 },
        horzLines:  { color: COLORS.gridLines, style: 1 },
      },
      crosshair: {
        vertLine: { labelBackgroundColor: '#640075' },
        horzLine: { labelBackgroundColor: '#640075' },
      },
      rightPriceScale: {
        borderColor:  COLORS.gridLines,
        scaleMargins: { top: 0.15, bottom: 0.1 },
      },
      timeScale: {
        borderColor:    COLORS.gridLines,
        timeVisible:    true,
        secondsVisible: false,
      },
      handleScroll:   true,
      handleScale:    true,
      autoSize:       true,
    });

    const series = chart.addAreaSeries({
      lineColor:    COLORS.profit,
      topColor:     `${COLORS.profit}33`,
      bottomColor:  `${COLORS.profit}00`,
      lineWidth:    2,
      priceFormat:  { type: 'custom', formatter: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(4)}` },
    });

    chartRef.current  = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current  = null;
      seriesRef.current = null;
    };
  }, []);

  // ── Load data when period changes ─────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setIsEmpty(false);

      try {
        const res = await botsApi.getPnlHistory(botName, period);
        if (cancelled) return;

        const raw: PnLDataPoint[] = res.data.points ?? [];

        if (raw.length === 0) {
          setIsEmpty(true);
          seriesRef.current?.setData([]);
          return;
        }

        // Determine chart colour from final cumulative value
        const lastValue = raw[raw.length - 1].value;
        const positive  = lastValue >= 0;
        setIsPositive(positive);

        const color    = positive ? COLORS.profit : COLORS.loss;
        seriesRef.current?.applyOptions({
          lineColor:   color,
          topColor:    `${color}33`,
          bottomColor: `${color}00`,
        });

        // lightweight-charts v5 uses UTCTimestamp (seconds) for time
        const chartData = raw.map((p) => ({
          time:  Math.round(p.timestamp) as UTCTimestamp,
          value: p.value,
        }));

        seriesRef.current?.setData(chartData);
        chartRef.current?.timeScale().fitContent();
      } catch {
        if (!cancelled) setIsEmpty(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [botName, period]);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">PnL Chart</p>

        {/* Period selector */}
        <div className="flex gap-1">
          {PERIODS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setPeriod(value)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                period === value
                  ? 'bg-primary text-white'
                  : 'text-text-muted hover:text-text hover:bg-surface-hover'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      <div className="relative h-48">
        {/* lightweight-charts mounts into this div */}
        <div ref={containerRef} className="h-full w-full" />

        {/* Skeleton overlay while loading */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface rounded-lg">
            <Skeleton className="h-full w-full rounded-lg" />
          </div>
        )}

        {/* Empty-state overlay */}
        {!loading && isEmpty && (
          <div className="absolute inset-0 flex items-center justify-center bg-background rounded-lg border border-border/50">
            <p className="text-xs text-text-muted">Недостаточно данных для отображения</p>
          </div>
        )}
      </div>

      {/* Colour legend */}
      {!loading && !isEmpty && (
        <div className="mt-2 flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-0.5 rounded"
            style={{ backgroundColor: isPositive ? COLORS.profit : COLORS.loss }}
          />
          <span className="text-xs text-text-muted">Cumulative PnL (USDT)</span>
        </div>
      )}
    </div>
  );
}
