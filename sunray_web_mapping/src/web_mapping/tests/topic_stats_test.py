#!/usr/bin/env python3
"""Topic health snapshot checks."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "web_mapping"))

from web_mapping.runtime.stats import TopicStats  # noqa: E402


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_stale_topic_reports_zero_live_metrics() -> None:
    stats = TopicStats("/livox/lidar")
    stats.record(points=20000, sampled_points=20000, stamp_sec=1.0)
    stats.record(points=21000, sampled_points=21000, stamp_sec=1.1)

    stale_snapshot = stats.snapshot(stats.last_received_monotonic + 2.1)

    assert stale_snapshot["state"] == "stale"
    assert stale_snapshot["hz"] == 0.0
    assert stale_snapshot["last_points"] == 0
    assert stale_snapshot["last_sampled_points"] == 0
    assert stale_snapshot["frames"] == 2


def test_online_topic_keeps_live_metrics() -> None:
    stats = TopicStats("/livox/lidar")
    stats.record(points=20000, sampled_points=19000, stamp_sec=1.0)
    stats.record(points=21000, sampled_points=20000, stamp_sec=1.1)

    online_snapshot = stats.snapshot(stats.last_received_monotonic + 0.1)

    assert online_snapshot["state"] == "online"
    assert online_snapshot["hz"] > 0.0
    assert online_snapshot["last_points"] == 21000
    assert online_snapshot["last_sampled_points"] == 20000


def test_receive_rate_is_independent_from_browser_sampling() -> None:
    stats = TopicStats("/livox/lidar")
    stats.record(points=20000, sampled_points=None, stamp_sec=1.0)
    stats.record_sampled(5000)
    stats.record(points=21000, sampled_points=None, stamp_sec=1.1)

    snapshot = stats.snapshot(stats.last_received_monotonic + 0.1)

    assert snapshot["state"] == "online"
    assert snapshot["hz"] > 0.0
    assert snapshot["last_points"] == 21000
    assert snapshot["last_sampled_points"] == 5000


def test_receive_rate_resets_after_stale_gap() -> None:
    clock = ManualClock()
    stats = TopicStats("/livox/lidar", clock=clock)
    stats.record(points=20000, sampled_points=20000, stamp_sec=1.0)
    clock.advance(0.1)
    stats.record(points=21000, sampled_points=21000, stamp_sec=1.1)

    clock.advance(5.0)
    stats.record(points=22000, sampled_points=22000, stamp_sec=6.1)
    clock.advance(0.1)
    stats.record(points=23000, sampled_points=23000, stamp_sec=6.2)

    snapshot = stats.snapshot(clock())

    assert snapshot["state"] == "online"
    assert 9.0 <= snapshot["hz"] <= 11.0
    assert snapshot["frames"] == 4


if __name__ == "__main__":
    test_stale_topic_reports_zero_live_metrics()
    test_online_topic_keeps_live_metrics()
    test_receive_rate_is_independent_from_browser_sampling()
    test_receive_rate_resets_after_stale_gap()
    print("topic stats ok")
