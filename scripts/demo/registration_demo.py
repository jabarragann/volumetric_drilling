import numpy as np
import matplotlib.pyplot as plt


# ----------------------------
# Target points
# ----------------------------
target = np.array([
    [0.191725, 0.0755409, 1.48524],
    [0.168758, 0.107173, 1.49484],
    [0.164905, 0.110339, 1.51358],
    [0.24607 , 0.110133, 1.52176],
    [0.244032, 0.111786, 1.53085],
    [0.220968, 0.0840052,1.54905],
])

# ----------------------------
# Source points
# ----------------------------
  # F_01_LOC: &F_01_LOC_ANCHOR {x: 4.411350858176039946e-02, y: -2.482102601740785938e-02, z: 7.996098933120956986e-02}
  # F_03_LOC: &F_03_LOC_ANCHOR {x: 7.458395140149765012e-02, y: -4.418101501464843928e-02, z: 6.243847469031103825e-02}
  # F_05_LOC: &F_05_LOC_ANCHOR {x: 7.430971401232361329e-02, y: -4.445639201099024079e-02, z: 4.231952203678550350e-02}
  # F_07_LOC: &F_07_LOC_ANCHOR {x: 7.237673113282701298e-02, y: 3.580897270238159180e-02, z: 5.121548843383789268e-02}
  # F_08_LOC: &F_08_LOC_ANCHOR {x: 7.225195099456280245e-02, y: 3.572770005819653205e-02, z: 4.148214708598595840e-02}
  # F_14_LOC: &F_14_LOC_ANCHOR {x: 4.255372797390247208e-02, y: 1.452212333679199323e-02, z: 2.449729537963867346e-02}

source = np.array([
    [4.411350858176039946e-02, -2.482102601740785938e-02, 7.996098933120956986e-02],
    [7.458395140149765012e-02, -4.418101501464843928e-02, 6.243847469031103825e-02],
    [7.430971401232361329e-02, -4.445639201099024079e-02, 4.231952203678550350e-02],
    [7.237673113282701298e-02,  3.580897270238159180e-02, 5.121548843383789268e-02],
    [7.225195099456280245e-02,  3.572770005819653205e-02, 4.148214708598595840e-02],
    [4.255372797390247208e-02,  1.452212333679199323e-02, 2.449729537963867346e-02],
])


# ----------------------------
# Rigid transform (Kabsch)
# ----------------------------
def rigid_transform(A, B):
    centroid_A = A.mean(axis=0)
    centroid_B = B.mean(axis=0)

    AA = A - centroid_A
    BB = B - centroid_B

    H = AA.T @ BB
    U, S, Vt = np.linalg.svd(H)

    R = Vt.T @ U.T

    if np.linalg.det(R) < 0:
        Vt[2, :] *= -1
        R = Vt.T @ U.T

    t = centroid_B - R @ centroid_A
    return R, t


# ----------------------------
# Visualization
# ----------------------------
def plot_registration(source, target, source_aligned):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(target[:,0], target[:,1], target[:,2],
               label="Target", s=80)

    ax.scatter(source_aligned[:,0], source_aligned[:,1], source_aligned[:,2],
               label="Source (aligned)", marker='^', s=80)

    # draw correspondence lines
    for i in range(len(target)):
        ax.plot([source_aligned[i,0], target[i,0]],
                [source_aligned[i,1], target[i,1]],
                [source_aligned[i,2], target[i,2]])

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.legend()
    plt.show()


# ----------------------------
# Run registration
# ----------------------------
R, t = rigid_transform(source, target)

source_aligned = (R @ source.T).T + t

rmse = np.sqrt(np.mean(np.sum((source_aligned - target)**2, axis=1)))

print("Rotation matrix:\n", R)
print("\nTranslation:\n", t)
print("\nRMSE:", rmse)

plot_registration(source, target, source_aligned)
