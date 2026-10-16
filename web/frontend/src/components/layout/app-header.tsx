// 黒い主ナビ。現在地だけ白、それ以外は薄い白。
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
    <header className="sticky top-0 z-40 w-full bg-black text-white">
      <div className="mx-auto flex h-12 max-w-[1280px] items-center gap-4 px-4 sm:gap-8 sm:px-12">
        <Link to="/" className="inline-flex h-11 shrink-0 items-center gap-2" aria-label="会社図鑑 トップ">
          <EggFigure className="h-7 w-auto" />
          <span className="text-sm font-medium tracking-wide">会社図鑑</span>
        </Link>
        <nav aria-label="ページ" className="min-w-0 flex-1 overflow-x-auto">
          <ul className="flex w-max items-center gap-1 sm:gap-2">
            {TABS.map((tab) => {
              const active = tab.match(pathname)
              return (
                <li key={tab.to}>
                  <Link
                    to={tab.to}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'inline-flex h-12 items-center px-3 text-sm font-medium tracking-wide whitespace-nowrap',
                      active ? 'text-white' : 'text-white/70 hover:text-white',
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
    </header>
  )
}
