import type { LaunchVehicleMeta } from '../api/types'

/** Bundled LV catalog — matches schemagraph/launch_compat/vehicles/*.json */
export const BUNDLED_LAUNCH_VEHICLES: LaunchVehicleMeta[] = [
  {
    id: 'f9',
    name: 'Falcon 9',
    provider: 'SpaceX',
    leo_capacity_kg: 22800,
    gto_capacity_kg: 8300,
    fairing_diameter_m: 5.2,
  },
  {
    id: 'elec',
    name: 'Electron',
    provider: 'Rocket Lab',
    leo_capacity_kg: 300,
    gto_capacity_kg: 0,
    fairing_diameter_m: 1.2,
  },
  {
    id: 'vulcan',
    name: 'Vulcan',
    provider: 'ULA',
    leo_capacity_kg: 27200,
    gto_capacity_kg: 14400,
    fairing_diameter_m: 5.4,
  },
  {
    id: 'a6',
    name: 'Ariane 6',
    provider: 'Arianespace',
    leo_capacity_kg: 21650,
    gto_capacity_kg: 10350,
    fairing_diameter_m: 5.4,
  },
  {
    id: 'starship',
    name: 'Starship',
    provider: 'SpaceX',
    leo_capacity_kg: 100000,
    gto_capacity_kg: 21000,
    fairing_diameter_m: 9.0,
  },
]
