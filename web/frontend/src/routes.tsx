// 会社図鑑。表紙、選んだ会社のシートと歩み、ランキング、日経225。
import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/components/layout/app-layout'
import { CompaniesPage } from '@/pages/companies-page'
import { HomePage } from '@/pages/home-page'
import { Nikkei225Page } from '@/pages/nikkei225-page'
import { RankingsPage } from '@/pages/rankings-page'
import { StoryPage } from '@/pages/story-page'

export const routeObjects: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'companies', element: <Navigate to="/" replace /> },
      { path: 'companies/:code', element: <CompaniesPage /> },
      { path: 'companies/:code/story', element: <StoryPage /> },
      { path: 'nikkei225', element: <Nikkei225Page /> },
      { path: 'rankings', element: <RankingsPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]
