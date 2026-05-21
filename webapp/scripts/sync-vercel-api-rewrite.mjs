/**
 * Injects /api proxy rewrites into vercel.json when VIOCI_API_ORIGIN is set
 * (Vercel project env var, e.g. https://vioci-api.onrender.com).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))
const vercelPath = path.join(root, '..', 'vercel.json')
const origin = (process.env.VIOCI_API_ORIGIN || '').trim().replace(/\/$/, '')

const config = JSON.parse(fs.readFileSync(vercelPath, 'utf8'))
const rewrites = (config.rewrites || []).filter((r) => !String(r.source || '').startsWith('/api'))

if (origin) {
  rewrites.unshift({
    source: '/api/:path*',
    destination: `${origin}/api/:path*`,
  })
  console.log(`[vercel] API rewrite → ${origin}/api/*`)
} else if (!rewrites.some((r) => r.source === '/(.*)')) {
  console.log('[vercel] Using API rewrite from vercel.json (VIOCI_API_ORIGIN unset)')
}

if (!rewrites.some((r) => r.source === '/(.*)')) {
  rewrites.push({ source: '/(.*)', destination: '/index.html' })
}
config.rewrites = rewrites
fs.writeFileSync(vercelPath, `${JSON.stringify(config, null, 2)}\n`)
