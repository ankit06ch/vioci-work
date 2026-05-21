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
const rewrites = []

if (origin) {
  rewrites.push({
    source: '/api/:path*',
    destination: `${origin}/api/:path*`,
  })
  console.log(`[vercel] API rewrite → ${origin}/api/*`)
} else {
  console.warn(
    '[vercel] VIOCI_API_ORIGIN unset — UI will call /api on the Vercel host only. Set after Render deploy.',
  )
}

rewrites.push({ source: '/(.*)', destination: '/index.html' })
config.rewrites = rewrites
fs.writeFileSync(vercelPath, `${JSON.stringify(config, null, 2)}\n`)
