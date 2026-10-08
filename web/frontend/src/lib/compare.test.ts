import { describe, expect, it } from 'vitest'

import { alignedValues, compareYears, latestValue, metricValue } from './compare'
import type { StoryResponse } from './types'

function story(code: string, rows: [number, number | null, number | null][]): StoryResponse {
  return {
    edinet_code: code,
    company_name: code,
    industry: null,
    fiscal_year: rows.at(-1)?.[0] ?? null,
    series: rows.map(([fiscal_year, sales, operating_profit]) => ({
      fiscal_year,
      sales,
      operating_profit,
      employee_count: null,
    })),
    narrative: { business: null, history: [], rewritten: false },
  }
}

describe('compareYears', () => {
  it('最新年がずれていても、両社を合わせた直近の年度にそろえる', () => {
    const a = story('A', [[2022, 100, 10], [2023, 110, 12]])
    const b = story('B', [[2023, 50, 5], [2024, 60, 6]])
    expect(compareYears([a, b])).toEqual([2022, 2023, 2024])
  })

  it('10年度を超えたら古い年を落とす', () => {
    const rows: [number, number, number][] = Array.from({ length: 12 }, (_, i) => [2013 + i, 100, 10])
    const years = compareYears([story('A', rows)])
    expect(years).toHaveLength(10)
    expect(years[0]).toBe(2015)
  })

  it('値が無い年は数えない', () => {
    expect(compareYears([story('A', [[2020, null, null], [2021, 1, 1]])])).toEqual([2021])
  })
})

describe('metricValue', () => {
  it('営業利益率は売上が正のときだけ', () => {
    expect(metricValue({ fiscal_year: 1, sales: 200, operating_profit: 20, employee_count: null }, 'operating_margin')).toBe(0.1)
    expect(metricValue({ fiscal_year: 1, sales: 0, operating_profit: 20, employee_count: null }, 'operating_margin')).toBeNull()
  })
})

describe('alignedValues / latestValue', () => {
  it('無い年は null で埋める', () => {
    const b = story('B', [[2023, 50, 5]])
    expect(alignedValues(b, [2022, 2023, 2024], 'sales')).toEqual([null, 50, null])
  })

  it('最新の値と年度を返す', () => {
    const a = story('A', [[2022, 100, 10], [2023, null, null]])
    expect(latestValue(a, 'sales')).toEqual({ year: 2022, value: 100 })
  })
})
