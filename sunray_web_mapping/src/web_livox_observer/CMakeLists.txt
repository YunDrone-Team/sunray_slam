cmake_minimum_required(VERSION 3.8)
project(web_livox_observer)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(livox_ros_driver2 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)

add_library(web_livox_observer_preview src/preview.cpp)
target_include_directories(web_livox_observer_preview PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include>"
)
ament_target_dependencies(
  web_livox_observer_preview
  livox_ros_driver2
  sensor_msgs
)

add_executable(web_livox_observer_node src/web_livox_observer_node.cpp)
target_link_libraries(web_livox_observer_node web_livox_observer_preview)
ament_target_dependencies(
  web_livox_observer_node
  livox_ros_driver2
  rclcpp
  sensor_msgs
  std_msgs
)

install(DIRECTORY include/
  DESTINATION include
)

install(TARGETS web_livox_observer_preview
  EXPORT export_web_livox_observer_preview
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(TARGETS web_livox_observer_node
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(preview_test test/preview_test.cpp)
  target_link_libraries(preview_test web_livox_observer_preview)
endif()

ament_export_include_directories(include)
ament_export_targets(export_web_livox_observer_preview HAS_LIBRARY_TARGET)
ament_package()
