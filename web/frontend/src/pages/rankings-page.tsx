// 図鑑のランキング。総合点を初期にし、業種と軸で絞る。
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
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
import { fetchRankings } from '@/lib/api'

function scoreText(score: number | null): string {
  return score == null ? '—' : String(score)
}

export function RankingsPage() {
  const [industry, setIndustry] = useState('all')
  const [axis, setAxis] = useState('level')
  const query = useQuery({
    queryKey: ['rankings', industry, axis],
    queryFn: () => fetchRankings(industry, axis),
  })
  const data = query.data

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Ranking"
        title="ランキング"
        description="会社シートと同じ点で並べます。業種と軸を変えると、その中での順になります。"
      />
      <QueryState isLoading={query.isLoading} error={query.error} isEmpty={false}>
        {data ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-4">
              <label className="text-sm">
                <span className="mr-2 text-[#5c7380]">業種</span>
                <select
                  className="rounded-md border border-[#d5e0e3] bg-white px-2 py-1"
                  aria-label="業種"
                  value={industry}
                  onChange={(event) => setIndustry(event.target.value)}
                >
                  <option value="all">すべて</option>
                  {data.industries.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="mr-2 text-[#5c7380]">軸</span>
                <select
                  className="rounded-md border border-[#d5e0e3] bg-white px-2 py-1"
                  aria-label="軸"
                  value={axis}
                  onChange={(event) => setAxis(event.target.value)}
                >
                  {data.axes.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
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
                    <TableHead>業種</TableHead>
                    <TableHead className="text-right">点</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.companies.map((company, index) => (
                    <TableRow key={company.edinet_code}>
                      <TableCell className="tabular-nums text-[#5c7380]">{index + 1}</TableCell>
                      <TableCell>
                        <Link
                          className="font-medium text-[#16303a] hover:underline"
                          to={`/companies/${company.edinet_code}`}
                        >
                          {company.company_name}
                        </Link>
                      </TableCell>
                      <TableCell>{company.industry ?? '—'}</TableCell>
                      <TableCell className="text-right text-lg font-semibold tabular-nums text-[#16303a]">
                        {scoreText(company.score)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        ) : null}
      </QueryState>
    </div>
  )
}
