// 企業を調べる。従業員情報 3 指標は提出会社×全労働者の行から取る。
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'

import { CompanyCombobox } from '@/components/company-combobox'
import { DimensionFilters } from '@/components/filters/dimension-filters'
import { PageHeader } from '@/components/page-header'
import { QueryState } from '@/components/query-state'
import { RatioBar } from '@/components/ratio-bar'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useFilters } from '@/hooks/use-filters'
import { fetchCompany } from '@/lib/api'
import {
  DEFAULT_SCOPE,
  DEFAULT_WORKER_TYPE,
  EMPLOYEE_INFO_LABELS,
  FINANCIAL_METRIC_LABELS,
  HC_METRIC_LABELS,
  SCOPE_LABELS,
  WORKER_TYPE_LABELS,
} from '@/lib/constants'
import {
  formatAge,
  formatCount,
  formatDate,
  formatManYen,
  formatOkuYen,
  formatPeople,
  formatYears,
} from '@/lib/format'
import type { CompanyMetricRow, Scope } from '@/lib/types'

type NumericKey = {
  [K in keyof CompanyMetricRow]: CompanyMetricRow[K] extends number | null ? K : never
}[keyof CompanyMetricRow]

type MetricFormat = (
  value: number | null | undefined,
  options?: { unit?: boolean },
) => string

type CompanyMetric = {
  key: NumericKey
  group: 'financial' | 'hc' | 'employee'
  cardLabel: string
  historyLabel: string
  format: MetricFormat
  employeeInfo?: boolean
}

function formatRatio(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(1)
}

const COMPANY_METRICS: CompanyMetric[] = [
  {
    key: 'sales',
    group: 'financial',
    cardLabel: FINANCIAL_METRIC_LABELS.sales,
    historyLabel: '売上高 (億円)',
    format: formatOkuYen,
  },
  {
    key: 'operating_profit',
    group: 'financial',
    cardLabel: FINANCIAL_METRIC_LABELS.operating_profit,
    historyLabel: '営業利益 (億円)',
    format: formatOkuYen,
  },
  {
    key: 'net_profit',
    group: 'financial',
    cardLabel: FINANCIAL_METRIC_LABELS.net_profit,
    historyLabel: '純利益 (億円)',
    format: formatOkuYen,
  },
  {
    key: 'employee_count',
    group: 'financial',
    cardLabel: FINANCIAL_METRIC_LABELS.employee_count,
    historyLabel: '従業員数 (人)',
    format: formatPeople,
  },
  {
    key: 'female_manager_ratio',
    group: 'hc',
    cardLabel: HC_METRIC_LABELS.female_manager_ratio,
    historyLabel: '女性管理職比率 (%)',
    format: formatRatio,
  },
  {
    key: 'male_childcare_leave_ratio',
    group: 'hc',
    cardLabel: HC_METRIC_LABELS.male_childcare_leave_ratio,
    historyLabel: '男性育休取得率 (%)',
    format: formatRatio,
  },
  {
    key: 'gender_wage_gap',
    group: 'hc',
    cardLabel: HC_METRIC_LABELS.gender_wage_gap,
    historyLabel: '男女賃金格差 (%)',
    format: formatRatio,
  },
  {
    key: 'average_annual_salary',
    group: 'employee',
    cardLabel: EMPLOYEE_INFO_LABELS.average_annual_salary,
    historyLabel: '平均年間給与 (万円)',
    format: formatManYen,
    employeeInfo: true,
  },
  {
    key: 'average_years_of_service',
    group: 'employee',
    cardLabel: EMPLOYEE_INFO_LABELS.average_years_of_service,
    historyLabel: '平均勤続年数 (年)',
    format: formatYears,
    employeeInfo: true,
  },
  {
    key: 'average_age',
    group: 'employee',
    cardLabel: EMPLOYEE_INFO_LABELS.average_age,
    historyLabel: '平均年齢 (歳)',
    format: formatAge,
    employeeInfo: true,
  },
]

const FINANCIAL_METRICS = COMPANY_METRICS.filter((item) => item.group === 'financial')
const HC_METRICS = COMPANY_METRICS.filter((item) => item.group === 'hc')
const EMPLOYEE_METRICS = COMPANY_METRICS.filter((item) => item.group === 'employee')

function pickRow(
  rows: CompanyMetricRow[],
  fiscalYear: number,
  scope: Scope,
  workerType: CompanyMetricRow['worker_type'],
) {
  return (
    rows.find(
      (row) =>
        row.fiscal_year === fiscalYear &&
        row.scope === scope &&
        row.worker_type === workerType,
    ) ?? null
  )
}

