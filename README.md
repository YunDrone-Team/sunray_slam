# sunray_slam

ROS2 source packages used by Drone3Plot SLAM and relocalization runtimes.

Layout:

- `fast_lio/`: FAST-LIO mapping package.
- `open3d_loc/`: global localization package used by reloc.
- `livox_ros_driver2/`: Livox ROS2 driver package.
- `Livox-SDK2/`: Livox lidar SDK, tracked as a git submodule.
- `scripts/`: generic ROS2 runtime helpers for building and launching FAST-LIO/reloc.
- `config/`: example environment files for those runtime helpers.
- `data/`: point-cloud maps used by relocalization.

Clone with submodules:

```bash
git clone --recursive <sunray_slam_repo_url>
```

If the repo was cloned without submodules:

```bash
git submodule update --init --recursive
```

Install Livox-SDK2 once on a new device before building `livox_ros_driver2`:

```bash
scripts/install_livox_sdk2.sh
```

Example ROS2 Humble workspace build:

```bash
LOCALIZATION_WS_ROOT=/tmp/sunray_slam_ws scripts/build_localization_ws.sh
```

Run FAST-LIO:

```bash
SUNRAY_ENV_FILE=config/fastlio.env.example scripts/run_fastlio.sh
```

Run relocalization:

```bash
SUNRAY_ENV_FILE=config/reloc.env.example scripts/run_reloc.sh
```

Configure a replacement MID360/MID360s lidar:

```bash
scripts/configure_livox_mid360.sh
```

The command defaults to `--iface eth0 --apply` and updates
`livox_ros_driver2/config/MID360s_config.json` plus
`livox_ros_driver2/config/MID360_config.json`.
