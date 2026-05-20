/** Schema registry artifacts shown under each schematic in the explorer. */

export type ExplorerSchemaFileId = 'components' | 'dependencies' | 'properties' | 'manifest'

export const SCHEMA_EXPORT_FILES: {
  id: ExplorerSchemaFileId
  label: string
  icon: string
}[] = [
  { id: 'components', label: 'components.csv', icon: '📊' },
  { id: 'dependencies', label: 'dependencies.csv', icon: '🔗' },
  { id: 'properties', label: 'properties.csv', icon: '📋' },
  { id: 'manifest', label: 'satellite_schema.json', icon: '📁' },
]
