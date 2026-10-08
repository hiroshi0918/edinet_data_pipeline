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
        kicker="点の順"
        title="ランキング"
        description="会社シートと同じ点で並べます。業種と軸を変えると、その中での順になります。"
      />
      <QueryState isLoading={query.isLoading} error={query.error} isEmpty={false}>
        {data ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-4">
              <label className="text-sm">
                <span className="mr-2 text-pencil">業種</span>
                <select
                  className="border border-border bg-label px-2 py-1"
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
                <span className="mr-2 text-pencil">軸</span>
                <select
                  className="border border-border bg-label px-2 py-1"
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
            <div className="overflow-x-auto bg-label">
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
                      <TableCell className="tabular-nums text-pencil">{index + 1}</TableCell>
                      <TableCell>
                        <Link
                          className="text-ink underline decoration-pencil underline-offset-4 hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-habitat"
                          to={`/companies/${company.edinet_code}`}
                        >
                          {company.company_name}
                        </Link>
                      </TableCell>
                      <TableCell>{company.industry ?? '—'}</TableCell>
                      <TableCell className="text-right font-mono text-lg tabular-nums text-ink">
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
