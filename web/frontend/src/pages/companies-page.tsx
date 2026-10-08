// 会社図鑑の入口。社名を選ぶと最新有報の札が出る。
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'

import { CompanyCombobox } from '@/components/company-combobox'
import { CompanySheet } from '@/components/company-sheet'
import { QueryState } from '@/components/query-state'
import { fetchSheet } from '@/lib/api'

export function CompaniesPage() {
  const { code } = useParams()
  const navigate = useNavigate()
  const sheetQuery = useQuery({
    queryKey: ['sheet', code],
    queryFn: () => fetchSheet(code ?? ''),
    enabled: Boolean(code),
  })

  const search = (
    <div className="max-w-xl space-y-1.5">
      <p className="font-mono text-[11px] text-pencil">社名</p>
      <CompanyCombobox
        searchRemote
        placeholder="社名を選ぶ"
        selectedCode={code}
        selectedLabel={
          sheetQuery.data
            ? `${sheetQuery.data.company_name} (${sheetQuery.data.edinet_code})`
            : undefined
        }
        onSelect={(company) => navigate(`/companies/${company.edinet_code}`)}
      />
    </div>
  )

  if (!code) {
    return (
      <section className="plate max-w-3xl px-5 py-8 pr-16 sm:px-8 sm:py-10 sm:pr-24">
        <p className="font-mono text-[11px] text-pencil">図鑑</p>
        <h1 className="mt-3 text-3xl text-ink sm:text-4xl">会社を開く</h1>
        <p className="mt-3 max-w-md text-sm leading-6 text-pencil">
          社名を選ぶと、最新の有報が1枚の札になります。
        </p>
        <div className="mt-8">{search}</div>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      {search}
      <QueryState
        isLoading={sheetQuery.isLoading}
        error={sheetQuery.error}
        isEmpty={!sheetQuery.data}
        empty="指定した会社のシートが見つかりません。"
      >
        {sheetQuery.data ? <CompanySheet sheet={sheetQuery.data} /> : null}
      </QueryState>
    </div>
  )
}
