// Brand identity for Y·NEX Studio
// Used by icon generator and UI theming
//
// ⚠️ 品牌收敛 B（代码/文案层）：此处 name 仅用于图标与 UI 主题资源生成；
//    安装包/可执行文件元数据由 electron-builder.yml 的 productName 决定，
//    为避免已发布客户端（appId com.comicstudio.ai）升级链断供，exe/productName
//    改名随正式 B 发布轮一并切换，本阶段保持 productName 不变。

export const BRAND = {
  // Primary brand colors (gradient-friendly)
  primary: '#3b82f6',     // blue-500
  secondary: '#8b5cf6',   // violet-500
  accent: '#ec4899',      // pink-500

  // Background colors (dark theme matching frontend)
  bgDark: '#1e1e2e',
  bgDarker: '#11111b',

  // Logo glyph (single character displayed in icon)
  glyph: 'Y',
  glyphColor: '#ffffff',

  // App name (used in some installer resources)
  name: 'Y·NEX Studio',
  nameShort: 'Y·NEX',

  // Icon sizes (px) generated for various platforms
  sizes: {
    favicon: 32,
    tray: 16,
    tray2x: 32,
    appSmall: 64,
    appMedium: 256,
    appLarge: 512,
    appXLarge: 1024,
    installerSidebar: { width: 164, height: 314 },
  },
} as const
