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
        kicker="225銘柄"
        title="日経225"
        description="構成銘柄を、図鑑の総合点が高い順に並べます。"
      />
      <QueryState isLoading={query.isLoading} error={query.error} isEmpty={false}>
        {query.data ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <p className="text-sm text-pencil">
                {query.data.as_of} 時点 · 図鑑にある {withSheet} / {companies.length} 社
              </p>
              <label className="text-sm">
                <span className="mr-2 text-pencil">日経の業種</span>
                <select
                  className="border border-border bg-label px-2 py-1"
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
            <div className="overflow-x-auto bg-label">
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
            <p className="text-xs text-pencil">{query.data.source_note}</p>
          </div>
        ) : null}
      </QueryState>
    </div>
  )
}

function NikkeiRow({ company, rank }: { company: Nikkei225Company; rank: number }) {
  const name = (
    <span>
      <span className="font-medium text-ink">{company.company_name}</span>
      <span className="ml-2 font-mono text-xs text-pencil">{company.securities_code}</span>
    </span>
  )
  return (
    <TableRow>
      <TableCell className="tabular-nums text-pencil">{rank}</TableCell>
      <TableCell>
        {company.has_sheet && company.edinet_code ? (
          <Link
            className="text-ink underline decoration-pencil underline-offset-4 hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-habitat"
            to={`/companies/${company.edinet_code}`}
          >
            {name}
          </Link>
        ) : (
          <span>
            {name}
            <span className="ml-2 text-xs text-pencil">図鑑に無い</span>
          </span>
        )}
      </TableCell>
      <TableCell>{company.nikkei_sector}</TableCell>
      <TableCell>{company.industry ?? '—'}</TableCell>
      <TableCell className="text-right font-mono text-lg tabular-nums text-ink">
        {levelText(company.level)}
      </TableCell>
    </TableRow>
  )
}
