"""CleanMap v1 post-processing helpers for saved FAST-LIO sessions."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import shutil
import struct
from typing import Iterable


ACCUMULATED_MAP_SUFFIX = "_accumulated_map.pcd"
GLOBAL_OPTIMIZED_MAP_SUFFIX = "_global_optimized_map.pcd"
LEGACY_BACKEND_MAP_SUFFIX = "_map.pcd"
LEGACY_FRONTEND_MAP_SUFFIX = "_frontend.pcd"

CLEAN_MAP_PRESETS = {
    "light": {
        "label": "轻量预览",
        "voxel_size": 0.08,
        "radius": 0.25,
        "min_neighbors": 1,
    },
    "default": {
        "label": "默认清理",
        "voxel_size": 0.05,
        "radius": 0.20,
        "min_neighbors": 1,
    },
    "detail": {
        "label": "保细节",
        "voxel_size": 0.03,
        "radius": 0.15,
        "min_neighbors": 1,
    },
}


@dataclass(frozen=True)
class CleanMapConfig:
    enabled: bool
    voxel_size: float
    min_neighbors: int
    radius: float
    min_z: float
    max_z: float
    min_retention_ratio: float
    min_output_points: int
    preset: str = "default"

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return {
            "enabled": self.enabled,
            "voxel_size": self.voxel_size,
            "min_neighbors": self.min_neighbors,
            "radius": self.radius,
            "min_z": self.min_z if math.isfinite(self.min_z) else None,
            "max_z": self.max_z if math.isfinite(self.max_z) else None,
            "min_retention_ratio": self.min_retention_ratio,
            "min_output_points": self.min_output_points,
            "preset": self.preset,
        }


def clean_map_config_for_preset(base: CleanMapConfig, preset: str) -> CleanMapConfig:
    normalized = preset if preset in CLEAN_MAP_PRESETS else base.preset or "default"
    values = CLEAN_MAP_PRESETS.get(normalized)
    if values is None:
        return base
    return CleanMapConfig(
        enabled=base.enabled,
        voxel_size=float(values["voxel_size"]),
        min_neighbors=int(values["min_neighbors"]),
        radius=float(values["radius"]),
        min_z=base.min_z,
        max_z=base.max_z,
        min_retention_ratio=base.min_retention_ratio,
        min_output_points=base.min_output_points,
        preset=normalized,
    )


@dataclass(frozen=True)
class CleanMapResult:
    success: bool
    message: str
    input_points: int = 0
    output_points: int = 0
    output_map_path: Path | None = None

    @property
    def retention_ratio(self) -> float:
        if self.input_points <= 0:
            return 0.0
        return self.output_points / self.input_points


@dataclass(frozen=True)
class PointRecord:
    x: float
    y: float
    z: float
    intensity: float


def copy_accumulated_map_compat(session_map_path: Path, accumulated_map_path: Path, legacy_map_path: Path) -> None:
    if session_map_path.is_file() and accumulated_map_path != session_map_path:
        shutil.copy2(session_map_path, accumulated_map_path)
    if accumulated_map_path.is_file() and legacy_map_path != accumulated_map_path:
        shutil.copy2(accumulated_map_path, legacy_map_path)


def run_clean_map(
    *,
    input_map_path: Path,
    output_map_path: Path,
    config: CleanMapConfig,
) -> CleanMapResult:
    if not config.enabled:
        return CleanMapResult(False, "CleanMap post-processing disabled")
    if not input_map_path.is_file():
        return CleanMapResult(False, f"Input map not found: {input_map_path}")

    try:
        points = read_pcd_xyzi(input_map_path)
    except (OSError, ValueError, struct.error) as exc:
        return CleanMapResult(False, f"Failed to read input map: {exc}")

    input_count = len(points)
    if input_count <= 0:
        return CleanMapResult(False, "Input map has no finite XYZ points")

    cleaned = filter_by_height(points, config.min_z, config.max_z)
    cleaned = voxel_downsample(cleaned, max(0.0, config.voxel_size))
    cleaned = radius_outlier_filter(cleaned, max(0.0, config.radius), max(0, config.min_neighbors))
    output_count = len(cleaned)
    if output_count <= 0:
        return CleanMapResult(False, "CleanMap removed all points", input_count, output_count)

    retention = output_count / input_count
    min_retention = max(0.0, min(1.0, config.min_retention_ratio))
    min_output_points = max(0, config.min_output_points)
    if retention < min_retention and output_count < min_output_points:
        return CleanMapResult(
            False,
            (
                f"CleanMap output too small: retention {retention:.3f} < {min_retention:.3f} "
                f"and points {output_count} < {min_output_points}"
            ),
            input_count,
            output_count,
        )

    try:
        write_ascii_pcd_xyzi(output_map_path, cleaned)
    except OSError as exc:
        return CleanMapResult(False, f"Failed to write post-processed map: {exc}", input_count, output_count)

    return CleanMapResult(
        True,
        f"CleanMap generated post-processed map ({input_count} -> {output_count} points)",
        input_count,
        output_count,
        output_map_path,
    )


def filter_by_height(points: Iterable[PointRecord], min_z: float, max_z: float) -> list[PointRecord]:
    use_min = math.isfinite(min_z)
    use_max = math.isfinite(max_z)
    if not use_min and not use_max:
        return list(points)
    filtered = []
    for point in points:
        if use_min and point.z < min_z:
            continue
        if use_max and point.z > max_z:
            continue
        filtered.append(point)
    return filtered


def voxel_downsample(points: Iterable[PointRecord], voxel_size: float) -> list[PointRecord]:
    source = list(points)
    if voxel_size <= 0.0 or len(source) <= 1:
        return source
    voxels: dict[tuple[int, int, int], list[float]] = {}
    counts: dict[tuple[int, int, int], int] = {}
    inv = 1.0 / voxel_size
    for point in source:
        key = (
            math.floor(point.x * inv),
            math.floor(point.y * inv),
            math.floor(point.z * inv),
        )
        accum = voxels.get(key)
        if accum is None:
            voxels[key] = [point.x, point.y, point.z, point.intensity]
            counts[key] = 1
            continue
        accum[0] += point.x
        accum[1] += point.y
        accum[2] += point.z
        accum[3] += point.intensity
        counts[key] += 1
    return [
        PointRecord(accum[0] / count, accum[1] / count, accum[2] / count, accum[3] / count)
        for key, accum in voxels.items()
        for count in (counts[key],)
    ]


def radius_outlier_filter(points: Iterable[PointRecord], radius: float, min_neighbors: int) -> list[PointRecord]:
    source = list(points)
    if radius <= 0.0 or min_neighbors <= 0 or len(source) <= min_neighbors:
        return source
    inv = 1.0 / radius
    buckets: dict[tuple[int, int, int], list[int]] = {}
    for index, point in enumerate(source):
        key = (
            math.floor(point.x * inv),
            math.floor(point.y * inv),
            math.floor(point.z * inv),
        )
        buckets.setdefault(key, []).append(index)

    radius_sq = radius * radius
    kept: list[PointRecord] = []
    for point in source:
        cx = math.floor(point.x * inv)
        cy = math.floor(point.y * inv)
        cz = math.floor(point.z * inv)
        neighbors = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other_index in buckets.get((cx + dx, cy + dy, cz + dz), ()):
                        other = source[other_index]
                        dist_sq = (
                            (point.x - other.x) * (point.x - other.x)
                            + (point.y - other.y) * (point.y - other.y)
                            + (point.z - other.z) * (point.z - other.z)
                        )
                        if dist_sq <= radius_sq:
                            neighbors += 1
                            if neighbors > min_neighbors:
                                kept.append(point)
                                break
                    if neighbors > min_neighbors:
                        break
                if neighbors > min_neighbors:
                    break
            if neighbors > min_neighbors:
                break
    return kept


def read_pcd_xyzi(path: Path) -> list[PointRecord]:
    data = path.read_bytes()
    header_end = data.find(b"DATA ")
    if header_end < 0:
        raise ValueError("PCD header is missing DATA line")
    line_end = data.find(b"\n", header_end)
    if line_end < 0:
        raise ValueError("PCD DATA line is not terminated")
    header = data[: line_end + 1].decode("utf-8", "replace").splitlines()
    body = data[line_end + 1 :]
    meta = _parse_pcd_header(header)
    fields = meta.get("FIELDS", [])
    if not all(name in fields for name in ("x", "y", "z")):
        raise ValueError(f"PCD is missing XYZ fields: {fields}")
    data_format = (meta.get("DATA") or ["ascii"])[0]
    if data_format == "ascii":
        return _read_ascii_points(body, fields)
    if data_format == "binary":
        return _read_binary_points(body, meta)
    raise ValueError(f"Unsupported PCD DATA format: {data_format}")


def write_ascii_pcd_xyzi(path: Path, points: list[PointRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        output.write("# .PCD v0.7 - Point Cloud Data file format\n")
        output.write("VERSION 0.7\n")
        output.write("FIELDS x y z intensity\n")
        output.write("SIZE 4 4 4 4\n")
        output.write("TYPE F F F F\n")
        output.write("COUNT 1 1 1 1\n")
        output.write(f"WIDTH {len(points)}\n")
        output.write("HEIGHT 1\n")
        output.write("VIEWPOINT 0 0 0 1 0 0 0\n")
        output.write(f"POINTS {len(points)}\n")
        output.write("DATA ascii\n")
        for point in points:
            output.write(f"{point.x:.6f} {point.y:.6f} {point.z:.6f} {point.intensity:.6f}\n")


def _parse_pcd_header(lines: list[str]) -> dict[str, list[str]]:
    meta: dict[str, list[str]] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        meta[parts[0]] = parts[1:]
    return meta


def _read_ascii_points(body: bytes, fields: list[str]) -> list[PointRecord]:
    xi = fields.index("x")
    yi = fields.index("y")
    zi = fields.index("z")
    ii = fields.index("intensity") if "intensity" in fields else -1
    points: list[PointRecord] = []
    for line in body.decode("utf-8", "replace").splitlines():
        values = line.split()
        if len(values) <= max(xi, yi, zi):
            continue
        try:
            x = float(values[xi])
            y = float(values[yi])
            z = float(values[zi])
            intensity = float(values[ii]) if ii >= 0 and len(values) > ii else 0.0
        except ValueError:
            continue
        if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
            points.append(PointRecord(x, y, z, intensity if math.isfinite(intensity) else 0.0))
    return points


def _read_binary_points(body: bytes, meta: dict[str, list[str]]) -> list[PointRecord]:
    fields = meta.get("FIELDS", [])
    sizes = [int(value) for value in meta.get("SIZE", [])]
    types = meta.get("TYPE", [])
    counts = [int(value) for value in meta.get("COUNT", ["1"] * len(fields))]
    if not (len(fields) == len(sizes) == len(types) == len(counts)):
        raise ValueError("PCD binary field metadata is inconsistent")
    offsets: dict[str, tuple[int, int, str]] = {}
    point_step = 0
    for field, size, field_type, count in zip(fields, sizes, types, counts):
        offsets[field] = (point_step, size, field_type)
        point_step += size * count
    if point_step <= 0:
        raise ValueError("PCD binary point step is invalid")
    declared_points = int((meta.get("POINTS") or [len(body) // point_step])[0])
    point_count = min(declared_points, len(body) // point_step)
    points: list[PointRecord] = []
    for index in range(point_count):
        base = index * point_step
        x = _unpack_pcd_scalar(body, base, offsets["x"])
        y = _unpack_pcd_scalar(body, base, offsets["y"])
        z = _unpack_pcd_scalar(body, base, offsets["z"])
        intensity = _unpack_pcd_scalar(body, base, offsets["intensity"]) if "intensity" in offsets else 0.0
        if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
            points.append(PointRecord(x, y, z, intensity if math.isfinite(intensity) else 0.0))
    return points


def _unpack_pcd_scalar(body: bytes, base: int, descriptor: tuple[int, int, str]) -> float:
    offset, size, field_type = descriptor
    if field_type == "F" and size == 4:
        return struct.unpack_from("<f", body, base + offset)[0]
    if field_type == "F" and size == 8:
        return float(struct.unpack_from("<d", body, base + offset)[0])
    if field_type == "U" and size == 1:
        return float(struct.unpack_from("<B", body, base + offset)[0])
    if field_type == "U" and size == 2:
        return float(struct.unpack_from("<H", body, base + offset)[0])
    if field_type == "U" and size == 4:
        return float(struct.unpack_from("<I", body, base + offset)[0])
    if field_type == "I" and size == 1:
        return float(struct.unpack_from("<b", body, base + offset)[0])
    if field_type == "I" and size == 2:
        return float(struct.unpack_from("<h", body, base + offset)[0])
    if field_type == "I" and size == 4:
        return float(struct.unpack_from("<i", body, base + offset)[0])
    raise ValueError(f"Unsupported PCD scalar field: TYPE={field_type} SIZE={size}")
