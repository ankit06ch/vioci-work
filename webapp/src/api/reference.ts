/** Canonical HTTP API reference (keep in sync with server/routes). */

export const API_BASE = '/api'

export type HttpMethod = 'GET' | 'POST' | 'DELETE' | 'WS'

export interface EndpointDoc {
  method: HttpMethod
  path: string
  summary: string
  description?: string
  requestBody?: string
  response?: string
  query?: string
  notes?: string[]
}

export interface ApiSection {
  id: string
  title: string
  description: string
  endpoints: EndpointDoc[]
}

export const API_SECTIONS: ApiSection[] = [
  {
    id: 'auth',
    title: 'Authentication',
    description:
      'JWT bearer tokens. Sign up (personal or enterprise), login, then send Authorization: Bearer <token> on all project routes. WebSocket: ?token=<jwt>.',
    endpoints: [
      {
        method: 'POST',
        path: '/api/auth/signup',
        summary: 'Create personal account',
        requestBody: '{ "email", "password" (min 8), "full_name" }',
        response: '{ "access_token", "token_type": "bearer" }',
      },
      {
        method: 'POST',
        path: '/api/auth/signup/enterprise',
        summary: 'Create organization + owner account',
        requestBody:
          '{ "organization_name", "organization_slug?", "plan", "email", "password", "full_name", "job_title?" }',
        response: '{ "access_token", "token_type": "bearer" }',
      },
      {
        method: 'POST',
        path: '/api/auth/login',
        summary: 'Login',
        requestBody: '{ "email", "password" }',
        response: '{ "access_token", "token_type": "bearer" }',
      },
      {
        method: 'GET',
        path: '/api/auth/me',
        summary: 'Current user profile',
        response: 'UserOut (requires Bearer token)',
      },
    ],
  },
  {
    id: 'overview',
    title: 'Overview',
    description:
      'REST + WebSocket API for diagram ingestion, IR extraction, telemetry sheets, Gemini chat, and simulation. All routes are prefixed with /api. Run the backend with make api or make dev (port 8000).',
    endpoints: [
      {
        method: 'GET',
        path: '/api/health',
        summary: 'Health check',
        response: '{ "ok": true }',
      },
      {
        method: 'GET',
        path: '/api',
        summary: 'API index (links & version)',
        response:
          '{ "name": "Vioci Schemagraph API", "version": "0.9.1", "openapi": "/api/openapi.json", "docs": "/api/docs" }',
      },
    ],
  },
  {
    id: 'projects',
    title: 'Projects',
    description:
      'A project is one uploaded diagram image plus derived IR, sheets, and metadata. Create projects by uploading files; list and delete from the registry.',
    endpoints: [
      {
        method: 'POST',
        path: '/api/projects/upload',
        summary: 'Upload one or more diagram images',
        description: 'multipart/form-data with field files (repeatable). Each file becomes a project.',
        requestBody: 'files: image/png, image/jpeg, …',
        response: '{ "projects": [ ProjectMeta, … ] }',
      },
      {
        method: 'GET',
        path: '/api/projects',
        summary: 'List all projects',
        response: '[ ProjectMeta, … ]',
      },
      {
        method: 'GET',
        path: '/api/projects/{project_id}',
        summary: 'Get project metadata',
        response: 'ProjectMeta',
      },
      {
        method: 'DELETE',
        path: '/api/projects/{project_id}',
        summary: 'Delete project and workspace files',
        response: '204 No Content',
      },
      {
        method: 'GET',
        path: '/api/projects/{project_id}/image',
        summary: 'Source diagram image (PNG)',
        response: 'image/png',
      },
      {
        method: 'GET',
        path: '/api/projects/{project_id}/diagram',
        summary: 'Parsed diagram IR (JSON)',
        response: 'Diagram — nodes, edges, parameters, domain',
        notes: ['404 if parse has not completed yet'],
      },
    ],
  },
  {
    id: 'parse',
    title: 'Parse & IR',
    description:
      'Queue asynchronous parsing. Uses Google Gemini only. Hand-drawn vs clean routing and annotation domain (electrical, spacecraft, generic, …) are inferred automatically.',
    endpoints: [
      {
        method: 'POST',
        path: '/api/projects/{project_id}/parse',
        summary: 'Queue diagram parse (background job)',
        requestBody: '{}  // optional legacy body, ignored',
        response: '{ "status": "queued" }',
        notes: [
          'Subscribe to WebSocket /events for progress',
          'parse_status transitions: idle → queued → running → done | error',
        ],
      },
    ],
  },
  {
    id: 'events',
    title: 'WebSocket events',
    description: 'Real-time parse and simulation progress for a project.',
    endpoints: [
      {
        method: 'WS',
        path: '/api/projects/{project_id}/events',
        summary: 'Progress event stream',
        response:
          'JSON messages: { "type": "progress"|"error", "phase": "parse"|"annotate"|"done"|…, "message": "…", "progress": 0.0–1.0 }',
        notes: ['First message: connected. Client should reconnect on disconnect.'],
      },
    ],
  },
  {
    id: 'sheets',
    title: 'Telemetry sheets',
    description:
      'Attach CSV time-series or tabular data to diagram nodes. Data is stored per-project and referenced by sheet_id on node properties.',
    endpoints: [
      {
        method: 'POST',
        path: '/api/projects/{project_id}/sheets/{node_id}/upload',
        summary: 'Upload CSV for a node',
        requestBody: 'multipart: file (.csv)',
        response: '{ "sheet_id": "…", "rows_written": 42 }',
      },
      {
        method: 'GET',
        path: '/api/projects/{project_id}/sheets/{node_id}/rows',
        summary: 'Query sheet rows',
        query: 'limit (default 100), where (optional filter expression)',
        response: '{ "sheet_id": "…", "rows": [ { col: value, … } ], "count": N }',
      },
      {
        method: 'GET',
        path: '/api/projects/{project_id}/sheets/{node_id}/summary',
        summary: 'Column stats and row count',
        response: '{ "rows": N, "columns": [ … ], … }',
      },
    ],
  },
  {
    id: 'chat',
    title: 'AI chat (Gemini)',
    description:
      'Engineering Q&A over the full diagram or a single node. Requires GOOGLE_API_KEY or Vertex credentials (same as CLI).',
    endpoints: [
      {
        method: 'POST',
        path: '/api/projects/{project_id}/chat',
        summary: 'Diagram-level chat',
        requestBody: '{ "message": "Explain the power budget" }',
        response: '{ "reply": "…" }',
      },
      {
        method: 'POST',
        path: '/api/projects/{project_id}/chat/{node_id}',
        summary: 'Node-targeted chat',
        requestBody: '{ "message": "What is this component rated for?" }',
        response: '{ "reply": "…" }',
        notes: ['Includes node properties and sample sheet rows when available'],
      },
    ],
  },
  {
    id: 'simulate',
    title: 'Simulation',
    description:
      'Run in-process simulators against the parsed IR. Supports parameter overrides and multi-point sweeps.',
    endpoints: [
      {
        method: 'POST',
        path: '/api/projects/{project_id}/simulate',
        summary: 'Run simulation',
        requestBody: '{ "engine": "analytic_rc", "overrides": { "R1": 1000 } }',
        response:
          '{ "engine", "success", "log", "artifacts", "metadata", "datasets": [{ "series": [{ "name", "values" }] }] }',
        notes: ['Engines: analytic_rc, ngspice (when installed)'],
      },
      {
        method: 'POST',
        path: '/api/projects/{project_id}/sweep',
        summary: 'Parameter sweep',
        requestBody: '{ "engine": "analytic_rc", "axis": { "R1": [500, 1000, 2000] } }',
        response: '[ { "overrides": { … }, "result": { … } | "error": "…" }, … ]',
      },
    ],
  },
]

