// 最新有報の図鑑の見開き。左にすみかとキャラ、右に総合点とステータス。実数は行を開くと出る。
import {
  ArrowRightIcon,
  BanknoteIcon,
  Building2Icon,
  ChevronDownIcon,
  HeartIcon,
  HouseIcon,
  SparklesIcon,
  UsersIcon,
  WalletIcon,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { CollectRule } from '@/components/collect-rule'
import { CompanyMark } from '@/components/company-mark'
import { LevelBadge } from '@/components/level-badge'
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

const GAUGE_STAGGER_MS = 160
const GAUGE_START_MS = 350

// ゲージの意味を線で示す。人は愛、稼ぐ力はお金。
const AXIS_ICON: Record<SheetAxis['key'], LucideIcon> = {
  sales: Building2Icon,
  employee_count: UsersIcon,
  operating_margin: BanknoteIcon,
  people: HeartIcon,
  average_annual_salary: WalletIcon,
  average_years_of_service: HouseIcon,
  expectation: SparklesIcon,
}

function AxisGlyph({ axisKey }: { axisKey: SheetAxis['key'] }) {
  const Icon = AXIS_ICON[axisKey]
  return (
    <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl border-[length:var(--line)] border-ink bg-page shadow-ink-sm">
      <Icon
        className="size-6 text-ink"
        strokeWidth={2.5}
        aria-hidden="true"
        fill={axisKey === 'people' ? 'var(--shu)' : 'none'}
      />
    </span>
  )
}

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

function AxisRow({
  axis,
  order,
  open,
  onToggle,
}: {
  axis: SheetAxis
  order: number
  open: boolean
  onToggle: () => void
}) {
  const panelId = `sheet-axis-${axis.key}`
  const delayMs = GAUGE_START_MS + order * GAUGE_STAGGER_MS
  return (
    <div className={cn('rounded-2xl px-3 py-4 transition-colors sm:px-4', open ? 'bg-paper-deep' : 'hover:bg-paper-deep/60')}>
      <button
        type="button"
        className="group w-full cursor-pointer rounded-xl text-left"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-3">
            <AxisGlyph axisKey={axis.key} />
            <span className="text-lg leading-tight font-black text-ink">{axis.nickname}</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="font-num text-4xl leading-none font-black text-ink">{scoreText(axis.score)}</span>
            <ChevronDownIcon
              className={cn('size-5 text-ink transition-transform duration-200', open && 'rotate-180')}
              strokeWidth={3}
              aria-hidden="true"
            />
          </span>
        </span>
        <CollectRule score={axis.score} delayMs={delayMs} />
      </button>
      {open ? (
        <div id={panelId} className="rise-in mt-4 space-y-2 rounded-xl border-2 border-dashed border-ink/25 bg-page p-4 text-sm">
          <p className="text-xs font-bold text-ink-soft">{axis.label}</p>
          {axis.key === 'people' ? <PeopleFacts axis={axis} /> : <FaceFacts axis={axis} />}
          {axis.score == null ? <p className="text-ink-soft">{blankReason(axis)}</p> : null}
        </div>
      ) : null}
    </div>
  )
}

function FaceFacts({ axis }: { axis: SheetPercentileAxis | SheetExpectationAxis }) {
  const basis = axis.key === 'expectation' ? psrBasisText(axis.psr_basis) : null
  return (
    <div className="space-y-1">
      <p className="font-num text-2xl font-black text-ink">{formatFaceValue(axis)}</p>
      {axis.key === 'expectation' && axis.per != null ? (
        <p className="font-num font-bold text-ink">実績PER {formatMultiple(axis.per)}</p>
      ) : null}
      {basis ? <p className="text-ink-soft">{basis}</p> : null}
    </div>
  )
}

function PeopleFacts({ axis }: { axis: SheetPeopleAxis }) {
  return (
    <dl className="space-y-1.5">
      {axis.metrics.map((metric) => (
        <div key={metric.key} className="flex justify-between gap-3">
          <dt className="text-ink-soft">{HC_METRIC_LABELS[metric.key]}</dt>
          <dd className="font-num font-bold text-ink">{formatPct(metric.value)}</dd>
        </div>
      ))}
      <div className="flex justify-between gap-3">
        <dt className="text-ink-soft">平均年齢</dt>
        <dd className="font-num font-bold text-ink">{formatAge(axis.average_age)}</dd>
      </div>
    </dl>
  )
}

export function CompanySheet({ sheet }: { sheet: SheetResponse }) {
  const [openKey, setOpenKey] = useState<string | null>(null)

  return (
    <section className="sheet relative overflow-hidden rounded-[2rem] shadow-ink-lg">
      <div className="grid lg:grid-cols-[minmax(18rem,26rem)_minmax(0,1fr)]">
        <div className="relative border-b-[length:var(--line)] border-ink bg-paper px-6 pt-8 pb-10 lg:border-r-[length:var(--line)] lg:border-b-0">
          <div className="lg:sticky lg:top-24">
            <SpecimenFigure industry={sheet.industry} level={sheet.level} />
          </div>
        </div>
        <div className="min-w-0 px-5 pt-6 pb-8 sm:px-8 sm:pt-8">
          <div className="flex items-center justify-between gap-3 text-xs font-bold text-ink-soft">
            <span className="font-num">{sheet.edinet_code}</span>
            {sheet.fiscal_year != null ? (
              <span className="rounded-full border-2 border-ink/20 px-2.5 py-0.5">{sheet.fiscal_year}年度の有報</span>
            ) : null}
          </div>
          {/* 狭い幅はロゴの下に社名。広い幅は横に並べ、総合点は下に置く。 */}
          <div className="mt-5 flex flex-col gap-5">
            <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:gap-6">
              <CompanyMark name={sheet.company_name} securitiesCode={sheet.securities_code} />
              <div className="min-w-0">
                <h1 className="text-3xl leading-tight font-black text-balance text-ink">{sheet.company_name}</h1>
                <p className="mt-3 inline-flex rounded-full bg-paper-deep px-3 py-1 text-xs font-bold text-ink">
                  {sheet.industry ?? '業種なし'}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
              <LevelBadge level={sheet.level} />
              <div className="flex flex-col items-start gap-3">
                <Link
                  className="press inline-flex h-11 items-center gap-2 rounded-full border-[length:var(--line)] border-ink bg-shu px-5 text-sm font-black text-page"
                  to={`/companies/${sheet.edinet_code}/story`}
                >
                  歩みを見る
                  <ArrowRightIcon className="size-4" strokeWidth={3} aria-hidden="true" />
                </Link>
                <Link
                  className="text-sm font-bold text-ink underline decoration-shu decoration-2 underline-offset-4"
                  to={`/compare?a=${sheet.edinet_code}`}
                >
                  ほかの会社とくらべる
                </Link>
              </div>
            </div>
          </div>
          <h2 className="mt-8 mb-2 text-xs font-black tracking-[0.2em] text-shu">ステータス</h2>
          <div className="-mx-3 space-y-1 sm:-mx-4">
            {sheet.axes.map((axis, index) => (
              <AxisRow
                key={axis.key}
                axis={axis}
                order={index}
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
