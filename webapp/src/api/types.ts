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
  has_schema_registry?: boolean
  image_enhanced?: boolean
  image_quality_score?: number | null
}

export interface BBoxPx {
  x: number
  y: number
  w: number
  h: number
}

export type AnnotationVectorKind = 'line' | 'polyline' | 'rect' | 'arrow' | 'polygon'

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

export interface SchemaRegistryMeta {
  updated_at: string
  parse_status: string
  last_domain: string | null
  node_count: number
  edge_count: number
  part_count: number
  project_name: string
}

export interface SchemaRegistryTable {
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface SchemaRegistryDocument {
  version: number
  project_id: string
  project_name: string
  updated_at: string
  parse_status: string
  last_domain: string | null
  node_count: number
  edge_count: number
  part_count: number
  tables: Record<string, SchemaRegistryTable>
  files: Record<string, string>
}

export interface SchemaRegistrySqlResult {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  mutated: boolean
  message?: string | null
}

export interface SchemaRegistryQuery {
  table: string
  columns: string[]
  rows: Record<string, unknown>[]
  total: number
  filtered: number
  truncated: boolean
  meta?: SchemaRegistryMeta | null
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

export interface LaunchVehicleMeta {
  id: string
  name: string
  provider: string
  leo_capacity_kg: number
  gto_capacity_kg: number
  fairing_diameter_m: number
}

export interface LaunchCompatCheck {
  id: string
  category: string
  title: string
  status: 'pass' | 'warn' | 'fail'
  value: string
  limit: string
  detail: string
}

export interface LaunchStressHotspot {
  col: number
  row: number
  x: number
  y: number
  stress_mpa: number
  power_w: number
  stress_norm: number
  power_norm: number
}

export interface LaunchCompatResult {
  vehicle_id: string
  vehicle_name: string
  orbit: string
  overall_score: number
  overall_status: 'nominal' | 'review' | 'caution' | 'fail'
  payload_mass_kg: number
  mass_source: string
  capacity_kg: number
  mass_margin_pct: number
  mass_properties: Record<string, number>
  category_scores: Record<string, number>
  checks: LaunchCompatCheck[]
  warnings: { level: string; text: string; check_id: string }[]
  stress_field: {
    cols: number
    rows: number
    stress_mpa: number[][]
    power_w: number[][]
    max_stress_mpa: number
    max_power_w: number
    cg: { x: number; y: number }
    first_bending_hz: number
    hotspots: LaunchStressHotspot[]
    power_hotspots: LaunchStressHotspot[]
  }
  simulation: { engine: string; fea_mode: string; notes: string }
}
