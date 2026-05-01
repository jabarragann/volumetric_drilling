cmake_minimum_required(VERSION 3.8)
project(cpp_test_package)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)

add_executable(drill_location_listener src/drill_location_listener.cpp)
ament_target_dependencies(drill_location_listener rclcpp geometry_msgs)

install(TARGETS
  drill_location_listener
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
