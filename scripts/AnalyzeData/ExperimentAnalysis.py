from collections import defaultdict
import sys
import pandas as pd

from pydrilling.Recording import Recording

sys.path.append(__file__)

from pydrilling.Metrics.PerformanceMetrics import PerformanceMetrics
from pathlib import Path
from natsort import natsorted

# fmt:off

# Experiments Metadata
# Array indicating which anatomy was used in each trial
# Keys indicated the attempt number - values indicate the anatomy used. (In guidance dict, the anatomy and the modality are indicated.)

metadata = {"Participant_1": {"Baseline":{0:"D",1:"E",2:"A",3:"B",4:"C"},
                              "Guidance":{0:["B","Haptic"]}},
            "Participant_2": {"Baseline":{0:"D",1:"E"},
                              "Guidance":{0:["E","Haptic"]}},
            "Participant_3": {"Baseline":{0:"E",1:"A",2:"C"},
                              "Guidance":{0:["E","Haptic"],1:["A","Visual"]}},
            "Participant_4": {"Baseline":{0:"B"},
                              "Guidance":{0:["D","Audio"],1:["D","Visual"],2:["D","Baseline"],3:["D","Haptic"],
                                          4:["E","Baseline"],5:["E","Visual"],6:["E","Haptic"],7:["E","Audio"]}}
                              }

# fmt:on


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

    # Calculate metrics
    results = []
    for participant_id, data_paths in participant_dict.items():
        for mode in ["Guidance", "Baseline"]:
            for trial_idx, trial_path in enumerate(data_paths[mode]):
                if mode == "Guidance":
                    anatomy, guidance_type = metadata[participant_id][mode][trial_idx]
                else:
                    anatomy = metadata[participant_id][mode][trial_idx]
                    guidance_type = mode

                trial_meta_data = {
                    "participant_id": participant_id,
                    "guidance_modality": guidance_type,
                    "anatomy": anatomy,
                    "trial_idx": trial_idx,
                }

                with Recording(trial_path, **trial_meta_data) as recording:
                    print(f"Read {len(recording)} h5 files for {recording.participant_id}")
                    metrics = PerformanceMetrics(recording, generate_first_vid=True)
                    results.append(metrics.generate_summary_dataframe())

    results_df = pd.concat(results)
    results_df = results_df.reset_index(drop=True)
    results_df = results_df.sort_values(["participant_id", "anatomy", "trial_idx"])
    results_df.to_csv(root / "results.csv", index=None)

    print(results_df)


if __name__ == "__main__":
    analyze_experiment()
