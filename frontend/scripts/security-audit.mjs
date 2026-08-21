import { spawnSync } from 'node:child_process'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

// Policy: the frontend is a client-only BrowserRouter SPA and must ship with
// ZERO known npm vulnerabilities. The previous time-bound RSC-advisory exception
// (GHSA-qwww-vcr4-c8h2) is removed because react-router-dom was upgraded to the
// patched 7.18.x. Any npm vulnerability now fails the release gate.

function sourceFiles(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    return statSync(path).isDirectory() ? sourceFiles(path) : [path]
  })
}

const npmCli = process.env.npm_execpath
if (!npmCli) {
  throw new Error('Run this policy through npm run audit:production')
}
const result = spawnSync(
  process.execPath,
  [npmCli, 'audit', '--json', '--registry=https://registry.npmjs.org'],
  { encoding: 'utf8' },
)
if (!result.stdout) {
  throw new Error(`npm audit produced no JSON: ${result.stderr || 'unknown error'}`)
}

const report = JSON.parse(result.stdout)
const vulnerabilities = report.vulnerabilities ?? {}
const checked = new Set()

function validateVulnerability(name) {
  if (checked.has(name)) return
  checked.add(name)
  const vulnerability = vulnerabilities[name]
  if (!vulnerability) {
    throw new Error(`npm audit referenced missing vulnerability: ${name}`)
  }
  // Zero-tolerance: any advisory fails the gate.
  throw new Error(`Blocked npm advisory: ${name} (${vulnerability.severity})`)
}

for (const name of Object.keys(vulnerabilities)) {
  validateVulnerability(name)
}

const forbiddenRouterModes = [
  /from\s+['"]react-router(?:-dom)?\/server['"]/,
  /\bcreateStaticRouter\b/,
  /\bcreateRequestHandler\b/,
  /\bRSCRouter\b/,
  /\bServerRouter\b/,
]
for (const file of sourceFiles(join(process.cwd(), 'src'))) {
  if (!/\.[cm]?[jt]sx?$/.test(file)) continue
  const source = readFileSync(file, 'utf8')
  if (forbiddenRouterModes.some((pattern) => pattern.test(source))) {
    throw new Error(`RSC/server router API invalidates advisory exception: ${relative(process.cwd(), file)}`)
  }
}

const appSource = readFileSync(join(process.cwd(), 'src', 'App.tsx'), 'utf8')
if (!appSource.includes('BrowserRouter')) {
  throw new Error('Release gate requires the BrowserRouter-only SPA architecture')
}

if (Object.keys(vulnerabilities).length === 0) {
  console.log('npm audit: no known vulnerabilities')
} else {
  // validateVulnerability() above already threw; this is defensive.
  console.error('npm audit: vulnerabilities detected; failing release gate')
  process.exit(1)
}
