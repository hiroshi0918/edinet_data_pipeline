// 見出し。上に小さな見出し、題に蛍光ペン、下に1文。
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function SectionHeading({
  kicker,
  title,
  description,
  as: Tag = 'h1',
  className,
}: {
  kicker?: ReactNode
  title: string
  description?: ReactNode
  as?: 'h1' | 'h2'
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {kicker ? <p className="font-num text-xs font-extrabold tracking-[0.18em] text-shu">{kicker}</p> : null}
      <Tag className="text-3xl leading-tight font-black text-ink sm:text-4xl">
        <span className="marker-line">{title}</span>
      </Tag>
      {description ? <p className="max-w-2xl text-sm leading-7 text-ink-soft sm:text-base">{description}</p> : null}
    </div>
  )
}
