import os.path

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition

from launch_ros.actions import Node


def generate_launch_description():
    package_path = get_package_share_directory('fast_lio')
    default_config_path = os.path.join(package_path, 'config')
    default_rviz_config_path = os.path.join(
        package_path, 'rviz', 'fastlio.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time')
    config_path = LaunchConfiguration('config_path')
    config_file = LaunchConfiguration('config_file')
    rviz_use = LaunchConfiguration('rviz')
    rviz_cfg = LaunchConfiguration('rviz_cfg')
    cloud_registered_topic = LaunchConfiguration('cloud_registered_topic')
    cloud_registered_body_topic = LaunchConfiguration('cloud_registered_body_topic')
    cloud_effected_topic = LaunchConfiguration('cloud_effected_topic')
    laser_map_topic = LaunchConfiguration('laser_map_topic')
    odometry_topic = LaunchConfiguration('odometry_topic')
    path_topic = LaunchConfiguration('path_topic')
    map_save_service = LaunchConfiguration('map_save_service')
    map_file_path = LaunchConfiguration('map_file_path')

    declare_use_sim_time_cmd = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation (Gazebo) clock if true'
    )
    declare_config_path_cmd = DeclareLaunchArgument(
        'config_path', default_value=default_config_path,
        description='Yaml config file path'
    )
    declare_config_file_cmd = DeclareLaunchArgument(
        'config_file', default_value='mid360.yaml',
        description='Config file'
    )
    declare_rviz_cmd = DeclareLaunchArgument(
        'rviz', default_value='true',
        description='Use RViz to monitor results'
    )
    declare_rviz_config_path_cmd = DeclareLaunchArgument(
        'rviz_cfg', default_value=default_rviz_config_path,
        description='RViz config file path'
    )
    declare_cloud_registered_topic_cmd = DeclareLaunchArgument(
        'cloud_registered_topic', default_value='/cloud_registered',
        description='FAST-LIO registered scan topic'
    )
    declare_cloud_registered_body_topic_cmd = DeclareLaunchArgument(
        'cloud_registered_body_topic', default_value='/cloud_registered_body',
        description='FAST-LIO body-frame registered scan topic'
    )
    declare_cloud_effected_topic_cmd = DeclareLaunchArgument(
        'cloud_effected_topic', default_value='/cloud_effected',
        description='FAST-LIO effected feature cloud topic'
    )
    declare_laser_map_topic_cmd = DeclareLaunchArgument(
        'laser_map_topic', default_value='/Laser_map',
        description='FAST-LIO accumulated map topic'
    )
    declare_odometry_topic_cmd = DeclareLaunchArgument(
        'odometry_topic', default_value='/Odometry',
        description='FAST-LIO odometry topic'
    )
    declare_path_topic_cmd = DeclareLaunchArgument(
        'path_topic', default_value='/path',
        description='FAST-LIO path topic'
    )
    declare_map_save_service_cmd = DeclareLaunchArgument(
        'map_save_service', default_value='map_save',
        description='FAST-LIO map save service name'
    )
    declare_map_file_path_cmd = DeclareLaunchArgument(
        'map_file_path', default_value='/tmp/fast_lio_map.pcd',
        description='Override map_file_path parameter when non-empty'
    )

    fast_lio_node = Node(
        package='fast_lio',
        executable='fastlio_mapping',
        parameters=[PathJoinSubstitution([config_path, config_file]),
                    {
                        'use_sim_time': use_sim_time,
                        'map_file_path': map_file_path,
                    }],
        remappings=[
            ('/cloud_registered', cloud_registered_topic),
            ('/cloud_registered_body', cloud_registered_body_topic),
            ('/cloud_effected', cloud_effected_topic),
            ('/Laser_map', laser_map_topic),
            ('/Odometry', odometry_topic),
            ('/path', path_topic),
            ('map_save', map_save_service),
        ],
        output='screen'
    )
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_cfg],
        condition=IfCondition(rviz_use)
    )

    ld = LaunchDescription()
    ld.add_action(declare_use_sim_time_cmd)
    ld.add_action(declare_config_path_cmd)
    ld.add_action(declare_config_file_cmd)
    ld.add_action(declare_rviz_cmd)
    ld.add_action(declare_rviz_config_path_cmd)
    ld.add_action(declare_cloud_registered_topic_cmd)
    ld.add_action(declare_cloud_registered_body_topic_cmd)
    ld.add_action(declare_cloud_effected_topic_cmd)
    ld.add_action(declare_laser_map_topic_cmd)
    ld.add_action(declare_odometry_topic_cmd)
    ld.add_action(declare_path_topic_cmd)
    ld.add_action(declare_map_save_service_cmd)
    ld.add_action(declare_map_file_path_cmd)

    ld.add_action(fast_lio_node)
    ld.add_action(rviz_node)

    return ld
