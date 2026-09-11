/**
 * P2 桌面环境类型桥：window.electronAPI（desktop 通过 preload 暴露；浏览器环境为 undefined）
 */
declare global {
  interface Window {
    electronAPI?: {
      account: {
        login: (username: string, password: string) => Promise<unknown>
        me: () => Promise<unknown>
        logout: () => Promise<boolean>
      }
    }
  }
}

export {}
