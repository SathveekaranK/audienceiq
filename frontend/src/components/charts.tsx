import React from 'react'

/**
 * Lightweight, dependency-free SVG charts.
 *
 * Every chart is responsive (viewBox + preserveAspectRatio) and inherits the
 * app's colour tokens via CSS custom properties.
 */

// ---------------------------------------------------------------------------
// Donut chart
// ---------------------------------------------------------------------------

export interface DonutSlice {
  label: string
  value: number
  color: string
}

interface DonutProps {
  data: DonutSlice[]
  size?: number
  thickness?: number
  centerLabel?: string
  centerValue?: string
}

export const DonutChart: React.FC<DonutProps> = ({
  data,
  size = 180,
  thickness = 22,
  centerLabel,
  centerValue,
}) => {
  const total = data.reduce((sum, d) => sum + d.value, 0)
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center sm:gap-6">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
          role="img"
          aria-label="Sentiment distribution"
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--surface-subtle)"
            strokeWidth={thickness}
          />
          {total > 0 &&
            data.map((slice, sliceIndex) => {
              const fraction = slice.value / total
              const dash = fraction * circumference
              const element = (
                <circle
                  key={`${slice.label}-${sliceIndex}`}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={slice.color}
                  strokeWidth={thickness}
                  strokeDasharray={`${dash} ${circumference - dash}`}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                />
              )
              offset += dash
              return element
            })}
        </svg>
        {(centerValue || centerLabel) && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            {centerValue ? (
              <span className="text-2xl font-semibold tabular text-strong">
                {centerValue}
              </span>
            ) : null}
            {centerLabel ? (
              <span className="mt-0.5 text-xs text-muted">{centerLabel}</span>
            ) : null}
          </div>
        )}
      </div>

      <ul className="w-full min-w-0 space-y-2">
        {data.map((slice, sliceIndex) => {
          const pct = total > 0 ? (slice.value / total) * 100 : 0
          return (
            <li key={`${slice.label}-${sliceIndex}`} className="flex items-center gap-2.5">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: slice.color }}
              />
              <span className="flex-1 truncate text-xs capitalize text-body">
                {slice.label}
              </span>
              <span className="shrink-0 text-xs font-semibold tabular text-strong">
                {slice.value.toLocaleString()}
              </span>
              <span className="w-11 shrink-0 text-right text-xs tabular text-muted">
                {pct.toFixed(1)}%
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Horizontal bar chart
// ---------------------------------------------------------------------------

export interface BarDatum {
  label: string
  value: number
  color?: string
  meta?: string
}

interface BarsProps {
  data: BarDatum[]
  max?: number
  valueSuffix?: string
  emptyMessage?: string
}

export const BarList: React.FC<BarsProps> = ({
  data,
  max,
  valueSuffix = '',
  emptyMessage = 'No data yet',
}) => {
  const peak = max ?? Math.max(1, ...data.map((d) => d.value))

  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-xs text-muted">{emptyMessage}</p>
    )
  }

  return (
    <ul className="space-y-3">
      {data.map((item, itemIndex) => {
        const pct = (item.value / peak) * 100
        return (
          <li key={`${item.label}-${itemIndex}`}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3">
              <span className="truncate text-xs font-medium text-body">
                {item.label}
              </span>
              <span className="shrink-0 text-xs tabular text-muted">
                {item.value.toLocaleString()}
                {valueSuffix}
                {item.meta ? (
                  <span className="ml-1.5 text-subtle-text">{item.meta}</span>
                ) : null}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-subtle">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.max(pct, 2)}%`,
                  backgroundColor: item.color ?? 'var(--brand-500)',
                }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Line / area chart (sentiment over time)
// ---------------------------------------------------------------------------

export interface SeriesPoint {
  label: string
  values: number[]
}

interface TrendProps {
  series: SeriesPoint[]
  /** One label per x position (e.g. the date). */
  labels: string[]
  colors: string[]
  height?: number
  yMax?: number
}

export const TrendChart: React.FC<TrendProps> = ({
  series,
  labels,
  colors,
  height = 220,
  yMax,
}) => {
  const width = 720
  const padding = { top: 12, right: 12, bottom: 26, left: 34 }

  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom

  const allValues = series.flatMap((s) => s.values)
  const peak = yMax ?? Math.max(1, ...allValues)
  const count = Math.max(1, series[0]?.values.length ?? 1)

  const xAt = (i: number) =>
    padding.left + (i / Math.max(1, count - 1)) * innerW
  const yAt = (v: number) => padding.top + innerH - (v / peak) * innerH

  // Build the Y-axis ticks. Rounding can collapse them into duplicates
  // (e.g. peak=1 -> [0,0,1,1,1]), so de-duplicate while keeping the order.
  const ticks = Array.from(
    new Set([0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(peak * f))),
  )

  if (allValues.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-xs text-muted">
        No trend data yet
      </div>
    )
  }

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-auto w-full"
      role="img"
      aria-label="Trend over time"
    >
      {/* Grid + Y axis */}
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={yAt(tick)}
            y2={yAt(tick)}
            stroke="var(--line-subtle)"
            strokeWidth="1"
          />          <text
            x={padding.left - 8}
            y={yAt(tick) + 3.5}
            textAnchor="end"
            className="fill-[var(--text-subtle)] text-[10px]"
          >
            {tick}
          </text>
        </g>
      ))}

      {/* X labels - show first, middle and last to avoid crowding */}
      {labels.map((label, i) => {
        const showEvery = Math.max(1, Math.ceil(count / 6))
        const isLast = i === count - 1
        if (i % showEvery !== 0 && !isLast) return null
        return (
          <text
            key={i}
            x={xAt(i)}
            y={height - 8}
            textAnchor={isLast ? 'end' : i === 0 ? 'start' : 'middle'}
            className="fill-[var(--text-subtle)] text-[10px]"
          >
            {label}
          </text>
        )
      })}

      {/* Series */}
      {series.map((s, sIndex) => {
        const color = colors[sIndex % colors.length]
        const points = s.values
          .map((v, i) => `${xAt(i)},${yAt(v)}`)
          .join(' ')
        const areaPath = `M ${xAt(0)},${yAt(0)} L ${s.values
          .map((v, i) => `${xAt(i)},${yAt(v)}`)
          .join(' L ')} L ${xAt(s.values.length - 1)},${yAt(0)} Z`

        return (
          <g key={s.label}>
            {s.values.length > 1 ? (
              <>
                <path d={areaPath} fill={color} opacity="0.08" />
                <polyline
                  points={points}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </>
            ) : null}
            {s.values.map((v, i) => (
              <circle
                key={i}
                cx={xAt(i)}
                cy={yAt(v)}
                r="3"
                fill="var(--surface-card)"
                stroke={color}
                strokeWidth="2"
              />
            ))}
          </g>
        )
      })}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Sparkline
// ---------------------------------------------------------------------------

export const Sparkline: React.FC<{
  values: number[]
  color?: string
  width?: number
  height?: number
}> = ({ values, color = 'var(--brand-500)', width = 100, height = 28 }) => {
  if (values.length < 2) {
    return <div style={{ width, height }} />
  }
  const peak = Math.max(1, ...values)
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width
      const y = height - (v / peak) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Chart legend
// ---------------------------------------------------------------------------

export const ChartLegend: React.FC<{
  items: { label: string; color: string }[]
}> = ({ items }) => (
  <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
    {items.map((item) => (
      <li key={item.label} className="flex items-center gap-1.5">
        <span
          className="size-2 rounded-full"
          style={{ backgroundColor: item.color }}
        />
        <span className="text-xs capitalize text-muted">{item.label}</span>
      </li>
    ))}
  </ul>
)

// ---------------------------------------------------------------------------
// Sentiment colours
// ---------------------------------------------------------------------------

export const SENTIMENT_COLORS = {
  positive: 'var(--success)',
  negative: 'var(--danger)',
  neutral: 'var(--text-subtle)',
  unanalyzed: 'var(--line-default)',
} as const

export const CHART_PALETTE = [
  'var(--brand-500)',
  'var(--success)',
  'var(--warning)',
  'var(--danger)',
  'var(--text-subtle)',
] as const
