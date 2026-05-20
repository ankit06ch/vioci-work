export type ParseStatus = 'idle' | 'queued' | 'running' | 'done' | 'error'

export interface SchemaFolder {
  id: string
  name: string
  parent_id: string | null
  created_at: string
}

export interface ProjectMeta {
  id: string
  name: string
  folder_id?: string | null
  created_at: string
  parse_status: ParseStatus
  parse_error: string | null
  last_provider: string | null
  last_domain: string | null
  handdrawn: boolean
  has_diagram: boolean
  image_enhanced?: boolean
  image_quality_score?: number | null
}

export interface BBoxPx {
  x: number
  y: number
  w: number
  h: number
}

export type AnnotationVectorKind = 'line' | 'polyline' | 'rect' | 'arrow'

export interface AnnotationVector {
  id: string
  kind: AnnotationVectorKind
  points: [number, number][]
  auto: boolean
  label?: string | null
}

export interface PartAnnotation {
  id: string
  node_id: string | null
  name: string
  auto_detected: boolean
  bbox: BBoxPx | null
  vectors: AnnotationVector[]
  mass_kg: number | null
  length_m: number | null
  width_m: number | null
  height_m: number | null
  depth_m: number | null
  volume_m3: number | null
  material: string | null
  power_w: number | null
  notes: string | null
  extra: Record<string, unknown>
}

export interface AnnotationsDocument {
  annotations: PartAnnotation[]
  image_enhanced: boolean
  image_quality_score: number | null
}

export interface BBox {
  x: number
  y: number
  w: number
  h: number
}

export interface GeometryRef {
  bbox?: BBox | null
  polyline_px?: [number, number][] | null
  rotation_deg?: number
}

export interface DiagramNode {
  id: string
  kind: string
  label?: string | null
  properties: Record<string, unknown>
  geometry?: GeometryRef | null
  ports?: { id: string; position_px?: [number, number] }[]
}

export interface DiagramEdge {
  id: string
  source: string
  target: string
  kind?: string
  label?: string | null
}

export interface Quantity {
  value: number
  unit: string
  raw?: string | null
}

export interface DiagramParameter {
  id: string
  name: string
  default?: Quantity | null
  bounds?: [number, number] | null
  description?: string | null
  targets: string[]
}

export interface Diagram {
  id: string
  domain?: string | null
  nodes: DiagramNode[]
  edges: DiagramEdge[]
  parameters?: DiagramParameter[]
}

export interface WsEvent {
  type: string
  phase?: string
  message?: string
  progress?: number
}

export interface SimulateResult {
  engine: string
  success: boolean
  log: string
  artifacts: Record<string, string>
  metadata: Record<string, unknown>
  datasets: {
    id: string
    name?: string | null
    axes: string[]
    series: { name: string; values: number[] }[]
  }[]
}
