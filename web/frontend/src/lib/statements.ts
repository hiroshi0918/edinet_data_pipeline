// お財布の図の計算。箱の高さ、売上から利益までの段、お金の流れの棒。
import { formatRatioAsPct, formatYenShort } from '@/lib/format'
import type { StatementPart, StatementsResponse } from '@/lib/types'

type IncomeStatement = NonNullable<StatementsResponse['income_statement']>
type CashFlow = NonNullable<StatementsResponse['cash_flow']>

// 箱の色。PlayStation Blue の濃淡と黒で塗り分ける。
export const PART_FILLS: Record<string, { fill: string; dark: boolean }> = {
  cash: { fill: '#0070d1', dark: true },
  receivables: { fill: '#53b1ff', dark: true },
  inventories: { fill: '#004d8d', dark: true },
  property: { fill: '#121314', dark: true },
  intangibles: { fill: '#d6e6f5', dark: false },
  investments: { fill: '#8eb8e0', dark: true },
  other: { fill: '#f3f3f3', dark: false },
  debt: { fill: '#000000', dark: true },
  other_liabilities: { fill: '#1f2024', dark: true },
  liabilities: { fill: '#0064b7', dark: true },
  net_assets: { fill: '#e8f1fa', dark: false },
}

export type BoxBlock = StatementPart & { height: number }

// 左右の柱の高さは、高い方を 1 とした割合。債務超過では負債の柱が総資産より高くなる。
export function boxColumns(assets: StatementPart[], funding: StatementPart[]) {
  const positive = (parts: StatementPart[]) =>
    parts.filter((part) => (part.amount ?? 0) > 0)
  const sum = (parts: StatementPart[]) => parts.reduce((acc, part) => acc + (part.amount ?? 0), 0)
  const assetParts = positive(assets)
  const fundingParts = positive(funding)
  const scale = Math.max(sum(assetParts), sum(fundingParts), 1)
  const toBlocks = (parts: StatementPart[]): BoxBlock[] =>
    parts.map((part) => ({ ...part, height: (part.amount ?? 0) / scale }))
  return { assets: toBlocks(assetParts), funding: toBlocks(fundingParts) }
}

// 持ち物の合計と、返さなくてよいお金。債務超過のときは純資産がマイナスだと書く。
export function balanceHeadline(totalAssets: number, funding: StatementPart[]): string {
  const total = formatYenShort(totalAssets)
  const net = funding.find((part) => part.key === 'net_assets')
  if (net?.amount == null) return `持ち物は ${total} です。`
  if (net.amount < 0) {
    return `持ち物は ${total} です。純資産は ${formatYenShort(net.amount)} で、負債が持ち物を上回っています。`
  }
  if (net.amount === 0) return `持ち物は ${total} です。返さなくてよいお金はありません。`
  const share = totalAssets > 0 ? `（${formatRatioAsPct(net.amount / totalAssets)}）` : ''
  return `持ち物は ${total} です。出どころも同じ額で、${formatYenShort(net.amount)}${share}は返さなくてよいお金です。`
}

export type WaterfallRow = {
  key: string
  label: string
  kind: 'total' | 'delta'
  start: number
  end: number
  value: number
}

const MILESTONES = [
  { key: 'net_sales', label: '売上' },
  { key: 'gross_profit', label: '粗利' },
  { key: 'operating_income', label: '本業の利益' },
  { key: 'net_income', label: '最後に残った利益' },
] as const

const DELTA_LABELS: Record<string, string> = {
  'net_sales>gross_profit': '原価（作る・仕入れる費用）',
  'gross_profit>operating_income': '人件費・広告などの費用',
  'net_sales>operating_income': '本業の費用',
  'operating_income>net_income': '利息・税金など',
  'gross_profit>net_income': '費用・利息・税金など',
  'net_sales>net_income': '費用・利息・税金など',
}

// 売上から、取れている利益の段だけをたどる。段と段の間は差し引きの棒。
export function waterfallRows(income: IncomeStatement): WaterfallRow[] {
  const present = MILESTONES.filter((milestone) => income[milestone.key] != null)
  if (present.length === 0 || present[0].key !== 'net_sales') return []

  const rows: WaterfallRow[] = []
  let previous: { key: string; value: number } | null = null
  for (const milestone of present) {
    const value = income[milestone.key] as number
    if (previous) {
      const key = `${previous.key}>${milestone.key}`
      rows.push({
        key,
        label: DELTA_LABELS[key],
        kind: 'delta',
        start: previous.value,
        end: value,
        value: value - previous.value,
      })
    }
    rows.push({ key: milestone.key, label: milestone.label, kind: 'total', start: 0, end: value, value })
    previous = { key: milestone.key, value }
  }
  return rows
}

export type SalesSlice = {
  key: string
  label: string
  amount: number
  share: number
  shareLabel: string
}

export type IncomeStep = WaterfallRow & { shareLabel: string | null }

export type IncomeStory = {
  headline: string
  slices: SalesSlice[]
  remainder: SalesSlice | null
  note: string | null
  steps: IncomeStep[]
}

