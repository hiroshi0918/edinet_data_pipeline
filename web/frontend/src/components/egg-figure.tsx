// 絵の無い業種と読込中に出す、たまご。
import { cn } from '@/lib/utils'

export function EggFigure({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 140" className={cn('overflow-visible', className)} aria-hidden="true">
      <ellipse cx="60" cy="132" rx="30" ry="5" fill="var(--ink)" opacity="0.12" />
      <path
        d="M60 10C34 10 16 52 16 82c0 28 19 46 44 46s44-18 44-46C104 52 86 10 60 10Z"
        fill="var(--page)"
        stroke="var(--ink)"
        strokeWidth="4"
      />
      <path d="M30 70c10-6 20 4 30-2s20-8 30 0" fill="none" stroke="var(--shu)" strokeWidth="4" strokeLinecap="round" />
      <circle cx="44" cy="92" r="6" fill="var(--marker)" stroke="var(--ink)" strokeWidth="3" />
      <circle cx="76" cy="100" r="4" fill="var(--marker)" stroke="var(--ink)" strokeWidth="3" />
      <path d="M40 36c-6 8-9 16-10 24" fill="none" stroke="var(--page)" strokeWidth="5" strokeLinecap="round" opacity="0.9" />
    </svg>
  )
}
