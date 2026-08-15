# sunray_web_mapping

面向 Livox MID-360、FAST-LIO2 和浏览器建图控制的 ROS 2 工作区。

本目录提供 Livox、FAST-LIO2、ROS broker 和 web_mapping 的完整建图流程。浏览器可以启动/停止建图会话、预览实时点云并下载地图。雷达驱动复用父仓库的 `livox_ros_driver2` 子模块，不进入本目录的 `src`。

## 组件

- `src/fast_lio`: FAST-LIO2 ROS 2 算法包，基于 `Ericsii/FAST_LIO_ROS2`。
- `../livox_ros_driver2`: 父仓库统一维护的 Livox MID-360 ROS 2 驱动；setup 时生成忽略的构建副本。
- `src/web_livox_observer`: 将 Livox 原始点云/IMU 转成 Web 预览和雷达状态。
- `src/web_fast_lio_broker`: 管理 Livox、FAST-LIO 和地图保存的 ROS broker。
- `src/web_mapping`: 浏览器 UI，以及点云、位姿、轨迹、状态和历史地图的 HTTP/WebSocket 桥接。

## 依赖

- ROS 2 Humble 或 Foxy
- `colcon`
- 主机网络能访问 Livox MID-360
- 如果不替换配置文件，主机网口需要匹配仓库内置的 MID-360 配置

默认硬件配置：

- LiDAR IP: `192.168.1.122`
- Host IP: `192.168.1.5`

## 构建

```bash
cd sunray_slam
git submodule update --init --recursive
cd sunray_web_mapping
./scripts/setup_workspace.sh
source /opt/ros/humble/setup.bash
colcon build --base-paths src .runtime/external --cmake-args -DROS_EDITION=ROS2
source install/setup.bash
```

## 运行

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch web_fast_lio_broker mid360_web_mapping.launch.py
```

打开 Web UI：

```text
http://127.0.0.1:8765
```

点击“启动雷达”后等待状态 online，再点击“开始建图”。broker 会启动或复用 Livox 驱动和 FAST-LIO，并把数据转给 web_mapping。

如果只需要 Web 桥接，也可以单独运行 `ros2 launch web_mapping web_mapping.launch.py`。

## 运行时 Topic

launch 文件会把 FAST-LIO2 输出映射到 Web 侧 topic：

- `/web_fast_lio/cloud_registered` -> `/web_mapping/current_frame`，用于 Web 实时显示“里程计地图”
- `/web_fast_lio/laser_map` 用于 FAST-LIO2 保存 PCD；未发布实时配准点云时也可作为 `/web_mapping/current_frame` 的兜底来源
- `/web_mapping/global_map` 用于保存后的后处理地图
- `/web_fast_lio/odometry` -> `/web_mapping/pose`
- `/web_fast_lio/path` -> `/web_mapping/optimized_path`
- `/livox/lidar` 是 FAST-LIO2 的 Livox 输入
- `/livox/imu` 是 FAST-LIO2 的 Livox 输入
- `/web_mapping/raw_cloud` 是 observer 发布的降采样原始点云
- `/web_mapping/raw_observation` 是 observer 发布的雷达状态

## 说明

- FAST-LIO2 不提供后处理结果；Web 里程计地图图层默认累积显示 FAST-LIO2 的 `/cloud_registered`，保存的里程计地图文件来自 FAST-LIO2 map save 输出。
- broker 负责完整的启动、停止、保存和后处理流程；web_mapping 本身只负责 Web 桥接。
- 第三方包保留各自 license 和上游来源说明。

## 来源与致谢

- FAST-LIO2 算法来自 HKU-MARS 的 FAST-LIO 系列工作。
- 本仓库中的 `src/fast_lio` 基于 `Ericsii/FAST_LIO_ROS2` 的 ROS 2 移植版本整理集成。
- Livox ROS driver 来自父仓库的 `livox_ros_driver2` 子模块。
- `src/web_mapping` 来自 `Jasonzzhu0514/web_mapping`，用于浏览器点云可视化和建图控制界面。
