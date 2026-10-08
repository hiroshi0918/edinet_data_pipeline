// API_CONTRACT.md と対応するレスポンス型。変換せず snake_case。
export type Scope = 'reporting_company' | 'consolidated_subsidiary'
export type SpotlightScope = Scope | 'auto'
export type WorkerType = 'all' | 'regular' | 'non_regular'
export type HcMetric =
  | 'female_manager_ratio'
  | 'male_childcare_leave_ratio'
  | 'gender_wage_gap'
export type RankingHcMetric = 'female_manager_ratio' | 'gender_wage_gap'
export type SizeAxis = 'sales' | 'operating_profit' | 'employee_count'

export type MetaResponse = {
  company_count: number
  year_count: number
  total_records: number
  latest_submission: string | null
  fiscal_years: number[]
  default_year: number
}

export type CompanySummary = {
  edinet_code: string
  company_name: string
  industry: string | null
}

export type CompaniesResponse = {
  companies: CompanySummary[]
}

export type CompanyMetricRow = {
  fiscal_year: number
  scope: Scope
  worker_type: WorkerType
  doc_id: string | null
  submitted_date: string | null
  sales: number | null
  operating_profit: number | null
  net_profit: number | null
  employee_count: number | null
  female_manager_ratio: number | null
  male_childcare_leave_ratio: number | null
  gender_wage_gap: number | null
  average_annual_salary: number | null
  average_years_of_service: number | null
  average_age: number | null
}

export type CompanyDetail = {
  edinet_code: string
  company_name: string
  industry: string | null
  rows: CompanyMetricRow[]
}

export type SpotlightPeer = {
  edinet_code: string
  company_name: string
  industry: string | null
  employee_count: number | null
  sales: number | null
  operating_profit: number | null
  net_profit: number | null
  female_manager_ratio: number | null
  male_childcare_leave_ratio: number | null
  gender_wage_gap: number | null
}

export type SpotlightTarget = {
  sales: number | null
  operating_profit: number | null
  employee_count: number | null
  female_manager_ratio: number | null
  male_childcare_leave_ratio: number | null
  gender_wage_gap: number | null
}

export type IndustryRankMetricKey = 'sales' | 'operating_profit' | 'female_manager_ratio'

export type IndustryRankMetric = {
  key: IndustryRankMetricKey
  rank: number | null
  among: number
}

export type IndustryRank = {
  industry: string | null
  industry_total: number
  metrics: IndustryRankMetric[]
}

export type BenchmarkSet = {
  current: number | null
  industry_p75: number | null
  size_peer_p75: number | null
  ideal_cluster_avg: number | null
  industry_top10_avg: number | null
}

export type SpotlightResponse = {
  edinet_code: string
  company_name: string
  industry: string | null
  fiscal_year: number
  scope: Scope
  scope_auto: boolean
  worker_type: WorkerType
  target: SpotlightTarget
  industry_rank: IndustryRank
  industry_peers: SpotlightPeer[]
  size_peers: SpotlightPeer[]
  ideal_cluster: SpotlightPeer[]
  benchmarks: {
    female_manager_ratio: BenchmarkSet
    male_childcare_leave_ratio: BenchmarkSet
    gender_wage_gap: BenchmarkSet
  }
}

export type HcDistributionRow = {
  industry: string
  edinet_code: string
  company_name: string
  value: number
}

export type HcDistributionResponse = {
  metric: HcMetric
  rows: HcDistributionRow[]
}

export type RankingRow = {
  rank: number
  edinet_code: string
  company_name: string
  industry: string | null
  value: number
}

export type HcRankingResponse = {
  metric: RankingHcMetric
  top: RankingRow[]
  bottom: RankingRow[]
}

export type SizeRankingRow = RankingRow & {
  female_manager_ratio: number | null
  gender_wage_gap: number | null
}

export type SizeRankingResponse = {
  axis: SizeAxis
  top: SizeRankingRow[]
  bottom: SizeRankingRow[]
}

export type ApiErrorBody = {
  error: string
}