export function CompaniesPage() {
  const { code } = useParams()
  const navigate = useNavigate()
  const { year, scope, worker_type, searchParams, meta, metaQuery } = useFilters()
  const companyQuery = useQuery({
    queryKey: ['company', code],
    queryFn: () => fetchCompany(code!),
    enabled: Boolean(code),
  })

  const row =
    companyQuery.data && year != null
      ? pickRow(companyQuery.data.rows, year, scope, worker_type)
      : null
  const employeeRow =
    companyQuery.data && year != null
      ? pickRow(
          companyQuery.data.rows,
          year,
          DEFAULT_SCOPE,
          DEFAULT_WORKER_TYPE,
        )
      : null

  const years = companyQuery.data
    ? [...new Set(companyQuery.data.rows.map((item) => item.fiscal_year))].sort(
        (a, b) => b - a,
      )
    : []

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Company lookup"
        title="企業を調べる"
        description="会社名・年度・開示範囲を選ぶと、その 1 社の有価証券報告書に記載された財務指標と人的資本指標を確認できます。"
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <KpiCard
          label="企業数 (年度重複排除)"
          value={formatCount(meta?.company_count, '社')}
          loading={metaQuery.isLoading}
        />
        <KpiCard
          label="収録年度数"
          value={formatCount(meta?.year_count, '年度')}
          loading={metaQuery.isLoading}
        />
        <KpiCard
          label="最新提出日"
          value={formatDate(meta?.latest_submission)}
          loading={metaQuery.isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="space-y-1.5">
          <p className="text-sm font-medium">会社名で検索・選択</p>
          <CompanyCombobox
            selectedCode={code}
            selectedLabel={
              companyQuery.data
                ? `${companyQuery.data.company_name} (${companyQuery.data.edinet_code})`
                : undefined
            }
            onSelect={(company) =>
              navigate({
                pathname: `/companies/${company.edinet_code}`,
                search: searchParams.toString(),
              })
            }
          />
        </div>
        <DimensionFilters />
      </div>

      {!code ? (
        <Alert>
          <AlertDescription>企業を選択してください</AlertDescription>
        </Alert>
      ) : (
        <QueryState
          isLoading={companyQuery.isLoading}
          error={companyQuery.error}
          isEmpty={!companyQuery.data}
          empty="指定した企業のデータが見つかりません"
        >
          {companyQuery.data ? (
            <div className="space-y-6">
              <div className="text-sm leading-6">
                <p>
                  <span className="text-muted-foreground">企業名: </span>
                  {companyQuery.data.company_name}{' '}
                  <span className="font-mono text-muted-foreground">
                    ({companyQuery.data.edinet_code})
                  </span>
                </p>
                <p>
                  <span className="text-muted-foreground">業種: </span>
                  {companyQuery.data.industry ?? '(業種未取得)'}
                </p>
                <p>
                  <span className="text-muted-foreground">対象: </span>
                  {year} 年度 / {SCOPE_LABELS[scope]} ×{' '}
                  {WORKER_TYPE_LABELS[worker_type]}
                </p>
              </div>

              {!row ? (
                <Alert>
                  <AlertDescription>
                    選択した次元（{SCOPE_LABELS[scope]} ×{' '}
                    {WORKER_TYPE_LABELS[worker_type]}）に該当する行が {year}{' '}
                    年度にありません。次元を切り替えてください。
                  </AlertDescription>
                </Alert>
              ) : (
                <>
                  <section className="space-y-3">
                    <h2 className="text-lg font-semibold">財務指標</h2>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      {FINANCIAL_METRICS.map((def) => (
                        <KpiCard
                          key={def.key}
                          label={def.cardLabel}
                          value={def.format(row[def.key])}
                        />
                      ))}
                    </div>
                  </section>

                  <section className="space-y-3">
                    <h2 className="text-lg font-semibold">人的資本指標</h2>
                    <div className="grid gap-3 md:grid-cols-3">
                      {HC_METRICS.map((def) => (
                        <RatioBar
                          key={def.key}
                          label={def.cardLabel}
                          value={row[def.key]}
                        />
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      バーは 0% → 100% のパリティ目盛りです。提出会社/連結子会社・労働者区分で値が異なるため、上の次元セレクタで切り替えられます。
                    </p>
                  </section>

                  <section className="space-y-3">
                    <h2 className="text-lg font-semibold">従業員情報</h2>
                    <div className="grid gap-3 md:grid-cols-3">
                      {EMPLOYEE_METRICS.map((def) => (
                        <KpiCard
                          key={def.key}
                          label={def.cardLabel}
                          value={def.format(employeeRow?.[def.key])}
                        />
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      「従業員の状況」に記載される提出会社単体の値です。開示範囲・労働者区分セレクタの影響を受けません。
                    </p>
                  </section>
                </>
              )}

              <section className="space-y-3">
                <h2 className="text-lg font-semibold">年度推移 (全データ)</h2>
                <HistoryTable
                  rows={companyQuery.data.rows}
                  years={years}
                  scope={scope}
                  worker_type={worker_type}
                />
                <p className="text-xs text-muted-foreground">
                  財務・人的資本指標は選択中の開示範囲×労働者区分、従業員情報は提出会社単体の値です。
                </p>
              </section>
            </div>
          ) : null}
        </QueryState>
      )}
    </div>
  )
}

function KpiCard({
  label,
  value,
  loading,
}: {
  label: string
  value: string
  loading?: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tabular-nums">
          {loading ? '…' : value}
        </p>
      </CardContent>
    </Card>
  )
}

function HistoryTable({
  rows,
  years,
  scope,
  worker_type,
}: {
  rows: CompanyMetricRow[]
  years: number[]
  scope: Scope
  worker_type: CompanyMetricRow['worker_type']
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>指標</TableHead>
          {years.map((item) => (
            <TableHead key={item} className="text-right">
              {item}年度
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {COMPANY_METRICS.map((def) => (
          <TableRow key={def.key}>
            <TableCell className="font-medium">{def.historyLabel}</TableCell>
            {years.map((item) => {
              const source = pickRow(
                rows,
                item,
                def.employeeInfo ? DEFAULT_SCOPE : scope,
                def.employeeInfo ? DEFAULT_WORKER_TYPE : worker_type,
              )
              return (
                <TableCell key={item} className="text-right tabular-nums">
                  {def.format(source?.[def.key], { unit: false })}
                </TableCell>
              )
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
