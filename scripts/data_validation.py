import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation as R
from utils import *

def verify_xyz(depth, K):
    h, w = depth.shape[1:3]
    u, v = np.meshgrid(np.arange(0, w), np.arange(0, h))
    uv = np.stack([u, v], axis=-1)
    uv_one = np.concatenate([uv, np.ones([h, w, 1])], axis=-1)[None]  # 1xHxWx3
    uvz = uv_one * depth[..., -1][..., None]  # NxHxWx3
    K_inv = np.linalg.inv(K)  # 3x3
    xyz = np.einsum('ab,nhwb->nhwa', K_inv, uvz)

    assert np.all(np.isclose(xyz, depth, rtol=0.01, atol=1e-3)
                  ), "Analytical result doesn't match emperical result"


def pose_to_matrix(pose):
    quat_norm = np.linalg.norm(pose[:, 3:], axis=-1)
    assert np.all(np.isclose(quat_norm, 1.0))
    r = R.from_quat(pose[:, 3:]).as_matrix()
    t = pose[:, :3]
    tau = np.identity(4)[None].repeat(pose.shape[0], axis=0)
    tau[:, :3, :3] = r
    tau[:, :3, -1] = t

    return tau


def verify_sphere(depth, K, RT, pose_cam, pose_primitive, time_stamps):
    # simple test, querying a point on the sphere
    query_point = np.array([1, 0, 0, 1])[None, :, None]  # homo, Nx4x1
    query_point_c = np.linalg.inv(pose_cam) @ (pose_primitive @ query_point)
    query_point_c = RT @ query_point_c
    uvz = K @ query_point_c[..., :3, :]
    u = np.rint((uvz[..., 0, :] / uvz[..., -1, :]).squeeze()).astype(int)
    v = np.rint((uvz[..., 1, :] / uvz[..., -1, :]).squeeze()).astype(int)
    z = uvz[..., -1, :].squeeze()

    h, w = depth.shape[1:3]

    # make sure point is within image
    valid_u = np.logical_and(0 <= u, u < w)
    valid_v = np.logical_and(0 <= v, v < h)
    valid = np.logical_and(valid_u, valid_v)
    depth_output = np.array([depth[idx, v_, u_]
                            for idx, (v_, u_) in enumerate(zip(v, u))])
    depth_output = depth_output[valid]
    time_stamps = time_stamps[valid]
    pose_cam = pose_cam[valid]
    for i in range(len(depth_output)):
        z_act = z[i]
        z_mea = depth_output[i]
        ts = time_stamps[i]
        err = z_act - z_mea
        time_str = INFO_STR("t: " + "{:10.6f}".format(ts))
        cam_xyz = pose_cam[i][0:3, 3]
        lag_lead_str = ""
        cam_pose_str = "Cam Z: " + toStr(cam_xyz[0])
        error_str = "Anal_z: " + \
            toStr(z_act) + " Depth_z: " + toStr(z_mea) + " Diff: "
        if abs(err) < 0.01:
            error_str = error_str + " " + OK_STR(err)
        else:
            error_str = error_str + " " + FAIL_STR(err)
            if i > 0:
                if z_mea == depth_output[i-1]:
                    lag_lead_str = WARN_STR("LAG")
                else:
                    lag_lead_str = WARN2_STR("LEAD")
        print(time_str, cam_pose_str, error_str, lag_lead_str)
    # print(depth_output)
    assert np.all(np.isclose(z, depth_output, rtol=0.01)
                  ), "fail, largest error %f" % (np.max(np.abs(z - depth_output)))

    print("pass")

    return


def verify_cube(depth, K, RT, poses):
    # TODO
    return


def verify_cylinder(depth, K, RT, poses):
    # TODO
    return


f = h5py.File(
    '/home/adnan/ambf_plugins/volumetric_drilling/scripts/data/test.hdf5', 'r')
intrinsic = f['metadata']['camera_intrinsic'][()]
extrinsic = f['metadata']['camera_extrinsic'][()]

depth = f['data']['depth'][()]
time_stamps = f['data']['time'][()]
np.set_printoptions(suppress=True, formatter={'float_kind':'{:f}'.format})
# verify_xyz(depth, intrinsic)
# plt.imshow(depth[0].astype(np.float32))
# plt.show()

# img = f['data']['l_img'][()]
# plt.imshow(img[0])
# plt.show()

pose_cam = pose_to_matrix(f['data']['pose_main_camera'][()])
pose_sphere = pose_to_matrix(f['data']['pose_Sphere'][()])

verify_sphere(depth, intrinsic, extrinsic, pose_cam, pose_sphere, time_stamps)
# print(intrinsics)
# print(depth.shape)
#
# plt.imshow(depth[0, ..., -1].astype(np.float32))
# plt.show()
