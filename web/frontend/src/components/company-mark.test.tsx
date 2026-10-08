import { act, fireEvent, render, screen } from '@testing-library/react'

import { CompanyMark } from '@/components/company-mark'

beforeEach(() => {
  vi.stubEnv('VITE_LOGO_DEV_PUBLISHABLE_KEY', 'publishable-test')
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllEnvs()
})

function failLogo(name: string) {
  fireEvent.error(screen.getByRole('img', { name: `${name}のロゴ` }))
}

test('別の証券コードでは、失敗したロゴの試行を引き継がない', () => {
  const { rerender } = render(<CompanyMark name="透明株式会社" securitiesCode="1111" />)

  failLogo('透明株式会社')
  act(() => {
    vi.advanceTimersByTime(800)
  })
  failLogo('透明株式会社')

  expect(screen.queryByRole('img', { name: '透明株式会社のロゴ' })).not.toBeInTheDocument()
  expect(screen.getByText('透')).toBeInTheDocument()

  rerender(<CompanyMark name="本物株式会社" securitiesCode="7203" />)

  const next = screen.getByRole('img', { name: '本物株式会社のロゴ' })
  expect(next).toHaveAttribute('src', expect.stringContaining('/ticker/7203.T?'))
  expect(next.getAttribute('src')).not.toContain('retry=')
})

test('別の証券コードへ移ったあとに、前の再試行タイマーは発火しない', () => {
  const { rerender } = render(<CompanyMark name="透明株式会社" securitiesCode="1111" />)

  failLogo('透明株式会社')
  rerender(<CompanyMark name="本物株式会社" securitiesCode="7203" />)
  act(() => {
    vi.advanceTimersByTime(800)
  })

  const next = screen.getByRole('img', { name: '本物株式会社のロゴ' })
  expect(next.getAttribute('src')).not.toContain('retry=')
})
