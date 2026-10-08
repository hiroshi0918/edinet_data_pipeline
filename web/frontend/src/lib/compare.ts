// 2社の歩みを年度でそろえる。両社の年度を合わせた直近10年度を横軸にする。
import type { StoryPoint, StoryResponse } from '@/lib/types'

export const COMPARE_WINDOW = 10

export type CompareMetric = 'sales' | 'operating_profit' | 'operating_margin'

export function metricValue(point: StoryPoint | undefined, metric: CompareMetric): number | null {
  if (!point) return null
  if (metric === 'operating_margin') {
    if (point.sales == null || point.sales <= 0 || point.operating_profit == null) return null
    return point.operating_profit / point.sales
  }
  return point[metric]
}

export function compareYears(stories: StoryResponse[]): number[] {
  const years = new Set<number>()
  for (const story of stories) {
    for (const point of story.series) {
      if (point.sales != null || point.operating_profit != null) years.add(point.fiscal_year)
    }
  }
  if (years.size === 0) return []
  const latest = Math.max(...years)
  const earliest = Math.max(Math.min(...years), latest - (COMPARE_WINDOW - 1))
  const range: number[] = []
  for (let year = earliest; year <= latest; year += 1) range.push(year)
  return range
}

export function alignedValues(story: StoryResponse, years: number[], metric: CompareMetric): (number | null)[] {
  const byYear = new Map(story.series.map((point) => [point.fiscal_year, point]))
  return years.map((year) => metricValue(byYear.get(year), metric))
}

export function latestValue(story: StoryResponse, metric: CompareMetric): { year: number; value: number } | null {
  for (const point of [...story.series].reverse()) {
    const value = metricValue(point, metric)
    if (value != null) return { year: point.fiscal_year, value }
  }
  return null
}
