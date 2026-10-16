// 会社のお財布。最新の有報の財務諸表を、簿記を知らない人向けに、札と箱と棒で読む。
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import { CharacterImage } from '@/components/character-image'
import { QueryState } from '@/components/query-state'
import { BalanceBoxes } from '@/components/statements/balance-boxes'
import { CashFlowBars } from '@/components/statements/cash-flow-bars'
import { ProfitWaterfall } from '@/components/statements/profit-waterfall'
import { fetchStatements } from '@/lib/api'
import { specimenNo } from '@/lib/specimen'
import { cashFlowRows, standardLabel, waterfallRows } from '@/lib/statements'
import type { StatementInsight, StatementsResponse, StatementTone } from '@/lib/types'

const TONE_BAR: Record<StatementTone, string> = {
  good: '#0070d1',
  neutral: '#6b6b6b',
  caution: '#d53b00',
}

export function StatementsPage() {
  const { code } = useParams()
  const query = useQuery({
    queryKey: ['statements', code],
    queryFn: () => fetchStatements(code ?? ''),
    enabled: Boolean(code),
  })
  const data = query.data

  return (
    <QueryState isLoading={query.isLoading} error={query.error} isEmpty={!data} empty="お財布が見つかりません。">
      {data ? <StatementsView data={data} /> : null}
    </QueryState>
  )
}

function StatementsView({ data }: { data: StatementsResponse }) {
  const basis = standardLabel(data)
  return (
    <article className="space-y-10">
      <header className="space-y-5">
        <Link
          className="inline-flex h-11 items-center gap-1.5 text-base text-link underline decoration-link/30 underline-offset-4 hover:decoration-link"
          to={`/companies/${data.edinet_code}`}
        >
          <ArrowLeftIcon className="size-4" strokeWidth={3} aria-hidden="true" />
          シートに戻る
        </Link>
        <div className="flex items-end gap-4 sm:gap-6">
          <div className="flex size-24 shrink-0 items-end justify-center rounded-lg bg-[#f5f7fa] sm:size-32">
            <CharacterImage industry={data.industry} idle eager className="h-[115%] w-auto" />
          </div>
          <div className="min-w-0 pb-1">
            <p className="text-xs font-bold text-ink sm:text-sm">
              <span className="font-num font-bold tracking-wide">{specimenNo(data.industry)}</span>
              {' · '}
              {data.industry ?? '業種なし'}
              {data.fiscal_year != null ? ` · ${data.fiscal_year}年度` : ''}
              {basis ? ` · ${basis}` : ''}
            </p>
            <h1 className="mt-1 text-3xl leading-tight font-light text-ink sm:text-4xl">{data.company_name}のお財布</h1>
          </div>
        </div>
      </header>

      {data.note ? (
        <p className="sheet border-l-4 px-5 py-4 text-sm leading-7 text-ink" style={{ borderLeftColor: 'var(--amber)' }}>
          {data.note}
        </p>
      ) : null}

      {data.balance_sheet == null ? (
        <p className="sheet p-6 text-sm font-bold text-ink-soft">この会社の財務諸表は、まだ有報から取れていません。</p>
      ) : (
        <>
          {data.insights.length > 0 ? <Insights insights={data.insights} /> : null}

          <Section title="持ち物と、そのお金の出どころ">
            <BalanceBoxes
              totalAssets={data.balance_sheet.total_assets}
              assets={data.balance_sheet.assets}
              funding={data.balance_sheet.funding}
            />
            {!data.balance_sheet.debt_known ? (
              <p className="mt-4 text-xs text-ink-soft">
                この会社は借入金を独自の項目で開示しているため、負債を借入金とそれ以外に分けていません。
              </p>
            ) : null}
          </Section>

          <Section title="売上が手元に残るまで">
            <IncomeBody income={data.income_statement} />
          </Section>

          <Section title="1年のお金の流れ">
            <CashFlowBody cashFlow={data.cash_flow} />
          </Section>
        </>
      )}
    </article>
  )
}

function Insights({ insights }: { insights: StatementInsight[] }) {
  return (
    <section aria-labelledby="statements-insights" className="space-y-3">
      <h2
        id="statements-insights"
        className="text-[1.375rem] leading-tight font-light text-ink"
      >
        ひとことで言うと
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {insights.map((insight) => (
          <li
            key={insight.key}
            className="sheet border-l-4 px-5 py-4"
            style={{ borderLeftColor: TONE_BAR[insight.tone] }}
          >
            <p className="text-lg font-light text-ink">{insight.label}</p>
            <p className="mt-1 text-sm leading-6 text-ink">{insight.text}</p>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink">札は一般的な目安で出しています。業種によって当たり前の形は違います。</p>
    </section>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="sheet px-5 py-6 sm:px-8 sm:py-8">
      <h2 className="text-[1.375rem] font-light text-ink sm:text-[1.75rem]">{title}</h2>
      <div className="mt-6">{children}</div>
    </section>
  )
}

function IncomeBody({ income }: { income: StatementsResponse['income_statement'] }) {
  const rows = income ? waterfallRows(income) : []
  if (!income || rows.length === 0) {
    return <p className="text-sm text-ink-soft">売上が有報から取れていないため、表示できません。</p>
  }
  return (
    <>
      <ProfitWaterfall rows={rows} />
      {income.sales_source === 'summary' ? (
        <p className="mt-4 text-xs text-ink-soft">売上は、有報の「経営指標等」の値です。</p>
      ) : null}
    </>
  )
}

function CashFlowBody({ cashFlow }: { cashFlow: StatementsResponse['cash_flow'] }) {
  if (!cashFlow || cashFlowRows(cashFlow).every((row) => row.value == null)) {
    return <p className="text-sm text-ink-soft">キャッシュ・フローは、この有報から取れていません。</p>
  }
  return (
    <>
      <CashFlowBars rows={cashFlowRows(cashFlow)} />
      {cashFlow.pattern ? (
        <div className="mt-6 border-l-4 bg-platinum px-4 py-3" style={{ borderLeftColor: TONE_BAR[cashFlow.pattern.tone] }}>
          <p className="text-base font-medium text-ink">{cashFlow.pattern.label}</p>
          <p className="mt-1 text-sm leading-6 text-ink">{cashFlow.pattern.text}</p>
        </div>
      ) : null}
    </>
  )
}
