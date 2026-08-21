import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import { resolve } from 'path'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/main/index.ts'),
        },
      },
    },
    resolve: {
      alias: {
        '@main': resolve(__dirname, 'src/main'),
        '@shared': resolve(__dirname, 'src/shared'),
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/preload/index.ts'),
        },
      },
    },
    resolve: {
      alias: {
        '@main': resolve(__dirname, 'src/main'),
        '@preload': resolve(__dirname, 'src/preload'),
        '@shared': resolve(__dirname, 'src/shared'),
      },
    },
  },
  renderer: {
    root: '../frontend',
    css: {
      postcss: resolve(__dirname, '../frontend'),
    },
    build: {
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        input: {
          index: resolve(__dirname, '../frontend/index.html'),
        },
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
      outDir: resolve(__dirname, 'out/renderer'),
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, '../frontend/src'),
      },
    },
  },
})
