// 図鑑の表紙。ラベンダーの板に箱文字、検索、業種のタイル。
import { useQuery } from '@tanstack/react-query'
import { ArrowDownIcon, ArrowRightIcon } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { CharacterImage } from '@/components/character-image'
import { CompanyCombobox } from '@/components/company-combobox'
import { SectionHeading } from '@/components/section-heading'
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
    <section className="chamfer relative overflow-hidden border border-chrome bg-lavender">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-35"
        style={{
          backgroundImage:
            'linear-gradient(var(--chrome) 1px, transparent 1px), linear-gradient(90deg, var(--chrome) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />
      <div className="relative grid items-end gap-6 px-5 py-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div>
          <p className="inline-block bg-surface px-2 py-1 text-[11px] font-bold tracking-wide text-ink">
            有価証券報告書から生まれた、いきものの図鑑
          </p>
          <h1 className="box-art mt-4 text-[clamp(3.25rem,10vw,6.5rem)] leading-none">会社図鑑</h1>
          <div className="mt-6 max-w-xl">
            <CompanyCombobox
              size="hero"
              searchRemote
              placeholder="会社の名前でさがす"
              onSelect={(company) => navigate(`/companies/${company.edinet_code}`)}
            />
          </div>
          <a href="#index" className="mt-4 inline-flex h-11 items-center gap-2 text-sm font-bold text-ink">
            業種からさがす
            <ArrowDownIcon className="size-4 text-signal" strokeWidth={2.75} />
          </a>
        </div>
        <div className="relative min-h-44">
          <p className="absolute top-0 right-0 z-10 max-w-44 bg-surface px-3 py-2 text-[11px] leading-snug font-bold text-carbon shadow-[0_2px_0_var(--chrome)]">
            会社図鑑へようこそ
          </p>
          <div className="absolute inset-x-0 bottom-0 flex items-end justify-end">
            {CAST.map((industry) => (
              <CharacterImage key={industry} industry={industry} eager className="-mr-3 h-32 w-auto sm:h-40" />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function IndustryIndex() {
  const query = useQuery({ queryKey: ['industries'], queryFn: fetchIndustries })
  const entries = industryIndex(query.data?.industries)

  return (
    <section id="index" className="scroll-mt-28 pt-8">
      <SectionHeading
        as="h2"
        title="業種の目次"
        description="33の業種に、それぞれのいきものがいます。押すと、その業種の会社が点の順に並びます。"
      />
      <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {entries.map((entry) => (
          <IndexTile key={entry.no} entry={entry} />
        ))}
      </ul>
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
        className="press group flex h-full flex-col border border-chrome bg-periwinkle p-2"
      >
        <span className="flex items-center justify-between gap-1">
          <span className="font-num text-[10px] font-bold tracking-wider text-carbon">{entry.no}</span>
          <span className="flex size-6 items-center justify-center bg-surface text-[11px] font-black text-carbon">
            {entry.label}
          </span>
        </span>
        <span className="flex h-24 items-end justify-center">
          <CharacterImage industry={entry.industry} className="h-full w-auto" />
        </span>
        <span className="mt-1 line-clamp-2 min-h-[2.4em] text-xs leading-snug font-bold text-ink">{name}</span>
        <span className="mt-auto flex items-center justify-between pt-2">
          <span className="font-num text-[11px] text-carbon">
            {entry.companyCount == null ? '—' : `${entry.companyCount.toLocaleString('ja-JP')}社`}
          </span>
          <span className="inline-flex size-6 items-center justify-center rounded-full bg-signal text-carbon">
            <ArrowRightIcon className="size-3.5" strokeWidth={3} aria-hidden="true" />
          </span>
        </span>
      </Link>
    </li>
  )
}

function OtherWays() {
  return (
    <section className="pt-8">
      <div className="grid gap-3 md:grid-cols-2">
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
    <Link to={to} className="press group relative flex min-h-40 flex-col overflow-hidden border border-chrome bg-lavender p-5">
      <span className="text-lg font-black text-ink">{title}</span>
      <span className="mt-2 max-w-[16rem] text-sm leading-6 text-ink">{body}</span>
      <span className="mt-4 inline-flex size-8 items-center justify-center rounded-full bg-signal text-carbon">
        <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" strokeWidth={3} aria-hidden="true" />
      </span>
      <CharacterImage industry={industry} className="absolute -right-1 bottom-0 h-32 w-auto sm:h-36" />
    </Link>
  )
}
