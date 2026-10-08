// 採集尺。長さが同業の中での位置。針は点数の先端。
const TICKS = [0, 25, 50, 75, 100]

export function CollectRule({ score }: { score: number | null }) {
  const width = score == null ? '0%' : `${Math.min(100, Math.max(0, score))}%`
  return (
    <span className="collect-rule mt-3" aria-hidden="true">
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
