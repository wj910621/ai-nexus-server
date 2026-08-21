// Brand identity for Y·NEX Story Studio
// Used by icon generator and UI theming

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
  name: 'Y·NEX Story Studio',
  nameShort: 'Y·NEX Story',

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
