/**
 * Procedural icon generator for ComicStudio AI.
 * Generates:
 *   - resources/icons/icon.png       (1024x1024 master PNG)
 *   - resources/icons/icon.ico       (Windows multi-size ICO)
 *   - resources/icons/icon.icns      (macOS ICNS — placeholder PNG, real ICNS requires native tools)
 *   - resources/icons/tray.png       (32x32 tray icon)
 *   - resources/icons/trayTemplate.png (16x16 macOS template)
 *   - build/installer-sidebar.bmp    (NSIS sidebar 164x314)
 *
 * Usage: npx tsx scripts/generate-icons.ts
 *
 * Design: A rounded-square gradient background (blue→violet) with a white "C" glyph centered.
 *         The "C" has a clean geometric cut, evoking modern AI software branding.
 */
import sharp from 'sharp'
import pngToIco from 'png-to-ico'
import * as fs from 'fs/promises'
import * as path from 'path'
import { BRAND } from '../src/main/brand'

const ICONS_DIR = path.resolve(__dirname, '../resources/icons')
const BUILD_DIR = path.resolve(__dirname, '../build')

async function ensureDirs(): Promise<void> {
  await fs.mkdir(ICONS_DIR, { recursive: true })
  await fs.mkdir(BUILD_DIR, { recursive: true })
}

/**
 * Build an SVG string for the master icon at a given size.
 */
function buildIconSvg(size: number): string {
  const padding = size * 0.05
  const innerSize = size - padding * 2
  const radius = size * 0.18

  // "C" glyph: rendered as an arc using SVG path
  // Center at (size/2, size/2), radius = size * 0.28
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.28
  const strokeWidth = size * 0.14

  // Arc from 60deg to 300deg (counterclockwise) — opens to the right
  // Convert degrees to radians and compute start/end points
  const startAngle = (60 * Math.PI) / 180
  const endAngle = (300 * Math.PI) / 180
  const startX = cx + r * Math.cos(startAngle)
  const startY = cy - r * Math.sin(startAngle)
  const endX = cx + r * Math.cos(endAngle)
  const endY = cy - r * Math.sin(endAngle)

  // Sweep flag: 0 for counterclockwise (going through top)
  const largeArc = 0
  const sweep = 0

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="${BRAND.primary}"/>
      <stop offset="100%" stop-color="${BRAND.secondary}"/>
    </linearGradient>
    <linearGradient id="glyphGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="1"/>
      <stop offset="100%" stop-color="#e0e7ff" stop-opacity="0.95"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="${size * 0.02}"/>
      <feOffset dx="0" dy="${size * 0.01}" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA type="linear" slope="0.3"/>
      </feComponentTransfer>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <!-- Background rounded rectangle with gradient -->
  <rect x="${padding}" y="${padding}" width="${innerSize}" height="${innerSize}" rx="${radius}" ry="${radius}" fill="url(#bg)"/>
  <!-- Subtle inner glow -->
  <rect x="${padding + size * 0.02}" y="${padding + size * 0.02}" width="${innerSize - size * 0.04}" height="${innerSize - size * 0.04}" rx="${radius - size * 0.02}" ry="${radius - size * 0.02}" fill="none" stroke="#ffffff" stroke-opacity="0.15" stroke-width="${size * 0.008}"/>
  <!-- "C" glyph as a thick arc -->
  <path d="M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} ${sweep} ${endX} ${endY}"
        fill="none"
        stroke="url(#glyphGrad)"
        stroke-width="${strokeWidth}"
        stroke-linecap="round"
        filter="url(#shadow)"/>
</svg>`
}

/**
 * Generate the master 1024x1024 PNG.
 */
async function generateMasterPng(): Promise<Buffer> {
  const svg = buildIconSvg(BRAND.sizes.appXLarge)
  const png = await sharp(Buffer.from(svg)).png().toBuffer()
  await fs.writeFile(path.join(ICONS_DIR, 'icon.png'), png)
  return png
}

/**
 * Generate the Windows ICO (multi-size embedded).
 */
async function generateIco(masterPng: Buffer): Promise<void> {
  const sizes = [16, 32, 48, 64, 128, 256]
  const pngBuffers: Buffer[] = []
  for (const size of sizes) {
    const buf = await sharp(masterPng).resize(size, size).png().toBuffer()
    pngBuffers.push(buf)
  }
  const ico = await pngToIco(pngBuffers)
  await fs.writeFile(path.join(ICONS_DIR, 'icon.ico'), ico)
}

/**
 * Generate the macOS ICNS.
 * Note: Real ICNS generation requires native tools (iconutil on macOS).
 * We generate the PNG master; electron-builder will convert it to ICNS during packaging.
 * As a fallback, we copy the PNG to icon.icns as a placeholder.
 */
async function generateIcns(masterPng: Buffer): Promise<void> {
  // electron-builder accepts a 1024x1024 PNG and auto-converts to ICNS using iconutil.
  // We don't write a .icns file here; instead, electron-builder.yml points to icon.png.
  // But for platforms without iconutil, we provide a fallback.
  await fs.writeFile(path.join(ICONS_DIR, 'icon.icns'), masterPng)
}

/**
 * Generate tray icons (16x16 and 32x32).
 * For macOS template, use a monochrome version (white glyph on transparent).
 */
async function generateTrayIcons(): Promise<void> {
  // Colored tray icon (for Windows/Linux)
  const svg32 = buildIconSvg(BRAND.sizes.tray2x)
  const png32 = await sharp(Buffer.from(svg32)).png().toBuffer()
  await fs.writeFile(path.join(ICONS_DIR, 'tray.png'), png32)

  // macOS template: simple white "C" on transparent background, marked as template
  const size = BRAND.sizes.tray
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.32
  const strokeWidth = size * 0.18
  const startAngle = (60 * Math.PI) / 180
  const endAngle = (300 * Math.PI) / 180
  const startX = cx + r * Math.cos(startAngle)
  const startY = cy - r * Math.sin(startAngle)
  const endX = cx + r * Math.cos(endAngle)
  const endY = cy - r * Math.sin(endAngle)
  const templateSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <path d="M ${startX} ${startY} A ${r} ${r} 0 0 0 ${endX} ${endY}"
        fill="none" stroke="#000000" stroke-width="${strokeWidth}" stroke-linecap="round"/>
</svg>`
  const templatePng = await sharp(Buffer.from(templateSvg)).png().toBuffer()
  await fs.writeFile(path.join(ICONS_DIR, 'trayTemplate.png'), templatePng)
}

