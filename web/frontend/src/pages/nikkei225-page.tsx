// 日経225の構成銘柄。総合点の高い順。図鑑にある会社はシートへ進む。
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { PageHeader } from '@/components/page-header'
import { QueryState } from '@/components/query-state'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { fetchNikkei225 } from '@/lib/api'
import type { Nikkei225Company } from '@/lib/types'

function levelText(level: number | null): string {
  return level == null ? '—' : String(level)
}

export function Nikkei225Page() {
  const [sector, setSector] = useState('all')
  const query = useQuery({
    queryKey: ['nikkei225'],
    queryFn: fetchNikkei225,
  })
  const companies = query.data?.companies ?? []
  const sectors = useMemo(
    () => [...new Set(companies.map((company) => company.nikkei_sector))].sort(),
    [companies],
  )
  const visible = companies.filter(
    (company) => sector === 'all' || company.nikkei_sector === sector,
  )
  const withSheet = companies.filter((company) => company.has_sheet).length

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Nikkei 225"
        title="日経225"
        description="構成銘柄を、図鑑の総合点が高い順に並べます。"
      />
      <QueryState isLoading={query.isLoading} error={query.error} isEmpty={false}>
        {query.data ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <p className="text-sm text-[#5c7380]">
                {query.data.as_of} 時点 · 図鑑にある {withSheet} / {companies.length} 社
              </p>
              <label className="text-sm">
                <span className="mr-2 text-[#5c7380]">日経の業種</span>
                <select
                  className="rounded-md border border-[#d5e0e3] bg-white px-2 py-1"
                  value={sector}
                  aria-label="日経の業種"
                  onChange={(event) => setSector(event.target.value)}
                >
                  <option value="all">すべて</option>
                  {sectors.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="overflow-hidden rounded-2xl bg-[#e7eef2]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-14">順</TableHead>
                    <TableHead>会社</TableHead>
                    <TableHead>日経の業種</TableHead>
                    <TableHead>図鑑の業種</TableHead>
                    <TableHead className="text-right">総合</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visible.map((company, index) => (
                    <NikkeiRow key={company.securities_code} company={company} rank={index + 1} />
                  ))}
                </TableBody>
              </Table>
            </div>
            <p className="text-xs text-[#5c7380]">{query.data.source_note}</p>
          </div>
        ) : null}
      </QueryState>
    </div>
  )
}

function NikkeiRow({ company, rank }: { company: Nikkei225Company; rank: number }) {
  const name = (
    <span>
      <span className="font-medium text-[#16303a]">{company.company_name}</span>
      <span className="ml-2 font-mono text-xs text-[#5c7380]">{company.securities_code}</span>
    </span>
  )
  return (
    <TableRow>
      <TableCell className="tabular-nums text-[#5c7380]">{rank}</TableCell>
      <TableCell>
        {company.has_sheet && company.edinet_code ? (
          <Link className="hover:underline" to={`/companies/${company.edinet_code}`}>
            {name}
          </Link>
        ) : (
          <span>
            {name}
            <span className="ml-2 text-xs text-[#5c7380]">図鑑に無い</span>
          </span>
        )}
      </TableCell>
      <TableCell>{company.nikkei_sector}</TableCell>
      <TableCell>{company.industry ?? '—'}</TableCell>
      <TableCell className="text-right text-lg font-semibold tabular-nums text-[#16303a]">
        {levelText(company.level)}
      </TableCell>
    </TableRow>
  )
}
