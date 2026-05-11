#!/usr/bin/env python3
"""Discover a Livox MID360-like lidar on an Ethernet port and update config.

Default mode is read-only: it sniffs Livox discovery/ARP packets and prints the
detected lidar IP, broadcast code/SN, and suggested host IP.
Use --apply with --config to modify existing lidar_configs ip fields.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DISCOVERY_PORT = 56000
CONFIG_NAMES = ("MID360s_config.json", "MID360_config.json")


@dataclass
class Discovery:
    lidar_ip: str | None = None
    broadcast_code: str | None = None
    requested_host_ip: str | None = None
    iface_ip: str | None = None
    source: str | None = None
    raw_packets: int = 0


def run_text(command: list[str], timeout: float | None = None) -> str:
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return stdout + stderr
    return proc.stdout + proc.stderr


def iface_ipv4(iface: str) -> str | None:
    output = run_text(["ip", "-4", "-o", "addr", "show", "dev", iface])
    match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", output)
    return match.group(1) if match else None


def verbose_print(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[debug] {message}", file=sys.stderr)


def parse_ascii_from_hex_dump(lines: list[str], verbose: bool = False) -> str | None:
    blob = bytearray()
    for line in lines:
        match = re.search(r"0x[0-9a-fA-F]+:\s+(.*)$", line)
        if not match:
            continue
        for token in match.group(1).split():
            if not re.fullmatch(r"[0-9a-fA-F]{4}", token):
                break
            blob.extend(bytes.fromhex(token))
    if not blob:
        verbose_print(verbose, "hex dump: no payload bytes found")
        return None
    text = "".join(chr(b) if 32 <= b < 127 else " " for b in blob)
    candidates = re.findall(r"[A-Z0-9]{10,16}", text)
    verbose_print(verbose, f"hex dump: decoded {len(blob)} bytes")
    verbose_print(verbose, f"hex dump ascii: {text.strip() or 'N/A'}")
    verbose_print(verbose, f"broadcast candidates: {candidates or 'N/A'}")
    if not candidates:
        return None
    candidates.sort(key=lambda item: (("LIVOX" in item) or ("ARM" in item), len(item)), reverse=True)
    verbose_print(verbose, f"selected broadcast_code candidate: {candidates[0]}")
    return candidates[0]


def parse_tcpdump(output: str, iface: str, verbose: bool = False) -> Discovery:
    result = Discovery(iface_ip=iface_ipv4(iface))
    hex_lines: list[str] = []
    lines = output.splitlines()
    verbose_print(verbose, f"parse iface={iface}, iface_ip={result.iface_ip or 'N/A'}")
    verbose_print(verbose, f"tcpdump output lines={len(lines)}")
    for line in output.splitlines():
        if f".{DISCOVERY_PORT} >" in line and "IP " in line:
            match = re.search(r"\bIP\s+(\d+\.\d+\.\d+\.\d+)\.%d\s+>" % DISCOVERY_PORT, line)
            if match:
                result.lidar_ip = match.group(1)
                result.source = "udp-discovery"
                result.raw_packets += 1
                verbose_print(verbose, f"UDP discovery packet: lidar_ip={result.lidar_ip}, line={line}")
        if "ARP," in line and "who-has" in line and " tell " in line:
            match = re.search(
                r"who-has\s+(\d+\.\d+\.\d+\.\d+)\s+tell\s+(\d+\.\d+\.\d+\.\d+)",
                line,
            )
            if match:
                host_ip, lidar_ip = match.groups()
                verbose_print(verbose, f"ARP request: lidar_ip={lidar_ip}, requested_host_ip={host_ip}")
                if result.lidar_ip is None or result.lidar_ip == lidar_ip:
                    result.lidar_ip = lidar_ip
                    result.requested_host_ip = host_ip
                    result.source = "arp-request"
        if re.search(r"0x[0-9a-fA-F]+:", line):
            hex_lines.append(line)
    verbose_print(verbose, f"hex dump lines={len(hex_lines)}")
    result.broadcast_code = parse_ascii_from_hex_dump(hex_lines, verbose=verbose)
    verbose_print(
        verbose,
        "parse result: "
        f"lidar_ip={result.lidar_ip or 'N/A'}, "
        f"broadcast_code={result.broadcast_code or 'N/A'}, "
        f"requested_host_ip={result.requested_host_ip or 'N/A'}, "
        f"raw_packets={result.raw_packets}",
    )
    return result


def sniff(iface: str, timeout_sec: float, sudo: bool, verbose: bool = False) -> Discovery:
    tcpdump = shutil.which("tcpdump")
    if not tcpdump:
        raise RuntimeError("tcpdump not found. Install it first, e.g. sudo apt install tcpdump")
    command = [
        tcpdump,
        "-ni",
        iface,
        f"(udp and port {DISCOVERY_PORT}) or arp",
        "-X",
    ]
    if sudo and hasattr(__import__("os"), "geteuid") and __import__("os").geteuid() != 0:
        command.insert(0, "sudo")
    verbose_print(verbose, f"sniff command: {' '.join(command)}")
    verbose_print(verbose, f"sniff timeout: {timeout_sec}s")
    output = run_text(["timeout", "-k", "2", str(timeout_sec), *command], timeout=timeout_sec + 5)
    if verbose:
        preview = "\n".join(output.splitlines()[:40])
        verbose_print(verbose, "tcpdump preview begin")
        if preview:
            print(preview, file=sys.stderr)
        else:
            print("(empty tcpdump output)", file=sys.stderr)
        verbose_print(verbose, "tcpdump preview end")
    return parse_tcpdump(output, iface, verbose=verbose)


def discover_neighbor(iface: str, verbose: bool = False) -> Discovery:
    iface_ip = iface_ipv4(iface)
    output = run_text(["ip", "neigh", "show", "dev", iface])
    candidates: list[str] = []
    verbose_print(verbose, f"neighbor output: {output.strip() or 'N/A'}")
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        ip = fields[0]
        if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip):
            continue
        if ip == iface_ip:
            continue
        if any(state in fields for state in ("FAILED", "INCOMPLETE")):
            continue
        candidates.append(ip)

    unique_candidates = sorted(set(candidates))
    verbose_print(verbose, f"neighbor candidates: {unique_candidates or 'N/A'}")
    if len(unique_candidates) != 1:
        return Discovery(iface_ip=iface_ip)
    return Discovery(lidar_ip=unique_candidates[0], iface_ip=iface_ip, source="ip-neigh")


def repo_root_from_script() -> Path:
    sunray_root = Path(__file__).resolve().parent.parent
    if sunray_root.parent.name == "thirdparty":
        return sunray_root.parent.parent
    return sunray_root


def default_config_paths() -> list[Path]:
    repo_root = repo_root_from_script()
    sunray_root = Path(__file__).resolve().parent.parent
    runtime_config_dir = repo_root / ".runtime/localization_ws/src/livox_ros_driver2/config"
    source_config_dir = sunray_root / "livox_ros_driver2/config"

    runtime_paths = [runtime_config_dir / name for name in CONFIG_NAMES]
    if any(path.exists() for path in runtime_paths):
        return runtime_paths
    return [source_config_dir / name for name in CONFIG_NAMES]


def update_config(path: Path, lidar_ip: str) -> None:
    if not path.exists():
        print(f"skip missing config: {path}")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    lidar_configs = data.get("lidar_configs")
    if not isinstance(lidar_configs, list) or not lidar_configs:
        print(f"skip config without existing lidar_configs: {path}", file=sys.stderr)
        return

    updated = 0
    for item in lidar_configs:
        if isinstance(item, dict) and "ip" in item:
            item["ip"] = lidar_ip
            updated += 1
    if updated == 0:
        print(f"skip config without existing lidar_configs ip: {path}", file=sys.stderr)
        return

    backup = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated: {path} ({updated} lidar ip field(s))")
    print(f"backup:  {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-discover Livox lidar IP/SN from eth discovery packets.",
    )
    parser.add_argument("-i", "--iface", default="eth0", help="Ethernet interface to sniff")
    parser.add_argument("-t", "--timeout", type=float, default=8.0, help="sniff timeout seconds")
    parser.add_argument("-v", "--verbose", action="store_true", help="print detailed sniff/parse diagnostics")
    parser.add_argument("--no-sudo", action="store_true", help="do not prefix tcpdump with sudo")
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        help="MID360/MID360s config path to update; can be specified multiple times",
    )
    parser.add_argument("--apply", action="store_true", help="actually update config files")
    parser.add_argument(
        "--host-ip",
        default="auto",
        help="deprecated; host IP is detected and printed but not written",
    )
    args = parser.parse_args()

    result = sniff(args.iface, args.timeout, sudo=not args.no_sudo, verbose=args.verbose)
    if not result.lidar_ip:
        result = discover_neighbor(args.iface, verbose=args.verbose)
    print(f"iface:           {args.iface}")
    print(f"iface_ip:        {result.iface_ip or 'N/A'}")
    print(f"lidar_ip:        {result.lidar_ip or 'N/A'}")
    print(f"lidar_ip_source: {result.source or 'N/A'}")
    print(f"broadcast_code:  {result.broadcast_code or 'N/A'}")
    print(f"arp_host_ip:     {result.requested_host_ip or 'N/A'}")
    print(f"discovery_pkts:  {result.raw_packets}")

    if not result.lidar_ip:
        print("ERROR: no Livox discovery packet found", file=sys.stderr)
        return 2

    if args.host_ip == "none":
        host_ip = None
    elif args.host_ip == "auto":
        host_ip = result.requested_host_ip or result.iface_ip
    else:
        host_ip = args.host_ip
    print(f"selected_host_ip:{host_ip or 'skip'}")
    print("host_ip_write:   skipped")

    if args.apply:
        config_paths = [Path(raw_path).expanduser() for raw_path in args.config]
        if not config_paths:
            config_paths = default_config_paths()
        for path in config_paths:
            update_config(path, result.lidar_ip)
    else:
        default_paths = default_config_paths()
        print("default_config_targets:")
        for path in default_paths:
            print(f"  {path}")
        print("dry-run: add --apply to update default targets, or --apply --config /path/to/config.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
