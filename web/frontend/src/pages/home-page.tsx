// 図鑑の表紙。ロゴと検索、丘を歩くキャラの行進、業種の目次。
import { useQuery } from '@tanstack/react-query'
import { ArrowDownIcon, ArrowRightIcon } from 'lucide-react'
import { motion, useScroll, useTransform } from 'motion/react'
import { type CSSProperties, useRef } from 'react'
import { Link, useNavigate } from 'react-router'

import { CharacterImage } from '@/components/character-image'
import { CompanyCombobox } from '@/components/company-combobox'
import { SectionHeading } from '@/components/section-heading'
import { fetchIndustries } from '@/lib/api'
import { type IndustryEntry, industryIndex } from '@/lib/specimen'

const TITLE = ['会', '社', '図', '鑑']
const TITLE_TILT = [-4, 3, -2, 4]
const PARADE = industryIndex(undefined).map((entry) => entry.industry)
const FRONT_ROW = PARADE.filter((_, index) => index % 2 === 0)
const BACK_ROW = PARADE.filter((_, index) => index % 2 === 1)
const EGG_NAME = 'そのほかの法人'

export function HomePage() {
  return (
    <>
      <Hero />
      <IndustryIndex />
      <OtherWays />
    </>
  )
}

function Hero() {
  const navigate = useNavigate()
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const titleY = useTransform(scrollYProgress, [0, 1], [0, 140])
  const titleOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0])
  const backY = useTransform(scrollYProgress, [0, 1], [0, 90])
  const hillY = useTransform(scrollYProgress, [0, 1], [0, 40])
  const frontY = useTransform(scrollYProgress, [0, 1], [0, -30])

  return (
    <section ref={ref} className="relative flex min-h-svh flex-col overflow-hidden">
      <motion.div
        aria-hidden="true"
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="absolute top-[9%] left-1/2 size-[min(78vw,36rem)] -translate-x-1/2 rounded-full bg-marker/55"
      />
      <motion.div
        style={{ y: titleY, opacity: titleOpacity }}
        className="relative z-10 mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-5 pt-20 pb-6 text-center"
      >
        <motion.p
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="rounded-full border-[length:var(--line)] border-ink bg-page px-4 py-1.5 text-xs font-bold text-ink shadow-ink-sm sm:text-sm"
        >
          有価証券報告書から生まれた、いきものの図鑑
        </motion.p>
        <h1
          aria-label="会社図鑑"
          className="mt-5 flex text-[clamp(3.75rem,min(17vw,17vh),9.5rem)] leading-[1.05] font-black tracking-[0.02em] text-ink [text-shadow:0.06em_0.06em_0_var(--page)]"
        >
          {TITLE.map((char, index) => (
            <motion.span
              key={char}
              aria-hidden="true"
              initial={{ opacity: 0, y: 50, scale: 0.3, rotate: 0 }}
              animate={{ opacity: 1, y: 0, scale: 1, rotate: TITLE_TILT[index] }}
              transition={{ type: 'spring', stiffness: 420, damping: 13, delay: 0.15 + index * 0.09 }}
              className="inline-block"
            >
              {char}
            </motion.span>
          ))}
        </h1>
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.7 }}
          className="mt-7 w-full max-w-xl"
        >
          <CompanyCombobox
            size="hero"
            searchRemote
            placeholder="会社の名前でさがす"
            onSelect={(company) => navigate(`/companies/${company.edinet_code}`)}
          />
        </motion.div>
        <motion.a
          href="#index"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="group mt-5 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold text-ink underline decoration-shu decoration-2 underline-offset-4"
        >
          業種からさがす
          <ArrowDownIcon className="size-4 transition-transform group-hover:translate-y-1" strokeWidth={2.75} />
        </motion.a>
      </motion.div>

      <div aria-hidden="true" className="relative h-[clamp(12rem,34vh,17rem)] shrink-0">
        <motion.div style={{ y: backY }} className="absolute inset-x-0 bottom-[46%]">
          <Parade industries={BACK_ROW} duration={95} itemClass="h-[clamp(3.75rem,10vh,6rem)]" reverseDelay />
        </motion.div>
        <motion.svg
          style={{ y: hillY }}
          viewBox="0 0 1440 200"
          preserveAspectRatio="none"
          className="absolute inset-x-0 bottom-0 h-[62%] w-full"
        >
          <path
            d="M0 70C160 20 300 20 440 52s260 50 420 12 300-64 420-30 120 30 160 26V200H0Z"
            fill="var(--paper-deep)"
            stroke="var(--ink)"
            strokeWidth="2.5"
            vectorEffect="non-scaling-stroke"
          />
        </motion.svg>
        <svg viewBox="0 0 1440 120" preserveAspectRatio="none" className="absolute inset-x-0 bottom-0 h-[30%] w-full">
          <path
            d="M0 40C240 10 480 6 720 26s480 30 720 4V120H0Z"
            fill="var(--page)"
            stroke="var(--ink)"
            strokeWidth="2.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <motion.div style={{ y: frontY }} className="absolute inset-x-0 bottom-[10%]">
          <Parade industries={FRONT_ROW} duration={70} itemClass="h-[clamp(7rem,20vh,10.5rem)]" />
        </motion.div>
      </div>
    </section>
  )
}

