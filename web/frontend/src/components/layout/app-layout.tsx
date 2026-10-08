// 抽斗の地に、左の背表紙と本文を載せる。
import type { CSSProperties } from 'react'
import { Outlet } from 'react-router'

import { AppSidebar } from '@/components/layout/app-sidebar'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'

const spineWidth = { '--sidebar-width': '13rem' } as CSSProperties

export function AppLayout() {
  return (
    <SidebarProvider style={spineWidth}>
      <AppSidebar />
      <SidebarInset className="bg-drawer">
        <header className="flex h-10 items-center px-3 md:px-4">
          <SidebarTrigger className="text-ink" />
        </header>
        <div className="flex-1 px-4 pb-12 md:px-8">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
