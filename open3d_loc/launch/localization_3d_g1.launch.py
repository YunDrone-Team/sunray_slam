import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    fast_lio_share = FindPackageShare('fast_lio')
    open3d_loc_share = FindPackageShare('open3d_loc')
    livox_share = FindPackageShare('livox_ros_driver2')
    use_sim_time = LaunchConfiguration('use_sim_time')
    start_livox_driver = LaunchConfiguration('start_livox_driver')
    rviz = LaunchConfiguration('rviz')
    map_file = LaunchConfiguration('map_file')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )
    start_livox_driver_arg = DeclareLaunchArgument(
        'start_livox_driver',
        default_value='true',
        description='Start livox_ros_driver2 for MID360 input'
    )
    rviz_arg = DeclareLaunchArgument(
        'rviz',
        default_value='false',
        description='Start RViz visualization'
    )
    map_file_arg = DeclareLaunchArgument(
        'map_file',
        default_value=os.getenv(
            'RELOC_MAP_FILE',
            '/home/yundrone/drone3plot/scripts/reloc/data/office.ply'
        ),
        description='Point cloud map path for open3d_loc'
    )

    livox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                livox_share,
                'launch_ROS2',
                'msg_MID360s_launch.py'
            ])
        ]),
        condition=IfCondition(start_livox_driver)
    )

    fast_lio_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                fast_lio_share,
                'launch',
                'mapping.launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'start_livox_driver': 'false',
            'rviz': 'false'
        }.items()
    )

    open3d_loc_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                open3d_loc_share,
                'launch',
                'open3d_loc_g1.launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'map_file': map_file
        }.items()
    )

    rviz_config_path = PathJoinSubstitution([
        open3d_loc_share,
        'rviz_cfg',
        'fastlio.rviz'
    ])

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz_map_cur',
        arguments=['-d', rviz_config_path],
        output='screen',
        prefix='nice',
        condition=IfCondition(rviz)
    )

    return LaunchDescription([
        use_sim_time_arg,
        start_livox_driver_arg,
        rviz_arg,
        map_file_arg,
        livox_launch,
        fast_lio_launch,
        open3d_loc_launch,
        rviz_node
    ])
