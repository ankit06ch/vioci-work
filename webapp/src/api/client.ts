import axios, { isAxiosError } from 'axios'
import type {
  AnnotationsDocument,
  Diagram,
  PartAnnotation,
  LaunchCompatCheck,
  LaunchCompatResult,
  LaunchVehicleMeta,
  ProjectMeta,
  SchemaFolder,
  SchemaRegistryDocument,
  SchemaRegistryQuery,
  SchemaRegistrySqlResult,
  SimulateResult,
  WsEvent,
} from './types'
import { getStoredToken } from '../state/auth'

/** Empty = same origin (Vite proxy locally, Vercel /api rewrite in prod). */
export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export const http = axios.create({
  baseURL: apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
})

http.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (r) => r,
  (error) => {
    if (isAxiosError(error) && error.response?.status === 401) {
      const path = window.location.pathname
      if (!path.startsWith('/login') && !path.startsWith('/signup')) {
        window.location.href = `/login?next=${encodeURIComponent(path)}`
      }
    }
    return Promise.reject(error)
  },
)

/** User-facing message for failed API calls (network, 404, FastAPI detail, …). */
export function formatApiError(e: unknown): string {
  if (isAxiosError(e)) {
    if (e.code === 'ECONNABORTED') {
      return 'Request timed out — the API may be stuck reloading. Run `make kill-dev-ports` then `make dev`, or wait a few seconds and refresh.'
    }
    if (e.response == null) {
      return 'Cannot reach API — start the backend (port 8000) and use `npm run dev` so /api is proxied.'
    }
    const data = e.response.data as { detail?: unknown } | undefined
    const d = data?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      const msg = d
        .map((x) =>
          typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : String(x),
        )
        .join('; ')
      return msg || `${e.response.status} ${e.response.statusText}`
    }
    if (d != null && typeof d === 'object') {
      return JSON.stringify(d)
    }
    return `${e.response.status} ${e.response.statusText || e.message}`
  }
  if (e instanceof Error) return e.message
  return String(e)
}

export async function listFolders(): Promise<SchemaFolder[]> {
  const { data } = await http.get<SchemaFolder[]>('/api/folders')
  return data
}

export async function createFolder(name: string, parentId?: string | null): Promise<SchemaFolder> {
  const { data } = await http.post<SchemaFolder>('/api/folders', {
    name,
    parent_id: parentId ?? null,
  })
  return data
}

export async function deleteFolder(folderId: string): Promise<void> {
  await http.delete(`/api/folders/${folderId}`)
}

export async function moveProjectToFolder(
  projectId: string,
  folderId: string | null,
): Promise<ProjectMeta> {
  const { data } = await http.patch<ProjectMeta>(`/api/projects/${projectId}/folder`, {
    folder_id: folderId,
  })
  return data
}

export async function uploadProjects(
  files: File[],
  folderId?: string | null,
): Promise<ProjectMeta[]> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  if (folderId) fd.append('folder_id', folderId)
  const { data } = await http.post<{ projects: ProjectMeta[] }>('/api/projects/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.projects
}

export async function listProjects(): Promise<ProjectMeta[]> {
  const { data } = await http.get<ProjectMeta[]>('/api/projects')
  return data
}

export async function getProject(id: string): Promise<ProjectMeta> {
  const { data } = await http.get<ProjectMeta>(`/api/projects/${id}`)
  return data
}

export async function deleteProject(id: string): Promise<void> {
  await http.delete(`/api/projects/${id}`)
}

export async function getDiagram(id: string): Promise<Diagram> {
  const { data } = await http.get<Diagram>(`/api/projects/${id}/diagram`)
  return data
}

export async function deleteDiagramNodes(projectId: string, nodeIds: string[]): Promise<Diagram> {
  const { data } = await http.delete<Diagram>(`/api/projects/${projectId}/diagram/nodes`, {
    data: { node_ids: nodeIds },
  })
  return data
}

export async function renameDiagramNode(
  projectId: string,
  nodeId: string,
  label: string,
): Promise<Diagram> {
  const { data } = await http.patch<Diagram>(`/api/projects/${projectId}/diagram/nodes/${nodeId}`, {
    label,
  })
  return data
}

export function imageUrl(projectId: string): string {
  return `/api/projects/${projectId}/image`
}

export async function queueParse(projectId: string): Promise<void> {
  await http.post(`/api/projects/${projectId}/parse`, {})
}

