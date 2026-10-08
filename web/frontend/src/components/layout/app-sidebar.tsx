// 会社図鑑のナビ。入口は社名検索だけ。
import { BookOpenIcon, Building2Icon, ListIcon, TrophyIcon } from 'lucide-react'
import { Link, useLocation } from 'react-router'

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

export function AppSidebar() {
  const location = useLocation()
  const onCompanies =
    location.pathname.startsWith('/companies') && location.pathname !== '/nikkei225'
  const onNikkei = location.pathname.startsWith('/nikkei225')
  const onRankings = location.pathname.startsWith('/rankings')

  return (
    <Sidebar>
      <SidebarHeader className="px-4 py-4">
        <div className="flex items-center gap-2 text-sidebar-foreground">
          <BookOpenIcon className="size-5" />
          <div className="leading-tight">
            <div className="text-sm font-semibold">会社図鑑</div>
            <div className="text-xs text-sidebar-foreground/70">有報から読む</div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>開く</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={onCompanies}>
                  <Link to="/companies">
                    <Building2Icon />
                    <span>会社を開く</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={onRankings}>
                  <Link to="/rankings">
                    <TrophyIcon />
                    <span>ランキング</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={onNikkei}>
                  <Link to="/nikkei225">
                    <ListIcon />
                    <span>日経225</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
