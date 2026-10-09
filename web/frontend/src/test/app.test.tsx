// 会社図鑑のルート。API は fixtures でモックする。
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'

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
  vi.unstubAllEnvs()
})

test('/ は表紙で、検索と業種の目次を出す', async () => {
  renderAt('/')
  expect(screen.getByRole('heading', { level: 1, name: '会社図鑑' })).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: '企業を検索・選択' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '業種の目次' })).toBeInTheDocument()

  const tile = screen.getByRole('link', { name: '輸送用機器の会社を見る' })
  expect(tile).toHaveAttribute('href', `/rankings?industry=${encodeURIComponent('輸送用機器')}`)
  expect(tile).toHaveTextContent('No.017')
  await waitFor(() => expect(tile).toHaveTextContent('12社'))
  expect(screen.getByRole('link', { name: 'サービス業の会社を見る' })).toHaveTextContent('1,234社')
})

test('検索候補の左は業種キャラではなく企業ロゴ', async () => {
  vi.stubEnv('VITE_LOGO_DEV_PUBLISHABLE_KEY', 'pk_test')
  const user = userEvent.setup()
  renderAt('/')
  await user.click(screen.getByRole('combobox', { name: '企業を検索・選択' }))
  expect(await screen.findByText('株式会社セプテーニ・ホールディングス')).toBeInTheDocument()
  const list = document.querySelector('[data-slot="command-list"]')
  const logo = list?.querySelector('img')
  expect(logo).toHaveAttribute('src', expect.stringContaining('img.logo.dev/ticker/4293.T'))
  expect(list?.querySelector('img[src*="/characters/"]')).toBeNull()
  expect(screen.getByRole('link', { name: 'ロゴ: logo.dev' })).toBeInTheDocument()
})

test('目次の業種を押すと、その業種のランキングが開く', async () => {
  const user = userEvent.setup()
  const { router } = renderAt('/')
  await user.click(screen.getByRole('link', { name: '輸送用機器の会社を見る' }))
  await waitFor(() => expect(router.state.location.pathname).toBe('/rankings'))
  expect(router.state.location.search).toBe(`?industry=${encodeURIComponent('輸送用機器')}`)
  expect(await screen.findByRole('heading', { name: '輸送用機器' })).toBeInTheDocument()
  const links = await screen.findAllByRole('link', { name: /会社$/ })
  expect(links.map((link) => link.textContent)).toEqual(['高い会社', '売上の会社'])
})

test('/companies と未知のパスは表紙へ戻る', async () => {
  const { router } = renderAt('/companies')
  await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  expect(screen.getByRole('heading', { level: 1, name: '会社図鑑' })).toBeInTheDocument()
})

test('/companies/:code はシートの点を出す', async () => {
  const { container } = renderAt('/companies/E05206')
  expect(
    await screen.findByRole('heading', { name: '株式会社セプテーニ・ホールディングス' }),
  ).toBeInTheDocument()
  expect(screen.getByText('86')).toBeInTheDocument()
  expect(screen.getByText('傘・おや')).toBeInTheDocument()
  expect(container.querySelectorAll('.collect-rule')).toHaveLength(7)
  expect(screen.getByRole('button', { name: /^規模/ })).toHaveTextContent('80')
  expect(screen.queryByText('売上高')).not.toBeInTheDocument()
  expect(screen.queryByText('開示')).not.toBeInTheDocument()
  expect(screen.queryByText('人の開示')).not.toBeInTheDocument()
})

test('カードを開くと有報の実数が出る', async () => {
  const user = userEvent.setup()
  renderAt('/companies/E05206')
  const sales = await screen.findByRole('button', { name: /^規模/ })
  await user.click(sales)
  expect(await screen.findByText('売上高')).toBeInTheDocument()
  expect(screen.getByText('176.3 億円')).toBeInTheDocument()
  expect(screen.queryByText('有報の値')).not.toBeInTheDocument()
  expect(screen.queryByText('比べた会社 40社')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /^人(?!数)/ }))
  expect(screen.getByText('人的資本')).toBeInTheDocument()
  expect(screen.getByText('女性管理職比率')).toBeInTheDocument()
  expect(screen.getByText('12.3%')).toBeInTheDocument()
  expect(screen.getByText('36.4 歳')).toBeInTheDocument()
  expect(screen.queryByText('176.3 億円')).not.toBeInTheDocument()
  expect(screen.queryByText('売上高')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /^期待/ }))
  expect(screen.getByText('株価売上高倍率')).toBeInTheDocument()
  expect(screen.getByText('1.5倍')).toBeInTheDocument()
  expect(screen.getByText('実績PER 12.5倍')).toBeInTheDocument()
  expect(screen.getByText('決算月の終値')).toBeInTheDocument()
})

