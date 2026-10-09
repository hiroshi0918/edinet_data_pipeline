import { expect, test } from 'vitest'

import { tiedRanks } from '@/lib/rank'

test('同点は同じ順位で、次はその人数ぶん飛ばす', () => {
  expect(tiedRanks([100, 100, 94, 94, 94, 80])).toEqual([1, 1, 3, 3, 3, 6])
})

test('点が無い行は同点扱いにしない', () => {
  expect(tiedRanks([90, null, null])).toEqual([1, 2, 3])
})
