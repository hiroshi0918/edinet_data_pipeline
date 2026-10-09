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
  const src = logoDevSrc(securitiesCode, token, compact ? 64 : 128)
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
        compact ? undefined : 'flex w-16 flex-col items-center gap-1 sm:w-20',
      )}
    >
      <div
        className={cn(
          'flex items-center justify-center overflow-hidden border-[length:var(--line)] border-ink bg-page',
          compact
            ? 'size-8 rounded-lg'
            : 'size-16 rounded-2xl shadow-ink-sm sm:size-20',
        )}
      >
        {showLogo ? (
          <img
            src={src ?? undefined}
            alt={compact ? '' : `${name}のロゴ`}
            className={cn('size-full object-contain', compact ? 'p-0.5' : 'p-1')}
            onError={() => setFailed(true)}
          />
        ) : (
          <span
            className={cn(
              'leading-none font-black text-ink',
              compact ? 'text-sm' : 'text-2xl sm:text-3xl',
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
