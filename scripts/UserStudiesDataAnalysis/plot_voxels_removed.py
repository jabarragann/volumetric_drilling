from mpl_toolkits import mplot3d
import matplotlib.pyplot as plt
import h5py
import numpy as np

from pydrilling.DataUtils.DataMerger import DataMerger

params = {
    "legend.fontsize": "x-large",
    "figure.figsize": (9, 5),
    "axes.labelsize": "large",
    "axes.titlesize": "x-large",
    "xtick.labelsize": "medium",
    "ytick.labelsize": "medium",
}

plt.rcParams.update(params)

def rgb_to_hex(r, g, b):
    return '#%02x%02x%02x' % (int(r), int(g), int(b))

files = []
files.append(['P1', '/home/amunawa2/Downloads/2022-11-03 14.00.17'])
# files.append(['P2', '/home/amunawa2/RedCap/Baseline/Participant_2/2022-11-04 11.56.44'])
# files.append(['P3', '/home/amunawa2/RedCap/Guidance/Participant_3/2022-11-04 14.59.22'])
# files.append(['P4', '/home/amunawa2/RedCap/Guidance/Participant_4/2022-11-09 19:26:43'])
# files.append(['P5', '/home/amunawa2/RedCap/Guidance/Participant_5/2022-11-10 12:54:16'])
# files.append(['P6', '/home/amunawa2/RedCap/Guidance/Participant_6/2022-11-10 18:16:42'])
# files.append(['P7', '/home/amunawa2/RedCap/Guidance/Participant_7/2022-11-11 10:42:18'])

data_merger = DataMerger()

for lab, f in files:
    data = data_merger.get_merged_data(f, False)

    vrm = data['voxels_removed']['voxel_removed'][()]
    vcol = data['voxels_removed']['voxel_color'][()]

    colors = [None for _ in range(vcol.shape[0])]

    for i, c in enumerate(vcol):
        colors[i] = rgb_to_hex(c[1], c[2], c[3])

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(vrm[:, 1], vrm[:, 2], vrm[:, 3], alpha=.3, c=colors)
    # ax.scatter([1, 2, 3], [5, 6, 4], [9, 5, 4], label="X")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    # plt.legend(["Dura", "Tegmen"])
    plt.title('Removed Voxels')
    plt.show()
    # plt.savefig('/home/amunawa2/Desktop/voxels_removed_' + lab + '.png')
