import { render } from '@testing-library/react'

import { CollectRule } from '@/components/collect-rule'

test('採集尺は 0 から 100 まで目盛り、点があるときは針を出す', () => {
  const { container } = render(<CollectRule score={40} />)
  const ticks = [...container.querySelectorAll('.collect-rule-ticks span')].map((tick) => tick.textContent)
  expect(ticks).toEqual(['0', '25', '50', '75', '100'])
  expect(container.querySelector('.collect-rule-pin')).not.toBeNull()
})

test('点がない採集尺は針を出さない', () => {
  const { container } = render(<CollectRule score={null} />)
  expect(container.querySelector('.collect-rule-pin')).toBeNull()
})
