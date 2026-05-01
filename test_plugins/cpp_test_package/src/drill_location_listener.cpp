#include <functional>
#include <memory>

#include "geometry_msgs/msg/point_stamped.hpp"
#include "rclcpp/rclcpp.hpp"

class DrillLocationListener : public rclcpp::Node {
public:
  DrillLocationListener() : Node("drill_location_listener") {
    subscription_ = this->create_subscription<geometry_msgs::msg::PointStamped>(
      "/ambf/env/plugin/volumetric_drilling/drill_location_in_volume",
      10,
      std::bind(&DrillLocationListener::on_point_received, this, std::placeholders::_1));

    RCLCPP_INFO(
      this->get_logger(),
      "Listening on /ambf/env/plugin/volumetric_drilling/drill_location_in_volume");
  }

private:
  void on_point_received(const geometry_msgs::msg::PointStamped::SharedPtr msg) const {
    const auto & stamp = msg->header.stamp;
    RCLCPP_INFO(
      this->get_logger(),
      "PointStamped t=%d.%09u x=%.6f, y=%.6f, z=%.6f",
      stamp.sec,
      stamp.nanosec,
      msg->point.x,
      msg->point.y,
      msg->point.z);
  }

  rclcpp::Subscription<geometry_msgs::msg::PointStamped>::SharedPtr subscription_;
};

int main(int argc, char * argv[]) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<DrillLocationListener>());
  rclcpp::shutdown();
  return 0;
}
