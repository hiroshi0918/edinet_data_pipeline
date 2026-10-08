// 0–100% のパリティバー。色は赤（低）→緑（高）。
import { formatPct } from '@/lib/format'

export function RatioBar({
  label,
  value,
}: {
  label: string
  value: number | null | undefined
}) {
  const clamped =
    value == null || Number.isNaN(value)
      ? null
      : Math.min(100, Math.max(0, value))
  const hue = clamped == null ? 0 : (clamped / 100) * 140

  return (
    <div className="space-y-2 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{formatPct(value)}</span>
      </div>
      <div className="h-2 rounded-full bg-muted">
        <div
          className="h-2 rounded-full transition-all"
          style={{
            width: `${clamped ?? 0}%`,
            backgroundColor:
              clamped == null ? 'transparent' : `hsl(${hue} 70% 42%)`,
          }}
        />
      </div>
    </div>
  )
}
