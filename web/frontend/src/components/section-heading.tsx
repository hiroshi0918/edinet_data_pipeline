// 見出し。板の上端につく太いラベルと、下に1文。
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function SectionHeading({
  title,
  description,
  as: Tag = 'h1',
  className,
}: {
  title: string
  description?: ReactNode
  as?: 'h1' | 'h2'
  className?: string
}) {
  return (
    <div className={cn(className)}>
      <Tag className="inline-flex border border-chrome bg-canvas px-3 py-2 text-xs font-bold tracking-[0.14em] text-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.45),0_2px_0_var(--chrome)]">
        {title}
      </Tag>
      {description ? <p className="mt-3 max-w-2xl text-sm leading-6 text-ink">{description}</p> : null}
    </div>
  )
}
