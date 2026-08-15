from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    broker_share = get_package_share_directory("web_fast_lio_broker")

    host = LaunchConfiguration("host")
    port = LaunchConfiguration("port")
    map_history_root = LaunchConfiguration("map_history_root")
    livox_config = LaunchConfiguration("livox_config")
    fast_lio_config = LaunchConfiguration("fast_lio_config")
    use_sim_time = LaunchConfiguration("use_sim_time")
    start_livox_driver = LaunchConfiguration("start_livox_driver")
    start_fast_lio = LaunchConfiguration("start_fast_lio")
    rviz = LaunchConfiguration("rviz")
    lidar_check_timeout_sec = LaunchConfiguration("lidar_check_timeout_sec")
    lidar_min_points = LaunchConfiguration("lidar_min_points")

    livox_lidar_topic = LaunchConfiguration("livox_lidar_topic")
    livox_imu_topic = LaunchConfiguration("livox_imu_topic")
    fast_lio_current_frame_topic = LaunchConfiguration("fast_lio_current_frame_topic")
    fast_lio_current_body_frame_topic = LaunchConfiguration("fast_lio_current_body_frame_topic")
    fast_lio_map_topic = LaunchConfiguration("fast_lio_map_topic")
    fast_lio_odom_topic = LaunchConfiguration("fast_lio_odom_topic")
    fast_lio_path_topic = LaunchConfiguration("fast_lio_path_topic")
    fast_lio_map_save_service = LaunchConfiguration("fast_lio_map_save_service")
    clean_map_enabled = LaunchConfiguration("clean_map_enabled")
    clean_map_voxel_size = LaunchConfiguration("clean_map_voxel_size")
    clean_map_min_neighbors = LaunchConfiguration("clean_map_min_neighbors")
    clean_map_radius = LaunchConfiguration("clean_map_radius")
    clean_map_min_z = LaunchConfiguration("clean_map_min_z")
    clean_map_max_z = LaunchConfiguration("clean_map_max_z")
    clean_map_min_retention_ratio = LaunchConfiguration("clean_map_min_retention_ratio")
    clean_map_min_output_points = LaunchConfiguration("clean_map_min_output_points")
    publish_fast_lio_current_frame = LaunchConfiguration("publish_fast_lio_current_frame")

    broker_node = Node(
        package="web_fast_lio_broker",
        executable="web_fast_lio_broker",
        name="web_fast_lio_broker",
        output="screen",
        parameters=[{
            "map_history_root": map_history_root,
            "manage_livox_driver": True,
            "livox_config_path": livox_config,
            "fast_lio_map_save_service": fast_lio_map_save_service,
            "fast_lio_config_path": fast_lio_config,
            "fast_lio_config_file": "mid360_fast_lio.yaml",
            "raw_livox_topic": livox_lidar_topic,
            "raw_observation_topic": "/web_mapping/raw_observation",
            "fast_lio_current_frame_topic": fast_lio_current_frame_topic,
            "fast_lio_current_body_frame_topic": fast_lio_current_body_frame_topic,
            "fast_lio_map_topic": fast_lio_map_topic,
            "fast_lio_odom_topic": fast_lio_odom_topic,
            "fast_lio_path_topic": fast_lio_path_topic,
            "fast_lio_imu_topic": livox_imu_topic,
            "publish_fast_lio_current_frame": ParameterValue(publish_fast_lio_current_frame, value_type=bool),
            "clean_map_enabled": ParameterValue(clean_map_enabled, value_type=bool),
            "clean_map_voxel_size": ParameterValue(clean_map_voxel_size, value_type=float),
            "clean_map_min_neighbors": ParameterValue(clean_map_min_neighbors, value_type=int),
            "clean_map_radius": ParameterValue(clean_map_radius, value_type=float),
            "clean_map_min_z": ParameterValue(clean_map_min_z, value_type=float),
            "clean_map_max_z": ParameterValue(clean_map_max_z, value_type=float),
            "clean_map_min_retention_ratio": ParameterValue(clean_map_min_retention_ratio, value_type=float),
            "clean_map_min_output_points": ParameterValue(clean_map_min_output_points, value_type=int),
            "stop_livox_after_stop": True,
            "stop_livox_after_save": False,
            "stop_fast_lio_after_stop": True,
            "stop_fast_lio_after_save": False,
            "lidar_check_timeout_sec": ParameterValue(lidar_check_timeout_sec, value_type=float),
            "lidar_min_points": ParameterValue(lidar_min_points, value_type=int),
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument("host", default_value="0.0.0.0"),
        DeclareLaunchArgument("port", default_value="8765"),
        DeclareLaunchArgument("map_history_root", default_value="maps"),
        DeclareLaunchArgument(
            "livox_config",
            default_value=PathJoinSubstitution([broker_share, "config", "MID360S_192_168_1_122.json"]),
        ),
        DeclareLaunchArgument(
            "fast_lio_config",
            default_value=PathJoinSubstitution([broker_share, "config"]),
        ),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("start_livox_driver", default_value="false"),
        DeclareLaunchArgument("start_fast_lio", default_value="false"),
        DeclareLaunchArgument("rviz", default_value="false"),
        DeclareLaunchArgument("lidar_check_timeout_sec", default_value="8.0"),
        DeclareLaunchArgument("lidar_min_points", default_value="1"),
        DeclareLaunchArgument("livox_lidar_topic", default_value="/livox/lidar"),
        DeclareLaunchArgument("livox_imu_topic", default_value="/livox/imu"),
        DeclareLaunchArgument("fast_lio_current_frame_topic", default_value="/web_fast_lio/cloud_registered"),
        DeclareLaunchArgument("fast_lio_current_body_frame_topic", default_value="/web_fast_lio/cloud_registered_body"),
        DeclareLaunchArgument("fast_lio_map_topic", default_value="/web_fast_lio/laser_map"),
        DeclareLaunchArgument("fast_lio_odom_topic", default_value="/web_fast_lio/odometry"),
        DeclareLaunchArgument("fast_lio_path_topic", default_value="/web_fast_lio/path"),
        DeclareLaunchArgument("fast_lio_map_save_service", default_value="/web_fast_lio/map_save"),
        DeclareLaunchArgument("fast_lio_map_file_path", default_value="/tmp/web_fast_lio_direct_map.pcd"),
        DeclareLaunchArgument("publish_fast_lio_current_frame", default_value="true"),
        DeclareLaunchArgument("clean_map_enabled", default_value="true"),
        DeclareLaunchArgument("clean_map_voxel_size", default_value="0.05"),
        DeclareLaunchArgument("clean_map_min_neighbors", default_value="1"),
        DeclareLaunchArgument("clean_map_radius", default_value="0.20"),
        DeclareLaunchArgument("clean_map_min_z", default_value="-inf"),
        DeclareLaunchArgument("clean_map_max_z", default_value="inf"),
        DeclareLaunchArgument("clean_map_min_retention_ratio", default_value="0.05"),
        DeclareLaunchArgument("clean_map_min_output_points", default_value="20000"),
        Node(
            package="livox_ros_driver2",
            executable="livox_ros_driver2_node",
            name="livox_lidar_publisher",
            output="screen",
            condition=IfCondition(start_livox_driver),
            parameters=[{
                "xfer_format": 1,
                "multi_topic": 0,
                "data_src": 0,
                "publish_freq": 10.0,
                "output_data_type": 0,
                "frame_id": "livox_frame",
                "lvx_file_path": "/tmp/livox_test.lvx",
                "user_config_path": livox_config,
                "cmdline_input_bd_code": "livox0000000001",
                "use_sim_time": ParameterValue(use_sim_time, value_type=bool),
            }],
        ),
        Node(
            package="fast_lio",
            executable="fastlio_mapping",
            name="laser_mapping",
            output="screen",
            condition=IfCondition(start_fast_lio),
            parameters=[
                PathJoinSubstitution([fast_lio_config, "mid360_fast_lio.yaml"]),
                {
                    "use_sim_time": ParameterValue(use_sim_time, value_type=bool),
                    "map_file_path": LaunchConfiguration("fast_lio_map_file_path"),
                },
            ],
            remappings=[
                ("/cloud_registered", fast_lio_current_frame_topic),
                ("/cloud_registered_body", fast_lio_current_body_frame_topic),
                ("/Laser_map", fast_lio_map_topic),
                ("/Odometry", fast_lio_odom_topic),
                ("/path", fast_lio_path_topic),
                ("map_save", fast_lio_map_save_service),
            ],
        ),
        Node(
            package="web_livox_observer",
            executable="web_livox_observer_node",
            name="web_livox_observer",
            output="screen",
            respawn=True,
            respawn_delay=2.0,
            parameters=[{
                "livox_custom_topic": livox_lidar_topic,
                "imu_topic": livox_imu_topic,
                "raw_cloud_topic": "/web_mapping/raw_cloud",
                "web_imu_topic": "/web_mapping/imu",
                "raw_observation_topic": "/web_mapping/raw_observation",
                "max_raw_points_per_cloud": 15000,
                "min_raw_cloud_interval_sec": 0.3,
                "web_imu_min_interval_sec": 0.1,
                "publish_raw_cloud": True,
            }],
        ),
        broker_node,
        RegisterEventHandler(
            OnProcessExit(
                target_action=broker_node,
                on_exit=[EmitEvent(event=Shutdown(reason="web_fast_lio_broker exited"))],
            )
        ),
        Node(
            package="web_mapping",
            executable="web_mapping_bridge",
            name="web_mapping_bridge",
            output="screen",
            respawn=True,
            respawn_delay=2.0,
            parameters=[{
                "host": host,
                "port": ParameterValue(port, value_type=int),
                "raw_cloud_topic": "/web_mapping/raw_cloud",
                "optimized_cloud_topic": "/web_mapping/current_frame",
                "map_cloud_topic": "/web_mapping/global_map",
                "pose_topic": "/web_mapping/pose",
                "raw_path_topic": "/web_mapping/raw_path",
                "optimized_path_topic": "/web_mapping/optimized_path",
                "imu_topic": "/web_mapping/imu",
                "lidar_status_topic": "/web_mapping/lidar_status",
                "mapping_command_topic": "/web_mapping/command",
                "mapping_status_topic": "/web_mapping/status",
                "use_broker_backend": True,
                "max_points_per_cloud": 0,
                "max_raw_points_per_cloud": 15000,
                "max_optimized_points_per_cloud": 30000,
                "max_map_points_per_cloud": 250000,
                "min_raw_cloud_interval_sec": 0.3,
                "min_cloud_interval_sec": 0.08,
                "min_map_interval_sec": 0.5,
                "min_telemetry_interval_sec": 0.1,
                "path_max_points": 5000,
                "map_history_root": map_history_root,
                "map_history_limit": 20,
            }],
        ),
    ])
