#!/usr/bin/env python3
"""CleanMap v1 post-processing helper checks."""

from __future__ import annotations

from pathlib import Path
import json
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web_fast_lio_broker.clean_map_postprocess import (  # noqa: E402
    CleanMapConfig,
    PointRecord,
    clean_map_config_for_preset,
    radius_outlier_filter,
    read_pcd_xyzi,
    run_clean_map,
    voxel_downsample,
    write_ascii_pcd_xyzi,
)
from web_fast_lio_broker.clean_map_batch_eval import (  # noqa: E402
    REPORT_CSV,
    REPORT_JSON,
    REPORT_MARKDOWN,
    default_clean_map_config,
    run_batch_eval,
)


def test_read_ascii_and_binary_pcd_xyzi() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ascii_path = root / "ascii.pcd"
        write_ascii_pcd_xyzi(
            ascii_path,
            [
                PointRecord(1.0, 2.0, 3.0, 4.0),
                PointRecord(float("nan"), 0.0, 0.0, 1.0),
                PointRecord(-1.0, -2.0, -3.0, 8.0),
            ],
        )
        ascii_points = read_pcd_xyzi(ascii_path)
        assert ascii_points == [
            PointRecord(1.0, 2.0, 3.0, 4.0),
            PointRecord(-1.0, -2.0, -3.0, 8.0),
        ]

        binary_path = root / "binary.pcd"
        binary_path.write_bytes(
            "\n".join(
                [
                    "# .PCD v0.7",
                    "VERSION 0.7",
                    "FIELDS x y z intensity",
                    "SIZE 4 4 4 4",
                    "TYPE F F F F",
                    "COUNT 1 1 1 1",
                    "WIDTH 2",
                    "HEIGHT 1",
                    "VIEWPOINT 0 0 0 1 0 0 0",
                    "POINTS 2",
                    "DATA binary",
                    "",
                ]
            ).encode("utf-8")
            + struct.pack("<ffffffff", 1.0, 2.0, 3.0, 4.0, -1.0, -2.0, -3.0, 8.0)
        )
        assert read_pcd_xyzi(binary_path) == [
            PointRecord(1.0, 2.0, 3.0, 4.0),
            PointRecord(-1.0, -2.0, -3.0, 8.0),
        ]


def test_voxel_downsample_averages_points() -> None:
    points = [
        PointRecord(0.01, 0.01, 0.01, 1.0),
        PointRecord(0.02, 0.02, 0.02, 3.0),
        PointRecord(1.0, 1.0, 1.0, 5.0),
    ]
    downsampled = voxel_downsample(points, 0.1)
    assert len(downsampled) == 2
    assert PointRecord(0.015, 0.015, 0.015, 2.0) in downsampled


def test_radius_outlier_filter_removes_isolated_points() -> None:
    points = [
        PointRecord(0.0, 0.0, 0.0, 0.0),
        PointRecord(0.05, 0.0, 0.0, 0.0),
        PointRecord(3.0, 3.0, 3.0, 0.0),
    ]
    filtered = radius_outlier_filter(points, radius=0.2, min_neighbors=1)
    assert filtered == points[:2]


def test_run_clean_map_writes_postprocessed_map() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_path = root / "input.pcd"
        output_path = root / "output.pcd"
        write_ascii_pcd_xyzi(
            input_path,
            [
                PointRecord(0.0, 0.0, 0.0, 1.0),
                PointRecord(0.05, 0.0, 0.0, 1.0),
                PointRecord(0.0, 0.05, 0.0, 1.0),
                PointRecord(5.0, 5.0, 5.0, 1.0),
            ],
        )
        result = run_clean_map(
            input_map_path=input_path,
            output_map_path=output_path,
            config=CleanMapConfig(
                enabled=True,
                voxel_size=0.0,
                min_neighbors=1,
                radius=0.2,
                min_z=float("-inf"),
                max_z=float("inf"),
                min_retention_ratio=0.0,
                min_output_points=0,
            ),
        )
        assert result.success
        assert result.input_points == 4
        assert result.output_points == 3
        assert output_path.is_file()


def test_clean_map_config_json_uses_null_for_unbounded_height() -> None:
    config = CleanMapConfig(
        enabled=True,
        voxel_size=0.05,
        min_neighbors=1,
        radius=0.20,
        min_z=float("-inf"),
        max_z=float("inf"),
        min_retention_ratio=0.05,
        min_output_points=20000,
    )
    payload = json.dumps(config.to_dict(), allow_nan=False)
    assert '"min_z": null' in payload
    assert '"max_z": null' in payload


