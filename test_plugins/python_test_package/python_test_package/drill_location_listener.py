#!/usr/bin/env python3

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node


class DrillLocationListener(Node):
    def __init__(self) -> None:
        super().__init__("drill_location_listener")
        self._subscription = self.create_subscription(
            PointStamped,
            "/ambf/env/plugin/volumetric_drilling/drill_location_in_volume",
            self._on_point_received,
            10,
        )
        self.get_logger().info(
            "Listening on /ambf/env/plugin/volumetric_drilling/drill_location_in_volume"
        )

    def _on_point_received(self, msg: PointStamped) -> None:
        stamp = msg.header.stamp
        self.get_logger().info(
            f"PointStamped t={stamp.sec}.{stamp.nanosec:09d} "
            f"x={msg.point.x:.6f}, y={msg.point.y:.6f}, z={msg.point.z:.6f}"
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DrillLocationListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
