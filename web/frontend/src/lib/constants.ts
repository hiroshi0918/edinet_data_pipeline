// 画面表示用ラベルと既定の次元。API のキー名と揃える。
import type {
  HcMetric,
  RankingHcMetric,
  Scope,
  SizeAxis,
  WorkerType,
} from '@/lib/types'

export const DEFAULT_SCOPE: Scope = 'reporting_company'
export const DEFAULT_WORKER_TYPE: WorkerType = 'all'
export const DEFAULT_HC_METRIC: HcMetric = 'female_manager_ratio'
export const DEFAULT_RANKING_METRIC: RankingHcMetric = 'female_manager_ratio'
export const DEFAULT_SIZE_AXIS: SizeAxis = 'sales'

export const SCOPE_LABELS: Record<Scope, string> = {
  reporting_company: '提出会社',
  consolidated_subsidiary: '連結子会社',
}

export const WORKER_TYPE_LABELS: Record<WorkerType, string> = {
  all: '全労働者',
  regular: '正規雇用',
  non_regular: '非正規雇用',
}

export const SCOPES = Object.keys(SCOPE_LABELS) as Scope[]
export const WORKER_TYPES = Object.keys(WORKER_TYPE_LABELS) as WorkerType[]

export const FINANCIAL_METRIC_LABELS = {
  sales: '売上高',
  operating_profit: '営業利益',
  net_profit: '純利益',
  employee_count: '従業員数',
} as const

export const HC_METRIC_LABELS: Record<HcMetric, string> = {
  female_manager_ratio: '女性管理職比率',
  male_childcare_leave_ratio: '男性育休取得率',
  gender_wage_gap: '男女賃金格差',
}

export const EMPLOYEE_INFO_LABELS = {
  average_annual_salary: '平均年間給与',
  average_years_of_service: '平均勤続年数',
  average_age: '平均年齢',
} as const

export const RANKING_HC_METRICS: RankingHcMetric[] = [
  'female_manager_ratio',
  'gender_wage_gap',
]

export const SIZE_AXIS_METRICS: SizeAxis[] = [
  'sales',
  'operating_profit',
  'employee_count',
]

export const HC_METRICS: HcMetric[] = [
  'female_manager_ratio',
  'male_childcare_leave_ratio',
  'gender_wage_gap',
]

export const EMPLOYEE_INFO_KEYS = [
  'average_annual_salary',
  'average_years_of_service',
  'average_age',
] as const
