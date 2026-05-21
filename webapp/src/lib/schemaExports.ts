/** Schema registry artifacts shown under each schematic in the explorer. */

export type ExplorerSchemaFileId =
  | 'components'
  | 'dependencies'
  | 'properties'
  | 'manifest'
  | 'launch_schema'
  | 'launch_readiness'
  | 'launch_mission'
  | 'launch_components'
  | 'launch_check_catalog'

export const SCHEMA_EXPORT_FILES: {
  id: ExplorerSchemaFileId
  label: string
  icon: string
}[] = [
  { id: 'components', label: 'components.csv', icon: '📊' },
  { id: 'dependencies', label: 'dependencies.csv', icon: '🔗' },
  { id: 'properties', label: 'properties.csv', icon: '📋' },
  { id: 'manifest', label: 'satellite_schema.json', icon: '📁' },
  { id: 'launch_schema', label: 'satellite_launch_schema.json', icon: '📐' },
  { id: 'launch_readiness', label: 'launch_readiness.json', icon: '🛰' },
  { id: 'launch_mission', label: 'launch_mission.csv', icon: '◎' },
  { id: 'launch_components', label: 'launch_components.csv', icon: '▣' },
  { id: 'launch_check_catalog', label: 'launch_check_catalog.csv', icon: '✓' },
]

export const EXPLORER_JSON_FILE_IDS = new Set<ExplorerSchemaFileId>([
  'manifest',
  'launch_schema',
  'launch_readiness',
])

export const EXPLORER_CSV_FILE_IDS = new Set<ExplorerSchemaFileId>([
  'components',
  'dependencies',
  'properties',
  'launch_mission',
  'launch_components',
  'launch_check_catalog',
])
