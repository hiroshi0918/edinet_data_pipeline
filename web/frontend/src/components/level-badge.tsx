// 総合点の白い板。段階名と、段階の数だけの星。星は印なので琥珀。
import { STAGE_LABEL, specimenStage } from '@/lib/specimen'
import { cn } from '@/lib/utils'

function Star({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="size-3.5" aria-hidden="true">
      <path
        d="M12 2.8l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 16.8l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"
        fill={filled ? 'var(--amber)' : 'var(--surface)'}
        stroke="var(--carbon)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function LevelBadge({ level, className }: { level: number | null; className?: string }) {
  const stage = specimenStage(level)
  return (
    <div
      className={cn(
        'flex size-28 shrink-0 flex-col items-center justify-center border border-chrome bg-surface shadow-[inset_0_1px_0_#fff,0_2px_0_var(--chrome)] sm:size-32',
        className,
      )}
    >
      <p className="text-[11px] leading-none font-bold tracking-wide text-chrome">総合</p>
      <p className="font-num mt-1 text-5xl leading-none font-black text-ink sm:text-[3.5rem]">
        {level == null ? '—' : level}
      </p>
      <p className="mt-1 text-[11px] leading-none font-bold text-ink">{STAGE_LABEL[stage]}</p>
      <div className="mt-1 flex gap-0.5" aria-label={`段階 ${stage} / 4`} role="img">
        {[1, 2, 3, 4].map((index) => (
          <Star key={index} filled={index <= stage} />
        ))}
      </div>
    </div>
  )
}
