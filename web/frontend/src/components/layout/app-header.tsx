// ロゴと、しおり型のタブ。トップではヒーローに重ねて透明にする。
import { Link, useLocation } from 'react-router'

import { EggFigure } from '@/components/egg-figure'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/', label: 'さがす', match: (path: string) => path === '/' || path.startsWith('/companies') },
  { to: '/rankings', label: 'ランキング', match: (path: string) => path.startsWith('/rankings') },
  { to: '/nikkei225', label: '日経225', match: (path: string) => path.startsWith('/nikkei225') },
]

export function AppHeader({ overlay }: { overlay: boolean }) {
  const { pathname } = useLocation()
  return (
    <header
      className={cn(
        'z-40 w-full',
        overlay
          ? 'absolute inset-x-0 top-0'
          : 'sticky top-0 border-b-[length:var(--line)] border-ink bg-paper/90 backdrop-blur-sm',
      )}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-2 px-3 sm:gap-3 sm:px-8">
        <Link to="/" className="group flex items-center gap-1.5 rounded-full" aria-label="会社図鑑 トップ">
          <EggFigure className="h-8 w-auto transition-transform duration-300 ease-(--ease-pop) group-hover:-rotate-12" />
          <span className="text-base font-black whitespace-nowrap text-ink sm:text-xl sm:tracking-wide">会社図鑑</span>
        </Link>
        <nav aria-label="ページ">
          <ul className="flex items-center gap-0.5 sm:gap-2">
            {TABS.map((tab) => {
              const active = tab.match(pathname)
              return (
                <li key={tab.to}>
                  <Link
                    to={tab.to}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'inline-flex h-9 items-center rounded-full px-2.5 text-[13px] font-bold whitespace-nowrap text-ink transition-[background-color,transform] duration-150 sm:h-10 sm:px-4 sm:text-sm',
                      active
                        ? 'border-[length:var(--line)] border-ink bg-marker shadow-ink-sm'
                        : 'border-[length:var(--line)] border-transparent hover:-translate-y-0.5 hover:bg-paper-deep',
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