// 行進の帯。同じ並びを2周ぶん置き、半分ずらして継ぎ目を消す。
function Parade({
  industries,
  duration,
  itemClass,
  reverseDelay = false,
}: {
  industries: string[]
  duration: number
  itemClass: string
  reverseDelay?: boolean
}) {
  const loop = [...industries, ...industries]
  return (
    <motion.div
      initial={{ x: '35%' }}
      animate={{ x: 0 }}
      transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1], delay: reverseDelay ? 0.45 : 0.25 }}
      className="parade"
    >
      <div className="parade-track gap-[clamp(1rem,3vw,2.5rem)]" style={{ '--parade-duration': `${duration}s` } as CSSProperties}>
        {loop.map((industry, index) => (
          <div
            key={`${industry}-${index}`}
            className="parade-step shrink-0"
            style={{ '--step-delay': `${-(index % 5) * 0.18}s` } as CSSProperties}
          >
            <CharacterImage industry={industry} eager className={`${itemClass} w-auto`} />
          </div>
        ))}
      </div>
    </motion.div>
  )
}

function IndustryIndex() {
  const query = useQuery({ queryKey: ['industries'], queryFn: fetchIndustries })
  const entries = industryIndex(query.data?.industries)

  return (
    <section id="index" className="scroll-mt-4 border-t-[length:var(--line)] border-ink bg-paper-deep/60 px-4 py-20 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          as="h2"
          title="業種の目次"
          description="33の業種に、それぞれのいきものがいます。押すと、その業種の会社が点の順に並びます。"
        />
        <ul className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-5 md:grid-cols-4 lg:grid-cols-6">
          {entries.map((entry, index) => (
            <IndexTile key={entry.no} entry={entry} order={index} />
          ))}
        </ul>
      </div>
    </section>
  )
}

function IndexTile({ entry, order }: { entry: IndustryEntry; order: number }) {
  const name = entry.no === 'No.000' ? EGG_NAME : entry.industry
  return (
    <motion.li
      initial={{ opacity: 0, y: 28, scale: 0.94 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ type: 'spring', stiffness: 300, damping: 22, delay: (order % 6) * 0.05 }}
    >
      <Link
        to={`/rankings?industry=${encodeURIComponent(entry.industry)}`}
        aria-label={`${name}の会社を見る`}
        className="press group flex h-full flex-col rounded-3xl border-[length:var(--line)] border-ink bg-page p-3"
      >
        <span className="flex items-center justify-between">
          <span className="font-num text-[11px] font-black tracking-wider text-shu">{entry.no}</span>
          <span className="flex size-8 items-center justify-center rounded-full border-2 border-ink bg-marker text-sm font-black">
            {entry.label}
          </span>
        </span>
        <span className="flex h-28 items-end justify-center sm:h-32">
          <CharacterImage
            industry={entry.industry}
            className="h-full w-auto transition-transform duration-300 ease-(--ease-pop) group-hover:-translate-y-2 group-hover:-rotate-6 group-hover:scale-105"
          />
        </span>
        <span className="mt-2 line-clamp-2 min-h-[2.6em] text-sm leading-snug font-black text-ink">{name}</span>
        <span className="font-num mt-1 text-xs font-extrabold text-ink-soft">
          {entry.companyCount == null ? '—' : entry.companyCount.toLocaleString('ja-JP')}社
        </span>
      </Link>
    </motion.li>
  )
}

function OtherWays() {
  return (
    <section className="px-4 py-20 sm:px-8">
      <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-2">
        <WayLink
          to="/rankings"
          kicker="点の順"
          title="ランキングを見る"
          body="総合点や売上高の順に、図鑑の会社を並べます。"
          industry="サービス業"
        />
        <WayLink
          to="/nikkei225"
          kicker="225銘柄"
          title="日経225をめくる"
          body="日経平均の構成銘柄を、総合点の高い順に。"
          industry="輸送用機器"
        />
      </div>
    </section>
  )
}

function WayLink({
  to,
  kicker,
  title,
  body,
  industry,
}: {
  to: string
  kicker: string
  title: string
  body: string
  industry: string
}) {
  return (
    <Link
      to={to}
      className="press group relative flex min-h-56 flex-col overflow-hidden rounded-3xl border-[length:var(--line)] border-ink bg-page p-7 sm:p-9"
    >
      <span className="font-num text-xs font-black tracking-[0.18em] text-shu">{kicker}</span>
      <span className="mt-2 flex items-center gap-2 text-2xl font-black text-ink sm:text-3xl">
        {title}
        <ArrowRightIcon className="size-6 transition-transform group-hover:translate-x-1.5" strokeWidth={3} />
      </span>
      <span className="mt-3 max-w-[16rem] text-sm leading-7 text-ink-soft">{body}</span>
      <CharacterImage
        industry={industry}
        className="absolute -right-2 -bottom-8 h-44 w-auto transition-transform duration-300 ease-(--ease-pop) group-hover:-translate-y-3 group-hover:-rotate-6 sm:h-52"
      />
    </Link>
  )
}
