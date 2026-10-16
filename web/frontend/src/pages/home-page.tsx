// 表紙。黒い導入、白い業種の目次、暗い別の入り方。
import { useQuery } from '@tanstack/react-query'
import { ArrowDownIcon, ArrowRightIcon } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { CharacterImage } from '@/components/character-image'
import { CompanyCombobox } from '@/components/company-combobox'
import { fetchIndustries } from '@/lib/api'
import { type IndustryEntry, industryIndex } from '@/lib/specimen'

const CAST = ['サービス業', '輸送用機器', '銀行業']
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

  return (
    <section className="bg-black text-white">
      <div className="mx-auto grid max-w-[1280px] items-center gap-10 px-4 py-16 sm:px-12 md:py-24 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div>
          <p className="text-sm tracking-wide text-white/70">有価証券報告書から生まれた、いきものの図鑑</p>
          <h1 className="mt-4 text-[clamp(2.75rem,7vw,3.375rem)] leading-[1.25] font-light tracking-tight">会社図鑑</h1>
          <div className="mt-8 max-w-xl">
            <CompanyCombobox
              size="hero"
              searchRemote
              placeholder="会社の名前でさがす"
              onSelect={(company) => navigate(`/companies/${company.edinet_code}`)}
            />
          </div>
          <a
            href="#index"
            className="mt-6 inline-flex h-12 items-center gap-2 rounded-full border border-white/30 px-7 text-sm font-bold tracking-wide text-white"
          >
            業種からさがす
            <ArrowDownIcon className="size-4" strokeWidth={2.5} />
          </a>
        </div>
        <div className="flex items-end justify-center lg:justify-end">
          {CAST.map((industry, index) => (
            <CharacterImage
              key={industry}
              industry={industry}
              eager
              onPaper={false}
              className={index < CAST.length - 1 ? '-mr-8 h-44 w-auto sm:h-56' : 'h-44 w-auto sm:h-56'}
            />
          ))}
        </div>
      </div>
    </section>
  )
}

function IndustryIndex() {
  const query = useQuery({ queryKey: ['industries'], queryFn: fetchIndustries })
  const entries = industryIndex(query.data?.industries)

  return (
    <section id="index" className="scroll-mt-16 bg-white">
      <div className="mx-auto max-w-[1280px] px-4 py-16 sm:px-12 md:py-24">
        <h2 className="text-[1.75rem] leading-tight font-light sm:text-[2.75rem]">業種の目次</h2>
        <p className="mt-3 max-w-xl text-base leading-relaxed text-black/60">
          33の業種に、それぞれのいきものがいます。押すと、その業種の会社が点の順に並びます。
        </p>
        <ul className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {entries.map((entry) => (
            <IndexTile key={entry.no} entry={entry} />
          ))}
        </ul>
      </div>
    </section>
  )
}

function IndexTile({ entry }: { entry: IndustryEntry }) {
  const name = entry.no === 'No.000' ? EGG_NAME : entry.industry
  return (
    <li>
      <Link
        to={`/rankings?industry=${encodeURIComponent(entry.industry)}`}
        aria-label={`${name}の会社を見る`}
        className="group flex h-full flex-col rounded-lg bg-[#f5f7fa] p-3"
      >
        <span className="flex items-center justify-between gap-1">
          <span className="font-num text-xs tracking-wide text-black/60">{entry.no}</span>
          <span className="flex size-6 items-center justify-center rounded-full bg-white text-[11px] font-medium text-black">
            {entry.label}
          </span>
        </span>
        <span className="flex h-24 items-end justify-center">
          <CharacterImage industry={entry.industry} className="h-full w-auto" />
        </span>
        <span className="mt-2 line-clamp-2 min-h-[2.6em] text-sm leading-snug font-medium text-black">{name}</span>
        <span className="mt-auto flex items-center justify-between pt-3">
          <span className="font-num text-xs text-black/60">
            {entry.companyCount == null ? '—' : `${entry.companyCount.toLocaleString('ja-JP')}社`}
          </span>
          <span className="inline-flex size-8 items-center justify-center rounded-full bg-primary text-white">
            <ArrowRightIcon className="size-4" strokeWidth={2.5} aria-hidden="true" />
          </span>
        </span>
      </Link>
    </li>
  )
}

function OtherWays() {
  return (
    <section className="bg-[#121314] text-white">
      <div className="mx-auto grid max-w-[1280px] gap-4 px-4 py-16 sm:px-12 md:grid-cols-2 md:py-24">
        <WayLink
          to="/rankings"
          title="ランキングを見る"
          body="総合点や売上高の順に、図鑑の会社を並べます。"
          industry="サービス業"
        />
        <WayLink
          to="/nikkei225"
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
  title,
  body,
  industry,
}: {
  to: string
  title: string
  body: string
  industry: string
}) {
  return (
    <Link to={to} className="group relative flex min-h-48 flex-col overflow-hidden rounded-lg bg-[#181818] p-8">
      <span className="text-[1.375rem] leading-tight font-light">{title}</span>
      <span className="mt-3 max-w-[16rem] text-base leading-relaxed text-white/70">{body}</span>
      <span className="mt-6 inline-flex h-12 w-fit items-center gap-2 rounded-full bg-primary px-6 text-sm font-bold tracking-wide text-white">
        開く
        <ArrowRightIcon className="size-4" strokeWidth={2.5} aria-hidden="true" />
      </span>
      <span className="pointer-events-none absolute right-2 bottom-0 hidden h-36 w-28 sm:block">
        <span className="absolute inset-x-0 bottom-3 h-28 rounded-lg bg-[#f5f7fa]" />
        <CharacterImage industry={industry} className="absolute inset-x-0 bottom-3 h-32 w-full" />
      </span>
    </Link>
  )
}
