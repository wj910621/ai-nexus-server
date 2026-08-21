/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_BASE_URL: string
  readonly VITE_BASE_PATH?: string
  readonly VITE_ROUTER_BASE?: string
  readonly VITE_JARVIS_BILLING_PORTAL_URL: string
  readonly VITE_COMMERCIAL_OPERATIONS_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
