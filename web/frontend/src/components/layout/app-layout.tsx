// 白地に、黒いナビと青いフッター。表紙だけ帯を画面幅いっぱいに出す。
import { MotionConfig, motion } from 'motion/react'
import { Outlet, ScrollRestoration, useLocation } from 'react-router'

import { AppHeader } from '@/components/layout/app-header'
import { cn } from '@/lib/utils'

export function AppLayout() {
  const { pathname } = useLocation()
  const home = pathname === '/'

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-svh flex-col bg-white">
        <AppHeader />
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="w-full flex-1"
        >
          {home ? (
            <Outlet />
          ) : (
            <div className={cn('mx-auto w-full max-w-[1280px] px-4 py-12 sm:px-12')}>
              <Outlet />
            </div>
          )}
        </motion.main>
        <footer className="bg-primary px-4 py-12 text-center text-sm leading-6 text-white sm:px-12">
          有価証券報告書（EDINET）の数字から作った図鑑です。
        </footer>
        <ScrollRestoration />
      </div>
    </MotionConfig>
  )
}
