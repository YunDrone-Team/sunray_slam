# sunray_slam

ROS2 source packages used by Drone3Plot SLAM and relocalization runtimes.

Layout:

- `fast_lio/`: FAST-LIO mapping package.
- `open3d_loc/`: global localization package used by reloc.
- `livox_ros_driver2/`: Livox ROS2 driver package.
- `Livox-SDK2/`: Livox lidar SDK, tracked as a git submodule.

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
cmake -S Livox-SDK2 -B Livox-SDK2/build
cmake --build Livox-SDK2/build --parallel "$(nproc)"
sudo cmake --install Livox-SDK2/build
sudo ldconfig
```

Example ROS2 Humble workspace build:

```bash
mkdir -p /tmp/sunray_slam_ws/src
ln -s "$(pwd)/fast_lio" /tmp/sunray_slam_ws/src/fast_lio
ln -s "$(pwd)/open3d_loc" /tmp/sunray_slam_ws/src/open3d_loc
ln -s "$(pwd)/livox_ros_driver2" /tmp/sunray_slam_ws/src/livox_ros_driver2
cp livox_ros_driver2/package_ROS2.xml livox_ros_driver2/package.xml
source /opt/ros/humble/setup.bash
cd /tmp/sunray_slam_ws
colcon build --symlink-install
```
