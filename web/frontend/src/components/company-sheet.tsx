// 最新有報の標本ラベル。点を先に出し、実数は行を開くと出る。
import { useState } from 'react'
import { Link } from 'react-router'

import { CollectRule } from '@/components/collect-rule'
import { CompanyMark } from '@/components/company-mark'
import { SpecimenFigure } from '@/components/specimen-figure'
import { HC_METRIC_LABELS } from '@/lib/constants'
import {
  formatAge,
  formatManYen,
  formatMultiple,
  formatOkuYen,
  formatPeople,
  formatPct,
  formatRatioAsPct,
  formatYears,
} from '@/lib/format'
import type {
  SheetAxis,
  SheetExpectationAxis,
  SheetPeopleAxis,
  SheetPercentileAxis,
  SheetResponse,
} from '@/lib/types'
import { cn } from '@/lib/utils'

function scoreText(score: number | null): string {
  return score == null ? '—' : String(score)
}

function blankReason(axis: SheetAxis): string {
  if (axis.key === 'expectation' && axis.value == null) return '株価が揃うと点が出ます。'
  if (axis.key === 'operating_margin' && axis.value == null) {
    return '売上が無いため、率は出ません。'
  }
  if (axis.key === 'people') {
    if (axis.metrics.every((metric) => metric.value == null)) {
      return '人の3指標はこの年度の有報にありません。'
    }
    if (axis.metrics.some((metric) => metric.value != null && metric.peer_count < 5)) {
      return '比べられる会社が5社未満です。'
    }
  }
  if (axis.peer_count != null && axis.peer_count < 5) {
    return '比べられる会社が5社未満です。'
  }
  if (axis.value == null) return 'この年度の有報に値がありません。'
  return '点は出ていません。'
}

function formatFaceValue(axis: SheetPercentileAxis | SheetExpectationAxis): string {
  switch (axis.key) {
    case 'sales':
      return formatOkuYen(axis.value)
    case 'employee_count':
      return formatPeople(axis.value)
    case 'operating_margin':
      return formatRatioAsPct(axis.value)
    case 'average_annual_salary':
      return formatManYen(axis.value)
    case 'average_years_of_service':
      return formatYears(axis.value)
    case 'expectation':
      return formatMultiple(axis.value)
  }
}

function psrBasisText(basis: SheetExpectationAxis['psr_basis']): string | null {
  if (basis === 'close') return '決算月の終値'
  if (basis === 'reported_per') return '有報の株価収益率'
  return null
}

function DisclosureStamp({ score }: { score: number | null }) {
  const marked = score != null
  return (
    <span
      className={cn(
        'inline-flex size-12 shrink-0 items-center justify-center rounded-full border-2 font-mono text-sm tabular-nums',
        marked ? 'border-stamp text-stamp' : 'border-pencil text-pencil',
      )}
    >
      {scoreText(score)}
    </span>
  )
}

