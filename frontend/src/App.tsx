import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppRoutes from '@/routes'
import { useThemeStore } from '@/stores/themeStore'
import '@/styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export default function App() {
  const themeMode = useThemeStore((s) => s.theme)
  const routerBase = import.meta.env.VITE_ROUTER_BASE || undefined

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: themeMode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#3B82F6',
          borderRadius: 6,
          fontFamily: "'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif",
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename={routerBase}>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  )
}
