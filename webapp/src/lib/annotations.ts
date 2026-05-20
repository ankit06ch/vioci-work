import type { PartAnnotation } from '../api/types'

export { ANNOTATION_FIELDS } from './partDataFields'

export function totalMassKg(annotations: PartAnnotation[]): number | null {
  const vals = annotations
    .map((a) => a.mass_kg)
    .filter((v): v is number => v != null && !Number.isNaN(v))
  if (!vals.length) return null
  return vals.reduce((s, v) => s + v, 0)
}

export function annotationsMissingMass(annotations: PartAnnotation[]): PartAnnotation[] {
  return annotations.filter((a) => a.mass_kg == null || Number.isNaN(a.mass_kg))
}

export function missionReadinessHint(annotations: PartAnnotation[]): string | null {
  if (!annotations.length) {
    return 'Add part annotations (auto-generated after convert) and enter mass/size for each component.'
  }
  const missing = annotationsMissingMass(annotations)
  if (missing.length === annotations.length) {
    return 'Enter mass (kg) for at least one annotated part.'
  }
  if (missing.length) {
    return `${missing.length} part(s) still need mass values.`
  }
  const total = totalMassKg(annotations)
  if (total != null) {
    return `Total annotated mass: ${total.toFixed(2)} kg`
  }
  return null
}
