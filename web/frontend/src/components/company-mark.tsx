// 証券コードから logo.dev のロゴを出す。取れないときは社名の頭文字。
// 一覧は一度に何件も頼むと 429 になるので、画面に入ったものから列に載せる。
import { useEffect, useRef, useState } from 'react'

import { logoDevSrc, monogramChar } from '@/lib/company-mark'
import { loadLogo } from '@/lib/logo-queue'
import { cn } from '@/lib/utils'

// 透過だけの画像は社名の頭文字に戻す。
function logoHasInk(image: HTMLImageElement) {
  if (image.naturalWidth === 0 || image.naturalHeight === 0) return true
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

function isAbort(error: unknown) {
  return typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError'
}

function observeWhenVisible(element: Element, onVisible: () => void) {
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      observer.disconnect()
      onVisible()
    },
    { rootMargin: '240px 0px' },
  )
  observer.observe(element)
  return () => observer.disconnect()
}

function useCompanyLogo(url: string | null) {
  const ref = useRef<HTMLDivElement>(null)
  const [trackedUrl, setTrackedUrl] = useState(url)
  const [src, setSrc] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)
  if (url !== trackedUrl) {
    setTrackedUrl(url)
    setSrc(null)
    setMissing(false)
  }

  useEffect(() => {
    if (!url) return
    const element = ref.current
    if (!element) return
    let cancelled = false
    let objectUrl: string | null = null
    const controller = new AbortController()
    const stop = observeWhenVisible(element, () => {
      void loadLogo(url, controller.signal).then(
        (next) => {
          if (cancelled) {
            URL.revokeObjectURL(next)
            return
          }
          objectUrl = next
          setSrc(next)
        },
        (error: unknown) => {
          if (cancelled || isAbort(error)) return
          setMissing(true)
        },
      )
    })
    return () => {
      cancelled = true
      controller.abort()
      stop()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  return { ref, src, missing, markMissing: () => setMissing(true) }
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
  const url = logoDevSrc(securitiesCode, token, size)
  const { ref, src, missing, markMissing } = useCompanyLogo(url)
  const showLogo = Boolean(src) && !missing

  const face = (
    <div
      ref={ref}
      className={cn(
        'flex items-center justify-center overflow-hidden',
        mode === 'inline'
          ? cn(
              'shrink-0 @container',
              showLogo ? 'bg-transparent' : 'rounded-lg bg-[#f5f7fa]',
            )
          : showLogo
            ? 'bg-transparent'
            : 'rounded-lg bg-[#f5f7fa]',
        mode === 'compact' && 'size-8',
        mode === 'badge' && 'size-32 sm:size-40',
        mode === 'inline' && className,
      )}
    >
      {showLogo ? (
        <img
          key={securitiesCode}
          src={src ?? undefined}
          alt={mode === 'compact' ? '' : `${name}のロゴ`}
          decoding="async"
          className="size-full object-contain"
          onError={() => markMissing()}
          onLoad={(event) => {
            try {
              if (!logoHasInk(event.currentTarget)) markMissing()
            } catch {
              // 画素が読めないときは、表示できたロゴを残す。
            }
          }}
        />
      ) : missing || !url ? (
        <span
          className={cn(
            'leading-none font-light text-ink',
            mode === 'compact' ? 'text-sm' : mode === 'inline' ? 'text-[45cqw]' : 'text-5xl sm:text-6xl',
          )}
          aria-hidden="true"
        >
          {monogramChar(name)}
        </span>
      ) : null}
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
  ) : missing || !url ? (
    <span className="text-[10px] leading-none text-ink-soft">社章</span>
  ) : null

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
    <p className={cn('text-xs text-ink', className)}>
      <a
        href="https://logo.dev"
        className="underline decoration-ink-soft/60 underline-offset-2"
      >
        ロゴ: logo.dev
      </a>
    </p>
  )
}