function wsOrigin(): string {
  if (apiBaseUrl) {
    const u = new URL(apiBaseUrl)
    const scheme = u.protocol === 'https:' ? 'wss' : 'ws'
    return `${scheme}://${u.host}`
  }
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}`
}

export function openProjectEvents(projectId: string, onMessage: (e: WsEvent) => void): WebSocket {
  const token = getStoredToken()
  const q = token ? `?token=${encodeURIComponent(token)}` : ''
  const ws = new WebSocket(`${wsOrigin()}/api/projects/${projectId}/events${q}`)
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data as string) as WsEvent)
    } catch {
      /* ignore */
    }
  }
  return ws
}

export async function uploadSheetCsv(projectId: string, nodeId: string, file: File): Promise<void> {
  const fd = new FormData()
  fd.append('file', file)
  await http.post(`/api/projects/${projectId}/sheets/${nodeId}/upload`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function fetchSheetRows(
  projectId: string,
  nodeId: string,
  limit = 50,
): Promise<Record<string, unknown>[]> {
  const { data } = await http.get<{ rows: Record<string, unknown>[] }>(
    `/api/projects/${projectId}/sheets/${nodeId}/rows`,
    { params: { limit } },
  )
  return data.rows
}

export async function fetchSheetSummary(projectId: string, nodeId: string): Promise<Record<string, unknown>> {
  const { data } = await http.get(`/api/projects/${projectId}/sheets/${nodeId}/summary`)
  return data as Record<string, unknown>
}

export async function chatDiagram(projectId: string, message: string): Promise<string> {
  const { data } = await http.post<{ reply: string }>(`/api/projects/${projectId}/chat`, { message })
  return data.reply
}

export async function chatNode(projectId: string, nodeId: string, message: string): Promise<string> {
  const { data } = await http.post<{ reply: string }>(
    `/api/projects/${projectId}/chat/${nodeId}`,
    { message },
  )
  return data.reply
}

export async function runSimulate(
  projectId: string,
  engine: string,
  overrides: Record<string, unknown>,
): Promise<SimulateResult> {
  const { data } = await http.post<SimulateResult>(`/api/projects/${projectId}/simulate`, {
    engine,
    overrides,
  })
  return data
}

export async function runSweep(
  projectId: string,
  engine: string,
  axis: Record<string, unknown[]>,
): Promise<{ overrides: Record<string, unknown>; result?: SimulateResult; error?: string }[]> {
  const { data } = await http.post(`/api/projects/${projectId}/sweep`, { engine, axis })
  return data
}

export async function getAnnotations(projectId: string): Promise<AnnotationsDocument> {
  const { data } = await http.get<AnnotationsDocument>(`/api/projects/${projectId}/annotations`)
  return data
}

export async function saveAnnotations(
  projectId: string,
  annotations: PartAnnotation[],
): Promise<AnnotationsDocument> {
  const { data } = await http.put<AnnotationsDocument>(`/api/projects/${projectId}/annotations`, {
    annotations,
  })
  return data
}

export async function syncAnnotations(projectId: string): Promise<AnnotationsDocument> {
  const { data } = await http.post<AnnotationsDocument>(
    `/api/projects/${projectId}/annotations/sync`,
  )
  return data
}

export async function autoDetectAnnotations(projectId: string): Promise<AnnotationsDocument> {
  const { data } = await http.post<AnnotationsDocument>(
    `/api/projects/${projectId}/annotations/auto-detect`,
  )
  return data
}

export async function enhanceProjectImage(
  projectId: string,
): Promise<{ enhanced: boolean; quality_score: number; message: string }> {
  const { data } = await http.post(`/api/projects/${projectId}/image/enhance`)
  return data
}

export async function restoreProjectImage(
  projectId: string,
): Promise<{ enhanced: boolean; quality_score: number; message: string }> {
  const { data } = await http.post(`/api/projects/${projectId}/image/restore`)
  return data
}

export async function getSchemaRegistry(projectId: string): Promise<SchemaRegistryDocument> {
  const { data } = await http.get<SchemaRegistryDocument>(
    `/api/projects/${projectId}/schema-registry`,
  )
  return data
}

export async function querySchemaRegistry(
  projectId: string,
  table: 'components' | 'dependencies' | 'properties',
  q?: string,
  full = false,
): Promise<SchemaRegistryQuery> {
  const { data } = await http.get<SchemaRegistryQuery>(
    `/api/projects/${projectId}/schema-registry/query`,
    { params: { table, q: q || undefined, full: full || undefined } },
  )
  return data
}

export async function patchRegistryRow(
  projectId: string,
  table: 'components' | 'dependencies' | 'properties',
  rowIndex: number,
  values: Record<string, unknown>,
): Promise<{ row: Record<string, unknown>; row_index: number }> {
  const { data } = await http.patch(
    `/api/projects/${projectId}/schema-registry/tables/${table}/rows/${rowIndex}`,
    { values },
  )
  return data
}

export async function deleteRegistryRow(
  projectId: string,
  table: 'components' | 'dependencies' | 'properties',
  rowIndex: number,
): Promise<void> {
  await http.delete(
    `/api/projects/${projectId}/schema-registry/tables/${table}/rows/${rowIndex}`,
  )
}

export async function createRegistryRow(
  projectId: string,
  table: 'components' | 'dependencies' | 'properties',
  values: Record<string, unknown>,
): Promise<{ row: Record<string, unknown>; row_index: number }> {
  const { data } = await http.post(
    `/api/projects/${projectId}/schema-registry/tables/${table}/rows`,
    { values },
  )
  return data
}

export async function runRegistrySql(
  projectId: string,
  sql: string,
): Promise<SchemaRegistrySqlResult> {
  const { data } = await http.post<SchemaRegistrySqlResult>(
    `/api/projects/${projectId}/schema-registry/sql`,
    { sql },
  )
  return data
}

export async function refreshSchemaRegistry(
  projectId: string,
): Promise<SchemaRegistryDocument> {
  const { data } = await http.post<SchemaRegistryDocument>(
    `/api/projects/${projectId}/schema-registry/refresh`,
  )
  return data
}

export function schemaRegistryCsvUrl(
  projectId: string,
  table: 'components' | 'dependencies' | 'properties',
): string {
  return `/api/projects/${projectId}/schema-registry/csv/${table}`
}

export function explorerSchemaFileUrl(projectId: string, fileKey: string): string {
  return `/api/projects/${projectId}/schema-registry/explorer-file/${fileKey}`
}

export async function fetchExplorerSchemaFile(
  projectId: string,
  fileKey: string,
): Promise<string> {
  const { data } = await http.get<string>(explorerSchemaFileUrl(projectId, fileKey), {
    responseType: 'text',
  })
  return data
}

export async function listLaunchVehicles(): Promise<LaunchVehicleMeta[]> {
  const { data } = await http.get<LaunchVehicleMeta[]>('/api/launch-vehicles')
  return data
}

export async function runLaunchCompat(
  projectId: string,
  body: { vehicle_id: string; orbit: string; profile: Record<string, string | number> },
): Promise<LaunchCompatResult> {
  const { data } = await http.post<LaunchCompatResult>(
    `/api/projects/${projectId}/launch-compat`,
    body,
  )
  return data
}

export async function getLaunchReport(projectId: string): Promise<LaunchCompatResult> {
  const { data } = await http.get<LaunchCompatResult>(`/api/projects/${projectId}/launch-compat/report`)
  return data
}

export async function runLaunchTest(
  projectId: string,
  testId: string,
  body: { vehicle_id: string; orbit: string; profile: Record<string, string | number> },
): Promise<LaunchCompatCheck> {
  const { data } = await http.post<LaunchCompatCheck>(
    `/api/projects/${projectId}/launch-compat/tests/${testId}`,
    body,
  )
  return data
}

export async function getLaunchReadiness(projectId: string): Promise<Record<string, unknown> | null> {
  try {
    const { data } = await http.get<Record<string, unknown>>(
      `/api/projects/${projectId}/launch-readiness`,
    )
    return data
  } catch {
    return null
  }
}

export async function importLaunchReadiness(
  projectId: string,
  file: File,
): Promise<{ ok: boolean; check_readiness?: Record<string, unknown>; manifest: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post(`/api/projects/${projectId}/launch-readiness/import`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadLaunchLoads(
  projectId: string,
  kind: string,
  file: File,
): Promise<{ ok: boolean; kind: string; keys: string[] }> {
  const form = new FormData()
  form.append('kind', kind)
  form.append('file', file)
  const { data } = await http.post(`/api/projects/${projectId}/launch-loads`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
