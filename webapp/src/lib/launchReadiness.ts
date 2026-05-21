import type { PartAnnotation } from '../api/types'
import type { LaunchVehicleMeta } from '../api/types'
import { PROFILE_FIELDS, type ProfileFieldDef, type SatelliteProfile } from './satelliteProfile'

export type LaunchOrbit = 'leo' | 'gto' | 'sso'

export type LaunchMissionConfig = {
  mission: SatelliteProfile
  components?: StructuralAnnotation[]
  launch_vehicle_preferences: {
    preferred_vehicle_id: string
    target_orbit: LaunchOrbit
  }
}

export type StructuralAnnotation = Pick<
  PartAnnotation,
  'mass_kg' | 'length_m' | 'width_m' | 'height_m' | 'material'
>

export function defaultLaunchMissionConfig(
  vehicleId = 'f9',
  orbit: LaunchOrbit = 'leo',
): LaunchMissionConfig {
  return {
    mission: {},
    launch_vehicle_preferences: {
      preferred_vehicle_id: vehicleId,
      target_orbit: orbit,
    },
  }
}

export function launchRunRequiredFields(): ProfileFieldDef[] {
  return PROFILE_FIELDS.filter(
    (f) => f.requiredFor.includes('launch') || f.requiredFor.includes('all'),
  )
}

function fieldPresent(profile: SatelliteProfile, key: string): boolean {
  const v = profile[key]
  if (v === undefined || v === null || v === '') return false
  if (key === 'interface_type') return String(v).trim().length > 0
  return !Number.isNaN(Number(v))
}

export function countStructuralAnnotations(annotations: StructuralAnnotation[]): number {
  return annotations.filter(
    (a) =>
      a.mass_kg != null &&
      !Number.isNaN(a.mass_kg) &&
      a.length_m != null &&
      a.width_m != null &&
      a.height_m != null &&
      a.material,
  ).length
}

export function validateLaunchInputs(
  mission: SatelliteProfile,
  annotations: StructuralAnnotation[],
): { ready: boolean; errors: string[] } {
  const errors: string[] = []

  for (const f of launchRunRequiredFields()) {
    if (!fieldPresent(mission, f.key)) {
      errors.push(
        `[AEGIS-LV] ERROR missing: ${f.label}${f.unit ? ` (${f.unit})` : ''}`,
      )
    }
  }

  if (!annotations.length) {
    errors.push('[AEGIS-LV] ERROR missing: part annotations (convert schematic or import mission JSON)')
  } else if (countStructuralAnnotations(annotations) < 2) {
    errors.push(
      '[AEGIS-LV] ERROR missing: ≥2 annotated parts with mass_kg, length_m, width_m, height_m, and material',
    )
  } else if (!annotations.some((a) => a.mass_kg != null && !Number.isNaN(a.mass_kg))) {
    errors.push('[AEGIS-LV] ERROR missing: mass_kg on at least one annotated part')
  }

  return { ready: errors.length === 0, errors }
}

export function applyVehicleToMissionConfig(
  config: LaunchMissionConfig,
  vehicle: LaunchVehicleMeta,
  orbit: LaunchOrbit,
): LaunchMissionConfig {
  const mission = { ...config.mission }
  if (!fieldPresent(mission, 'fairing_diameter_m')) {
    mission.fairing_diameter_m = vehicle.fairing_diameter_m
  }
  return {
    mission,
    components: config.components,
    launch_vehicle_preferences: {
      preferred_vehicle_id: vehicle.id,
      target_orbit: orbit,
    },
  }
}

export function configFromLaunchReadinessDoc(doc: {
  mission?: SatelliteProfile
  components?: StructuralAnnotation[]
  launch_vehicle_preferences?: { preferred_vehicle_id?: string; target_orbit?: string }
}): LaunchMissionConfig {
  const prefs = doc.launch_vehicle_preferences ?? {}
  const orbit = (prefs.target_orbit as LaunchOrbit) || 'leo'
  return {
    mission: { ...(doc.mission ?? {}) },
    components: Array.isArray(doc.components) ? doc.components : undefined,
    launch_vehicle_preferences: {
      preferred_vehicle_id: prefs.preferred_vehicle_id ?? 'f9',
      target_orbit: orbit === 'gto' || orbit === 'sso' ? orbit : 'leo',
    },
  }
}

export function missionConfigToJson(config: LaunchMissionConfig): string {
  return JSON.stringify(config, null, 2)
}

export function parseMissionConfigJson(text: string): LaunchMissionConfig {
  const raw = JSON.parse(text) as Record<string, unknown>
  if (raw.mission && typeof raw.mission === 'object') {
    return configFromLaunchReadinessDoc(
      raw as {
        mission: SatelliteProfile
        components?: StructuralAnnotation[]
        launch_vehicle_preferences?: LaunchMissionConfig['launch_vehicle_preferences']
      },
    )
  }
  return {
    mission: raw as SatelliteProfile,
    launch_vehicle_preferences: defaultLaunchMissionConfig().launch_vehicle_preferences,
  }
}
