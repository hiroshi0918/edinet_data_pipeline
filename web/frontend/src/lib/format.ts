// 円 → 億円、給与は万円。null は "—"。unit: false は見出し側に単位がある表用。
type FormatOptions = { unit?: boolean }

function isBlank(value: number | null | undefined): value is null | undefined {
  return value == null || Number.isNaN(value)
}

function withUnit(amount: string, unit: string, options?: FormatOptions): string {
  if (options?.unit === false) return amount
  return `${amount} ${unit}`
}

export function formatOkuYen(
  value: number | null | undefined,
  options?: FormatOptions,
): string {
  if (isBlank(value)) return '—'
  const amount = (value / 1e8).toLocaleString('ja-JP', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
  return withUnit(amount, '億円', options)
}

// 兆・億・万で丸める。1兆以上は小数1桁、それ未満は整数。負は「−」を付ける。
export function formatYenShort(value: number | null | undefined): string {
  if (isBlank(value)) return '—'
  const sign = value < 0 ? '−' : ''
  const abs = Math.abs(value)
  if (abs >= 1e12) {
    return `${sign}${(abs / 1e12).toLocaleString('ja-JP', { maximumFractionDigits: 1 })}兆円`
  }
  if (abs >= 1e8) return `${sign}${Math.round(abs / 1e8).toLocaleString('ja-JP')}億円`
  if (abs >= 1e4) return `${sign}${Math.round(abs / 1e4).toLocaleString('ja-JP')}万円`
  return `${sign}${Math.round(abs).toLocaleString('ja-JP')}円`
}

export function formatPeople(
  value: number | null | undefined,
  options?: FormatOptions,
): string {
  if (isBlank(value)) return '—'
  const amount = Math.round(value).toLocaleString('ja-JP')
  return withUnit(amount, '人', options)
}

export function formatManYen(
  value: number | null | undefined,
  options?: FormatOptions,
): string {
  if (isBlank(value)) return '—'
  const amount = Math.round(value / 1e4).toLocaleString('ja-JP')
  return withUnit(amount, '万円', options)
}

export function formatYears(
  value: number | null | undefined,
  options?: FormatOptions,
): string {
  if (isBlank(value)) return '—'
  return withUnit(value.toFixed(1), '年', options)
}

export function formatAge(
  value: number | null | undefined,
  options?: FormatOptions,
): string {
  if (isBlank(value)) return '—'
  return withUnit(value.toFixed(1), '歳', options)
}

export function formatMultiple(value: number | null | undefined): string {
  if (isBlank(value)) return '—'
  return `${value.toFixed(1)}倍`
}

export function formatRatioAsPct(value: number | null | undefined): string {
  if (isBlank(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export function formatPct(value: number | null | undefined): string {
  if (isBlank(value)) return '—'
  return `${value.toFixed(1)}%`
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (isBlank(value)) return '—'
  return value.toLocaleString('ja-JP', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return value
}

export function formatCount(value: number | null | undefined, unit: string): string {
  if (isBlank(value)) return '—'
  return `${value.toLocaleString('ja-JP')} ${unit}`
}
