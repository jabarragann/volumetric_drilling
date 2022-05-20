from argparse import ArgumentParser

import h5py
import matplotlib.pyplot as plt
import numpy as np

from data_validation import pose_to_matrix


def view_data():
    for i in range(l_img.shape[0]):
        plt.subplot(221)
        plt.imshow(l_img[i])
        plt.subplot(222)
        plt.imshow(r_img[i])
        plt.subplot(223)
        plt.imshow(depth[i], vmax=1)
        plt.subplot(224)
        plt.imshow(segm[i])

        plt.show()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('--file', type=str, default=None)
    args = parser.parse_args()

    if args.file is not None:
        file = h5py.File(args.file, 'r')
        print(file.keys()) # ['burr_change', 'data', 'metadata', 'voxels_removed']
        print(file["data"].keys()) # ['depth', 'l_img', 'pose_main_camera', 'pose_mastoidectomy_drill', 'r_img', 'segm', 'time']
        print(file["voxels_removed"].keys()) # ['time_stamp', 'voxel_color', 'voxel_removed']
        removed_time = file["voxels_removed"]['time_stamp'][()]
        removed_color = file["voxels_removed"]['voxel_color'][()]
        removed_voxel = file["voxels_removed"]['voxel_removed'][()]


        removed_anatomy_index = []

        for i in range(removed_color.shape[0]):
            # bone color = [255, 249, 219, 255]
            if not (removed_color[i][0] == 255 and removed_color[i][1] == 249 and removed_color[i][2] ==219):
                removed_anatomy_index.append(i)
        
        time = file["data"]["time"][()]
        print("time:", time[-1] - time[0])
        print("removed_time;", removed_time[-1] - removed_time[0])
        # print(removed_color.shape)  
        # print(len(removed_anatomy_index))

        removed_anatomy_color = []
        for j in range(len(removed_anatomy_index)):
            if len(removed_anatomy_color) == 0:
                removed_anatomy_color.append(removed_color[removed_anatomy_index[j]])
            else:
                flag_new = True
                for k in range(len(removed_anatomy_color)):
                    if (removed_anatomy_color[k][0] == removed_color[removed_anatomy_index[j]][0] and 
                    removed_anatomy_color[k][1] == removed_color[removed_anatomy_index[j]][1] and 
                    removed_anatomy_color[k][2] == removed_color[removed_anatomy_index[j]][2]):
                        flag_new = False
                if flag_new == True:
                    removed_anatomy_color.append(removed_color[removed_anatomy_index[j]])  
        
        print("removed structure color:", removed_anatomy_color)

        # Commented out form original 
        # l_img = file["data"]["l_img"][()]
        # r_img = file["data"]["r_img"][()]
        # depth = file["data"]["depth"][()]
        # segm = file["data"]["segm"][()]
        # K = file['metadata']["camera_intrinsic"][()]
        # extrinsic = file['metadata']['camera_extrinsic'][()]

        # pose_cam = pose_to_matrix(file['data']['pose_main_camera'][()])
        # pose_cam = np.matmul(pose_cam, np.linalg.inv(extrinsic)[None])  # update pose so world directly maps to CV
        # pose_drill = pose_to_matrix(file['data']['pose_mastoidectomy_drill'][()])

        # view_data()
