import { spawnSync } from 'node:child_process'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const allowedAdvisories = new Set(['https://github.com/advisories/GHSA-qwww-vcr4-c8h2'])
const reviewDeadline = new Date('2026-08-31T00:00:00Z')

function sourceFiles(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    return statSync(path).isDirectory() ? sourceFiles(path) : [path]
  })
}

if (new Date() >= reviewDeadline) {
  throw new Error('React Router RSC advisory exception expired; review and upgrade dependency')
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
  for (const via of vulnerability.via ?? []) {
    if (typeof via === 'string') {
      validateVulnerability(via)
      continue
    }
    if (!allowedAdvisories.has(via.url)) {
      throw new Error(`Unapproved ${via.severity} advisory: ${via.url} (${name})`)
    }
  }
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
  throw new Error('Advisory exception requires the BrowserRouter-only SPA architecture')
}

if (Object.keys(vulnerabilities).length === 0) {
  console.log('npm audit: no known vulnerabilities')
} else {
  console.log(
    'npm audit: only GHSA-qwww-vcr4-c8h2 remains; time-bound BrowserRouter SPA exception verified',
  )
}
