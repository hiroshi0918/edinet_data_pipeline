// 年度・scope・worker_type・指標を URL search params と同期する。
import { useQuery } from '@tanstack/react-query'
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

import { fetchMeta } from '@/lib/api'
import {
  DEFAULT_HC_METRIC,
  DEFAULT_RANKING_METRIC,
  DEFAULT_SCOPE,
  DEFAULT_SIZE_AXIS,
  DEFAULT_WORKER_TYPE,
  HC_METRICS,
  RANKING_HC_METRICS,
  SCOPES,
  SIZE_AXIS_METRICS,
  WORKER_TYPES,
} from '@/lib/constants'
import type { SpotlightScope } from '@/lib/types'

function isOneOf<T extends string>(value: string | null, allowed: T[]): T | null {
  if (value && (allowed as string[]).includes(value)) return value as T
  return null
}

export function useFilters() {
  const [searchParams, setSearchParams] = useSearchParams()
  const metaQuery = useQuery({
    queryKey: ['meta'],
    queryFn: fetchMeta,
  })

  const yearParam = searchParams.get('year')
  const parsedYear = yearParam ? Number(yearParam) : NaN
  const year = Number.isFinite(parsedYear)
    ? parsedYear
    : (metaQuery.data?.default_year ?? null)

  const scopeParam = searchParams.get('scope')
  // auto はスポットライト専用。他画面の scope は提出会社に落とす。
  const scope = isOneOf(scopeParam, SCOPES) ?? DEFAULT_SCOPE
  const spotlightScope: SpotlightScope = scopeParam === 'auto' ? 'auto' : scope
  const worker_type =
    isOneOf(searchParams.get('worker_type'), WORKER_TYPES) ?? DEFAULT_WORKER_TYPE
  const metric =
    isOneOf(searchParams.get('metric'), HC_METRICS) ?? DEFAULT_HC_METRIC
  const ranking_metric =
    isOneOf(searchParams.get('metric'), RANKING_HC_METRICS) ?? DEFAULT_RANKING_METRIC
  const axis = isOneOf(searchParams.get('axis'), SIZE_AXIS_METRICS) ?? DEFAULT_SIZE_AXIS

  const setFilter = useCallback(
    (patch: Record<string, string | null | undefined>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [key, value] of Object.entries(patch)) {
            if (value == null || value === '') next.delete(key)
            else next.set(key, value)
          }
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  return {
    year,
    scope,
    spotlightScope,
    worker_type,
    metric,
    ranking_metric,
    axis,
    fiscal_years: metaQuery.data?.fiscal_years ?? [],
    meta: metaQuery.data,
    metaQuery,
    searchParams,
    setFilter,
  }
}

export function useFilterSearch() {
  const [searchParams] = useSearchParams()
  return searchParams.toString()
}
