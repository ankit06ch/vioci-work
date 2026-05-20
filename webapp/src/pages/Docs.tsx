import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LoadingIndicator } from '../components/LoadingIndicator'
import {
  API_BASE,
  API_SECTIONS,
  CURL_EXAMPLES,
  ENV_VARS,
  PROJECT_META_SHAPE,
} from '../api/reference'

function MethodBadge({ method }: { method: string }) {
  const cls =
    method === 'GET'
      ? 'method-get'
      : method === 'POST'
        ? 'method-post'
        : method === 'DELETE'
          ? 'method-delete'
          : 'method-ws'
  return <span className={`method-badge ${cls}`}>{method}</span>
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="code-block">
      <button type="button" className="code-copy btn btn-ghost" onClick={() => void copy()}>
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="mono">{code}</pre>
    </div>
  )
}

export function Docs() {
  const [apiInfo, setApiInfo] = useState<Record<string, unknown> | null>(null)
  const [apiErr, setApiErr] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const r = await fetch(`${API_BASE}`)
        if (!r.ok) throw new Error(`${r.status}`)
        setApiInfo((await r.json()) as Record<string, unknown>)
      } catch (e) {
        setApiErr(e instanceof Error ? e.message : String(e))
      }
    })()
  }, [])

  return (
    <div className="docs-page">
      <header className="page-header">
        <h2>API Documentation</h2>
        <p className="muted">
          Programmatic access to diagram ingestion, IR, telemetry, AI chat, and simulation. Use
          from scripts, CI, or custom integrations — the web UI is a client of this same API.
        </p>
      </header>

      <div className="docs-actions">
        <a href="/api/docs" target="_blank" rel="noreferrer" className="btn btn-primary">
          OpenAPI (Swagger) ↗
        </a>
        <a href="/api/redoc" target="_blank" rel="noreferrer" className="btn">
          ReDoc ↗
        </a>
        <a href="/api/openapi.json" target="_blank" rel="noreferrer" className="btn btn-ghost">
          openapi.json ↗
        </a>
        <Link to="/upload" className="btn btn-ghost">
          Try ingest pipeline
        </Link>
      </div>

      {apiInfo ? (
        <div className="card docs-status">
          <span className="status-dot live" />
          <span className="mono">
            API online — {(apiInfo.name as string) ?? 'schemagraph'} v
            {(apiInfo.version as string) ?? '?'}
          </span>
        </div>
      ) : apiErr ? (
        <div className="card">
          <p className="error">API index unreachable ({apiErr}). Start backend: make dev</p>
        </div>
      ) : (
        <LoadingIndicator label="Checking API…" size="sm" />
      )}

      <div className="docs-layout">
        <nav className="docs-toc glass-panel">
          <div className="panel-head">
            <h3 className="panel-title">Sections</h3>
          </div>
          <ul>
            <li>
              <a href="#auth">Authentication</a>
            </li>
            <li>
              <a href="#quickstart">Quick start</a>
            </li>
            <li>
              <a href="#types">Types</a>
            </li>
            <li>
              <a href="#env">Environment</a>
            </li>
            {API_SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`}>{s.title}</a>
              </li>
            ))}
            <li>
              <a href="#workflow">Typical workflow</a>
            </li>
          </ul>
        </nav>

        <div className="docs-content">
          <section id="quickstart" className="docs-section card">
            <h3>Quick start</h3>
            <p className="muted">
              Base URL: <code className="mono">http://127.0.0.1:8000</code> (or proxied via Vite at{' '}
              <code className="mono">/api</code> during <code className="mono">npm run dev</code>).
              No authentication on local dev.
            </p>
            <ol className="docs-steps">
              <li>
                <strong>Authenticate</strong> — POST <code className="mono">/api/auth/login</code>{' '}
                or signup; use <code className="mono">Authorization: Bearer …</code> on requests.
              </li>
              <li>
                <strong>Upload</strong> — POST <code className="mono">/api/projects/upload</code>{' '}
                with diagram images.
              </li>
              <li>
                <strong>Parse</strong> — POST <code className="mono">/api/projects/&#123;id&#125;/parse</code>{' '}
                and watch WebSocket <code className="mono">/events</code>.
              </li>
              <li>
                <strong>Consume IR</strong> — GET{' '}
                <code className="mono">/api/projects/&#123;id&#125;/diagram</code>.
              </li>
              <li>
                <strong>Optional</strong> — attach CSV sheets, chat, simulate.
              </li>
            </ol>
            {CURL_EXAMPLES.map((ex) => (
              <div key={ex.title} className="docs-example">
                <h4>{ex.title}</h4>
                <CodeBlock code={ex.code} />
              </div>
            ))}
          </section>

          <section id="types" className="docs-section card">
            <h3>Core types</h3>
            <p className="muted">Project metadata returned by list/get/upload endpoints.</p>
            <CodeBlock code={PROJECT_META_SHAPE} />
            <p className="muted" style={{ marginTop: '0.75rem' }}>
              Full IR schema: see repo <code className="mono">docs/ir_spec.md</code> and parsed JSON
              from <code className="mono">GET …/diagram</code>.
            </p>
          </section>

          <section id="env" className="docs-section card">
            <h3>Environment</h3>
            <p className="muted">Set in repo-root <code className="mono">.env</code> for parse &amp; chat.</p>
            <table className="inspector-table">
              <thead>
                <tr>
                  <th>Variable</th>
                  <th>Purpose</th>
                </tr>
              </thead>
              <tbody>
                {ENV_VARS.map((v) => (
                  <tr key={v.name}>
                    <td className="mono glow-cyan">{v.name}</td>
                    <td>{v.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {API_SECTIONS.filter((s) => s.id !== 'overview').map((section) => (
            <section key={section.id} id={section.id} className="docs-section card">
              <h3>{section.title}</h3>
              <p className="muted">{section.description}</p>
              <div className="endpoint-list">
                {section.endpoints.map((ep) => (
                  <article key={`${ep.method}-${ep.path}`} className="endpoint-card">
                    <div className="endpoint-head">
                      <MethodBadge method={ep.method} />
                      <code className="mono endpoint-path">{ep.path}</code>
                    </div>
                    <p className="endpoint-summary">{ep.summary}</p>
                    {ep.description ? <p className="muted">{ep.description}</p> : null}
                    {ep.requestBody ? (
                      <div className="endpoint-detail">
                        <span className="detail-label">Request</span>
                        <code className="mono">{ep.requestBody}</code>
                      </div>
                    ) : null}
                    {ep.query ? (
                      <div className="endpoint-detail">
                        <span className="detail-label">Query</span>
                        <code className="mono">{ep.query}</code>
                      </div>
                    ) : null}
                    {ep.response ? (
                      <div className="endpoint-detail">
                        <span className="detail-label">Response</span>
                        <code className="mono">{ep.response}</code>
                      </div>
                    ) : null}
                    {ep.notes?.map((n, i) => (
                      <p key={i} className="endpoint-note muted">
                        • {n}
                      </p>
                    ))}
                  </article>
                ))}
              </div>
            </section>
          ))}

          <section id="overview" className="docs-section card">
            <h3>System endpoints</h3>
            <p className="muted">{API_SECTIONS[0].description}</p>
            <div className="endpoint-list">
              {API_SECTIONS[0].endpoints.map((ep) => (
                <article key={ep.path} className="endpoint-card">
                  <div className="endpoint-head">
                    <MethodBadge method={ep.method} />
                    <code className="mono endpoint-path">{ep.path}</code>
                  </div>
                  <p className="endpoint-summary">{ep.summary}</p>
                  {ep.response ? (
                    <code className="mono muted">{ep.response}</code>
                  ) : null}
                </article>
              ))}
            </div>
          </section>

          <section id="workflow" className="docs-section card">
            <h3>Typical workflow</h3>
            <div className="workflow-diagram mono">
              <pre>{`upload → parse (async) → diagram JSON
                    ↓
         ┌──────────┼──────────┐
         ▼          ▼          ▼
    sheets/CSV   chat      simulate
    per node    (Gemini)   / sweep`}</pre>
            </div>
            <p className="muted">
              The browser UI uses these same endpoints via{' '}
              <code className="mono">webapp/src/api/client.ts</code>. Build your own client in any
              language against OpenAPI or the reference above.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
