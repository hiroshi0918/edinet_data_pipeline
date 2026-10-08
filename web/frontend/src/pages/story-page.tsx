// 会社の歩み。10年のグラフと、有報の事業・沿革を絵本のように読む。
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { Link, useParams } from 'react-router'

import { CharacterImage } from '@/components/character-image'
import { QueryState } from '@/components/query-state'
import { YearChart } from '@/components/year-chart'
import { fetchStory } from '@/lib/api'
import { specimenNo } from '@/lib/specimen'

export function StoryPage() {
  const { code } = useParams()
  const query = useQuery({
    queryKey: ['story', code],
    queryFn: () => fetchStory(code ?? ''),
    enabled: Boolean(code),
  })
  const story = query.data

  return (
    <QueryState isLoading={query.isLoading} error={query.error} isEmpty={!story} empty="歩みが見つかりません。">
      {story ? (
        <article className="space-y-12">
          <header className="space-y-5">
            <Link
              className="inline-flex items-center gap-1.5 rounded-full text-sm font-bold text-ink underline decoration-shu decoration-2 underline-offset-4"
              to={`/companies/${story.edinet_code}`}
            >
              <ArrowLeftIcon className="size-4" strokeWidth={3} aria-hidden="true" />
              シートに戻る
            </Link>
            <div className="flex items-end gap-4 sm:gap-6">
              <motion.div
                initial={{ opacity: 0, scale: 0.6, rotate: -10 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 14 }}
                className="flex size-24 shrink-0 items-end justify-center rounded-full border-[length:var(--line)] border-ink bg-marker sm:size-32"
              >
                <CharacterImage industry={story.industry} idle eager className="h-[115%] w-auto" />
              </motion.div>
              <div className="min-w-0 pb-1">
                <p className="text-xs font-bold text-ink-soft sm:text-sm">
                  <span className="font-num font-black text-shu">{specimenNo(story.industry)}</span>
                  {' · '}
                  {story.industry ?? '業種なし'}
                  {story.fiscal_year != null ? ` · ${story.fiscal_year}年度までの10年` : ''}
                </p>
                <h1 className="mt-1 text-3xl leading-tight font-black text-ink sm:text-4xl">
                  <span className="marker-line">{story.company_name}の歩み</span>
                </h1>
              </div>
            </div>
          </header>

          <div className="grid gap-5 lg:grid-cols-3">
            <YearChart
              title="売上高"
              kind="yen"
              delayMs={150}
              points={story.series.map((point) => ({ fiscal_year: point.fiscal_year, value: point.sales }))}
            />
            <YearChart
              title="営業利益"
              kind="yen"
              delayMs={300}
              points={story.series.map((point) => ({
                fiscal_year: point.fiscal_year,
                value: point.operating_profit,
              }))}
            />
            <YearChart
              title="従業員数"
              kind="people"
              delayMs={450}
              points={story.series.map((point) => ({
                fiscal_year: point.fiscal_year,
                value: point.employee_count,
              }))}
            />
          </div>

          <section className="sheet mx-auto max-w-3xl px-6 py-8 sm:px-10 sm:py-10">
            <h2 className="text-xs font-black tracking-[0.2em] text-shu">事業</h2>
            {story.narrative.business ? (
              <>
                <p className="mt-4 text-lg leading-9 text-ink sm:text-xl sm:leading-10">
                  {story.narrative.business.text}
                </p>
                <details className="group mt-6 text-sm text-ink-soft">
                  <summary className="cursor-pointer font-bold text-ink underline decoration-ink/30 underline-offset-4">
                    原文
                  </summary>
                  <p className="mt-3 rounded-2xl bg-paper p-4 leading-7 whitespace-pre-wrap">
                    {story.narrative.business.source}
                  </p>
                </details>
              </>
            ) : (
              <p className="mt-3 text-sm text-ink-soft">事業の内容は、この有報から取れていません。</p>
            )}
          </section>

          <section className="mx-auto max-w-3xl">
            <h2 className="text-2xl font-black text-ink">
              <span className="marker-line">これまでの歩み</span>
            </h2>
            {story.narrative.history.length === 0 ? (
              <p className="mt-3 text-sm text-ink-soft">沿革は、この有報から取れていません。</p>
            ) : (
              <ol className="relative mt-8 space-y-6 pl-10 before:absolute before:top-2 before:bottom-2 before:left-[0.9rem] before:border-l-[3px] before:border-dashed before:border-ink/40">
                {story.narrative.history.map((beat, index) => (
                  <motion.li
                    key={`${beat.label}-${beat.text}`}
                    initial={{ opacity: 0, x: -16 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: '-30px' }}
                    transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: Math.min(index, 4) * 0.05 }}
                    className="relative"
                  >
                    <span
                      aria-hidden="true"
                      className="absolute top-1 -left-10 size-[1.85rem] rounded-full border-[length:var(--line)] border-ink bg-marker shadow-ink-sm"
                    />
                    {beat.label ? <p className="font-num text-sm font-black text-shu">{beat.label}</p> : null}
                    <p className="mt-0.5 text-base leading-8 text-ink">{beat.text}</p>
                  </motion.li>
                ))}
              </ol>
            )}
          </section>
        </article>
      ) : null}
    </QueryState>
  )
}
