// 一覧の1行。上位3つは琥珀の順位印と白い板。社名の前はロゴ。
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
        'grid grid-cols-[2.25rem_auto_minmax(0,1fr)_auto] items-center gap-x-3 sm:gap-x-4',
        podium
          ? 'sheet mb-2 px-3 py-3 sm:px-4'
          : 'border-b border-chrome/25 bg-platinum/80 px-3 py-2.5 transition-colors hover:bg-surface sm:px-4',
      )}
    >
      <span
        className={cn(
          'font-num flex size-8 items-center justify-center text-sm font-black',
          podium ? 'bg-amber text-carbon' : 'text-chrome',
        )}
      >
        {rank}
      </span>
      <CompanyMark
        name={companyName}
        securitiesCode={securitiesCode}
        layout="inline"
        className={podium ? 'size-12 sm:size-14' : 'size-9'}
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
        {score == null ? (
          '—'
        ) : (
          <>
            {score}
            <span className={cn('ml-0.5 font-bold text-ink-soft', podium ? 'text-sm' : 'text-xs')}>点</span>
          </>
        )}
      </span>
    </li>
  )
}

// 一覧の右の点が何の点かを、見出しのすぐ下に小さく1行で書く。
export function ScoreNote({ axisLabel }: { axisLabel?: string }) {
  const what = !axisLabel || axisLabel === '総合' ? '総合点' : `${axisLabel}の点`
  return <p className="text-xs text-ink">同じ業種の会社と比べた{what}（100点満点）</p>
}
