import type { Subsystem } from './subsystems'

export type ProfileFieldKey =
  | 'mass_kg'
  | 'orbit_altitude_km'
  | 'orbit_inclination_deg'
  | 'power_budget_w'
  | 'fairing_diameter_m'
  | 'deployable_span_m'
  | 'design_life_years'

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
