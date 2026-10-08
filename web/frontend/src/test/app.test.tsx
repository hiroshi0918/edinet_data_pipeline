// ルート表とフィルタ → URL の往復。API は fixtures でモックする。
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { TooltipProvider } from '@/components/ui/tooltip'
import { routeObjects } from '@/routes'
import { installApiMock } from '@/test/fixtures'

function renderAt(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const router = createMemoryRouter(routeObjects, { initialEntries: [path] })
  const view = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  )
  return { ...view, router }
}

beforeEach(() => {
  installApiMock()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('/ は /companies にリダイレクトする', async () => {
  const { router } = renderAt('/')
  await waitFor(() => {
    expect(router.state.location.pathname).toBe('/companies')
  })
  expect(await screen.findByRole('heading', { name: '企業を調べる' })).toBeInTheDocument()
})

test('/companies/:code がマッチする', async () => {
  const { router } = renderAt('/companies/E05206')
  expect(router.state.matches.some((match) => match.pathname === '/companies/E05206')).toBe(
    true,
  )
  expect(await screen.findByRole('heading', { name: '企業を調べる' })).toBeInTheDocument()
  expect(await screen.findByText(/セプテーニ/)).toBeInTheDocument()
})

test('/companies/:code/spotlight がマッチする', async () => {
  const { router } = renderAt('/companies/E05206/spotlight')
  expect(
    router.state.matches.some((match) => match.pathname === '/companies/E05206/spotlight'),
  ).toBe(true)
  expect(
    await screen.findByRole('heading', { name: '企業スポットライト' }),
  ).toBeInTheDocument()
})

test('5 画面がルートに載っている', async () => {
  for (const [path, heading] of [
    ['/companies', '企業を調べる'],
    ['/industry', '業種で比べる'],
    ['/hc-ranking', '人的資本トップ/ボトム企業'],
    ['/size-hc', '規模×人的資本'],
    ['/companies/E05206/spotlight', '企業スポットライト'],
  ] as const) {
    const { unmount } = renderAt(path)
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
    unmount()
  }
})

test('フィルタ変更で search params が更新される', async () => {
  const user = userEvent.setup()
  const { router } = renderAt('/companies')
  const yearTrigger = await screen.findByRole('combobox', { name: '年度' })
  await user.click(yearTrigger)
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name: '2023年度' }))
  await waitFor(() => {
    expect(router.state.location.search).toContain('year=2023')
  })

  const scopeTrigger = screen.getByRole('combobox', { name: '開示範囲' })
  await user.click(scopeTrigger)
  const scopeList = await screen.findByRole('listbox')
  await user.click(within(scopeList).getByRole('option', { name: '連結子会社' }))
  await waitFor(() => {
    expect(router.state.location.search).toContain('scope=consolidated_subsidiary')
  })

  const workerTrigger = screen.getByRole('combobox', { name: '労働者区分' })
  await user.click(workerTrigger)
  const workerList = await screen.findByRole('listbox')
  await user.click(within(workerList).getByRole('option', { name: '正規雇用' }))
  await waitFor(() => {
    expect(router.state.location.search).toContain('worker_type=regular')
  })
})