test('/compare は2社のPLを同じ目盛りで重ね、最新の値を右にそろえる', async () => {
  renderAt('/compare?a=E05206&b=E10001')
  expect(screen.getByRole('heading', { name: '2社をくらべる' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: '売上高' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '営業利益' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '営業利益率' })).toBeInTheDocument()
  expect(screen.getByText('1,200.0 億円')).toBeInTheDocument()
  expect(screen.getByText('500.0 億円')).toBeInTheDocument()
  expect(screen.getByText('7.5%')).toBeInTheDocument()
  expect(screen.getAllByText('2026年度').length).toBeGreaterThan(0)
  expect(screen.getAllByRole('img', { name: /億円/ })).toHaveLength(2)
})

test('/compare は1社しか無いと、2社えらぶよう促す', () => {
  renderAt('/compare?a=E05206')
  expect(screen.getByText('くらべる会社を2社えらんでください。')).toBeInTheDocument()
})

test('シートから比較へ、その会社を1社目にして入れる', async () => {
  renderAt('/companies/E05206')
  const link = await screen.findByRole('link', { name: 'ほかの会社とくらべる' })
  expect(link).toHaveAttribute('href', '/compare?a=E05206')
})

function routePaths(routes: RouteObject[]): string[] {
  return routes.flatMap((route) => [
    route.path ?? '',
    ...(route.children ? routePaths(route.children) : []),
  ])
}

test('外した分析画面はルートに無い', () => {
  const paths = routePaths(routeObjects)
  expect(paths).toEqual([
    '/',
    '',
    'companies',
    'companies/:code',
    'companies/:code/story',
    'compare',
    'nikkei225',
    'rankings',
    '*',
  ])
})

test('ランキングは総合点から始まり、業種と軸で並びが変わる', async () => {
  const user = userEvent.setup()
  const { router } = renderAt('/rankings')
  expect(await screen.findByRole('heading', { name: 'ランキング' })).toBeInTheDocument()
  const overall = await screen.findAllByRole('link', { name: /会社$/ })
  expect(overall.map((link) => link.textContent)).toEqual([
    '高い会社',
    '売上の会社',
    '別業種の会社',
  ])
  expect(overall[0]).toHaveAttribute('href', '/companies/E10001')

  await user.selectOptions(screen.getByRole('combobox', { name: '軸' }), 'sales')
  await waitFor(() => {
    expect(screen.getAllByRole('link', { name: /会社$/ })[0]).toHaveTextContent('売上の会社')
  })

  await user.selectOptions(screen.getByRole('combobox', { name: '業種' }), '輸送用機器')
  await waitFor(() => {
    expect(screen.queryByRole('link', { name: '別業種の会社' })).not.toBeInTheDocument()
  })
  expect(router.state.location.search).toBe(`?axis=sales&industry=${encodeURIComponent('輸送用機器')}`)
  expect(screen.getByRole('link', { name: '日経225' })).toBeInTheDocument()
})

test('歩みのページにグラフと原文の抜粋が出る', async () => {
  renderAt('/companies/E05206/story')
  expect(
    await screen.findByRole('heading', { name: '株式会社セプテーニ・ホールディングスの歩み' }),
  ).toBeInTheDocument()
  expect(screen.getByText('売上高')).toBeInTheDocument()
  expect(screen.getByText('インターネット広告を行う。')).toBeInTheDocument()
  expect(screen.getByText('1990年に設立した。')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'シートに戻る' })).toHaveAttribute(
    'href',
    '/companies/E05206',
  )
})

test('日経225の一覧からシートへ進める', async () => {
  const user = userEvent.setup()
  renderAt('/nikkei225')
  expect(await screen.findByRole('heading', { name: '日経225' })).toBeInTheDocument()
  expect(await screen.findByRole('link', { name: /トヨタ自動車株式会社/ })).toHaveAttribute(
    'href',
    '/companies/E02144',
  )
  expect(screen.getByText('76')).toBeInTheDocument()
  expect(screen.getByText('図鑑に無い')).toBeInTheDocument()

  await user.selectOptions(screen.getByRole('combobox', { name: '日経の業種' }), '海運')
  expect(screen.queryByRole('link', { name: /トヨタ自動車株式会社/ })).not.toBeInTheDocument()
  expect(screen.getByText('（株）商船三井')).toBeInTheDocument()
})
