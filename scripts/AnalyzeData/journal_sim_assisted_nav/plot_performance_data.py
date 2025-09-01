import csv
import matplotlib.pyplot as plt
import numpy as np

time = []
graphics = []
physics = []

with open("performance.txt", "r") as f:
    reader = csv.reader(f, delimiter=",")
    header = next(reader)  # Skip header if present
    for row in reader:
        t, xv, yv = map(float, row)
        time.append(t)
        graphics.append(xv)
        physics.append(yv)

# Remove the first time from all time values
time0 = time[0]
time = [t - time0 for t in time]

graphics_mean = np.mean(graphics)

fig, axs = plt.subplots(1, 2, figsize=(5, 2.5))

# axs[0].set_title("Digital twin update rates (Experiment 1)")
graphics = np.array(graphics)
physics = np.array(physics)
time = np.array(time)

downsample = 40
time = time[::downsample]
graphics = graphics[::downsample]
physics = physics[::downsample]
print(graphics.shape)
axs[0].plot(time, graphics, label="Graphics")
axs[0].set_ylabel("Graphics Update (Hz)")
axs[0].axhline(graphics_mean, color="red", linestyle=":", label=f"Mean={graphics_mean:.1f}Hz")
axs[0].set_xlabel("time (s)")
axs[0].legend()
axs[0].grid()

axs[1].plot(time, physics, label="Physics", color="orange")
axs[1].set_ylabel("Physics Update (Hz)")
axs[1].set_xlabel("time (s)")
# axs[1].set_title("Physics over time")
axs[1].grid()

plt.tight_layout()
plt.show()