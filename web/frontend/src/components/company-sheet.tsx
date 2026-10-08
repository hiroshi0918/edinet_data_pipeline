// 最新有報のキャラクターシート。点を先に出し、実数はカードを開くと出る。
import { useState } from 'react'
import { Link } from 'react-router'

import { HC_METRIC_LABELS } from '@/lib/constants'
import {
  formatAge,
  formatManYen,
  formatOkuYen,
  formatPeople,
  formatMultiple,
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

function Gauge({
  score,
  tone,
}: {
  score: number | null
  tone: 'position' | 'disclosure'
}) {
  const width = score == null ? 0 : Math.min(100, Math.max(0, score))
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[#d7e2e4]">
      <div
        className={cn(
          'h-full motion-safe:transition-[width] motion-safe:duration-300',
          tone === 'disclosure' ? 'bg-[#c46b3a]' : 'bg-[#1f6f68]',
        )}
        style={{ width: `${width}%` }}
      />
    </div>
  )
}

function AxisCard({
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
    <div
      className={cn(
        'rounded-xl border border-[#d5e0e3] bg-white p-4',
        axis.key === 'people' && 'sm:col-span-2',
      )}
    >
      <button
        type="button"
        className="w-full space-y-3 text-left"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <p className="text-[11px] tracking-[0.14em] text-[#5c7380]">{axis.nickname}</p>
            <p className="text-sm font-medium text-[#16303a]">{axis.label}</p>
          </div>
          <p className="text-4xl font-semibold tabular-nums tracking-tight text-[#16303a]">
            {scoreText(axis.score)}
          </p>
        </div>
        <Gauge score={axis.score} tone="position" />
        {axis.key === 'people' ? <DisclosureGauge axis={axis} /> : null}
      </button>
      {open ? (
        <div id={panelId} className="mt-4 space-y-2 border-t border-[#e4ecee] pt-3 text-sm">
          <p className="text-[#5c7380]">有報の値</p>
          {axis.key === 'people' ? (
            <PeopleFacts axis={axis} />
          ) : (
            <FaceFacts axis={axis} />
          )}
          {axis.score == null ? <p className="text-[#5c7380]">{blankReason(axis)}</p> : null}
          {axis.peer_count != null ? (
            <p className="text-xs text-[#5c7380]">比べた会社 {axis.peer_count}社</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function DisclosureGauge({ axis }: { axis: SheetPeopleAxis }) {
  const disclosure = axis.disclosure
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs text-[#5c7380]">
        <span>
          {disclosure.nickname} <span className="text-[#16303a]">{disclosure.label}</span>
        </span>
        <span className="text-lg font-semibold tabular-nums text-[#16303a]">
          {scoreText(disclosure.score)}
        </span>
      </div>
      <Gauge score={disclosure.score} tone="disclosure" />
    </div>
  )
}

function FaceFacts({ axis }: { axis: SheetPercentileAxis | SheetExpectationAxis }) {
  const basis = axis.key === 'expectation' ? psrBasisText(axis.psr_basis) : null
  return (
    <div className="space-y-1">
      <p className="text-lg font-medium tabular-nums text-[#16303a]">{formatFaceValue(axis)}</p>
      {axis.key === 'expectation' && axis.per != null ? (
        <p className="tabular-nums text-[#16303a]">実績PER {formatMultiple(axis.per)}</p>
      ) : null}
      {basis ? <p className="text-[#5c7380]">{basis}</p> : null}
    </div>
  )
}

function PeopleFacts({ axis }: { axis: SheetPeopleAxis }) {
  return (
    <dl className="space-y-1">
      {axis.metrics.map((metric) => (
        <div key={metric.key} className="flex justify-between gap-3">
          <dt className="text-[#5c7380]">{HC_METRIC_LABELS[metric.key]}</dt>
          <dd className="tabular-nums text-[#16303a]">{formatPct(metric.value)}</dd>
        </div>
      ))}
      <div className="flex justify-between gap-3">
        <dt className="text-[#5c7380]">平均年齢</dt>
        <dd className="tabular-nums text-[#16303a]">{formatAge(axis.average_age)}</dd>
      </div>
    </dl>
  )
}

export function CompanySheet({ sheet }: { sheet: SheetResponse }) {
  const [openKey, setOpenKey] = useState<string | null>(null)

  return (
    <section className="space-y-6 rounded-2xl bg-[#e7eef2] p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-[#5c7380]">
            {sheet.industry ?? '業種なし'}
            {sheet.fiscal_year != null ? ` · ${sheet.fiscal_year}年度` : ''}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-[#16303a]">
            {sheet.company_name}
          </h1>
          <p className="font-mono text-xs text-[#5c7380]">{sheet.edinet_code}</p>
          <Link
            className="mt-2 inline-block text-sm font-medium text-[#1f6f68] hover:underline"
            to={`/companies/${sheet.edinet_code}/story`}
          >
            歩みを見る
          </Link>
        </div>
        <div className="text-right">
          <p className="text-[11px] tracking-[0.16em] text-[#5c7380]">総合</p>
          <p className="text-6xl font-semibold tabular-nums leading-none text-[#16303a]">
            {scoreText(sheet.level)}
          </p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {sheet.axes.map((axis) => (
          <AxisCard
            key={axis.key}
            axis={axis}
            open={openKey === axis.key}
            onToggle={() => setOpenKey((current) => (current === axis.key ? null : axis.key))}
          />
        ))}
      </div>
    </section>
  )
}
