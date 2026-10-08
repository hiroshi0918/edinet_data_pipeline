// 紙の地に、上のしおりと本文を載せる。トップだけは全幅で、ヘッダーを重ねる。
import { MotionConfig, motion } from 'motion/react'
import { Outlet, ScrollRestoration, useLocation } from 'react-router'

import { AppHeader } from '@/components/layout/app-header'
import { cn } from '@/lib/utils'

export function AppLayout() {
  const { pathname } = useLocation()
  const home = pathname === '/'

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-svh flex-col">
        <AppHeader overlay={home} />
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          className={cn('flex-1', !home && 'mx-auto w-full max-w-6xl px-4 pt-8 pb-24 sm:px-8')}
        >
          <Outlet />
        </motion.main>
        <footer className="border-t-2 border-dashed border-ink/20 px-4 py-6 text-center text-xs text-ink-soft">
          有価証券報告書（EDINET）の数字から作った図鑑です。
        </footer>
        <ScrollRestoration />
      </div>
    </MotionConfig>
  )
}
