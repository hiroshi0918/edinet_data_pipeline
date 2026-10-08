// 企業スポットライト。peer の violin と 4 種の理想値。scope=auto で持株会社判定。
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { Data, Layout } from 'plotly.js'
import { useNavigate, useParams } from 'react-router'

import { Plot } from '@/components/charts/plot'
import { CompanyCombobox } from '@/components/company-combobox'
import { DimensionFilters } from '@/components/filters/dimension-filters'
import { PageHeader } from '@/components/page-header'
import { QueryState } from '@/components/query-state'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useFilters } from '@/hooks/use-filters'
import { fetchSpotlight } from '@/lib/api'
import { HC_METRIC_LABELS, HC_METRICS, SCOPE_LABELS, WORKER_TYPE_LABELS } from '@/lib/constants'
import { formatNumber } from '@/lib/format'
import type {
  BenchmarkSet,
  HcMetric,
  IndustryRank,
  IndustryRankMetricKey,
  SpotlightPeer,
  SpotlightTarget,
} from '@/lib/types'

function peerNote(n: number) {
  if (n < 5) return `n=${n} は参考値（信頼区間が極めて広い）`
  if (n < 10) return `n=${n} は少なめ`
  return `n=${n}`
}

function violinData(
  peers: SpotlightPeer[],
  metric: HcMetric,
  target: number | null,
): { data: Data[]; layout: Partial<Layout> } {
  const values = peers
    .map((peer) => peer[metric])
    .filter((value): value is number => value != null)
  const data: Data[] = values.length
    ? [
        {
          type: 'violin',
          y: values,
          name: 'peer',
          box: { visible: true },
          meanline: { visible: true },
          points: 'all',
          line: { color: '#2E5BDA' },
          fillcolor: 'rgba(46,91,218,0.12)',
          marker: { opacity: 0.35, color: '#2E5BDA', size: 4 },
        },
      ]
    : []
  const layout: Partial<Layout> = {
    showlegend: false,
    title: { text: HC_METRIC_LABELS[metric] },
    margin: { l: 48, r: 16, t: 40, b: 32 },
    yaxis: {
      ticksuffix: '%',
      ...(metric === 'male_childcare_leave_ratio' ? { range: [0, 100] } : {}),
    },
    shapes:
      target != null
        ? [
            {
              type: 'line',
              xref: 'paper',
              x0: 0,
              x1: 1,
              y0: target,
              y1: target,
              line: { color: '#C0483F', width: 2 },
            },
          ]
        : [],
    annotations:
      target != null
        ? [
            {
              x: 0,
              xref: 'paper',
              y: target,
              text: `対象: ${target.toFixed(1)}%`,
              showarrow: false,
              xanchor: 'left',
              font: { color: '#C0483F', size: 11 },
            },
          ]
        : [],
  }
  return { data, layout }
}

