// 見出し。細い大きな文字と、その下の1文。
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
      <Tag className="text-[1.75rem] leading-tight font-light text-ink sm:text-[2.75rem]">{title}</Tag>
      {description ? <p className="mt-3 max-w-xl text-base leading-relaxed text-black/60">{description}</p> : null}
    </div>
  )
}
