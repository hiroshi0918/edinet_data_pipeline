// 日経225の構成銘柄。総合点の高い順。図鑑にある会社はシートへ進む。
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { LogoCredit } from '@/components/company-mark'
import { EggFigure } from '@/components/egg-figure'
import { FilterSelect } from '@/components/filter-select'
import { QueryState } from '@/components/query-state'
import { RankRow } from '@/components/rank-row'
import { SectionHeading } from '@/components/section-heading'
import { fetchNikkei225 } from '@/lib/api'
import type { Nikkei225Company } from '@/lib/types'

export function Nikkei225Page() {
  const [sector, setSector] = useState('all')
  const query = useQuery({
    queryKey: ['nikkei225'],
    queryFn: fetchNikkei225,
  })
  const companies = useMemo(() => query.data?.companies ?? [], [query.data])
  const sectors = useMemo(
    () => [...new Set(companies.map((company) => company.nikkei_sector))].sort(),
    [companies],
  )
  const visible = companies.filter((company) => sector === 'all' || company.nikkei_sector === sector)
  const withSheet = companies.filter((company) => company.has_sheet).length

  return (
    <div className="space-y-8">
      <SectionHeading kicker="225銘柄" title="日経225" description="構成銘柄を、図鑑の総合点が高い順に並べます。" />
      <QueryState isLoading={query.isLoading} error={query.error} isEmpty={false}>
        {query.data ? (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <FilterSelect
                label="日経の業種"
                value={sector}
                onChange={setSector}
                options={[{ value: 'all', label: 'すべて' }, ...sectors.map((item) => ({ value: item, label: item }))]}
              />
              <p className="text-sm font-bold text-ink-soft">
                {query.data.as_of} 時点 · 図鑑にある{' '}
                <span className="font-num font-black text-ink">
                  {withSheet} / {companies.length}
                </span>{' '}
                社
              </p>
            </div>
            <ol>
              {visible.map((company, index) => (
                <NikkeiRow key={company.securities_code} company={company} rank={index + 1} />
              ))}
            </ol>
            <p className="text-xs text-ink-soft">{query.data.source_note}</p>
            <LogoCredit />
          </div>
        ) : null}
      </QueryState>
    </div>
  )
}

function NikkeiRow({ company, rank }: { company: Nikkei225Company; rank: number }) {
  const name = (
    <span>
      <span>{company.company_name}</span>
      <span className="font-num ml-2 text-xs font-bold text-ink-soft">{company.securities_code}</span>
    </span>
  )
  const meta = (
    <>
      {company.nikkei_sector}
      {' · 図鑑: '}
      {company.industry ?? '—'}
    </>
  )
  return (
    <RankRow
      rank={rank}
      companyName={company.company_name}
      securitiesCode={company.securities_code}
      score={company.level}
      podium={rank <= 3 && company.level != null}
      meta={meta}
      title={
        company.has_sheet && company.edinet_code ? (
          <Link
            className="text-ink underline decoration-ink/25 decoration-2 underline-offset-4 hover:decoration-shu"
            to={`/companies/${company.edinet_code}`}
          >
            {name}
          </Link>
        ) : (
          <span className="inline-flex items-center gap-2">
            {name}
            <span className="inline-flex items-center gap-1 rounded-full bg-paper-deep px-2 py-0.5 text-xs font-bold text-ink-soft">
              <EggFigure className="h-3.5 w-auto" />
              図鑑に無い
            </span>
          </span>
        )
      }
    />
  )
}
