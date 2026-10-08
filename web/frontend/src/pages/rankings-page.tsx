// 図鑑のランキング。総合点を初期にし、業種と軸で絞る。絞り込みは URL に持つ。
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { CharacterImage } from '@/components/character-image'
import { FilterSelect } from '@/components/filter-select'
import { QueryState } from '@/components/query-state'
import { RankRow } from '@/components/rank-row'
import { SectionHeading } from '@/components/section-heading'
import { Button } from '@/components/ui/button'
import { fetchRankings } from '@/lib/api'
import { specimenLabel, specimenNo } from '@/lib/specimen'

const PAGE_SIZE = 100

export function RankingsPage() {
  const [params, setParams] = useSearchParams()
  const industry = params.get('industry') || 'all'
  const axis = params.get('axis') || 'level'
  const filterKey = `${industry}|${axis}`
  const [shown, setShown] = useState({ key: filterKey, count: PAGE_SIZE })
  const visibleCount = shown.key === filterKey ? shown.count : PAGE_SIZE

  const query = useQuery({
    queryKey: ['rankings', industry, axis],
    queryFn: () => fetchRankings(industry, axis),
    placeholderData: keepPreviousData,
  })
  const data = query.data

  const update = (key: 'industry' | 'axis', value: string, fallback: string) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value === fallback) next.delete(key)
        else next.set(key, value)
        return next
      },
      { replace: true },
    )
  }

  return (
    <div className="space-y-8">
      {industry === 'all' ? (
        <SectionHeading
          kicker="点の順"
          title="ランキング"
          description="会社シートと同じ点で並べます。業種と軸を変えると、その中での順になります。"
        />
      ) : (
        <SpeciesBanner industry={industry} count={data?.companies.length} />
      )}
      <QueryState isLoading={query.isLoading} error={query.error} isEmpty={false}>
        {data ? (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-4">
              <FilterSelect
                label="業種"
                value={industry}
                onChange={(value) => update('industry', value, 'all')}
                options={[
                  { value: 'all', label: 'すべて' },
                  ...data.industries.map((item) => ({ value: item, label: item })),
                ]}
              />
              <FilterSelect
                label="軸"
                value={axis}
                onChange={(value) => update('axis', value, 'level')}
                options={data.axes.map((item) => ({ value: item.key, label: item.label }))}
              />
              <span className="font-num text-sm font-bold text-ink-soft">{data.companies.length.toLocaleString('ja-JP')}社</span>
            </div>
            <ol className={query.isPlaceholderData ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
              {data.companies.slice(0, visibleCount).map((company, index) => (
                <RankRow
                  key={company.edinet_code}
                  rank={index + 1}
                  industry={company.industry}
                  score={company.score}
                  title={
                    <Link
                      className="text-ink underline decoration-ink/25 decoration-2 underline-offset-4 hover:decoration-shu"
                      to={`/companies/${company.edinet_code}`}
                    >
                      {company.company_name}
                    </Link>
                  }
                  meta={company.industry ?? '—'}
                />
              ))}
            </ol>
            {data.companies.length > visibleCount ? (
              <div className="flex justify-center">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => setShown({ key: filterKey, count: visibleCount + PAGE_SIZE })}
                >
                  もっと見る（あと {(data.companies.length - visibleCount).toLocaleString('ja-JP')}社）
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </QueryState>
    </div>
  )
}

// 業種で絞ったときの見出し。図鑑のその業種のページに見せる。
function SpeciesBanner({ industry, count }: { industry: string; count: number | undefined }) {
  return (
    <div className="sheet relative flex items-center gap-5 overflow-hidden bg-paper-deep px-5 py-5 sm:gap-8 sm:px-8">
      <div className="flex size-28 shrink-0 items-end justify-center rounded-full border-[length:var(--line)] border-ink bg-marker sm:size-36">
        <CharacterImage industry={industry} idle eager className="h-[118%] w-auto" />
      </div>
      <div className="min-w-0">
        <p className="font-num text-xs font-black tracking-[0.18em] text-shu">
          {specimenNo(industry)} · {specimenLabel(industry)}
        </p>
        <h1 className="mt-1 text-2xl leading-tight font-black text-ink sm:text-4xl">
          <span className="marker-line">{industry}</span>
        </h1>
        <p className="mt-2 text-sm text-ink-soft">
          この業種の会社を、点の高い順に並べます。{count != null ? `${count.toLocaleString('ja-JP')}社。` : ''}
        </p>
      </div>
    </div>
  )
}
