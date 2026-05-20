"""Catalog of launch vehicles with fairing, performance, and load envelopes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchVehicle:
    id: str
    name: str
    provider: str
    leo_capacity_kg: float
    gto_capacity_kg: float
    sso_capacity_kg: float
    fairing_diameter_m: float
    fairing_height_m: float
    static_envelope_diameter_m: float
    dynamic_envelope_diameter_m: float
    max_axial_g: float
    max_lateral_g: float
    fairing_acoustic_db: float
    shock_peak_g: float
    isp_vac_s: float
    depressurization_max_pa_per_s: float
    vehicle_dry_mass_kg: float
    propellant_mass_kg: float


VEHICLES: dict[str, LaunchVehicle] = {
    "f9": LaunchVehicle(
        id="f9",
        name="Falcon 9",
        provider="SpaceX",
        leo_capacity_kg=22_800,
        gto_capacity_kg=8_300,
        sso_capacity_kg=15_600,
        fairing_diameter_m=5.2,
        fairing_height_m=13.1,
        static_envelope_diameter_m=4.6,
        dynamic_envelope_diameter_m=4.35,
        max_axial_g=6.0,
        max_lateral_g=0.8,
        fairing_acoustic_db=142.0,
        shock_peak_g=1200.0,
        isp_vac_s=348.0,
        depressurization_max_pa_per_s=850.0,
        vehicle_dry_mass_kg=22_200,
        propellant_mass_kg=395_700,
    ),
    "elec": LaunchVehicle(
        id="elec",
        name="Electron",
        provider="Rocket Lab",
        leo_capacity_kg=300,
        gto_capacity_kg=0,
        sso_capacity_kg=200,
        fairing_diameter_m=1.2,
        fairing_height_m=2.5,
        static_envelope_diameter_m=1.05,
        dynamic_envelope_diameter_m=0.98,
        max_axial_g=7.5,
        max_lateral_g=1.0,
        fairing_acoustic_db=138.0,
        shock_peak_g=900.0,
        isp_vac_s=318.0,
        depressurization_max_pa_per_s=1200.0,
        vehicle_dry_mass_kg=1_300,
        propellant_mass_kg=10_800,
    ),
    "starship": LaunchVehicle(
        id="starship",
        name="Starship",
        provider="SpaceX",
        leo_capacity_kg=100_000,
        gto_capacity_kg=21_000,
        sso_capacity_kg=45_000,
        fairing_diameter_m=9.0,
        fairing_height_m=18.0,
        static_envelope_diameter_m=8.0,
        dynamic_envelope_diameter_m=7.5,
        max_axial_g=5.0,
        max_lateral_g=0.6,
        fairing_acoustic_db=145.0,
        shock_peak_g=800.0,
        isp_vac_s=380.0,
        depressurization_max_pa_per_s=600.0,
        vehicle_dry_mass_kg=200_000,
        propellant_mass_kg=1_200_000,
    ),
    "vulcan": LaunchVehicle(
        id="vulcan",
        name="Vulcan",
        provider="ULA",
        leo_capacity_kg=27_200,
        gto_capacity_kg=14_400,
        sso_capacity_kg=18_000,
        fairing_diameter_m=5.4,
        fairing_height_m=15.2,
        static_envelope_diameter_m=4.8,
        dynamic_envelope_diameter_m=4.5,
        max_axial_g=6.5,
        max_lateral_g=0.9,
        fairing_acoustic_db=141.0,
        shock_peak_g=1100.0,
        isp_vac_s=362.0,
        depressurization_max_pa_per_s=780.0,
        vehicle_dry_mass_kg=35_000,
        propellant_mass_kg=450_000,
    ),
    "a6": LaunchVehicle(
        id="a6",
        name="Ariane 6",
        provider="Arianespace",
        leo_capacity_kg=21_650,
        gto_capacity_kg=10_350,
        sso_capacity_kg=14_500,
        fairing_diameter_m=5.4,
        fairing_height_m=14.0,
        static_envelope_diameter_m=4.7,
        dynamic_envelope_diameter_m=4.4,
        max_axial_g=6.2,
        max_lateral_g=0.85,
        fairing_acoustic_db=140.0,
        shock_peak_g=1050.0,
        isp_vac_s=355.0,
        depressurization_max_pa_per_s=820.0,
        vehicle_dry_mass_kg=32_000,
        propellant_mass_kg=420_000,
    ),
}


def orbit_capacity_kg(vehicle: LaunchVehicle, orbit: str) -> float:
    o = orbit.lower()
    if o == "gto":
        return vehicle.gto_capacity_kg
    if o == "sso":
        return vehicle.sso_capacity_kg
    return vehicle.leo_capacity_kg
