// 一覧の1行。1〜3位は王冠つきで大きく出す。社名の前はロゴ。
import { CrownIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { CompanyMark } from '@/components/company-mark'
import { cn } from '@/lib/utils'

export function RankRow({
  rank,
  companyName,
  securitiesCode,
  title,
  meta,
  score,
  podium = rank <= 3,
}: {
  rank: number
  companyName: string
  securitiesCode: string | null
  title: ReactNode
  meta?: ReactNode
  score: number | null
  podium?: boolean
}) {
  return (
    <li
      className={cn(
        'grid grid-cols-[2.75rem_auto_minmax(0,1fr)_auto] items-center gap-x-3 sm:gap-x-4',
        podium
          ? 'sheet mb-3 px-3 py-3 sm:px-5'
          : 'border-b-2 border-dashed border-ink/15 px-3 py-2.5 transition-colors hover:bg-paper-deep/70 sm:px-5',
      )}
    >
      <span className="relative flex items-center justify-center">
        {podium ? (
          <span className="flex size-11 flex-col items-center justify-center rounded-full bg-marker">
            <CrownIcon className="size-4 text-shu" strokeWidth={2.75} aria-hidden="true" />
            <span className="font-num text-sm leading-none font-black text-ink">{rank}</span>
          </span>
        ) : (
          <span className="font-num text-base font-extrabold text-ink-soft">{rank}</span>
        )}
      </span>
      <CompanyMark
        name={companyName}
        securitiesCode={securitiesCode}
        layout="inline"
        className={podium ? 'size-14 rounded-2xl sm:size-16' : 'size-9'}
      />
      <span className="min-w-0">
        <span className={cn('block truncate', podium ? 'text-base font-black sm:text-lg' : 'text-sm font-bold')}>
          {title}
        </span>
        {meta ? <span className="mt-0.5 block truncate text-xs text-ink-soft">{meta}</span> : null}
      </span>
      <span
        className={cn(
          'font-num text-right leading-none font-black text-ink',
          podium ? 'text-3xl sm:text-4xl' : 'text-xl',
        )}
      >
        {score == null ? '—' : score}
      </span>
    </li>
  )
}
