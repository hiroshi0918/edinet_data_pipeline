import { render, screen } from '@testing-library/react'

import { CompanyMark } from '@/components/company-mark'
import { resetLogoQueueForTests } from '@/lib/logo-queue'

const PNG = Uint8Array.from(
  atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=='),
  (char) => char.charCodeAt(0),
)

beforeEach(() => {
  vi.stubEnv('VITE_LOGO_DEV_PUBLISHABLE_KEY', 'publishable-test')
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('1111')) return new Response('missing', { status: 404 })
      return new Response(PNG, { status: 200, headers: { 'Content-Type': 'image/png' } })
    }),
  )
})

afterEach(() => {
  resetLogoQueueForTests()
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

test('取れないロゴは頭文字に戻り、次の証券コードは最初から取り直す', async () => {
  const { rerender } = render(<CompanyMark name="透明株式会社" securitiesCode="1111" />)

  expect(await screen.findByText('透')).toBeInTheDocument()
  expect(screen.queryByRole('img', { name: '透明株式会社のロゴ' })).not.toBeInTheDocument()

  rerender(<CompanyMark name="本物株式会社" securitiesCode="7203" />)

  const next = await screen.findByRole('img', { name: '本物株式会社のロゴ' })
  expect(vi.mocked(fetch).mock.calls.map((call) => String(call[0]))).toEqual(
    expect.arrayContaining([expect.stringContaining('/ticker/7203.T?')]),
  )
  expect(next.getAttribute('src')).not.toContain('retry=')
})

test('別の証券コードへ移ると、前の取得結果は捨てる', async () => {
  let resolveFirst: ((response: Response) => void) | undefined
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('1111')) {
        return new Promise<Response>((resolve) => {
          resolveFirst = resolve
        })
      }
      return Promise.resolve(new Response(PNG, { status: 200, headers: { 'Content-Type': 'image/png' } }))
    }),
  )

  const { rerender } = render(<CompanyMark name="透明株式会社" securitiesCode="1111" />)
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled())

  rerender(<CompanyMark name="本物株式会社" securitiesCode="7203" />)
  expect(await screen.findByRole('img', { name: '本物株式会社のロゴ' })).toBeInTheDocument()

  resolveFirst?.(new Response(PNG, { status: 200, headers: { 'Content-Type': 'image/png' } }))
  await vi.waitFor(() => expect(screen.queryByRole('img', { name: '透明株式会社のロゴ' })).not.toBeInTheDocument())
})
