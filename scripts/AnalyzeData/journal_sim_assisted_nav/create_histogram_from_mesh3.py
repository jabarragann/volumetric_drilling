from plyfile import PlyData
import numpy as np
import matplotlib.pyplot as plt

# Load the PLY file and extract 'quality'
plydata = PlyData.read('/home/juan95/Downloads/SimAssistedPaper/meshlab_nice/drilled_area.ply')
quality = np.array(plydata['vertex'].data['quality'])

quality_max = np.max(quality)
quality_min = np.min(quality)
print(f"quality max {quality_max} quality_min {quality_min}")

# Create horizontal histogram
counts, bins, patches = plt.hist(quality, bins=50, orientation='horizontal', edgecolor='none')

# Color bars by vertical bin position (bin center)
bin_centers = 0.5 * (bins[:-1] + bins[1:])
norm = plt.Normalize(min(bin_centers), max(bin_centers))
cmap = plt.colormaps['turbo']

for center, patch in zip(bin_centers, patches):
    patch.set_facecolor(cmap(norm(center)))

# Clean the plot appearance
ax = plt.gca()
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['bottom'].set_visible(False)
ax.xaxis.set_visible(False)  # Remove x-axis (frequency)
ax.tick_params(axis='y', labelsize=13)

plt.ylabel('Distance from reference mesh (mm)', fontsize=15)
plt.tight_layout()

# Save with transparent background
plt.savefig("histogram_quality.png", dpi=300, transparent=True)
plt.show()
