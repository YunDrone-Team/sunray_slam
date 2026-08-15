#include "web_livox_observer/preview.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <string>
#include <vector>

#include "sensor_msgs/msg/point_field.hpp"

namespace web_livox_observer
{
namespace
{

template<typename T>
void write_le(std::vector<uint8_t> & data, size_t offset, const T value)
{
  std::memcpy(data.data() + offset, &value, sizeof(T));
}

sensor_msgs::msg::PointField make_field(const std::string & name, uint32_t offset)
{
  sensor_msgs::msg::PointField field;
  field.name = name;
  field.offset = offset;
  field.datatype = sensor_msgs::msg::PointField::FLOAT32;
  field.count = 1;
  return field;
}

}  // namespace

sensor_msgs::msg::PointCloud2 makeRawCloudPreview(
  const livox_ros_driver2::msg::CustomMsg & msg,
  uint32_t point_count,
  int max_points)
{
  sensor_msgs::msg::PointCloud2 cloud;
  cloud.header = msg.header;
  cloud.height = 1;
  cloud.is_bigendian = false;
  cloud.is_dense = false;
  cloud.fields = {
    make_field("x", 0),
    make_field("y", 4),
    make_field("z", 8),
    make_field("intensity", 12),
  };
  cloud.point_step = 16;

  const auto bounded_count = static_cast<uint32_t>(
    std::min<size_t>(static_cast<size_t>(point_count), msg.points.size()));
  const auto point_limit = std::max(0, max_points);
  const auto sample_every = point_limit <= 0 || bounded_count <= static_cast<uint32_t>(point_limit)
    ? 1U
    : static_cast<uint32_t>(
        std::ceil(static_cast<double>(bounded_count) / static_cast<double>(point_limit)));
  const auto sampled_count = sample_every == 0 ? 0U : ((bounded_count + sample_every - 1U) / sample_every);
  cloud.width = sampled_count;
  cloud.row_step = cloud.point_step * cloud.width;
  cloud.data.resize(static_cast<size_t>(cloud.row_step));

  size_t output_index = 0;
  for (uint32_t i = 0; i < bounded_count; i += sample_every) {
    const auto & point = msg.points[i];
    const auto base = output_index * cloud.point_step;
    write_le<float>(cloud.data, base, point.x);
    write_le<float>(cloud.data, base + 4, point.y);
    write_le<float>(cloud.data, base + 8, point.z);
    write_le<float>(cloud.data, base + 12, static_cast<float>(point.reflectivity));
    ++output_index;
  }
  return cloud;
}

}  // namespace web_livox_observer
