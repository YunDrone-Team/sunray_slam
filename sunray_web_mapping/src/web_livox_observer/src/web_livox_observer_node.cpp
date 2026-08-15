#include <algorithm>
#include <chrono>
#include <cstdint>
#include <sstream>
#include <string>

#include "livox_ros_driver2/msg/custom_msg.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "std_msgs/msg/string.hpp"
#include "web_livox_observer/preview.hpp"

namespace
{

using Clock = std::chrono::steady_clock;
using LivoxCustomMsg = livox_ros_driver2::msg::CustomMsg;

double stamp_to_sec(const builtin_interfaces::msg::Time & stamp)
{
  return static_cast<double>(stamp.sec) + static_cast<double>(stamp.nanosec) * 1e-9;
}

std::string json_escape(const std::string & text)
{
  std::ostringstream out;
  for (const char ch : text) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        out << ch;
        break;
    }
  }
  return out.str();
}

}  // namespace

class WebLivoxObserver : public rclcpp::Node
{
public:
  WebLivoxObserver()
  : Node("web_livox_observer")
  {
    livox_custom_topic_ = declare_parameter<std::string>("livox_custom_topic", "/livox/lidar");
    imu_topic_ = declare_parameter<std::string>("imu_topic", "/livox/imu");
    raw_cloud_topic_ = declare_parameter<std::string>("raw_cloud_topic", "/web_mapping/raw_cloud");
    web_imu_topic_ = declare_parameter<std::string>("web_imu_topic", "/web_mapping/imu");
    raw_observation_topic_ =
      declare_parameter<std::string>("raw_observation_topic", "/web_mapping/raw_observation");
    max_raw_points_per_cloud_ = declare_parameter<int>("max_raw_points_per_cloud", 15000);
    min_raw_cloud_interval_sec_ = declare_parameter<double>("min_raw_cloud_interval_sec", 0.3);
    web_imu_min_interval_sec_ = declare_parameter<double>("web_imu_min_interval_sec", 0.1);
    publish_raw_cloud_ = declare_parameter<bool>("publish_raw_cloud", true);

    auto sensor_qos = rclcpp::QoS(rclcpp::KeepLast(5)).best_effort().durability_volatile();
    auto reliable_qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();

    raw_observation_pub_ = create_publisher<std_msgs::msg::String>(raw_observation_topic_, reliable_qos);
    raw_cloud_pub_ = create_publisher<sensor_msgs::msg::PointCloud2>(raw_cloud_topic_, sensor_qos);
    imu_pub_ = create_publisher<sensor_msgs::msg::Imu>(web_imu_topic_, sensor_qos);

    if (!livox_custom_topic_.empty()) {
      livox_sub_ = create_subscription<LivoxCustomMsg>(
        livox_custom_topic_, sensor_qos,
        std::bind(&WebLivoxObserver::livox_callback, this, std::placeholders::_1));
    }
    if (!imu_topic_.empty()) {
      imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
        imu_topic_, sensor_qos,
        std::bind(&WebLivoxObserver::imu_callback, this, std::placeholders::_1));
    }

    RCLCPP_INFO(
      get_logger(),
      "Web Livox observer: raw=%s -> %s, imu=%s -> %s",
      livox_custom_topic_.c_str(), raw_cloud_topic_.c_str(),
      imu_topic_.c_str(), web_imu_topic_.c_str());
  }

private:
  void livox_callback(const LivoxCustomMsg::SharedPtr msg)
  {
    const auto point_count = static_cast<uint32_t>(
      std::min<size_t>(static_cast<size_t>(msg->point_num), msg->points.size()));
    publish_raw_observation(*msg, point_count);

    if (!publish_raw_cloud_ || raw_cloud_pub_->get_subscription_count() == 0) {
      return;
    }

    const auto now = Clock::now();
    const auto min_interval = std::chrono::duration<double>(
      std::max(0.0, min_raw_cloud_interval_sec_));
    if (raw_cloud_published_ && now - last_raw_cloud_published_at_ < min_interval) {
      return;
    }
    raw_cloud_published_ = true;
    last_raw_cloud_published_at_ = now;

    raw_cloud_pub_->publish(web_livox_observer::makeRawCloudPreview(
      *msg, point_count, max_raw_points_per_cloud_));
  }

  void imu_callback(const sensor_msgs::msg::Imu::SharedPtr msg)
  {
    if (imu_pub_->get_subscription_count() == 0) {
      return;
    }
    const auto now = Clock::now();
    const auto min_interval = std::chrono::duration<double>(
      std::max(0.0, web_imu_min_interval_sec_));
    if (imu_published_ && now - last_imu_published_at_ < min_interval) {
      return;
    }
    imu_published_ = true;
    last_imu_published_at_ = now;
    imu_pub_->publish(*msg);
  }

  void publish_raw_observation(const LivoxCustomMsg & msg, uint32_t point_count)
  {
    if (raw_observation_pub_->get_subscription_count() == 0) {
      return;
    }
    std::ostringstream payload;
    payload << "{\"topic\":\"" << json_escape(livox_custom_topic_) << "\""
            << ",\"frame_id\":\"" << json_escape(msg.header.frame_id) << "\""
            << ",\"point_count\":" << point_count
            << ",\"stamp_sec\":" << stamp_to_sec(msg.header.stamp)
            << "}";
    std_msgs::msg::String out;
    out.data = payload.str();
    raw_observation_pub_->publish(out);
  }

  std::string livox_custom_topic_;
  std::string imu_topic_;
  std::string raw_cloud_topic_;
  std::string web_imu_topic_;
  std::string raw_observation_topic_;
  int max_raw_points_per_cloud_ = 15000;
  double min_raw_cloud_interval_sec_ = 0.3;
  double web_imu_min_interval_sec_ = 0.1;
  bool publish_raw_cloud_ = true;
  bool raw_cloud_published_ = false;
  bool imu_published_ = false;
  Clock::time_point last_raw_cloud_published_at_;
  Clock::time_point last_imu_published_at_;

  rclcpp::Subscription<LivoxCustomMsg>::SharedPtr livox_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr raw_observation_pub_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr raw_cloud_pub_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_pub_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<WebLivoxObserver>());
  rclcpp::shutdown();
  return 0;
}
