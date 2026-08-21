import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    base: env.VITE_BASE_PATH || '/',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      // Workflow, Markdown, and React cores are isolated as stable cacheable
      // chunks. Ant Design remains route-split so users do not download every
      // component on first paint.
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            if (id.includes('reactflow')) return 'workflow-vendor'
            if (id.includes('react-markdown') || id.includes('remark-') || id.includes('micromark')) {
              return 'markdown-vendor'
            }
            if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('react-router')) {
              return 'react-vendor'
            }
            return undefined
          },
        },
      },
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://localhost:8000',
          ws: true,
        },
      },
    },
  }
})
