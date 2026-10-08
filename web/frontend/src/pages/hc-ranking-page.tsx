// 人的資本トップ/ボトム。賃金格差は値が高いほどパリティに近い。
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
import { fetchHcRanking } from '@/lib/api'
import { HC_METRIC_LABELS, RANKING_HC_METRICS } from '@/lib/constants'
import { formatPct } from '@/lib/format'
import type { RankingHcMetric, RankingRow } from '@/lib/types'

const DIRECTION_NOTE: Record<RankingHcMetric, { top: string; bottom: string }> = {
  female_manager_ratio: {
    top: '上位 = 女性管理職比率が高い',
    bottom: '下位 = 低い',
  },
  gender_wage_gap: {
    top: '上位 = 格差が小さい（値は大きいほどパリティに近い）',
    bottom: '下位 = 格差が大きい',
  },
}

export function HcRankingPage() {
  const { year, scope, worker_type, ranking_metric, searchParams, setFilter } =
    useFilters()
  const query = useQuery({
    queryKey: ['hc-ranking', year, scope, worker_type, ranking_metric],
    queryFn: () =>
      fetchHcRanking({
        year: year!,
        scope,
        worker_type,
        metric: ranking_metric,
      }),
    enabled: year != null,
  })

  const note = DIRECTION_NOTE[ranking_metric]
  const empty =
    !query.data?.top.length && !query.data?.bottom.length

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Ranking · companies"
        title="人的資本トップ/ボトム企業"
        description="女性管理職比率・男女賃金格差の上位 10 社と下位 10 社を企業名で示します。男性育休取得率は単一企業の値がぶれやすいため、業種で比べるページで確認してください。"
      />
      <DimensionFilters />
      <Tabs
        value={ranking_metric}
        onValueChange={(value) => setFilter({ metric: value })}
      >
        <TabsList>
          {RANKING_HC_METRICS.map((item) => (
            <TabsTrigger key={item} value={item}>
              {HC_METRIC_LABELS[item]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <QueryState
        isLoading={query.isLoading || year == null}
        error={query.error}
        isEmpty={empty}
        empty={`${year} 年度・選択次元に ${HC_METRIC_LABELS[ranking_metric]} の開示がありません。`}
      >
        <RankingTable
          title={`上位 10 社`}
          caption={note.top}
          rows={query.data?.top ?? []}
          metricLabel={HC_METRIC_LABELS[ranking_metric]}
          search={searchParams.toString()}
        />
        <RankingTable
          title={`下位 10 社`}
          caption={note.bottom}
          rows={query.data?.bottom ?? []}
          metricLabel={HC_METRIC_LABELS[ranking_metric]}
          search={searchParams.toString()}
        />
      </QueryState>
    </div>
  )
}

function RankingTable({
  title,
  caption,
  rows,
  metricLabel,
  search,
}: {
  title: string
  caption: string
  rows: RankingRow[]
  metricLabel: string
  search: string
}) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-xs text-muted-foreground">{caption}</p>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">該当する企業がありません。</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">順位</TableHead>
              <TableHead>企業名</TableHead>
              <TableHead>業種</TableHead>
              <TableHead className="text-right">{metricLabel}</TableHead>
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
                  {formatPct(row.value)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  )
}
