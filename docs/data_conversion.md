

# Data conversions

ROS PoseStamped to chai cTransform

```cpp
void DrillingRosPublisher::atracsys_callback(const geometry_msgs::PoseStamped &msg)
{
    cout << "Received Atracsys pose: " << msg.pose.position.x << " " << msg.pose.position.y << " " << msg.pose.position.z << endl;
    // drill_marker_from_atracsys = cVector3d(msg.pose.position.x, msg.pose.position.y, msg.pose.position.z);

    world_T_drillmarker.setLocalPos(cVector3d(msg.pose.position.x,
                                        msg.pose.position.y,
                                        msg.pose.position.z));
    cQuaternion rot(msg.pose.orientation.w,
                    msg.pose.orientation.x,
                    msg.pose.orientation.y,
                    msg.pose.orientation.z);
    cMatrix3d rotM;
    rot.toRotMat(rotM);
    world_T_drillmarker.setLocalRot(rotM);

}
```