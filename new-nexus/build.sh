echo "=== TriGen Desktop Build Script ==="
echo ""

# Step 1: Install dependencies
echo "[1/3] Installing npm dependencies..."
npm install
if [ $? -ne 0 ]; then
  echo "❌ npm install failed"
  exit 1
fi
echo "✅ Dependencies installed"

# Step 2: Build for current platform
echo ""
echo "[2/3] Building desktop installer..."
npm run dist
if [ $? -ne 0 ]; then
  echo "❌ Build failed"
  exit 1
fi

# Step 3: Show results
echo ""
echo "[3/3] ✅ Build complete!"
echo ""
echo "📦 Installer location:"
ls -la release/*.exe release/*.dmg release/*.AppImage 2>/dev/null || echo "   (check release/ directory)"

echo ""
echo "🔧 Available commands:"
echo "   npm start          # Run in development mode"
echo "   npm run dist:win   # Build Windows installer"
echo "   npm run dist:mac   # Build macOS installer"
echo "   npm run dist:linux # Build Linux installer"
echo ""
echo "📋 System requirements:"
echo "   Node.js 18+"
echo "   Windows: NSIS (included with electron-builder)"
echo "   macOS: Xcode command line tools"
echo "   Linux: rpm, dpkg"