function industryCounts(cluster: SpotlightPeer[]) {
  const counts = new Map<string, number>()
  for (const item of cluster) {
    const key = item.industry ?? '(未取得)'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
}

export function SpotlightPage() {
  const { code } = useParams()
  const navigate = useNavigate()
  const { year, spotlightScope, worker_type, searchParams } = useFilters()
  const query = useQuery({
    queryKey: ['spotlight', code, year, spotlightScope, worker_type],
    queryFn: () =>
      fetchSpotlight(code!, {
        year: year ?? undefined,
        scope: spotlightScope,
        worker_type,
      }),
    enabled: Boolean(code) && year != null,
  })

  const industryDist = useMemo(
    () => industryCounts(query.data?.ideal_cluster ?? []),
    [query.data?.ideal_cluster],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Spotlight"
        title="企業スポットライト"
        description="単一企業の人的資本指標 3 つを、業界 peer と規模類似 peer の分布に並べ、理想値との差分を確認します。"
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="space-y-1.5">
          <p className="text-sm font-medium">企業名で検索（部分一致）</p>
          <CompanyCombobox
            selectedCode={code}
            selectedLabel={
              query.data
                ? `${query.data.company_name} (${query.data.edinet_code})`
                : undefined
            }
            searchRemote
            onSelect={(company) =>
              navigate({
                pathname: `/companies/${company.edinet_code}/spotlight`,
                search: searchParams.toString(),
              })
            }
          />
        </div>
        <DimensionFilters allowAutoScope />
      </div>

      {!code ? (
        <p className="text-sm text-muted-foreground">企業を選択してください</p>
      ) : (
        <QueryState
          isLoading={query.isLoading || year == null}
          error={query.error}
          isEmpty={!query.data}
          empty="指定した企業のスポットライトデータがありません"
        >
          {query.data ? (
            <div className="space-y-6">
              <section className="space-y-1 text-sm leading-6">
                <h2 className="text-lg font-semibold">企業プロファイル</h2>
                <p>
                  企業名: {query.data.company_name}{' '}
                  <span className="font-mono text-muted-foreground">
                    ({query.data.edinet_code})
                  </span>
                </p>
                <p>業界: {query.data.industry ?? '(industry 未取得)'}</p>
                <p>
                  評価次元: {SCOPE_LABELS[query.data.scope]} ×{' '}
                  {WORKER_TYPE_LABELS[query.data.worker_type]}
                  {query.data.scope_auto ? '（自動推定）' : ''}
                </p>
                <p>対象年度: {query.data.fiscal_year}</p>
              </section>

              <IndustryRankCards rank={query.data.industry_rank} year={query.data.fiscal_year} />

              <PeerViolins
                title="業界 peer 分布"
                groupLabel="業界 peer"
                peers={query.data.industry_peers}
                target={query.data.target}
              />
              <PeerViolins
                title="規模類似 peer 分布（対数スケール ±0.3 dex）"
                groupLabel="規模 peer"
                peers={query.data.size_peers}
                target={query.data.target}
              />

              <section className="space-y-2">
                <h2 className="text-lg font-semibold">4 種の「理想値」と現在値の差分</h2>
                <p className="text-xs text-muted-foreground">
                  業界 P75 / 規模 peer P75 / 理想クラスタ平均（3 指標すべて P75 以上 AND 営業利益率 P50 以上） / 業界トップ10 平均 を並べます。
                </p>
                <BenchmarkTable benchmarks={query.data.benchmarks} />
              </section>

              {query.data.ideal_cluster.length > 0 ? (
                <section className="space-y-2">
                  <p className="text-xs text-muted-foreground">
                    理想クラスタの構成企業数: {query.data.ideal_cluster.length} 社。クラスタ業種分布を以下に示します。
                  </p>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>業種</TableHead>
                        <TableHead className="text-right">社数</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {industryDist.map(([industry, count]) => (
                        <TableRow key={industry}>
                          <TableCell>{industry}</TableCell>
                          <TableCell className="text-right tabular-nums">{count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </section>
              ) : null}
            </div>
          ) : null}
        </QueryState>
      )}
    </div>
  )
}

const RANK_LABELS: Record<IndustryRankMetricKey, string> = {
  sales: '売上高 ランク',
  operating_profit: '営業利益 ランク',
  female_manager_ratio: '女性管理職比率 ランク',
}

function IndustryRankCards({ rank, year }: { rank: IndustryRank; year: number }) {
  if (!rank.industry) return null
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">
        業種内ランク（{rank.industry}・{year}年度）
      </h2>
      <p className="text-xs text-muted-foreground">
        同業種 {rank.industry_total} 社の中でこの企業がどの位置にいるか
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        {rank.metrics.map((metric) => (
          <RankCard
            key={metric.key}
            label={RANK_LABELS[metric.key]}
            rank={metric.rank}
            total={metric.among}
          />
        ))}
      </div>
    </section>
  )
}

function RankCard({
  label,
  rank,
  total,
}: {
  label: string
  rank: number | null
  total: number
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tabular-nums">
          {rank != null ? `${rank} 位` : '—'}
        </p>
        <p className="text-xs text-muted-foreground">
          {rank != null ? `/ ${total} 社中` : ''}
        </p>
      </CardContent>
    </Card>
  )
}

function PeerViolins({
  title,
  groupLabel,
  peers,
  target,
}: {
  title: string
  groupLabel: string
  peers: SpotlightPeer[]
  target: SpotlightTarget
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {peers.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {title} に該当する peer がありません（n=0）。
        </p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {groupLabel}: {peerNote(peers.length)}
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {HC_METRICS.map((metric) => {
              const plot = violinData(peers, metric, target[metric])
              return (
                <Plot
                  key={metric}
                  data={plot.data}
                  layout={plot.layout}
                  height={350}
                />
              )
            })}
          </div>
        </>
      )}
    </section>
  )
}

function BenchmarkTable({
  benchmarks,
}: {
  benchmarks: Record<HcMetric, BenchmarkSet>
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>指標</TableHead>
          <TableHead className="text-right">現在値</TableHead>
          <TableHead className="text-right">業界 P75</TableHead>
          <TableHead className="text-right">規模 peer P75</TableHead>
          <TableHead className="text-right">理想クラスタ平均</TableHead>
          <TableHead className="text-right">業界トップ10 平均</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {HC_METRICS.map((metric) => {
          const row = benchmarks[metric]
          return (
            <TableRow key={metric}>
              <TableCell>{HC_METRIC_LABELS[metric]}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row?.current)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row?.industry_p75)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row?.size_peer_p75)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row?.ideal_cluster_avg)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(row?.industry_top10_avg)}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
