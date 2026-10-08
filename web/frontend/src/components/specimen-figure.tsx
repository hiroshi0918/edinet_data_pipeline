// 業種の標本。絵は1枚。無い業種は卵。段階はキャプションに出る。
import { specimenCaption, specimenPortrait } from '@/lib/specimen'

export function SpecimenFigure({
  industry,
  level,
}: {
  industry: string | null
  level: number | null
}) {
  const portrait = specimenPortrait(industry)
  const caption = specimenCaption(industry, level)

  return (
    <figure className="flex w-full shrink-0 flex-col items-center">
      {portrait ? (
        <img
          src={portrait}
          alt={caption}
          className="h-auto w-auto max-h-[26rem] max-w-full object-contain object-bottom sm:max-h-[32rem] lg:max-h-[40rem]"
        />
      ) : (
        <svg viewBox="0 0 120 120" className="h-auto w-52 overflow-visible sm:w-72" aria-hidden="true">
          <ellipse cx="60" cy="76" rx="18" ry="23" fill="var(--label)" stroke="var(--ink)" strokeWidth="1.6" />
          <path d="M48 72c6-4 18-4 24 0" fill="none" stroke="var(--pencil)" strokeWidth="1.2" />
          <circle cx="60" cy="82" r="3" fill="var(--ink)" />
        </svg>
      )}
      <figcaption className="mt-2 text-center font-mono text-[11px] leading-none text-pencil">
        {caption}
      </figcaption>
    </figure>
  )
}
