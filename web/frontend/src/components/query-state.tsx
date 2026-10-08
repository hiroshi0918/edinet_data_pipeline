// 読込中 / エラー / 空 をページ共通で出す。
import type { ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
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
      <div className="space-y-3" data-testid="loading">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>取得に失敗しました</AlertTitle>
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    )
  }
  if (isEmpty) {
    return (
      <Alert>
        <AlertTitle>データがありません</AlertTitle>
        <AlertDescription>{empty}</AlertDescription>
      </Alert>
    )
  }
  return children
}
