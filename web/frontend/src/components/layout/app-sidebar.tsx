// 5 画面のナビ。スポットライトは選択中の企業コードをパスに載せる。
import {
  Building2Icon,
  FactoryIcon,
  LayoutDashboardIcon,
  ScaleIcon,
  ScanSearchIcon,
  TrophyIcon,
} from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'

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

const NAV = [
  { id: 'companies', label: '企業を調べる', icon: Building2Icon },
  { id: 'industry', label: '業種で比べる', icon: FactoryIcon },
  { id: 'hc-ranking', label: '人的資本トップ/ボトム', icon: TrophyIcon },
  { id: 'size-hc', label: '規模×人的資本', icon: ScaleIcon },
  { id: 'spotlight', label: 'スポットライト', icon: ScanSearchIcon },
] as const

export function AppSidebar() {
  const location = useLocation()
  const { code } = useParams()
  const search = location.search

  function hrefFor(id: (typeof NAV)[number]['id']) {
    if (id === 'companies') return { pathname: '/companies', search }
    if (id === 'industry') return { pathname: '/industry', search }
    if (id === 'hc-ranking') return { pathname: '/hc-ranking', search }
    if (id === 'size-hc') return { pathname: '/size-hc', search }
    if (code) return { pathname: `/companies/${code}/spotlight`, search }
    return { pathname: '/companies', search }
  }

  function isActive(id: (typeof NAV)[number]['id']) {
    const path = location.pathname
    if (id === 'spotlight') return path.includes('/spotlight')
    if (id === 'companies') {
      return path.startsWith('/companies') && !path.includes('/spotlight')
    }
    return path === `/${id}` || path.startsWith(`/${id}/`)
  }

  return (
    <Sidebar>
      <SidebarHeader className="px-4 py-4">
        <div className="flex items-center gap-2 text-sidebar-foreground">
          <LayoutDashboardIcon className="size-5" />
          <div className="leading-tight">
            <div className="text-sm font-semibold">EDINET</div>
            <div className="text-xs text-sidebar-foreground/70">人的資本ダッシュボード</div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>分析</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton asChild isActive={isActive(item.id)}>
                    <Link to={hrefFor(item.id)}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
