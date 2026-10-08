// 会社の歩み。10年のグラフと、有報の事業・沿革。
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { QueryState } from '@/components/query-state'
import { YearChart } from '@/components/year-chart'
import { fetchStory } from '@/lib/api'

export function StoryPage() {
  const { code } = useParams()
  const query = useQuery({
    queryKey: ['story', code],
    queryFn: () => fetchStory(code ?? ''),
    enabled: Boolean(code),
  })
  const story = query.data

  return (
    <div className="space-y-6">
      <QueryState
        isLoading={query.isLoading}
        error={query.error}
        isEmpty={!story}
        empty="歩みが見つかりません。"
      >
        {story ? (
          <section className="space-y-6 rounded-2xl bg-[#e7eef2] p-5 sm:p-6">
            <div>
              <Link
                className="text-sm font-medium text-[#1f6f68] hover:underline"
                to={`/companies/${story.edinet_code}`}
              >
                シートに戻る
              </Link>
              <p className="mt-3 text-sm text-[#5c7380]">
                {story.industry ?? '業種なし'}
                {story.fiscal_year != null ? ` · ${story.fiscal_year}年度までの10年` : ''}
              </p>
              <h1 className="text-2xl font-semibold tracking-tight text-[#16303a]">
                {story.company_name}の歩み
              </h1>
            </div>
            <div className="grid gap-3 lg:grid-cols-3">
              <YearChart
                title="売上高"
                kind="yen"
                points={story.series.map((point) => ({
                  fiscal_year: point.fiscal_year,
                  value: point.sales,
                }))}
              />
              <YearChart
                title="営業利益"
                kind="yen"
                points={story.series.map((point) => ({
                  fiscal_year: point.fiscal_year,
                  value: point.operating_profit,
                }))}
              />
              <YearChart
                title="従業員数"
                kind="people"
                points={story.series.map((point) => ({
                  fiscal_year: point.fiscal_year,
                  value: point.employee_count,
                }))}
              />
            </div>
            <article className="rounded-xl border border-[#d5e0e3] bg-white p-4">
              <h2 className="text-sm font-medium text-[#16303a]">事業</h2>
              {story.narrative.business ? (
                <>
                  <p className="mt-2 text-sm leading-6 text-[#16303a]">
                    {story.narrative.business.text}
                  </p>
                  <details className="mt-3 text-sm text-[#5c7380]">
                    <summary>原文</summary>
                    <p className="mt-2 whitespace-pre-wrap">{story.narrative.business.source}</p>
                  </details>
                </>
              ) : (
                <p className="mt-2 text-sm text-[#5c7380]">事業の内容は、この有報から取れていません。</p>
              )}
            </article>
            <article className="rounded-xl border border-[#d5e0e3] bg-white p-4">
              <h2 className="text-sm font-medium text-[#16303a]">これまでの歩み</h2>
              {story.narrative.history.length === 0 ? (
                <p className="mt-2 text-sm text-[#5c7380]">沿革は、この有報から取れていません。</p>
              ) : (
                <ol className="mt-3 space-y-3">
                  {story.narrative.history.map((beat) => (
                    <li key={`${beat.label}-${beat.text}`} className="text-sm leading-6">
                      {beat.label ? (
                        <p className="text-xs tracking-wide text-[#5c7380]">{beat.label}</p>
                      ) : null}
                      <p className="text-[#16303a]">{beat.text}</p>
                    </li>
                  ))}
                </ol>
              )}
            </article>
          </section>
        ) : null}
      </QueryState>
    </div>
  )
}