// 売上を 100% とした帯と、その下に出す式。帯は費用が売上を食いきる手前まで。
export function incomeStory(rows: WaterfallRow[]): IncomeStory {
  const sales = rows.find((row) => row.kind === 'total' && row.key === 'net_sales') ?? null
  const built = sales && sales.value > 0 ? buildBand(rows, sales.value) : { slices: [], remainder: null, note: null }
  return {
    headline: incomeHeadline(rows, sales),
    slices: built.slices,
    remainder: built.remainder,
    note: built.note,
    steps: rows.map((row) => ({
      ...row,
      shareLabel:
        sales && sales.value > 0 && row.kind === 'total' && row.key !== 'net_sales'
          ? formatSignedShare(row.value / sales.value)
          : null,
    })),
  }
}

function buildBand(rows: WaterfallRow[], sales: number) {
  const slices: SalesSlice[] = []
  let remainder: SalesSlice | null = null
  let note: string | null = null
  let consumed = 0
  let previous = rows.find((row) => row.kind === 'total')

  for (let index = 0; index < rows.length; index++) {
    const row = rows[index]
    if (row.kind === 'delta') {
      const next = rows[index + 1]
      if (!next || next.kind !== 'total' || !previous) break
      if (row.value > 0) {
        const rest = rows.slice(index + 2)
        if (rest.length === 0 && slices.length > 0) {
          note = `そのあと ${formatYenShort(row.value)} 増えて、${next.label}は ${formatYenShort(next.value)} です。`
        }
        break
      }
      const eat = -row.value
      if (consumed + eat > sales + 0.5) {
        note = `${row.label}が${previous.label}を上回り、${next.label}は ${formatYenShort(next.value)} です。`
        break
      }
      if (eat > 0) {
        slices.push(slice(row.key, row.label, eat, sales))
        consumed += eat
      }
      continue
    }
    if (row.key === 'net_sales') continue
    if (row.value <= 0) {
      remainder = null
      break
    }
    remainder = slice(row.key, row.label, row.value, sales)
    previous = row
  }

  return { slices, remainder, note }
}

function slice(key: string, label: string, amount: number, sales: number): SalesSlice {
  const share = amount / sales
  return { key, label, amount, share, shareLabel: formatRatioAsPct(share) }
}

function incomeHeadline(rows: WaterfallRow[], sales: WaterfallRow | null): string {
  if (!sales) return ''
  const salesYen = formatYenShort(sales.value)
  const totals = rows.filter((row) => row.kind === 'total')
  if (totals.length === 1 || sales.value <= 0) return `売上は ${salesYen} です。`

  const bridge =
    totals.find((row) => row.key === 'operating_income') ?? totals.find((row) => row.key === 'gross_profit')
  const net = totals.find((row) => row.key === 'net_income')
  const focus = [bridge, net].filter((row): row is WaterfallRow => row != null)
  const unique = focus.filter((row, index) => focus.findIndex((item) => item.key === row.key) === index)
  const body = unique.map((row) => resultClause(row, sales.value)).join('。')
  return `売上 ${salesYen} のうち、${body}です。`
}

function resultClause(row: WaterfallRow, sales: number): string {
  const amount = formatYenShort(row.value)
  if (row.value === 0) {
    if (row.key === 'operating_income') return '本業で残るのは 0円'
    if (row.key === 'net_income') return '最後に残るのは 0円'
    return `${row.label}は 0円`
  }
  if (row.value < 0) {
    if (row.key === 'operating_income') return `本業は ${amount} の赤字`
    if (row.key === 'net_income') return `最後は ${amount} の赤字`
    return `${row.label}は ${amount} の赤字`
  }
  const share = sales > 0 ? `（売上の ${formatRatioAsPct(row.value / sales)}）` : ''
  if (row.key === 'operating_income') return `本業で残るのは ${amount}${share}`
  if (row.key === 'net_income') return `最後に残るのは ${amount}${share}`
  return `${row.label}は ${amount}${share}`
}

function formatSignedShare(ratio: number): string {
  const pct = formatRatioAsPct(Math.abs(ratio))
  return ratio < 0 ? `−${pct}` : pct
}

// 横棒の位置。0 を含む範囲に対する左端と幅の割合。
export function barSpan(start: number, end: number, min: number, max: number) {
  const span = max - min || 1
  const low = Math.min(start, end)
  const high = Math.max(start, end)
  return { left: (low - min) / span, width: (high - low) / span }
}

export function rowsRange(rows: WaterfallRow[]) {
  const values = rows.flatMap((row) => [row.start, row.end])
  return { min: Math.min(0, ...values), max: Math.max(0, ...values) }
}

export type CashFlowRow = {
  key: 'operating' | 'investing' | 'financing'
  label: string
  hint: string
  value: number | null
}

export function cashFlowRows(cashFlow: CashFlow): CashFlowRow[] {
  return [
    { key: 'operating', label: '本業のお金', hint: '商品やサービスを売って入ったお金から、仕入れや給料で出たお金を引いた残り', value: cashFlow.operating },
    { key: 'investing', label: '投資のお金', hint: '設備や他社の株を買うと出ていき、売ると入る', value: cashFlow.investing },
    { key: 'financing', label: '借入れ・返済・配当', hint: '借りる・増資すると入り、返す・配当を払うと出ていく', value: cashFlow.financing },
  ]
}

export function standardLabel(response: Pick<StatementsResponse, 'accounting_standard' | 'basis'>) {
  const basis = response.basis === 'consolidated' ? '連結' : response.basis === 'non_consolidated' ? '単体' : null
  const standard =
    response.accounting_standard === 'ifrs' ? '国際会計基準' : response.accounting_standard === 'jgaap' ? '日本基準' : null
  return [basis, standard].filter(Boolean).join('・')
}
