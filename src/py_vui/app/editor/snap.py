from __future__ import annotations

GRID_SIZE = 8


def snap(value: float, *, grid: int = GRID_SIZE) -> float:
    return round(value / grid) * grid


def snap_size(value: float, *, min_size: float = GRID_SIZE, grid: int = GRID_SIZE) -> float:
    return max(min_size, snap(value, grid=grid))