export const CURL_EXAMPLES: { title: string; code: string }[] = [
  {
    title: 'Health check',
    code: `curl -s http://127.0.0.1:8000/api/health`,
  },
  {
    title: 'Upload a diagram',
    code: `curl -s -X POST http://127.0.0.1:8000/api/projects/upload \\
  -F "files=@/path/to/schematic.png"`,
  },
  {
    title: 'Queue parse',
    code: `PROJECT_ID="<uuid-from-upload>"
curl -s -X POST "http://127.0.0.1:8000/api/projects/$PROJECT_ID/parse" \\
  -H "Content-Type: application/json" \\
  -d '{}'`,
  },
  {
    title: 'Fetch diagram IR',
    code: `curl -s "http://127.0.0.1:8000/api/projects/$PROJECT_ID/diagram" | jq .`,
  },
  {
    title: 'Diagram chat',
    code: `curl -s -X POST "http://127.0.0.1:8000/api/projects/$PROJECT_ID/chat" \\
  -H "Content-Type: application/json" \\
  -d '{"message":"Summarize major subsystems"}'`,
  },
  {
    title: 'Run simulation',
    code: `curl -s -X POST "http://127.0.0.1:8000/api/projects/$PROJECT_ID/simulate" \\
  -H "Content-Type: application/json" \\
  -d '{"engine":"analytic_rc","overrides":{"R":1000}}'`,
  },
]

export const PROJECT_META_SHAPE = `interface ProjectMeta {
  id: string
  name: string
  created_at: string       // ISO-8601
  parse_status: "idle" | "queued" | "running" | "done" | "error"
  parse_error: string | null
  last_provider: string | null   // e.g. "google"
  last_domain: string | null   // e.g. "electrical", "spacecraft"
  handdrawn: boolean
  has_diagram: boolean
}`

export const ENV_VARS = [
  { name: 'GOOGLE_API_KEY', desc: 'Gemini API key for parse and chat' },
  { name: 'GOOGLE_CLOUD_PROJECT', desc: 'Vertex AI project (alternative to API key)' },
  { name: 'GOOGLE_APPLICATION_CREDENTIALS', desc: 'Service account JSON for Vertex' },
]
