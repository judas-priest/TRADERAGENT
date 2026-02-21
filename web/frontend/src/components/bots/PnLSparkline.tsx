import type { PnLDataPoint } from '../../api/bots';

interface PnLSparklineProps {
  points: PnLDataPoint[];
  width?: number;
  height?: number;
}

export function PnLSparkline({ points, width = 120, height = 40 }: PnLSparklineProps) {
  if (points.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-xs text-text-muted"
        style={{ width, height }}
      >
        —
      </div>
    );
  }

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const coords = points.map((p, i) => {
    const x = pad + (i / Math.max(points.length - 1, 1)) * w;
    const y = pad + h - ((p.value - min) / range) * h;
    return { x, y };
  });

  const polyline = coords.map((c) => `${c.x},${c.y}`).join(' ');
  const lastValue = values[values.length - 1];
  const isPositive = lastValue >= 0;
  const color = isPositive ? '#3fb950' : '#f85149';

  // Build fill path: polyline + bottom-right + bottom-left
  const first = coords[0];
  const last = coords[coords.length - 1];
  const fillPath = `M${first.x},${first.y} ${coords.map((c) => `L${c.x},${c.y}`).join(' ')} L${last.x},${pad + h} L${first.x},${pad + h} Z`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-label="PnL sparkline"
      role="img"
    >
      <path d={fillPath} fill={color} fillOpacity="0.15" />
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
