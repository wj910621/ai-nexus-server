import { Menu, MenuItemConstructorOptions, app, shell, BrowserWindow } from 'electron'
import { APP_NAME } from './constants'

/**
 * Build the application menu template.
 * Pure function: takes injectable callbacks for testability.
 */
export function buildMenuTemplate(callbacks: {
  onNewWindow?: () => void
  onReload?: () => void
  onToggleDevTools?: () => void
  onAbout?: () => void
  onSettings?: () => void
} = {}): MenuItemConstructorOptions[] {
  const isMac = process.platform === 'darwin'

  const template: MenuItemConstructorOptions[] = [
    // App menu (macOS only)
    ...(isMac ? [{
      label: APP_NAME,
      submenu: [
        { role: 'about', label: `关于 ${APP_NAME}` },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide', label: '隐藏' },
        { role: 'hideOthers', label: '隐藏其他' },
        { role: 'unhide', label: '显示全部' },
        { type: 'separator' },
        { role: 'quit', label: `退出 ${APP_NAME}` },
      ] as MenuItemConstructorOptions[],
    }] : []),

    // File menu
    {
      label: '文件',
      submenu: [
        {
          label: '新建项目',
          accelerator: 'CmdOrCtrl+N',
          click: () => callbacks.onNewWindow?.(),
        },
        { type: 'separator' },
        {
          label: '设置',
          accelerator: 'CmdOrCtrl+,',
          click: () => callbacks.onSettings?.(),
        },
        ...(isMac ? [] : [{ type: 'separator' as const }, { role: 'quit' as const, label: '退出' }]),
      ],
    },

    // Edit menu
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' },
      ],
    },

    // View menu
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '重新加载' },
        { role: 'forceReload', label: '强制重新加载' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '重置缩放' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' },
      ],
    },

    // Window menu
    {
      label: '窗口',
      submenu: [
        { role: 'minimize', label: '最小化' },
        { role: 'zoom', label: '缩放' },
        { type: 'separator' },
        { role: 'front', label: '前置全部窗口' },
      ],
    },

    // Help menu
    {
      label: '帮助',
      submenu: [
        {
          label: '关于',
          click: () => callbacks.onAbout?.(),
        },
        {
          label: '官方文档',
          click: () => shell.openExternal('https://github.com/comicstudio-ai/docs'),
        },
        {
          label: '问题反馈',
          click: () => shell.openExternal('https://github.com/comicstudio-ai/issues'),
        },
        { type: 'separator' },
        {
          label: '检查更新',
          click: () => callbacks.onAbout?.(),
        },
      ],
    },
  ]

  return template
}

/**
 * Apply the application menu to the given window (or globally on macOS).
 */
export function setupMenu(callbacks: Parameters<typeof buildMenuTemplate>[0] = {}): void {
  const template = buildMenuTemplate(callbacks)
  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}
