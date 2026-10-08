// 年度・開示範囲・労働者区分。変更は URL に書き戻す。
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useFilters } from '@/hooks/use-filters'
import { SCOPE_LABELS, SCOPES, WORKER_TYPE_LABELS, WORKER_TYPES } from '@/lib/constants'

type DimensionFiltersProps = {
  allowAutoScope?: boolean
}

export function DimensionFilters({ allowAutoScope = false }: DimensionFiltersProps) {
  const { year, scope, spotlightScope, worker_type, fiscal_years, metaQuery, setFilter } =
    useFilters()

  if (metaQuery.isLoading) {
    return <Skeleton className="h-10 w-full" />
  }

  const years = fiscal_years.length > 0 ? fiscal_years : year != null ? [year] : []
  const scopeValue = allowAutoScope ? spotlightScope : scope

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="space-y-1.5">
        <Label htmlFor="filter-year">年度</Label>
        <Select
          value={year != null ? String(year) : undefined}
          onValueChange={(value) => setFilter({ year: value })}
        >
          <SelectTrigger id="filter-year" aria-label="年度" className="w-full">
            <SelectValue placeholder="年度" />
          </SelectTrigger>
          <SelectContent>
            {years.map((item) => (
              <SelectItem key={item} value={String(item)}>
                {item}年度
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="filter-scope">開示範囲</Label>
        <Select
          value={scopeValue}
          onValueChange={(value) => setFilter({ scope: value })}
        >
          <SelectTrigger id="filter-scope" aria-label="開示範囲" className="w-full">
            <SelectValue placeholder="開示範囲" />
          </SelectTrigger>
          <SelectContent>
            {allowAutoScope ? <SelectItem value="auto">自動推定</SelectItem> : null}
            {SCOPES.map((item) => (
              <SelectItem key={item} value={item}>
                {SCOPE_LABELS[item]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="filter-worker-type">労働者区分</Label>
        <Select
          value={worker_type}
          onValueChange={(value) => setFilter({ worker_type: value })}
        >
          <SelectTrigger
            id="filter-worker-type"
            aria-label="労働者区分"
            className="w-full"
          >
            <SelectValue placeholder="労働者区分" />
          </SelectTrigger>
          <SelectContent>
            {WORKER_TYPES.map((item) => (
              <SelectItem key={item} value={item}>
                {WORKER_TYPE_LABELS[item]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
