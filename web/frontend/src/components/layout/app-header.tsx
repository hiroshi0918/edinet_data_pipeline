// カーボンの主ナビと、その下の淡い帯。現在地の文字だけ琥珀。
import { Link, useLocation } from 'react-router'

import { EggFigure } from '@/components/egg-figure'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/', label: 'さがす', match: (path: string) => path === '/' || path.startsWith('/companies') },
  { to: '/compare', label: 'くらべる', match: (path: string) => path.startsWith('/compare') },
  { to: '/rankings', label: 'ランキング', match: (path: string) => path.startsWith('/rankings') },
  { to: '/nikkei225', label: '日経225', match: (path: string) => path.startsWith('/nikkei225') },
]

export function AppHeader() {
  const { pathname } = useLocation()
  return (
    <header className="sticky top-0 z-40 w-full">
      <div className="carbon-slab">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-3 sm:gap-4 sm:px-8">
          <Link
            to="/"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-surface px-2.5"
            aria-label="会社図鑑 トップ"
          >
            <EggFigure className="h-6 w-auto" />
            <span className="hidden text-sm font-black tracking-wide text-brand min-[420px]:inline">会社図鑑</span>
          </Link>
          <nav aria-label="ページ" className="min-w-0 flex-1 overflow-x-auto">
            <ul className="flex w-max items-center gap-1 sm:gap-3">
              {TABS.map((tab) => {
                const active = tab.match(pathname)
                return (
                  <li key={tab.to}>
                    <Link
                      to={tab.to}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'inline-flex h-11 items-center px-2 text-[13px] font-bold tracking-wide whitespace-nowrap sm:px-3',
                        active ? 'text-amber' : 'text-nav-gold hover:text-surface',
                      )}
                    >
                      {tab.label}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
        </div>
      </div>
      <div className="border-b border-chrome bg-canvas-soft">
        <p className="mx-auto flex h-8 max-w-6xl items-center px-3 text-[11px] font-bold tracking-wide text-ink sm:px-8">
          有価証券報告書（EDINET）の数字から作った図鑑
        </p>
      </div>
    </header>
  )
}
