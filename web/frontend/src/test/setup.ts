import '@testing-library/jest-dom/vitest'

Element.prototype.scrollIntoView = vi.fn()
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
HTMLElement.prototype.hasPointerCapture = vi.fn()
HTMLElement.prototype.setPointerCapture = vi.fn()
HTMLElement.prototype.releasePointerCapture = vi.fn()

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverMock)

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
})

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn(),
    purge: vi.fn(),
  },
}))
