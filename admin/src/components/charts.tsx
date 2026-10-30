import { useEffect, useRef, useState, type ReactNode } from 'react'

import { Button, Card } from './ui'

const MONTHS = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek']
const MONTHS_FULL = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']

/** "2026-10" → "okt" (axis) / "Oktabr 2026" (tooltip, table). */
export function monthLabel(key: string, full = false): string {
  const [year, month] = key.split('-').map(Number)
  return full ? `${MONTHS_FULL[month - 1]} ${year}` : MONTHS[month - 1]
}

export function formatNumber(value: number): string {
  return value.toLocaleString('uz-UZ').replace(/,/g, ' ')
}

function niceMax(value: number): number {
  if (value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  for (const step of [1, 2, 4, 5, 10]) {
    if (value <= step * power) return step * power
  }
  return 10 * power
}

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

/** A card with a title and a table-view toggle (the accessible twin of every chart). */
export function ChartCard({
  title,
  subtitle,
  table,
  children,
}: {
  title: string
  subtitle?: string
  table?: { head: string[]; rows: (string | number)[][] }
  children: ReactNode
}) {
  const [showTable, setShowTable] = useState(false)
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{title}</h2>
          {subtitle && <p className="text-xs text-app-hint">{subtitle}</p>}
        </div>
        {table && (
          <Button variant="ghost" className="shrink-0 text-xs" onClick={() => setShowTable((value) => !value)} aria-pressed={showTable}>
            {showTable ? 'Diagramma' : 'Jadval'}
          </Button>
        )}
      </div>
      {showTable && table ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-app-hint">
              {table.head.map((cell, index) => (
                <th key={cell} className={`py-1 font-medium ${index > 0 ? 'text-right' : ''}`}>
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border">
            {table.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, index) => (
                  <td key={index} className={`py-1 ${index > 0 ? 'text-right tabular-nums' : ''}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        children
      )}
    </Card>
  )
}

/** Single-series column chart: thin bars, rounded data end, hairline grid, hover/focus tooltip. */
export function ColumnChart({
  labels,
  values,
  tooltipLabels,
  unit = '',
  height = 150,
  labelLast = true,
}: {
  labels: string[]
  values: number[]
  tooltipLabels?: string[]
  unit?: string
  height?: number
  /** Direct-label the newest value (time series); off for distributions. */
  labelLast?: boolean
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const axis = 32
  const bottom = 22
  const top = 16
  const plotWidth = Math.max(0, width - axis)
  const plotHeight = height - bottom - top
  const max = niceMax(Math.max(...values, 0))
  const ticks = max >= 2 && max % 2 === 0 ? [0, max / 2, max] : [0, max]
  const band = values.length ? plotWidth / values.length : 0
  const barWidth = Math.min(24, band * 0.6)
  const y = (value: number) => top + plotHeight - (value / max) * plotHeight
  const last = values.length - 1

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={labels.map((label, i) => `${tooltipLabels?.[i] ?? label}: ${values[i]}`).join('; ')}>
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={axis} x2={width} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? 'var(--viz-axis)' : 'var(--viz-grid)'} strokeWidth={1} />
              <text x={axis - 6} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-app-hint" style={{ fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                {formatNumber(Math.round(tick))}
              </text>
            </g>
          ))}
          {values.map((value, index) => {
            const x = axis + band * index + (band - barWidth) / 2
            const barHeight = Math.max(0, (value / max) * plotHeight)
            const radius = Math.min(4, barHeight, barWidth / 2)
            const baseline = top + plotHeight
            const path =
              barHeight <= 0
                ? ''
                : `M${x},${baseline} V${baseline - barHeight + radius} Q${x},${baseline - barHeight} ${x + radius},${baseline - barHeight} H${x + barWidth - radius} Q${x + barWidth},${baseline - barHeight} ${x + barWidth},${baseline - barHeight + radius} V${baseline} Z`
            return (
              <g
                key={index}
                tabIndex={0}
                role="graphics-symbol"
                aria-label={`${tooltipLabels?.[index] ?? labels[index]}: ${formatNumber(value)}${unit}`}
                onPointerEnter={() => setActive(index)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
                className="outline-none"
              >
                <rect x={axis + band * index} y={top} width={band} height={plotHeight + bottom} fill="transparent" />
                {path && <path d={path} fill="var(--viz-series)" opacity={active === null || active === index ? 1 : 0.55} />}
                <text x={x + barWidth / 2} y={height - 6} textAnchor="middle" className="fill-app-hint" style={{ fontSize: 10 }}>
                  {labels[index]}
                </text>
                {labelLast && index === last && (
                  <text x={x + barWidth / 2} y={y(value) - 5} textAnchor="middle" className="fill-app-text" style={{ fontSize: 11, fontWeight: 600 }}>
                    {formatNumber(value)}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      )}
      {active !== null && width > 0 && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-md border border-app-border bg-app-bg px-2 py-1 text-xs shadow"
          style={{ left: axis + band * active + band / 2, top: Math.max(0, y(values[active]) - 44) }}
        >
          <p className="font-semibold tabular-nums">
            {formatNumber(values[active])}
            {unit}
          </p>
          <p className="whitespace-nowrap text-app-hint">{tooltipLabels?.[active] ?? labels[active]}</p>
        </div>
      )}
    </div>
  )
}

/** Horizontal single-series bars with the value at the tip. */
export function BarList({ rows, unit = '' }: { rows: { label: string; sublabel?: string; value: number }[]; unit?: string }) {
  const max = Math.max(...rows.map((row) => row.value), 0) || 1
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((row) => (
        <li key={row.label + (row.sublabel ?? '')} className="grid grid-cols-[minmax(0,13rem)_1fr] items-center gap-3 text-sm" tabIndex={0} title={`${row.label}: ${formatNumber(row.value)}${unit}`}>
          <span className="truncate">
            {row.label}
            {row.sublabel && <span className="text-xs text-app-hint"> · {row.sublabel}</span>}
          </span>
          <span className="flex items-center gap-2">
            <span className="h-3 rounded-r-[4px]" style={{ width: `${(row.value / max) * 85}%`, minWidth: row.value > 0 ? 3 : 0, background: 'var(--viz-series)' }} />
            <span className="whitespace-nowrap text-xs font-semibold tabular-nums">
              {formatNumber(row.value)}
              {unit}
            </span>
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Planned vs actual, one row per item: a faint bar = planned, a solid bar = actual, both to one scale.
 * Single hue (the actual sits inside the planned), so it reads as «of the planned, this much came». */
export function PlannedVsActual({ rows }: { rows: { label: string; planned: number; actual: number; rate: number }[] }) {
  const max = Math.max(...rows.map((row) => Math.max(row.planned, row.actual)), 1)
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((row) => (
        <li
          key={row.label}
          className="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3 text-sm"
          tabIndex={0}
          title={`${row.label}: keldi ${formatNumber(row.actual)} / rejada ${formatNumber(row.planned)} (${row.rate}%)`}
        >
          <span className="truncate">{row.label}</span>
          <span className="relative h-3 overflow-hidden rounded-full" style={{ background: 'var(--viz-track)' }}>
            <span
              className="absolute inset-y-0 left-0 rounded-full opacity-40"
              style={{ width: `${(row.planned / max) * 100}%`, background: 'var(--viz-series)' }}
            />
            <span
              className="absolute inset-y-0 left-0 rounded-full"
              style={{ width: `${(Math.min(row.actual, max) / max) * 100}%`, background: 'var(--viz-series)' }}
            />
          </span>
          <span className="whitespace-nowrap text-xs tabular-nums text-app-hint">
            <span className="font-semibold text-app-text">{formatNumber(row.actual)}</span> / {formatNumber(row.planned)} · {row.rate}%
          </span>
        </li>
      ))}
    </ul>
  )
}

/** A ratio against 100%: same-ramp track, value as text beside it. */
export function Meter({ value, label }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <span className="flex items-center gap-2" title={label}>
      <span className="h-2 w-20 overflow-hidden rounded-full" style={{ background: 'var(--viz-track)' }}>
        <span className="block h-2 rounded-full" style={{ width: `${clamped}%`, background: 'var(--viz-series)' }} />
      </span>
      <span className="text-xs tabular-nums">{value}%</span>
    </span>
  )
}

/** Stat tile: label, value, optional note. */
export function StatTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-app-hint">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {note && <p className="mt-0.5 text-xs text-app-hint">{note}</p>}
    </Card>
  )
}
