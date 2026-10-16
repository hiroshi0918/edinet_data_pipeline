// logo.dev の CDN は、Community プランだと分あたりの上限がある。
// 一覧の全行を同じ瞬間に出すと 429 になる。画面に入った分は並行して取り、
// 429 のときだけ Retry-After のあいだ列を止める。

const MAX_ACTIVE = 8
const DEFAULT_RETRY_AFTER_MS = 8_000

type Waiter = {
  url: string
  signal: AbortSignal
  attempt: number
  resolve: (objectUrl: string) => void
  reject: (error: unknown) => void
}

let active = 0
let holdUntil = 0
let timer: number | null = null
let generation = 0
const waiters: Waiter[] = []
const running = new Set<Waiter>()

function abortError() {
  return new DOMException('The operation was aborted.', 'AbortError')
}

function failQueued(error: Error) {
  const pending = waiters.splice(0)
  for (const waiter of pending) waiter.reject(error)
}

function schedule() {
  if (timer != null || active >= MAX_ACTIVE || waiters.length === 0) return
  const delay = Math.max(0, holdUntil - Date.now())
  if (delay === 0) {
    pump()
    return
  }
  timer = window.setTimeout(() => {
    timer = null
    pump()
  }, delay)
}

function pump() {
  while (active < MAX_ACTIVE && waiters.length > 0) {
    const delay = Math.max(0, holdUntil - Date.now())
    if (delay > 0) {
      schedule()
      return
    }
    const waiter = waiters.shift()
    if (!waiter || waiter.signal.aborted) continue
    active += 1
    void run(waiter, generation)
  }
}

async function run(waiter: Waiter, gen: number) {
  running.add(waiter)
  try {
    const response = await fetch(waiter.url, { signal: waiter.signal, mode: 'cors' })
    if (gen !== generation || waiter.signal.aborted) return
    if (response.status === 429) {
      waiter.attempt += 1
      const retryAfter = Number(response.headers.get('Retry-After'))
      const pauseMs =
        Number.isFinite(retryAfter) && retryAfter > 0
          ? Math.min(retryAfter * 1000, 60_000)
          : DEFAULT_RETRY_AFTER_MS
      holdUntil = Math.max(holdUntil, Date.now() + pauseMs)
      if (waiter.attempt >= 2) {
        const error = new Error('429')
        waiter.reject(error)
        failQueued(error)
        return
      }
      waiters.unshift(waiter)
      return
    }
    if (!response.ok) {
      waiter.reject(new Error(String(response.status)))
      return
    }
    const blob = await response.blob()
    if (gen !== generation || waiter.signal.aborted) return
    waiter.resolve(URL.createObjectURL(blob))
  } catch (error) {
    if (gen !== generation) return
    waiter.reject(error)
  } finally {
    running.delete(waiter)
    if (gen === generation) {
      active -= 1
      schedule()
    }
  }
}

export function loadLogo(url: string, signal: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError())
      return
    }
    const waiter: Waiter = { url, signal, attempt: 0, resolve, reject }
    const onAbort = () => {
      const index = waiters.indexOf(waiter)
      if (index >= 0) waiters.splice(index, 1)
      reject(abortError())
    }
    signal.addEventListener('abort', onAbort, { once: true })
    waiters.push(waiter)
    schedule()
  })
}

export function resetLogoQueueForTests() {
  generation += 1
  if (timer != null) window.clearTimeout(timer)
  timer = null
  failQueued(new Error('reset'))
  for (const waiter of running) waiter.reject(new Error('reset'))
  running.clear()
  active = 0
  holdUntil = 0
}
