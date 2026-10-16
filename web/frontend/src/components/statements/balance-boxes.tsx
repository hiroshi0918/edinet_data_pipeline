// 持ち物と、そのお金の出どころ。幅は持ち物の合計に対する割合。金額は触れた区間に出す。
import { formatRatioAsPct } from '@/lib/format'
import { balanceHeadline, PART_FILLS } from '@/lib/statements'
import type { StatementPart } from '@/lib/types'

import { HoverBand, type HoverSlice } from './hover-band'

const CAPTION = '幅は、持ち物の合計に対する割合です。'

export function BalanceBoxes({
  totalAssets,
  assets,
  funding,
}: {
  totalAssets: number
  assets: StatementPart[]
  funding: StatementPart[]
}) {
  return (
    <div className="space-y-6">
      <p className="text-base leading-7 font-bold text-ink sm:text-lg">{balanceHeadline(totalAssets, funding)}</p>
      <Band title="持ち物" caption="資産" parts={toSlices(assets, totalAssets)} />
      <Band title="お金の出どころ" caption="負債と純資産" parts={toSlices(funding, totalAssets)} />
    </div>
  )
}

function Band({ title, caption, parts }: { title: string; caption: string; parts: HoverSlice[] }) {
  if (parts.length === 0) return null
  return (
    <div>
      <p className="text-base font-light text-ink">
        {title}
        <span className="ml-1.5 text-xs font-bold text-ink-soft">{caption}</span>
      </p>
      <HoverBand parts={parts} caption={CAPTION} room="pt-40" />
    </div>
  )
}

function toSlices(parts: StatementPart[], total: number): HoverSlice[] {
  return parts.flatMap((part) => {
    if (part.amount == null || part.amount <= 0) return []
    const style = PART_FILLS[part.key] ?? PART_FILLS.other
    const share = part.share ?? (total > 0 ? part.amount / total : null)
    const shareLabel = share == null ? '' : formatRatioAsPct(share)
    return [
      {
        key: part.key,
        label: part.label,
        amount: part.amount,
        fill: style.fill,
        dark: style.dark,
        shareLabel,
        shareText: shareLabel ? `持ち物の ${shareLabel}` : '',
        hint: part.hint,
      },
    ]
  })
}
