// 選んだ会社の札。上の検索で別の会社をひらける。
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

  return (
    <div className="space-y-8">
      <div className="max-w-md">
        <CompanyCombobox
          searchRemote
          placeholder="ほかの会社をひらく"
          selectedCode={code}
          selectedLabel={
            sheetQuery.data
              ? `${sheetQuery.data.company_name} (${sheetQuery.data.edinet_code})`
              : undefined
          }
          onSelect={(company) => navigate(`/companies/${company.edinet_code}`)}
        />
      </div>
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
