// 画面と URL の対応。フィルタは各ページが search params で持つ。
import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/components/layout/app-layout'
import { CompaniesPage } from '@/pages/companies-page'
import { HcRankingPage } from '@/pages/hc-ranking-page'
import { IndustryPage } from '@/pages/industry-page'
import { SizeHcPage } from '@/pages/size-hc-page'
import { SpotlightPage } from '@/pages/spotlight-page'

export const routeObjects: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/companies" replace /> },
      { path: 'companies', element: <CompaniesPage /> },
      { path: 'companies/:code', element: <CompaniesPage /> },
      { path: 'companies/:code/spotlight', element: <SpotlightPage /> },
      { path: 'industry', element: <IndustryPage /> },
      { path: 'hc-ranking', element: <HcRankingPage /> },
      { path: 'size-hc', element: <SizeHcPage /> },
    ],
  },
]
