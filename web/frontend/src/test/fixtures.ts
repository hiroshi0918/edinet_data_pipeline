import type {
  CompaniesResponse,
  CompanyDetail,
  HcDistributionResponse,
  HcRankingResponse,
  MetaResponse,
  Nikkei225Response,
  SheetResponse,
  StoryResponse,
  SizeRankingResponse,
  SpotlightResponse,
} from '@/lib/types'

export const metaFixture: MetaResponse = {
  company_count: 1234,
  year_count: 4,
  total_records: 5000,
  latest_submission: '2025-06-27',
  fiscal_years: [2022, 2023, 2024],
  default_year: 2024,
}

export const companiesFixture: CompaniesResponse = {
  companies: [
    {
      edinet_code: 'E05206',
      company_name: '株式会社セプテーニ・ホールディングス',
      industry: 'サービス業',
    },
  ],
}

export const companyDetailFixture: CompanyDetail = {
  edinet_code: 'E05206',
  company_name: '株式会社セプテーニ・ホールディングス',
  industry: 'サービス業',
  rows: [
    {
      fiscal_year: 2024,
      scope: 'reporting_company',
      worker_type: 'all',
      doc_id: 'S100XXXX',
      submitted_date: '2025-06-27',
      sales: 17628035000,
      operating_profit: 1000000000,
      net_profit: 800000000,
      employee_count: 58,
      female_manager_ratio: 12.3,
      male_childcare_leave_ratio: 45.0,
      gender_wage_gap: 78.5,
      average_annual_salary: 6500000,
      average_years_of_service: 8.2,
      average_age: 36.4,
    },
  ],
}

export const sheetFixture: SheetResponse = {
  edinet_code: 'E05206',
  company_name: '株式会社セプテーニ・ホールディングス',
  industry: 'サービス業',
  securities_code: '4293',
  fiscal_year: 2024,
  level: 86,
  axes: [
    {
      key: 'sales',
      label: '売上高',
      nickname: '規模',
      score: 80,
      value: 17628035000,
      peer_count: 40,
    },
    {
      key: 'employee_count',
      label: '従業員数',
      nickname: '人数',
      score: 40,
      value: 58,
      peer_count: 40,
    },
    {
      key: 'operating_margin',
      label: '営業利益率',
      nickname: '稼ぐ力',
      score: 70,
      value: 0.0567,
      peer_count: 38,
    },
    {
      key: 'people',
      label: '人的資本',
      nickname: '人',
      score: 60,
      value: null,
      peer_count: null,
      average_age: 36.4,
      metrics: [
        { key: 'female_manager_ratio', value: 12.3, score: 40, peer_count: 30 },
        { key: 'male_childcare_leave_ratio', value: null, score: null, peer_count: 4 },
        { key: 'gender_wage_gap', value: 78.5, score: 80, peer_count: 28 },
      ],
      disclosure: {
        key: 'disclosure',
        label: '人の開示',
        nickname: '開示',
        score: 67,
        value: 2,
        peer_count: null,
        disclosed_count: 2,
        expected_count: 3,
      },
    },
    {
      key: 'average_annual_salary',
      label: '平均年間給与',
      nickname: '待遇',
      score: 55,
      value: 6500000,
      peer_count: 36,
    },
    {
      key: 'average_years_of_service',
      label: '平均勤続年数',
      nickname: '定着',
      score: 50,
      value: 8.2,
      peer_count: 36,
    },
    {
      key: 'expectation',
      label: '株価売上高倍率',
      nickname: '期待',
      score: 40,
      value: 1.5,
      peer_count: 20,
      per: 12.5,
      psr_basis: 'close',
    },
  ],
}

