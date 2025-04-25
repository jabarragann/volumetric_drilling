import matplotlib.pyplot as plt
import matplotlib.colorbar as colorbar
import matplotlib.colors as colors
import numpy as np

max_val = 3.5 
min_val = -3.5
num_of_ticks = 9

# Create a figure and axis for the color bar with extra padding
fig, ax = plt.subplots(figsize=(1.5, 6))  # Increase width for left/right padding

# Define the colormap and normalization for the color bar
cmap = plt.get_cmap("turbo")  # Replace with your preferred colormap
norm = colors.Normalize(vmin=min_val, vmax=max_val)

# Create the color bar
cb = colorbar.ColorbarBase(ax, cmap=cmap, norm=norm, orientation="vertical")

# Set color bar label with increased font size and unit
cb.set_label("SDF distance to reference mesh (mm)", fontsize=14, labelpad=20)
cb.ax.tick_params(labelsize=12)  # Increase tick font size

ticks = np.linspace(min_val, max_val, num_of_ticks).tolist()
ticks_str = [f"{t:0.1f}" for t in ticks]
cb.set_ticks(ticks)  # Explicitly set tick positions
cb.set_ticklabels(ticks_str)  # Set the labels accordingly

print(ticks)
print(ticks_str)

# Add padding around the color bar
plt.subplots_adjust(left=0.3, right=0.7)

# Save the color bar as an image if needed
plt.savefig("color_map_bar.png", dpi=300, bbox_inches="tight", transparent=True)
plt.show()
