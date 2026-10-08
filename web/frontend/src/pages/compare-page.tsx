// 2社をくらべる。PL（売上高・営業利益・営業利益率）を同じ目盛りに重ね、会社ごとに色を固定する。
// URL は /compare?a=EDINETコード&b=EDINETコード。データは歩みと同じ GET /companies/:code/story。
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'

import { CompanyCombobox } from '@/components/company-combobox'
import { LineChart, type LineSeries } from '@/components/line-chart'
import { QueryState } from '@/components/query-state'
import { SectionHeading } from '@/components/section-heading'
import { fetchStory } from '@/lib/api'
import type { ChartKind } from '@/lib/chart-scale'
import { alignedValues, type CompareMetric, compareYears, latestValue } from '@/lib/compare'
import { formatOkuYen, formatRatioAsPct } from '@/lib/format'
import type { StoryResponse } from '@/lib/types'
import { cn } from '@/lib/utils'

const SLOTS = [
  { param: 'a', color: 'var(--compare-a)', swatch: 'bg-compare-a', dashed: false, placeholder: '1社目をえらぶ' },
  { param: 'b', color: 'var(--compare-b)', swatch: 'bg-compare-b', dashed: true, placeholder: '2社目をえらぶ' },
] as const

const METRICS: { key: CompareMetric; title: string; kind: ChartKind; unitNote: string }[] = [
  { key: 'sales', title: '売上高', kind: 'yen', unitNote: '単位は億円（1兆円以上の目盛りは兆円）' },
  { key: 'operating_profit', title: '営業利益', kind: 'yen', unitNote: '単位は億円（1兆円以上の目盛りは兆円）' },
  { key: 'operating_margin', title: '営業利益率', kind: 'pct', unitNote: '営業利益 ÷ 売上高。売上が無い年は出しません' },
]

function useStory(code: string | null) {
  return useQuery({
    queryKey: ['story', code],
    queryFn: () => fetchStory(code ?? ''),
    enabled: Boolean(code),
  })
}

function formatMetric(metric: CompareMetric, value: number): string {
  return metric === 'operating_margin' ? formatRatioAsPct(value) : formatOkuYen(value)
}

function Swatch({ className, dashed }: { className: string; dashed: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn('inline-block h-1 w-6 shrink-0 rounded-full', dashed ? 'bg-transparent' : className)}
      style={
        dashed
          ? { backgroundImage: `repeating-linear-gradient(90deg, var(--compare-b) 0 7px, transparent 7px 12px)` }
          : undefined
      }
    />
  )
}

export function ComparePage() {
  const [params, setParams] = useSearchParams()
  const codes = SLOTS.map((slot) => params.get(slot.param))
  const queries = [useStory(codes[0]), useStory(codes[1])]
  const stories = queries.map((query) => query.data)
  const ready = stories.every((story): story is StoryResponse => Boolean(story))

  const choose = (param: string, code: string) => {
    const next = new URLSearchParams(params)
    next.set(param, code)
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-10">
      <SectionHeading
        kicker="COMPARE"
        title="2社をくらべる"
        description="売上高・営業利益・営業利益率を、同じ目盛りで年度ごとに重ねます。"
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {SLOTS.map((slot, index) => {
          const story = stories[index]
          return (
            <div key={slot.param} className="sheet space-y-3 p-4">
              <p className="flex items-center gap-2 text-xs font-black text-ink-soft">
                <Swatch className={slot.swatch} dashed={slot.dashed} />
                {index === 0 ? '1社目（実線）' : '2社目（点線）'}
              </p>
              <CompanyCombobox
                searchRemote
                placeholder={slot.placeholder}
                selectedCode={codes[index] ?? undefined}
                selectedLabel={story ? `${story.company_name} (${story.edinet_code})` : undefined}
                onSelect={(company) => choose(slot.param, company.edinet_code)}
              />
            </div>
          )
        })}
      </div>

      {codes.every(Boolean) ? (
        <QueryState
          isLoading={queries.some((query) => query.isLoading)}
          error={queries.find((query) => query.error)?.error ?? null}
          isEmpty={!ready}
          empty="えらんだ会社の数字が見つかりません。"
        >
          {ready ? <CompareCharts stories={stories as StoryResponse[]} /> : null}
        </QueryState>
      ) : (
        <p className="sheet p-6 text-sm font-bold text-ink-soft">くらべる会社を2社えらんでください。</p>
      )}
    </div>
  )
}

function CompareCharts({ stories }: { stories: StoryResponse[] }) {
  const years = compareYears(stories)
  if (years.length === 0) {
    return <p className="sheet p-6 text-sm font-bold text-ink-soft">2社とも、この10年の有報に売上と営業利益がありません。</p>
  }

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      {METRICS.map((metric, metricIndex) => {
        const series: LineSeries[] = stories.map((story, index) => ({
          key: story.edinet_code,
          label: story.company_name,
          color: SLOTS[index].color,
          values: alignedValues(story, years, metric.key),
        }))
        return (
          <section key={metric.key} className="sheet flex flex-col p-5">
            <h2 className="text-sm font-black text-ink">{metric.title}</h2>
            <div className="mt-3">
              <LineChart title={metric.title} kind={metric.kind} years={years} series={series} delayMs={150 * (metricIndex + 1)} />
            </div>
            <dl className="mt-4 space-y-1.5 border-t-2 border-dashed border-ink/20 pt-3">
              {stories.map((story, index) => {
                const latest = latestValue(story, metric.key)
                return (
                  <div key={story.edinet_code} className="flex items-baseline gap-2">
                    <dt className="flex min-w-0 flex-1 items-center gap-2 text-xs font-bold text-ink">
                      <Swatch className={SLOTS[index].swatch} dashed={SLOTS[index].dashed} />
                      <span className="truncate">{story.company_name}</span>
                    </dt>
                    <dd className="font-num text-right text-base font-black text-ink tabular-nums">
                      {latest ? formatMetric(metric.key, latest.value) : '—'}
                    </dd>
                    <dd className="font-num w-12 text-right text-[11px] font-bold text-ink-soft">
                      {latest ? `${latest.year}年度` : ''}
                    </dd>
                  </div>
                )
              })}
            </dl>
            <p className="mt-3 text-[11px] leading-5 text-ink-soft">
              {metric.unitNote}。年度は各社の有報の事業年度。連結・個別は有報の経営指標のとおりで、会社によって混ざることがあります。
            </p>
          </section>
        )
      })}
    </div>
  )
}