/**
 * Encode raw RGBA pixels into a 24-bit BMP buffer (BI_RGB, bottom-up).
 * sharp cannot write BMP directly (not a supported output format), so we
 * encode it manually from raw RGBA pixels fetched via sharp().raw().
 */
function encodeBmp(rgba: Buffer, width: number, height: number): Buffer {
  // Each row is padded to a 4-byte boundary; 24bpp = 3 bytes/pixel.
  const rowSize = Math.floor((24 * width + 31) / 32) * 4
  const pixelDataSize = rowSize * height
  const fileSize = 54 + pixelDataSize

  const bmp = Buffer.alloc(fileSize)
  // BITMAPFILEHEADER (14 bytes)
  bmp.write('BM', 0)
  bmp.writeUInt32LE(fileSize, 2)
  bmp.writeUInt32LE(0, 6)
  bmp.writeUInt32LE(54, 10)
  // BITMAPINFOHEADER (40 bytes)
  bmp.writeUInt32LE(40, 14)
  bmp.writeInt32LE(width, 18)
  bmp.writeInt32LE(height, 22) // positive => bottom-up
  bmp.writeUInt16LE(1, 26) // planes
  bmp.writeUInt16LE(24, 28) // bpp
  bmp.writeUInt32LE(0, 30) // BI_RGB
  bmp.writeUInt32LE(pixelDataSize, 34)
  bmp.writeUInt32LE(2835, 38) // x ppm (~72 DPI)
  bmp.writeUInt32LE(2835, 42) // y ppm
  bmp.writeUInt32LE(0, 46)
  bmp.writeUInt32LE(0, 50)

  // Pixel data: bottom-up, BGR, each row padded to 4-byte boundary
  let rowStart = 54
  for (let y = height - 1; y >= 0; y--) {
    let out = rowStart
    for (let x = 0; x < width; x++) {
      const src = (y * width + x) * 4 // RGBA
      bmp[out++] = rgba[src + 2] // B
      bmp[out++] = rgba[src + 1] // G
      bmp[out++] = rgba[src] // R
    }
    rowStart += rowSize
  }
  return bmp
}

/**
 * Generate the NSIS installer sidebar bitmap (164x314).
 * Solid dark background with brand gradient stripe and app name.
 */
async function generateInstallerSidebar(): Promise<void> {
  const { width, height } = BRAND.sizes.installerSidebar
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="${BRAND.bgDark}"/>
      <stop offset="100%" stop-color="${BRAND.bgDarker}"/>
    </linearGradient>
    <linearGradient id="stripe" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="${BRAND.primary}"/>
      <stop offset="100%" stop-color="${BRAND.secondary}"/>
    </linearGradient>
  </defs>
  <rect width="${width}" height="${height}" fill="url(#bg)"/>
  <rect x="0" y="${height - 8}" width="${width}" height="8" fill="url(#stripe)"/>
  <text x="${width / 2}" y="${height / 2 - 10}" text-anchor="middle" fill="#ffffff" font-family="Segoe UI, sans-serif" font-size="22" font-weight="700">${BRAND.nameShort}</text>
  <text x="${width / 2}" y="${height / 2 + 18}" text-anchor="middle" fill="#9ca3af" font-family="Segoe UI, sans-serif" font-size="11">AI Comic Studio</text>
</svg>`
  // NSIS expects BMP format. sharp cannot write BMP directly, so we render
  // the SVG to raw RGBA pixels via sharp and encode BMP manually.
  const { data, info } = await sharp(Buffer.from(svg))
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true })
  const bmp = encodeBmp(data, info.width, info.height)
  await fs.writeFile(path.join(BUILD_DIR, 'installer-sidebar.bmp'), bmp)
}

async function main(): Promise<void> {
  console.log('Generating ComicStudio AI icons...')
  await ensureDirs()
  const masterPng = await generateMasterPng()
  await generateIco(masterPng)
  await generateIcns(masterPng)
  await generateTrayIcons()
  await generateInstallerSidebar()
  console.log('Icons generated successfully in resources/icons and build/')
}

main().catch((err) => {
  console.error('Icon generation failed:', err)
  process.exit(1)
})
