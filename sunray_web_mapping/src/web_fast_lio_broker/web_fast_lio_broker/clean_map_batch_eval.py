#!/usr/bin/env python3
"""Batch evaluation for CleanMap v1 presets over saved map sessions."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import time

from web_fast_lio_broker.clean_map_postprocess import (
    ACCUMULATED_MAP_SUFFIX,
    CLEAN_MAP_PRESETS,
    LEGACY_BACKEND_MAP_SUFFIX,
    CleanMapConfig,
    clean_map_config_for_preset,
    run_clean_map,
)


REPORT_JSON = "summary.json"
REPORT_CSV = "summary.csv"
REPORT_MARKDOWN = "summary.md"


@dataclass(frozen=True)
class BatchEvalRow:
    session: str
    preset: str
    state: str
    message: str
    input_points: int
    output_points: int
    retention_ratio: float
    input_size_bytes: int
    output_size_bytes: int
    duration_sec: float
    output_map_path: str
    voxel_size: float
    radius: float
    min_neighbors: int
    min_retention_ratio: float
    min_output_points: int


def default_clean_map_config() -> CleanMapConfig:
    return CleanMapConfig(
        enabled=True,
        voxel_size=0.05,
        min_neighbors=1,
        radius=0.20,
        min_z=float("-inf"),
        max_z=float("inf"),
        min_retention_ratio=0.05,
        min_output_points=20000,
        preset="default",
    )


def discover_session_maps(maps_root: Path) -> list[tuple[str, Path]]:
    sessions: list[tuple[str, Path]] = []
    if not maps_root.is_dir():
        return sessions
    for directory in sorted((path for path in maps_root.iterdir() if path.is_dir()), key=lambda path: path.name):
        session = directory.name
        accumulated = directory / f"{session}{ACCUMULATED_MAP_SUFFIX}"
        if accumulated.is_file():
            sessions.append((session, accumulated))
            continue
        legacy = directory / f"{session}{LEGACY_BACKEND_MAP_SUFFIX}"
        if legacy.is_file():
            sessions.append((session, legacy))
    return sessions


def run_batch_eval(
    *,
    maps_root: Path,
    output_root: Path,
    presets: list[str],
    base_config: CleanMapConfig,
    limit: int = 0,
) -> list[BatchEvalRow]:
    sessions = discover_session_maps(maps_root)
    if limit > 0:
        sessions = sessions[:limit]
    rows: list[BatchEvalRow] = []
    output_root.mkdir(parents=True, exist_ok=True)
    for session, input_map in sessions:
        input_size = _file_size(input_map)
        for preset in presets:
            config = clean_map_config_for_preset(base_config, preset)
            preset_dir = output_root / session / config.preset
            output_map = preset_dir / f"{session}_{config.preset}_clean_map.pcd"
            started = time.monotonic()
            result = run_clean_map(input_map_path=input_map, output_map_path=output_map, config=config)
            duration = time.monotonic() - started
            output_size = _file_size(output_map) if result.success else 0
            row = BatchEvalRow(
                session=session,
                preset=config.preset,
                state="completed" if result.success else "failed",
                message=result.message,
                input_points=result.input_points,
                output_points=result.output_points,
                retention_ratio=round(result.retention_ratio, 6),
                input_size_bytes=input_size,
                output_size_bytes=output_size,
                duration_sec=round(duration, 3),
                output_map_path=str(output_map) if result.success else "",
                voxel_size=config.voxel_size,
                radius=config.radius,
                min_neighbors=config.min_neighbors,
                min_retention_ratio=config.min_retention_ratio,
                min_output_points=config.min_output_points,
            )
            rows.append(row)
            _write_preset_metadata(preset_dir / "postprocess_eval.json", row, input_map, config)
    write_reports(output_root, rows)
    return rows


def write_reports(output_root: Path, rows: list[BatchEvalRow]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    write_json_report(output_root / REPORT_JSON, rows)
    write_csv_report(output_root / REPORT_CSV, rows)
    write_markdown_report(output_root / REPORT_MARKDOWN, rows)


def write_json_report(path: Path, rows: list[BatchEvalRow]) -> None:
    payload = {
        "algorithm": "clean_map_v1",
        "generated_at": round(time.time(), 3),
        "rows": [asdict(row) for row in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv_report(path: Path, rows: list[BatchEvalRow]) -> None:
    fieldnames = list(BatchEvalRow.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_markdown_report(path: Path, rows: list[BatchEvalRow]) -> None:
    lines = [
        "# CleanMap v1 批量评估",
        "",
        "| session | preset | state | input | output | retention | size | duration |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.session,
                    row.preset,
                    row.state,
                    str(row.input_points),
                    str(row.output_points),
                    f"{row.retention_ratio * 100:.1f}%",
                    _format_bytes(row.output_size_bytes),
                    f"{row.duration_sec:.3f}s",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.extend(_recommendation_lines(rows))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-evaluate CleanMap v1 presets over saved map sessions.")
    parser.add_argument("--maps-root", type=Path, default=Path("maps"), help="Directory containing saved map sessions.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("postprocess_eval"),
        help="Directory for generated evaluation maps and reports.",
    )
    parser.add_argument(
        "--presets",
        default="light,default,detail",
        help="Comma-separated CleanMap presets to evaluate.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of sessions for a quick trial.")
    parser.add_argument("--min-retention-ratio", type=float, default=0.05)
    parser.add_argument("--min-output-points", type=int, default=20000)
    parser.add_argument("--min-z", type=float, default=float("-inf"))
    parser.add_argument("--max-z", type=float, default=float("inf"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    presets = _parse_presets(args.presets)
    base = default_clean_map_config()
    base = CleanMapConfig(
        enabled=True,
        voxel_size=base.voxel_size,
        min_neighbors=base.min_neighbors,
        radius=base.radius,
        min_z=args.min_z,
        max_z=args.max_z,
        min_retention_ratio=args.min_retention_ratio,
        min_output_points=args.min_output_points,
        preset=base.preset,
    )
    rows = run_batch_eval(
        maps_root=args.maps_root,
        output_root=args.output_root,
        presets=presets,
        base_config=base,
        limit=max(0, args.limit),
    )
    print(f"CleanMap batch eval: {len(rows)} runs, reports written to {args.output_root}")


def _parse_presets(value: str) -> list[str]:
    presets = []
    for item in value.split(","):
        preset = item.strip()
        if not preset:
            continue
        if preset not in CLEAN_MAP_PRESETS:
            raise SystemExit(f"Unknown CleanMap preset: {preset}")
        presets.append(preset)
    if not presets:
        raise SystemExit("No CleanMap presets selected")
    return presets


def _write_preset_metadata(path: Path, row: BatchEvalRow, input_map: Path, config: CleanMapConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **asdict(row),
        "algorithm": "clean_map_v1",
        "input_map_path": str(input_map),
        "config": config.to_dict(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _recommendation_lines(rows: list[BatchEvalRow]) -> list[str]:
    if not rows:
        return ["未发现可评估的地图 session。"]
    completed = [row for row in rows if row.state == "completed"]
    failed = [row for row in rows if row.state != "completed"]
    lines = [
        "## 汇总",
        "",
        f"- 总运行数：{len(rows)}",
        f"- 成功：{len(completed)}",
        f"- 失败：{len(failed)}",
    ]
    for preset in sorted({row.preset for row in rows}):
        preset_rows = [row for row in completed if row.preset == preset]
        if not preset_rows:
            lines.append(f"- {preset}: 无成功结果")
            continue
        retention = sum(row.retention_ratio for row in preset_rows) / len(preset_rows)
        duration = sum(row.duration_sec for row in preset_rows) / len(preset_rows)
        lines.append(f"- {preset}: 平均保留率 {retention * 100:.1f}%，平均耗时 {duration:.3f}s")
    return lines


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _format_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024.0
    return f"{value:.1f}GB"


if __name__ == "__main__":
    main()
