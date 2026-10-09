// 見出し。題に蛍光ペン、下に1文。上の小さな赤字は邪魔なので置かない。
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
    <div className={cn('space-y-2', className)}>
      <Tag className="text-3xl leading-tight font-black text-ink sm:text-4xl">
        <span className="marker-line">{title}</span>
      </Tag>
      {description ? <p className="max-w-2xl text-sm leading-7 text-ink-soft sm:text-base">{description}</p> : null}
    </div>
  )
}
