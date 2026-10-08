// 証券コードから logo.dev のロゴを出す。取れないときは社名の頭文字。
import { useState } from 'react'

import { monogramChar, tokyoTicker } from '@/lib/company-mark'

export function CompanyMark({
  name,
  securitiesCode,
}: {
  name: string
  securitiesCode: string | null
}) {
  const token = import.meta.env.VITE_LOGO_DEV_PUBLISHABLE_KEY
  const ticker = tokyoTicker(securitiesCode)
  const [failed, setFailed] = useState(false)
  const showLogo = Boolean(token && ticker && !failed)

  return (
    <div className="flex w-16 shrink-0 flex-col items-center gap-1 sm:w-20">
      <div className="flex size-16 items-center justify-center overflow-hidden border border-ink bg-label sm:size-20">
        {showLogo ? (
          <img
            src={`https://img.logo.dev/ticker/${encodeURIComponent(ticker ?? '')}?token=${encodeURIComponent(token ?? '')}&format=png&size=128&retina=true&fallback=404`}
            alt={`${name}のロゴ`}
            className="size-full object-contain"
            onError={() => setFailed(true)}
          />
        ) : (
          <span className="font-display text-2xl leading-none text-ink sm:text-3xl" aria-hidden="true">
            {monogramChar(name)}
          </span>
        )}
      </div>
      {showLogo ? (
        <a
          href="https://logo.dev"
          className="font-mono text-[10px] leading-none text-pencil underline decoration-pencil/60 underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-habitat"
        >
          ロゴ: logo.dev
        </a>
      ) : (
        <span className="font-mono text-[10px] leading-none text-pencil">社章</span>
      )}
    </div>
  )
}
