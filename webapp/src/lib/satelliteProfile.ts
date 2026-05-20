import type { Subsystem } from './subsystems'

export type ProfileFieldKey =
  | 'mass_kg'
  | 'orbit_altitude_km'
  | 'orbit_inclination_deg'
  | 'power_budget_w'
  | 'fairing_diameter_m'
  | 'deployable_span_m'
  | 'design_life_years'
  | 'cg_x_mm'
  | 'cg_y_mm'
  | 'cg_z_mm'
  | 'moi_ixx_kgm2'
  | 'moi_iyy_kgm2'
  | 'moi_izz_kgm2'
  | 'interface_type'
  | 'primary_lateral_hz'
  | 'primary_axial_hz'
  | 'vent_area_m2'
  | 'sealed_volume_m3'

export type ProfileFieldDef = {
  key: ProfileFieldKey
  label: string
  unit?: string
  subsystemHint?: Subsystem
  requiredFor: ('launch' | 'simulate' | 'all')[]
}

export const PROFILE_FIELDS: ProfileFieldDef[] = [
  {
    key: 'mass_kg',
    label: 'Total spacecraft mass',
    unit: 'kg',
    subsystemHint: 'Structure',
    requiredFor: ['launch', 'simulate', 'all'],
  },
  {
    key: 'orbit_altitude_km',
    label: 'Orbit altitude',
    unit: 'km',
    requiredFor: ['simulate', 'all'],
  },
  {
    key: 'orbit_inclination_deg',
    label: 'Orbit inclination',
    unit: '°',
    requiredFor: ['simulate'],
  },
  {
    key: 'power_budget_w',
    label: 'Power budget',
    unit: 'W',
    subsystemHint: 'Solar arrays',
    requiredFor: ['simulate', 'all'],
  },
  {
    key: 'fairing_diameter_m',
    label: 'Fairing diameter',
    unit: 'm',
    requiredFor: ['launch'],
  },
  {
    key: 'deployable_span_m',
    label: 'Max deployable span',
    unit: 'm',
    subsystemHint: 'Structure',
    requiredFor: ['launch'],
  },
  {
    key: 'design_life_years',
    label: 'Design life',
    unit: 'yr',
    requiredFor: ['all'],
  },
  {
    key: 'cg_x_mm',
    label: 'CG lateral X (above interface)',
    unit: 'mm',
    subsystemHint: 'Structure',
    requiredFor: ['launch'],
  },
  {
    key: 'cg_y_mm',
    label: 'CG lateral Y',
    unit: 'mm',
    requiredFor: ['launch'],
  },
  {
    key: 'cg_z_mm',
    label: 'CG height above SIP',
    unit: 'mm',
    requiredFor: ['launch'],
  },
  {
    key: 'moi_ixx_kgm2',
    label: 'MOI Ixx (measured)',
    unit: 'kg·m²',
    requiredFor: ['launch'],
  },
  {
    key: 'moi_iyy_kgm2',
    label: 'MOI Iyy',
    unit: 'kg·m²',
    requiredFor: ['launch'],
  },
  {
    key: 'moi_izz_kgm2',
    label: 'MOI Izz',
    unit: 'kg·m²',
    requiredFor: ['launch'],
  },
  {
    key: 'interface_type',
    label: 'LV interface (PAF type)',
    requiredFor: ['launch'],
  },
  {
    key: 'primary_lateral_hz',
    label: 'Primary lateral mode',
    unit: 'Hz',
    requiredFor: ['launch'],
  },
  {
    key: 'primary_axial_hz',
    label: 'Primary axial mode',
    unit: 'Hz',
    requiredFor: ['launch'],
  },
  {
    key: 'vent_area_m2',
    label: 'Vent orifice area',
    unit: 'm²',
    requiredFor: ['launch'],
  },
  {
    key: 'sealed_volume_m3',
    label: 'Sealed cavity volume',
    unit: 'm³',
    requiredFor: ['launch'],
  },
]

export type SatelliteProfile = Record<string, string | number>

export type PendingQuestion = {
  id: string
  field: ProfileFieldKey
  question: string
  reason: string
}

export function missingFields(
  profile: SatelliteProfile,
  intent: 'launch' | 'simulate',
): ProfileFieldDef[] {
  return PROFILE_FIELDS.filter((f) => {
    if (!f.requiredFor.includes(intent) && !f.requiredFor.includes('all')) return false
    const v = profile[f.key]
    return v === undefined || v === '' || Number.isNaN(Number(v))
  })
}

export function buildFollowUpQuestions(
  missing: ProfileFieldDef[],
  reason: string,
): PendingQuestion[] {
  return missing.map((f, i) => ({
    id: `q-${f.key}-${i}`,
    field: f.key,
    question: `Please provide ${f.label}${f.unit ? ` (${f.unit})` : ''} for accurate ${reason}.`,
    reason,
  }))
}
