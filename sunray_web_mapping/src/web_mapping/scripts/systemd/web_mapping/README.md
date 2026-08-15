# Web Mapping Systemd Service

This directory contains a systemd unit template for starting `web_mapping` at
boot.

By default the service runs:

```bash
ros2 launch web_mapping web_mapping.launch.py
```

It sources ROS 2 and the containing workspace explicitly, so it does not depend
on `~/.bashrc`. The runner uses `install/local_setup.bash` by default to avoid
pulling stale underlays recorded in `install/setup.bash`.

## Install

```bash
cd /path/to/ros2_ws
source /opt/ros/<distro>/setup.bash
colcon build --symlink-install
src/web_mapping/scripts/systemd/web_mapping/install_web_mapping_service.sh
```

The repository stores a `web_mapping.service.in` template without a fixed user
or home directory. The installer renders `/etc/systemd/system/web_mapping.service`
with the current user, group, home directory, workspace path, runner path, and
env-file path. Override them with `WEB_MAPPING_USER`, `WEB_MAPPING_GROUP`,
`WEB_MAPPING_HOME`, `WEB_MAPPING_RUNNER`, or `WEB_MAPPING_ENV_FILE` when
installing if needed.

If `install/setup.bash` contains a ROS 1 underlay such as `/opt/ros/noetic`,
rebuild from a clean ROS 2 environment before relying on `install/setup.bash`.
The service itself uses `install/local_setup.bash` to avoid stale underlays.

The installer enables boot autostart and restarts the service immediately.

## Operate

```bash
sudo systemctl status web_mapping.service
sudo systemctl restart web_mapping.service
sudo systemctl stop web_mapping.service
journalctl -u web_mapping.service -f
```

The Web Mapping UI listens on `0.0.0.0:8765` by default. Edit
`web_mapping.env` to change ports, topics, ROS domain, map directory, or point
limits, then restart the service.

## Host Launch Override

Host workspaces can run an integration launch file instead of the standalone
bridge. For example, this workspace uses the FAST-LIO broker launch:

```bash
WEB_MAPPING_LAUNCH_PACKAGE=web_fast_lio_broker
WEB_MAPPING_LAUNCH_FILE=mid360_web_mapping.launch.py
WEB_MAPPING_LAUNCH_ARGS_MODE=none
WEB_MAPPING_EXTRA_LAUNCH_ARGS="host:=0.0.0.0 port:=8765 map_history_root:=maps start_livox_driver:=false start_fast_lio:=false rviz:=false"
```

Use the same ROS domain and localhost setting as the LiDAR/SLAM process that
publishes `/livox/lidar`, `/livox/imu`, and the `/web_fast_lio/*` FAST-LIO
topics. Set `start_livox_driver:=true` or `start_fast_lio:=true` only when the
systemd service should own those processes; the default deployment leaves them
disabled and lets the browser broker start/stop them on demand.
