// 業種の標本。ペリウィンクルの板の上にキャラが立ち、番号と段階が札に出る。
import { CharacterImage } from '@/components/character-image'
import { specimenCaption, specimenNo } from '@/lib/specimen'

export function SpecimenFigure({
  industry,
  level,
}: {
  industry: string | null
  level: number | null
}) {
  const caption = specimenCaption(industry, level)

  return (
    <figure className="relative flex w-full flex-col items-center">
      <div className="relative aspect-square w-full max-w-[26rem]">
        <div aria-hidden="true" className="absolute inset-[8%] rounded-lg bg-[#f5f7fa]" />
        <div className="absolute inset-x-0 top-0 bottom-[4%]">
          <CharacterImage
            industry={industry}
            variant="full"
            alt={caption}
            eager
            className="mx-auto h-full w-auto"
          />
        </div>
      </div>
      <figcaption className="relative z-10 -mt-2 flex items-center gap-2 rounded-full bg-white px-4 py-2">
        <span className="font-num text-xs font-medium tracking-wide text-ink-soft">{specimenNo(industry)}</span>
        <span className="text-sm font-medium text-ink">{caption}</span>
      </figcaption>
    </figure>
  )
}
