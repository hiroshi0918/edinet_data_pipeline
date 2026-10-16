// 割合の帯。金額は、触れた区間の上に出す。
import { useLayoutEffect, useRef, useState } from 'react'

import { formatYenShort } from '@/lib/format'

export type HoverSlice = {
  key: string
  label: string
  amount: number
  fill: string
  dark: boolean
  shareLabel: string
  shareText: string
  hint?: string
}

export function HoverBand({ parts, caption, room = 'pt-24' }: { parts: HoverSlice[]; caption: string; room?: string }) {
  const barRef = useRef<HTMLDivElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const segmentRefs = useRef(new Map<string, HTMLButtonElement>())
  const [active, setActive] = useState<string | null>(null)
  const [tipLeft, setTipLeft] = useState(0)
  const activePart = parts.find((part) => part.key === active) ?? null

  useLayoutEffect(() => {
    const bar = barRef.current
    const tip = tipRef.current
    const segment = active ? segmentRefs.current.get(active) : null
    if (!bar || !tip || !segment) return

    function place() {
      if (!bar || !tip || !segment) return
      const barBox = bar.getBoundingClientRect()
      const segBox = segment.getBoundingClientRect()
      const tipBox = tip.getBoundingClientRect()
      const center = segBox.left + segBox.width / 2 - barBox.left
      const next = Math.max(0, Math.min(center - tipBox.width / 2, barBox.width - tipBox.width))
      setTipLeft(next)
    }

    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [active])

  if (parts.length === 0) return null

  return (
    <figure
      onMouseLeave={() => setActive(null)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setActive(null)
      }}
    >
      <div className={room}>
        <div ref={barRef} className="relative">
          <p className={`absolute bottom-full left-0 mb-2 text-xs text-ink-soft ${activePart ? 'invisible' : ''}`}>
            棒に触れると金額が出ます。
          </p>
          <div className="flex h-14 border border-chrome bg-surface">
            {parts.map((part) => (
              <button
                key={part.key}
                type="button"
                ref={(node) => {
                  if (node) segmentRefs.current.set(part.key, node)
                  else segmentRefs.current.delete(part.key)
                }}
                className="h-full min-w-px cursor-pointer border-0 p-0 focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-signal"
                style={{
                  flexGrow: part.amount,
                  flexBasis: 0,
                  backgroundColor: part.fill,
                  boxShadow:
                    active === part.key
                      ? `inset 0 0 0 2px ${part.dark ? 'var(--surface)' : 'var(--carbon)'}`
                      : undefined,
                }}
                onMouseEnter={() => setActive(part.key)}
                onFocus={() => setActive(part.key)}
              >
                <span className="sr-only">{accessibleName(part)}</span>
              </button>
            ))}
          </div>
          {activePart ? (
            <div
              ref={tipRef}
              role="tooltip"
              className="absolute left-0 z-10 w-max max-w-full pb-2"
              style={{ bottom: '100%', transform: `translateX(${tipLeft}px)` }}
            >
              <div className="rounded-lg bg-white px-3 py-2">
                <p className="text-[11px] font-bold text-ink-soft">{activePart.label}</p>
                <p className="font-num text-base font-light text-ink">{formatYenShort(activePart.amount)}</p>
                {activePart.shareText ? (
                  <p className="font-num text-xs text-ink-soft">{activePart.shareText}</p>
                ) : null}
                {activePart.hint ? <p className="mt-1 text-xs leading-5 font-normal text-ink">{activePart.hint}</p> : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>
      <figcaption>
        <p className="mt-2 text-xs text-ink-soft">{caption}</p>
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
          {parts.map((part) => (
            <li key={part.key}>
              <button
                type="button"
                tabIndex={-1}
                className={`flex cursor-pointer items-center gap-2 border-0 px-1 py-0.5 text-left text-xs font-bold text-ink ${active === part.key ? 'bg-platinum' : 'bg-transparent'}`}
                onMouseEnter={() => setActive(part.key)}
                onClick={() => segmentRefs.current.get(part.key)?.focus()}
              >
                <span aria-hidden="true" className="size-3 shrink-0 border border-chrome" style={{ backgroundColor: part.fill }} />
                <span>{part.label}</span>
                {part.shareLabel ? <span className="font-num font-bold text-ink-soft">{part.shareLabel}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  )
}

function accessibleName(part: HoverSlice) {
  return [part.label, formatYenShort(part.amount), part.shareText, part.hint].filter(Boolean).join('、')
}
