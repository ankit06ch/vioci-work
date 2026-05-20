"""Physics test plugin registry."""

from __future__ import annotations

from typing import Callable

from schemagraph.launch_compat.models import LaunchContext, PhysicsTestResult, SpacecraftModel
from schemagraph.launch_compat.vehicles.loader import VehicleBundle

TestFn = Callable[[LaunchContext, SpacecraftModel, VehicleBundle], PhysicsTestResult]

_REGISTRY: dict[str, TestFn] = {}


def register(test_id: str):
    def deco(fn: TestFn):
        _REGISTRY[test_id] = fn
        return fn
    return deco


def get_test(test_id: str) -> TestFn:
    if test_id not in _REGISTRY:
        raise KeyError(f"unknown physics test: {test_id}")
    return _REGISTRY[test_id]


def list_tests() -> list[str]:
    return sorted(_REGISTRY.keys())


def run_test(
    test_id: str,
    ctx: LaunchContext,
    spacecraft: SpacecraftModel,
    vehicle: VehicleBundle,
) -> PhysicsTestResult:
    return get_test(test_id)(ctx, spacecraft, vehicle)


def run_all(
    ctx: LaunchContext,
    spacecraft: SpacecraftModel,
    vehicle: VehicleBundle,
    test_ids: list[str] | None = None,
) -> list[PhysicsTestResult]:
    ids = test_ids or list_tests()
    return [run_test(tid, ctx, spacecraft, vehicle) for tid in ids]