def test_clean_map_presets_override_density_parameters() -> None:
    base = CleanMapConfig(
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

    light = clean_map_config_for_preset(base, "light")
    detail = clean_map_config_for_preset(base, "detail")

    assert light.preset == "light"
    assert light.voxel_size == 0.08
    assert light.radius == 0.25
    assert detail.preset == "detail"
    assert detail.voxel_size == 0.03
    assert detail.radius == 0.15
    assert clean_map_config_for_preset(base, "unknown") == base


def test_retention_guard_allows_large_absolute_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_path = root / "input.pcd"
        output_path = root / "output.pcd"
        write_ascii_pcd_xyzi(
            input_path,
            [
                PointRecord(0.0, 0.0, 0.0, 1.0),
                PointRecord(0.05, 0.0, 0.0, 1.0),
                PointRecord(0.0, 0.05, 0.0, 1.0),
                PointRecord(5.0, 5.0, 5.0, 1.0),
            ],
        )

        result = run_clean_map(
            input_map_path=input_path,
            output_map_path=output_path,
            config=CleanMapConfig(
                enabled=True,
                voxel_size=0.0,
                min_neighbors=1,
                radius=0.2,
                min_z=float("-inf"),
                max_z=float("inf"),
                min_retention_ratio=0.9,
                min_output_points=3,
            ),
        )

        assert result.success
        assert result.output_points == 3
        assert output_path.is_file()


def test_retention_guard_rejects_small_absolute_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_path = root / "input.pcd"
        output_path = root / "output.pcd"
        write_ascii_pcd_xyzi(
            input_path,
            [
                PointRecord(0.0, 0.0, 0.0, 1.0),
                PointRecord(0.05, 0.0, 0.0, 1.0),
                PointRecord(0.0, 0.05, 0.0, 1.0),
                PointRecord(5.0, 5.0, 5.0, 1.0),
            ],
        )

        result = run_clean_map(
            input_map_path=input_path,
            output_map_path=output_path,
            config=CleanMapConfig(
                enabled=True,
                voxel_size=0.0,
                min_neighbors=1,
                radius=0.2,
                min_z=float("-inf"),
                max_z=float("inf"),
                min_retention_ratio=0.9,
                min_output_points=4,
            ),
        )

        assert not result.success
        assert "CleanMap output too small" in result.message
        assert not output_path.exists()


def test_batch_eval_writes_reports_without_touching_session_map() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        maps_root = root / "maps"
        output_root = root / "eval"
        session_dir = maps_root / "session_a"
        session_dir.mkdir(parents=True)
        input_path = session_dir / "session_a_accumulated_map.pcd"
        write_ascii_pcd_xyzi(
            input_path,
            [
                PointRecord(0.0, 0.0, 0.0, 1.0),
                PointRecord(0.05, 0.0, 0.0, 1.0),
                PointRecord(0.0, 0.05, 0.0, 1.0),
                PointRecord(1.0, 1.0, 1.0, 1.0),
                PointRecord(1.05, 1.0, 1.0, 1.0),
            ],
        )

        rows = run_batch_eval(
            maps_root=maps_root,
            output_root=output_root,
            presets=["default", "detail"],
            base_config=default_clean_map_config(),
        )

        assert len(rows) == 2
        assert {row.preset for row in rows} == {"default", "detail"}
        assert all(row.session == "session_a" for row in rows)
        assert (output_root / REPORT_JSON).is_file()
        assert (output_root / REPORT_CSV).is_file()
        assert (output_root / REPORT_MARKDOWN).is_file()
        assert (output_root / "session_a" / "default" / "postprocess_eval.json").is_file()
        assert input_path.is_file()
        report = json.loads((output_root / REPORT_JSON).read_text(encoding="utf-8"))
        assert report["algorithm"] == "clean_map_v1"
        assert len(report["rows"]) == 2


if __name__ == "__main__":
    test_read_ascii_and_binary_pcd_xyzi()
    test_voxel_downsample_averages_points()
    test_radius_outlier_filter_removes_isolated_points()
    test_run_clean_map_writes_postprocessed_map()
    test_clean_map_config_json_uses_null_for_unbounded_height()
    test_clean_map_presets_override_density_parameters()
    test_retention_guard_allows_large_absolute_output()
    test_retention_guard_rejects_small_absolute_output()
    test_batch_eval_writes_reports_without_touching_session_map()
    print("clean map postprocess ok")
