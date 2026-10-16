// 売上が手元に残るまで。帯の幅は売上に対する割合。金額は、触れた区間の上に出す。
import { incomeStory, type SalesSlice } from '@/lib/statements'

import { HoverBand, type HoverSlice } from './hover-band'

const SLICE_FILLS = ['#0070d1', '#121314', '#53b1ff']
const SLICE_DARK = [true, true, false]
const REMAINDER_FILL = 'var(--systems-teal)'

export function ProfitWaterfall({ rows }: { rows: Parameters<typeof incomeStory>[0] }) {
  const story = incomeStory(rows)
  const parts = bandParts(story.slices, story.remainder)

  return (
    <div className="space-y-5">
      <p className="text-base leading-7 font-bold text-ink sm:text-lg">{story.headline}</p>
      {parts.length > 0 ? <HoverBand parts={parts} caption="幅は、売上を 100% としたときの割合です。" /> : null}
      {story.note ? (
        <p className="border-l-4 border-primary bg-[#f5f7fa] px-4 py-3 text-sm leading-6 text-ink">{story.note}</p>
      ) : null}
    </div>
  )
}

function bandParts(slices: SalesSlice[], remainder: SalesSlice | null): HoverSlice[] {
  return [
    ...slices.map((slice, index) => toSlice(slice, SLICE_FILLS[index % SLICE_FILLS.length], SLICE_DARK[index % SLICE_DARK.length])),
    ...(remainder ? [toSlice(remainder, REMAINDER_FILL, true)] : []),
  ]
}

function toSlice(slice: SalesSlice, fill: string, dark: boolean): HoverSlice {
  return {
    key: slice.key,
    label: slice.label,
    amount: slice.amount,
    fill,
    dark,
    shareLabel: slice.shareLabel,
    shareText: `売上の ${slice.shareLabel}`,
  }
}