function AxisRow({
  axis,
  open,
  onToggle,
}: {
  axis: SheetAxis
  open: boolean
  onToggle: () => void
}) {
  const panelId = `sheet-axis-${axis.key}`
  return (
    <div className="py-4">
      <button
        type="button"
        className="w-full cursor-pointer text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-habitat"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span className="flex items-baseline justify-between gap-3">
          <span>
            <span className="block font-mono text-[11px] text-pencil">{axis.nickname}</span>
            <span className="mt-0.5 block text-sm">{axis.label}</span>
          </span>
          <span className="font-mono text-4xl leading-none tabular-nums">{scoreText(axis.score)}</span>
        </span>
        <CollectRule score={axis.score} />
        {axis.key === 'people' ? (
          <span className="mt-3 flex items-center gap-3">
            <DisclosureStamp score={axis.disclosure.score} />
            <span>
              <span className="block font-mono text-[11px] text-pencil">
                {axis.disclosure.nickname}
              </span>
              <span className="mt-0.5 block text-sm">{axis.disclosure.label}</span>
            </span>
          </span>
        ) : null}
      </button>
      {open ? (
        <div id={panelId} className="mt-3 space-y-2 border-t border-pencil/30 pt-3 text-sm">
          <p className="text-pencil">有報の値</p>
          {axis.key === 'people' ? <PeopleFacts axis={axis} /> : <FaceFacts axis={axis} />}
          {axis.score == null ? <p className="text-pencil">{blankReason(axis)}</p> : null}
          {axis.peer_count != null ? (
            <p className="text-xs text-pencil">比べた会社 {axis.peer_count}社</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function FaceFacts({ axis }: { axis: SheetPercentileAxis | SheetExpectationAxis }) {
  const basis = axis.key === 'expectation' ? psrBasisText(axis.psr_basis) : null
  return (
    <div className="space-y-1">
      <p className="font-mono text-lg tabular-nums text-ink">{formatFaceValue(axis)}</p>
      {axis.key === 'expectation' && axis.per != null ? (
        <p className="font-mono tabular-nums text-ink">実績PER {formatMultiple(axis.per)}</p>
      ) : null}
      {basis ? <p className="text-pencil">{basis}</p> : null}
    </div>
  )
}

function PeopleFacts({ axis }: { axis: SheetPeopleAxis }) {
  return (
    <dl className="space-y-1">
      {axis.metrics.map((metric) => (
        <div key={metric.key} className="flex justify-between gap-3">
          <dt className="text-pencil">{HC_METRIC_LABELS[metric.key]}</dt>
          <dd className="font-mono tabular-nums text-ink">{formatPct(metric.value)}</dd>
        </div>
      ))}
      <div className="flex justify-between gap-3">
        <dt className="text-pencil">平均年齢</dt>
        <dd className="font-mono tabular-nums text-ink">{formatAge(axis.average_age)}</dd>
      </div>
    </dl>
  )
}

export function CompanySheet({ sheet }: { sheet: SheetResponse }) {
  const [openKey, setOpenKey] = useState<string | null>(null)

  return (
    <section className="plate px-5 pt-5 pr-16 pb-6 sm:px-8 sm:pt-6 sm:pr-24 sm:pb-8">
      {sheet.fiscal_year != null ? (
        <p className="text-right font-mono text-xs text-pencil">{sheet.fiscal_year}年度</p>
      ) : null}
      <div className="mt-4 grid items-start gap-8 lg:grid-cols-[minmax(18rem,30rem)_minmax(0,1fr)] lg:gap-10">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <SpecimenFigure industry={sheet.industry} level={sheet.level} />
        </div>
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-4">
            <p className="font-mono text-xs text-pencil">{sheet.edinet_code}</p>
            <div className="shrink-0 text-right">
              <p className="font-mono text-[11px] text-pencil">総合</p>
              <p className="font-mono text-5xl leading-none tabular-nums text-ink sm:text-6xl">
                {scoreText(sheet.level)}
              </p>
            </div>
          </div>
          <div className="mt-2 flex items-start gap-3 sm:gap-4">
            <CompanyMark name={sheet.company_name} securitiesCode={sheet.securities_code} />
            <div className="min-w-0 flex-1">
              <h1 className="font-display text-3xl leading-tight text-ink sm:text-4xl">{sheet.company_name}</h1>
              <p className="mt-2 text-sm text-pencil">{sheet.industry ?? '業種なし'}</p>
              <Link
                className="mt-3 inline-block text-sm text-ink underline decoration-pencil underline-offset-4 hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-habitat"
                to={`/companies/${sheet.edinet_code}/story`}
              >
                歩みを見る
              </Link>
            </div>
          </div>
          <div className="mt-6 divide-y divide-pencil/30 border-y border-pencil/30">
            {sheet.axes.map((axis) => (
              <AxisRow
                key={axis.key}
                axis={axis}
                open={openKey === axis.key}
                onToggle={() => setOpenKey((current) => (current === axis.key ? null : axis.key))}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
