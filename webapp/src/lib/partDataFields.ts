import type { PartAnnotation } from '../api/types'

export type StandardFieldKey =
  | 'mass_kg'
  | 'length_m'
  | 'width_m'
  | 'height_m'
  | 'depth_m'
  | 'volume_m3'
  | 'power_w'
  | 'material'
  | 'notes'

export type FieldPreset = {
  key: StandardFieldKey
  label: string
  unit: string
  valueType: 'number' | 'text' | 'textarea'
}

/** Catalog of properties users can attach per part (not shown until added). */
export const FIELD_PRESETS: FieldPreset[] = [
  { key: 'mass_kg', label: 'Mass', unit: 'kg', valueType: 'number' },
  { key: 'length_m', label: 'Length', unit: 'm', valueType: 'number' },
  { key: 'width_m', label: 'Width', unit: 'm', valueType: 'number' },
  { key: 'height_m', label: 'Height', unit: 'm', valueType: 'number' },
  { key: 'depth_m', label: 'Depth', unit: 'm', valueType: 'number' },
  { key: 'volume_m3', label: 'Volume', unit: 'm³', valueType: 'number' },
  { key: 'power_w', label: 'Power', unit: 'W', valueType: 'number' },
  { key: 'material', label: 'Material', unit: '', valueType: 'text' },
  { key: 'notes', label: 'Notes', unit: '', valueType: 'textarea' },
]

export type CustomDataPoint = {
  id: string
  label: string
  value: string
  unit: string
}

const ATTACHED_KEY = '_attachedStandard'

export function presetForKey(key: StandardFieldKey): FieldPreset {
  return FIELD_PRESETS.find((p) => p.key === key)!
}

function fieldHasValue(part: PartAnnotation, key: StandardFieldKey): boolean {
  if (key === 'notes') return !!(part.notes && part.notes.trim())
  if (key === 'material') return !!(part.material && part.material.trim())
  const v = part[key]
  return typeof v === 'number' && !Number.isNaN(v)
}

/** Standard fields the user has attached (or that already have values). */
export function attachedStandardFields(part: PartAnnotation): StandardFieldKey[] {
  const stored = part.extra?.[ATTACHED_KEY]
  if (Array.isArray(stored)) {
    return stored.filter((k): k is StandardFieldKey =>
      FIELD_PRESETS.some((p) => p.key === k),
    )
  }
  return FIELD_PRESETS.filter((p) => fieldHasValue(part, p.key)).map((p) => p.key)
}

export function customDataPoints(part: PartAnnotation): CustomDataPoint[] {
  const raw = part.extra?.dataPoints
  if (!Array.isArray(raw)) return []
  return raw
    .filter(
      (row): row is CustomDataPoint =>
        row != null &&
        typeof row === 'object' &&
        typeof (row as CustomDataPoint).id === 'string',
    )
    .map((row) => ({
      id: row.id,
      label: String(row.label ?? ''),
      value: String(row.value ?? ''),
      unit: String(row.unit ?? ''),
    }))
}

export function availablePresetsToAttach(part: PartAnnotation): FieldPreset[] {
  const attached = new Set(attachedStandardFields(part))
  return FIELD_PRESETS.filter((p) => !attached.has(p.key))
}

export function withAttachedField(
  part: PartAnnotation,
  key: StandardFieldKey,
): Record<string, unknown> {
  const attached = new Set(attachedStandardFields(part))
  attached.add(key)
  return { ...part.extra, [ATTACHED_KEY]: [...attached] }
}

export function withoutAttachedField(
  part: PartAnnotation,
  key: StandardFieldKey,
): Record<string, unknown> {
  const attached = attachedStandardFields(part).filter((k) => k !== key)
  return { ...part.extra, [ATTACHED_KEY]: attached }
}

export function readStandardFieldValue(part: PartAnnotation, key: StandardFieldKey): string {
  if (key === 'notes') return part.notes ?? ''
  if (key === 'material') return part.material ?? ''
  const v = part[key]
  return v == null || Number.isNaN(v as number) ? '' : String(v)
}

export function patchStandardField(
  key: StandardFieldKey,
  raw: string,
): Partial<PartAnnotation> {
  if (key === 'notes') return { notes: raw.trim() || null }
  if (key === 'material') return { material: raw.trim() || null }
  const n = raw.trim() === '' ? null : Number(raw)
  return { [key]: n == null || Number.isNaN(n) ? null : n } as Partial<PartAnnotation>
}

export function clearStandardField(key: StandardFieldKey): Partial<PartAnnotation> {
  return patchStandardField(key, '')
}

export function newDataPointId(): string {
  return crypto.randomUUID?.() ?? `dp-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/** Back-compat catalog for code that lists numeric / material part properties. */
export const ANNOTATION_FIELDS = FIELD_PRESETS.filter((p) => p.key !== 'notes')
