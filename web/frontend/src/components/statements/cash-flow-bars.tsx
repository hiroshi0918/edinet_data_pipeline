// 1年のお金の出入り。中央の線から右が入ったお金、左が出ていったお金。
import { formatYenShort } from '@/lib/format'
import type { CashFlowRow } from '@/lib/statements'

export function CashFlowBars({ rows }: { rows: CashFlowRow[] }) {
  const largest = Math.max(1, ...rows.map((row) => Math.abs(row.value ?? 0)))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_1fr] text-xs font-bold text-ink-soft sm:ml-[12rem] sm:mr-[7.5rem]">
        <span>← 出ていった</span>
        <span className="text-right">入ってきた →</span>
      </div>
      <ol className="space-y-4">
        {rows.map((row) => {
          const width = row.value == null ? 0 : (Math.abs(row.value) / largest) * 50
          const inflow = (row.value ?? 0) >= 0
          return (
            <li key={row.key} className="grid gap-x-3 gap-y-1 sm:grid-cols-[11rem_1fr_6.5rem] sm:items-center">
              <div>
                <p className="text-sm font-medium text-ink">{row.label}</p>
                <p className="text-xs text-ink-soft">{row.hint}</p>
              </div>
              <div className="relative h-7 bg-platinum/60">
                <span aria-hidden="true" className="absolute inset-y-0 left-1/2 w-px bg-ink/50" />
                {row.value != null ? (
                  <span
                    aria-hidden="true"
                    className="absolute inset-y-1"
                    style={{
                      left: inflow ? '50%' : `${50 - width}%`,
                      width: `max(${width}%, 2px)`,
                      backgroundColor: inflow ? 'var(--systems-teal)' : 'var(--carbon)',
                    }}
                  />
                ) : null}
              </div>
              <p className="text-right font-num text-sm text-ink">{describe(row.value)}</p>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function describe(value: number | null) {
  if (value == null) return '—'
  if (value >= 0) return `+${formatYenShort(value)} 入った`
  return `${formatYenShort(value)} 出た`
}
