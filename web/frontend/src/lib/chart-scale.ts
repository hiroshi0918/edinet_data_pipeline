// 折れ線の目盛り。縦軸はかならず 0 を含め、小さな変化を大きく見せない。
export type ChartKind = 'yen' | 'people' | 'pct'

export type Axis = {
  ticks: number[]
  min: number
  max: number
  divisor: number
  unit: string
}

function niceStep(raw: number): number {
  if (!(raw > 0) || !Number.isFinite(raw)) return 1
  const exp = Math.floor(Math.log10(raw))
  const base = 10 ** exp
  const fraction = raw / base
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10
  return nice * base
}

function roundTo(value: number, step: number): number {
  const digits = Math.max(0, -Math.floor(Math.log10(step)) + 2)
  return Number(value.toFixed(digits))
}

// values の最小・最大と 0 を含む、切りのよい目盛り（既定で4区間前後）。
export function niceTicks(values: number[], count = 4): { ticks: number[]; min: number; max: number } {
  const finite = values.filter((value) => Number.isFinite(value))
  let low = Math.min(0, ...finite)
  let high = Math.max(0, ...finite)
  if (low === high) high = low + 1
  const step = niceStep((high - low) / count)
  low = Math.floor(low / step) * step
  high = Math.ceil(high / step) * step
  const ticks: number[] = []
  for (let tick = low; tick <= high + step / 2; tick += step) ticks.push(roundTo(tick, step))
  return { ticks, min: ticks[0], max: ticks[ticks.length - 1] }
}

// 目盛りの単位。億円が4桁を超えたら兆円、人が1万を超えたら万人。
export function axisUnit(kind: ChartKind, maxAbs: number): { divisor: number; unit: string } {
  if (kind === 'yen') return maxAbs >= 1e12 ? { divisor: 1e12, unit: '兆円' } : { divisor: 1e8, unit: '億円' }
  if (kind === 'people') return maxAbs >= 1e4 ? { divisor: 1e4, unit: '万人' } : { divisor: 1, unit: '人' }
  return { divisor: 0.01, unit: '%' }
}

export function buildAxis(values: number[], kind: ChartKind, count = 4): Axis {
  const { ticks, min, max } = niceTicks(values, count)
  const maxAbs = Math.max(Math.abs(min), Math.abs(max))
  return { ticks, min, max, ...axisUnit(kind, maxAbs) }
}

export function formatTick(value: number, divisor: number): string {
  const scaled = value / divisor
  return (Math.abs(scaled) < 1e-9 ? 0 : scaled).toLocaleString('ja-JP', { maximumFractionDigits: 2 })
}

// 年のラベルを出す位置。7年以上なら1年おき。最新年はかならず出す。
export function yearLabelIndexes(length: number): number[] {
  const every = length > 6 ? 2 : 1
  const indexes: number[] = []
  for (let index = length - 1; index >= 0; index -= every) indexes.unshift(index)
  return indexes
}
