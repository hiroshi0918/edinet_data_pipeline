// ペリウィンクルの地に、カーボンのナビと本文を載せる。
import { MotionConfig, motion } from 'motion/react'
import { Outlet, ScrollRestoration, useLocation } from 'react-router'

import { AppHeader } from '@/components/layout/app-header'

export function AppLayout() {
  const { pathname } = useLocation()

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-svh flex-col">
        <AppHeader />
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-16 sm:px-8"
        >
          <Outlet />
        </motion.main>
        <footer className="carbon-slab px-4 py-5 text-center text-[11px] leading-5">
          有価証券報告書（EDINET）の数字から作った図鑑です。
        </footer>
        <ScrollRestoration />
      </div>
    </MotionConfig>
  )
}
