// 採集尺。長さが同業の中での位置。先端の玉が点数。delayMs で上の行から順に満ちる。
import type { CSSProperties } from 'react'

const TICKS = [0, 25, 50, 75, 100]

export function CollectRule({ score, delayMs = 0 }: { score: number | null; delayMs?: number }) {
  const width = score == null ? '0%' : `${Math.min(100, Math.max(0, score))}%`
  const style = { '--rule-delay': `${delayMs}ms` } as CSSProperties
  return (
    <span className="collect-rule mt-3" style={style} aria-hidden="true">
      <span className="collect-rule-track">
        <span className="collect-rule-fill" style={{ width }} />
        {score != null ? <span className="collect-rule-pin" style={{ left: width }} /> : null}
      </span>
      <span className="collect-rule-ticks">
        {TICKS.map((tick) => (
          <span key={tick}>{tick}</span>
        ))}
      </span>
    </span>
  )
}
