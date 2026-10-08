// 開示の点。朱の判子が少し傾いて押される。点が無いときは墨の薄い円。
import type { CSSProperties } from 'react'

import { cn } from '@/lib/utils'

export function HankoStamp({ score, delayMs = 0 }: { score: number | null; delayMs?: number }) {
  const marked = score != null
  return (
    <span
      style={{ '--hanko-delay': `${delayMs}ms` } as CSSProperties}
      className={cn(
        'hanko font-num inline-flex size-14 shrink-0 items-center justify-center rounded-full text-lg font-black',
        marked
          ? 'border-[3px] border-shu text-shu shadow-[inset_0_0_0_3px_var(--page),inset_0_0_0_4.5px_var(--shu)]'
          : 'border-2 border-dashed border-ink-soft text-ink-soft',
      )}
    >
      {marked ? score : '—'}
    </span>
  )
}
