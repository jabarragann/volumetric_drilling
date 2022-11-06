from collections import defaultdict
import sys

sys.path.append(__file__)

from PerformanceMetrics import PerformanceMetrics
from pathlib import Path
from natsort import natsorted


def analyze_experiment():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap")

    if not root.exists():
        print("path does not exists")
        exit(0)

    participant_dict = defaultdict(lambda: {"Guidance": [], "Baseline": []})

    for file in root.glob("*/*/*"):
        # File structure ~/path2data/RedCap/mode/partipant_id/
        participant_id = file.parent.name
        mode = file.parent.parent.name
        participant_dict[participant_id][mode].append(file)

    # Sort attempts
    participant_dict = dict(participant_dict)
    for k, v in participant_dict.items():
        v["Guidance"] = natsorted(v["Guidance"])
        v["Baseline"] = natsorted(v["Baseline"])

    for participant_id, data_paths in participant_dict.items():
        print(participant_id)
        for mode in ["Guidance", "Baseline"]:
            print(mode)
            for trial in data_paths[mode]:
                PerformanceMetrics(trial)
                # print(f"Error with trial {trial.name}")


if __name__ == "__main__":
    analyze_experiment()
