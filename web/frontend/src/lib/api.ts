// Rails /api/v1 への GET。キーは snake_case のまま使う。
import type {
  ApiErrorBody,
  CompaniesResponse,
  CompanyDetail,
  HcDistributionResponse,
  HcMetric,
  HcRankingResponse,
  MetaResponse,
  RankingHcMetric,
  SizeAxis,
  SizeRankingResponse,
  SpotlightResponse,
  SpotlightScope,
  WorkerType,
} from '@/lib/types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type QueryParams = Record<string, string | number | undefined | null>

export async function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  const search = new URLSearchParams()
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value == null || value === '') continue
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  const url = `/api/v1${path}${qs ? `?${qs}` : ''}`
  const response = await fetch(url)
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as ApiErrorBody
      if (body.error) message = body.error
    } catch {
      // 契約どおり JSON でない場合はステータスだけ出す
    }
    throw new ApiError(message, response.status)
  }
  return (await response.json()) as T
}

export function fetchMeta() {
  return apiGet<MetaResponse>('/meta')
}

export function fetchCompanies(q?: string, limit?: number) {
  return apiGet<CompaniesResponse>('/companies', { q, limit })
}

export function fetchCompany(code: string) {
  return apiGet<CompanyDetail>(`/companies/${encodeURIComponent(code)}`)
}

export function fetchSpotlight(
  code: string,
  params: {
    year?: number
    scope?: SpotlightScope
    worker_type?: WorkerType
  },
) {
  return apiGet<SpotlightResponse>(
    `/companies/${encodeURIComponent(code)}/spotlight`,
    params,
  )
}

export function fetchHcDistribution(params: {
  year: number
  scope: string
  worker_type: string
  metric: HcMetric
}) {
  return apiGet<HcDistributionResponse>('/industries/hc_distribution', params)
}

export function fetchHcRanking(params: {
  year: number
  scope: string
  worker_type: string
  metric: RankingHcMetric
}) {
  return apiGet<HcRankingResponse>('/rankings/human_capital', params)
}

export function fetchSizeRanking(params: {
  year: number
  scope: string
  worker_type: string
  axis: SizeAxis
}) {
  return apiGet<SizeRankingResponse>('/rankings/size', params)
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return '不明なエラーが発生しました'
}
