// 業種で比べる。中央値昇順の横向き箱ひげ。
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { Data } from 'plotly.js'

import { Plot } from '@/components/charts/plot'
import { DimensionFilters } from '@/components/filters/dimension-filters'
import { PageHeader } from '@/components/page-header'
import { QueryState } from '@/components/query-state'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useFilters } from '@/hooks/use-filters'
import { fetchHcDistribution } from '@/lib/api'
import { HC_METRIC_LABELS, HC_METRICS } from '@/lib/constants'
import type { HcDistributionRow, HcMetric } from '@/lib/types'

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!
}

function groupByIndustry(rows: HcDistributionRow[]) {
  const map = new Map<string, number[]>()
  for (const row of rows) {
    const list = map.get(row.industry) ?? []
    list.push(row.value)
    map.set(row.industry, list)
  }
  return [...map.entries()]
    .map(([industry, values]) => ({ industry, values, median: median(values) }))
    .sort((a, b) => a.median - b.median)
}

export function IndustryPage() {
  const { year, scope, worker_type, metric, setFilter } = useFilters()
  const query = useQuery({
    queryKey: ['hc-distribution', year, scope, worker_type, metric],
    queryFn: () =>
      fetchHcDistribution({
        year: year!,
        scope,
        worker_type,
        metric,
      }),
    enabled: year != null,
  })

  const grouped = useMemo(
    () => groupByIndustry(query.data?.rows ?? []),
    [query.data?.rows],
  )

  const plotData = useMemo<Data[]>(() => {
    const n = grouped.length
    return grouped.map((item, index) => {
      const t = n <= 1 ? 1 : index / (n - 1)
      const color = `oklch(${0.72 - t * 0.22} 0.12 ${200 + t * 40})`
      return {
        type: 'box',
        x: item.values,
        name: item.industry,
        orientation: 'h',
        boxpoints: 'outliers',
        marker: { color, size: 4, opacity: 0.5 },
        line: { color, width: 1.4 },
        fillcolor: color,
        hovertemplate: `${item.industry}<br>${HC_METRIC_LABELS[metric]}: %{x:.1f}%<extra></extra>`,
      } satisfies Data
    })
  }, [grouped, metric])

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="By industry"
        title="業種で比べる"
        description="人的資本指標の業種別分布を箱ひげ図で表示します。箱は四分位、縦線は中央値、外側の点は外れ値です。開示 5 社未満の業種は API 側で除外済みです。"
      />
      <DimensionFilters />
      <Tabs
        value={metric}
        onValueChange={(value) => setFilter({ metric: value as HcMetric })}
      >
        <TabsList>
          {HC_METRICS.map((item) => (
            <TabsTrigger key={item} value={item}>
              {HC_METRIC_LABELS[item]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <QueryState
        isLoading={query.isLoading || year == null}
        error={query.error}
        isEmpty={!query.data?.rows.length}
        empty={`${year} 年度・選択次元で、${HC_METRIC_LABELS[metric]} を 5 社以上開示している業種がありません。`}
      >
        <Plot
          data={plotData}
          height={Math.max(420, 26 * grouped.length)}
          layout={{
            showlegend: false,
            xaxis: { title: { text: `${HC_METRIC_LABELS[metric]} (%)` }, ticksuffix: '%' },
            margin: { l: 160, r: 24, t: 16, b: 48 },
          }}
        />
        {metric === 'male_childcare_leave_ratio' ? (
          <p className="text-xs text-muted-foreground">
            男性育休取得率は前年度の出産に当年度取得した等の集計タイミングで 100% を超える値が正当に発生します。箱の外の点として表示され、中央値ベースの並びには影響しません。
          </p>
        ) : null}
        <p className="text-xs text-muted-foreground">
          対象: {grouped.length} 業種 / {query.data?.rows.length.toLocaleString('ja-JP')} 社
          {year != null ? ` (${year} 年度)` : ''}
        </p>
      </QueryState>
    </div>
  )
}
