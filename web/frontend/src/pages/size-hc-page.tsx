// 規模×人的資本。財務軸の上位/下位 10 社に HC を横並び。
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { DimensionFilters } from '@/components/filters/dimension-filters'
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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useFilters } from '@/hooks/use-filters'
import { fetchSizeRanking } from '@/lib/api'
import { FINANCIAL_METRIC_LABELS, SIZE_AXIS_METRICS } from '@/lib/constants'
import { formatOkuYen, formatPeople, formatPct } from '@/lib/format'
import type { SizeAxis, SizeRankingRow } from '@/lib/types'

const BOTTOM_NOTE: Record<SizeAxis, string> = {
  sales: '下位は売上 1 億円以上に限定 (銀行等の抽出エラーを除外)',
  operating_profit: '下位はフィルタなし (巨額赤字は実体)',
  employee_count: '下位は従業員 1 人以上に限定 (0 人の持株会社等を除外)',
}

function formatAxis(value: number, axis: SizeAxis) {
  if (axis === 'employee_count') return formatPeople(value)
  return formatOkuYen(value)
}

export function SizeHcPage() {
  const { year, scope, worker_type, axis, searchParams, setFilter } = useFilters()
  const query = useQuery({
    queryKey: ['size-ranking', year, scope, worker_type, axis],
    queryFn: () =>
      fetchSizeRanking({
        year: year!,
        scope,
        worker_type,
        axis,
      }),
    enabled: year != null,
  })
  const empty = !query.data?.top.length && !query.data?.bottom.length
  const axisLabel = FINANCIAL_METRIC_LABELS[axis]

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Scale × human capital"
        title="規模×人的資本"
        description="財務規模の上位 10 社・下位 10 社に、女性管理職比率・男女賃金格差を併記します。大企業と小規模企業の人的資本開示を読み比べるためのページです。"
      />
      <DimensionFilters />
      <Tabs value={axis} onValueChange={(value) => setFilter({ axis: value })}>
        <TabsList>
          {SIZE_AXIS_METRICS.map((item) => (
            <TabsTrigger key={item} value={item}>
              {FINANCIAL_METRIC_LABELS[item]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <QueryState
        isLoading={query.isLoading || year == null}
        error={query.error}
        isEmpty={empty}
        empty={`${year} 年度・選択次元に ${axisLabel} のデータがありません。`}
      >
        <SizeTable
          title={`${axisLabel} 上位 10 社`}
          rows={query.data?.top ?? []}
          axis={axis}
          search={searchParams.toString()}
        />
        <SizeTable
          title={`${axisLabel} 下位 10 社`}
          caption={BOTTOM_NOTE[axis]}
          rows={query.data?.bottom ?? []}
          axis={axis}
          search={searchParams.toString()}
        />
      </QueryState>
    </div>
  )
}

function SizeTable({
  title,
  caption,
  rows,
  axis,
  search,
}: {
  title: string
  caption?: string
  rows: SizeRankingRow[]
  axis: SizeAxis
  search: string
}) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      {caption ? <p className="text-xs text-muted-foreground">{caption}</p> : null}
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">該当する企業がありません。</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">順位</TableHead>
              <TableHead>企業名</TableHead>
              <TableHead>業種</TableHead>
              <TableHead className="text-right">{FINANCIAL_METRIC_LABELS[axis]}</TableHead>
              <TableHead className="text-right">女性管理職比率</TableHead>
              <TableHead className="text-right">男女賃金格差</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={`${row.rank}-${row.edinet_code}`}>
                <TableCell className="tabular-nums">{row.rank}</TableCell>
                <TableCell>
                  <Link
                    className="hover:underline"
                    to={{
                      pathname: `/companies/${row.edinet_code}`,
                      search,
                    }}
                  >
                    {row.company_name}
                  </Link>
                </TableCell>
                <TableCell>{row.industry ?? '(未取得)'}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatAxis(row.value, axis)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatPct(row.female_manager_ratio)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatPct(row.gender_wage_gap)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  )
}
