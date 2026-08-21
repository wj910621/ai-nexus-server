// Builds a desktop installer variant by selecting a target block from
// electron-builder.yml and invoking electron-builder.
//
// Usage:
//   node scripts/build-variant.js --target nsis-gpu
//   node scripts/build-variant.js --target appimage-cpu
//
// Variants are defined as top-level keys in electron-builder.yml with
// artifactName and target-specific overrides. This script:
//   1. Reads electron-builder.yml
//   2. Validates the requested --target exists
//   3. Builds the main/renderer via electron-vite
//   4. Invokes electron-builder with the --config flag and --win/--linux

const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')

const VALID_TARGETS = new Set([
  'nsis-gpu',
  'nsis-cpu',
  'appimage-gpu',
  'appimage-cpu',
])

function parseArgs(argv) {
  const args = { target: null, skipBuild: false }
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === '--target') {
      args.target = argv[++i]
    } else if (arg === '--skip-build') {
      args.skipBuild = true
    } else if (arg === '--help' || arg === '-h') {
      printUsage()
      process.exit(0)
    }
  }
  return args
}

function printUsage() {
  console.log('Usage: node scripts/build-variant.js --target <target> [--skip-build]')
  console.log('')
  console.log('Valid targets:')
  for (const t of VALID_TARGETS) {
    console.log(`  ${t}`)
  }
}

function readElectronBuilderConfig() {
  const configPath = path.join(__dirname, '..', 'electron-builder.yml')
  if (!fs.existsSync(configPath)) {
    throw new Error(`electron-builder.yml not found at ${configPath}`)
  }
  const raw = fs.readFileSync(configPath, 'utf8')
  // Use js-yaml if available; otherwise fall back to a minimal parser
  try {
    const yaml = require('js-yaml')
    return yaml.load(raw)
  } catch {
    throw new Error(
      'js-yaml is required to parse electron-builder.yml. Run: npm install js-yaml --save-dev',
    )
  }
}

function platformForTarget(target) {
  if (target.startsWith('nsis-')) return 'win'
  if (target.startsWith('appimage-')) return 'linux'
  throw new Error(`Unknown target platform for: ${target}`)
}

function main() {
  const args = parseArgs(process.argv)
  if (!args.target) {
    console.error('Error: --target is required')
    printUsage()
    process.exit(1)
  }
  if (!VALID_TARGETS.has(args.target)) {
    console.error(`Error: invalid target "${args.target}"`)
    printUsage()
    process.exit(1)
  }

  const config = readElectronBuilderConfig()
  if (!config[args.target]) {
    throw new Error(
      `Target "${args.target}" block not found in electron-builder.yml. ` +
        'Run Phase 7 Task 16 first to add variant blocks.',
    )
  }

  const platform = platformForTarget(args.target)
  console.log(`[build-variant] target=${args.target} platform=${platform}`)

  // Step 1: build main/preload/renderer via electron-vite
  if (!args.skipBuild) {
    console.log('[build-variant] running electron-vite build...')
    // Invoke local JavaScript CLIs with Node directly.  On Windows, spawning
    // npx.cmd without a shell can fail with EINVAL and hides the real build.
    const desktopRoot = path.join(__dirname, '..')
    const buildResult = spawnSync(
      process.execPath,
      [path.join(desktopRoot, 'node_modules', 'electron-vite', 'bin', 'electron-vite.js'), 'build'],
      { stdio: 'inherit', cwd: desktopRoot },
    )
    if (buildResult.status !== 0) {
      console.error('[build-variant] electron-vite build failed')
      process.exit(buildResult.status || 1)
    }
  }

  // Step 2: run electron-builder with the variant as --config target
  // electron-builder merges top-level keys; we pass the variant block via
  // an inline override using the --config flag with a filtered config.
  const variantConfig = { ...config }
  // Variant blocks are project metadata, not electron-builder schema keys.
  // Remove every block before passing the generated configuration to the
  // builder, then apply only the requested variant at the top level.
  for (const target of VALID_TARGETS) {
    delete variantConfig[target]
  }
  // Variant block contains artifactName + extra resources; merge it into the
  // active builder configuration.
  Object.assign(variantConfig, config[args.target])

  const tmpConfigPath = path.join(__dirname, '..', `.electron-builder.${args.target}.yml`)
  const yaml = require('js-yaml')
  fs.writeFileSync(tmpConfigPath, yaml.dump(variantConfig))

  try {
    console.log(`[build-variant] running electron-builder for ${platform}...`)
    const desktopRoot = path.join(__dirname, '..')
    const ebResult = spawnSync(
      process.execPath,
      [path.join(desktopRoot, 'node_modules', 'electron-builder', 'cli.js'), `--${platform}`, '--config', tmpConfigPath],
      { stdio: 'inherit', cwd: desktopRoot },
    )
    if (ebResult.status !== 0) {
      console.error('[build-variant] electron-builder failed')
      process.exit(ebResult.status || 1)
    }
    console.log(`[build-variant] success: ${args.target}`)
  } finally {
    if (fs.existsSync(tmpConfigPath)) {
      fs.unlinkSync(tmpConfigPath)
    }
  }
}

main()
