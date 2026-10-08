// 1社の直近10年度の折れ線。目盛りと年は LineChart が描く。最新年だけ朱の点。
import { LineChart } from '@/components/line-chart'
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
  if (present.length === 0) {
    return (
      <div className="sheet p-5">
        <p className="text-sm font-black text-ink">{title}</p>
        <p className="mt-2 text-sm text-ink-soft">この10年の有報には値がありません。</p>
      </div>
    )
  }

  return (
    <div className="sheet p-5">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-black text-ink">{title}</p>
        <p className="font-num text-lg font-black text-ink">{formatLatest(points, kind)}</p>
      </div>
      <div className="mt-3">
        <LineChart
          title={title}
          kind={kind}
          delayMs={delayMs}
          years={points.map((point) => point.fiscal_year)}
          series={[{ key: 'value', label: title, color: 'var(--ink)', values: points.map((point) => point.value) }]}
        />
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
