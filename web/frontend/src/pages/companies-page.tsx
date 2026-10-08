// 会社図鑑の入口。社名を選ぶと最新有報のシートを出す。
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'

import { CompanyCombobox } from '@/components/company-combobox'
import { CompanySheet } from '@/components/company-sheet'
import { PageHeader } from '@/components/page-header'
import { QueryState } from '@/components/query-state'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
    <div className="space-y-6">
      {!code ? (
        <PageHeader
          kicker="Zukan"
          title="会社を開く"
          description="社名を選ぶと、最新の有報から業種内の位置がシートになります。"
        />
      ) : null}

      <div className="max-w-xl space-y-1.5">
        <p className="text-sm font-medium">社名</p>
        <CompanyCombobox
          searchRemote
          selectedCode={code}
          selectedLabel={
            sheetQuery.data
              ? `${sheetQuery.data.company_name} (${sheetQuery.data.edinet_code})`
              : undefined
          }
          onSelect={(company) => navigate(`/companies/${company.edinet_code}`)}
        />
      </div>

      {!code ? (
        <Alert>
          <AlertDescription>社名を選んでください。</AlertDescription>
        </Alert>
      ) : (
        <QueryState
          isLoading={sheetQuery.isLoading}
          error={sheetQuery.error}
          isEmpty={!sheetQuery.data}
          empty="指定した会社のシートが見つかりません。"
        >
          {sheetQuery.data ? <CompanySheet sheet={sheetQuery.data} /> : null}
        </QueryState>
      )}
    </div>
  )
}
