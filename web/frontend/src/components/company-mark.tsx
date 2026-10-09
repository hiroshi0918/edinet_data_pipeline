// 証券コードから logo.dev のロゴを出す。取れないときは社名の頭文字。
import { useState } from 'react'

import { logoDevSrc, monogramChar } from '@/lib/company-mark'
import { cn } from '@/lib/utils'

export function CompanyMark({
  name,
  securitiesCode,
  compact = false,
}: {
  name: string
  securitiesCode: string | null
  compact?: boolean
}) {
  const token = import.meta.env.VITE_LOGO_DEV_PUBLISHABLE_KEY
  const src = logoDevSrc(securitiesCode, token, compact ? 64 : 256)
  const [failed, setFailed] = useState(false)
  const showLogo = Boolean(src && !failed)
  const caption = showLogo ? (
    <a
      href="https://logo.dev"
      className="text-[10px] leading-none text-ink-soft underline decoration-ink-soft/60 underline-offset-2"
    >
      ロゴ: logo.dev
    </a>
  ) : (
    <span className="text-[10px] leading-none text-ink-soft">社章</span>
  )

  return (
    <div
      className={cn(
        'shrink-0',
        compact ? undefined : 'flex w-32 flex-col items-center gap-1.5 sm:w-40',
      )}
    >
      <div
        className={cn(
          'flex items-center justify-center overflow-hidden',
          showLogo
            ? 'bg-transparent'
            : 'border-[length:var(--line)] border-ink bg-page',
          compact
            ? 'size-8 rounded-lg'
            : cn('size-32 rounded-3xl sm:size-40', showLogo ? undefined : 'shadow-ink'),
        )}
      >
        {showLogo ? (
          <img
            src={src ?? undefined}
            alt={compact ? '' : `${name}のロゴ`}
            className="size-full object-contain"
            onError={() => setFailed(true)}
          />
        ) : (
          <span
            className={cn(
              'leading-none font-black text-ink',
              compact ? 'text-sm' : 'text-5xl sm:text-6xl',
            )}
            aria-hidden="true"
          >
            {monogramChar(name)}
          </span>
        )}
      </div>
      {compact ? null : caption}
    </div>
  )
}
