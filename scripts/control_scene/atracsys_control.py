import time
import csv
from ambf_client import Client
from geometry_msgs.msg import Pose
import numpy as np
from tf_transformations import (
    quaternion_matrix,
    quaternion_from_matrix
)


def pose_to_matrix(pose: Pose):
    q = pose.orientation
    t = pose.position

    # quaternion → 4x4 rotation matrix
    T = quaternion_matrix([q.x, q.y, q.z, q.w])

    # insert translation
    T[0:3, 3] = [t.x, t.y, t.z]

    return T

def matrix_to_pose(T):
    pose = Pose()

    # translation
    pose.position.x = T[0, 3]
    pose.position.y = T[1, 3]
    pose.position.z = T[2, 3]

    # rotation
    q = quaternion_from_matrix(T)
    pose.orientation.x = q[0]
    pose.orientation.y = q[1]
    pose.orientation.z = q[2]
    pose.orientation.w = q[3]

    return pose

############
# Temp solution (ROS2 init required by your environment)
############
import rclpy
rclpy.init()
node = rclpy.create_node("pose_player_node")
time.sleep(0.4)
############

CSV_FILE = "../../resources/ros2_test_assets/phantom01/atracsys_touching_surface.csv"   # <-- change to your csv file path
APPLY_PERIOD = 0.01       # 100 ms

# -------------------------
# Connect to AMBF
# -------------------------
client = Client("client")
client.connect()

print("Connected to AMBF")

drill_body_handle = client.get_obj_handle("drill_body_4mm")
drill_marker_handle = client.get_obj_handle("marker")
drill_tip_handle = client.get_obj_handle("drill_tip")

if drill_marker_handle is None or drill_tip_handle is None:
    raise RuntimeError("Could not retrieve drill handles")

print("Handles acquired")

pivot_pose = Pose()

# Position
pivot_pose.position.x = 0.125657
pivot_pose.position.y = -0.137231
pivot_pose.position.z = -0.0570812

# Orientation (quaternion)
pivot_pose.orientation.x = 1.0 
pivot_pose.orientation.y = 0.0 
pivot_pose.orientation.z = 0.0 
pivot_pose.orientation.w = 0.0 

marker_T_tip = pose_to_matrix(pivot_pose)

print(marker_T_tip)

# -------------------------
# Read CSV and apply poses
# -------------------------
with open(CSV_FILE, "r") as f:
    reader = csv.reader(f)

    for row in reader:
        # Skip empty lines
        if not row:
            continue

        # Skip header if present
        if row[0].strip().lower() == "x":
            continue

        x, y, z, rx, ry, rz, rw = map(float, row)

        body_pose = Pose()

        # Position
        body_pose.position.x = x
        body_pose.position.y = y
        body_pose.position.z = z

        # Orientation (quaternion)
        body_pose.orientation.x = rx
        body_pose.orientation.y = ry
        body_pose.orientation.z = rz
        body_pose.orientation.w = rw

        world_T_marker = pose_to_matrix(body_pose)

        world_T_tip =  world_T_marker @ marker_T_tip 

        tip_final_pose = matrix_to_pose(world_T_tip)

        ## Body drill - rotate 180 degrees about y
        tip_T_body = np.identity(4)
        tip_T_body[0,0] = -1.0
        tip_T_body[2,2] = -1.0
        
        world_T_body = world_T_tip @ tip_T_body
        body_final_pose = matrix_to_pose(world_T_body)

        # Apply to both handles
        drill_body_handle.set_pose(body_final_pose)
        drill_tip_handle.set_pose(tip_final_pose)
        drill_marker_handle.set_pose(body_pose)

        time.sleep(APPLY_PERIOD)

client.clean_up()
rclpy.shutdown()
print("Finished applying poses")
