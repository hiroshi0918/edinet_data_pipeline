// 業種の標本。すみかの円の上にキャラが立ち、図鑑番号と段階が札に出る。
import { motion } from 'motion/react'

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
      <div className="relative flex aspect-square w-full max-w-[26rem] items-end justify-center">
        <div
          aria-hidden="true"
          className="absolute inset-[6%] rounded-full border-[length:var(--line)] border-ink bg-paper-deep"
        />
        <div
          aria-hidden="true"
          className="absolute inset-x-[14%] bottom-[9%] h-[10%] rounded-[50%] bg-ink/10"
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.55, y: 40 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 14 }}
          className="relative h-[96%] w-full"
        >
          <CharacterImage
            industry={industry}
            variant="full"
            alt={caption}
            idle
            eager
            className="mx-auto h-full w-auto"
          />
        </motion.div>
      </div>
      <figcaption className="-mt-3 flex items-center gap-2 rounded-full border-[length:var(--line)] border-ink bg-page px-4 py-1.5 shadow-ink-sm">
        <span className="font-num text-xs font-black text-shu">{specimenNo(industry)}</span>
        <span className="text-sm font-black text-ink">{caption}</span>
      </figcaption>
    </figure>
  )
}
