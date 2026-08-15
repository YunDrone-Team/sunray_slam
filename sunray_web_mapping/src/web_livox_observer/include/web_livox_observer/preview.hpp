#pragma once

#include <cstdint>

#include "livox_ros_driver2/msg/custom_msg.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"

namespace web_livox_observer
{

sensor_msgs::msg::PointCloud2 makeRawCloudPreview(
  const livox_ros_driver2::msg::CustomMsg & msg,
  uint32_t point_count,
  int max_points);

}  // namespace web_livox_observer
