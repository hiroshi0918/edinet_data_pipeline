// 冊子の背表紙。地の色のまま、社名の引き方だけを置く。
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
    location.pathname.startsWith('/companies') && !location.pathname.startsWith('/nikkei225')
  const onNikkei = location.pathname.startsWith('/nikkei225')
  const onRankings = location.pathname.startsWith('/rankings')

  return (
    <Sidebar>
      <SidebarHeader className="px-5 pt-6 pb-2">
        <p className="w-fit self-start font-display text-xl leading-none tracking-[0.28em] text-ink [writing-mode:vertical-rl]">
          会社図鑑
        </p>
        <p className="mt-3 font-mono text-[10px] tracking-[0.14em] text-pencil">有報から読む</p>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="font-mono text-[10px] tracking-[0.14em] text-pencil">
            開く
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={onCompanies}>
                  <Link to="/companies">会社を開く</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={onRankings}>
                  <Link to="/rankings">ランキング</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={onNikkei}>
                  <Link to="/nikkei225">日経225</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
