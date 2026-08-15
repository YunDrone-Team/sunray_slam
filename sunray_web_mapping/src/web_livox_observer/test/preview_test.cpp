#include "web_livox_observer/preview.hpp"

#include <cstring>

#include "gtest/gtest.h"

namespace
{

float read_float(const sensor_msgs::msg::PointCloud2 & cloud, size_t point_index, size_t offset)
{
  float value = 0.0F;
  std::memcpy(&value, cloud.data.data() + point_index * cloud.point_step + offset, sizeof(float));
  return value;
}

livox_ros_driver2::msg::CustomMsg make_custom_msg(size_t count)
{
  livox_ros_driver2::msg::CustomMsg msg;
  msg.header.frame_id = "livox_frame";
  msg.header.stamp.sec = 12;
  msg.header.stamp.nanosec = 345000000;
  msg.point_num = static_cast<uint32_t>(count);
  msg.points.resize(count);
  for (size_t i = 0; i < count; ++i) {
    auto & point = msg.points[i];
    point.x = static_cast<float>(i);
    point.y = static_cast<float>(i + 10);
    point.z = static_cast<float>(i + 20);
    point.reflectivity = static_cast<uint8_t>(i + 30);
  }
  return msg;
}

}  // namespace

TEST(RawCloudPreview, KeepsPointCloud2LayoutStable)
{
  const auto msg = make_custom_msg(3);
  const auto cloud = web_livox_observer::makeRawCloudPreview(msg, msg.point_num, 0);

  ASSERT_EQ(cloud.header.frame_id, "livox_frame");
  ASSERT_EQ(cloud.width, 3U);
  ASSERT_EQ(cloud.height, 1U);
  ASSERT_EQ(cloud.point_step, 16U);
  ASSERT_EQ(cloud.row_step, 48U);
  ASSERT_EQ(cloud.fields.size(), 4U);
  EXPECT_EQ(cloud.fields[0].name, "x");
  EXPECT_EQ(cloud.fields[1].name, "y");
  EXPECT_EQ(cloud.fields[2].name, "z");
  EXPECT_EQ(cloud.fields[3].name, "intensity");
  EXPECT_FLOAT_EQ(read_float(cloud, 2, 0), 2.0F);
  EXPECT_FLOAT_EQ(read_float(cloud, 2, 4), 12.0F);
  EXPECT_FLOAT_EQ(read_float(cloud, 2, 8), 22.0F);
  EXPECT_FLOAT_EQ(read_float(cloud, 2, 12), 32.0F);
}

TEST(RawCloudPreview, SamplesByCeilingStride)
{
  const auto msg = make_custom_msg(10);
  const auto cloud = web_livox_observer::makeRawCloudPreview(msg, msg.point_num, 4);

  ASSERT_EQ(cloud.width, 4U);
  EXPECT_FLOAT_EQ(read_float(cloud, 0, 0), 0.0F);
  EXPECT_FLOAT_EQ(read_float(cloud, 1, 0), 3.0F);
  EXPECT_FLOAT_EQ(read_float(cloud, 2, 0), 6.0F);
  EXPECT_FLOAT_EQ(read_float(cloud, 3, 0), 9.0F);
}

TEST(RawCloudPreview, BoundsPointCountToAvailablePoints)
{
  auto msg = make_custom_msg(2);
  msg.point_num = 5;
  const auto cloud = web_livox_observer::makeRawCloudPreview(msg, msg.point_num, 0);

  ASSERT_EQ(cloud.width, 2U);
  EXPECT_FLOAT_EQ(read_float(cloud, 1, 0), 1.0F);
}
