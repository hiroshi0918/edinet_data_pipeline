// 証券コードから logo.dev のロゴを出す。取れないときは社名の頭文字。
import { useEffect, useRef, useState } from 'react'

import { logoDevSrc, monogramChar } from '@/lib/company-mark'
import { cn } from '@/lib/utils'

// 透過だけの画像は社名の頭文字に戻す。
function logoHasInk(image: HTMLImageElement) {
  const canvas = document.createElement('canvas')
  canvas.width = 16
  canvas.height = 16
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return true
  ctx.drawImage(image, 0, 0, 16, 16)
  const pixels = ctx.getImageData(0, 0, 16, 16).data
  for (let index = 3; index < pixels.length; index += 4) {
    if (pixels[index] > 24) return true
  }
  return false
}

export function CompanyMark({
  name,
  securitiesCode,
  compact = false,
  layout = 'badge',
  className,
}: {
  name: string
  securitiesCode: string | null
  /** 検索候補の小さい社章。キャプションは出さない。 */
  compact?: boolean
  /** badge はシートの社章。inline は一覧の行頭。 */
  layout?: 'badge' | 'inline'
  className?: string
}) {
  const token = import.meta.env.VITE_LOGO_DEV_PUBLISHABLE_KEY
  const mode = compact ? 'compact' : layout
  const size = mode === 'compact' ? 64 : mode === 'inline' ? 128 : 256
  const [logoAttempt, setLogoAttempt] = useState({ code: securitiesCode, attempt: 0 })
  const retryTimer = useRef<number | null>(null)
  // 前の会社で透過ロゴや取得失敗になると attempt が 2 のまま残る。別の証券コードでは最初から試す。
  if (logoAttempt.code !== securitiesCode) {
    setLogoAttempt({ code: securitiesCode, attempt: 0 })
  }
  const attempt = logoAttempt.code === securitiesCode ? logoAttempt.attempt : 0
  const setAttempt = (next: number) => {
    setLogoAttempt((current) =>
      current.code === securitiesCode ? { code: securitiesCode, attempt: next } : current,
    )
  }
  const src = attempt < 2 ? logoDevSrc(securitiesCode, token, size, attempt) : null
  const showLogo = Boolean(src)

  useEffect(() => {
    return () => {
      if (retryTimer.current != null) {
        window.clearTimeout(retryTimer.current)
        retryTimer.current = null
      }
    }
  }, [securitiesCode])

  const face = (
    <div
      className={cn(
        'flex items-center justify-center overflow-hidden',
        mode === 'inline'
          ? 'shrink-0 border-[length:var(--line)] border-ink bg-page @container rounded-xl'
          : showLogo
            ? 'bg-transparent'
            : 'border-[length:var(--line)] border-ink bg-page',
        mode === 'compact' && 'size-8 rounded-lg',
        mode === 'badge' && cn('size-32 rounded-3xl sm:size-40', showLogo ? undefined : 'shadow-ink'),
        mode === 'inline' && className,
      )}
    >
      {showLogo ? (
        <img
          key={securitiesCode}
          src={src ?? undefined}
          alt={mode === 'compact' ? '' : `${name}のロゴ`}
          crossOrigin="anonymous"
          loading={mode === 'inline' ? 'lazy' : 'eager'}
          decoding="async"
          className={cn('size-full object-contain', mode === 'inline' && 'p-0.5')}
          onLoad={(event) => {
            try {
              if (!logoHasInk(event.currentTarget)) setAttempt(2)
            } catch {
              // 画素が読めないときは、表示できたロゴを残す。
            }
          }}
          onError={() => {
            if (attempt > 0) {
              setAttempt(2)
              return
            }
            if (retryTimer.current != null) return
            retryTimer.current = window.setTimeout(() => setAttempt(1), 800)
          }}
        />
      ) : (
        <span
          className={cn(
            'leading-none font-black text-ink',
            mode === 'compact' ? 'text-sm' : mode === 'inline' ? 'text-[45cqw]' : 'text-5xl sm:text-6xl',
          )}
          aria-hidden="true"
        >
          {monogramChar(name)}
        </span>
      )}
    </div>
  )

  if (mode === 'compact') return <div className="shrink-0">{face}</div>
  if (mode === 'inline') return face

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
    <div className="flex w-32 shrink-0 flex-col items-center gap-1.5 sm:w-40">
      {face}
      {caption}
    </div>
  )
}

export function LogoCredit({ className }: { className?: string }) {
  if (!import.meta.env.VITE_LOGO_DEV_PUBLISHABLE_KEY) return null
  return (
    <p className={cn('text-xs text-ink-soft', className)}>
      <a
        href="https://logo.dev"
        className="underline decoration-ink-soft/60 underline-offset-2"
      >
        ロゴ: logo.dev
      </a>
    </p>
  )
}
