// 読込中 / エラー / 空 をページ共通で出す。読込中はたまごが揺れる。
import type { ReactNode } from 'react'

import { EggFigure } from '@/components/egg-figure'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { errorMessage } from '@/lib/api'

export function QueryState({
  isLoading,
  error,
  isEmpty,
  empty = '表示するデータがありません',
  children,
}: {
  isLoading: boolean
  error: unknown
  isEmpty?: boolean
  empty?: string
  children: ReactNode
}) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-3 py-16" data-testid="loading" role="status">
        <EggFigure className="egg-wobble h-20 w-auto" />
        <p className="text-sm font-bold text-ink">よみこみ中…</p>
      </div>
    )
  }
  if (error) {
    return (
      <Alert variant="destructive" className="max-w-xl">
        <AlertTitle className="font-medium">取得に失敗しました</AlertTitle>
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    )
  }
  if (isEmpty) {
    return (
      <div className="flex max-w-xl items-end gap-4">
        <EggFigure className="h-20 w-auto shrink-0" />
        <Alert className="bg-surface">
          <AlertTitle className="font-medium">データがありません</AlertTitle>
          <AlertDescription>{empty}</AlertDescription>
        </Alert>
      </div>
    )
  }
  return children
}
