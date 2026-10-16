import { loadLogo, resetLogoQueueForTests } from '@/lib/logo-queue'

const PNG = Uint8Array.from(
  atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=='),
  (char) => char.charCodeAt(0),
)

function ok() {
  return new Response(PNG, { status: 200, headers: { 'Content-Type': 'image/png' } })
}

afterEach(() => {
  resetLogoQueueForTests()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('画面に入ったロゴは待たずに並行して取りに行く', async () => {
  const pending: Array<(response: Response) => void> = []
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          pending.push(resolve)
        }),
    ),
  )

  const controllers = [0, 1, 2].map(() => new AbortController())
  const jobs = controllers.map((controller, index) =>
    loadLogo(`https://img.logo.dev/ticker/720${index}.T`, controller.signal),
  )

  await Promise.resolve()
  expect(fetch).toHaveBeenCalledTimes(3)

  pending.forEach((resolve) => resolve(ok()))
  const urls = await Promise.all(jobs)
  expect(urls.every((url) => url.startsWith('blob:'))).toBe(true)
})

test('429 のあとは Retry-After まで待って同じロゴを取り直す', async () => {
  vi.useFakeTimers()
  let calls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      calls += 1
      if (calls === 1) return new Response('later', { status: 429, headers: { 'Retry-After': '5' } })
      return ok()
    }),
  )

  const pending = loadLogo('https://img.logo.dev/ticker/7203.T?token=pk', new AbortController().signal)
  await vi.advanceTimersByTimeAsync(0)
  expect(calls).toBe(1)

  await vi.advanceTimersByTimeAsync(4999)
  expect(calls).toBe(1)

  await vi.advanceTimersByTimeAsync(1)
  await expect(pending).resolves.toMatch(/^blob:/)
  expect(calls).toBe(2)
})

test('429 で待っているあいだは次のロゴを送らない', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('later', { status: 429, headers: { 'Retry-After': '5' } })))

  const firstController = new AbortController()
  const first = loadLogo('https://img.logo.dev/ticker/7203.T', firstController.signal)
  const firstSettled = first.catch((error: unknown) => error)
  await vi.advanceTimersByTimeAsync(0)
  expect(fetch).toHaveBeenCalledTimes(1)

  const secondController = new AbortController()
  const second = loadLogo('https://img.logo.dev/ticker/7267.T', secondController.signal)
  const secondSettled = second.catch((error: unknown) => error)
  await Promise.resolve()
  expect(fetch).toHaveBeenCalledTimes(1)

  firstController.abort()
  secondController.abort()
  await firstSettled
  await secondSettled
})
