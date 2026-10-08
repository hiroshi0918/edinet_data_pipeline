// 直近10年度の折れ線。値が無い年は線を切る。
import { formatOkuYen, formatPeople } from '@/lib/format'

type Point = { fiscal_year: number; value: number | null }

export function YearChart({
  title,
  points,
  kind,
}: {
  title: string
  points: Point[]
  kind: 'yen' | 'people'
}) {
  const present = points.filter((point) => point.value != null)
  const width = 360
  const height = 140
  const pad = 18
  if (present.length === 0) {
    return (
      <div className="rounded-xl border border-[#d5e0e3] bg-white p-4">
        <p className="text-sm font-medium text-[#16303a]">{title}</p>
        <p className="mt-2 text-sm text-[#5c7380]">この10年の有報には値がありません。</p>
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

  return (
    <div className="rounded-xl border border-[#d5e0e3] bg-white p-4">
      <p className="text-sm font-medium text-[#16303a]">{title}</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-2 w-full" role="img" aria-label={title}>
        {segments.map((segment) => (
          <polyline
            key={segment}
            fill="none"
            stroke="#1f6f68"
            strokeWidth="2"
            points={segment}
          />
        ))}
        {points.map((point, index) =>
          point.value == null ? null : (
            <circle key={point.fiscal_year} cx={xFor(index)} cy={yFor(point.value)} r="3" fill="#16303a" />
          ),
        )}
      </svg>
      <div className="flex justify-between text-[11px] text-[#5c7380]">
        <span>{points[0]?.fiscal_year}</span>
        <span>{points[points.length - 1]?.fiscal_year}</span>
      </div>
      <p className="mt-1 text-xs text-[#5c7380]">
        最新 {formatLatest(points, kind)} · 値がある年 {present.length}
      </p>
    </div>
  )
}

function formatLatest(points: Point[], kind: 'yen' | 'people'): string {
  const latest = [...points].reverse().find((point) => point.value != null)
  if (!latest || latest.value == null) return '—'
  return kind === 'yen' ? formatOkuYen(latest.value) : formatPeople(latest.value)
}
