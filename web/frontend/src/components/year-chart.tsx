// 直近10年度の折れ線。値が無い年は線を切る。線は描かれていき、最新年だけ朱の点。
import type { CSSProperties } from 'react'

import { formatOkuYen, formatPeople } from '@/lib/format'

type Point = { fiscal_year: number; value: number | null }

export function YearChart({
  title,
  points,
  kind,
  delayMs = 0,
}: {
  title: string
  points: Point[]
  kind: 'yen' | 'people'
  delayMs?: number
}) {
  const present = points.filter((point) => point.value != null)
  const width = 360
  const height = 150
  const pad = 16
  if (present.length === 0) {
    return (
      <div className="sheet p-5">
        <p className="text-sm font-black text-ink">{title}</p>
        <p className="mt-2 text-sm text-ink-soft">この10年の有報には値がありません。</p>
      </div>
    )
  }
  const values = present.map((point) => point.value as number)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const xFor = (index: number) =>
    pad + (index * (width - pad * 2)) / Math.max(points.length - 1, 1)
  const yFor = (value: number) => height - pad - ((value - min) / span) * (height - pad * 2)
  const segments: string[] = []
  let current: string[] = []
  points.forEach((point, index) => {
    if (point.value == null) {
      if (current.length > 1) segments.push(current.join(' '))
      current = []
      return
    }
    current.push(`${xFor(index)},${yFor(point.value)}`)
  })
  if (current.length > 1) segments.push(current.join(' '))
  const latestIndex = points.findLastIndex((point) => point.value != null)
  const style = { '--draw-delay': `${delayMs}ms` } as CSSProperties

  return (
    <div className="sheet p-5">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-black text-ink">{title}</p>
        <p className="font-num text-lg font-black text-ink">{formatLatest(points, kind)}</p>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 w-full overflow-visible" role="img" aria-label={title}>
        <line
          x1={pad}
          x2={width - pad}
          y1={height - pad + 6}
          y2={height - pad + 6}
          stroke="var(--ink)"
          strokeOpacity="0.2"
          strokeWidth="2"
          strokeDasharray="4 6"
        />
        {segments.map((segment) => (
          <polyline
            key={segment}
            className="draw-line"
            style={style}
            pathLength={1}
            fill="none"
            stroke="var(--ink)"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={segment}
          />
        ))}
        {points.map((point, index) =>
          point.value == null ? null : index === latestIndex ? (
            <circle
              key={point.fiscal_year}
              cx={xFor(index)}
              cy={yFor(point.value)}
              r="7"
              fill="var(--shu)"
              stroke="var(--ink)"
              strokeWidth="2.5"
            />
          ) : (
            <circle
              key={point.fiscal_year}
              cx={xFor(index)}
              cy={yFor(point.value)}
              r="4"
              fill="var(--page)"
              stroke="var(--ink)"
              strokeWidth="2.5"
            />
          ),
        )}
      </svg>
      <div className="font-num mt-2 flex justify-between text-[11px] font-bold text-ink-soft">
        <span>{points[0]?.fiscal_year}</span>
        <span>{points[points.length - 1]?.fiscal_year}</span>
      </div>
      <p className="mt-1 text-xs text-ink-soft">値がある年 {present.length}</p>
    </div>
  )
}

function formatLatest(points: Point[], kind: 'yen' | 'people'): string {
  const latest = [...points].reverse().find((point) => point.value != null)
  if (!latest || latest.value == null) return '—'
  return kind === 'yen' ? formatOkuYen(latest.value) : formatPeople(latest.value)
}
