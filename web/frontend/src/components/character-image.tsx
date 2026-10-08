// 業種のキャラ。一覧はサムネイル、シートは本体。絵が無い業種はたまご。
import type { CSSProperties } from 'react'

import { EggFigure } from '@/components/egg-figure'
import { specimenPortrait, specimenThumb } from '@/lib/specimen'
import { cn } from '@/lib/utils'

export function CharacterImage({
  industry,
  variant = 'thumb',
  alt = '',
  idle = false,
  bobDelay = 0,
  className,
  eager = false,
}: {
  industry: string | null | undefined
  variant?: 'thumb' | 'full'
  alt?: string
  idle?: boolean
  bobDelay?: number
  className?: string
  eager?: boolean
}) {
  const src = variant === 'full' ? specimenPortrait(industry) : specimenThumb(industry)
  const style = idle ? ({ '--bob-delay': `${bobDelay}s` } as CSSProperties) : undefined

  if (!src) {
    return (
      <EggFigure
        className={cn('h-full w-auto', variant === 'full' && 'p-[16%]', idle && 'idle-bob', className)}
      />
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      draggable={false}
      style={style}
      className={cn('on-paper object-contain select-none', idle && 'idle-bob', className)}
    />
  )
}
