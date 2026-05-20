"""Backward-compatible re-exports."""

from schemagraph.launch_compat.vehicles.loader import (
    VehicleBundle as LaunchVehicle,
    VehicleBundle,
    get_vehicle,
    list_launch_vehicles,
    orbit_capacity_kg,
)

__all__ = ["LaunchVehicle", "VehicleBundle", "get_vehicle", "list_launch_vehicles", "orbit_capacity_kg", "VEHICLES"]


def __getattr__(name: str):
    if name == "VEHICLES":
        ids = ["f9", "elec", "starship", "vulcan", "a6"]
        return {i: get_vehicle(i) for i in ids}
    raise AttributeError(name)
