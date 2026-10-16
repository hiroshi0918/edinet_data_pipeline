import { expect, test } from 'vitest'

import { balanceHeadline, barSpan, boxColumns, incomeStory, rowsRange, standardLabel, waterfallRows } from '@/lib/statements'
import type { StatementPart } from '@/lib/types'

function part(key: string, amount: number | null): StatementPart {
  return { key, label: key, hint: '', amount, share: null }
}

const income = {
  net_sales: 1000,
  sales_source: 'statement' as const,
  cost_of_sales: 600,
  gross_profit: 400,
  sga_expenses: 300,
  operating_income: 100,
  ordinary_income: 90,
  net_income: 60,
}

test('waterfallRows は売上から純利益まで、差し引きの棒をはさむ', () => {
  const rows = waterfallRows(income)

  expect(rows.map((row) => row.key)).toEqual([
    'net_sales',
    'net_sales>gross_profit',
    'gross_profit',
    'gross_profit>operating_income',
    'operating_income',
    'operating_income>net_income',
    'net_income',
  ])
  expect(rows[1]).toMatchObject({ kind: 'delta', start: 1000, end: 400, value: -600 })
})

test('waterfallRows は欠けた段を飛ばし、売上が無ければ空', () => {
  const rows = waterfallRows({ ...income, gross_profit: null })
  expect(rows.map((row) => row.key)).toEqual([
    'net_sales',
    'net_sales>operating_income',
    'operating_income',
    'operating_income>net_income',
    'net_income',
  ])
  expect(rows[1].label).toBe('本業の費用')
  expect(waterfallRows({ ...income, net_sales: null })).toEqual([])
})

test('incomeStory は売上を食った費用と、最後に残った分を帯にする', () => {
  const story = incomeStory(waterfallRows(income))

  expect(story.headline).toBe(
    '売上 1,000円 のうち、本業で残るのは 100円（売上の 10.0%）。最後に残るのは 60円（売上の 6.0%）です。',
  )
  expect(story.slices.map((slice) => slice.amount)).toEqual([600, 300, 40])
  expect(story.remainder).toMatchObject({ key: 'net_income', amount: 60, shareLabel: '6.0%' })
  expect(story.note).toBeNull()
  expect(story.steps.find((step) => step.key === 'gross_profit')?.shareLabel).toBe('40.0%')
})

test('incomeStory は売上を超える費用で帯を止め、赤字を見出しに出す', () => {
  const story = incomeStory(waterfallRows({ ...income, operating_income: -50, net_income: -80 }))

  expect(story.headline).toBe('売上 1,000円 のうち、本業は −50円 の赤字。最後は −80円 の赤字です。')
  expect(story.slices.map((slice) => slice.key)).toEqual(['net_sales>gross_profit'])
  expect(story.remainder).toMatchObject({ key: 'gross_profit', amount: 400 })
  expect(story.note).toBe('人件費・広告などの費用が粗利を上回り、本業の利益は −50円 です。')
})

test('incomeStory は利益が増える段を帯に入れず、式のあとに書く', () => {
  const story = incomeStory(waterfallRows({ ...income, net_income: 150 }))

  expect(story.remainder).toMatchObject({ key: 'operating_income', amount: 100 })
  expect(story.note).toBe('そのあと 50円 増えて、最後に残った利益は 150円 です。')
})

test('rowsRange と barSpan は赤字でも 0 を含む', () => {
  const rows = waterfallRows({ ...income, operating_income: -50, net_income: -80 })
  const range = rowsRange(rows)
  expect(range).toEqual({ min: -80, max: 1000 })
  expect(barSpan(0, -80, range.min, range.max)).toEqual({ left: 0, width: 80 / 1080 })
})

test('balanceHeadline は返さなくてよいお金を、債務超過ではマイナスだと書く', () => {
  const net = (amount: number | null) => [{ key: 'net_assets', label: '純資産', hint: '', amount, share: null }]
  expect(balanceHeadline(100_000_000_000, net(70_000_000_000))).toBe(
    '持ち物は 1,000億円 です。出どころも同じ額で、700億円（70.0%）は返さなくてよいお金です。',
  )
  expect(balanceHeadline(100_000_000_000, net(-5_000_000_000))).toBe(
    '持ち物は 1,000億円 です。純資産は −50億円 で、負債が持ち物を上回っています。',
  )
  expect(balanceHeadline(100_000_000_000, net(null))).toBe('持ち物は 1,000億円 です。')
})

test('boxColumns は高い方の柱を 1 にし、負や空の項目を落とす', () => {
  const columns = boxColumns(
    [part('cash', 300), part('other', 700), part('inventories', 0)],
    [part('liabilities', 1100), part('net_assets', -100)],
  )
  expect(columns.assets.map((block) => block.key)).toEqual(['cash', 'other'])
  expect(columns.assets[0].height).toBeCloseTo(300 / 1100)
  expect(columns.funding).toHaveLength(1)
  expect(columns.funding[0].height).toBe(1)
})

test('standardLabel は連結・単体と会計基準を並べる', () => {
  expect(standardLabel({ basis: 'consolidated', accounting_standard: 'ifrs' })).toBe('連結・国際会計基準')
  expect(standardLabel({ basis: 'non_consolidated', accounting_standard: 'jgaap' })).toBe('単体・日本基準')
  expect(standardLabel({ basis: null, accounting_standard: null })).toBe('')
})
