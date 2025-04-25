
from plyfile import PlyData
import numpy as np
import matplotlib.pyplot as plt

# Load the PLY file and extract 'quality'
plydata = PlyData.read('/home/juan95/Downloads/SimAssistedPaper/meshlab_nice/drilled_area.ply')
quality = np.array(plydata['vertex'].data['quality'])

# Create histogram
counts, bins, patches = plt.hist(quality, bins=50, edgecolor='none')

# Color bars by bin center using turbo colormap
bin_centers = 0.5 * (bins[:-1] + bins[1:])
norm = plt.Normalize(min(bin_centers), max(bin_centers))
cmap = plt.colormaps['turbo']

for center, patch in zip(bin_centers, patches):
    patch.set_facecolor(cmap(norm(center)))

# Clean the plot
ax = plt.gca()
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_visible(False)
ax.yaxis.set_visible(False)

plt.xlabel('Distance from reference mesh (mm)', fontsize=15)
plt.xticks(fontsize=13)
plt.tight_layout()
plt.show()
