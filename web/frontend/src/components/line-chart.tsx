// 年度の折れ線。縦軸は 0 を含む目盛りと単位、横軸は年。値が無い年は線を切る。
// 1社なら最新年だけ朱の点。2社以上なら会社ごとの色で、2本目以降は点線にして色に頼らず見分ける。
import type { CSSProperties } from 'react'

import { buildAxis, type ChartKind, formatTick, yearLabelIndexes } from '@/lib/chart-scale'

export type LineSeries = {
  key: string
  label: string
  color: string
  values: (number | null)[]
}

const WIDTH = 360
const HEIGHT = 200
const PAD = { top: 22, right: 14, bottom: 26, left: 44 }

export function LineChart({
  title,
  years,
  series,
  kind,
  delayMs = 0,
}: {
  title: string
  years: number[]
  series: LineSeries[]
  kind: ChartKind
  delayMs?: number
}) {
  const values = series.flatMap((line) => line.values.filter((value): value is number => value != null))
  const axis = buildAxis(values, kind)
  const plotWidth = WIDTH - PAD.left - PAD.right
  const plotHeight = HEIGHT - PAD.top - PAD.bottom
  const span = axis.max - axis.min || 1
  const xFor = (index: number) => PAD.left + (index * plotWidth) / Math.max(years.length - 1, 1)
  const yFor = (value: number) => PAD.top + plotHeight - ((value - axis.min) / span) * plotHeight
  const single = series.length === 1
  const style = { '--draw-delay': `${delayMs}ms` } as CSSProperties

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full overflow-visible" role="img" aria-label={`${title}（${axis.unit}）`}>
      <text x={PAD.left - 8} y={10} textAnchor="end" className="font-num" fontSize="11" fontWeight="800" fill="var(--ink-soft)">
        {axis.unit}
      </text>
      {axis.ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={yFor(tick)}
            y2={yFor(tick)}
            stroke="var(--ink)"
            strokeOpacity={tick === 0 ? 0.45 : 0.12}
            strokeWidth={tick === 0 ? 2 : 1.5}
            strokeDasharray={tick === 0 ? undefined : '3 5'}
          />
          <text
            x={PAD.left - 8}
            y={yFor(tick)}
            dy="0.35em"
            textAnchor="end"
            className="font-num"
            fontSize="11"
            fontWeight="700"
            fill="var(--ink-soft)"
          >
            {formatTick(tick, axis.divisor)}
          </text>
        </g>
      ))}
      {yearLabelIndexes(years.length).map((index) => (
        <text
          key={years[index]}
          x={xFor(index)}
          y={HEIGHT - 6}
          textAnchor="middle"
          className="font-num"
          fontSize="11"
          fontWeight="700"
          fill="var(--ink-soft)"
        >
          {years[index]}
        </text>
      ))}
      {series.map((line, seriesIndex) => {
        const dashed = !single && seriesIndex > 0
        const latestIndex = line.values.findLastIndex((value) => value != null)
        return (
          <g key={line.key}>
            {segmentsFor(line.values, xFor, yFor).map((segment) => (
              <polyline
                key={segment}
                className={dashed ? undefined : 'draw-line'}
                style={dashed ? undefined : style}
                pathLength={dashed ? undefined : 1}
                fill="none"
                stroke={line.color}
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={dashed ? '7 6' : undefined}
                points={segment}
              />
            ))}
            {line.values.map((value, index) => {
              if (value == null) return null
              const latest = index === latestIndex
              return (
                <circle
                  key={years[index]}
                  cx={xFor(index)}
                  cy={yFor(value)}
                  r={latest ? (single ? 7 : 6) : 4}
                  fill={single ? (latest ? 'var(--shu)' : 'var(--page)') : latest ? line.color : 'var(--page)'}
                  stroke={single ? 'var(--ink)' : line.color}
                  strokeWidth="2.5"
                />
              )
            })}
          </g>
        )
      })}
    </svg>
  )
}

function segmentsFor(
  values: (number | null)[],
  xFor: (index: number) => number,
  yFor: (value: number) => number,
): string[] {
  const segments: string[] = []
  let current: string[] = []
  values.forEach((value, index) => {
    if (value == null) {
      if (current.length > 1) segments.push(current.join(' '))
      current = []
      return
    }
    current.push(`${xFor(index)},${yFor(value)}`)
  })
  if (current.length > 1) segments.push(current.join(' '))
  return segments
}
