from plyfile import PlyData
import numpy as np
import csv

# Load the PLY and extract 'quality'
plydata = PlyData.read('//home/juan95/research/discovery_grant/user_studies/experimental_data/20241217_Andy_experiment/ExperimentAnalysis/MeshlabAnalysis/drilled_region_only_with_colored_errors.ply')
quality = np.array(plydata['vertex'].data['quality'])

# Total number of vertices
total = len(quality)

# Define bins
range_labels = ["0–1 mm", "1–2 mm", ">2 mm"]
counts = [
    np.sum((np.abs(quality) >= 0) & (np.abs(quality) < 1)),
    np.sum((np.abs(quality) >= 1) & (np.abs(quality) < 2)),
    np.sum(np.abs(quality) >= 2)
]

# Compute percentages
percentages = [round(100 * c / total, 2) for c in counts]

# Write to CSV
with open("vertex_error_distribution.csv", mode="w", newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Error Range", "Count", "Percentage"])
    for label, count, percent in zip(range_labels, counts, percentages):
        writer.writerow([label, count, f"{percent}%"])

print("Saved to vertex_error_distribution.csv")
