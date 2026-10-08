// Rails /api/v1 への GET。キーは snake_case のまま使う。
import type {
  ApiErrorBody,
  CompaniesResponse,
  CompanyDetail,
  IndustriesResponse,
  SheetResponse,
  StoryResponse,
  MetaResponse,
  RankingsResponse,
  Nikkei225Response,
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

export function fetchSheet(code: string) {
  return apiGet<SheetResponse>(`/companies/${encodeURIComponent(code)}/sheet`)
}

export function fetchStory(code: string) {
  return apiGet<StoryResponse>(`/companies/${encodeURIComponent(code)}/story`)
}

export function fetchIndustries() {
  return apiGet<IndustriesResponse>('/industries')
}

export function fetchNikkei225() {
  return apiGet<Nikkei225Response>('/nikkei225')
}

export function fetchRankings(industry?: string, axis?: string) {
  return apiGet<RankingsResponse>('/rankings', {
    industry: industry && industry !== 'all' ? industry : undefined,
    axis: axis && axis !== 'level' ? axis : undefined,
  })
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return '不明なエラーが発生しました'
}