export const spotlightFixture: SpotlightResponse = {
  edinet_code: 'E05206',
  company_name: '株式会社セプテーニ・ホールディングス',
  industry: 'サービス業',
  fiscal_year: 2024,
  scope: 'reporting_company',
  scope_auto: false,
  worker_type: 'all',
  target: {
    sales: 17628035000,
    operating_profit: 1000000000,
    employee_count: 58,
    female_manager_ratio: 12.3,
    male_childcare_leave_ratio: 45.0,
    gender_wage_gap: 78.5,
  },
  industry_rank: {
    industry: 'サービス業',
    industry_total: 40,
    metrics: [
      { key: 'sales', rank: 5, among: 38 },
      { key: 'operating_profit', rank: 8, among: 40 },
      { key: 'female_manager_ratio', rank: 12, among: 30 },
    ],
  },
  industry_peers: [
    {
      edinet_code: 'E00001',
      company_name: 'Peer A',
      industry: 'サービス業',
      employee_count: 100,
      sales: 1,
      operating_profit: 1,
      net_profit: 1,
      female_manager_ratio: 20,
      male_childcare_leave_ratio: 50,
      gender_wage_gap: 80,
    },
  ],
  size_peers: [],
  ideal_cluster: [
    {
      edinet_code: 'E00002',
      company_name: 'Ideal Co',
      industry: '情報・通信業',
      employee_count: 200,
      sales: 1,
      operating_profit: 1,
      net_profit: 1,
      female_manager_ratio: 30,
      male_childcare_leave_ratio: 70,
      gender_wage_gap: 90,
    },
  ],
  benchmarks: {
    female_manager_ratio: {
      current: 12.3,
      industry_p75: 20,
      size_peer_p75: 18,
      ideal_cluster_avg: 25,
      industry_top10_avg: 30,
    },
    male_childcare_leave_ratio: {
      current: 45,
      industry_p75: 60,
      size_peer_p75: 55,
      ideal_cluster_avg: 70,
      industry_top10_avg: 80,
    },
    gender_wage_gap: {
      current: 78.5,
      industry_p75: 85,
      size_peer_p75: 82,
      ideal_cluster_avg: 90,
      industry_top10_avg: 95,
    },
  },
}

export const hcDistributionFixture: HcDistributionResponse = {
  metric: 'female_manager_ratio',
  rows: [
    {
      industry: '情報・通信業',
      edinet_code: 'E00001',
      company_name: 'A',
      value: 15.2,
    },
    {
      industry: '情報・通信業',
      edinet_code: 'E00002',
      company_name: 'B',
      value: 18.0,
    },
    {
      industry: '情報・通信業',
      edinet_code: 'E00003',
      company_name: 'C',
      value: 10.0,
    },
    {
      industry: '情報・通信業',
      edinet_code: 'E00004',
      company_name: 'D',
      value: 22.0,
    },
    {
      industry: '情報・通信業',
      edinet_code: 'E00005',
      company_name: 'E',
      value: 12.0,
    },
    {
      industry: 'サービス業',
      edinet_code: 'E00006',
      company_name: 'F',
      value: 8.0,
    },
    {
      industry: 'サービス業',
      edinet_code: 'E00007',
      company_name: 'G',
      value: 9.0,
    },
    {
      industry: 'サービス業',
      edinet_code: 'E00008',
      company_name: 'H',
      value: 11.0,
    },
    {
      industry: 'サービス業',
      edinet_code: 'E00009',
      company_name: 'I',
      value: 7.0,
    },
    {
      industry: 'サービス業',
      edinet_code: 'E00010',
      company_name: 'J',
      value: 13.0,
    },
  ],
}

export const hcRankingFixture: HcRankingResponse = {
  metric: 'female_manager_ratio',
  top: [
    {
      rank: 1,
      edinet_code: 'E00001',
      company_name: 'Top Co',
      industry: 'サービス業',
      value: 40,
    },
  ],
  bottom: [
    {
      rank: 1,
      edinet_code: 'E00002',
      company_name: 'Bottom Co',
      industry: '建設業',
      value: 2,
    },
  ],
}

export const sizeRankingFixture: SizeRankingResponse = {
  axis: 'sales',
  top: [
    {
      rank: 1,
      edinet_code: 'E00001',
      company_name: 'Big Co',
      industry: '情報・通信業',
      value: 1e12,
      female_manager_ratio: 12,
      gender_wage_gap: 70,
    },
  ],
  bottom: [
    {
      rank: 1,
      edinet_code: 'E00002',
      company_name: 'Small Co',
      industry: 'サービス業',
      value: 2e8,
      female_manager_ratio: 20,
      gender_wage_gap: 80,
    },
  ],
}

