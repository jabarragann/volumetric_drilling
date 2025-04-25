from plyfile import PlyData
import numpy as np
import matplotlib.pyplot as plt

# Load the PLY file
plydata = PlyData.read('/home/juan95/Downloads/SimAssistedPaper/meshlab_nice/drilled_area.ply')

# Extract 'quality' values
quality = np.array(plydata['vertex'].data['quality'])

# Create histogram
counts, bins, patches = plt.hist(quality, bins=50, edgecolor='black')

# Color bars by bin center using turbo colormap
bin_centers = 0.5 * (bins[:-1] + bins[1:])
norm = plt.Normalize(min(bin_centers), max(bin_centers))
cmap = plt.colormaps['turbo']

for center, patch in zip(bin_centers, patches):
    patch.set_facecolor(cmap(norm(center)))

# Optional colorbar
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
plt.colorbar(sm, label='Quality (mm)')

# Custom plot appearance
plt.xlabel('Quality (mm)')
plt.ylabel('Frequency')
plt.title('Histogram of Vertex Quality')
plt.grid(False)  # No grid
plt.tight_layout()
plt.show()
