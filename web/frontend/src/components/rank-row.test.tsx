import { render, screen } from '@testing-library/react'

import { ScoreNote } from '@/components/rank-row'

test('総合点は同じ業種との比べだと書く', () => {
  render(<ScoreNote />)
  expect(screen.getByText('同じ業種の会社と比べた総合点（100点満点）')).toBeInTheDocument()
})

test('軸の名前を点の説明に入れる', () => {
  render(<ScoreNote axis="sales" axisLabel="売上高" />)
  expect(screen.getByText('同じ業種の会社と比べた売上高の点（100点満点）')).toBeInTheDocument()
})

test('人の開示は同業との比べではなく、3指標の揃い具合だと書く', () => {
  render(<ScoreNote axis="disclosure" axisLabel="人の開示" />)
  expect(screen.getByText('人の3指標が揃っているほど高い点（100点満点）')).toBeInTheDocument()
})