export const storyFixture: StoryResponse = {
  edinet_code: 'E05206',
  company_name: '株式会社セプテーニ・ホールディングス',
  industry: 'サービス業',
  fiscal_year: 2026,
  series: [
    { fiscal_year: 2017, sales: null, operating_profit: null, employee_count: null },
    { fiscal_year: 2025, sales: 100000000000, operating_profit: 8000000000, employee_count: 1500 },
    { fiscal_year: 2026, sales: 120000000000, operating_profit: 9000000000, employee_count: 1600 },
  ],
  narrative: {
    business: { text: 'インターネット広告を行う。', source: '当社はインターネット広告を行う。' },
    history: [{ label: '1990年', text: '1990年に設立した。', source: '1990年に設立した。' }],
    rewritten: false,
  },
}

export const nikkei225Fixture: Nikkei225Response = {
  as_of: '2026-10-08',
  source_note: 'テスト用の構成銘柄',
  companies: [
    {
      securities_code: '7203',
      short_name: 'トヨタ',
      listed_name: 'トヨタ自動車（株）',
      nikkei_sector: '自動車',
      edinet_code: 'E02144',
      company_name: 'トヨタ自動車株式会社',
      industry: '輸送用機器',
      fiscal_year: 2026,
      level: 76,
      has_sheet: true,
    },
    {
      securities_code: '9104',
      short_name: '商船三井',
      listed_name: '（株）商船三井',
      nikkei_sector: '海運',
      edinet_code: null,
      company_name: '（株）商船三井',
      industry: null,
      fiscal_year: null,
      level: null,
      has_sheet: false,
    },
  ],
}

export function rankingsFixture(axis = 'level', industry: string | null = null) {
  const companies = [
    {
      edinet_code: 'E10001',
      company_name: '高い会社',
      industry: '輸送用機器',
      fiscal_year: 2026,
      level: 90,
      score: axis === 'sales' ? 40 : 90,
    },
    {
      edinet_code: 'E10002',
      company_name: '売上の会社',
      industry: '輸送用機器',
      fiscal_year: 2026,
      level: 70,
      score: axis === 'sales' ? 100 : 70,
    },
    {
      edinet_code: 'E10003',
      company_name: '別業種の会社',
      industry: '水産・農林業',
      fiscal_year: 2026,
      level: 50,
      score: 50,
    },
  ]
  const visible = industry ? companies.filter((company) => company.industry === industry) : companies
  const sorted = [...visible].sort((left, right) => (right.score ?? -1) - (left.score ?? -1))
  return {
    axis,
    industry,
    industries: ['水産・農林業', '輸送用機器'],
    axes: [
      { key: 'level', label: '総合' },
      { key: 'sales', label: '売上高' },
    ],
    companies: sorted,
  }
}

export function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function installApiMock() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/v1/meta')) return jsonResponse(metaFixture)
      if (url.includes('/api/v1/nikkei225')) return jsonResponse(nikkei225Fixture)
      if (
        url.includes('/api/v1/rankings') &&
        !url.includes('human_capital') &&
        !url.includes('/size')
      ) {
        const parsed = new URL(url, 'http://localhost')
        return jsonResponse(
          rankingsFixture(
            parsed.searchParams.get('axis') ?? 'level',
            parsed.searchParams.get('industry'),
          ),
        )
      }
      if (url.includes('/api/v1/companies/E05206/sheet')) {
        return jsonResponse(sheetFixture)
      }
      if (url.includes('/api/v1/companies/E05206/story')) {
        return jsonResponse(storyFixture)
      }
      if (url.includes('/api/v1/companies/E05206/spotlight')) {
        return jsonResponse(spotlightFixture)
      }
      if (url.includes('/api/v1/companies/E05206')) {
        return jsonResponse(companyDetailFixture)
      }
      if (url.includes('/api/v1/companies')) return jsonResponse(companiesFixture)
      if (url.includes('/api/v1/industries/hc_distribution')) {
        return jsonResponse(hcDistributionFixture)
      }
      if (url.includes('/api/v1/rankings/human_capital')) {
        return jsonResponse(hcRankingFixture)
      }
      if (url.includes('/api/v1/rankings/size')) {
        return jsonResponse(sizeRankingFixture)
      }
      return jsonResponse({ error: `unmocked ${url}` }, 404)
    }),
  )
}
